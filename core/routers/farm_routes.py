"""
Farm advisory, farm graph, harvest optimizer, exposure, biomass, and portfolio routes.
Extracted from core/api.py (Session 10 — Router Wave 4).
Biomass endpoints added Session 23.
"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, func, or_

from core.models import LiceRecord, Locality
from core.async_db import get_async_session

router = APIRouter(tags=["farm"])


# ── Biomass Status (Fiskeridirektoratet) ────────────────────────────

@router.get("/api/farms/biomass/national")
async def biomass_national():
    """National biomass summary: total standing, MAB utilization, by PA."""
    from core.market.fiskeridir_biomass import fiskeridir_biomass
    return await fiskeridir_biomass.get_national_summary()


@router.get("/api/farms/biomass/pa/{pa}")
async def biomass_by_pa(pa: int):
    """Biomass data for a specific production area."""
    from core.market.fiskeridir_biomass import fiskeridir_biomass

    if pa < 1 or pa > 13:
        raise HTTPException(status_code=400, detail="Production area must be 1-13")

    return await fiskeridir_biomass.get_by_production_area(pa)


@router.get("/api/farms/biomass/locality/{locality_no}")
async def biomass_by_locality(locality_no: int):
    """Biomass status for a single locality."""
    from core.market.fiskeridir_biomass import fiskeridir_biomass
    return await fiskeridir_biomass.get_by_locality(locality_no)


@router.get("/api/farmer-advisory/{locality_no}")
async def farmer_advisory(locality_no: int):
    """Farm-level advisory (Professional+ tier)."""
    from core.valuechain.farmer_advisory import generate_farm_advisory

    async with get_async_session() as s:
        latest = (await s.execute(
            select(LiceRecord)
            .where(LiceRecord.locality_no == locality_no)
            .order_by(LiceRecord.year.desc(), LiceRecord.week.desc())
            .limit(1)
        )).scalar_one_or_none()

    if not latest:
        raise HTTPException(status_code=404, detail=f"No data for locality {locality_no}")

    advisory = generate_farm_advisory(
        locality_no=locality_no,
        current_lice=latest.avg_adult_female_lice or 0,
        sea_temp=latest.sea_temp_c or 8,
        forecasts_1w=[],
        forecasts_2w=[],
    )

    from core.source_lineage import provenance_for, summarise_rows

    # WS-14: the advisory's inputs are exactly this one lice row.
    lineage = summarise_rows([latest])
    return {
        "locality_no": advisory.locality_no,
        "risk_level": advisory.risk_level,
        "risk_score": advisory.risk_score,
        "current_lice": advisory.current_lice,
        "treatment_needed": advisory.treatment_needed,
        "recommended_treatment": advisory.recommended_treatment,
        "treatment_urgency": advisory.treatment_urgency,
        "harvest_advice": advisory.harvest_advice,
        "forecast_1w": advisory.forecast_1w,
        "forecast_2w": advisory.forecast_2w,
        "trend": advisory.trend,
        "summary": advisory.summary,
        "lineage": lineage,
        "data_provenance": provenance_for(
            lineage, "BarentsWatch lice + farm advisory model", 0.85
        ),
    }


# ── Farm Network Graph ───────────────────────────────────────────────

@router.get("/api/farm-graph/summary")
async def farm_graph_summary():
    """Get farm network graph statistics."""
    from core.market.data_provenance import DataProvenance
    from core.market.farm_graph import farm_graph
    result = await farm_graph.get_graph_summary()
    if isinstance(result, dict):
        result.setdefault("data_provenance", DataProvenance.degraded(
            "Farm network graph (BarentsWatch lice + locality registry)",
            reason=(
                "derived proximity/network graph over registered localities — a "
                "model artefact, not a reported figure"
            ),
            confidence=0.5,
        ).to_dict())
    return result


@router.get("/api/farm-graph/clusters")
async def farm_graph_clusters(risk_level: str = None):
    """Get farm clusters with risk assessment."""
    from core.market.farm_graph import farm_graph
    return await farm_graph.get_clusters(risk_level)


@router.get("/api/farm-graph/cascades")
async def farm_graph_cascades():
    """Get predicted treatment cascade events."""
    from core.market.farm_graph import farm_graph
    return await farm_graph.get_cascade_predictions()


@router.get("/api/farm-graph/company-exposure")
async def farm_graph_company_exposure():
    """Get per-company network exposure risk scores."""
    from core.market.farm_graph import farm_graph
    return await farm_graph.get_company_network_exposure()


@router.get("/api/farm-graph/farm/{locality_no}")
async def farm_graph_neighbors(locality_no: int):
    """Get a farm's neighbors and connections."""
    from core.market.farm_graph import farm_graph
    return await farm_graph.get_farm_neighbors(locality_no)


