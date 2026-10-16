"""Subscription & Tier Management — PROJECTION over core.entitlements.

This module used to hold its own 5-tier table with **monthly**
``api_calls_limit`` values that were never enforced, while ``core/auth.py`` held
a different 4-tier table with the per-**day** figures that were enforced. The
``/api/tiers`` endpoint served both, so the API contradicted itself and
``intelligence`` (present here only) silently fell back to the free quota.

The table below is now a compatibility view over ``core/entitlements.PLANS``
(the single source of truth) and every helper delegates there.

Canonical plans (core/entitlements.py): Insight (free), Operator, Desk
(professional), Enterprise, Investor, Intelligence, plus the licensed
Data & Assurance tier.
"""
from __future__ import annotations

from dataclasses import dataclass

from core.entitlements import PLANS as _PLANS
from core.entitlements import catalog_tiers as _catalog_tiers
from core.entitlements import daily_quota as _daily_quota
from core.entitlements import feature_allowed as _feature_allowed
from core.entitlements import get_plan as _get_plan
from core.entitlements import normalize_plan as _normalize_plan


@dataclass
class TierConfig:
    name: str
    monthly_price_nok: float
    api_calls_limit: int
    features: list[str]
    roles: list[str]  # which user roles can subscribe


# Single source of truth: core/entitlements.PLANS. Compatibility view only —
# `api_calls_limit` is DERIVED there (per-day quota x 30) so the enforced and
# displayed figures cannot diverge again.
TIERS: dict[str, TierConfig] = {
    key: TierConfig(
        name=cfg["name"],
        monthly_price_nok=cfg["monthly_price_nok"],
        api_calls_limit=cfg["api_calls_limit"],
        features=cfg["features"],
        roles=cfg["roles"],
    )
    for key, cfg in _catalog_tiers().items()
}


def check_feature_access(tier: str, feature: str) -> bool:
    """Does the plan (or any plan below it) include `feature`? (delegates)"""
    return _feature_allowed(tier, feature)


def check_api_limit(tier: str, current_calls: int) -> bool:
    """Is `current_calls` (this month) within the plan's allowance?

    The monthly limit is DERIVED from the enforced per-day quota, so the
    displayed and enforced figures cannot disagree (the old drift source).
    """
    limit = _get_plan(tier).api_calls_per_month
    if limit <= 0:
        return True  # unlimited
    return current_calls < limit


def get_tier_for_role(role: str) -> list[str]:
    """Available plan keys for a user role."""
    return [key for key, plan in _PLANS.items() if role in plan.roles]


def canonical_plan(tier: str | None) -> str:
    """Normalise any tier string (including legacy aliases) to a plan key."""
    return _normalize_plan(tier)


def enforced_daily_quota(tier: str | None) -> int:
    """The per-day figure the quota middleware actually enforces."""
    return _daily_quota(tier)
