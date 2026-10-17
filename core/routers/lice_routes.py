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
from core.cache import cached
from core.source_lineage import lineage_for, provenance_for, summarise_rows

router = APIRouter(prefix="/api/lice", tags=["lice"])


@router.get("/summary", response_model=LiceSummaryResponse)
@cached(ttl=300, key_prefix="lice_summary")
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
            empty_lineage = summarise_rows([])
            return {"year": None, "week": None, "avg_adult_female_lice": 0,
                    "max_adult_female_lice": 0, "std_adult_female_lice": 0,
                    "sites_above_threshold": 0, "count_above_05": 0, "records": 0,
                    "lineage": empty_lineage,
                    "data_provenance": provenance_for(
                        empty_lineage, "BarentsWatch Fishhealth API", 0.95
                    )}

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

        # WS-14: the lineage of exactly the rows aggregated above.
        lineage = await lineage_for(
            s,
            LiceRecord.year == year,
            LiceRecord.week == week,
            LiceRecord.avg_adult_female_lice.isnot(None),
            year=year,
        )

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
        "lineage": lineage,
        # One provenance rule (WS-14): live only when every row used is verified,
        # fresh and complete; staleness is reported once, by the lineage note.
        "data_provenance": provenance_for(lineage, "BarentsWatch Fishhealth API", 0.95),
    }
