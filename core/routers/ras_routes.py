"""
RAS (Recirculating Aquaculture Systems) routes: all /api/ras/* endpoints.
Extracted from misc_routes.py (Session 39 decomposition).
"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["ras"])


# ── RAS ──────────────────────────────────────────────────────────────
@router.get("/api/ras/companies")
async def ras_companies():
    from core.market.ras_tracker import ras_tracker
    return ras_tracker.get_companies()


@router.get("/api/ras/summary")
async def ras_summary():
    from core.market.data_provenance import DataProvenance
    from core.market.ras_tracker import ras_tracker
    result = ras_tracker.get_global_summary()
    if isinstance(result, dict):
        result.setdefault("data_provenance", DataProvenance.degraded(
            "RAS land-based tracker (published project capacities)",
            reason=(
                "aggregated from published project/company announcements — "
                "indicative capacity, not audited production"
            ),
            confidence=0.4,
        ).to_dict())
    return result


@router.get("/api/ras/timeline")
async def ras_timeline():
    from core.market.data_provenance import DataProvenance
    from core.market.ras_tracker import ras_tracker
    result = ras_tracker.get_timeline()
    if isinstance(result, dict):
        result.setdefault("data_provenance", DataProvenance.degraded(
            "RAS land-based tracker (published project capacities)",
            reason=(
                "aggregated from published project/company announcements — "
                "indicative capacity, not audited production"
            ),
            confidence=0.4,
        ).to_dict())
    return result
