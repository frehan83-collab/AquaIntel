"""
Supply & Biomass Routes
========================
Extracted from core/api.py for maintainability.
Supply forecasts, smolt pipeline, biomass outlook and scenarios.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from core.models import LiceRecord, Locality
from core.async_db import get_async_session
from core.market.data_provenance import DataProvenance
from core.schemas import BiomassOutlookResponse

router = APIRouter(prefix="/api", tags=["supply"])


@router.get("/supply-forecast")
async def supply_forecast():
    """Regional supply volume forecast (Enterprise+ tier)."""
    from core.valuechain.supply_forecast import generate_buyer_intelligence

    # Build PA-level lice summary from current data
    async with get_async_session() as s:
        latest = (await s.execute(
            select(LiceRecord.year, LiceRecord.week)
            .order_by(LiceRecord.year.desc(), LiceRecord.week.desc())
            .limit(1)
        )).first()

        if not latest:
            raise HTTPException(status_code=404, detail="No supply data available")

        year, week = latest
        records = (await s.execute(
            select(LiceRecord, Locality)
            .join(Locality, LiceRecord.locality_no == Locality.locality_no)
            .where(LiceRecord.year == year, LiceRecord.week == week)
            .where(LiceRecord.avg_adult_female_lice.isnot(None))
        )).all()

    # Aggregate by production area
    import numpy as np
    pa_data: dict[int, dict] = {}
    for lice, loc in records:
        pa = loc.production_area or 0
        if pa < 1 or pa > 13:
            continue
        if pa not in pa_data:
            pa_data[pa] = {"lice_values": [], "temps": []}
        pa_data[pa]["lice_values"].append(lice.avg_adult_female_lice or 0)
        pa_data[pa]["temps"].append(lice.sea_temp_c or 8)

    pa_summary = {}
    for pa, d in pa_data.items():
        arr = np.array(d["lice_values"])
        pa_summary[pa] = {
            "avg_lice": float(np.mean(arr)),
            "pct_above": float(np.mean(arr > 0.5)),
            "treatments": int(np.sum(arr > 0.5)),
            "temp": float(np.mean(d["temps"])),
        }

    intel = generate_buyer_intelligence(pa_summary)

    return {
        "generated_at": intel.generated_at.isoformat(),
        "total_predicted_tonnes": intel.total_predicted_tonnes,
        "total_baseline_tonnes": intel.total_baseline_tonnes,
        "net_supply_change_pct": intel.net_supply_change_pct,
        "quality_score": intel.overall_quality_score,
        "price_outlook": intel.price_outlook,
        "key_risks": intel.key_risks,
        "recommendations": intel.recommendations,
        "regions": [
            {
                "region": f.region,
                "predicted_tonnes": f.predicted_tonnes,
                "baseline_tonnes": f.baseline_tonnes,
                "net_adjustment_pct": f.net_adjustment_pct,
                "quality_score": f.avg_quality_score,
                "supply_risk": f.supply_risk,
                "price_pressure": f.price_pressure,
            }
            for f in intel.regional_forecasts
        ],
        "data_provenance": DataProvenance.live("Smolt model + Fiskeridirektoratet + BarentsWatch", confidence=0.75).to_dict(),
    }


@router.get("/supply/smolt-forecast")
async def supply_smolt_forecast(months: int = 18):
    from core.valuechain.smolt_model import smolt_model
    result = smolt_model.get_supply_pipeline(months)
    if isinstance(result, dict):
        result["data_provenance"] = DataProvenance.live("Smolt model + Fiskeridirektoratet + BarentsWatch", confidence=0.75).to_dict()
    return result


@router.get("/supply/cohort-timeline")
async def supply_cohort_timeline():
    from core.valuechain.smolt_model import smolt_model
    result = smolt_model.get_cohort_timeline()
    if isinstance(result, dict):
        result["data_provenance"] = DataProvenance.live("Smolt model + Fiskeridirektoratet + BarentsWatch", confidence=0.75).to_dict()
    return result


@router.get("/supply/demand-balance")
async def supply_demand_balance():
    from core.valuechain.smolt_model import smolt_model
    result = smolt_model.get_demand_balance()
    if isinstance(result, dict):
        result["data_provenance"] = DataProvenance.live("Smolt model + Fiskeridirektoratet + BarentsWatch", confidence=0.75).to_dict()
    return result


@router.get("/supply/summary")
async def supply_summary():
    from core.valuechain.smolt_model import smolt_model
    result = smolt_model.get_summary()
    if isinstance(result, dict):
        result["data_provenance"] = DataProvenance.live("Smolt model + Fiskeridirektoratet + BarentsWatch", confidence=0.75).to_dict()
    return result


@router.get("/biomass/outlook", response_model=BiomassOutlookResponse)
async def biomass_outlook(
    horizon: int = 20,
    scenarios: int = 1000,
    regulatory: str = "current",
):
    """
    Advanced biomass forecast with cohort dynamics, regulatory scenarios,
    and Monte Carlo simulation. B(t) = Sigma N_c(t) . w_c(t) <= M(t)
    """
    from core.market.biomass_predictor import biomass_predictor
    horizon = max(2, min(52, horizon))
    scenarios = max(100, min(5000, scenarios))
    outlook = await biomass_predictor.compute_outlook(horizon, scenarios, regulatory)
    result = biomass_predictor.get_outlook_dict()
    if not result:
        raise HTTPException(status_code=503, detail="Biomass outlook computation failed")
    result["data_provenance"] = DataProvenance.live("Smolt model + Fiskeridirektoratet + BarentsWatch", confidence=0.75).to_dict()
    return result


@router.get("/biomass/scenarios")
async def biomass_scenarios():
    """Compare regulatory scenarios (current vs all-green vs all-red)."""
    from core.market.biomass_predictor import biomass_predictor
    # Cache keys include the scenario, so each call computes fresh results.
    current = await biomass_predictor.compute_outlook(20, 500, "current")
    current_dict = biomass_predictor.get_outlook_dict()
    green = await biomass_predictor.compute_outlook(20, 500, "all_green")
    red = await biomass_predictor.compute_outlook(20, 500, "all_red")
    return {
        "current": current_dict or {},
        "all_green": {
            "national_mab": green.national_mab,
            "forecast_biomass": green.forecast_biomass,
            "utilization_pct": green.utilization_pct,
        },
        "all_red": {
            "national_mab": red.national_mab,
            "forecast_biomass": red.forecast_biomass,
            "utilization_pct": red.utilization_pct,
        },
        "data_provenance": DataProvenance.live("Smolt model + Fiskeridirektoratet + BarentsWatch", confidence=0.75).to_dict(),
    }
