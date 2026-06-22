"""
T4 eval — the grounded syllabus.

The trust-critical guarantee: the vote count is computed in code and handed to
the synthesis LLM as a FIXED fact ("DO NOT CHANGE"); the model only writes prose.
These tests assert that wiring deterministically, plus a key-gated live check.
"""

import asyncio
import os

import pytest


# --- fakes: an AsyncOpenAI stand-in that records the prompt + streams deltas ---

class _Event:
    def __init__(self, delta):
        self.type = "response.output_text.delta"
        self.delta = delta


class _FakeStream:
    def __init__(self, deltas):
        self._deltas = deltas

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        for d in self._deltas:
            yield _Event(d)


class _FakeResponses:
    def __init__(self, deltas, capture):
        self._deltas = deltas
        self._capture = capture

    async def create(self, **kwargs):
        self._capture.update(kwargs)
        return _FakeStream(self._deltas)


class _FakeClient:
    def __init__(self, deltas, capture):
        self.responses = _FakeResponses(deltas, capture)


def test_tally_string_exact():
    import app
    summary = {
        "support": ["Chief Justice Roberts", "Justice Kagan"],
        "overturn": ["Justice Alito"],
        "remand": ["Justice Thomas"],
    }
    assert app._build_tally_string(summary) == (
        "SUPPORT (2): Chief Justice Roberts, Justice Kagan\n"
        "OVERTURN (1): Justice Alito\n"
        "REMAND (1): Justice Thomas"
    )


def test_tally_string_empty():
    import app
    assert app._build_tally_string({}) == "No outcomes recorded."


async def test_grounding_passes_fixed_tally(monkeypatch):
    """N>=2: the code-computed tally + DO-NOT-CHANGE instruction reach the prompt,
    and the model is never asked to produce the count."""
    import app
    capture = {}
    monkeypatch.setattr(app, "client", _FakeClient(["The Court ", "was divided."], capture))

    summary = {
        "support": ["Chief Justice Roberts", "Justice Kagan"],
        "overturn": ["Justice Alito"],
    }
    tally = app._build_tally_string(summary)
    completed = [
        {"judge_title": "Chief Justice Roberts", "support_level": "support", "full_response": "..."},
        {"judge_title": "Justice Kagan", "support_level": "support", "full_response": "..."},
        {"judge_title": "Justice Alito", "support_level": "overturn", "full_response": "..."},
    ]
    q: asyncio.Queue = asyncio.Queue()
    text = await app._stream_syllabus(completed, tally, q)

    assert text == "The Court was divided."
    instr = capture["instructions"]
    assert tally in instr                       # the exact code-computed facts
    assert "DO NOT CHANGE" in instr             # the grounding guardrail
    assert "SUPPORT (2)" in tally and "OVERTURN (1)" in tally
    # tokens were emitted, and the drain sentinel is ALWAYS last (regression:
    # the old timeout-poll drain stranded syllabus tokens and never terminated
    # deterministically).
    kinds = []
    while not q.empty():
        kinds.append(q.get_nowait()[0])
    assert kinds[-1] == "__syllabus_done__"
    assert "syllabus_token" in kinds
    assert all(k == "syllabus_token" for k in kinds[:-1])


async def test_single_judge_uses_tldr(monkeypatch):
    """N==1: TL;DR translation prompt, not the consensus syllabus."""
    import app
    capture = {}
    monkeypatch.setattr(app, "client", _FakeClient(["Plain English."], capture))
    completed = [{"judge_title": "Justice Alito", "support_level": "overturn", "full_response": "..."}]
    q: asyncio.Queue = asyncio.Queue()
    await app._stream_syllabus(completed, "", q)
    instr = capture["instructions"].lower()
    assert "translate" in instr or "plain-english" in instr
    assert "DO NOT CHANGE" not in capture["instructions"]


async def test_syllabus_error_is_additive(monkeypatch):
    """A synthesis failure emits syllabus_error and returns None — never raises."""
    import app

    class _BoomResponses:
        async def create(self, **kwargs):
            raise RuntimeError("api down")

    class _BoomClient:
        responses = _BoomResponses()

    monkeypatch.setattr(app, "client", _BoomClient())
    q: asyncio.Queue = asyncio.Queue()
    completed = [{"judge_title": "Justice Alito", "support_level": "overturn", "full_response": "..."}]
    result = await app._stream_syllabus(completed, "TALLY", q)
    assert result is None
    kind, payload = q.get_nowait()
    assert kind == "syllabus_error" and "api down" in payload["error"]
    # even on error, the drain sentinel is emitted so the generator terminates
    assert q.get_nowait()[0] == "__syllabus_done__"


@pytest.mark.skipif(
    not os.environ.get("RUN_LIVE_EVAL") or not (os.environ.get("OPENAI_API_KEY", "").startswith("sk-")),
    reason="live eval — set RUN_LIVE_EVAL=1 with a real sk-... OPENAI_API_KEY",
)
async def test_live_syllabus_streams_nonempty():
    """Live faithfulness smoke: a real grounded synthesis streams non-empty prose.
    Opt-in (paid): RUN_LIVE_EVAL=1 + a real key. Asserts the model produced text."""
    import app
    summary = {"support": ["Chief Justice Roberts", "Justice Kagan"], "overturn": ["Justice Alito"]}
    tally = app._build_tally_string(summary)
    completed = [
        {"judge_title": "Chief Justice Roberts", "support_level": "support",
         "full_response": "I would uphold the statute; it is within Congress's commerce power."},
        {"judge_title": "Justice Kagan", "support_level": "support",
         "full_response": "Agree; the law is a valid economic regulation."},
        {"judge_title": "Justice Alito", "support_level": "overturn",
         "full_response": "I would strike it down as exceeding enumerated powers."},
    ]
    q: asyncio.Queue = asyncio.Queue()
    text = await app._stream_syllabus(completed, tally, q)
    assert text and len(text.strip()) > 0
    assert not q.empty()  # streamed at least one token
