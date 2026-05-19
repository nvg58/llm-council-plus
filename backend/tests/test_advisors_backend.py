"""Unit tests for the advisor debate stream (run_debate generator).

Mocks _query_advisor to avoid LLM API calls.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from backend.advisors import build_rotation_order, run_debate
from backend.personas import DEFAULT_PERSONAS

# Two personas used in most tests
SKEPTIC = next(p for p in DEFAULT_PERSONAS if p.id == "skeptic")
PRAGMATIST = next(p for p in DEFAULT_PERSONAS if p.id == "pragmatist")
INNOVATOR = next(p for p in DEFAULT_PERSONAS if p.id == "innovator")

DEFAULT_MODEL = "openai:gpt-4.1"


async def _collect_events(gen) -> list[dict]:
    """Drain an async generator into a list."""
    return [e async for e in gen]


def _make_query_advisor(responses: dict[str, tuple]):
    """
    Build a mock for _query_advisor.

    responses: {persona_id: (content, error)} — if error is None, success;
    if content is None and error is set, failure.
    Supports CONSENSUS:YES/NO tags being present in content.
    """
    async def _mock(pid, prompt, personas_map, model_assignments, default_model, temperature):
        content, error = responses.get(pid, ("Generic answer. CONSENSUS:NO", None))
        return pid, default_model, content, error
    return _mock


# ── build_rotation_order ──────────────────────────────────────────────────────

def test_rotation_order_round_1_unchanged():
    ids = ["a", "b", "c"]
    assert build_rotation_order(ids, 1) == ["a", "b", "c"]


def test_rotation_order_round_2_shifts_left_by_one():
    ids = ["a", "b", "c"]
    assert build_rotation_order(ids, 2) == ["b", "c", "a"]


def test_rotation_order_round_3_shifts_left_by_two():
    ids = ["a", "b", "c"]
    assert build_rotation_order(ids, 3) == ["c", "a", "b"]


def test_rotation_order_single_persona():
    ids = ["solo"]
    assert build_rotation_order(ids, 5) == ["solo"]


# ── run_debate event sequence ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_debate_emits_debate_start_first():
    responses = {
        "skeptic": ("Answer. CONSENSUS:NO", None),
        "pragmatist": ("Answer. CONSENSUS:NO", None),
    }
    with patch("backend.advisors._query_advisor", side_effect=_make_query_advisor(responses)):
        with patch("backend.advisors._query_neutral", new_callable=AsyncMock) as mock_neutral:
            mock_neutral.return_value = {"model": DEFAULT_MODEL, "content": "Verdict", "error": None}
            events = await _collect_events(run_debate(
                question="Test question?",
                persona_ids=["skeptic", "pragmatist"],
                default_model=DEFAULT_MODEL,
                max_rounds=1,
            ))

    types = [e["type"] for e in events]
    assert types[0] == "advisor_debate_start"


@pytest.mark.asyncio
async def test_run_debate_emits_correct_event_sequence():
    responses = {
        "skeptic": ("Answer. CONSENSUS:NO", None),
        "pragmatist": ("Answer. CONSENSUS:NO", None),
    }
    with patch("backend.advisors._query_advisor", side_effect=_make_query_advisor(responses)):
        with patch("backend.advisors._query_neutral", new_callable=AsyncMock) as mock_neutral:
            mock_neutral.return_value = {"model": DEFAULT_MODEL, "content": "Verdict", "error": None}
            events = await _collect_events(run_debate(
                question="Test?",
                persona_ids=["skeptic", "pragmatist"],
                default_model=DEFAULT_MODEL,
                max_rounds=1,
            ))

    types = [e["type"] for e in events]
    assert "advisor_debate_start" in types
    assert "advisor_round_start" in types
    assert "advisor_response" in types
    assert "advisor_round_complete" in types
    assert "advisor_verdict_start" in types
    assert "advisor_verdict" in types
    assert "advisor_complete" in types


@pytest.mark.asyncio
async def test_run_debate_advisor_complete_contains_personas():
    responses = {
        "skeptic": ("Answer. CONSENSUS:YES", None),
        "pragmatist": ("Answer. CONSENSUS:YES", None),
    }
    with patch("backend.advisors._query_advisor", side_effect=_make_query_advisor(responses)):
        with patch("backend.advisors._query_neutral", new_callable=AsyncMock) as mock_neutral:
            mock_neutral.return_value = {"model": DEFAULT_MODEL, "content": "Verdict", "error": None}
            events = await _collect_events(run_debate(
                question="Test?",
                persona_ids=["skeptic", "pragmatist"],
                default_model=DEFAULT_MODEL,
                max_rounds=1,
            ))

    complete = next(e for e in events if e["type"] == "advisor_complete")
    assert "personas" in complete["data"]
    personas = complete["data"]["personas"]
    assert len(personas) == 2
    ids = {p["id"] for p in personas}
    assert ids == {"skeptic", "pragmatist"}


@pytest.mark.asyncio
async def test_run_debate_consensus_stops_early():
    """All advisors vote YES → debate ends after round 1 even if max_rounds=3."""
    responses = {
        "skeptic": ("I agree! CONSENSUS:YES", None),
        "pragmatist": ("Me too! CONSENSUS:YES", None),
    }
    with patch("backend.advisors._query_advisor", side_effect=_make_query_advisor(responses)):
        with patch("backend.advisors._query_neutral", new_callable=AsyncMock) as mock_neutral:
            mock_neutral.return_value = {"model": DEFAULT_MODEL, "content": "Verdict", "error": None}
            events = await _collect_events(run_debate(
                question="Test?",
                persona_ids=["skeptic", "pragmatist"],
                default_model=DEFAULT_MODEL,
                max_rounds=3,
            ))

    round_starts = [e for e in events if e["type"] == "advisor_round_start"]
    assert len(round_starts) == 1

    complete = next(e for e in events if e["type"] == "advisor_complete")
    assert complete["data"]["consensus_reached"] is True


@pytest.mark.asyncio
async def test_run_debate_tiebreaker_fires_for_two_personas():
    """2 personas, no consensus after all rounds → tiebreaker fires."""
    responses = {
        "skeptic": ("No. CONSENSUS:NO", None),
        "pragmatist": ("No. CONSENSUS:NO", None),
    }
    with patch("backend.advisors._query_advisor", side_effect=_make_query_advisor(responses)):
        with patch("backend.advisors._query_neutral", new_callable=AsyncMock) as mock_neutral:
            mock_neutral.return_value = {"model": DEFAULT_MODEL, "content": "Tiebreaker/Verdict", "error": None}
            events = await _collect_events(run_debate(
                question="Test?",
                persona_ids=["skeptic", "pragmatist"],
                default_model=DEFAULT_MODEL,
                max_rounds=1,
            ))

    types = [e["type"] for e in events]
    assert "advisor_tiebreaker_start" in types
    assert "advisor_tiebreaker" in types


@pytest.mark.asyncio
async def test_run_debate_tiebreaker_skipped_for_three_personas():
    """3 personas, no consensus → NO tiebreaker (only fires for exactly 2)."""
    responses = {
        "skeptic": ("No. CONSENSUS:NO", None),
        "pragmatist": ("No. CONSENSUS:NO", None),
        "innovator": ("No. CONSENSUS:NO", None),
    }
    with patch("backend.advisors._query_advisor", side_effect=_make_query_advisor(responses)):
        with patch("backend.advisors._query_neutral", new_callable=AsyncMock) as mock_neutral:
            mock_neutral.return_value = {"model": DEFAULT_MODEL, "content": "Verdict", "error": None}
            events = await _collect_events(run_debate(
                question="Test?",
                persona_ids=["skeptic", "pragmatist", "innovator"],
                default_model=DEFAULT_MODEL,
                max_rounds=1,
            ))

    types = [e["type"] for e in events]
    assert "advisor_tiebreaker_start" not in types
    assert "advisor_tiebreaker" not in types


@pytest.mark.asyncio
async def test_run_debate_one_advisor_error_round_still_completes():
    """One persona errors per round; others succeed. Round still emits round_complete."""
    async def flaky_advisor(pid, prompt, personas_map, model_assignments, default_model, temperature):
        if pid == "skeptic":
            return pid, default_model, None, "Timeout"
        return pid, default_model, "Good answer. CONSENSUS:NO", None

    with patch("backend.advisors._query_advisor", side_effect=flaky_advisor):
        with patch("backend.advisors._query_neutral", new_callable=AsyncMock) as mock_neutral:
            mock_neutral.return_value = {"model": DEFAULT_MODEL, "content": "Verdict", "error": None}
            events = await _collect_events(run_debate(
                question="Test?",
                persona_ids=["skeptic", "pragmatist"],
                default_model=DEFAULT_MODEL,
                max_rounds=1,
            ))

    round_completes = [e for e in events if e["type"] == "advisor_round_complete"]
    assert len(round_completes) == 1

    responses = round_completes[0]["data"]["responses"]
    skeptic_resp = next(r for r in responses if r["persona_id"] == "skeptic")
    assert skeptic_resp["error"] == "Timeout"


@pytest.mark.asyncio
async def test_run_debate_round_order_rotates():
    """Round 1 uses original order; round 2 shifts left by 1."""
    async def recording_advisor(pid, prompt, personas_map, model_assignments, default_model, temperature):
        return pid, default_model, "Answer. CONSENSUS:NO", None

    with patch("backend.advisors._query_advisor", side_effect=recording_advisor):
        with patch("backend.advisors._query_neutral", new_callable=AsyncMock) as mock_neutral:
            mock_neutral.return_value = {"model": DEFAULT_MODEL, "content": "Verdict", "error": None}
            events = await _collect_events(run_debate(
                question="Test?",
                persona_ids=["skeptic", "pragmatist"],
                default_model=DEFAULT_MODEL,
                max_rounds=2,
            ))

    round_starts = [e for e in events if e["type"] == "advisor_round_start"]
    assert len(round_starts) == 2
    assert round_starts[0]["data"]["round_number"] == 1
    assert round_starts[1]["data"]["round_number"] == 2
    # Round 2 order should be shifted
    r1_order = round_starts[0]["data"]["order"]
    r2_order = round_starts[1]["data"]["order"]
    assert r1_order != r2_order
    assert r2_order == r1_order[1:] + r1_order[:1]


@pytest.mark.asyncio
async def test_run_debate_too_few_personas_yields_error():
    """Less than 2 personas → advisor_error event, no rounds."""
    events = await _collect_events(run_debate(
        question="Test?",
        persona_ids=["skeptic"],  # only 1
        default_model=DEFAULT_MODEL,
        max_rounds=1,
    ))
    assert len(events) == 1
    assert events[0]["type"] == "advisor_error"


@pytest.mark.asyncio
async def test_run_debate_advisor_complete_has_correct_round_count():
    responses = {
        "skeptic": ("Answer. CONSENSUS:NO", None),
        "pragmatist": ("Answer. CONSENSUS:NO", None),
    }
    with patch("backend.advisors._query_advisor", side_effect=_make_query_advisor(responses)):
        with patch("backend.advisors._query_neutral", new_callable=AsyncMock) as mock_neutral:
            mock_neutral.return_value = {"model": DEFAULT_MODEL, "content": "Verdict", "error": None}
            events = await _collect_events(run_debate(
                question="Test?",
                persona_ids=["skeptic", "pragmatist"],
                default_model=DEFAULT_MODEL,
                max_rounds=2,
            ))

    complete = next(e for e in events if e["type"] == "advisor_complete")
    assert len(complete["data"]["rounds"]) == 2
