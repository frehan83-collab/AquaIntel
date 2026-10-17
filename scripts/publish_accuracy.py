"""Publish versioned accuracy artifacts from a REAL walk-forward evaluation.

Usage::

    python scripts/publish_accuracy.py [--weeks 260]
    python scripts/publish_accuracy.py --from-backtest [PATH]

The ``--from-backtest`` mode publishes the price model the deployment actually
serves plus its horizon-matched carry-forward baseline from one
``data/models/price_backtest.json`` run (WS-23), so both are measured on the
same window and points and the model entry carries the Diebold-Mariano result.
It refuses artifacts that used demo/seed history rows or measured another tier.

Writes ``artifacts/accuracy/<id>.json`` (tracked in git) through
``core.ml.accuracy_registry.publish``.

It deliberately **exits non-zero and writes nothing** when there is not enough
real data — the platform must never publish a MAPE it did not measure.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.ml.accuracy_registry import ARTIFACT_SCHEMA_VERSION, publish  # noqa: E402

MIN_OBS = 60
MIN_PAIRS = 12
MIN_BACKTEST_PAIRS = 30  # same floor the backtest uses to write an artifact
HEADLINE_HORIZON = 4  # weeks — the horizon the price outlook surfaces by default
DEFAULT_BACKTEST_PATH = Path("data/models/price_backtest.json")
CALIBRATION_FRACTION = 0.7
INTERVAL_LEVEL = 0.8

# Rows whose `source` marks them as synthetic must never back an accuracy claim.
# One definition (core/source_lineage.py), shared with the freshness monitor.
from core.source_lineage import SYNTHETIC_MARKERS as DEMO_SOURCE_MARKERS  # noqa: E402


def _is_real_source(source: str | None) -> bool:
    """False for demo/seed/synthetic rows — they cannot measure accuracy."""
    if not source:
        return False
    lowered = str(source).lower()
    return not any(marker in lowered for marker in DEMO_SOURCE_MARKERS)


def _week_number(raw) -> int | None:
    """Parse an SSB week label ('W42', '42', 42) into an int.

    `ssb_price_client.get_price_history` returns `"week": "W42"`, so a bare
    `int()` raises `ValueError: invalid literal for int() with base 10: 'W42'` —
    a latent bug that only surfaced once live SSB data actually arrived.
    """
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if text[:1].lower() == "w":
        text = text[1:]
    try:
        return int(text)
    except ValueError:
        return None


async def _series(weeks: int) -> list[tuple[int, int, float]]:
    """Real SSB weekly salmon export prices (NOK/kg), oldest first."""
    from core.market.ssb_price_client import ssb_price_client

    history = await ssb_price_client.get_price_history(n_weeks=weeks)
    series: list[tuple[int, int, float]] = []
    for row in history:
        price = row.get("price_nok")
        week = _week_number(row.get("week"))
        year = _week_number(row.get("year"))
        if price and year and week:
            series.append((year, week, float(price)))
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


def publish_from_backtest(
    path: Path, *, ensemble_version: str, publish_fn=publish,
) -> tuple[int, list[dict]]:
    """Publish the served price model AND its carry-forward baseline from one artifact.

    Both artifacts are measured on the same walk-forward window and evaluation
    points, and the model artifact carries the Diebold-Mariano result, so
    ``/api/accuracy`` can answer "does it beat doing nothing, on which window,
    with what confidence" without a second experiment. Refuses (exit 2, nothing
    written) when the artifact measured demo rows or a model tier that is not
    the one actually served — that was the WS-23 defect.
    """
    if not path.exists():
        print(f"NOT PUBLISHED: {path} not found — run scripts/backtest_price_ml.py first.")
        return 2, []
    try:
        bt = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"NOT PUBLISHED: {path} unreadable ({exc}).")
        return 2, []

    demo_rows = bt.get("demo_rows_used")
    if not (type(demo_rows) is int and demo_rows == 0):
        print(
            f"NOT PUBLISHED: backtest declares demo_rows_used={demo_rows!r}; a "
            "calibration measured on seeded rows cannot back an accuracy claim."
        )
        return 2, []
    if bt.get("model_version") != ensemble_version:
        print(
            f"NOT PUBLISHED: backtest measured {bt.get('model_version')!r} but this "
            f"deployment serves {ensemble_version!r} — re-run the backtest."
        )
        return 2, []

    per_h = bt.get("per_horizon") or {}
    baseline_mape = ((bt.get("baselines") or {}).get("carry_forward") or {}).get("mape") or {}
    horizons = sorted(int(h) for h in per_h)
    if not horizons:
        print("NOT PUBLISHED: backtest artifact has no per-horizon results.")
        return 2, []
    headline = HEADLINE_HORIZON if str(HEADLINE_HORIZON) in per_h else horizons[0]
    head = per_h[str(headline)]
    if int(head.get("n", 0)) < MIN_BACKTEST_PAIRS:
        print(
            f"NOT PUBLISHED: horizon {headline}w has {head.get('n')} evaluation "
            f"points (need >= {MIN_BACKTEST_PAIRS})."
        )
        return 2, []
    if str(headline) not in baseline_mape:
        print("NOT PUBLISHED: backtest artifact has no carry-forward baseline for "
              f"horizon {headline}w.")
        return 2, []

    dm = head.get("diebold_mariano") or {}
    provenance = bt.get("history_provenance") or {}
    window = bt.get("window") or "unknown"
    produced_at = dt.datetime.now(dt.UTC).isoformat()
    n_obs = int(head["n"])

    model_artifact = {
        "artifact_id": "price_ensemble_walk_forward",
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "model": ensemble_version,
        "target": "SSB weekly salmon export price (NOK/kg)",
        "method": (
            bt.get("method", "walk-forward; see scripts/backtest_price_ml.py")
            + "; this evaluates the price-only configuration — the live outlook also "
            "applies lice and supply signals, which this score does not cover"
        ),
        "window": window,
        "n_obs": n_obs,
        "metrics": {
            "mape_pct": head["mape"],
            "mape_by_horizon_pct": {h: v["mape"] for h, v in per_h.items()},
            "carry_forward_mape_pct": baseline_mape[str(headline)],
            "carry_forward_mape_by_horizon_pct": baseline_mape,
            "diebold_mariano_stat": dm.get("dm_stat"),
            "diebold_mariano_p": dm.get("p_value"),
            "diebold_mariano_better": dm.get("better"),
            "coverage_pct": head.get("coverage_80"),
            "interval_level": INTERVAL_LEVEL,
            "horizon_weeks": headline,
        },
        "produced_at": produced_at,
        "source": (
            "SSB table 03024 weekly export prices (real rows only: "
            f"{provenance.get('synthetic_rows_skipped', 0)} synthetic rows refused, "
            f"{bt.get('rows_used')} rows used)"
        ),
        "fallback_used": "rule" in ensemble_version,
        "notes": (
            "Walk-forward, price-only path (biological inputs neutral). Headline "
            f"{headline}w: MAPE {head['mape']}% vs horizon-matched carry-forward "
            f"{baseline_mape[str(headline)]}% on the same {n_obs} points; "
            f"Diebold-Mariano p={dm.get('p_value')} ({dm.get('better')} lower loss). "
            "coverage_pct is the engine's own 80% band, not re-calibrated here. "
            "Demo/seed history rows are refused, so the 2026-10-12 numbers are "
            "superseded."
        ),
    }
    baseline_artifact = {
        "artifact_id": "carry_forward_weekly_prices",
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "model": "carry-forward (price at t held for t+h)",
        "target": "SSB weekly salmon export price (NOK/kg)",
        "method": (
            "same evaluation points, stride and horizon-matched weeks as "
            "price_ensemble_walk_forward; no-change baseline"
        ),
        "window": window,
        "n_obs": n_obs,
        "metrics": {
            "mape_pct": baseline_mape[str(headline)],
            "mape_by_horizon_pct": baseline_mape,
            "horizon_weeks": headline,
        },
        "produced_at": produced_at,
        "source": "SSB table 03024 weekly export prices (real rows only)",
        "fallback_used": True,
        "notes": (
            "The floor a price model must beat. Published on the identical window "
            "and points as price_ensemble_walk_forward so the comparison is exact."
        ),
    }

    published: list[dict] = []
    for artifact in (model_artifact, baseline_artifact):
        info = publish_fn(artifact)
        published.append(info)
        print(f"PUBLISHED {artifact['artifact_id']} -> {info['path']}")
    print(
        f"  {headline}w MAPE {head['mape']}% vs carry-forward "
        f"{baseline_mape[str(headline)]}% (n={n_obs}, DM p={dm.get('p_value')})"
    )
    return 0, published


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weeks", type=int, default=260, help="history window (weeks)")
    parser.add_argument(
        "--from-backtest",
        nargs="?",
        const=str(DEFAULT_BACKTEST_PATH),
        default=None,
        help="publish the served price model + carry-forward baseline from a "
             "walk-forward backtest artifact (default: data/models/price_backtest.json)",
    )
    args = parser.parse_args()

    if args.from_backtest is not None:
        from core.market.price_ml import price_ensemble

        code, _ = publish_from_backtest(
            Path(args.from_backtest), ensemble_version=price_ensemble.model_version,
        )
        return code

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