@router.get("/api/farm-graph/map-data")
async def farm_graph_map():
    """Get full map visualization data (nodes + edges + clusters)."""
    from core.market.data_provenance import DataProvenance
    from core.market.farm_graph import farm_graph
    result = await farm_graph.get_map_data()
    if isinstance(result, dict):
        result.setdefault("data_provenance", DataProvenance.degraded(
            "Farm network graph (BarentsWatch lice + locality registry)",
            reason=(
                "derived proximity/network graph over registered localities — a "
                "model artefact, not a reported figure"
            ),
            confidence=0.5,
        ).to_dict())
    return result


# ── Harvest Optimizer ────────────────────────────────────────────────

@router.get("/api/harvest/optimize/{locality_no}")
async def harvest_optimize(locality_no: int):
    """Optimal harvest recommendation for a single farm using LIVE data."""
    from core.ml.harvest_optimizer import harvest_optimizer
    return await harvest_optimizer.optimize(locality_no)


@router.get("/api/harvest/portfolio/{company_name}")
async def harvest_portfolio(company_name: str):
    """Run harvest optimizer across all farms for a company."""
    from core.ml.harvest_optimizer import harvest_optimizer
    return await harvest_optimizer.portfolio(company_name)


@router.get("/api/harvest/simulate")
async def harvest_simulate(locality_no: int, weeks: int = 12):
    """Simulate N-week trajectory under the harvest policy."""
    from core.ml.harvest_optimizer import harvest_optimizer
    return await harvest_optimizer.simulate(locality_no, weeks=weeks)


# ── Farm Portfolio ──────────────────────────────────────────────────

@router.get("/api/farms/portfolio")
async def farm_portfolio(locality_nos: str = Query(..., description="Comma-separated locality numbers")):
    """Multi-farm portfolio overview with lice, decisions, and aggregate stats."""
    from core.market.decision_engine import decision_engine
    from core.source_lineage import provenance_for, summarise_rows

    # Parse locality numbers
    try:
        loc_list = [int(x.strip()) for x in locality_nos.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="locality_nos must be comma-separated integers")

    if not loc_list:
        raise HTTPException(status_code=400, detail="At least one locality_no required")
    if len(loc_list) > 50:
        loc_list = loc_list[:50]  # Cap at 50 farms

    # Fetch latest lice data + locality info for all requested farms
    async with get_async_session() as s:
        # Get latest lice record per farm
        subq = (
            select(
                LiceRecord.locality_no,
                func.max(LiceRecord.year * 100 + LiceRecord.week).label("max_yw"),
            )
            .where(
                LiceRecord.locality_no.in_(loc_list),
                LiceRecord.avg_adult_female_lice.isnot(None),
            )
            .group_by(LiceRecord.locality_no)
            .subquery()
        )

        rows = (await s.execute(
            select(
                Locality.locality_no,
                Locality.name,
                Locality.production_area,
                Locality.owner_company,
                LiceRecord.avg_adult_female_lice,
                LiceRecord.sea_temp_c,
                LiceRecord.has_cleaner_fish,
                LiceRecord.year,
                LiceRecord.week,
                LiceRecord.source,
                LiceRecord.fetched_at,
            )
            .join(LiceRecord, LiceRecord.locality_no == Locality.locality_no)
            .join(subq, (
                LiceRecord.locality_no == subq.c.locality_no
            ) & (
                (LiceRecord.year * 100 + LiceRecord.week) == subq.c.max_yw
            ))
            .where(Locality.locality_no.in_(loc_list))
        )).all()

    # WS-14: one lineage over every row behind the portfolio cards.
    lineage = summarise_rows(rows)

    # Build per-farm data with decision cards
    farms = []
    total_lice = 0.0
    farms_needing_treatment = 0
    lice_count = 0

    for r in rows:
        loc_no, name, pa, company, lice, temp, cleaner, year, week = r
        lice_val = float(lice) if lice is not None else 0.0
        total_lice += lice_val
        lice_count += 1

        # Get decision for this farm
        decision = await decision_engine.get_decision(loc_no)
        action = decision.get("action", "UNKNOWN") if "error" not in decision else "UNKNOWN"
        urgency = decision.get("urgency", "") if "error" not in decision else ""
        method = decision.get("recommended_method", "") if "error" not in decision else ""
        roi = decision.get("roi_estimate", 0) if "error" not in decision else 0

        # Determine risk level
        if lice_val > 0.5:
            risk = "critical"
        elif lice_val > 0.3:
            risk = "high"
        elif lice_val > 0.15:
            risk = "moderate"
        else:
            risk = "low"

        if action in ("TREAT_NOW", "SCHEDULE_TREATMENT"):
            farms_needing_treatment += 1

        farms.append({
            "locality_no": loc_no,
            "name": name or f"Locality {loc_no}",
            "production_area": pa,
            "company": company or "",
            "lice_level": round(lice_val, 4),
            "sea_temp_c": round(float(temp), 1) if temp else None,
            "has_cleaner_fish": bool(cleaner),
            "data_week": f"{year}W{week:02d}" if year and week else None,
            "risk_level": risk,
            "decision": {
                "action": action,
                "urgency": urgency,
                "recommended_method": method,
                "roi_estimate": round(roi, 1) if roi else 0,
                "reasoning": decision.get("reasoning", []) if "error" not in decision else [],
            },
        })

    # Sort by risk level (highest first)
    risk_order = {"critical": 0, "high": 1, "moderate": 2, "low": 3}
    farms.sort(key=lambda f: (risk_order.get(f["risk_level"], 4), -f["lice_level"]))

    avg_lice = round(total_lice / lice_count, 4) if lice_count > 0 else 0.0

    return {
        "farms": farms,
        "summary": {
            "total_farms": len(farms),
            "avg_lice_level": avg_lice,
            "farms_needing_treatment": farms_needing_treatment,
            "risk_breakdown": {
                "critical": sum(1 for f in farms if f["risk_level"] == "critical"),
                "high": sum(1 for f in farms if f["risk_level"] == "high"),
                "moderate": sum(1 for f in farms if f["risk_level"] == "moderate"),
                "low": sum(1 for f in farms if f["risk_level"] == "low"),
            },
        },
        "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        "lineage": lineage,
        "data_provenance": provenance_for(
            lineage, "BarentsWatch + Decision Engine", 0.85
        ),
    }


