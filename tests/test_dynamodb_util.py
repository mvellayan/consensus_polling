"""Tests for dynamodb_util — table-name env override."""

import importlib
import os
import sys


def test_table_name_env_override(monkeypatch):
    """QUERIES_TABLE / RESPONSES_TABLE env vars must override defaults."""
    monkeypatch.setenv("QUERIES_TABLE", "custom_queries")
    monkeypatch.setenv("RESPONSES_TABLE", "custom_responses")

    # Force a fresh import so module-level env reads pick up the overrides.
    sys.modules.pop("dynamodb_util", None)
    mod = importlib.import_module("dynamodb_util")

    assert mod.QUERIES_TABLE == "custom_queries"
    assert mod.RESPONSES_TABLE == "custom_responses"


def test_table_name_defaults(monkeypatch):
    """Without env vars, defaults are used."""
    monkeypatch.delenv("QUERIES_TABLE", raising=False)
    monkeypatch.delenv("RESPONSES_TABLE", raising=False)

    sys.modules.pop("dynamodb_util", None)
    mod = importlib.import_module("dynamodb_util")

    assert mod.QUERIES_TABLE == "scotus_queries"
    assert mod.RESPONSES_TABLE == "scotus_responses"


def test_removed_functions_absent():
    """Job-progress machinery must be gone."""
    sys.modules.pop("dynamodb_util", None)
    mod = importlib.import_module("dynamodb_util")
    assert not hasattr(mod, "save_job_progress")
    assert not hasattr(mod, "get_job_progress")
    assert not hasattr(mod, "_calculate_summary")
    assert hasattr(mod, "log_query")
    assert hasattr(mod, "log_response")
    assert hasattr(mod, "get_ip_query_count")
    assert hasattr(mod, "get_total_query_count")


# --- T5: GSI query + atomic counter (no full-table scans) ---

class _FakeTable:
    def __init__(self):
        self.query_calls = []
        self.update_calls = []
        self.put_calls = []
        self.get_calls = []
        self._count = 3
        self._counter_item = {"query_count": 42}

    def query(self, **kwargs):
        self.query_calls.append(kwargs)
        return {"Count": self._count}

    def scan(self, **kwargs):  # must never be called now
        raise AssertionError("scan() must not be used — GSI/counter only")

    def update_item(self, **kwargs):
        self.update_calls.append(kwargs)

    def put_item(self, **kwargs):
        self.put_calls.append(kwargs)

    def get_item(self, **kwargs):
        self.get_calls.append(kwargs)
        return {"Item": self._counter_item} if self._counter_item else {}


class _FakeResource:
    def __init__(self, table):
        self._table = table

    def Table(self, name):
        return self._table


def _load_with_fake_table(monkeypatch):
    sys.modules.pop("dynamodb_util", None)
    mod = importlib.import_module("dynamodb_util")
    table = _FakeTable()
    monkeypatch.setattr(mod, "dynamodb", _FakeResource(table))
    return mod, table


def test_ip_count_uses_gsi_not_scan(monkeypatch):
    mod, table = _load_with_fake_table(monkeypatch)
    n = mod.get_ip_query_count("1.2.3.4")
    assert n == 3
    assert len(table.query_calls) == 1
    assert table.query_calls[0]["IndexName"] == mod.IP_ADDRESS_INDEX
    assert table.query_calls[0]["Select"] == "COUNT"


def test_ip_count_localhost_short_circuits(monkeypatch):
    mod, table = _load_with_fake_table(monkeypatch)
    assert mod.get_ip_query_count("127.0.0.1") == 0
    assert table.query_calls == []  # no DynamoDB call at all


def test_total_count_reads_counter_item(monkeypatch):
    mod, table = _load_with_fake_table(monkeypatch)
    assert mod.get_total_query_count() == 42
    assert table.get_calls[0]["Key"] == {"ipaddress_timestamp": mod.TOTAL_COUNTER_KEY}


def test_total_count_zero_when_counter_absent(monkeypatch):
    mod, table = _load_with_fake_table(monkeypatch)
    table._counter_item = None
    assert mod.get_total_query_count() == 0


def test_log_query_bumps_counter(monkeypatch):
    mod, table = _load_with_fake_table(monkeypatch)
    mod.log_query("9.9.9.9", "is this constitutional?")
    assert len(table.put_calls) == 1
    assert len(table.update_calls) == 1
    upd = table.update_calls[0]
    assert upd["Key"] == {"ipaddress_timestamp": mod.TOTAL_COUNTER_KEY}
    assert "ADD" in upd["UpdateExpression"]
