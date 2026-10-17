"""
Signal, order, audit, disclaimer, and sentiment routes.
Extracted from core/api.py (Session 10 — Router Wave 4).
"""
from __future__ import annotations


from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select

from core.auth import require_admin
from core.async_db import get_async_session
from core.legal.equity_signals import notice as equity_signals_withdrawn
from core.models import Order

router = APIRouter(tags=["signals"])


class SignalConfirmRequest(BaseModel):
    signal_id: int


# WS-20: equity direction signals are withdrawn (core/legal/equity_signals.py).
# The routes keep their frozen signatures (query parameters and request body, so the
# OpenAPI contract and the limit bound stand) but serve no signal: the table keeps
# its rows, nothing reads them here.


@router.get("/api/signals")
async def list_signals(
    status: str | None = None,
    limit: int = Query(50, ge=1, le=1000),
):
    return equity_signals_withdrawn()


@router.post("/api/signals/confirm")
async def confirm_signal(req: SignalConfirmRequest):
    # Confirming was the consent step the execution agent turned into a (paper)
    # order — a withdrawn signal can be neither confirmed nor rejected.
    raise HTTPException(410, equity_signals_withdrawn())


@router.post("/api/signals/reject")
async def reject_signal(req: SignalConfirmRequest):
    raise HTTPException(410, equity_signals_withdrawn())


@router.get("/api/orders")
async def list_orders(limit: int = Query(50, ge=1, le=1000)):
    async with get_async_session() as s:
        orders = (await s.execute(
            select(Order).order_by(Order.created_at.desc()).limit(limit)
        )).scalars().all()

    return [
        {
            "id": o.id,
            "ticker": o.ticker,
            "side": o.side,
            "quantity": o.quantity,
            "price": o.price,
            "status": o.status,
            "broker": o.broker,
            "user_consent": o.user_consent,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        }
        for o in orders
    ]


@router.get("/api/audit")
async def audit_log(
    limit: int = Query(100, ge=1, le=1000),
    _admin=Depends(require_admin),
):
    """Export the compliance audit trail (admin only).

    The trail carries user-scoped metadata (who did what, webhook/API-key
    names), so it is operational data under AGENTS.md rule 2 — it was
    unauthenticated until the liveness audit surfaced it returning 500s.
    """
    from compliance.compliance_agent import ComplianceAgent
    return await ComplianceAgent.export_audit_log(limit=limit)


@router.get("/api/disclaimer")
async def disclaimer():
    from compliance.compliance_agent import ComplianceAgent
    return {"disclaimer": ComplianceAgent.get_disclaimer()}


# ── Sentiment Engine ─────────────────────────────────────────────────

@router.get("/api/sentiment/signals")
async def sentiment_signals():
    """Get per-ticker sentiment signals from news analysis."""
    from core.market.sentiment_engine import sentiment_engine
    await sentiment_engine.poll_feeds()
    return sentiment_engine.get_signals()


@router.get("/api/sentiment/articles")
async def sentiment_articles(hours: int = 24, ticker: str = None):
    """Get recent analyzed news articles."""
    from core.market.sentiment_engine import sentiment_engine
    return sentiment_engine.get_recent_articles(hours, ticker)


@router.get("/api/sentiment/summary")
async def sentiment_summary():
    """Get overall market sentiment summary."""
    from core.market.data_provenance import DataProvenance
    from core.market.sentiment_engine import sentiment_engine
    summary = sentiment_engine.get_sentiment_summary()
    if isinstance(summary, dict):
        n_articles = int(summary.get("articles_24h") or 0)
        summary.setdefault(
            "data_provenance",
            (
                DataProvenance.live(f"News feeds ({n_articles} articles in 24h)", confidence=0.7)
                if n_articles > 0
                else DataProvenance.degraded(
                    "News feeds",
                    "no articles analysed in the last 24h — sentiment buckets are empty",
                    confidence=0.1,
                )
            ).to_dict(),
        )
    return summary


@router.get("/api/sentiment/poll")
async def sentiment_poll():
    """Trigger a manual sentiment poll and return new articles."""
    from core.market.data_provenance import DataProvenance
    from core.market.sentiment_engine import sentiment_engine
    articles = await sentiment_engine.poll_feeds()
    n_new = len(articles)
    return {
        "new_articles": n_new,
        "titles": [a.title for a in articles[:10]],
        "data_provenance": (
            DataProvenance.live(f"News feeds ({n_new} new articles)", confidence=0.7)
            if n_new
            else DataProvenance.degraded(
                "News feeds", "poll returned no new articles", confidence=0.2
            )
        ).to_dict(),
    }
