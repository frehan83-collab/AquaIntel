"""
Billing & Subscription Routes (Stripe)
=========================================
Extracted from core/api.py for maintainability.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/billing", tags=["billing"])


@router.post("/create-checkout-session")
async def billing_create_checkout(tier: str, request: Request):
    """Create a Stripe Checkout Session for subscription upgrade."""
    from core.auth import get_current_user, security
    creds = await security(request)
    user = await get_current_user(creds)
    if not user:
        raise HTTPException(401, "Authentication required")
    from core.billing.stripe_billing import stripe_billing
    return await stripe_billing.create_checkout_session(user.user_id, user.email, tier)


@router.post("/webhook")
async def billing_webhook(request: Request):
    """Stripe webhook handler — NO auth required (Stripe calls directly)."""
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    from core.billing.stripe_billing import stripe_billing
    return await stripe_billing.handle_webhook(payload, sig)


@router.get("/subscription-status")
async def billing_subscription_status(request: Request):
    """Get current subscription status."""
    from core.auth import get_current_user, security
    creds = await security(request)
    user = await get_current_user(creds)
    if not user:
        raise HTTPException(401, "Authentication required")
    from core.billing.stripe_billing import stripe_billing
    return await stripe_billing.get_subscription_status(user.user_id)


@router.post("/cancel-subscription")
async def billing_cancel(request: Request):
    """Cancel subscription at end of current period."""
    from core.auth import get_current_user, security
    creds = await security(request)
    user = await get_current_user(creds)
    if not user:
        raise HTTPException(401, "Authentication required")
    from core.billing.stripe_billing import stripe_billing
    return await stripe_billing.cancel_subscription(user.user_id)


@router.get("/invoice-history")
async def billing_invoices(request: Request):
    """Get invoice history from Stripe."""
    from core.auth import get_current_user, security
    creds = await security(request)
    user = await get_current_user(creds)
    if not user:
        raise HTTPException(401, "Authentication required")
    from core.billing.stripe_billing import stripe_billing
    return await stripe_billing.get_invoice_history(user.user_id)
