"""Locality search routes — lets farmers find farms by name instead of number."""
from fastapi import APIRouter, Query
from sqlalchemy import select

router = APIRouter(tags=["localities"])


@router.get("/api/localities/search")
async def search_localities(q: str = Query("", description="Search term for farm name")):
    """Search localities by name (or return top 50 alphabetically if empty)."""
    from core.async_db import get_async_session
    from core.models import Locality

    async with get_async_session() as s:
        stmt = select(Locality.locality_no, Locality.name)
        if q.strip():
            stmt = stmt.where(Locality.name.ilike(f"%{q.strip()}%")).limit(20)
        else:
            stmt = stmt.order_by(Locality.name).limit(50)
        results = (await s.execute(stmt)).fetchall()

    return [
        {"locality_no": r[0], "name": r[1] or f"Locality {r[0]}"}
        for r in results
    ]
