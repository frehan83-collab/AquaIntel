"""Publish versioned accuracy artifacts from a REAL walk-forward evaluation.

Usage::

    python scripts/publish_accuracy.py [--weeks 260]

Writes ``artifacts/accuracy/<id>.json`` (tracked in git) through
``core.ml.accuracy_registry.publish``.

It deliberately **exits non-zero and writes nothing** when there is not enough
real data — the platform must never publish a MAPE it did not measure.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.ml.accuracy_registry import ARTIFACT_SCHEMA_VERSION, publish  # noqa: E402

MIN_OBS = 60
MIN_PAIRS = 12
CALIBRATION_FRACTION = 0.7
INTERVAL_LEVEL = 0.8

# Rows whose `source` marks them as synthetic must never back an accuracy claim.
DEMO_SOURCE_MARKERS = ("demo", "seed", "synthetic", "mock", "fallback")


def _is_real_source(source: str | None) -> bool:
    """False for demo/seed/synthetic rows — they cannot measure accuracy."""
    if not source:
        return False
    lowered = str(source).lower()
    return not any(marker in lowered for marker in DEMO_SOURCE_MARKERS)


async def _series(weeks: int) -> list[tuple[int, int, float]]:
    """Real SSB weekly salmon export prices (NOK/kg), oldest first."""
    from core.market.ssb_price_client import ssb_price_client

    history = await ssb_price_client.get_price_history(n_weeks=weeks)
    series: list[tuple[int, int, float]] = []
    for row in history:
        price = row.get("price_nok")
        if price and row.get("year") and row.get("week"):
            series.append((int(row["year"]), int(row["week"]), float(price)))
    series.sort(key=lambda r: (r[0], r[1]))
    return series


def _db_series() -> tuple[list[tuple[int, int, float]], int]:
    """Locally persisted SSB observations, EXCLUDING demo/synthetic rows.

    Returns ``(series, skipped_synthetic_rows)``. The dev/test seed writes
    ``source='demo_seed'`` rows; measuring accuracy on those would fabricate a
    claim, so they are counted and reported, never used.
    """
    import sqlite3

    from config.settings import settings

    url = str(getattr(settings, "database_url", "sqlite:///data/openclaw.db"))
    path = url.split("sqlite:///")[-1] if "sqlite" in url else "data/openclaw.db"
    series: list[tuple[int, int, float]] = []
    skipped = 0
    try:
        conn = sqlite3.connect(path)
        rows = conn.execute(
            "SELECT year, week, price_nok, source FROM ssb_weekly_prices"
        ).fetchall()
        conn.close()
    except Exception:
        return [], 0
    for year, week, price, source in rows:
        if not _is_real_source(source):
            skipped += 1
            continue
        if price and year and week:
            series.append((int(year), int(week), float(price)))
    series.sort(key=lambda r: (r[0], r[1]))
    return series, skipped


def _seasonal_pairs(series: list[tuple[int, int, float]]) -> list[tuple[float, float]]:
    """(actual, forecast) where the forecast is the same ISO week one year back."""
    by_key = {(y, w): p for y, w, p in series}
    pairs: list[tuple[float, float]] = []
    for year, week, actual in series:
        previous = by_key.get((year - 1, week))
        if previous:
            pairs.append((actual, previous))
    return pairs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weeks", type=int, default=260, help="history window (weeks)")
    args = parser.parse_args()

    series = asyncio.run(_series(args.weeks))
    source_label = "SSB via core.market.ssb_price_client (live fetch)"
    if len(series) < MIN_OBS:
        db_series, skipped_synthetic = _db_series()
        if skipped_synthetic:
            print(
                f"NOTE: ignored {skipped_synthetic} locally persisted row(s) whose "
                "source marks them synthetic (demo_seed) — accuracy cannot be "
                "measured on those."
            )
        if len(db_series) > len(series):
            series = db_series
            source_label = "SSB observations persisted locally (real sources only)"
    if len(series) < MIN_OBS:
        print(
            f"NOT PUBLISHED: only {len(series)} real observations "
            f"(need >= {MIN_OBS}). No artifact written — refusing to estimate."
        )
        return 2

    pairs = _seasonal_pairs(series)
    if len(pairs) < MIN_PAIRS:
        print(
            f"NOT PUBLISHED: seasonal-naive needs a year-back pair per point; "
            f"got {len(pairs)} (need >= {MIN_PAIRS})."
        )
        return 2

    errors = [abs(actual - forecast) / actual for actual, forecast in pairs if actual > 0]
    mape = st.fmean(errors) * 100.0
    mae = st.fmean([abs(a - f) for a, f in pairs])

    # Interval calibrated on the first 70% of pairs, coverage measured
    # out-of-sample on the remainder (no leakage back into calibration).
    split = max(1, int(len(pairs) * CALIBRATION_FRACTION))
    calibration = sorted(abs(a - f) for a, f in pairs[:split])
    quantile = calibration[min(len(calibration) - 1, int(len(calibration) * INTERVAL_LEVEL))]
    test = pairs[split:]
    coverage = (
        100.0 * sum(1 for a, f in test if abs(a - f) <= quantile) / len(test)
        if test
        else None
    )

    artifact = {
        "artifact_id": "seasonal_naive_weekly_prices",
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "model": "seasonal-naive (same ISO week, year-1)",
        "target": "SSB weekly salmon export price (NOK/kg)",
        "method": (
            "walk-forward; prediction interval calibrated on the first 70% of "
            "year-back pairs, coverage measured out-of-sample on the remainder"
        ),
        "window": f"{series[0][0]}W{series[0][1]:02d}..{series[-1][0]}W{series[-1][1]:02d}",
        "n_obs": len(pairs),
        "metrics": {
            "mape_pct": round(mape, 2),
            "mae_nok_kg": round(mae, 3),
            "coverage_pct": None if coverage is None else round(coverage, 1),
            "interval_level": INTERVAL_LEVEL,
        },
        "produced_at": dt.datetime.now(dt.UTC).isoformat(),
        "source": source_label,
        "fallback_used": True,
        "notes": (
            "This IS the honest fallback baseline: when no foundation model weights "
            "are available the platform predicts with exactly this rule, so its "
            "measured error is the floor a live model must beat. Reported here "
            "instead of a model score we cannot produce."
        ),
    }

    info = publish(artifact)
    print(
        f"PUBLISHED {artifact['artifact_id']} -> {info['path']} "
        f"(MAPE {mape:.2f}%, MAE {mae:.3f} NOK/kg, coverage "
        f"{'n/a' if coverage is None else f'{coverage:.1f}%'}, n={len(pairs)})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
