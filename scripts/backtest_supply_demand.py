"""
Supply-Demand price-path backtest — writes the REAL walk-forward artifact.
=========================================================================
Runs a strict no-lookahead walk-forward evaluation of the supply-demand
price path's core (seasonal + reversion) on real SSB 03024 history and
writes `data/models/supply_demand_backtest.json`, which
`core.market.supply_demand_engine` loads (and validates) to expose real
MAPE numbers via `/api/supply/demand-balance` -> `price_forecast.backtest`.

Nothing is fabricated: if SSB is unreachable or history is too short the
script exits non-zero and writes nothing.

Usage:
    python scripts/backtest_supply_demand.py [--start-year 2020]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.market.supply_demand_engine import BACKTEST_ARTIFACT, run_walk_forward
from core.market.ssb_price_client import ssb_price_client


def _print_report(artifact: dict) -> None:
    print()
    print("=" * 64)
    print("  SUPPLY-DEMAND PRICE PATH — WALK-FORWARD BACKTEST (real SSB data)")
    print("=" * 64)
    print(f"  History:        {artifact['history_weeks']} weeks")
    print(f"  Origins:        {artifact['n_origins']} (min train {artifact['min_train_weeks']}w)")
    print(f"  Method:         {artifact['method']}")
    print()
    print(f"  {'h':>4} | {'MAPE %':>7} | {'n':>4} | {'cov(in-sample q)':>16} | {'cov(wf q)':>9}")
    print(f"  {'-'*4}-+-{'-'*7}-+-{'-'*4}-+-{'-'*16}-+-{'-'*9}")
    for h, mape in artifact["mape"].items():
        n = artifact["mape_n_by_horizon"].get(h, 0)
        cov_is = artifact.get("coverage_80_band_in_sample", {}).get(h)
        cov_wf = artifact.get("coverage_80_band_walk_forward", {}).get(h)
        is_s = f"{cov_is:.1f}%" if cov_is is not None else "n/a"
        wf_s = f"{cov_wf:.1f}%" if cov_wf is not None else "n/a"
        print(f"  {h:>2}w  | {mape:>7.2f} | {n:>4} | {is_s:>16} | {wf_s:>9}")
    print()
    print("  cov = share of realized prices inside the p10-p90 band; (wf q)")
    print("  is the out-of-sample calibration the live engine ships.")
    print()
    print("  Backtested components: ", ", ".join(artifact["components_backtested"]))
    print("  NOT backtested (heuristic overlays):", ", ".join(artifact["components_not_backtested"]))
    print()


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, default=2020)
    args = parser.parse_args()

    print(f"Fetching SSB 03024 history since {args.start_year} ...")
    bulk = await ssb_price_client.fetch_bulk_history(args.start_year)
    if not bulk.prices:
        print("ERROR: no SSB price history available (network/API) — no artifact written.")
        return 1

    try:
        artifact = run_walk_forward(bulk.prices)
    except ValueError as e:
        print(f"ERROR: {e} — no artifact written.")
        return 1

    BACKTEST_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    BACKTEST_ARTIFACT.write_text(json.dumps(artifact, indent=2))
    _print_report(artifact)
    print(f"  Artifact written: {BACKTEST_ARTIFACT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
