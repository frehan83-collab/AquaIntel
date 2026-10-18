"""WS-45 — the § 8 limit is per site and per week, and the chat must not guess.

The council's rank 4: the platform printed both limits ("0.5 normally, 0.2 in the spring
window, PA 3 this week 0.5") and let the farmer pick. The limit is 0.5, or 0.2 inside the spring
window — south weeks 16-21, north weeks 21-26 — so an unbound answer is a compliance hazard with
the platform's name on it.

These tests pin the matrix the council asked for: PA x ISO week, plus the unknown region and the
unbound case.
"""
from __future__ import annotations

import datetime as dt

import pytest

from core.llm.grounding import build_context

#: 2026 weeks: W16 = 13 Apr, W18 = 27 Apr, W19 = 4 May, W22 = 25 May, W24 = 8 Jun.
WEEKS = {16: dt.datetime(2026, 4, 13), 18: dt.datetime(2026, 4, 27), 19: dt.datetime(2026, 5, 4),
         22: dt.datetime(2026, 5, 25), 24: dt.datetime(2026, 6, 8)}


async def _limit(pa: int | None, week: int, *, bound: bool = True):
    now = WEEKS[week].replace(tzinfo=dt.UTC)
    site = {"locality_no": 13035, "pa": pa, "name": "Testfarm"} if bound else None
    context = await build_context(now=now, site=site)
    return context.get("lice.limit")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "pa,week,expected,spring",
    [
        (3, 18, 0.2, True),    # south, inside the spring window
        (3, 19, 0.2, True),
        (3, 24, 0.5, False),   # south, after it
        (1, 16, 0.2, True),    # south
        (9, 16, 0.5, False),   # north, before its window
        (9, 22, 0.2, True),    # north, inside it
        (9, 24, 0.2, True),
    ],
)
async def test_the_limit_matrix(pa, week, expected, spring):
    fact = await _limit(pa, week)
    assert fact.provenance == "live", fact.note
    assert fact.value["limit"] == pytest.approx(expected)
    assert fact.value["in_spring_window"] is spring
    assert fact.value["trigger_level"] == pytest.approx(round(expected * 0.6, 3))
    assert "Testfarm" in fact.label


@pytest.mark.asyncio
async def test_an_unresolved_production_area_refuses_to_quote_a_limit():
    fact = await _limit(None, 19)
    assert fact.provenance == "unavailable"
    assert fact.value is None
    assert "unknown" in fact.note.lower()
    assert not fact.usable


@pytest.mark.asyncio
async def test_without_a_bound_site_no_single_limit_is_stated():
    fact = await _limit(None, 19, bound=False)
    assert fact.provenance == "live"
    assert "depends" in str(fact.value)
    assert "0.5" in fact.line() and "0.2" in fact.line()
    assert "ask for the farm" in (fact.note or "")


@pytest.mark.asyncio
async def test_the_chat_request_carries_the_binding_to_the_prompt():
    from core.llm import chat_service as module

    captured = {}

    async def fake_build_context(*args, **kwargs):
        captured["site"] = kwargs.get("site")
        return await real_build(*args, **kwargs)

    real_build = module.build_context

    class _Response:
        content = "The limit for this site is 0.2."
        model = "test"
        input_tokens = 100
        output_tokens = 10
        cost_usd = 0.0
        error = None

    async def complete(**kwargs):
        return _Response()

    module.build_context = fake_build_context
    try:
        service = module.ChatService(complete=complete)
        await service.ask("What is the lice limit?", site={"locality_no": 13035, "pa": 3})
    finally:
        module.build_context = real_build

    assert captured["site"] == {"locality_no": 13035, "pa": 3}
