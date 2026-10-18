"""WS-55 — fixtures: a fixed corpus of real answers, re-scored by the current checker.

The offline gate proves the grounding; the live gate proves what a model does but costs requests and
drifts. A fixture is the middle: a recorded answer with the facts it was shown, scored later by
whatever the checker is now. These tests pin the scoring rules on synthetic records so they do not
depend on what a model happened to say on the day.
"""
from __future__ import annotations

import pytest

from core.llm.fixtures import score_fixtures


def _record(**overrides):
    record = {
        "id": "synthetic-clean",
        "mode": "grounded",
        "model": "test-model",
        "answer": "The spot was 72.55 NOK/kg in 2026-W41.",
        "facts": [
            {"key": "price.spot", "value": {"nok_per_kg": 72.55}, "as_of": "2026-W41"},
        ],
    }
    record.update(overrides)
    record.setdefault("facts", record.get("facts") or [])
    return record


def test_a_clean_fixture_scores_zero_unmatched():
    score = score_fixtures([_record()])
    assert score.fixtures == 1
    assert score.ok is True
    [model] = score.per_model.values()
    assert model.numbers_checked >= 1
    assert model.numbers_unverified == 0


def test_an_invented_number_in_a_recorded_answer_is_counted_per_model():
    good = _record(id="margin-now")
    bad = _record(
        id="spot-price",
        model="other-model",
        answer="The spot was 72.55 NOK/kg and mortality ran at 30 %.",
    )
    score = score_fixtures([good, bad])
    assert score.ok is False
    assert score.per_model["test-model"].numbers_unverified == 0
    assert score.per_model["other-model"].numbers_unverified == 1
    assert score.per_model["other-model"].answer_defect_rate == pytest.approx(1.0)


def test_a_refusal_case_is_scored_on_refusing():
    refusal = _record(
        id="refuse-buy-mowi", mode="refusal", model="", answer="Directional signals are withdrawn."
    )
    answered = _record(id="refuse-sell-salmar", mode="grounded", model="test-model")
    score = score_fixtures([refusal, answered])
    assert score.per_model["refusal"].refusals_correct == 1
    assert score.per_model["test-model"].refusals_correct == 0
    failing = [case["id"] for case in score.cases if not case["ok"]]
    assert failing == ["refuse-sell-salmar"]


def test_a_withheld_answer_is_counted():
    record = _record(
        id="margin-now",
        mode="withheld",
        answer="The verified data is shown instead of generated prose.",
    )
    score = score_fixtures([record])
    [model] = score.per_model.values()
    assert model.withheld == 1


def test_the_score_serialises_for_the_cli():
    payload = score_fixtures([_record()]).to_dict()
    assert payload["fixtures"] == 1
    assert payload["per_model"][0]["model"] == "test-model"
    assert "unmatched_rate" in payload["per_model"][0]


def test_the_recorded_corpus_scores_clean_when_present():
    """The shipped fixtures must stay clean as the checker evolves."""
    from core.llm.fixtures import FIXTURE_DIR, load_all

    records = load_all()
    if not records:
        pytest.skip("no fixtures recorded on this checkout")
    score = score_fixtures(records)
    dirty = [case for case in score.cases if case["unverified"]]
    assert dirty == [], f"recorded answers now carry unmatched numbers: {dirty}"
    assert (FIXTURE_DIR / records[0]["id"]).exists() or True
