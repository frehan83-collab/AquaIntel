"""
ML & GNN Routes
================
Extracted from core/api.py for maintainability.
GNN farm network model, Chronos-2 zero-shot baselines, TimesFM 2.5 forecasting.
"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from core.models import LiceRecord, Locality
from core.async_db import get_async_session
from core.market.data_provenance import DataProvenance

router = APIRouter(prefix="/api", tags=["ml"])


# ── GNN Farm Network ──────────────────────────────────────────────────

@router.get("/gnn/status")
async def gnn_status():
    """Check Lice GNN availability and training state."""
    try:
        from core.market.lice_gnn import lice_gnn_trainer
    except ImportError as _e:
        raise HTTPException(503, f"Lice GNN dependencies not installed: {_e}")
    result = lice_gnn_trainer.status()
    if isinstance(result, dict):
        result["data_provenance"] = DataProvenance.from_model_result(result, "Lice GNN (PyTorch Geometric)", confidence=0.70).to_dict()
    return result


@router.post("/gnn/build-training-data")
async def gnn_build_training_data():
    try:
        from core.market.lice_gnn import lice_gnn_trainer
    except ImportError as _e:
        raise HTTPException(503, f"Lice GNN dependencies not installed: {_e}")
    result = lice_gnn_trainer.build_training_data_from_db()
    if isinstance(result, dict):
        result["data_provenance"] = DataProvenance.from_model_result(result, "Lice GNN (PyTorch Geometric)", confidence=0.70).to_dict()
    return result


@router.post("/gnn/train")
async def gnn_train(epochs: int = 50):
    """
    Train the Lice GNN on historical BarentsWatch data.
    Runs asynchronously — heavy operation (minutes on CPU).
    """
    try:
        from core.market.lice_gnn import lice_gnn_trainer
    except ImportError as _e:
        raise HTTPException(503, f"Lice GNN dependencies not installed: {_e}")
    if not lice_gnn_trainer.is_available():
        raise HTTPException(503, "torch_geometric not installed. Run: pip install torch_geometric")

    if not lice_gnn_trainer._graph_snapshots:
        lice_gnn_trainer.build_training_data_from_db()

    # Load training data from DB
    async with get_async_session() as s:
        rows = (await s.execute(
            select(
                LiceRecord.locality_no,
                LiceRecord.year,
                LiceRecord.week,
                LiceRecord.avg_adult_female_lice,
                LiceRecord.sea_temp_c,
                LiceRecord.has_cleaner_fish,
                Locality.latitude,
                Locality.longitude,
                Locality.production_area,
            )
            .join(Locality, LiceRecord.locality_no == Locality.locality_no)
            .where(
                Locality.latitude.isnot(None),
                Locality.longitude.isnot(None),
                LiceRecord.avg_adult_female_lice.isnot(None),
            )
            .order_by(LiceRecord.year.asc(), LiceRecord.week.asc())
        )).all()

    if len(rows) < 100:
        raise HTTPException(400, f"Insufficient training data: {len(rows)} records (need >=100)")

    farm_records = [
        {
            "locality_no": r[0],
            "year": r[1],
            "week": r[2],
            "avg_adult_female_lice": r[3],
            "sea_temp_c": r[4],
            "has_cleaner_fish": r[5],
            "lat": r[6],
            "lon": r[7],
            "production_area": r[8] or 1,
            "company_id": hash(r[0]) % 100,  # stable integer from locality_no
        }
        for r in rows
    ]

    lice_gnn_trainer.prepare_data(farm_records)
    result = lice_gnn_trainer.train(epochs=epochs)
    return {"status": "trained", **result, "data_provenance": DataProvenance.live("Lice GNN (PyTorch Geometric)", confidence=0.70).to_dict()}


@router.get("/gnn/predict/{locality_no}")
async def gnn_predict(locality_no: int):
    """Predict next-week lice count + exceedance probability for a farm."""
    try:
        from core.market.lice_gnn import lice_gnn_trainer
    except ImportError as _e:
        raise HTTPException(503, f"Lice GNN dependencies not installed: {_e}")
    if not lice_gnn_trainer.is_available():
        raise HTTPException(503, "torch_geometric not installed")
    try:
        result = lice_gnn_trainer.predict(farm_id=locality_no)
        if isinstance(result, dict):
            result["data_provenance"] = DataProvenance.from_model_result(result, "Lice GNN (PyTorch Geometric)", confidence=0.70).to_dict()
        return result
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/gnn/predict-all")
async def gnn_predict_all():
    """Predict lice levels for all farms — returns list sorted by risk."""
    try:
        from core.market.lice_gnn import lice_gnn_trainer
    except ImportError as _e:
        raise HTTPException(503, f"Lice GNN dependencies not installed: {_e}")
    if not lice_gnn_trainer.is_available():
        raise HTTPException(503, "torch_geometric not installed")
    try:
        predictions = lice_gnn_trainer.predict_all_farms()
        high_risk = [p for p in predictions if p["above_threshold"]]
        return {
            "generated_at": dt.datetime.now(dt.UTC).isoformat(),
            "n_farms": len(predictions),
            "n_high_risk": len(high_risk),
            "high_risk_farms": high_risk[:20],
            "all_predictions": predictions[:100],
            "data_provenance": DataProvenance.live("Lice GNN (PyTorch Geometric)", confidence=0.70).to_dict(),
        }
    except RuntimeError as e:
        raise HTTPException(400, str(e))


# ── Chronos-2 Zero-Shot Baselines ─────────────────────────────────────

@router.get("/ml/chronos/price-forecast")
async def chronos_price_forecast(horizon: int = 4):
    """Zero-shot salmon price forecast using Chronos-2."""
    from core.ml.chronos_baseline import chronos_baseline
    result = await chronos_baseline.forecast_salmon_prices(horizon)
    if isinstance(result, dict):
        result["data_provenance"] = DataProvenance.from_model_result(result, "Amazon Chronos zero-shot", confidence=0.70).to_dict()
    return result


@router.get("/ml/chronos/lice-forecast/{locality_no}")
async def chronos_lice_forecast(locality_no: int, horizon: int = 8):
    """Zero-shot lice count forecast for a specific farm."""
    from core.ml.chronos_baseline import chronos_baseline
    result = await chronos_baseline.forecast_lice_counts(locality_no, horizon)
    if isinstance(result, dict):
        result["data_provenance"] = DataProvenance.from_model_result(result, "Amazon Chronos zero-shot", confidence=0.70).to_dict()
    return result


@router.get("/ml/chronos/temperature-forecast/{locality_no}")
async def chronos_temperature_forecast(locality_no: int, horizon: int = 8):
    """Zero-shot sea temperature forecast for a specific farm."""
    from core.ml.chronos_baseline import chronos_baseline
    result = await chronos_baseline.forecast_temperatures(locality_no, horizon)
    if isinstance(result, dict):
        result["data_provenance"] = DataProvenance.from_model_result(result, "Amazon Chronos zero-shot", confidence=0.70).to_dict()
    return result


@router.get("/ml/chronos/supply-forecast")
async def chronos_supply_forecast(horizon: int = 6):
    """Zero-shot export volume forecast (monthly)."""
    from core.ml.chronos_baseline import chronos_baseline
    result = await chronos_baseline.forecast_supply_volumes(horizon)
    if isinstance(result, dict):
        result["data_provenance"] = DataProvenance.from_model_result(result, "Amazon Chronos zero-shot", confidence=0.70).to_dict()
    return result


@router.get("/ml/chronos/model-comparison")
async def chronos_model_comparison(series: str = "price", horizon: int = 4):
    """Compare Chronos-2 vs TFT vs seasonal naive on holdout window."""
    from core.ml.chronos_baseline import chronos_baseline
    result = await chronos_baseline.compare_models(series, horizon)
    if isinstance(result, dict):
        result["data_provenance"] = DataProvenance.from_model_result(result, "Amazon Chronos zero-shot", confidence=0.70).to_dict()
    return result


@router.post("/ml/chronos/custom-forecast")
async def chronos_custom_forecast(request: Request):
    """Custom zero-shot forecast from user-provided values."""
    from core.ml.chronos_baseline import chronos_baseline
    data = await request.json()
    values = data.get("values", [])
    horizon = data.get("horizon", 8)
    if not values or len(values) < 3:
        raise HTTPException(400, "Need at least 3 data points")
    result = await chronos_baseline.forecast_series(values, horizon=horizon)
    if isinstance(result, dict):
        result["data_provenance"] = DataProvenance.from_model_result(result, "Amazon Chronos zero-shot", confidence=0.70).to_dict()
    return result


# ── TimesFM 2.5 Zero-Shot Forecasting ────────────────────────────────

_TIMESFM_PROVENANCE = "Google TimesFM 2.5 zero-shot"
_TIMESFM_CONFIDENCE = 0.75


@router.get("/ml/timesfm/price-forecast")
async def timesfm_price_forecast(horizon: int = 4):
    """Zero-shot salmon price forecast using TimesFM 2.5.

    Optionally uses export supply volume as an exogenous regressor
    (Asche & Bjorndal 2011: supply is a key spot price driver).
    """
    from core.ml.timesfm_engine import timesfm_engine
    result = await timesfm_engine.forecast_salmon_prices(horizon)
    if isinstance(result, dict):
        result["data_provenance"] = DataProvenance.from_model_result(result, 
            _TIMESFM_PROVENANCE, confidence=_TIMESFM_CONFIDENCE
        ).to_dict()
    return result


@router.get("/ml/timesfm/lice-forecast/{locality_no}")
async def timesfm_lice_forecast(locality_no: int, horizon: int = 8):
    """Zero-shot lice count forecast using TimesFM 2.5.

    Optionally uses sea temperature as an exogenous regressor
    (Stige et al. 2006: temperature drives louse reproduction).
    """
    from core.ml.timesfm_engine import timesfm_engine
    result = await timesfm_engine.forecast_lice_counts(locality_no, horizon)
    if isinstance(result, dict):
        result["data_provenance"] = DataProvenance.from_model_result(result, 
            _TIMESFM_PROVENANCE, confidence=_TIMESFM_CONFIDENCE
        ).to_dict()
    return result


@router.get("/ml/timesfm/temperature-forecast/{locality_no}")
async def timesfm_temperature_forecast(locality_no: int, horizon: int = 8):
    """Zero-shot sea temperature forecast using TimesFM 2.5."""
    from core.ml.timesfm_engine import timesfm_engine
    result = await timesfm_engine.forecast_temperatures(locality_no, horizon)
    if isinstance(result, dict):
        result["data_provenance"] = DataProvenance.from_model_result(result, 
            _TIMESFM_PROVENANCE, confidence=_TIMESFM_CONFIDENCE
        ).to_dict()
    return result


@router.get("/ml/timesfm/supply-forecast")
async def timesfm_supply_forecast(horizon: int = 6):
    """Zero-shot export volume forecast (monthly) using TimesFM 2.5."""
    from core.ml.timesfm_engine import timesfm_engine
    result = await timesfm_engine.forecast_supply_volumes(horizon)
    if isinstance(result, dict):
        result["data_provenance"] = DataProvenance.from_model_result(result, 
            _TIMESFM_PROVENANCE, confidence=_TIMESFM_CONFIDENCE
        ).to_dict()
    return result


@router.get("/ml/timesfm/model-comparison")
async def timesfm_model_comparison(series: str = "price", horizon: int = 4):
    """Compare TimesFM 2.5 vs Chronos-2 vs TFT vs seasonal naive.

    Uses holdout window evaluation with MAPE, RMSE, and 80% interval
    coverage metrics.
    """
    from core.ml.timesfm_engine import timesfm_engine
    result = await timesfm_engine.compare_models(series, horizon)
    if isinstance(result, dict):
        result["data_provenance"] = DataProvenance.from_model_result(result, 
            _TIMESFM_PROVENANCE, confidence=_TIMESFM_CONFIDENCE
        ).to_dict()
    return result


@router.post("/ml/timesfm/custom-forecast")
async def timesfm_custom_forecast(request: Request):
    """Custom zero-shot forecast from user-provided values using TimesFM 2.5.

    Accepts JSON body with:
        - values: list[float] (at least 3 data points)
        - horizon: int (default 8, max 256)
        - xreg: optional list[list[float]] (exogenous regressors)
    """
    from core.ml.timesfm_engine import timesfm_engine
    data = await request.json()
    values = data.get("values", [])
    horizon = data.get("horizon", 8)
    xreg = data.get("xreg", None)
    if not values or len(values) < 3:
        raise HTTPException(400, "Need at least 3 data points")
    if horizon > 256:
        raise HTTPException(400, "TimesFM max horizon is 256")
    result = await timesfm_engine.forecast_series(
        values, horizon=horizon, xreg=xreg
    )
    if isinstance(result, dict):
        result["data_provenance"] = DataProvenance.from_model_result(result, 
            _TIMESFM_PROVENANCE, confidence=_TIMESFM_CONFIDENCE
        ).to_dict()
    return result


# ── MOIRAI-2 Zero-Shot Forecasting (Low-Latency) ───────────────────

_MOIRAI_PROVENANCE = "Salesforce MOIRAI-2 zero-shot"
_MOIRAI_CONFIDENCE = 0.72


@router.get("/ml/moirai/price-forecast")
async def moirai_price_forecast(horizon: int = 4):
    """Zero-shot salmon price forecast using MOIRAI-2 (30M params).

    Optimized for low-latency inference — ideal for real-time WebSocket
    endpoints. Uses Liu et al. (2025) MOIRAI-2 architecture.
    """
    from core.ml.moirai_engine import moirai_engine
    result = await moirai_engine.forecast_salmon_prices(horizon)
    if isinstance(result, dict):
        result["data_provenance"] = DataProvenance.from_model_result(result, 
            _MOIRAI_PROVENANCE, confidence=_MOIRAI_CONFIDENCE
        ).to_dict()
    return result


@router.get("/ml/moirai/lice-forecast/{locality_no}")
async def moirai_lice_forecast(locality_no: int, horizon: int = 8):
    """Zero-shot lice count forecast using MOIRAI-2 (low-latency)."""
    from core.ml.moirai_engine import moirai_engine
    result = await moirai_engine.forecast_lice_counts(locality_no, horizon)
    if isinstance(result, dict):
        result["data_provenance"] = DataProvenance.from_model_result(result, 
            _MOIRAI_PROVENANCE, confidence=_MOIRAI_CONFIDENCE
        ).to_dict()
    return result


@router.get("/ml/moirai/supply-forecast")
async def moirai_supply_forecast(horizon: int = 6):
    """Zero-shot export volume forecast (monthly) using MOIRAI-2."""
    from core.ml.moirai_engine import moirai_engine
    result = await moirai_engine.forecast_supply_volumes(horizon)
    if isinstance(result, dict):
        result["data_provenance"] = DataProvenance.from_model_result(result, 
            _MOIRAI_PROVENANCE, confidence=_MOIRAI_CONFIDENCE
        ).to_dict()
    return result


@router.get("/ml/moirai/model-comparison")
async def moirai_model_comparison(series: str = "price", horizon: int = 4):
    """Compare MOIRAI-2 vs Chronos-2 vs TimesFM 2.5 vs TFT vs seasonal naive.

    Highlights MOIRAI-2's latency advantage (30M params, 2x faster).
    Uses holdout window evaluation with MAPE, RMSE, and 80% interval
    coverage metrics.
    """
    from core.ml.moirai_engine import moirai_engine
    result = await moirai_engine.compare_models(series, horizon)
    if isinstance(result, dict):
        result["data_provenance"] = DataProvenance.from_model_result(result, 
            _MOIRAI_PROVENANCE, confidence=_MOIRAI_CONFIDENCE
        ).to_dict()
    return result


@router.post("/ml/moirai/custom-forecast")
async def moirai_custom_forecast(request: Request):
    """Custom zero-shot forecast from user-provided values using MOIRAI-2.

    Accepts JSON body with:
        - values: list[float] (at least 3 data points)
        - horizon: int (default 8, max 128)
    """
    from core.ml.moirai_engine import moirai_engine
    data = await request.json()
    values = data.get("values", [])
    horizon = data.get("horizon", 8)
    if not values or len(values) < 3:
        raise HTTPException(400, "Need at least 3 data points")
    if horizon > 128:
        raise HTTPException(400, "MOIRAI-2 max horizon is 128")
    result = await moirai_engine.forecast_series(values, horizon=horizon)
    if isinstance(result, dict):
        result["data_provenance"] = DataProvenance.from_model_result(result, 
            _MOIRAI_PROVENANCE, confidence=_MOIRAI_CONFIDENCE
        ).to_dict()
    return result


# ── Foundation Model Ensemble ─────────────────────────────────────────
# Combines TimesFM 2.5 + Chronos-2 + MOIRAI-2 for best-in-class forecasting.
# Ensemble diversity = decorrelated errors → more robust predictions.
# Reference: GIFT-Eval benchmark (2025-2026) shows ensemble approaches
# consistently outperform single models.

@router.get("/ml/ensemble/price-forecast")
async def ensemble_price_forecast(horizon: int = 4):
    """Ensemble salmon price forecast combining available foundation models.

    Aggregates predictions from TimesFM 2.5, Chronos, and MOIRAI-2 using
    median-of-medians for point estimate and union of quantile bands for
    uncertainty. Model diversity = decorrelated errors = more robust predictions.

    Honesty contract: a model only counts as "used" if it produced real model
    output (engines tag their seasonal-naive fallbacks with model="...-fallback").
    The response reports models_used (real), models_fallback (degraded), and a
    data_provenance that is live only when >= 1 real model ran.
    """
    import numpy as np
    results = {}
    models_available = []
    models_fallback = []

    async def _run(label: str, coro) -> None:
        nonlocal first_fallback
        try:
            r = await coro
        except Exception:
            r = None
        if not r or "median" not in r:
            return
        model_tag = str(r.get("model", "")).lower()
        if "fallback" in model_tag or r.get("fallback") is True or r.get("error"):
            models_fallback.append(label)
            if first_fallback is None:
                first_fallback = r
            return
        results[label] = r
        models_available.append(label)

    first_fallback: dict | None = None

    # Run all 3 models, gracefully handle any that fail or fall back
    from core.ml.timesfm_engine import timesfm_engine
    from core.ml.chronos_baseline import chronos_baseline
    from core.ml.moirai_engine import moirai_engine
    await _run("TimesFM 2.5", timesfm_engine.forecast_salmon_prices(horizon))
    await _run("Chronos", chronos_baseline.forecast_salmon_prices(horizon))
    await _run("MOIRAI-2", moirai_engine.forecast_salmon_prices(horizon))

    if not results and first_fallback is None:
        return {"error": "No foundation models available", "models_tried": 3}

    if not results:
        # Every model fell back — do NOT fabricate an "ensemble of 3".
        # Return the first fallback forecast, clearly marked as degraded.
        r = first_fallback or {}
        if not r or "median" not in r:
            return {"error": "No foundation models available", "models_tried": 3}
        return {
            "model": f"fallback ({r.get('model', 'naive')})",
            "models_used": [],
            "models_fallback": models_fallback,
            "horizon": horizon,
            "median": [round(v, 2) for v in r["median"]],
            "lo80": [round(v, 2) for v in r.get("lo80", r["median"])],
            "hi80": [round(v, 2) for v in r.get("hi80", r["median"])],
            "lo95": [round(v, 2) for v in r.get("lo95", r["median"])],
            "hi95": [round(v, 2) for v in r.get("hi95", r["median"])],
            "individual_forecasts": {
                "fallback": {"median": r.get("median"), "model": r.get("model", "naive")},
            },
            "generated_at": dt.datetime.now(dt.UTC).isoformat(),
            "data_provenance": DataProvenance.degraded(
                "Foundation-model ensemble",
                reason="all 3 foundation models unavailable — seasonal-naive fallback used",
                confidence=0.3,
            ).to_dict(),
        }

    # Ensemble: median of medians, widest quantile bands (real models only)
    all_medians = [np.array(r["median"]) for r in results.values()]
    ensemble_median = np.median(np.stack(all_medians), axis=0).tolist()

    # Conservative uncertainty: take widest bands from any model
    all_lo80 = [np.array(r.get("lo80", r["median"])) for r in results.values()]
    all_hi80 = [np.array(r.get("hi80", r["median"])) for r in results.values()]
    all_lo95 = [np.array(r.get("lo95", r["median"])) for r in results.values()]
    all_hi95 = [np.array(r.get("hi95", r["median"])) for r in results.values()]

    ensemble_lo80 = np.min(np.stack(all_lo80), axis=0).tolist()
    ensemble_hi80 = np.max(np.stack(all_hi80), axis=0).tolist()
    ensemble_lo95 = np.min(np.stack(all_lo95), axis=0).tolist()
    ensemble_hi95 = np.max(np.stack(all_hi95), axis=0).tolist()

    provenance = DataProvenance.live(
        f"Ensemble: {' + '.join(models_available)}",
        confidence=min(0.95, 0.70 + 0.05 * len(results)),
    )
    if models_fallback:
        # Still live (>=1 real model ran) but record the degraded members.
        provenance.fallback_reason = (
            f"excluded fallback members: {', '.join(models_fallback)}"
        )

    return {
        "model": f"ensemble ({len(results)} models)",
        "models_used": models_available,
        "models_fallback": models_fallback,
        "horizon": horizon,
        "median": [round(v, 2) for v in ensemble_median],
        "lo80": [round(v, 2) for v in ensemble_lo80],
        "hi80": [round(v, 2) for v in ensemble_hi80],
        "lo95": [round(v, 2) for v in ensemble_lo95],
        "hi95": [round(v, 2) for v in ensemble_hi95],
        "individual_forecasts": {
            name: {
                "median": r.get("median"),
                "model": r.get("model", name),
            }
            for name, r in results.items()
        },
        "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        "data_provenance": provenance.to_dict(),
    }
