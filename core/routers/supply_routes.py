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
from core.source_lineage import provenance_for, summarise_rows

router = APIRouter(prefix="/api", tags=["supply"])

# The smolt model reads Fiskeridirektoratet smolt/production series only — it
# never reads the lice table, so its label must not claim BarentsWatch (WS-14).
SMOLT_LABEL = "Smolt model + Fiskeridirektoratet"


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
    used: list = []  # WS-14: the rows this payload is actually computed from
    for lice, loc in records:
        pa = loc.production_area or 0
        if pa < 1 or pa > 13:
            continue
        used.append(lice)
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
    lineage = summarise_rows(used, year=year)

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
        "lineage": lineage,
        "data_provenance": provenance_for(
            lineage, "Smolt model + Fiskeridirektoratet + BarentsWatch lice", 0.75
        ),
    }


@router.get("/supply/smolt-forecast")
async def supply_smolt_forecast(months: int = 18):
    """18-month cohort-based smolt pipeline.

    Contract correction (post-review, L5 migration finding): this route
    returned a BARE LIST with no provenance metadata — the old
    ``isinstance(result, dict)`` guard could never fire, and three
    divergent fictional shapes existed across the frontend type and the
    api-docs sample. It now returns the documented platform envelope,
    consistent with the sibling supply routes:

        {"pipeline": [SupplyPoint...], "horizon_months": n,
         "total_harvest_tonnes": t, "data_provenance": {...}}

    Every engine response must carry provenance
    (core/market/data_provenance.py doctrine). In-repo consumers were
    verified (frontend only); docs/openapi.frozen.json declares no schema
    for this path (re-frozen, no diff).
    """
    from core.valuechain.smolt_model import smolt_model
    pipeline = smolt_model.get_supply_pipeline(months)
    if not isinstance(pipeline, list):
        return pipeline
    return {
        "pipeline": pipeline,
        "horizon_months": months,
        "total_harvest_tonnes": round(
            sum(p.get("projected_harvest_tonnes", 0) for p in pipeline), 0
        ),
        "data_provenance": DataProvenance.live(
            SMOLT_LABEL, confidence=0.75
        ).to_dict(),
    }


@router.get("/supply/cohort-timeline")
async def supply_cohort_timeline():
    """Active cohorts with their growth stage.

    Contract correction (same class as smolt-forecast): this route
    returned a BARE LIST with an unreachable provenance guard; it now
    returns {"cohorts": [...], "count": n, "data_provenance": {...}} so
    the platform doctrine holds (every engine response carries
    provenance). Sole in-repo consumer is the supply-forecast page.
    """
    from core.valuechain.smolt_model import smolt_model
    cohorts = smolt_model.get_cohort_timeline()
    if not isinstance(cohorts, list):
        return cohorts
    return {
        "cohorts": cohorts,
        "count": len(cohorts),
        "data_provenance": DataProvenance.live(
            SMOLT_LABEL, confidence=0.75
        ).to_dict(),
    }


@router.get("/supply/demand-balance")
async def supply_demand_balance():
    """Integrated supply-demand balance + 2-20 week price path (R7).

    Legacy fields (horizon_months, total_supply_tonnes, total_demand_tonnes,
    balance_tonnes, balance_pct, signal, price_pressure) are unchanged;
    everything new is additive (contract: additive-v1):
      balance_label, integration, supply_breakdown, demand_breakdown,
      price_forecast (incl. empirical p10-p90 bands; a backtest is served only
      once it is published in the accuracy registry).
    """
    from core.market.supply_demand_engine import supply_demand_engine
    from core.valuechain.smolt_model import smolt_model

    result = smolt_model.get_demand_balance()
    if not isinstance(result, dict):
        return result
    intel = await supply_demand_engine.compute()
    result.update(intel)
    return result


@router.get("/supply/summary")
async def supply_summary():
    from core.valuechain.smolt_model import smolt_model
    result = smolt_model.get_summary()
    if isinstance(result, dict):
        result["data_provenance"] = DataProvenance.live(SMOLT_LABEL, confidence=0.75).to_dict()
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
    await biomass_predictor.compute_outlook(horizon, scenarios, regulatory)
    result = biomass_predictor.get_outlook_dict()
    if not result:
        raise HTTPException(status_code=503, detail="Biomass outlook computation failed")
    lineage = result.get("lineage")
    result["data_provenance"] = provenance_for(
        lineage, "Biomass model + Fiskeridirektoratet + BarentsWatch lice/temperature", 0.75
    )
    return result


@router.get("/biomass/scenarios")
async def biomass_scenarios():
    """Compare regulatory scenarios (current vs all-green vs all-red)."""
    from core.market.biomass_predictor import biomass_predictor
    # Cache keys include the scenario, so each call computes fresh results.
    await biomass_predictor.compute_outlook(20, 500, "current")
    current_dict = biomass_predictor.get_outlook_dict()
    current_lineage = (current_dict or {}).get("lineage")
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
        # Both scenario runs project from the same current state, so they share
        # its lineage (WS-14).
        "lineage": current_lineage,
        "data_provenance": provenance_for(
            current_lineage, "Biomass model + Fiskeridirektoratet + BarentsWatch lice/temperature", 0.75
        ),
    }
