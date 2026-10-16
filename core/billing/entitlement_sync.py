"""Billing → entitlement synchronisation (ONE place).

Both the real Stripe webhook and the dev/mock checkout path call these helpers, so
the entitlement write cannot diverge between them. The plan key is resolved from
the **Stripe price id** where possible (authoritative — never a client-supplied
tier string) and only then from object metadata, then normalised through
``core.entitlements``.
"""
from __future__ import annotations

import datetime as dt

import structlog

from core.billing import stripe_catalog
from core.entitlements import PLANS, get_plan

log = structlog.get_logger(__name__)


def activate(
    user_id: int,
    plan_key: str,
    *,
    price_id: str | None = None,
    subscription_id: str | None = None,
    customer_id: str | None = None,
    current_period_end: dt.datetime | None = None,
) -> dict:
    """Grant ``plan_key`` to ``user_id``: update ``User.tier`` + ``Subscription``."""
    from sqlalchemy import select

    from core.models import Session as DBSession, Subscription, User

    plan = get_plan(plan_key)
    now = dt.datetime.now(dt.UTC)
    with DBSession() as s:
        user = s.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        if user is None:
            return {"error": "user_not_found", "user_id": user_id}
        user.tier = plan.key
        if customer_id:
            user.stripe_customer_id = customer_id

        sub = s.execute(
            select(Subscription).where(Subscription.user_id == user_id)
        ).scalar_one_or_none()
        if sub is None:
            sub = Subscription(user_id=user_id, tier=plan.key)
            s.add(sub)
        sub.tier = plan.key
        sub.is_active = True
        sub.cancel_at_period_end = False
        sub.monthly_price_nok = plan.price_nok_month
        sub.api_calls_limit = plan.api_calls_per_month
        sub.started_at = sub.started_at or now
        if subscription_id:
            sub.stripe_subscription_id = subscription_id
        if price_id:
            sub.stripe_price_id = price_id
        if customer_id:
            sub.stripe_customer_id = customer_id
        if current_period_end:
            sub.current_period_end = current_period_end
        s.commit()

    log.info("entitlement_activated", user_id=user_id, plan=plan.key)
    return {
        "status": "activated",
        "user_id": user_id,
        "plan": plan.key,
        "api_calls_per_day": plan.api_calls_per_day,
    }


def revoke(user_id: int, *, reason: str = "subscription_deleted") -> dict:
    """Return the user to the free plan and deactivate the subscription row."""
    from sqlalchemy import select

    from core.models import Session as DBSession, Subscription, User

    plan = PLANS["free"]
    with DBSession() as s:
        user = s.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        if user is None:
            return {"error": "user_not_found", "user_id": user_id}
        user.tier = plan.key
        sub = s.execute(
            select(Subscription).where(Subscription.user_id == user_id)
        ).scalar_one_or_none()
        if sub is not None:
            sub.tier = plan.key
            sub.is_active = False
            sub.monthly_price_nok = 0
            sub.api_calls_limit = plan.api_calls_per_month
        s.commit()

    log.info("entitlement_revoked", user_id=user_id, reason=reason)
    return {"status": "revoked", "user_id": user_id, "plan": plan.key}


def plan_for_event(data: dict) -> str | None:
    """Best-effort plan resolution for a Stripe event object.

    Order matters: price id first (server-side truth), metadata second (legacy
    objects created before the canonical metadata key existed).
    """
    items = data.get("items")
    if isinstance(items, dict):
        rows = items.get("data") or []
        if rows:
            resolved = stripe_catalog.plan_from_price_id(
                (rows[0].get("price") or {}).get("id")
            )
            if resolved:
                return resolved
    price = data.get("price")
    if isinstance(price, dict):
        resolved = stripe_catalog.plan_from_price_id(price.get("id"))
        if resolved:
            return resolved
    return stripe_catalog.plan_from_metadata(data.get("metadata"))


def user_id_for_event(data: dict) -> int | None:
    """Resolve the user a billing event belongs to (metadata, else the DB)."""
    uid = stripe_catalog.user_id_from_metadata(data.get("metadata"))
    if uid is not None:
        return uid

    from sqlalchemy import select

    from core.models import Session as DBSession, Subscription, User

    subscription_id = data.get("subscription") or data.get("id")
    customer_id = data.get("customer")
    with DBSession() as s:
        if subscription_id:
            sub = s.execute(
                select(Subscription).where(
                    Subscription.stripe_subscription_id == subscription_id
                )
            ).scalar_one_or_none()
            if sub is not None:
                return sub.user_id
        if customer_id:
            user = s.execute(
                select(User).where(User.stripe_customer_id == customer_id)
            ).scalar_one_or_none()
            if user is not None:
                return user.id
    return None