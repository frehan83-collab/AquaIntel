"""Per-user chat usage: the meter behind the allowance.

A grounded question costs roughly USD 0.02 at the current model and prompt size, so the
allowance is not a revenue line — it is a fair-use meter that stops one power user
consuming the platform's model budget, and gives the sales conversation a number
("your plan includes 100 grounded questions a month") that is easy to say and easy to
enforce.

Design rules:

* **One row per (user, month).** Unique constraint, upsert on write; a month boundary
  starts a new row, so no reset job exists to fail.
* **Cost is recorded, not guessed.** Each answer carries the provider's token counts and
  the client's computed `cost_usd`; the meter sums what was actually spent.
* **Never block on the meter.** If the table is missing or the write fails, the answer is
  still served and the failure is logged — an unavailable meter must not take the product
  down, and the route's allowance check treats an unreadable meter as "unknown", which is
  reported rather than silently allowed.
"""
from __future__ import annotations

import datetime as dt

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from core.async_db import get_async_session

log = structlog.get_logger(__name__)


def month_key(now: dt.datetime | None = None) -> str:
    moment = now or dt.datetime.now(dt.UTC)
    return moment.strftime("%Y-%m")


def allowance_for(plan_key: str | None) -> int:
    """Questions per month for a plan; -1 means unlimited, 0 means not included."""
    from core.entitlements import get_plan

    try:
        return int(get_plan(plan_key).chat_questions_per_month)
    except Exception:  # noqa: BLE001 — an unknown plan never unlocks the paid feature
        return 0


def _next_month_start(now: dt.datetime | None = None) -> str:
    """The first day of next month — when the allowance resets."""
    moment = now or dt.datetime.now(dt.UTC)
    year = moment.year + (1 if moment.month == 12 else 0)
    month = 1 if moment.month == 12 else moment.month + 1
    return f"{year:04d}-{month:02d}-01"


async def used_this_month(user_key: str, *, now: dt.datetime | None = None) -> dict | None:
    """The meter for this user and month, or None when the table is unavailable."""
    from core.models import ChatUsage

    key = month_key(now)
    try:
        async with get_async_session() as session:
            row = (
                await session.execute(
                    select(ChatUsage).where(
                        ChatUsage.user_key == user_key, ChatUsage.month == key
                    )
                )
            ).scalar_one_or_none()
    except Exception as exc:  # noqa: BLE001 — reported as "unknown", never a crash
        log.warning("chat_usage.read_failed", error=str(exc)[:120])
        return None
    if row is None:
        return {
            "month": key,
            "questions": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
        }
    return {
        "month": key,
        "questions": int(row.questions or 0),
        "input_tokens": int(row.input_tokens or 0),
        "output_tokens": int(row.output_tokens or 0),
        "cost_usd": round(float(row.cost_usd or 0.0), 6),
    }


async def record(user_key: str, usage: dict | None, *, now: dt.datetime | None = None) -> None:
    """Add one answer's tokens and cost to the meter. Never raises."""
    from core.models import ChatUsage

    usage = usage or {}
    key = month_key(now)
    try:
        async with get_async_session() as session:
            row = (
                await session.execute(
                    select(ChatUsage).where(
                        ChatUsage.user_key == user_key, ChatUsage.month == key
                    )
                )
            ).scalar_one_or_none()
            if row is None:
                row = ChatUsage(user_key=user_key, month=key)
                session.add(row)
            row.questions = int(row.questions or 0) + 1
            row.input_tokens = int(row.input_tokens or 0) + int(usage.get("input_tokens") or 0)
            row.output_tokens = int(row.output_tokens or 0) + int(usage.get("output_tokens") or 0)
            row.cost_usd = round(
                float(row.cost_usd or 0.0) + float(usage.get("cost_usd") or 0.0), 6
            )
            row.updated_at = dt.datetime.now(dt.UTC)
            await session.commit()
    except IntegrityError:
        # Two requests raced the first insert of the month; the winner's row stands and
        # the loser's tokens are lost rather than corrupting the count.
        log.info("chat_usage.race_lost", user_key=user_key, month=key)
    except Exception as exc:  # noqa: BLE001 — the meter must not fail a paid answer
        log.warning("chat_usage.write_failed", error=str(exc)[:160])


async def status(
    user_key: str, plan_key: str | None, *, now: dt.datetime | None = None
) -> dict:
    """What the UI shows: allowance, used, remaining, and the honest unknowns."""
    meter = await used_this_month(user_key, now=now)
    allowance = allowance_for(plan_key)
    used = meter["questions"] if meter else None
    remaining = None
    if allowance < 0:
        remaining = -1
    elif used is not None:
        remaining = max(0, allowance - used)
    return {
        "plan": plan_key or "anonymous",
        "month": month_key(now),
        "allowance": allowance,
        "unlimited": allowance < 0,
        "included": allowance != 0,
        "used": used,
        "remaining": remaining,
        "meter_available": meter is not None,
        "input_tokens": meter["input_tokens"] if meter else None,
        "output_tokens": meter["output_tokens"] if meter else None,
        "cost_usd": meter["cost_usd"] if meter else None,
        "resets_on": _next_month_start(now),
    }


def exhausted(status_payload: dict) -> bool:
    """True when a plan with a finite allowance has used it up."""
    if status_payload.get("unlimited"):
        return False
    allowance = status_payload.get("allowance")
    used = status_payload.get("used")
    if allowance is None or allowance <= 0:
        return False
    return used is not None and used >= allowance


def not_included(status_payload: dict) -> bool:
    return status_payload.get("allowance") == 0
