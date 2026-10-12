"""
Decision Engine + Treatment routes — farmer decision cards, treatment logging,
efficacy tracking, and treatment cost optimizer.
Extracted from core/api.py (Session 8).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from core.schemas import TreatmentOutcomeRequest, TreatmentOutcomeResponse

router = APIRouter(prefix="/api", tags=["decision", "treatment"])


# ══════════════════════════════════════════════════════════════════════
# TREATMENT COST OPTIMIZER
# ══════════════════════════════════════════════════════════════════════

@router.get("/treatment/optimize/{locality_no}")
async def treatment_optimize(locality_no: int, budget: float = None):
    """Find optimal treatment timing based on live lice trajectory and SST."""
    try:
        from core.market.treatment_optimizer import treatment_optimizer
        return treatment_optimizer.optimize_timing(locality_no, budget_nok=budget)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Treatment optimization failed for locality {locality_no}: {e}")


@router.get("/treatment/compare/{locality_no}")
async def treatment_compare(locality_no: int):
    """Compare ROI across 5 treatment methods using live farm data."""
    try:
        from core.market.treatment_optimizer import treatment_optimizer
        return treatment_optimizer.compare_treatments(locality_no)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Treatment comparison failed for locality {locality_no}: {e}")


@router.get("/treatment/network-schedule/{pa}")
async def treatment_network_schedule(pa: int):
    """Coordinate PA-wide treatment schedule using live farm graph data."""
    try:
        from core.market.treatment_optimizer import treatment_optimizer
        return treatment_optimizer.network_schedule(pa)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Network schedule failed for PA {pa}: {e}")


@router.get("/treatment/cost-benefit/{locality_no}")
async def treatment_cost_benefit(locality_no: int, treatment_type: str = "mechanical"):
    """Project post-treatment lice trajectory vs cost using live baseline."""
    try:
        from core.market.treatment_optimizer import treatment_optimizer
        return treatment_optimizer.cost_benefit_analysis(locality_no, treatment_type)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Cost benefit analysis failed for locality {locality_no}: {e}")


@router.get("/treatment/cost-comparison")
async def treatment_cost_comparison(
    locality_no: int = None,
    biomass_tonnes: float = 500,
    lice_level: float = 0.5,
):
    """Interactive cost comparison calculator across all treatment methods.

    Computes total cost, expected lice reduction, ROI, mortality risk, and
    a recommendation score for each method. Optionally incorporates learned
    efficacy from the Efficacy Marketplace when available.
    """
    import datetime as dt
    from core.market.treatment_constants import (
        TREATMENT_PROFILES as _PROFILES,
    )
    from core.market.data_provenance import DataProvenance

    biomass_kg = biomass_tonnes * 1000
    salmon_value_nok_per_kg = 95.0
    avg_fish_weight_kg = 4.5
    fish_count = biomass_kg / avg_fish_weight_kg

    # Fetch sea temperature if locality provided (async DB)
    sea_temp_c = 10.0
    if locality_no:
        try:
            from core.models import LiceRecord
            from core.async_db import get_async_session
            from sqlalchemy import select, desc
            async with get_async_session() as s:
                row = (await s.execute(
                    select(LiceRecord.sea_temp_c)
                    .where(LiceRecord.locality_no == locality_no)
                    .order_by(desc(LiceRecord.year), desc(LiceRecord.week))
                    .limit(1)
                )).scalar()
                if row:
                    sea_temp_c = float(row)
        except Exception:
            pass

    # Fetch learned efficacy profiles from marketplace (async DB)
    learned_profiles = {}
    locality_pa = None
    try:
        from core.market.efficacy_marketplace import efficacy_marketplace
        learned_profiles = await efficacy_marketplace.get_learned_profiles()
        if locality_no:
            from core.models import Locality
            from core.async_db import get_async_session
            from sqlalchemy import select
            async with get_async_session() as s:
                locality_pa = (await s.execute(
                    select(Locality.production_area)
                    .where(Locality.locality_no == locality_no)
                )).scalar()
    except Exception:
        pass

    # Cost of inaction over 4 weeks (growth loss + mortality)
    growth_loss_per_week = 0.03 * lice_level * fish_count * avg_fish_weight_kg * salmon_value_nok_per_kg
    mortality_loss_per_week = 0.005 * max(0, lice_level - 0.3) * fish_count * avg_fish_weight_kg * salmon_value_nok_per_kg
    avoided_loss_4w = (growth_loss_per_week + mortality_loss_per_week) * 4

    methods = []
    for key, profile in _PROFILES.items():
        # Use literature efficacy
        efficacy_pct = profile.efficacy_pct
        efficacy_source = "literature"

        # Override with learned marketplace data if available
        if learned_profiles and locality_pa is not None:
            learned = learned_profiles.get((key, locality_pa))
            if learned and learned.get("sample_size", 0) >= 5:
                efficacy_pct = learned["reduction_pct"]
                efficacy_source = f"marketplace (n={learned['sample_size']})"

        # Temperature suitability
        t_lo, t_hi = profile.suitable_temp_range
        temp_suitable = t_lo <= sea_temp_c <= t_hi
        temp_penalty = 1.0 if temp_suitable else 0.85

        # Costs
        total_cost = profile.cost_per_fish_nok * fish_count
        mortality_cost = (profile.mortality_risk_pct / 100) * fish_count * avg_fish_weight_kg * salmon_value_nok_per_kg
        total_with_mortality = total_cost + mortality_cost

        # Efficacy
        effective_efficacy = efficacy_pct * temp_penalty
        expected_reduction = (effective_efficacy / 100) * lice_level
        post_treatment_lice = lice_level - expected_reduction

        # ROI
        roi = (avoided_loss_4w - total_with_mortality) / total_with_mortality if total_with_mortality > 0 else 0

        # Recommendation score: higher is better
        # Weights: efficacy 40%, ROI 25%, low mortality 20%, low resistance 10%, temp suitability 5%
        resistance_score = {"none": 1.0, "emerging": 0.6, "high": 0.2}.get(profile.resistance_risk, 0.5)
        mortality_score = max(0, 1.0 - profile.mortality_risk_pct / 5.0)
        rec_score = (
            0.40 * (effective_efficacy / 100)
            + 0.25 * min(1.0, max(0, roi / 5.0))
            + 0.20 * mortality_score
            + 0.10 * resistance_score
            + 0.05 * (1.0 if temp_suitable else 0.3)
        )

        methods.append({
            "key": key,
            "name": profile.label,
            "efficacy_pct": round(effective_efficacy, 1),
            "efficacy_range": list(profile.efficacy_range),
            "efficacy_source": efficacy_source,
            "mortality_risk_pct": profile.mortality_risk_pct,
            "cost_per_kg_nok": round(profile.cost_per_fish_nok / avg_fish_weight_kg, 2),
            "total_cost_nok": round(total_cost),
            "mortality_cost_nok": round(mortality_cost),
            "total_with_mortality_nok": round(total_with_mortality),
            "expected_lice_reduction": round(expected_reduction, 4),
            "post_treatment_lice": round(post_treatment_lice, 4),
            "roi": round(roi, 2),
            "recovery_weeks": profile.recovery_weeks,
            "resistance_risk": profile.resistance_risk,
            "environmental_impact": profile.environmental_impact,
            "temp_suitable": temp_suitable,
            "suitable_temp_range": list(profile.suitable_temp_range),
            "recommendation_score": round(rec_score, 3),
        })

    # Sort by recommendation score descending
    methods.sort(key=lambda m: m["recommendation_score"], reverse=True)

    # Mark top method as recommended
    for i, m in enumerate(methods):
        m["rank"] = i + 1
        m["recommended"] = i == 0

    return {
        "methods": methods,
        "inputs": {
            "biomass_tonnes": biomass_tonnes,
            "lice_level": lice_level,
            "locality_no": locality_no,
            "sea_temp_c": round(sea_temp_c, 1),
            "fish_count": round(fish_count),
        },
        "avoided_loss_4w_nok": round(avoided_loss_4w),
        "recommended_method": methods[0]["key"] if methods else None,
        "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        "data_provenance": DataProvenance.live(
            "Treatment constants (Overton 2019) + cost model",
            confidence=0.85,
        ).to_dict(),
    }


# ══════════════════════════════════════════════════════════════════════
# DECISION ENGINE (Farmer Decision Cards)
# ══════════════════════════════════════════════════════════════════════

@router.get("/decision/{locality_no}")
async def farm_decision(locality_no: int):
    """Get actionable decision card for a farm."""
    from core.market.decision_engine import decision_engine
    return await decision_engine.get_decision(locality_no)


@router.get("/decision/portfolio/{company_name}")
async def portfolio_decisions(company_name: str):
    """Get decision cards for all farms in a company portfolio."""
    from core.market.decision_engine import decision_engine
    return await decision_engine.portfolio_decisions(company_name)


@router.post("/treatment/log-outcome", response_model=TreatmentOutcomeResponse)
async def log_treatment_outcome(request: Request, data: TreatmentOutcomeRequest):
    """Log a validated treatment outcome for efficacy tracking.

    Validates input via Pydantic model:
    - pre_lice_count must be > 0
    - post_lice_count must be >= 0 and <= pre_lice_count
    - method must be one of: mechanical, thermal, freshwater, medicinal, biological
    - mortality_observed must be 0-100%
    """
    from core.market.efficacy_marketplace import efficacy_marketplace
    result = await efficacy_marketplace.log_outcome(data)

    # Audit: treatment outcome logged
    from core.audit import log_action, get_client_ip
    await log_action(
        None, "log_treatment",
        f"locality:{data.locality_no}",
        details={"method": data.method, "pre_lice": data.pre_lice_count, "post_lice": data.post_lice_count},
        ip=get_client_ip(request),
    )

    return result


@router.get("/treatment/efficacy-by-method")
async def treatment_efficacy_by_method():
    """Aggregate treatment efficacy comparison from real outcomes."""
    from core.market.decision_engine import decision_engine
    return await decision_engine.efficacy_by_method()


# ══════════════════════════════════════════════════════════════════════
# TREATMENT HISTORY (Per-Locality Timeline)
# ══════════════════════════════════════════════════════════════════════

@router.get("/treatment/history/{locality_no}")
async def treatment_history(locality_no: int, limit: int = Query(20, ge=1, le=1000)):
    """Get treatment history for a specific locality."""
    from core.async_db import get_async_session
    from sqlalchemy import text
    async with get_async_session() as s:
        rows = (await s.execute(text("""
            SELECT treatment_date, method, pre_lice_count, post_lice_count,
                   mortality_observed, cost_nok, notes, resistance_observed
            FROM treatment_outcomes
            WHERE locality_no = :loc
            ORDER BY treatment_date DESC
            LIMIT :lim
        """), {"loc": locality_no, "lim": limit})).fetchall()
    return [
        {
            "date": str(r[0]) if r[0] else None,
            "method": r[1],
            "pre_lice": float(r[2]) if r[2] else None,
            "post_lice": float(r[3]) if r[3] else None,
            "mortality": float(r[4]) if r[4] else None,
            "cost_nok": float(r[5]) if r[5] else None,
            "notes": r[6],
            "resistance_observed": bool(r[7]) if r[7] is not None else False,
        }
        for r in rows
    ]


# ══════════════════════════════════════════════════════════════════════
# EFFICACY MARKETPLACE (Crowdsourced Treatment Efficacy Database)
# ══════════════════════════════════════════════════════════════════════

@router.get("/efficacy/benchmarks")
async def efficacy_benchmarks():
    """Industry-wide treatment efficacy benchmarks per method."""
    from core.market.efficacy_marketplace import efficacy_marketplace
    return await efficacy_marketplace.get_method_benchmarks()


@router.get("/efficacy/by-region")
async def efficacy_by_region():
    """Treatment efficacy broken down by production area."""
    from core.market.efficacy_marketplace import efficacy_marketplace
    return await efficacy_marketplace.get_regional_efficacy()


@router.get("/efficacy/by-season")
async def efficacy_by_season():
    """How treatment efficacy varies by season and month."""
    from core.market.efficacy_marketplace import efficacy_marketplace
    return await efficacy_marketplace.get_seasonal_patterns()


@router.get("/efficacy/learned-profiles")
async def efficacy_learned_profiles():
    """Current learned efficacy profiles from crowdsourced outcomes.

    Returns (method, PA) cells with >= 5 outcomes that the Decision Engine
    uses to override static literature profiles. Includes sample sizes and
    data provenance with confidence based on sample count.
    """
    from core.market.efficacy_marketplace import efficacy_marketplace
    from core.market.data_provenance import DataProvenance
    import datetime as dt

    profiles = await efficacy_marketplace.get_learned_profiles()

    # Flatten to list for JSON serialization (tuple keys not JSON-safe)
    items = []
    for (method, pa), data in profiles.items():
        items.append({
            "method": method,
            "production_area": pa,
            **data,
        })

    total_outcomes = sum(d["sample_size"] for d in items)

    return {
        "profiles": items,
        "total_cells": len(items),
        "total_outcomes": total_outcomes,
        "note": "Cells with >= 5 outcomes. Used by Decision Engine to override static literature rates.",
        "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        "data_provenance": DataProvenance.live(
            "Crowdsourced treatment outcomes (learned profiles)",
            confidence=min(0.9, 0.3 + 0.03 * total_outcomes),
        ).to_dict(),
    }


@router.get("/efficacy/explore")
async def efficacy_explore(
    method: str = None,
    production_area: int = None,
    temp_min: float = None,
    temp_max: float = None,
    season: str = None,
):
    """Multi-dimensional efficacy exploration with filters."""
    from core.market.efficacy_marketplace import efficacy_marketplace
    temp_range = (temp_min, temp_max) if temp_min is not None and temp_max is not None else None
    return await efficacy_marketplace.aggregate_by_dimensions(
        method=method,
        production_area=production_area,
        temp_range=temp_range,
        season=season,
    )
