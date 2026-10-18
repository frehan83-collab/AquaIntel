"""Run the grounded-chat golden set offline and print the metrics that gate a merge.

    python scripts/eval_chat.py            # offline, free, deterministic (CI gate)
    python scripts/eval_chat.py --json     # the same report as JSON

The gate is the **silent-wrong-number rate**: on the deterministic path, every number in an
answer must be traceable to a verified fact. A non-zero rate exits 1, as does a missed refusal
or an undisclosed gap.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.llm.eval_chat import load_golden, run_eval  # noqa: E402


async def _record() -> None:
    """Answer each golden question live and store the fixture (no scoring here)."""
    from core.llm.chat_service import ChatService
    from core.llm.fixtures import save

    service = ChatService()
    for case in load_golden():
        answer = await service.ask(case["question"])
        payload = answer.to_dict()
        path = save(
            {
                "id": case["id"],
                "question": case["question"],
                "expect": case.get("expect", "answer"),
                "mode": payload["mode"],
                "model": payload["model"],
                "model_is_free": payload.get("model_is_free", False),
                "answer": payload["answer"],
                "facts": [
                    fact
                    for fact in payload.get("facts", [])
                    if fact.get("value") is not None
                ],
                "verification": payload.get("verification", {}),
                "usage": payload.get("usage", {}),
            }
        )
        print(f"recorded {case['id']} -> {path.name} ({payload['mode']}, {payload['model'] or 'n/a'})")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    parser.add_argument("--path", default=None, help="alternative golden-set path")
    parser.add_argument(
        "--record",
        action="store_true",
        help="answer the golden set live and write a fixture per case (costs requests)",
    )
    parser.add_argument(
        "--fixtures",
        action="store_true",
        help="score the recorded fixtures offline with the current checker (free, CI-able)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="answer with the real model (falls back to a free OpenRouter model); reports rather than gates",
    )
    args = parser.parse_args()

    if args.fixtures:
        from core.llm.fixtures import score_fixtures

        scored = score_fixtures()
        payload = scored.to_dict()
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"fixtures             {scored.fixtures}")
            for model in payload["per_model"]:
                print(
                    f"  {model['model'][:46]:46s} answers={model['answers']:2d} "
                    f"numbers={model['numbers_checked']:3d} unmatched={model['numbers_unverified']} "
                    f"defect_rate={model['answer_defect_rate']:.0%}"
                )
            for case in scored.cases:
                if not case["ok"]:
                    print(f"  FAIL {case['id']} ({case['model']}): {case['unverified']}")
        return 0 if scored.ok else 1

    if args.record:
        asyncio.run(_record())
        return 0

    report = asyncio.run(run_eval(Path(args.path) if args.path else None, live=args.live))
    payload = report.to_dict()
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"cases                {report.passed}/{report.total} passed")
        print(f"refusal accuracy     {report.refusal_accuracy:.0%} "
              f"({report.refusals_correct}/{report.refusals_expected})")
        print(f"gap disclosure       {report.gap_rate:.0%} "
              f"({report.gaps_disclosed}/{report.gaps_expected})")
        print(f"numbers checked      {report.numbers_checked}")
        print(f"mode                 {"live " + ", ".join(report.models) if report.live else "offline (deterministic)"}")
        print(f"silent-wrong-number  {report.silent_wrong_number_rate:.2%} "
              f"({report.numbers_unverified} unmatched)")
        for case in report.cases:
            if not case.ok:
                print(f"  FAIL {case.id}: {case.detail} (mode {case.mode})")
    if args.live:
        # A live run reports quality; it does not gate. The gate is the offline run.
        return 0 if report.refusal_accuracy == 1.0 and report.gap_rate == 1.0 else 1
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
