"""
Lice data routes — BarentsWatch lice summary with provenance.
Extracted from core/api.py (Session 8).
"""
from __future__ import annotations

import math

from fastapi import APIRouter
from sqlalchemy import select, func

from core.async_db import get_async_session
from core.models import LiceRecord
from core.schemas import LiceSummaryResponse

router = APIRouter(prefix="/api/lice", tags=["lice"])


@router.get("/summary", response_model=LiceSummaryResponse)
async def lice_summary():
    """Get latest aggregated lice summary with std dev, threshold counts, and PA breakdown."""
    async with get_async_session() as s:
        # Find the most recent week with data
        latest = (await s.execute(
            select(LiceRecord.year, LiceRecord.week)
            .order_by(LiceRecord.year.desc(), LiceRecord.week.desc())
            .limit(1)
        )).first()

        if not latest:
            return {"year": None, "week": None, "avg_adult_female_lice": 0,
                    "max_adult_female_lice": 0, "std_adult_female_lice": 0,
                    "sites_above_threshold": 0, "count_above_05": 0, "records": 0}

        year, week = latest

        # Main stats
        result = (await s.execute(
            select(
                func.avg(LiceRecord.avg_adult_female_lice),
                func.max(LiceRecord.avg_adult_female_lice),
                func.count(LiceRecord.id),
                func.min(LiceRecord.avg_adult_female_lice),
            ).where(
                LiceRecord.year == year,
                LiceRecord.week == week,
                LiceRecord.avg_adult_female_lice.isnot(None),
            )
        )).one()

        avg_lice = float(result[0] or 0)
        max_lice = float(result[1] or 0)
        n = int(result[2] or 0)
        min_lice = float(result[3] or 0)

        # Count sites above threshold
        above = (await s.execute(
            select(func.count(LiceRecord.id)).where(
                LiceRecord.year == year,
                LiceRecord.week == week,
                LiceRecord.avg_adult_female_lice > 0.5,
            )
        )).scalar() or 0

        # Std dev approximation using variance
        if n > 1:
            sq_sum = (await s.execute(
                select(func.sum(LiceRecord.avg_adult_female_lice * LiceRecord.avg_adult_female_lice))
                .where(
                    LiceRecord.year == year,
                    LiceRecord.week == week,
                    LiceRecord.avg_adult_female_lice.isnot(None),
                )
            )).scalar() or 0
            variance = max(0.0, float(sq_sum) / n - avg_lice ** 2)
            std_lice = math.sqrt(variance)
        else:
            std_lice = 0.0

    from core.market.data_provenance import DataProvenance
    import datetime as _dt
    # Assess freshness: BarentsWatch lice data is weekly
    _current_week = _dt.date.today().isocalendar()
    _weeks_stale = (_current_week.year - year) * 52 + (_current_week.week - week)
    if _weeks_stale <= 1:
        prov = DataProvenance.live("BarentsWatch Fishhealth API", confidence=0.95)
    elif _weeks_stale <= 3:
        prov = DataProvenance.degraded("BarentsWatch Fishhealth API", f"{_weeks_stale} weeks stale", confidence=0.7)
    else:
        prov = DataProvenance.degraded("BarentsWatch Fishhealth API", f"{_weeks_stale} weeks stale", confidence=0.4)

    return {
        "year": year,
        "week": week,
        "avg_adult_female_lice": round(avg_lice, 4),
        "max_adult_female_lice": round(max_lice, 4),
        "min_adult_female_lice": round(min_lice, 4),
        "std_adult_female_lice": round(std_lice, 4),
        "sites_above_threshold": int(above),
        "count_above_05": int(above),  # alias for backwards compat
        "threshold": 0.5,
        "records": n,
        "above_threshold_pct": round(above / max(n, 1) * 100, 1),
        "data_provenance": prov.to_dict(),
    }
