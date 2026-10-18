"""WS-38 — grounded chat: every number carries provenance, and gaps are admitted.

The chat used to be handed a string-interpolated snapshot: a national lice average over
**every** row (demo seeds included), a latest week with no age, and a hardcoded
"traffic light: green < 0.2" sentence that is not how the Norwegian system works. These
tests pin the replacement: facts with `as_of`/`source`/provenance, a prompt that forbids
numbers outside the block, a deterministic fallback when no model answers, and a legal
gate that spends no tokens on a request for a trade direction.
"""
from __future__ import annotations

import datetime as dt

import pytest

from core.llm.chat_service import (
    ChatService,
    _fallback_answer,
    _followups,
    _truncate,
    is_directional,
)
from core.llm.grounding import (
    PROVENANCE_DEGRADED,
    PROVENANCE_LIVE,
    PROVENANCE_STALE,
    PROVENANCE_UNAVAILABLE,
    Fact,
    PlatformContext,
    _age_days,
    _grade,
)


# ── 1. Facts render their honesty ──────────────────────────────────────


def test_a_live_fact_renders_without_a_warning():
    fact = Fact(
        key="price.spot",
        label="SSB price",
        value=72.55,
        unit="NOK/kg",
        as_of="2026-W41",
        source="SSB",
        provenance=PROVENANCE_LIVE,
        age_days=13,
    )
    line = fact.line()
    assert "72.55" in line
    assert "as of 2026-W41" in line
    assert "13d old" in line
    assert "LIVE" not in line


def test_a_stale_fact_says_so_with_its_age():
    fact = Fact(
        key="bloom.chlorophyll",
        label="Chlorophyll",
        value={"mean_mg_m3": 1.91},
        source="CMEMS",
        provenance=PROVENANCE_STALE,
        age_days=196,
    )
    line = fact.line()
    assert "196d old" in line
    assert "STALE" in line


def test_an_unavailable_fact_is_reported_as_a_gap_not_a_zero():
    fact = Fact(
        key="lice.national",
        label="Lice",
        provenance=PROVENANCE_UNAVAILABLE,
        note="no verified row",
    )
    line = fact.line()
    assert "UNAVAILABLE" in line
    assert "no verified row" in line
    assert not fact.usable


def test_the_block_forbids_numbers_outside_it():
    context = PlatformContext(
        facts=[
            Fact(key="price.spot", label="SSB price", value=72.55, source="SSB"),
            Fact(key="lice.national", label="Lice", provenance=PROVENANCE_UNAVAILABLE, note="none"),
        ],
        generated_at="2026-10-18T12:00:00+00:00",
    )
    block = context.block()
    assert "only numbers" in block and "may state" in block
    assert "never estimate" in block
    assert "1 of 2 facts usable" in block
    assert context.degraded is True
    assert context.unavailable == ["lice.national"]


def test_an_empty_context_is_explicit():
    block = PlatformContext().block()
    assert "none available" in block


def test_age_and_grade():
    now = dt.datetime(2026, 10, 18, tzinfo=dt.UTC)
    assert _age_days(dt.datetime(2026, 10, 8, tzinfo=dt.UTC), now) == 10
    assert _age_days(None, now) is None
    assert _grade(3, 7) == PROVENANCE_LIVE
    assert _grade(30, 7) == PROVENANCE_STALE
    assert _grade(None, 7) == PROVENANCE_DEGRADED


def test_sources_are_serialisable_for_the_ui():
    context = PlatformContext(
        facts=[Fact(key="k", label="L", value=1.0, source="S", as_of="2026-W41",
                    provenance=PROVENANCE_DEGRADED, age_days=109)]
    )
    [source] = context.sources()
    assert source["provenance"] == PROVENANCE_DEGRADED
    assert source["as_of"] == "2026-W41"
    assert source["age_days"] == 109


# ── 2. The service ─────────────────────────────────────────────────────


class _Response:
    def __init__(self, content="The margin is -1.69 NOK/kg.", input_tokens=4200,
                 output_tokens=180, cost_usd=0.0153):
        self.content = content
        self.model = "test-model"
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cost_usd = cost_usd


