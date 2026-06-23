"""Tests for the Quart streaming app — no network, AsyncOpenAI mocked."""

import json
import os
import sys
from unittest.mock import patch

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test-key")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as appmod  # noqa: E402


# --------------------------------------------------------------------------
# parse_certainty_scope
# --------------------------------------------------------------------------

def test_parse_certainty_scope_well_formed():
    resp = (
        "Support\n"
        "Certainty: [Likely] and Scope: [Narrow]\n"
        "Some reasoning paragraph."
    )
    out = appmod.parse_certainty_scope(resp)
    assert out == {"certainty": "Likely", "scope": "Narrow"}


def test_parse_certainty_scope_without_brackets():
    resp = "Overturn\nCertainty: Definitive and Scope: As-Applied\n\nbody"
    out = appmod.parse_certainty_scope(resp)
    assert out == {"certainty": "Definitive", "scope": "As-Applied"}


def test_parse_certainty_scope_missing_line2():
    out = appmod.parse_certainty_scope("Support")
    assert out == {"certainty": None, "scope": None}


def test_parse_certainty_scope_empty():
    out = appmod.parse_certainty_scope("")
    assert out == {"certainty": None, "scope": None}


def test_parse_certainty_scope_partial_only_certainty():
    resp = "Remand\nCertainty: [Qualified] but nothing else\nbody"
    out = appmod.parse_certainty_scope(resp)
    assert out == {"certainty": "Qualified", "scope": None}


def test_parse_certainty_scope_partial_only_scope():
    resp = "Remand\nScope: [Broad] and no certainty mentioned\nbody"
    out = appmod.parse_certainty_scope(resp)
    assert out == {"certainty": None, "scope": "Broad"}


def test_parse_certainty_scope_unlabeled_scope_drift():
    # Observed live: the model drops the "Scope:" label — "Certainty: Definitive | Facial".
    # The bare enum value must still be picked up.
    resp = "Overturn\nCertainty: Definitive | Facial\nbody"
    out = appmod.parse_certainty_scope(resp)
    assert out == {"certainty": "Definitive", "scope": "Facial"}


def test_parse_certainty_scope_fully_unlabeled():
    # Both labels dropped, bare values only.
    resp = "Support\nLikely, Narrow\nbody"
    out = appmod.parse_certainty_scope(resp)
    assert out == {"certainty": "Likely", "scope": "Narrow"}


def test_parse_certainty_scope_never_raises_on_garbage():
    # None-ish / weird input must not raise.
    assert appmod.parse_certainty_scope("\n\n\n") == {"certainty": None, "scope": None}


# --------------------------------------------------------------------------
# analyze_support_level
# --------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("Support\nCertainty: [Likely]", "support"),
    ("Overturn the law\nbody", "overturn"),
    ("Remand to lower court\nbody", "remand"),
    ("I am not sure about this\nbody", "unknown"),
    ("", "unknown"),
])
def test_analyze_support_level(text, expected):
    assert appmod.analyze_support_level(text) == expected


# --------------------------------------------------------------------------
# calculate_summary (tally) — REGRESSION-critical
# --------------------------------------------------------------------------

def test_calculate_summary_grouping():
    responses = [
        {"judge_title": "Chief Justice Roberts", "support_level": "support"},
        {"judge_title": "Justice Alito", "support_level": "overturn"},
        {"judge_title": "Justice Kagan", "support_level": "support"},
        {"judge_title": "Justice Thomas", "support_level": "remand"},
        {"judge_title": "Justice Barrett", "support_level": "overturn"},
    ]
    summary = appmod.calculate_summary(responses)
    assert summary["support"] == ["Chief Justice Roberts", "Justice Kagan"]
    assert summary["overturn"] == ["Justice Alito", "Justice Barrett"]
    assert summary["remand"] == ["Justice Thomas"]


def test_calculate_summary_unknown_bucket():
    responses = [{"judge_title": "Justice X"}]  # missing support_level
    summary = appmod.calculate_summary(responses)
    assert summary["unknown"] == ["Justice X"]