# ── Exposure Sites ───────────────────────────────────────────────────

@router.get("/api/exposure/sites")
async def exposure_sites():
    """All localities with coordinates, latest lice values, and company attribution."""
    async with get_async_session() as s:
        recent_weeks = (await s.execute(
            select(LiceRecord.year, LiceRecord.week)
            .distinct()
            .order_by(LiceRecord.year.desc(), LiceRecord.week.desc())
            .limit(2)
        )).all()

        if not recent_weeks:
            return []

        week_filter = or_(
            *[(LiceRecord.year == y) & (LiceRecord.week == w) for y, w in recent_weeks]
        )

        subq = (
            select(
                LiceRecord.locality_no,
                func.max(LiceRecord.year * 100 + LiceRecord.week).label("max_yw"),
            )
            .where(week_filter, LiceRecord.avg_adult_female_lice.isnot(None))
            .group_by(LiceRecord.locality_no)
            .subquery()
        )

        rows = (await s.execute(
            select(
                Locality.locality_no,
                Locality.name,
                Locality.latitude,
                Locality.longitude,
                Locality.owner_company,
                Locality.production_area,
                LiceRecord.avg_adult_female_lice,
                LiceRecord.has_cleaner_fish,
                LiceRecord.sea_temp_c,
            )
            .join(LiceRecord, LiceRecord.locality_no == Locality.locality_no)
            .join(subq, (
                LiceRecord.locality_no == subq.c.locality_no
            ) & (
                (LiceRecord.year * 100 + LiceRecord.week) == subq.c.max_yw
            ))
            .where(
                Locality.latitude.isnot(None),
                Locality.longitude.isnot(None),
                LiceRecord.avg_adult_female_lice.isnot(None),
            )
        )).all()

    return [
        {
            "id": r[0],
            "name": r[1],
            "lat": round(r[2], 5),
            "lng": round(r[3], 5),
            "company": r[4] or "",
            "pa": r[5],
            "lice": round(r[6], 4),
            "cleaner_fish": r[7] or False,
            "temp": round(r[8], 1) if r[8] else None,
        }
        for r in rows
    ]


# ── Offshore Farm Endpoints (Session 28) ──────────────────────────────
# Reference: SalMar Ocean Farm 1/2, Oppedal et al. (2017)


@router.get("/api/farms/offshore")
async def list_offshore_farms():
    """List all offshore and semi-offshore farm sites with their parameters."""
    from core.market.offshore_engine import offshore_engine
    return await offshore_engine.get_offshore_farms()


