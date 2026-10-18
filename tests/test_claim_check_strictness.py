"""WS-44 — the three lies the checker used to miss: sign, binding, round numbers.

The council found the first verifier blind in exactly the places a plausible answer would lie:

* it compared absolute values, so a −1.69 NOK/kg margin written as "+1.69 profit" verified;
* the candidate pool was one flat set, so swapping the spot price with the modelled cost, or the
  § 8 limit with the trigger, verified;
* 0 and 100 were exempt as trivial, so "0 lice" and "100 % mortality" were never claims.

These tests pin the fixes, and the fail-closed consequence: an unsupported number loses its
sentence, and the answer says one was withheld.
"""
from __future__ import annotations

import pytest

from core.llm.claim_check import (
    TRIVIAL,
    extract_numbers,
    strip_unsupported,
    verify,
)

FACTS = [
    {
        "key": "margin.bridge",
        "value": {
            "spot_nok_per_kg": 72.55,
            "modelled_cost_nok_per_kg": 74.24,
            "margin_nok_per_kg": -1.69,
        },
        "age_days": 109,
    },
    {
        "key": "lice.limit",
        "value": {
            "this_week_default": 0.5,
            "spring_window_limit": 0.2,
            "trigger_level": 0.4,
        },
    },
]


def test_a_sign_flipped_margin_fails_unless_the_sentence_says_loss():
    flipped = verify("The margin is +1.69 NOK/kg profit this week.", FACTS)
    assert flipped.clean is False
    assert [claim.token for claim in flipped.unverified] == ["1.69"]

    honest = verify("The margin is a loss of 1.69 NOK/kg this week.", FACTS)
    assert honest.clean is True


def test_swapping_the_spot_and_the_cost_fails_binding():
    swapped = verify("The spot was 74.24 NOK/kg and the modelled cost was 72.55.", FACTS)
    assert swapped.clean is False
    assert {claim.token for claim in swapped.unverified} == {"74.24", "72.55"}

    correct = verify("The spot was 72.55 NOK/kg and the modelled cost was 74.24.", FACTS)
    assert correct.clean is True


def test_swapping_the_lice_limit_and_the_trigger_fails_binding():
    swapped = verify("The limit is 0.4 and the trigger is 0.5.", FACTS)
    assert swapped.clean is False
    correct = verify("The limit is 0.5 and the trigger is 0.4.", FACTS)
    assert correct.clean is True


def test_zero_and_one_hundred_are_claims_again():
    assert 0.0 not in TRIVIAL
    assert 100.0 not in TRIVIAL
    result = verify("There were 0 lice and 100 % mortality.", FACTS)
    assert result.clean is False
    assert {claim.token for claim in result.unverified} == {"0", "100"}


def test_a_supported_zero_verifies():
    facts = [{"key": "lice.national", "value": {"sites_above_0.5": 0}}]
    assert verify("No site was above the limit: 0 sites.", facts).clean is True


def test_an_unsupported_number_loses_its_sentence_and_the_answer_says_so():
    text = "The spot was 72.55 NOK/kg. Mortality ran at 30 % this year. The feed period is July."
    result = verify(text, FACTS)
    cleaned, removed = strip_unsupported(text, result)

    assert removed == 1
    assert "30" not in cleaned
    assert "72.55" in cleaned
    assert "July" in cleaned


def test_dates_and_week_labels_are_still_not_claims():
    claims = extract_numbers("In 2026-W41 (2026-10-05) the spot was 72.55.")
    tokens = [claim.token for claim in claims]
    assert "41" not in tokens
    assert "2026" not in tokens
    assert "72.55" in tokens


@pytest.mark.asyncio
async def test_the_chat_withholds_an_unsupported_number_end_to_end(monkeypatch):
    from core.llm import chat_service as module
    from core.llm.grounding import Fact, PlatformContext

    context = PlatformContext(
        facts=[
            Fact(key="price.spot", label="SSB price", value={"nok_per_kg": 72.55},
                 unit="NOK/kg", as_of="2026-W41", source="SSB", age_days=13),
        ],
        generated_at="2026-10-18T12:00:00+00:00",
    )

    async def fake_context(*args, **kwargs):
        return context

    class _Response:
        content = "The spot is 72.55 NOK/kg. It will rise 30 % next month."
        model = "test-model"
        input_tokens = 100
        output_tokens = 20
        cost_usd = 0.001
        error = None

    async def complete(**kwargs):
        return _Response()

    monkeypatch.setattr(module, "build_context", fake_context)
    answer = await module.ChatService(complete=complete).ask("What is the spot price?")

    assert answer.mode == "grounded"
    assert "72.55" in answer.answer
    assert "30 %" not in answer.answer
    assert "withheld" in answer.answer
    assert answer.verification["clean"] is False
    assert answer.degraded is True