# --------------------------------------------------------------------------
# Fake AsyncOpenAI streaming infrastructure
# --------------------------------------------------------------------------

class _FakeEvent:
    def __init__(self, delta):
        self.type = "response.output_text.delta"
        self.delta = delta


class _FakeStream:
    """Async-iterable stream of text-delta events, or raises mid-stream."""

    def __init__(self, deltas, raise_at=None):
        self._deltas = deltas
        self._raise_at = raise_at

    def __aiter__(self):
        async def gen():
            for i, d in enumerate(self._deltas):
                if self._raise_at is not None and i == self._raise_at:
                    raise RuntimeError("simulated stream failure")
                yield _FakeEvent(d)
        return gen()


class _FakeResponses:
    def __init__(self, parent):
        self._parent = parent

    async def create(self, **kwargs):
        return self._parent._next_stream(kwargs)


class _FakeAsyncOpenAI:
    """Returns a scripted stream per call. Judge calls use file_search tools;
    the syllabus call has no tools."""

    def __init__(self, scripts):
        # scripts: dict judge_name -> (deltas, raise_at); plus "__syllabus__".
        self._scripts = scripts
        self.responses = _FakeResponses(self)

    def _next_stream(self, kwargs):
        has_tools = bool(kwargs.get("tools"))
        if not has_tools:
            deltas, raise_at = self._scripts.get("__syllabus__", (["syllabus."], None))
            return _FakeStream(deltas, raise_at)
        # Identify judge via the instructions content (contains judge title) —
        # but simplest: route by vector_store_id we stash in scripts by order.
        vsid = kwargs["tools"][0]["vector_store_ids"][0]
        deltas, raise_at = self._scripts[vsid]
        return _FakeStream(deltas, raise_at)


def _make_app_client(monkeypatch, scripts, ip_count=0):
    """Patch the module client + dynamodb + judge loading, return test client."""
    fake = _FakeAsyncOpenAI(scripts)
    monkeypatch.setattr(appmod, "client", fake)

    monkeypatch.setattr(appmod.dynamodb_util, "get_ip_query_count",
                        lambda ip: ip_count)
    monkeypatch.setattr(appmod.dynamodb_util, "log_query",
                        lambda ip, q: "qid-123")
    monkeypatch.setattr(appmod.dynamodb_util, "log_response",
                        lambda *a, **k: None)

    return appmod.app.test_client()


async def _collect_stream(test_client, payload):
    """POST and parse the NDJSON stream into a list of event dicts."""
    resp = await test_client.post("/api/query", json=payload)
    body = await resp.get_data()
    events = []
    for line in body.decode("utf-8").splitlines():
        line = line.strip()
        if line:
            events.append(json.loads(line))
    return resp, events


# --------------------------------------------------------------------------
# Streaming integration / error isolation
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_per_judge_error_isolation(monkeypatch):
    judges = {
        "roberts": {"judge_title": "Chief Justice Roberts",
                    "vector_store_id": "vs_roberts", "instructions": "x"},
        "alito": {"judge_title": "Justice Alito",
                  "vector_store_id": "vs_alito", "instructions": "x"},
        "kagan": {"judge_title": "Justice Kagan",
                  "vector_store_id": "vs_kagan", "instructions": "x"},
    }
    monkeypatch.setattr(appmod, "load_judge_assistants", lambda: judges)

    scripts = {
        "vs_roberts": (["Support\n", "Certainty: [Likely] and Scope: [Narrow]\n", "body"], None),
        # judge #2 raises mid-stream
        "vs_alito": (["Overturn\n", "boom"], 1),
        "vs_kagan": (["Remand\n", "Certainty: [Qualified] and Scope: [Broad]\n", "body"], None),
        "__syllabus__": (["A grounded ", "syllabus."], None),
    }
    tc = _make_app_client(monkeypatch, scripts)

    resp, events = await _collect_stream(
        tc, {"question": "is this legal", "judges": ["roberts", "alito", "kagan"]}
    )
    assert resp.status_code == 200

    types = [e["type"] for e in events]
    # Other judges still streamed tokens.
    roberts_tokens = [e for e in events if e["type"] == "token" and e["judge"] == "roberts"]
    kagan_tokens = [e for e in events if e["type"] == "token" and e["judge"] == "kagan"]
    assert roberts_tokens and kagan_tokens

    # judge #2 emitted a judge_error.
    errs = [e for e in events if e["type"] == "judge_error" and e["judge"] == "alito"]
    assert len(errs) == 1

    # Other judges emitted judge_done.
    dones = {e["judge"] for e in events if e["type"] == "judge_done"}
    assert "roberts" in dones and "kagan" in dones

    # tally present, syllabus streamed, terminal done.
    assert "tally" in types
    assert any(e["type"] == "syllabus_token" for e in events)
    assert types[-1] == "done"

    # Tally groups the two successful judges correctly; alito is 'unknown'.
    tally = next(e for e in events if e["type"] == "tally")["summary"]
    assert tally["support"] == ["Chief Justice Roberts"]
    assert tally["remand"] == ["Justice Kagan"]


