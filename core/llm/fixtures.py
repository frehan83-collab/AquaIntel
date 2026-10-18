"""Record live chat answers as fixtures, then score them offline — per model, for free.

The offline gate (`scripts/eval_chat.py`) runs the deterministic path, so it can prove the
grounding and the checker but not what a *model* does. The live gate measures that, but it costs
requests, drifts with whichever free model happens to answer, and cannot run in CI (the free tier
allows 50 requests a day).

Fixtures close the gap. A fixture stores what a real answer contained — mode, model, whether it was
free, the text, the facts it was shown (values included, with their `as_of`), the verification
verdict and the cost. Scoring a fixture re-runs the **current** claim checker over the recorded text
against the recorded facts, so:

* a checker improvement is measured against a fixed corpus instead of a moving model;
* each model gets its own number, which is what "quality" means when the free chain rotates;
* it costs nothing, so it can gate a merge.

The text is stored because it is synthetic evaluation input (a golden question, not a customer's);
customer answers are covered by the receipt, which stores a hash.
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field
from pathlib import Path

import structlog

from core.llm.claim_check import verify

log = structlog.get_logger(__name__)

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "chat_fixtures"


@dataclass
class ModelScore:
    model: str
    answers: int = 0
    numbers_checked: int = 0
    numbers_unverified: int = 0
    answers_with_unverified: int = 0
    refusals_expected: int = 0
    refusals_correct: int = 0
    withheld: int = 0

    @property
    def unmatched_rate(self) -> float:
        if not self.numbers_checked:
            return 0.0
        return round(self.numbers_unverified / self.numbers_checked, 4)

    @property
    def answer_defect_rate(self) -> float:
        if not self.answers:
            return 0.0
        return round(self.answers_with_unverified / self.answers, 4)

    def to_dict(self) -> dict:
        return {
            "model": self.model,
            "answers": self.answers,
            "numbers_checked": self.numbers_checked,
            "numbers_unverified": self.numbers_unverified,
            "unmatched_rate": self.unmatched_rate,
            "answer_defect_rate": self.answer_defect_rate,
            "refusals_expected": self.refusals_expected,
            "refusals_correct": self.refusals_correct,
            "withheld": self.withheld,
        }


@dataclass
class FixtureScore:
    fixtures: int = 0
    per_model: dict[str, ModelScore] = field(default_factory=dict)
    cases: list[dict] = field(default_factory=list)

    def add(self, record: dict, *, expected_refusal: bool) -> dict:
        model = record.get("model") or ("refusal" if record.get("mode") == "refusal" else "deterministic")
        score = self.per_model.setdefault(model, ModelScore(model=model))
        score.answers += 1
        facts = record.get("facts") or []
        text = record.get("answer") or ""
        result = verify(text, facts)
        score.numbers_checked += result.checked
        score.numbers_unverified += len(result.unverified)
        if result.unverified:
            score.answers_with_unverified += 1
        if record.get("mode") == "withheld":
            score.withheld += 1
        if expected_refusal:
            score.refusals_expected += 1
            if record.get("mode") == "refusal":
                score.refusals_correct += 1
        case = {
            "id": record.get("id"),
            "model": model,
            "mode": record.get("mode"),
            "checked": result.checked,
            "unverified": [claim.token for claim in result.unverified],
            "ok": not result.unverified and (record.get("mode") == "refusal") == expected_refusal,
        }
        self.cases.append(case)
        return case

    @property
    def ok(self) -> bool:
        return all(score.numbers_unverified == 0 for score in self.per_model.values()) and all(
            case["ok"] for case in self.cases
        )

    def to_dict(self) -> dict:
        return {
            "fixtures": self.fixtures,
            "ok": self.ok,
            "per_model": [score.to_dict() for score in self.per_model.values()],
            "cases": self.cases,
        }


def save(record: dict) -> Path:
    """Write one fixture; the file name is the case id."""
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    path = FIXTURE_DIR / f"{record['id']}.json"
    payload = dict(record)
    payload.setdefault("recorded_at", dt.datetime.now(dt.UTC).isoformat(timespec="seconds"))
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def load_all() -> list[dict]:
    if not FIXTURE_DIR.exists():
        return []
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(FIXTURE_DIR.glob("*.json"))
    ]


def score_fixtures(records: list[dict] | None = None) -> FixtureScore:
    """Re-score every fixture with the current checker, grouped by the model that answered."""
    records = records if records is not None else load_all()
    # The golden set carries the expectation; a fixture for a refusal case must still refuse.
    from core.llm.eval_chat import load_golden

    expectations = {case["id"]: case for case in load_golden()}
    result = FixtureScore(fixtures=len(records))
    for record in records:
        expected = (expectations.get(record.get("id")) or {}).get("expect", "answer")
        result.add(record, expected_refusal=expected == "refusal")
    log.info(
        "chat.fixtures_scored",
        fixtures=result.fixtures,
        models=len(result.per_model),
        ok=result.ok,
    )
    return result
