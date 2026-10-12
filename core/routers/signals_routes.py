"""
Signal, order, audit, disclaimer, and sentiment routes.
Extracted from core/api.py (Session 10 — Router Wave 4).
"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func

from core.async_db import get_async_session
from core.models import Signal, Order, AuditLog

router = APIRouter(tags=["signals"])


class SignalConfirmRequest(BaseModel):
    signal_id: int


@router.get("/api/signals")
async def list_signals(
    status: str | None = None,
    limit: int = Query(50, ge=1, le=1000),
):
    async with get_async_session() as s:
        q = select(Signal).order_by(Signal.created_at.desc()).limit(limit)
        if status:
            q = q.where(Signal.status == status)
        signals = (await s.execute(q)).scalars().all()

    return [
        {
            "id": sig.id,
            "ticker": sig.ticker,
            "direction": sig.direction,
            "strength": sig.strength,
            "status": sig.status,
            "rationale": sig.rationale,
            "created_at": sig.created_at.isoformat() if sig.created_at else None,
            "confirmed": sig.confirmed_by_user,
        }
        for sig in signals
    ]


@router.post("/api/signals/confirm")
async def confirm_signal(req: SignalConfirmRequest):
    from execution.execution_agent import ExecutionAgent
    success = await ExecutionAgent.confirm_signal(req.signal_id)
    if not success:
        raise HTTPException(400, "Signal not found or not in pending state")
    return {"status": "confirmed", "signal_id": req.signal_id}


@router.post("/api/signals/reject")
async def reject_signal(req: SignalConfirmRequest):
    from execution.execution_agent import ExecutionAgent
    success = await ExecutionAgent.reject_signal(req.signal_id)
    if not success:
        raise HTTPException(400, "Signal not found or not in pending state")
    return {"status": "rejected", "signal_id": req.signal_id}


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
async def audit_log(limit: int = Query(100, ge=1, le=1000)):
    from compliance.compliance_agent import ComplianceAgent
    logs = await ComplianceAgent.export_audit_log()
    return logs[:limit]


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
    from core.market.sentiment_engine import sentiment_engine
    return sentiment_engine.get_sentiment_summary()


@router.get("/api/sentiment/poll")
async def sentiment_poll():
    """Trigger a manual sentiment poll and return new articles."""
    from core.market.sentiment_engine import sentiment_engine
    articles = await sentiment_engine.poll_feeds()
    return {
        "new_articles": len(articles),
        "titles": [a.title for a in articles[:10]],
    }
