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
    from core.market import index_publication, indices

    out = {}
    for code in (indices.AI_STI, indices.AI_LPI):
        out[code] = await indices.compute(code)
    return {
        "method_version": indices.INDEX_METHOD_VERSION,
        "indices": out,
        # WS-2: whether the stored weekly series is current (the scheduler assertion)
        "publication": await index_publication.status(),
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
async def publish_indices(
    force: bool = False,
    reason: str | None = None,
    admin: TokenPayload = Depends(require_admin),
):
    """Compute + store this week's indices (admin).

    Obeys the same readiness gate as the ``index_publisher`` agent: an index with
    no value is never stored and, within the readiness grace, only a live value
    is. When nothing could be stored the answer is a 409 naming why; a partial
    store is a 200 whose ``storage`` names the withheld index. ``force=true``
    (with a ``reason``) overrides the grace only — never the null rule. The forced
    intent is written to the audit log BEFORE anything is stored (503 and no
    store if the audit log is unavailable), so a forced row can never exist
    without its audit trail; a store failure is a structured 500.
    """
    from core.async_db import get_async_session
    from core.market.bio_price_weekly import publish_week
    from core.market.index_publication import current_week_label
    from core.models import AuditLog
    from core.source_lineage import to_utc

    if force and not (reason or "").strip():
        raise HTTPException(422, "force=true requires a reason (it is audited)")
    now = to_utc(None)  # one instant for the audit row, the digest and the store
    week = current_week_label(now)
    if force:
        try:
            async with get_async_session() as session:
                session.add(
                    AuditLog(
                        event_type="index_publication_forced",
                        user_id=getattr(admin, "user_id", None),
                        detail=f"{week}: forced past the readiness grace (intent) — {reason}",
                    )
                )
        except Exception as exc:
            raise HTTPException(
                503,
                {
                    "error": "audit log unavailable",
                    "detail": str(exc)[:200],
                    "hint": "a forced publication is not performed without its audit row; nothing was stored",
                },
            ) from exc
    try:
        digest = await publish_week(as_of=now, force=force)
    except Exception as exc:
        raise HTTPException(
            500,
            {
                "error": "publication failed",
                "week": week,
                "detail": str(exc)[:200],
                "audited_intent": bool(force),
                "hint": "check GET /api/indices `publication` for what was stored",
            },
        ) from exc
    ready = digest["readiness"]
    storage = {code: data.get("storage") for code, data in digest["indices"].items()}
    withheld = {
        code: s.get("reason") for code, s in storage.items() if s and s.get("status") == "withheld"
    }
    stored = {code: s for code, s in storage.items() if s and s.get("status") != "withheld"}
    if withheld and not stored:
        raise HTTPException(
            409,
            {
                "error": "not ready",
                "week": digest["week"],
                "withheld": withheld,
                "stored": {},
                "hint": (
                    "force cannot store a value that was never computed; retry once the "
                    "inputs are available"
                    if force
                    else "an index with no value is never stored; a degraded value is stored "
                    "after the readiness grace, or now with force=true and a reason (audited)"
                ),
            },
        )
    return {
        "week": digest["week"],
        "storage": storage,
        "readiness": ready,
        "forced": digest.get("forced", False),
        "audited_intent": bool(force),
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