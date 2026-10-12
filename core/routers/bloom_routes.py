"""
Bloom Risk Routes
==================
Extracted from core/api.py for maintainability.
Algal bloom risk assessments, alerts, and chlorophyll data.
Includes unified bio-risk snapshot endpoint for time slider.
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict

from fastapi import APIRouter, Query
from sqlalchemy import select, func, and_

from core.models import Locality, LiceRecord
from core.async_db import get_async_session
from core.bloom.models import BloomRiskAssessment, BloomAlert, ChlorophyllReading
from core.market.data_provenance import DataProvenance

router = APIRouter(prefix="/api/bloom", tags=["bloom"])

# Secondary router for bio-risk namespace (registered separately in api.py)
bio_risk_router = APIRouter(prefix="/api/bio-risk", tags=["bio-risk"])


@router.get("/risk")
async def bloom_risk_map(limit: int = Query(1500, ge=1, le=10000)):
    """Latest bloom risk assessment per locality."""
    async with get_async_session() as s:
        # Get the most recent assessment per locality
        subq = (
            select(
                BloomRiskAssessment.locality_no,
                func.max(BloomRiskAssessment.assessed_at).label("latest"),
            )
            .group_by(BloomRiskAssessment.locality_no)
            .subquery()
        )
        assessments = (await s.execute(
            select(
                BloomRiskAssessment,
                Locality.name,
                Locality.latitude,
                Locality.longitude,
                Locality.owner_company,
            )
            .join(subq, (
                BloomRiskAssessment.locality_no == subq.c.locality_no
            ) & (
                BloomRiskAssessment.assessed_at == subq.c.latest
            ))
            .outerjoin(Locality, BloomRiskAssessment.locality_no == Locality.locality_no)
            .limit(limit)
        )).all()

    # Build chl-a sparklines per locality (last 8 assessments)
    locality_nos = [a.locality_no for a, *_ in assessments]
    sparklines: dict[int, list[float]] = {}
    if locality_nos:
        async with get_async_session() as s:
            history = (await s.execute(
                select(
                    BloomRiskAssessment.locality_no,
                    BloomRiskAssessment.chl_a_value,
                    BloomRiskAssessment.assessed_at,
                )
                .where(BloomRiskAssessment.locality_no.in_(locality_nos))
                .order_by(BloomRiskAssessment.assessed_at.asc())
            )).all()

            by_loc: dict[int, list[float]] = defaultdict(list)
            for loc_no, chl_a, _ in history:
                if chl_a is not None:
                    by_loc[loc_no].append(round(chl_a, 2))

            for loc_no, vals in by_loc.items():
                sparklines[loc_no] = vals[-8:]  # last 8 readings

    return {
        "data_provenance": DataProvenance.live("Copernicus CMEMS chlorophyll-a", confidence=0.85).to_dict(),
        "items": [
            {
                "locality_no": a.locality_no,
                "locality_name": name,
                "owner_company": owner,
                "latitude": lat,
                "longitude": lon,
                "risk_level": a.risk_level,
                "risk_score": a.risk_score,
                "chl_a": a.chl_a_value,
                "sst": a.sst_value,
                "chl_a_trend": a.chl_a_trend,
                "chl_a_sparkline": sparklines.get(a.locality_no, []),
                "assessed_at": a.assessed_at.isoformat() if a.assessed_at else None,
                "factors": a.contributing_factors,
            }
            for a, name, lat, lon, owner in assessments
        ],
    }


@router.get("/risk/{locality_no}")
async def bloom_risk_locality(locality_no: int, days: int = 30):
    """Bloom risk history for a single locality."""
    cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(days=days)
    async with get_async_session() as s:
        assessments = (await s.execute(
            select(BloomRiskAssessment)
            .where(
                BloomRiskAssessment.locality_no == locality_no,
                BloomRiskAssessment.assessed_at >= cutoff,
            )
            .order_by(BloomRiskAssessment.assessed_at.desc())
        )).scalars().all()

    return {
        "data_provenance": DataProvenance.live("Copernicus CMEMS chlorophyll-a", confidence=0.85).to_dict(),
        "items": [
            {
                "risk_level": a.risk_level,
                "risk_score": a.risk_score,
                "chl_a": a.chl_a_value,
                "sst": a.sst_value,
                "chl_a_trend": a.chl_a_trend,
                "assessed_at": a.assessed_at.isoformat() if a.assessed_at else None,
                "factors": a.contributing_factors,
            }
            for a in assessments
        ],
    }


@router.get("/alerts")
async def bloom_alerts(
    risk_level: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
):
    """Alert log for bloom notifications sent."""
    async with get_async_session() as s:
        q = select(BloomAlert).order_by(BloomAlert.sent_at.desc()).limit(limit)
        if risk_level:
            q = q.where(BloomAlert.risk_level == risk_level)
        alerts = (await s.execute(q)).scalars().all()

    return {
        "data_provenance": DataProvenance.live("Copernicus CMEMS chlorophyll-a", confidence=0.85).to_dict(),
        "items": [
            {
                "id": a.id,
                "locality_no": a.locality_no,
                "risk_level": a.risk_level,
                "channel": a.channel,
                "delivery_status": a.delivery_status,
                "sent_at": a.sent_at.isoformat() if a.sent_at else None,
                "message": a.message_text,
            }
            for a in alerts
        ],
    }


@router.get("/chlorophyll")
async def chlorophyll_data(days: int = 7, limit: int = Query(5000, ge=1, le=50000)):
    """Raw satellite chlorophyll-a readings for mapping."""
    cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(days=days)
    async with get_async_session() as s:
        readings = (await s.execute(
            select(ChlorophyllReading)
            .where(ChlorophyllReading.date >= cutoff)
            .order_by(ChlorophyllReading.date.desc())
            .limit(limit)
        )).scalars().all()

    return {
        "data_provenance": DataProvenance.live("Copernicus CMEMS chlorophyll-a", confidence=0.85).to_dict(),
        "items": [
            {
                "latitude": r.latitude,
                "longitude": r.longitude,
                "chl_a_mg_m3": r.chl_a_mg_m3,
                "date": r.date.isoformat() if r.date else None,
                "grid_cell_id": r.grid_cell_id,
            }
            for r in readings
        ],
    }


# ── Bio Risk Snapshot (Time Slider) ─────────────────────────────────

@bio_risk_router.get("/snapshot")
async def bio_risk_snapshot(
    week_offset: int = Query(0, ge=0, le=7, description="0 = current week, 1-7 = weeks ago"),
):
    """Aggregated bio-risk snapshot for a given week.

    Used by the Bio Risk Map time slider. For week_offset=0, returns live data
    from engines. For 1-7, queries historical DB records for that ISO week.
    """
    now = dt.datetime.now(dt.UTC)
    target_date = now - dt.timedelta(weeks=week_offset)
    iso = target_date.isocalendar()
    target_year, target_week = iso[0], iso[1]
    week_label = f"W{target_week} {target_year}"

    if week_offset == 0:
        # ── Live data from engines ──────────────────────────────────
        return await _snapshot_live(week_label)
    else:
        # ── Historical data from DB ─────────────────────────────────
        return await _snapshot_historical(target_year, target_week, week_label, week_offset)


async def _snapshot_live(week_label: str) -> dict:
    """Build snapshot from live engine calls (current week)."""

    # Lice summary (inline query — same as lice_routes but lighter)
    lice_data = {"avg": 0, "high_count": 0, "total_farms": 0}
    async with get_async_session() as s:
        latest = (await s.execute(
            select(LiceRecord.year, LiceRecord.week)
            .order_by(LiceRecord.year.desc(), LiceRecord.week.desc())
            .limit(1)
        )).first()
        if latest:
            year, week = latest
            result = (await s.execute(
                select(
                    func.avg(LiceRecord.avg_adult_female_lice),
                    func.count(LiceRecord.id),
                ).where(
                    LiceRecord.year == year,
                    LiceRecord.week == week,
                    LiceRecord.avg_adult_female_lice.isnot(None),
                )
            )).one()
            lice_data["avg"] = round(float(result[0] or 0), 4)
            lice_data["total_farms"] = int(result[1] or 0)

            high = (await s.execute(
                select(func.count(LiceRecord.id)).where(
                    LiceRecord.year == year,
                    LiceRecord.week == week,
                    LiceRecord.avg_adult_female_lice > 0.5,
                )
            )).scalar() or 0
            lice_data["high_count"] = int(high)

    # Bloom risk summary
    bloom_data = {"risk_level": "LOW", "affected_areas": 0}
    async with get_async_session() as s:
        subq = (
            select(
                BloomRiskAssessment.locality_no,
                func.max(BloomRiskAssessment.assessed_at).label("latest"),
            )
            .group_by(BloomRiskAssessment.locality_no)
            .subquery()
        )
        assessments = (await s.execute(
            select(BloomRiskAssessment.risk_level)
            .join(subq, and_(
                BloomRiskAssessment.locality_no == subq.c.locality_no,
                BloomRiskAssessment.assessed_at == subq.c.latest,
            ))
        )).all()
        high_bloom = sum(1 for (rl,) in assessments if rl in ("HIGH", "CRITICAL"))
        bloom_data["affected_areas"] = high_bloom
        if high_bloom > 5:
            bloom_data["risk_level"] = "HIGH"
        elif high_bloom > 0:
            bloom_data["risk_level"] = "ELEVATED"

    # Disease count from Mattilsynet
    disease_data = {"outbreak_count": 0, "types": []}
    try:
        from core.market.mattilsynet_client import mattilsynet_client
        norway = mattilsynet_client.get_active_outbreaks()
        disease_data["outbreak_count"] = norway.get("active_cases", 0)
        by_disease = norway.get("by_disease", {})
        disease_data["types"] = list(by_disease.keys())[:5]
    except Exception:
        pass

    # Regime status
    regime_data = {"status": "normal", "pa_summary": {}}
    try:
        from core.market.regime_detector import regime_detector
        states = regime_detector.get_all_states()
        if isinstance(states, list):
            reds = sum(1 for s in states if s.get("current_color") == "red")
            yellows = sum(1 for s in states if s.get("current_color") == "yellow")
            regime_data["pa_summary"] = {"red": reds, "yellow": yellows, "green": len(states) - reds - yellows}
            regime_data["status"] = "alert" if reds > 0 else ("watch" if yellows > 3 else "normal")
    except Exception:
        pass

    return {
        "week_label": week_label,
        "week_offset": 0,
        "is_live": True,
        "lice": lice_data,
        "bloom": bloom_data,
        "disease": disease_data,
        "regime": regime_data,
        "data_provenance": DataProvenance.live(
            "BarentsWatch + CMEMS + Mattilsynet + Regime", confidence=0.90
        ).to_dict(),
    }


async def _snapshot_historical(target_year: int, target_week: int, week_label: str, week_offset: int) -> dict:
    """Build snapshot from historical DB records for a past week."""
    # ── Lice for that ISO week ──────────────────────────────────────
    lice_data = {"avg": 0, "high_count": 0, "total_farms": 0}
    async with get_async_session() as s:
        result = (await s.execute(
            select(
                func.avg(LiceRecord.avg_adult_female_lice),
                func.count(LiceRecord.id),
            ).where(
                LiceRecord.year == target_year,
                LiceRecord.week == target_week,
                LiceRecord.avg_adult_female_lice.isnot(None),
            )
        )).one()
        lice_data["avg"] = round(float(result[0] or 0), 4)
        lice_data["total_farms"] = int(result[1] or 0)

        high = (await s.execute(
            select(func.count(LiceRecord.id)).where(
                LiceRecord.year == target_year,
                LiceRecord.week == target_week,
                LiceRecord.avg_adult_female_lice > 0.5,
            )
        )).scalar() or 0
        lice_data["high_count"] = int(high)

    # ── Bloom assessments for that week's date range ────────────────
    bloom_data = {"risk_level": "LOW", "affected_areas": 0}
    week_start = dt.datetime.fromisocalendar(target_year, target_week, 1).replace(tzinfo=dt.UTC)
    week_end = week_start + dt.timedelta(days=7)

    async with get_async_session() as s:
        assessments = (await s.execute(
            select(BloomRiskAssessment.risk_level)
            .where(
                BloomRiskAssessment.assessed_at >= week_start,
                BloomRiskAssessment.assessed_at < week_end,
            )
        )).all()
        if assessments:
            high_bloom = sum(1 for (rl,) in assessments if rl in ("HIGH", "CRITICAL"))
            bloom_data["affected_areas"] = high_bloom
            if high_bloom > 5:
                bloom_data["risk_level"] = "HIGH"
            elif high_bloom > 0:
                bloom_data["risk_level"] = "ELEVATED"

    # ── Disease: use Mattilsynet cache filtered by date ─────────────
    disease_data = {"outbreak_count": 0, "types": []}
    try:
        from core.market.mattilsynet_client import mattilsynet_client
        norway = mattilsynet_client.get_active_outbreaks()
        # Filter active outbreaks to those that were active during target week
        active = norway.get("active_outbreaks", [])
        week_end_str = week_end.strftime("%Y-%m-%d")
        filtered = [
            o for o in active
            if o.get("diagnosis_date", "9999") <= week_end_str
        ]
        disease_data["outbreak_count"] = len(filtered)
        types_set: set[str] = set()
        for o in filtered:
            d = o.get("disease", "")
            if d:
                types_set.add(d.split("(")[0].strip())
        disease_data["types"] = list(types_set)[:5]
    except Exception:
        pass

    # ── Regime: use current (regime state changes are slow) ─────────
    regime_data = {"status": "normal", "pa_summary": {}}
    try:
        from core.market.regime_detector import regime_detector
        states = regime_detector.get_all_states()
        if isinstance(states, list):
            reds = sum(1 for s in states if s.get("current_color") == "red")
            yellows = sum(1 for s in states if s.get("current_color") == "yellow")
            regime_data["pa_summary"] = {"red": reds, "yellow": yellows, "green": len(states) - reds - yellows}
            regime_data["status"] = "alert" if reds > 0 else ("watch" if yellows > 3 else "normal")
    except Exception:
        pass

    # Provenance: historical data has lower confidence
    confidence = max(0.5, 0.90 - week_offset * 0.05)

    return {
        "week_label": week_label,
        "week_offset": week_offset,
        "is_live": False,
        "lice": lice_data,
        "bloom": bloom_data,
        "disease": disease_data,
        "regime": regime_data,
        "data_provenance": DataProvenance.degraded(
            "BarentsWatch + CMEMS + Mattilsynet + Regime",
            f"Historical snapshot ({week_label})",
            confidence=confidence,
        ).to_dict(),
    }
