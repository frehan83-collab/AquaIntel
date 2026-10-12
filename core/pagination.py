"""
Standard pagination contract (arch report §4.4).

Model citizen: `admin_routes.py` audit-log (`limit`/`offset` Query bounds).
Two adoption levels:

1. **Bound existing params (additive, done in Session 40 wave 1)** — list
   endpoints keep their current response shape but clamp `limit` via
   `Query(default, ge=1, le=MAX_LIMIT)` so a caller can no longer request
   effectively-unbounded result sets.

2. **New endpoints use this helper** for the full contract:

       from core.pagination import PageParams, page_params, paginate

       @router.get("/things")
       async def things(pg: PageParams = Depends(page_params)):
           items = await load_all()
           return paginate(items, pg)

   Response envelope: ``{"items": [...], "total": n, "limit": l, "offset": o}``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Query

MAX_LIMIT = 1000
DEFAULT_LIMIT = 100


@dataclass
class PageParams:
    limit: int
    offset: int


def page_params(
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT, description="Max items per page"),
    offset: int = Query(0, ge=0, description="Item offset"),
) -> PageParams:
    """FastAPI dependency: ``pg: PageParams = Depends(page_params)``."""
    return PageParams(limit=limit, offset=offset)


def paginate(items: list[Any], params: PageParams, total: int | None = None) -> dict:
    """Slice items to the requested page; include the honest total."""
    return {
        "items": items[params.offset: params.offset + params.limit],
        "total": total if total is not None else len(items),
        "limit": params.limit,
        "offset": params.offset,
    }
