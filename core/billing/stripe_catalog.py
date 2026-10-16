"""Canonical Stripe catalog — derived from core.entitlements (ONE source).

Creates/updates the Stripe Products + Prices for the self-serve plans and maps a
``price_id`` back to a plan key, so a webhook can entitle a user without trusting
a client-supplied tier string.

When ``STRIPE_SECRET_KEY`` is unset the module serves a **deterministic mock
catalog**, making the whole money path — catalog → checkout → webhook →
entitlement → gated route — exercisable in dev and CI without credentials. Mock
entries carry ``"mock": true`` and ``price_mock_<plan>`` ids so they can never be
mistaken for live prices.

Env vars (see .env.example): STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET,
STRIPE_SUCCESS_URL, STRIPE_CANCEL_URL.
"""
from __future__ import annotations

import asyncio
from typing import Any

import structlog

from config.settings import settings
from core.entitlements import PLAN_HIERARCHY, PLANS

log = structlog.get_logger(__name__)

# The `data` plan is licensed per contract — never self-serve at checkout.
SELF_SERVE_PLANS: tuple[str, ...] = tuple(PLAN_HIERARCHY)

_CURRENCY = "nok"
# Canonical metadata key (new) + the legacy key still present on live Stripe
# objects created before the rename. Both are written; either is read.
PLAN_METADATA_KEY = "aquaintel_plan"
LEGACY_PLAN_METADATA_KEY = "openclaw_tier"
LEGACY_USER_METADATA_KEY = "openclaw_user_id"
USER_METADATA_KEY = "aquaintel_user_id"

_MOCK_PREFIX = "price_mock_"
_price_to_plan: dict[str, str] = {}   # populated by ensure_catalog (real mode)


def is_configured() -> bool:
    """True when a live Stripe key is present."""
    return bool(getattr(settings, "stripe_secret_key", ""))


def catalog() -> list[dict]:
    """Pricing-page model: canonical plans + Stripe ids (or mock ids)."""
    live = is_configured()
    out: list[dict] = []
    for key in SELF_SERVE_PLANS:
        plan = PLANS[key]
        out.append(
            {
                "plan": key,
                "name": plan.name,
                "audience": plan.audience,
                "amount_nok": plan.price_nok_month,
                "currency": _CURRENCY,
                "interval": "month",
                "api_calls_per_day": plan.api_calls_per_day,
                "seats": plan.seats,
                "sites": plan.sites,
                "features": list(plan.features),
                "upgrade_to": plan.upgrade_to,
                "premium_outputs_included": plan.premium,
                "price_id": None if live else f"{_MOCK_PREFIX}{key}",
                "product_id": None if live else f"prod_mock_{key}",
                "mock": not live,
            }
        )
    return out


def plan_from_price_id(price_id: str | None) -> str | None:
    """Reverse lookup price_id → plan key (mock ids resolve too)."""
    if not price_id:
        return None
    if price_id.startswith(_MOCK_PREFIX):
        key = price_id[len(_MOCK_PREFIX):]
        return key if key in PLANS else None
    return _price_to_plan.get(price_id)


def plan_from_metadata(metadata: dict | None) -> str | None:
    """Resolve a plan key from Stripe object metadata (new or legacy key)."""
    if not metadata:
        return None
    raw = metadata.get(PLAN_METADATA_KEY) or metadata.get(LEGACY_PLAN_METADATA_KEY)
    if not raw:
        return None
    from core.entitlements import normalize_plan

    return normalize_plan(raw)


def user_id_from_metadata(metadata: dict | None) -> int | None:
    """Resolve the owning user id from Stripe metadata (new or legacy key)."""
    if not metadata:
        return None
    raw = metadata.get(USER_METADATA_KEY) or metadata.get(LEGACY_USER_METADATA_KEY)
    try:
        return int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def mock_checkout_url(plan_key: str, user_id: int) -> str:
    """Deterministic stand-in checkout URL used when Stripe is unconfigured."""
    return f"/billing/mock-checkout?plan={plan_key}&user_id={user_id}"


def _metadata_for(plan_key: str) -> dict[str, str]:
    return {PLAN_METADATA_KEY: plan_key, LEGACY_PLAN_METADATA_KEY: plan_key}


async def ensure_catalog() -> dict[str, str]:
    """Create/find the Stripe Products + Prices; returns plan → price_id.

    Real mode only. Idempotent: products are found by metadata and prices by
    product + currency + amount, so repeated calls do not duplicate the catalog.
    """
    if not is_configured():
        return {key: f"{_MOCK_PREFIX}{key}" for key in SELF_SERVE_PLANS}
    return await asyncio.to_thread(_ensure_catalog_sync)


def _ensure_catalog_sync() -> dict[str, str]:
    import stripe

    stripe.api_key = settings.stripe_secret_key
    result: dict[str, str] = {}

    for key in SELF_SERVE_PLANS:
        plan = PLANS[key]
        products: Any = stripe.Product.search(
            query=f'metadata["{PLAN_METADATA_KEY}"]:"{key}"', limit=1
        )
        if products.data:
            product = products.data[0]
        else:
            product = stripe.Product.create(
                name=f"AquaIntel {plan.name}",
                description=plan.audience,
                metadata=_metadata_for(key),
            )
            log.info("stripe_product_created", plan=key, product_id=product.id)

        prices: Any = stripe.Price.list(product=product.id, active=True, limit=10)
        price = next(
            (
                p
                for p in prices.data
                if p.currency == _CURRENCY
                and p.unit_amount == int(plan.price_nok_month * 100)
            ),
            None,
        )
        if price is None:
            price = stripe.Price.create(
                product=product.id,
                unit_amount=int(plan.price_nok_month * 100),  # øre
                currency=_CURRENCY,
                recurring={"interval": "month"},
                metadata=_metadata_for(key),
            )
            log.info("stripe_price_created", plan=key, price_id=price.id)

        _price_to_plan[price.id] = key
        result[key] = price.id

    return result