@pytest.fixture()
def fake_context(monkeypatch):
    context = PlatformContext(
        facts=[
            Fact(key="price.spot", label="SSB price", value={"nok_per_kg": 72.55},
                 unit="NOK/kg", as_of="2026-W41", source="SSB", age_days=13),
            Fact(key="lice.national", label="Lice", provenance=PROVENANCE_UNAVAILABLE,
                 note="no verified row exists"),
        ],
        generated_at="2026-10-18T12:00:00+00:00",
    )
    import core.llm.chat_service as module

    async def fake_build_context(*args, **kwargs):
        return context

    monkeypatch.setattr(module, "build_context", fake_build_context)
    return context


@pytest.mark.asyncio
async def test_a_grounded_answer_reports_mode_sources_and_usage(fake_context):
    captured = {}

    async def complete(**kwargs):
        captured.update(kwargs)
        return _Response()

    service = ChatService(complete=complete)
    answer = await service.ask("What is the margin?", user_id="user:1")

    assert answer.mode == "grounded"
    assert answer.usage["cost_usd"] == pytest.approx(0.0153)
    assert answer.sources and answer.sources[0]["key"] == "price.spot"
    assert answer.degraded is True
    # The prompt carries the grounded block and the question, and nothing else.
    assert "only numbers" in captured["prompt"]
    assert "QUESTION: What is the margin?" in captured["prompt"]
    assert captured["user_id"] == "user:1"


@pytest.mark.asyncio
async def test_a_model_failure_falls_back_to_the_verified_numbers(fake_context):
    async def complete(**kwargs):
        raise RuntimeError("provider down")

    service = ChatService(complete=complete)
    answer = await service.ask("What is the margin?")

    assert answer.mode == "grounded_fallback"
    assert "verified numbers" in answer.answer.lower()
    assert "72.55" in answer.answer
    assert "no verified row exists" in answer.answer
    assert answer.usage["cost_usd"] == 0.0
    assert answer.model == ""


@pytest.mark.asyncio
async def test_a_directional_question_costs_nothing(fake_context):
    called = False

    async def complete(**kwargs):
        nonlocal called
        called = True
        return _Response()

    service = ChatService(complete=complete)
    answer = await service.ask("Should I buy MOWI now?")

    assert answer.mode == "refusal"
    assert answer.refusal
    assert called is False, "a legal refusal must not spend a token"


@pytest.mark.asyncio
async def test_an_empty_question_is_a_prompt_not_a_token_spend(fake_context):
    called = False

    async def complete(**kwargs):
        nonlocal called
        called = True
        return _Response()

    answer = await ChatService(complete=complete).ask("   ")
    assert answer.mode == "unavailable"
    assert called is False


@pytest.mark.parametrize(
    "question,expected",
    [
        ("Should I buy SalMar shares?", True),
        ("is MOWI a sell here", True),
        ("what is the price target on LSG", True),
        ("will the share price of GSF rise", True),
        ("What is the lice situation in PA 3?", False),
        ("How does the feed leg affect margin?", False),
        ("Which treatment is cheapest?", False),
    ],
)
def test_the_legal_gate_only_catches_directional_questions(question, expected):
    assert is_directional(question) is expected


def test_a_long_question_is_truncated_before_it_is_sent():
    from core.llm.grounding import MAX_QUESTION_CHARS

    text = _truncate("x" * (MAX_QUESTION_CHARS + 500))
    assert len(text) == MAX_QUESTION_CHARS


def test_the_fallback_says_the_model_did_not_write_it(fake_context):
    text = _fallback_answer(fake_context, "anything")
    assert "language model is not configured" in text
    assert "every figure above is real" in text


def test_the_fallback_refuses_to_estimate_when_nothing_is_usable():
    context = PlatformContext(
        facts=[Fact(key="k", label="L", provenance=PROVENANCE_UNAVAILABLE, note="down")]
    )
    text = _fallback_answer(context, "anything")
    assert "cannot answer" in text
    assert "Nothing here is estimated" in text


def test_followups_are_context_aware(fake_context):
    suggestions = _followups(fake_context)
    assert suggestions
    assert "When was the last verified lice report?" in suggestions
