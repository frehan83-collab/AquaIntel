"""Accuracy & Method — the public, versioned honesty surface.

Backs the Accuracy & Method page: published walk-forward metrics (or an explicit
"not yet published"), conformal coverage, and the fallback disclosure. Nothing
here estimates: if no artifact exists, the response says so and names the command
that produces one.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/accuracy", tags=["accuracy"])

HOW_TO_PUBLISH = (
    "python scripts/backtest_price_ml.py --start-year 2020 --stride 4 && "
    "python scripts/publish_accuracy.py --from-backtest  "
    "(publishes the served price model and its horizon-matched carry-forward "
    "baseline on one window; writes artifacts/accuracy/<id>.json; refuses to "
    "publish on demo rows, another model tier, or too few points). "
    "python scripts/publish_accuracy.py --weeks 260 publishes the seasonal-naive "
    "baseline artifact."
)


async def _fallback_disclosure() -> dict:
    """What the platform does when model weights are unavailable."""
    out: dict = {
        "policy": (
            "When a foundation model is unavailable, forecasts fall back to the "
            "seasonal-naive baseline and MUST be reported with is_live=false via "
            "DataProvenance.degraded(). A fallback is never presented as a model."
        ),
        "models_used_vs_fallback": "reported per response in /api/ml/* payloads",
    }
    try:
        from core.market.price_ml import BACKTEST_ARTIFACT

        out["legacy_backtest_artifact_present"] = BACKTEST_ARTIFACT.exists()
        out["legacy_artifact_note"] = (
            "A legacy artifact may exist under data/ (gitignored). The published "
            "registry is the only source allowed to back a public accuracy claim."
        )
    except Exception as exc:  # pragma: no cover - import defensive
        out["legacy_backtest_artifact_present"] = None
        out["legacy_artifact_error"] = str(exc)
    try:
        import torch  # noqa: F401

        out["foundation_models_available"] = True
    except Exception:
        out["foundation_models_available"] = False
        out["foundation_models_note"] = (
            "torch is not installed in this environment, so foundation-model "
            "forecasts cannot run and every forecast is the seasonal-naive "
            "fallback. That is disclosed, not hidden."
        )
    return out


@router.get("")
async def accuracy_summary():
    """Published accuracy metrics — or an explicit 'not yet published'."""
    from core.ml.accuracy_registry import ARTIFACT_SCHEMA_VERSION, summary

    data = summary()
    published = data["published"] > 0
    return {
        "published": published,
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "metrics": data["surfaces"],
        "fallback_used_count": data["fallback_used_count"],
        "invalid_artifacts": data["invalid_artifacts"],
        "statement": (
            "Every metric below was produced by a real walk-forward evaluation and "
            "is versioned as an artifact."
            if published
            else (
                "No accuracy artifact has been published from a real walk-forward "
                "evaluation yet. We do not display estimated, illustrative or "
                "third-party MAPE figures — a number appears here only once it has "
                "been measured on real data."
            )
        ),
        "how_to_publish": HOW_TO_PUBLISH,
        "fallback_disclosure": await _fallback_disclosure(),
        "methodology_url": "/api/accuracy/method",
    }


@router.get("/method")
async def accuracy_method():
    """The published artifact contract and evaluation protocol."""
    from core.ml.accuracy_registry import (
        ARTIFACT_DIR,
        ARTIFACT_SCHEMA_VERSION,
        REQUIRED_KEYS,
        REQUIRED_METRICS,
    )

    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "directory": str(ARTIFACT_DIR),
        "artifact_contract": {
            "required_keys": list(REQUIRED_KEYS),
            "required_metrics": list(REQUIRED_METRICS),
            "optional_metrics": ["mae_nok_kg", "coverage_pct", "interval_level", "rmse"],
            "fallback_used": (
                "boolean — true when the evaluated predictor is the honest "
                "seasonal-naive fallback rather than a trained model"
            ),
            "validation": "core.ml.accuracy_registry.validate(); invalid artifacts are reported, never silently ignored",
        },
        "evaluation_protocol": {
            "temporal": "strict walk-forward: each prediction uses only data available before it",
            "interval_calibration": (
                "prediction intervals are calibrated on the first 70% of "
                "year-back pairs and coverage is measured OUT-OF-SAMPLE on the "
                "remaining 30% (no leakage back into calibration)"
            ),
            "reported": ["mape_pct", "mae_nok_kg", "coverage_pct", "n_obs", "window"],
        },
        "prohibited": [
            "displaying a MAPE, coverage or backtest number not backed by a valid artifact",
            "measuring accuracy on demo/seed/synthetic rows (source must not be synthetic)",
            "presenting a fallback result as a model result",
        ],
        "how_to_publish": HOW_TO_PUBLISH,
    }


@router.get("/artifacts/{artifact_id}")
async def accuracy_artifact(artifact_id: str):
    """One published artifact, verbatim (dashboard/audit use)."""
    from core.ml.accuracy_registry import registry

    for artifact in registry()["artifacts"]:
        if artifact["artifact_id"] == artifact_id:
            return artifact
    raise HTTPException(404, f"No published artifact '{artifact_id}'")
