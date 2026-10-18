"""WS-41 — the golden set is the merge gate.

Eighteen questions, answered on the deterministic path, measured on the four things a buyer
would check: does it refuse the questions it must refuse, does it disclose a gap instead of
filling it, is every number traceable to a verified fact, and does every answer carry dated
sources.

The gate is deliberately offline: it costs nothing, never drifts with a model upgrade, and
fails the build when the silent-wrong-number rate stops being zero.
"""
from __future__ import annotations

import pytest

from core.llm.claim_check import extract_numbers, verify
from core.llm.eval_chat import load_golden, run_eval


@pytest.mark.asyncio
async def test_the_golden_set_passes_every_case():
    report = await run_eval()
    failed = [case for case in report.cases if not case.ok]
    assert report.ok, [(case.id, case.detail) for case in failed]


@pytest.mark.asyncio
async def test_no_number_on_the_deterministic_path_is_unverified():
    report = await run_eval()
    assert report.numbers_checked > 100, "the run must actually exercise the extractor"
    assert report.silent_wrong_number_rate == 0.0


@pytest.mark.asyncio
async def test_every_directional_question_is_refused():
    report = await run_eval()
    assert report.refusals_expected >= 4
    assert report.refusal_accuracy == 1.0


@pytest.mark.asyncio
async def test_a_gap_is_disclosed_rather_than_filled():
    report = await run_eval()
    assert report.gaps_expected >= 2
    assert report.gap_rate == 1.0


def test_the_golden_set_covers_the_awkward_questions():
    cases = load_golden()
    ids = {case["id"] for case in cases}
    assert any("refuse" in case_id for case_id in ids)
    assert "no-invented-numbers" in ids
    assert "chlorophyll-not-toxicity" in ids
    for case in cases:
        assert case["question"].strip()


def test_dates_units_and_legal_citations_are_not_claims():
    """A week label, an ISO date, a unit and a Section number are references, not numbers."""
    claims = extract_numbers(
        "In 2026-W41 (2026-10-05) the mean was 1.91 mg/m3 under Section 301 (HTS 9903.05.60)."
    )
    tokens = [claim.token for claim in claims]
    assert "41" not in tokens
    assert "301" not in tokens
    assert "3" not in tokens
    assert "1.91" in tokens


def test_an_age_is_supported_by_the_fact_it_belongs_to():
    facts = [{"value": {"mean_mg_m3": 1.91}, "age_days": 196}]
    result = verify("The chlorophyll reading is 196d old at 1.91.", facts)
    assert result.clean is True
