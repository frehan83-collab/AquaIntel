"""Accuracy & Method — the public, versioned honesty surface.

Backs the Accuracy & Method page: published walk-forward metrics (or an explicit
"not yet published"), conformal coverage, and the fallback disclosure. Nothing
here estimates: if no artifact exists, the response says so and names the command
that produces one.
"""
from __future__ import annotations

import importlib.util

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


#: The three foundation models the platform can serve, and the library each
#: one needs to load. `torch` alone is not availability: torch can be present
#: with none of these installed, in which case every forecast is a fallback.
FOUNDATION_MODELS: dict[str, tuple[str, str]] = {
    "chronos": ("Amazon Chronos-2", "chronos"),
    "timesfm": ("Google TimesFM 2.5", "timesfm"),
    "moirai": ("Salesforce MOIRAI-2", "uni2ts"),
}


def _installed(module: str, probe=None) -> bool:
    """True when ``module`` can be imported here, without importing it."""
    find_spec = probe or importlib.util.find_spec
    try:
        return find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def _loaded_in_process(model: str) -> bool:
    """True when this process already holds the model in memory.

    Reads the engine's state directly on purpose: ``is_available()`` would
    trigger a multi-hundred-MB download inside a public GET.
    """
    try:
        if model == "chronos":
            from core.ml.chronos_baseline import chronos_baseline

            return bool(chronos_baseline.is_loaded)
        if model == "timesfm":
            from core.ml.timesfm_engine import timesfm_engine

            return timesfm_engine._model is not None
        from core.ml.moirai_engine import moirai_engine

        return moirai_engine._model is not None
    except Exception:
        return False


def _foundation_model_availability(probe=None) -> dict:
    """Availability per model, from the library that actually loads it.

    A model is available only when its own loading library is installed (all
    three also need torch). Weights download on first use, so an installed
    library is not proof that a forecast was real — every forecast response
    still reports models_used vs models_fallback.
    """
    torch_ok = _installed("torch", probe)
    models = {
        key: {
            "label": label,
            "requires": package,
            "installed": _installed(package, probe),
            "loaded": _loaded_in_process(key),
        }
        for key, (label, package) in FOUNDATION_MODELS.items()
    }
    installed = [k for k, v in models.items() if v["installed"]]
    loaded = [k for k, v in models.items() if v["loaded"]]
    available = torch_ok and bool(installed)

    if available:
        note = (
            f"{len(installed)} of {len(FOUNDATION_MODELS)} foundation-model libraries "
            f"are installed ({', '.join(installed)}); {len(loaded)} loaded in this "
            "process. Weights download on first use — an importable library is not "
            "proof that a forecast was real, and every response reports models_used "
            "vs models_fallback."
        )
    elif torch_ok:
        note = (
            "torch is installed but none of chronos-forecasting, timesfm or uni2ts "
            "is, so no foundation model can load and every forecast is the "
            "seasonal-naive fallback (is_live=false). That is disclosed, not hidden."
        )
    else:
        note = (
            "torch is not installed in this environment, so foundation-model "
            "forecasts cannot run and every forecast is the seasonal-naive "
            "fallback. That is disclosed, not hidden."
        )
    return {
        "foundation_models_available": available,
        "foundation_models": models,
        "foundation_models_installed": installed,
        "foundation_models_loaded": loaded,
        "foundation_models_note": note,
    }


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
    out.update(_foundation_model_availability())
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
