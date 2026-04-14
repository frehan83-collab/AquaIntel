"""
RAS (Recirculating Aquaculture Systems) routes: all /api/ras/* endpoints.
Extracted from misc_routes.py (Session 39 decomposition).
"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["ras"])


@router.get("/api/ras/companies")
async def ras_companies():
    from core.market.ras_tracker import ras_tracker
    return ras_tracker.get_companies()

@router.get("/api/ras/summary")
async def ras_summary():
    from core.market.ras_tracker import ras_tracker
    return ras_tracker.get_global_summary()

@router.get("/api/ras/timeline")
async def ras_timeline():
    from core.market.ras_tracker import ras_tracker
    return ras_tracker.get_timeline()
