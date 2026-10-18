"""Offline evaluation of the grounded chat: refuses when it should, invents nothing.

The research is emphatic that an LLM judge must never score a number and that the metric that
matters is the **silent-wrong-number rate**. Both can be measured without spending a token:
the deterministic fallback path (`mode: "grounded_fallback"`) assembles an answer straight
from the verified facts, so any number it contains that the facts do not support is a defect
in the grounding or the extractor — and a directional question must be refused before a model
is ever called.

So this harness runs the golden question set against the real grounding + chat service with a
provider that always fails, and reports:

* **refusal accuracy** — every directional question is refused, no token spent;
* **gap disclosure** — a question about a feed that is unavailable says so;
* **numbers checked / unverified** — the silent-wrong-number rate on the deterministic path;
* **provenance coverage** — every answer carries at least one source with a date.

`--live` exists for a run with a real model, but the number that gates a merge is the offline
one, because it costs nothing and never drifts with a model upgrade.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import structlog

from core.llm.chat_service import ChatService
from core.llm.claim_check import verify

log = structlog.get_logger(__name__)

GOLDEN_PATH = Path(__file__).resolve().parents[2] / "artifacts" / "chat_golden_questions.json"


@dataclass
class CaseResult:
    id: str
    question: str
    expect: str
    mode: str
    ok: bool
    detail: str = ""


@dataclass
class EvalReport:
    total: int = 0
    passed: int = 0
    refusals_expected: int = 0
    refusals_correct: int = 0
    numbers_checked: int = 0
    numbers_unverified: int = 0
    live: bool = False
    models: list[str] = field(default_factory=list)
    gaps_expected: int = 0
    gaps_disclosed: int = 0
    cases: list[CaseResult] = field(default_factory=list)

    @property
    def silent_wrong_number_rate(self) -> float:
        if not self.numbers_checked:
            return 0.0
        return round(self.numbers_unverified / self.numbers_checked, 4)

    @property
    def refusal_accuracy(self) -> float:
        if not self.refusals_expected:
            return 1.0
        return round(self.refusals_correct / self.refusals_expected, 3)

    @property
    def gap_rate(self) -> float:
        if not self.gaps_expected:
            return 1.0
        return round(self.gaps_disclosed / self.gaps_expected, 3)

    @property
    def ok(self) -> bool:
        return (
            self.silent_wrong_number_rate == 0.0
            and self.refusal_accuracy == 1.0
            and self.gap_rate == 1.0
        )

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "passed": self.passed,
            "refusal_accuracy": self.refusal_accuracy,
            "gap_rate": self.gap_rate,
            "numbers_checked": self.numbers_checked,
            "numbers_unverified": self.numbers_unverified,
            "silent_wrong_number_rate": self.silent_wrong_number_rate,
            "live": self.live,
            "models": self.models,
            "ok": self.ok,
            "cases": [
                {"id": c.id, "expect": c.expect, "mode": c.mode, "ok": c.ok, "detail": c.detail}
                for c in self.cases
            ],
        }


def load_golden(path: Path | None = None) -> list[dict]:
    target = path or GOLDEN_PATH
    return json.loads(target.read_text(encoding="utf-8"))["cases"]


async def _no_model(**kwargs):
    """A provider that always fails: every answer comes from the deterministic path."""
    raise RuntimeError("evaluation runs without a model (see module docstring)")


async def run_eval(path: Path | None = None, *, live: bool = False) -> EvalReport:
    cases = load_golden(path)
    # Offline: a provider that always fails, so every answer is deterministic and free.
    # Live: the real client, which uses the paid model and falls back to a free one (WS-42).
    service = ChatService() if live else ChatService(complete=_no_model)
    report = EvalReport(total=len(cases))
    report.live = live
    report.models = []

    for case in cases:
        answer = await service.ask(case["question"], user_id="eval")
        expect = case.get("expect", "answer")
        problems: list[str] = []
        if expect == "refusal":
            report.refusals_expected += 1
            if answer.mode == "refusal":
                report.refusals_correct += 1
            else:
                problems.append(f"expected refusal, got {answer.mode}")
        if expect == "gap":
            report.gaps_expected += 1
            lowered = answer.answer.lower()
            if any(token in lowered for token in ("unavailable", "cannot answer", "not available")):
                report.gaps_disclosed += 1
            else:
                problems.append("expected an explicit gap, none found")
        for phrase in case.get("must_mention", []):
            if phrase.lower() not in answer.answer.lower():
                problems.append(f"missing {phrase!r}")
        for phrase in case.get("must_not_mention", []):
            if phrase.lower() in answer.answer.lower():
                problems.append(f"contains {phrase!r}")
        if expect != "refusal":
            if not answer.sources:
                problems.append("no provenance sources")
            check = verify(answer.answer, answer.facts)
            report.numbers_checked += check.checked
            report.numbers_unverified += len(check.unverified)
            if check.unverified:
                problems.append(
                    "unverified numbers: " + ", ".join(c.token for c in check.unverified[:4])
                )
        if answer.model and answer.model not in report.models:
            report.models.append(answer.model)
        report.cases.append(
            CaseResult(
                id=case["id"],
                question=case["question"],
                expect=expect,
                mode=answer.mode,
                ok=not problems,
                detail="; ".join(problems),
            )
        )
        if not problems:
            report.passed += 1

    log.info(
        "chat.eval_done",
        total=report.total,
        passed=report.passed,
        refusal_accuracy=report.refusal_accuracy,
        silent_wrong_number_rate=report.silent_wrong_number_rate,
    )
    return report
