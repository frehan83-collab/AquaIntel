"""WS-49: an answer receipt — what the model was given, and what it was allowed to say.

Two needs meet here. Legally, a customer who says "your assistant told me X" (or a regulator who
asks what the system did) can only be answered if the facts, their `as_of`, the mode and the
claim-check verdict were retained at the time — the stale-data gate is a defence only if you can
prove the age was shown. Commercially, "here is exactly what the model saw and what it was
allowed to say" is a differentiator at the Investor and Intelligence tiers.

Design:

* one row per answer that a customer saw a model answer for (`grounded`, `grounded_fallback`,
  `model`); refusals and unavailable answers are not receipts;
* the **question is hashed, not stored** — a receipt proves what the system did without becoming
  a transcript of a customer's strategy; the answer text is not stored either, only its mode,
  model, factual sources with dates, the verification verdict and the cost;
* retention is 24 months (`RETENTION_MONTHS`), written into `retained_until` at insert; the purge
  is an explicit callable (`purge_expired`), not a silent cron, so an erasure request is a single
  auditable action;
* an unreadable receipt table never blocks an answer: the failure is logged, the answer is
  served, and the payload simply carries no receipt id.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json

import structlog
from sqlalchemy import select

from core.async_db import get_async_session

log = structlog.get_logger(__name__)

#: Accountability window. Long enough to answer a complaint about a document a customer forwarded.
RETENTION_MONTHS = 24


def question_hash(question: str) -> str:
    return hashlib.sha256((question or "").strip().lower().encode("utf-8")).hexdigest()[:32]


def retained_until(now: dt.datetime | None = None) -> dt.datetime:
    moment = now or dt.datetime.now(dt.UTC)
    year = moment.year + (RETENTION_MONTHS // 12)
    return moment.replace(year=year)


async def record(user_key: str, answer: dict, *, kind: str = "chat") -> int | None:
    """Persist a receipt for a model-backed answer. Never raises."""
    from core.models import AnswerReceipt

    mode = str(answer.get("mode") or "")
    if mode in ("refusal", "unavailable", "withheld"):
        return None
    try:
        sources = answer.get("sources") or []
        verification = answer.get("verification") or {}
        usage = answer.get("usage") or {}
        async with get_async_session() as session:
            row = AnswerReceipt(
                user_key=user_key,
                kind=kind,
                question_hash=question_hash(answer.get("question") or ""),
                mode=mode,
                model=str(answer.get("model") or ""),
                model_is_free=bool(answer.get("model_is_free")),
                sources_json=json.dumps(sources, ensure_ascii=False)[:20000],
                verification_json=json.dumps(verification, ensure_ascii=False)[:8000],
                cost_usd=round(float(usage.get("cost_usd") or 0.0), 6),
                latency_ms=float(answer.get("latency_ms") or 0.0),
                retained_until=retained_until(),
            )
            session.add(row)
            await session.commit()
            return row.id
    except Exception as exc:  # noqa: BLE001 — a receipt must never block an answer
        log.warning("receipts.write_failed", error=str(exc)[:160])
        return None


async def list_for(user_key: str, *, limit: int = 50) -> list[dict]:
    from core.models import AnswerReceipt

    try:
        async with get_async_session() as session:
            rows = (
                await session.execute(
                    select(AnswerReceipt)
                    .where(AnswerReceipt.user_key == user_key)
                    .order_by(AnswerReceipt.id.desc())
                    .limit(limit)
                )
            ).scalars().all()
    except Exception as exc:  # noqa: BLE001
        log.warning("receipts.read_failed", error=str(exc)[:120])
        return []
    return [
        {
            "id": row.id,
            "kind": row.kind,
            "mode": row.mode,
            "model": row.model,
            "model_is_free": bool(row.model_is_free),
            "question_hash": row.question_hash,
            "sources": json.loads(row.sources_json or "[]"),
            "verification": json.loads(row.verification_json or "{}"),
            "cost_usd": row.cost_usd,
            "latency_ms": row.latency_ms,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "retained_until": row.retained_until.isoformat() if row.retained_until else None,
        }
        for row in rows
    ]


async def purge_expired(*, now: dt.datetime | None = None) -> int:
    """Delete receipts past their retention date. Returns how many were removed."""
    from core.models import AnswerReceipt

    moment = now or dt.datetime.now(dt.UTC)
    try:
        async with get_async_session() as session:
            rows = (
                await session.execute(
                    select(AnswerReceipt).where(AnswerReceipt.retained_until < moment)
                )
            ).scalars().all()
            for row in rows:
                await session.delete(row)
            await session.commit()
    except Exception as exc:  # noqa: BLE001
        log.warning("receipts.purge_failed", error=str(exc)[:120])
        return 0
    if rows:
        log.info("receipts.purged", count=len(rows))
    return len(rows)
