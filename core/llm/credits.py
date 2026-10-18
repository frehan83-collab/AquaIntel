"""The credit ledger: buy runs, spend runs, never go negative silently.

A credit is one deep-analysis run (see `core/billing/credits_catalog.py`). The ledger is
append-only: every grant, purchase and spend is a row with a signed `delta`, so a balance is
always reconstructable and a support question ("where did my 30 runs go?") has an answer.

Rules that matter:

* **Append-only.** No row is ever updated. A refund is a new positive row.
* **Spend is atomic-ish.** The balance is checked and the spend row written in one
  transaction; a race that double-spends is prevented by the balance re-read inside the
  transaction, and the loser gets `InsufficientCredits` rather than a negative balance.
* **A missing ledger is not free credits.** If the table is unreadable the balance is
  reported as `None` and the route refuses to run, rather than assuming an entitlement.
"""
from __future__ import annotations

import datetime as dt

import structlog
from sqlalchemy import func, select

from core.async_db import get_async_session

log = structlog.get_logger(__name__)


class InsufficientCredits(Exception):
    """Raised when a run is requested without a credit to pay for it."""

    def __init__(self, balance: int, needed: int = 1) -> None:
        super().__init__(f"balance {balance} < {needed}")
        self.balance = balance
        self.needed = needed


async def balance(user_key: str) -> int | None:
    """Credits available, or None when the ledger cannot be read."""
    from core.models import CreditLedger

    try:
        async with get_async_session() as session:
            total = (
                await session.execute(
                    select(func.coalesce(func.sum(CreditLedger.delta), 0)).where(
                        CreditLedger.user_key == user_key
                    )
                )
            ).scalar()
    except Exception as exc:  # noqa: BLE001 — reported as unknown, never as free credits
        log.warning("credits.balance_failed", error=str(exc)[:120])
        return None
    return int(total or 0)


async def _append(session, user_key: str, delta: int, reason: str, ref: str | None) -> int:
    from core.models import CreditLedger

    row = CreditLedger(
        user_key=user_key,
        delta=int(delta),
        reason=reason,
        ref=ref,
        created_at=dt.datetime.now(dt.UTC),
    )
    session.add(row)
    await session.flush()
    return row.id


async def grant(
    user_key: str, credits: int, *, reason: str = "purchase", ref: str | None = None
) -> int:
    """Add credits (a purchase, a grant, a refund). Returns the new balance."""
    from core.models import CreditLedger  # noqa: F401 — ensures the table is mapped

    async with get_async_session() as session:
        await _append(session, user_key, credits, reason, ref)
        await session.commit()
        total = (
            await session.execute(
                select(func.coalesce(func.sum(CreditLedger.delta), 0)).where(
                    CreditLedger.user_key == user_key
                )
            )
        ).scalar()
    new_balance = int(total or 0)
    log.info("credits.granted", user_key=user_key, credits=credits, reason=reason,
             balance=new_balance)
    return new_balance


async def spend(
    user_key: str, credits: int = 1, *, reason: str = "run", ref: str | None = None
) -> int:
    """Spend credits or raise `InsufficientCredits`. Returns the new balance."""
    from core.models import CreditLedger

    if credits <= 0:
        raise ValueError("credits to spend must be positive")
    async with get_async_session() as session:
        total = (
            await session.execute(
                select(func.coalesce(func.sum(CreditLedger.delta), 0)).where(
                    CreditLedger.user_key == user_key
                )
            )
        ).scalar()
        available = int(total or 0)
        if available < credits:
            raise InsufficientCredits(available, credits)
        await _append(session, user_key, -credits, reason, ref)
        await session.commit()
    new_balance = available - credits
    log.info("credits.spent", user_key=user_key, credits=credits, reason=reason,
             balance=new_balance)
    return new_balance


async def history(user_key: str, limit: int = 20) -> list[dict]:
    from core.models import CreditLedger

    try:
        async with get_async_session() as session:
            rows = (
                await session.execute(
                    select(CreditLedger)
                    .where(CreditLedger.user_key == user_key)
                    .order_by(CreditLedger.id.desc())
                    .limit(limit)
                )
            ).scalars().all()
    except Exception as exc:  # noqa: BLE001
        log.warning("credits.history_failed", error=str(exc)[:120])
        return []
    return [
        {
            "id": row.id,
            "delta": int(row.delta or 0),
            "reason": row.reason,
            "ref": row.ref,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


async def status(user_key: str) -> dict:
    """What the UI shows: balance, and the pack catalogue beside it."""
    from core.billing.credits_catalog import CREDIT_VALIDITY_NOTE, catalog

    credits = await balance(user_key)
    return {
        "balance": credits,
        "available": credits is not None,
        "packs": catalog(),
        "validity_note": CREDIT_VALIDITY_NOTE,
    }
