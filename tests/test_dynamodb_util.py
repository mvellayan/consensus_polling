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
