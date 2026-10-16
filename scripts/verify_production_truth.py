"""Verify the production truth of a deployment.

    python scripts/verify_production_truth.py [--json] [--no-freshness]

Checks (see core/production_truth.py): production environment + JWT secret,
agents declared as their own service, database dialect/reachability/migration head,
model + accuracy artifacts, and per-source freshness.

Exit code 1 when any CRITICAL check fails — so CI/CD or a deploy gate can block a
deployment that would silently serve a degraded product.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.production_truth import run_checks  # noqa: E402

SYMBOLS = {"ok": "OK  ", "info": "INFO", "warn": "WARN", "fail": "FAIL"}


async def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument(
        "--no-freshness", action="store_true", help="skip the source freshness checks"
    )
    args = parser.parse_args()

    report = await run_checks(include_freshness=not args.no_freshness)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for check in report["checks"]:
            print(
                f"[{SYMBOLS.get(check['status'], check['status'])}] "
                f"{check['check']}: {check['detail']}"
            )
        print(
            f"\n{report['failed']} failure(s) "
            f"({len(report['critical_failures'])} critical), "
            f"{report['warnings']} warning(s)"
        )
        if report["truth_gaps"]:
            print("\nTruth gaps:")
            for gap in report["truth_gaps"]:
                print(f"  - {gap}")

    return 1 if report["critical_failures"] else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
