"""Entitlement surfaces — the public face of the single source of truth.

Backs the pricing page, the upgrade payloads emitted by the paywall
(``core/tier_quota.py``) and customer-facing "what is my plan?" checks. All
answers come from ``core/entitlements.py``; nothing here restates a price or a
quota.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from core.auth import TokenPayload, get_current_user
from core.entitlements import (
    PLAN_HIERARCHY,
    PLANS,
    PREMIUM_PREFIXES,
    get_plan,
    plan_catalog,
    route_allowed,
)

router = APIRouter(prefix="/api/entitlements", tags=["entitlements"])


@router.get("/plans")
async def list_plans():
    """Public pricing model: canonical plans in hierarchy order + licensing tier."""
    return {
        "plans": plan_catalog(),
        "hierarchy": list(PLAN_HIERARCHY),
        "currency": "NOK",
        "premium_prefixes": list(PREMIUM_PREFIXES),
        "note": (
            "Data & Assurance is licensed per contract (EUR 25k-150k/yr). "
            "Anonymous browsing is never gated; the paywall applies to "
            "authenticated accounts on the premium outputs listed above."
        ),
    }


@router.get("/me")
async def my_entitlements(user: TokenPayload | None = Depends(get_current_user)):
    """The caller's plan: quota, features, premium access and upgrade path."""
    if user is None:
        plan = get_plan(None)
        return {
            "authenticated": False,
            "plan": plan.key,
            "plan_name": plan.name,
            "api_calls_per_day": plan.api_calls_per_day,
            "features": list(plan.features),
            "premium_outputs_included": plan.premium,
            "upgrade_to": plan.upgrade_to,
            "note": "Anonymous browsing is ungated; sign in for account quotas.",
        }

    plan = get_plan(user.tier)
    from core.tier_quota import current_usage

    return {
        "authenticated": True,
        "user_id": user.user_id,
        "tier": user.tier,
        "plan": plan.key,
        "plan_name": plan.name,
        "api_calls_per_day": plan.api_calls_per_day,
        "used_today": current_usage(user.user_id, plan.key),
        "features": list(plan.features),
        "premium_outputs_included": plan.premium,
        "upgrade_to": plan.upgrade_to,
        "plans_url": "/api/entitlements/plans",
    }


@router.get("/check")
async def check_access(path: str, user: TokenPayload | None = Depends(get_current_user)):
    """Whether ``path`` is allowed for the caller's plan (for UI affordances)."""
    tier = user.tier if user else None
    return {
        "path": path,
        "allowed": route_allowed(tier, path),
        "plan": get_plan(tier).key,
        "plans_count": len(PLANS),
    }
