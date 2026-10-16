"""
Billing & Subscription Routes (Stripe)
=========================================
Extracted from core/api.py for maintainability.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/billing", tags=["billing"])


@router.get("/catalog")
async def billing_catalog():
    """Public pricing model: canonical plans + Stripe prices (or mock ids).

    Drives the pricing page. `mock: true` means Stripe is not configured and the
    ids are placeholders — never present those as live prices.
    """
    from core.billing import stripe_catalog
    from core.entitlements import PLANS

    return {
        "configured": stripe_catalog.is_configured(),
        "currency": "nok",
        "interval": "month",
        "plans": stripe_catalog.catalog(),
        "licensed_tier": {
            "plan": "data",
            "name": PLANS["data"].name,
            "audience": PLANS["data"].audience,
            "note": "Licensed per contract (EUR 25k-150k/yr) — contact sales.",
        },
    }


@router.post("/create-checkout-session")
async def billing_create_checkout(
    request: Request,
    tier: str | None = None,
    plan: str | None = None,
):
    """Create a Checkout Session for a plan upgrade.

    Accepts `?plan=<key>` (canonical) or the legacy `?tier=<key>`; the plan is
    validated against core.entitlements, not against the client's string.
    """
    from core.auth import get_current_user, security
    from core.billing.stripe_billing import stripe_billing

    requested = plan or tier
    if not requested:
        raise HTTPException(422, "Provide ?plan=<key> (see /api/billing/catalog)")

    creds = await security(request)
    user = await get_current_user(request, creds)
    if not user:
        raise HTTPException(401, "Authentication required")

    result = await stripe_billing.create_checkout_session(
        user.user_id, user.email, requested
    )
    if result.get("error"):
        raise HTTPException(400, result["error"])
    return result


@router.post("/webhook")
async def billing_webhook(request: Request):
    """Stripe webhook handler — NO auth required (Stripe calls directly)."""
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    from core.billing.stripe_billing import stripe_billing
    return await stripe_billing.handle_webhook(payload, sig)


@router.post("/webhook/mock")
async def billing_webhook_mock(request: Request):
    """Simulate a billing event so the money path is testable without Stripe.

    Dev/CI only: refused when FISHINTEL_ENV=production. When
    FISHINTEL_MOCK_BILLING_TOKEN is set, the caller must present it in the
    `X-Mock-Billing-Token` header (so a publicly reachable staging box cannot be
    told to upgrade arbitrary accounts).

    Body: {"event": "checkout.session.completed" | "customer.subscription.deleted",
           "user_id": 1, "plan": "professional"}
    """
    from config.settings import settings
    from core.billing.entitlement_sync import activate, revoke
    from core.entitlements import PLANS

    if settings.fishintel_env == "production":
        raise HTTPException(403, "Mock billing is disabled in production")

    expected = os.environ.get("FISHINTEL_MOCK_BILLING_TOKEN", "")
    if expected and request.headers.get("X-Mock-Billing-Token") != expected:
        raise HTTPException(403, "Invalid mock billing token")

    body = await request.json()
    event = body.get("event", "checkout.session.completed")
    user_id = body.get("user_id")
    if not isinstance(user_id, int):
        raise HTTPException(422, "user_id (int) is required")

    if event == "customer.subscription.deleted":
        return revoke(user_id, reason="mock_subscription_deleted")

    plan_key = str(body.get("plan", "professional"))
    if plan_key not in PLANS:
        raise HTTPException(422, f"Unknown plan '{plan_key}'")
    return activate(
        user_id,
        plan_key,
        price_id=f"price_mock_{plan_key}",
        subscription_id=body.get("subscription_id", "sub_mock"),
        customer_id=body.get("customer_id", "cus_mock"),
    )


@router.get("/subscription-status")
async def billing_subscription_status(request: Request):
    """Get current subscription status."""
    from core.auth import get_current_user, security
    creds = await security(request)
    user = await get_current_user(request, creds)
    if not user:
        raise HTTPException(401, "Authentication required")
    from core.billing.stripe_billing import stripe_billing
    return await stripe_billing.get_subscription_status(user.user_id)


@router.post("/cancel-subscription")
async def billing_cancel(request: Request):
    """Cancel subscription at end of current period."""
    from core.auth import get_current_user, security
    creds = await security(request)
    user = await get_current_user(request, creds)
    if not user:
        raise HTTPException(401, "Authentication required")
    from core.billing.stripe_billing import stripe_billing
    return await stripe_billing.cancel_subscription(user.user_id)


@router.get("/invoice-history")
async def billing_invoices(request: Request):
    """Get invoice history from Stripe."""
    from core.auth import get_current_user, security
    creds = await security(request)
    user = await get_current_user(request, creds)
    if not user:
        raise HTTPException(401, "Authentication required")
    from core.billing.stripe_billing import stripe_billing
    return await stripe_billing.get_invoice_history(user.user_id)
