"""Named public indices + the Bio→Price Weekly digest.

The published surface for AI-STI / AI-LPI: latest values, versioned history,
the methodology document and the weekly digest. Every value carries its method
version, component contributions and provenance — see docs/INDICES.md.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from core.auth import TokenPayload, require_admin

router = APIRouter(prefix="/api/indices", tags=["indices"])


@router.get("")
async def list_indices():
    """Latest value of every published index (compute-on-read)."""
    from core.market import indices

    out = {}
    for code in (indices.AI_STI, indices.AI_LPI):
        out[code] = await indices.compute(code)
    return {
        "method_version": indices.INDEX_METHOD_VERSION,
        "indices": out,
        "methodology_url": "/api/indices/methodology",
        "disclaimer": "Index output, not investment advice.",
    }


@router.get("/methodology")
async def index_methodology():
    """The published, versioned method behind every index value."""
    from core.market import indices

    return indices.methodology()


@router.get("/bio-price-weekly")
async def bio_price_weekly():
    """The flagship weekly digest: supply + lice pressure → price read."""
    from core.market.bio_price_weekly import build

    return await build()


@router.get("/{index_code}/history")
async def index_history(index_code: str, limit: int = 52):
    """Stored, versioned history for one index (empty until first publish)."""
    from core.market import indices

    code = index_code.strip().upper()
    if code not in indices.COMPUTERS:
        raise HTTPException(404, f"Unknown index '{index_code}'")
    return {
        "index": code,
        "version": indices.INDEX_METHOD_VERSION,
        "observations": await indices.history(code, limit=max(1, min(limit, 520))),
    }


@router.post("/publish")
async def publish_indices(_: TokenPayload = Depends(require_admin)):
    """Compute + store both indices (admin; the weekly job calls this)."""
    from core.market.bio_price_weekly import publish_week

    digest = await publish_week()
    return {
        "week": digest["week"],
        "storage": {
            code: data.get("storage") for code, data in digest["indices"].items()
        },
        "read": digest["transmission"]["read"],
    }


@router.get("/{index_code}")
async def get_index(index_code: str):
    """Latest value of one index (stable, public permalink)."""
    from core.market import indices

    code = index_code.strip().upper()
    if code not in indices.COMPUTERS:
        raise HTTPException(404, f"Unknown index '{index_code}'")
    return await indices.compute(code)