@pytest.mark.asyncio
async def test_single_judge_tldr_path(monkeypatch):
    judges = {
        "roberts": {"judge_title": "Chief Justice Roberts",
                    "vector_store_id": "vs_roberts", "instructions": "x"},
    }
    monkeypatch.setattr(appmod, "load_judge_assistants", lambda: judges)
    scripts = {
        "vs_roberts": (["Support\n", "Certainty: [Definitive] and Scope: [Broad]\n", "body"], None),
        "__syllabus__": (["Plain ", "English ", "tldr."], None),
    }
    tc = _make_app_client(monkeypatch, scripts)
    resp, events = await _collect_stream(
        tc, {"question": "q", "judges": ["roberts"]}
    )
    assert resp.status_code == 200
    types = [e["type"] for e in events]
    assert any(e["type"] == "syllabus_token" for e in events)
    assert types[-1] == "done"
    done = next(e for e in events if e["type"] == "judge_done")
    assert done["certainty"] == "Definitive"
    assert done["scope"] == "Broad"


# --------------------------------------------------------------------------
# No query limit — IP + count are informational only
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_query_limit_high_count_still_streams(monkeypatch):
    """A high per-IP count must NOT be blocked (limit removed)."""
    judges = {
        "roberts": {"judge_title": "Chief Justice Roberts",
                    "vector_store_id": "vs_roberts", "instructions": "x"},
    }
    monkeypatch.setattr(appmod, "load_judge_assistants", lambda: judges)
    tc = _make_app_client(monkeypatch, {"vs_roberts": (["x"], None)}, ip_count=999)

    resp = await tc.post("/api/query", json={"question": "q", "judges": ["roberts"]})
    assert resp.status_code == 200  # streams, no 429


@pytest.mark.asyncio
async def test_check_limit_returns_ip_and_count(monkeypatch):
    tc = _make_app_client(monkeypatch, {}, ip_count=7)
    resp = await tc.get("/api/check-limit")
    assert resp.status_code == 200
    data = await resp.get_json()
    assert data["count"] == 7
    assert "ip_address" in data
    assert "remaining" not in data and "limit_reached" not in data


@pytest.mark.asyncio
async def test_query_requires_question(monkeypatch):
    tc = _make_app_client(monkeypatch, {})
    resp = await tc.post("/api/query", json={"question": "", "judges": ["roberts"]})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_query_requires_judges(monkeypatch):
    tc = _make_app_client(monkeypatch, {})
    resp = await tc.post("/api/query", json={"question": "q", "judges": []})
    assert resp.status_code == 400


# --------------------------------------------------------------------------
# Simple endpoints
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health(monkeypatch):
    monkeypatch.setattr(appmod, "load_judge_assistants", lambda: {"roberts": {}})
    tc = appmod.app.test_client()
    resp = await tc.get("/health")
    assert resp.status_code == 200
    data = await resp.get_json()
    assert data["status"] == "healthy"
    assert data["judges_loaded"] == 1
