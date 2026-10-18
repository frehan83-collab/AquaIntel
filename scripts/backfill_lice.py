"""Backfill verified lice weeks from BarentsWatch Fishhealth v2.

The platform's lice history stopped at 2026-W15, and the reason turned out not to be a dead feed:
the v2 endpoint still returns 1 779 localities for the current week, 585 of them with
`liceReport.hasReported = true`, and the values are where the parser reads them
(`liceReport.adultFemaleLice.average`). The ingest simply has not run since W15 on this box.

This script re-ingests a week range through the same `DataIngestAgent._upsert_lice_v2` the agent
uses, so a backfilled row is indistinguishable from a live one (same source marker, same fields).

Usage:
    python scripts/backfill_lice.py                 # weeks 16..current-1 of this year
    python scripts/backfill_lice.py --from 2026 16 --to 2026 41
    python scripts/backfill_lice.py --year 2026 --weeks 16-41
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.data_ingest import DataIngestAgent  # noqa: E402
from core.barentswatch import BarentsWatchClient  # noqa: E402


async def ingest_week(client: BarentsWatchClient, agent: DataIngestAgent, year: int, week: int) -> int:
    raw = await client.get_historical_lice(year, week)
    if not isinstance(raw, list) or not raw:
        print(f"{year}-W{week:02d}: no payload")
        return 0
    written = await DataIngestAgent._upsert_lice_v2(raw, year, week)
    reported = sum(1 for rec in raw if (rec.get("liceReport") or {}).get("hasReported"))
    print(f"{year}-W{week:02d}: {reported} reported of {len(raw)} localities, {written} new rows")
    return written


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=None)
    parser.add_argument("--weeks", default=None, help="e.g. 16-41")
    parser.add_argument("--from-week", type=int, default=None)
    parser.add_argument("--to-week", type=int, default=None)
    args = parser.parse_args()

    today = dt.datetime.now(dt.UTC)
    year = args.year or today.year
    if args.weeks:
        start_s, _, end_s = args.weeks.partition("-")
        start, end = int(start_s), int(end_s or start_s)
    elif args.from_week and args.to_week:
        start, end = args.from_week, args.to_week
    else:
        start, end = 1, max(1, today.isocalendar().week - 1)

    client = BarentsWatchClient()
    agent = DataIngestAgent()
    total = 0
    try:
        for week in range(start, end + 1):
            try:
                total += await ingest_week(client, agent, year, week)
            except Exception as exc:  # noqa: BLE001 — one bad week must not stop the rest
                print(f"{year}-W{week:02d}: failed — {str(exc)[:140]}")
    finally:
        await client.close()
        await agent.shutdown()
    print(f"total new rows: {total}")
    return 0 if total else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
