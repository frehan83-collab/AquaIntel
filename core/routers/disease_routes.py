"""
Disease Intelligence routes — Mattilsynet, WOAH, global alerts.
Extracted from core/api.py (Session 8).
"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Query
from sqlalchemy import select

from core.async_db import get_async_session
from core.models import Locality
from core.market.data_provenance import DataProvenance

router = APIRouter(prefix="/api/disease", tags=["disease"])


@router.get("/norway")
async def disease_norway():
    """Real-time disease outbreaks from Mattilsynet (Norwegian Food Safety Authority).
    Covers ISA, PD (SAV2/SAV3), IHN — per locality with full timeline."""
    from core.market.mattilsynet_client import mattilsynet_client
    cases = await mattilsynet_client.fetch_disease_cases(limit=100)
    result = await mattilsynet_client.get_disease_summary(cases)
    if isinstance(result, dict):
        result["data_provenance"] = DataProvenance.live("Mattilsynet + WOAH + Sernapesca", confidence=0.90).to_dict()
    return result


@router.get("/norway/geo")
async def disease_norway_geo():
    """Disease outbreaks with coordinates for map overlay.
    Joins Mattilsynet cases with BarentsWatch locality positions."""
    from core.market.mattilsynet_client import mattilsynet_client
    cases = await mattilsynet_client.fetch_disease_cases(limit=100)

    # Look up coordinates from our locality database
    active = [c for c in cases if c.status == "active"]
    if not active:
        return {"features": [], "type": "FeatureCollection"}

    locality_nos = [c.locality_no for c in active]
    coords = {}
    async with get_async_session() as s:
        rows = (await s.execute(
            select(Locality.locality_no, Locality.latitude, Locality.longitude, Locality.owner_company)
            .where(Locality.locality_no.in_(locality_nos))
        )).all()
        for r in rows:
            coords[r[0]] = {"lat": float(r[1] or 0), "lng": float(r[2] or 0), "company": r[3] or ""}

    DISEASE_NAMES = {
        "PANKREASSYKDOM": "PD", "ILA": "ISA", "INFEKSIØS_LAKSEANEMI": "ISA",
        "IHN": "IHN", "FRANCISELLOSE": "Francisellosis", "BAKTERIELL_NYRESYKE": "BKD",
    }
    SEVERITY = {"ISA": "critical", "IHN": "critical", "PD": "high", "Francisellosis": "medium", "BKD": "medium"}

    features = []
    for c in active:
        loc = coords.get(c.locality_no)
        if not loc or not loc["lat"]:
            continue
        disease = DISEASE_NAMES.get(c.disease_type, c.disease_type)
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [loc["lng"], loc["lat"]]},
            "properties": {
                "locality_no": c.locality_no,
                "locality_name": c.locality_name,
                "disease": disease,
                "subtype": c.disease_subtype or "",
                "severity": SEVERITY.get(disease, "medium"),
                "company": loc["company"],
                "suspicion_date": c.suspicion_date,
                "diagnosis_date": c.diagnosis_date,
                "days_active": (dt.datetime.now(dt.UTC) - dt.datetime.fromisoformat(
                    c.suspicion_date.replace("Z", "+00:00")
                )).days if c.suspicion_date else 0,
            },
        })

    return {
        "type": "FeatureCollection",
        "features": features,
        "total_active": len(active),
        "data_provenance": DataProvenance.live("Mattilsynet + WOAH + Sernapesca", confidence=0.90).to_dict(),
    }


@router.get("/treatments")
async def disease_treatments(year: int = 2026, limit: int = Query(50, ge=1, le=1000)):
    """Lice treatment reports with medicinal/non-medicinal details + resistance data.
    Unique data not available from BarentsWatch."""
    from core.market.mattilsynet_client import mattilsynet_client
    treatments = await mattilsynet_client.fetch_lice_treatments(year, limit)
    with_treatment = [t for t in treatments if t.non_medicinal_treatments or t.medicinal_treatments]
    with_resistance = [t for t in treatments if t.resistance_suspicions]
    return {
        "source": "Mattilsynet (Norwegian Food Safety Authority)",
        "year": year,
        "total_reports": len(treatments),
        "with_treatments": len(with_treatment),
        "with_resistance_suspicions": len(with_resistance),
        "reports": [
            {
                "locality_no": t.locality_no,
                "locality_name": t.locality_name,
                "company": t.company,
                "week": t.week,
                "year": t.year,
                "sea_temp": t.sea_temp,
                "lice": {
                    "adult_female": t.adult_female_lice,
                    "mobile": t.mobile_lice,
                    "sessile": t.sessile_lice,
                },
                "treatments": {
                    "non_medicinal": t.non_medicinal_treatments,
                    "medicinal": t.medicinal_treatments,
                    "combination": t.combination_treatments,
                },
                "resistance_suspicions": t.resistance_suspicions,
                "sensitivity_tests": t.sensitivity_tests,
            }
            for t in treatments[:limit]
        ],
        "data_provenance": DataProvenance.live("Mattilsynet + WOAH + Sernapesca", confidence=0.90).to_dict(),
    }


@router.get("/by-company")
async def disease_by_company():
    """Active disease cases aggregated per company. Used by Leaders, ESG, Benchmark."""
    from core.market.mattilsynet_client import mattilsynet_client
    cases = await mattilsynet_client.fetch_disease_cases(limit=200)
    result = await mattilsynet_client.get_company_disease_counts(cases)
    if isinstance(result, dict):
        result["data_provenance"] = DataProvenance.live("Mattilsynet + WOAH + Sernapesca", confidence=0.90).to_dict()
    return result


@router.get("/alerts")
async def disease_alerts():
    """Global fish disease outbreak intelligence — WOAH, Sernapesca, Regime."""
    from core.market.disease_alerts import disease_alert_engine
    di = await disease_alert_engine.fetch_alerts()
    result = disease_alert_engine.to_dict(di)
    if isinstance(result, dict):
        result["data_provenance"] = DataProvenance.live("Mattilsynet + WOAH + Sernapesca", confidence=0.90).to_dict()
    return result


@router.get("/resistance-map")
async def resistance_map():
    """PA x method resistance matrix from Mattilsynet treatment data.
    Tracks treatment frequency per method per PA and estimates resistance risk.
    Includes freshwater resistance flag (Norwegian Veterinary Institute 2025)."""
    from core.market.resistance_tracker import resistance_tracker
    result = await resistance_tracker.build_resistance_matrix()
    result["data_provenance"] = DataProvenance.live(
        "Mattilsynet treatment reports + Norwegian Veterinary Institute",
        confidence=0.80,
    ).to_dict()
    return result


@router.get("/resistance/pa/{pa}")
async def resistance_by_pa(pa: int):
    """Resistance profile for a single production area.
    Shows treatment counts, frequency risk, inherent resistance risk per method."""
    from core.market.resistance_tracker import resistance_tracker
    return await resistance_tracker.get_pa_resistance(pa)
