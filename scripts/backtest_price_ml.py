"""
Walk-forward backtest for PriceEnsemble → data/models/price_backtest.json

HONESTY CONTRACT (core/market/price_ml.py):
The forecast accuracy statement may ONLY display MAPE/coverage numbers when
this script's artifact exists AND its model_version matches the model
actually running. If this script is never run, the API reports
"no validated backtest on record" — never fabricated numbers.

Method (no lookahead):
- Source: SSB table 03024 weekly salmon export prices (DB first, CSV fallback).
  DB rows whose `source` classifies as synthetic (demo/seed/mock — one
  definition in `core/source_lineage.SYNTHETIC_MARKERS`) are refused and
  counted; the artifact declares `demo_rows_used` so the conformal calibration
  may only be served when it measured real history (WS-23).
- A forecast is issued at week t using t's seasonal phase (as_of), then
  evaluated against the actual price at t+horizon.
- Biological/market inputs (lice, biomass, exports, futures) are held at
  neutral defaults — this measures the price-only path; recorded in the
  artifact's `method` field so the claim is scoped honestly.
- MAPE per horizon = mean(|actual-pred|/|actual|) * 100.
- coverage_80 = share of ALL evaluated (point, horizon) pairs whose actual
  fell inside the engine's own lo80/hi80 band (pooled), plus per-horizon.
- Baseline: horizon-matched carry-forward (price at t+h = price at t) on the
  same evaluation points, plus a two-sided Diebold-Mariano test (squared
  NOK/kg loss, Newey-West h-1 lags) so "beats doing nothing" is measured, not
  asserted (WS-23).

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

from core.source_lineage import REAL, SYNTHETIC, classify_source  # noqa: E402

MIN_EVAL_POINTS = 30  # refuse to write an artifact with fewer (garbage in)

# Provenance values this backtest accepts as a real SSB 03024 observation
# (``SSBWeeklyPrice.source`` default / ``SalmonPriceWeek.source``). The synthetic
# markers themselves come from core/source_lineage.py — never copied here.
REAL_SSB_SOURCES: tuple[str, ...] = ("ssb_03024",)


def load_ssb_series_with_provenance(
    start_year: int,
) -> tuple[list[tuple[int, int, float]], dict]:
    """(rows, provenance) — the history the backtest may measure on, and what it refused.

    WS-23: the 2026-10-12 run merged the database's 52 ``demo_seed`` SSB rows over
    the real CSV history (database winning), so its MAPE measured seeded data. A
    row whose ``source`` classifies as synthetic (one definition:
    ``core.source_lineage.SYNTHETIC_MARKERS``) is now counted and never used; a
    real database row may still override the CSV for the same week.
    """
    async def _db() -> list[tuple[int, int, float, str | None]]:
        from sqlalchemy import select
        from core.async_db import get_async_session
        from core.models import SSBWeeklyPrice

        async with get_async_session() as s:
            rows = (await s.execute(
                select(
                    SSBWeeklyPrice.year,
                    SSBWeeklyPrice.week,
                    SSBWeeklyPrice.price_nok_kg,
                    SSBWeeklyPrice.source,
                )
                .where(SSBWeeklyPrice.price_nok_kg.isnot(None))
                .order_by(SSBWeeklyPrice.year, SSBWeeklyPrice.week)
            )).all()
        return [(int(y), int(w), float(p), src) for y, w, p, src in rows]

    merged: dict[tuple[int, int], float] = {}
    provenance: dict = {
        "csv_rows": 0,
        "csv_path": None,
        "db_rows_used": 0,
        "db_rows_unverified": 0,
        "synthetic_rows_skipped": 0,
        "synthetic_rows_used": 0,
        "db_error": None,
    }

    # CSV first (full history), then real DB rows override
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
                provenance["csv_rows"] += 1
        provenance["csv_path"] = csv_path.name

    try:
        for y, w, p, src in asyncio.run(_db()):
            kind = classify_source(src, REAL_SSB_SOURCES)
            if kind == SYNTHETIC:
                provenance["synthetic_rows_skipped"] += 1
                continue
            if kind != REAL:
                provenance["db_rows_unverified"] += 1
            merged[(y, w)] = p
            provenance["db_rows_used"] += 1
    except Exception as exc:
        provenance["db_error"] = str(exc)[:200]
        print(f"  WARNING: DB history unavailable ({exc}); using CSV only")

    if not merged:
        raise SystemExit("No SSB price data available (DB empty and CSV missing)")

    rows = sorted((y, w, p) for (y, w), p in merged.items() if y >= start_year)
    return rows, provenance


def load_ssb_series(start_year: int) -> list[tuple[int, int, float]]:
    """(iso_year, iso_week, price_nok) ordered ascending — rows only."""
    return load_ssb_series_with_provenance(start_year)[0]


def diebold_mariano(
    model_errors: list[float], baseline_errors: list[float], *, horizon: int,
) -> dict:
    """Two-sided Diebold-Mariano test of two paired loss series (Newey-West HAC).

    ``model_errors``/``baseline_errors`` are absolute NOK/kg errors on the same
    evaluation points; the loss is squared, the long-run variance uses ``h-1``
    lags (the standard choice for overlapping h-step forecasts). ``better`` names
    the lower-loss side, ``p_value`` is the normal approximation (two-sided).
    """
    import math

    if len(model_errors) != len(baseline_errors):
        raise ValueError("loss series must be paired (same evaluation points)")
    n = len(model_errors)
    if n < 2:
        return {"n": n, "dm_stat": None, "p_value": None, "better": "unknown",
                "loss": "squared NOK/kg error", "lags": max(0, horizon - 1)}
    diff = [m * m - b * b for m, b in zip(model_errors, baseline_errors)]
    mean = sum(diff) / n
    var = sum((x - mean) ** 2 for x in diff) / n
    for lag in range(1, horizon):
        cov = sum((diff[i] - mean) * (diff[i - lag] - mean) for i in range(lag, n)) / n
        var += 2.0 * (1.0 - lag / horizon) * cov
    if var <= 1e-18:
        stat = 0.0 if abs(mean) < 1e-18 else math.copysign(float("inf"), mean)
        p_value = 1.0 if stat == 0.0 else 0.0
    else:
        stat = mean / math.sqrt(var / n)
        p_value = math.erfc(abs(stat) / math.sqrt(2.0))
    return {
        "n": n,
        "dm_stat": round(stat, 3),
        "p_value": round(p_value, 4),
        "mean_loss_diff": round(mean, 4),
        "better": "model" if mean < 0 else "baseline" if mean > 0 else "tie",
        "loss": "squared NOK/kg error",
        "lags": max(0, horizon - 1),
    }


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

    series, provenance = load_ssb_series_with_provenance(args.start_year)
    if provenance["synthetic_rows_used"]:
        # Cannot happen by construction (the loader refuses them); refuse loudly
        # rather than write an artifact that measures seeded data.
        raise SystemExit(
            f"Refusing to backtest: {provenance['synthetic_rows_used']} synthetic "
            "rows entered the evaluation series"
        )
    if len(series) < max(horizons) + MIN_EVAL_POINTS:
        raise SystemExit(f"Insufficient data: {len(series)} weeks (need >= {max(horizons) + MIN_EVAL_POINTS})")
    print(
        f"history: {len(series)} weeks used (CSV {provenance['csv_rows']}, DB "
        f"{provenance['db_rows_used']}, {provenance['db_rows_unverified']} unverified); "
        f"{provenance['synthetic_rows_skipped']} synthetic DB rows refused"
    )

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
    horizon_res: dict[str, list[float]] = {}
    pooled_in = pooled_total = 0
    skipped_gaps = 0
    for h in horizons:
        errs, inside, n = [], 0, 0
        abs_errs: list[float] = []
        cf_errs: list[float] = []
        cf_abs: list[float] = []
        res: list[float] = []
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
            abs_errs.append(abs(actual - fc.predicted_nok))
            # Horizon-matched carry-forward baseline on the SAME evaluation
            # point: "price next h weeks = today's price". WS-23 — a model is
            # only worth publishing if it beats this.
            cf_errs.append(abs(actual - prices[i]) / abs(actual))
            cf_abs.append(abs(actual - prices[i]))
            # Conformal calibration residual (actual − predicted), same sign
            # convention as PriceEnsemble._conformal_bands
            res.append(round(actual - fc.predicted_nok, 3))
            inside += 1 if fc.price_lo80 <= actual <= fc.price_hi80 else 0
            n += 1
        if n < MIN_EVAL_POINTS:
            print(f"  horizon {h:2d}w: only {n} eval points (<{MIN_EVAL_POINTS}) — refusing")
            return 1
        cf_mape = sum(cf_errs) / len(cf_errs) * 100
        per_h[str(h)] = {
            "mape": round(sum(errs) / len(errs) * 100, 2),
            "coverage_80": round(inside / n * 100, 1),
            "n": n,
            "carry_forward_mape": round(cf_mape, 2),
            "diebold_mariano": diebold_mariano(abs_errs, cf_abs, horizon=h),
        }
        horizon_res[str(h)] = res
        pooled_in += inside
        pooled_total += n
        dm = per_h[str(h)]["diebold_mariano"]
        print(f"  horizon {h:2d}w: MAPE {per_h[str(h)]['mape']:5.2f}%  "
              f"carry-fwd {per_h[str(h)]['carry_forward_mape']:5.2f}%  "
              f"DM p={dm['p_value']} ({dm['better']})  "
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
        # WS-23: the calibration this artifact produces may only be served when
        # it used no demo rows (PriceEnsemble._load_model enforces this).
        "demo_rows_used": provenance["synthetic_rows_used"],
        "rows_used": len(series),
        "history_provenance": provenance,
        "baselines": {
            "carry_forward": {
                "definition": "forecast(t+h) = observed price at t (no change)",
                "mape": {k: v["carry_forward_mape"] for k, v in per_h.items()},
                "evaluation_points": "identical to the model's, horizon-matched",
            },
        },
        "significance_test": {
            "name": "Diebold-Mariano (squared NOK/kg loss, Newey-West h-1 lags, two-sided)",
            "results": {k: v["diebold_mariano"] for k, v in per_h.items()},
        },
        "skipped_gap_points": skipped_gaps,
        "method": (
            "walk-forward one-shot forecasts from SSB 03024 weekly prices; "
            "forecast issued at week t with t's seasonal phase (as_of), "
            "evaluated at t+h only when the week gap is exactly h weeks; "
            "seasonal climatology computed from pre-window years only "
            f"(<{args.start_year}); biological inputs held at neutral defaults "
            "(price-only path); each horizon also scores a horizon-matched "
            "carry-forward baseline on the same points with a Diebold-Mariano "
            "test; synthetic (demo/seed) history rows are refused, never merged; "
            "produced by scripts/backtest_price_ml.py"
        ),
        "script": "scripts/backtest_price_ml.py",
    }
    BACKTEST_ARTIFACT.write_text(json.dumps(artifact, indent=2))
    print(f"\nwrote {BACKTEST_ARTIFACT}")

    # Conformal calibration residuals (QUANT #2) — consumed by
    # PriceEnsemble._conformal_bands for horizon-specific calibrated bands.
    calib_path = BACKTEST_ARTIFACT.parent / "conformal_residuals.json"
    calib_path.write_text(json.dumps({
        "model_version": model_version,
        "generated_at": artifact["generated_at"],
        # WS-23 lineage declaration: the residuals come from real SSB rows only,
        # so PriceEnsemble may serve them as calibrated bands.
        "demo_rows_used": artifact["demo_rows_used"],
        "rows_used": artifact["rows_used"],
        "window": artifact["window"],
        "residual_definition": "actual - predicted (NOK/kg), walk-forward",
        "horizon_residuals": horizon_res,
        "script": "scripts/backtest_price_ml.py",
    }))
    print(f"wrote {calib_path}")

    print(f"model_version={model_version}  pooled coverage_80={artifact['coverage_80']}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