@router.get("/api/farms/offshore/{locality_no}/risk")
async def offshore_risk_assessment(locality_no: int):
    """Structural and environmental risk assessment for an offshore farm.

    Factors: wave exposure, current stress, access difficulty, net depth.
    Returns composite risk score (0.0-1.0) with component breakdown.
    Reference: DNV GL STANDARD FOR CERTIFICATION No. 2.1
    """
    from core.market.offshore_engine import offshore_engine
    result = await offshore_engine.compute_structural_risk(locality_no)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/api/farms/offshore/lice-comparison")
async def offshore_lice_comparison():
    """Compare lice levels between inshore and offshore farms.

    Offshore farms typically show 60-80% lower adult female lice counts
    due to stronger currents dispersing copepodid larvae.
    Reference: Oppedal et al. (2017), Samsing et al. (2015)
    """
    from core.market.offshore_engine import offshore_engine
    return await offshore_engine.offshore_lice_comparison()


# ── Fish Welfare Scoring (Session 32) ───────────────────────────────
# Reference: Stien et al. (2013) "Salmon Welfare Index Model (SWIM)"

@router.get("/api/welfare/score/{locality_no}")
async def welfare_score(locality_no: int):
    """Get welfare score (0-100) for a farm with 5-component breakdown.

    Components: lice burden (35%), thermal stress (15%), mortality trend (20%),
    oxygen/environment (15%), treatment stress (15%).
    Also predicts 7-day mortality using heuristic model.
    """
    from core.market.welfare_scorer import welfare_scorer
    from core.source_lineage import provenance_for
    result = await welfare_scorer.score_farm(locality_no)
    payload = result.to_dict()
    # WS-14: 35% of the score is lice burden — carry the lineage of that row.
    payload["data_provenance"] = provenance_for(
        payload.get("lice_lineage"), "SWIM welfare score (Stien et al. 2013)", 0.75
    )
    return payload


@router.get("/api/welfare/pa/{pa}")
async def welfare_pa_summary(pa: int):
    """Get welfare scores for all farms in a production area.

    Returns per-farm scores + PA-level aggregates (avg score, grade distribution).
    """
    from core.market.welfare_scorer import welfare_scorer

    if pa < 1 or pa > 13:
        raise HTTPException(status_code=400, detail="Production area must be 1-13")

    # Query all localities in this PA
    async with get_async_session() as session:
        localities = (await session.execute(
            select(Locality.locality_no, Locality.name)
            .where(Locality.production_area == pa)
            .order_by(Locality.locality_no)
            .limit(100)
        )).all()

    if not localities:
        return {
            "pa": pa,
            "farms": [],
            "summary": {"avg_score": 0, "farm_count": 0, "grade_distribution": {}},
        }

    # Score each farm
    farm_scores = []
    farm_lineages: list = []
    for loc_no, loc_name in localities:
        try:
            score = await welfare_scorer.score_farm(loc_no)
            farm_lineages.append(score.lice_lineage)
            farm_scores.append({
                "locality_no": loc_no,
                "name": loc_name or f"Locality {loc_no}",
                "total_score": score.total_score,
                "grade": score.grade,
                "predicted_mortality_7d": score.predicted_mortality_7d,
                "alert_reason": score.alert_reason,
            })
        except Exception:
            farm_lineages.append(None)
            farm_scores.append({
                "locality_no": loc_no,
                "name": loc_name or f"Locality {loc_no}",
                "total_score": None,
                "grade": "N/A",
                "predicted_mortality_7d": None,
                "alert_reason": "Scoring failed",
            })

    # Aggregate
    scored = [f for f in farm_scores if f["total_score"] is not None]
    avg_score = round(sum(f["total_score"] for f in scored) / len(scored), 1) if scored else 0

    grade_dist: dict[str, int] = {}
    for f in scored:
        g = f["grade"]
        grade_dist[g] = grade_dist.get(g, 0) + 1

    # Sort by score ascending (worst first)
    farm_scores.sort(key=lambda f: f["total_score"] if f["total_score"] is not None else 999)

    from core.source_lineage import merge_lineages, provenance_for
    # WS-14: merge every farm's own lineage — a failed farm degrades the roll-up
    # instead of hiding behind the newest national week.
    lineage = merge_lineages(farm_lineages)

    return {
        "pa": pa,
        "farms": farm_scores,
        "summary": {
            "avg_score": avg_score,
            "farm_count": len(scored),
            "grade_distribution": grade_dist,
        },
        "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        "lineage": lineage,
        "data_provenance": provenance_for(
            lineage, "SWIM welfare scores (Stien et al. 2013)", 0.75
        ),
    }
