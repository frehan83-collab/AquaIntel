"""
Walk-forward backtest for PriceEnsemble → data/models/price_backtest.json

HONESTY CONTRACT (core/market/price_ml.py):
The forecast accuracy statement may ONLY display MAPE/coverage numbers when
this script's artifact exists AND its model_version matches the model
actually running. If this script is never run, the API reports
"no validated backtest on record" — never fabricated numbers.

Method (no lookahead):
- Source: SSB table 03024 weekly salmon export prices (DB first, CSV fallback).
- A forecast is issued at week t using t's seasonal phase (as_of), then
  evaluated against the actual price at t+horizon.
- Biological/market inputs (lice, biomass, exports, futures) are held at
  neutral defaults — this measures the price-only path; recorded in the
  artifact's `method` field so the claim is scoped honestly.
- MAPE per horizon = mean(|actual-pred|/|actual|) * 100.
- coverage_80 = share of ALL evaluated (point, horizon) pairs whose actual
  fell inside the engine's own lo80/hi80 band (pooled), plus per-horizon.

Usage:
    python scripts/backtest_price_ml.py [--start-year 2020] [--stride 4]
                                        [--horizons 2,4,6,8,10,12,16,20]
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

MIN_EVAL_POINTS = 30  # refuse to write an artifact with fewer (garbage in)


def load_ssb_series(start_year: int) -> list[tuple[int, int, float]]:
    """(iso_year, iso_week, price_nok) ordered ascending.

    Merges DB and CSV history (DB wins on conflicts) — the backtest needs the
    full ~1,400-week series, and either source alone can be partial.
    """
    async def _db() -> list[tuple[int, int, float]]:
        from sqlalchemy import select
        from core.async_db import get_async_session
        from core.models import SSBWeeklyPrice

        async with get_async_session() as s:
            rows = (await s.execute(
                select(SSBWeeklyPrice.year, SSBWeeklyPrice.week, SSBWeeklyPrice.price_nok_kg)
                .where(SSBWeeklyPrice.price_nok_kg.isnot(None))
                .order_by(SSBWeeklyPrice.year, SSBWeeklyPrice.week)
            )).all()
        return [(int(y), int(w), float(p)) for y, w, p in rows]

    merged: dict[tuple[int, int], float] = {}

    # CSV first (full history), then DB rows override
    import csv
    base = Path(__file__).resolve().parent.parent / "data" / "historical"
    candidates = sorted(base.glob("ssb_prices_*.csv"))
    csv_path = candidates[-1] if candidates else None
    if csv_path is not None:
        with csv_path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                try:
                    merged[(int(row["year"]), int(row["week"]))] = float(row["price_nok_per_kg"])
                except (KeyError, TypeError, ValueError):
                    continue

    try:
        for y, w, p in asyncio.run(_db()):
            merged[(y, w)] = p
    except Exception as exc:
        print(f"  WARNING: DB history unavailable ({exc}); using CSV only")

    if not merged:
        raise SystemExit("No SSB price data available (DB empty and CSV missing)")

    return sorted(
        (y, w, p) for (y, w), p in merged.items() if y >= start_year
    )


def load_full_history_seasonal(before_year: int) -> dict[int, float]:
    """Week-of-year mean price from years BEFORE the backtest window (W1).

    Only pre-window years are used so the seasonal climatology cannot leak
    information from weeks after any evaluation point.
    """
    import statistics
    from collections import defaultdict

    all_rows = load_ssb_series(start_year=1990)
    buckets: dict[int, list[float]] = defaultdict(list)
    for y, w, p in all_rows:
        if y < before_year:
            buckets[w].append(p)
    return {w: round(statistics.fmean(ps), 2) for w, ps in buckets.items() if ps}


def main() -> int:
    from core.market.price_ml import price_ensemble, BACKTEST_ARTIFACT

    ap = argparse.ArgumentParser(description="Walk-forward price backtest")
    ap.add_argument("--start-year", type=int, default=2020)
    ap.add_argument("--stride", type=int, default=4, help="weeks between evaluation points")
    ap.add_argument("--horizons", default="2,4,6,8,10,12,14,16,18,20")
    args = ap.parse_args()
    horizons = sorted({int(h) for h in args.horizons.split(",") if h.strip()})

    series = load_ssb_series(args.start_year)
    if len(series) < max(horizons) + MIN_EVAL_POINTS:
        raise SystemExit(f"Insufficient data: {len(series)} weeks (need >= {max(horizons) + MIN_EVAL_POINTS})")

    pattern = load_full_history_seasonal(before_year=args.start_year)
    if pattern:
        price_ensemble.set_seasonal_pattern(pattern)

    prices = [p for _, _, p in series]

    def as_of(i: int) -> dt.datetime | None:
        y, w, _ = series[i]
        try:
            return dt.datetime.fromisocalendar(y, w, 1).replace(tzinfo=dt.UTC)
        except ValueError:
            return None  # invalid ISO week (e.g. W53 in a 52-week year)

    # ISO-week ordinal per index — horizons must be real week gaps, not row
    # gaps (the weekly series can have holes; W2).
    ordinals: list[int | None] = []
    for i in range(len(series)):
        stamp = as_of(i)
        ordinals.append(stamp.toordinal() if stamp else None)

    # Probe: which model tier does THIS deployment actually run?
    probe = price_ensemble.predict(
        current_spot=prices[-1], horizon_weeks=4, n_scenarios=100,
        as_of=as_of(len(series) - 1),
    )
    model_version = probe.model_version

    if "tft" in model_version:
        # B2 guard: tft_predictor builds its features from the full series
        # through today (no as_of cutoff) — backtesting it here would leak
        # future weeks into the forecast and produce a dishonest artifact.
        raise SystemExit(
            "Refusing to backtest the TFT tier: tft_predictor does not accept an "
            "as_of cutoff, so walk-forward evaluation would contain lookahead. "
            "Thread as_of through tft_predictor first."
        )

    per_h: dict[str, dict] = {}
    pooled_in = pooled_total = 0
    skipped_gaps = 0
    for h in horizons:
        errs, inside, n = [], 0, 0
        for i in range(0, len(series) - h, args.stride):
            stamp = as_of(i)
            if stamp is None or ordinals[i] is None or ordinals[i + h] is None:
                continue
            if ordinals[i + h] - ordinals[i] != h * 7:
                skipped_gaps += 1  # gap in weekly series — not a true h-week horizon
                continue
            fc = price_ensemble.predict(
                current_spot=prices[i], horizon_weeks=h,
                n_scenarios=100, as_of=stamp,
            )
            actual = prices[i + h]
            errs.append(abs(actual - fc.predicted_nok) / abs(actual))
            inside += 1 if fc.price_lo80 <= actual <= fc.price_hi80 else 0
            n += 1
        if n < MIN_EVAL_POINTS:
            print(f"  horizon {h:2d}w: only {n} eval points (<{MIN_EVAL_POINTS}) — refusing")
            return 1
        per_h[str(h)] = {
            "mape": round(sum(errs) / len(errs) * 100, 2),
            "coverage_80": round(inside / n * 100, 1),
            "n": n,
        }
        pooled_in += inside
        pooled_total += n
        print(f"  horizon {h:2d}w: MAPE {per_h[str(h)]['mape']:5.2f}%  "
              f"cover80 {per_h[str(h)]['coverage_80']:5.1f}%  n={n}")

    first = f"{series[0][0]}W{series[0][1]:02d}"
    last = f"{series[-1][0]}W{series[-1][1]:02d}"
    artifact = {
        "model_version": model_version,
        "window": f"{first}–{last} (SSB 03024 weekly, stride {args.stride}w)",
        "generated_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "mape": {k: v["mape"] for k, v in per_h.items()},
        "coverage_80": round(pooled_in / pooled_total * 100, 1),
        "per_horizon": per_h,
        "skipped_gap_points": skipped_gaps,
        "method": (
            "walk-forward one-shot forecasts from SSB 03024 weekly prices; "
            "forecast issued at week t with t's seasonal phase (as_of), "
            "evaluated at t+h only when the week gap is exactly h weeks; "
            "seasonal climatology computed from pre-window years only "
            f"(<{args.start_year}); biological inputs held at neutral defaults "
            "(price-only path); produced by scripts/backtest_price_ml.py"
        ),
        "script": "scripts/backtest_price_ml.py",
    }
    BACKTEST_ARTIFACT.write_text(json.dumps(artifact, indent=2))
    print(f"\nwrote {BACKTEST_ARTIFACT}")
    print(f"model_version={model_version}  pooled coverage_80={artifact['coverage_80']}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
