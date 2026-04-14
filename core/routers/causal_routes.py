"""
Causal analysis routes: all /api/causal/* endpoints.
Extracted from misc_routes.py (Session 39 decomposition).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select, func, case

from core.models import LiceRecord
from core.async_db import get_async_session

router = APIRouter(tags=["causal"])


@router.get("/api/causal/summary")
async def causal_summary(max_lag: int = 16):
    from core.market.causal_engine import causal_engine
    from core.market.ssb_price_client import ssb_price_client

    async with get_async_session() as s:
        rows = (await s.execute(
            select(
                LiceRecord.year, LiceRecord.week,
                func.avg(LiceRecord.avg_adult_female_lice),
                func.sum(case((LiceRecord.avg_adult_female_lice > 0.5, 1), else_=0)),
                func.count(LiceRecord.id),
            ).where(LiceRecord.avg_adult_female_lice.isnot(None))
            .group_by(LiceRecord.year, LiceRecord.week)
            .order_by(LiceRecord.year, LiceRecord.week)
        )).all()

    if not rows or len(rows) < 30:
        raise HTTPException(400, f"Insufficient lice data: {len(rows) if rows else 0} weeks (need >=30)")

    lice_series = [float(r[2] or 0) for r in rows]
    pct_above_series = [float((r[3] or 0) / max(r[4] or 1, 1)) for r in rows]

    try:
        ssb_data = await ssb_price_client.fetch_prices(n_weeks=len(rows) + 10)
        price_series = [float(p.price_nok_kg) for p in ssb_data.prices[-len(rows):]]
    except Exception:
        raise HTTPException(503, "SSB price data unavailable")

    n = min(len(lice_series), len(price_series), len(pct_above_series))
    causal_engine.load_data(lice_series=lice_series[-n:], price_series=price_series[-n:],
                            pct_above_series=pct_above_series[-n:])
    return causal_engine.get_causal_summary(max_lag=max_lag)

@router.get("/api/causal/granger")
async def causal_granger(max_lag: int = 16):
    from core.market.causal_engine import causal_engine
    if causal_engine._lice is None:
        raise HTTPException(400, "No data loaded. Call /api/causal/summary first.")
    results_dict = causal_engine.run_granger(max_lag=max_lag)
    results_list = [{"lag": lag, **vals} for lag, vals in sorted(results_dict.items())] if results_dict else []
    return {"results": results_list, "dominant_lag": causal_engine.find_dominant_lag(max_lag=max_lag)}
