"""
Stripe Billing Engine
=======================
Handles subscription lifecycle: checkout sessions, webhooks, cancellations.
Maps AquaIntel tiers to Stripe Products/Prices.

Requires env vars: STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET
"""
from __future__ import annotations

import asyncio
import datetime as dt
from typing import Any

import structlog

from config.settings import settings

log = structlog.get_logger(__name__)

# Tier → Stripe metadata mapping
TIER_PRODUCTS = {
    "professional": {
        "name": "AquaIntel Professional",
        "price_nok": 2990,
        "description": "Real-time alerts, farm forecasts, harvest optimizer, ML baselines",
    },
    "enterprise": {
        "name": "AquaIntel Enterprise",
        "price_nok": 14900,
        "description": "Full market intelligence, EU traceability, supply chain tools",
    },
    "investor": {
        "name": "AquaIntel Investor",
        "price_nok": 24900,
        "description": "All features + trading signals, performance tracking, full API",
    },
}


class StripeBillingEngine:
    """Singleton Stripe billing integration."""

    def __init__(self) -> None:
        self._stripe: Any = None
        self._price_cache: dict[str, str] = {}  # tier → stripe_price_id

    def _get_stripe(self) -> Any:
        """Lazy-init Stripe client."""
        if self._stripe is None:
            import stripe
            stripe.api_key = settings.stripe_secret_key
            self._stripe = stripe
        return self._stripe

    async def _ensure_price(self, tier: str) -> str:
        return await asyncio.to_thread(self._ensure_price_sync, tier)

    def _ensure_price_sync(self, tier: str) -> str:
        """Get or create Stripe Price for a tier (sync SDK calls)."""
        if tier in self._price_cache:
            return self._price_cache[tier]

        stripe = self._get_stripe()
        tier_info = TIER_PRODUCTS[tier]

        # Search for existing product by metadata
        products = stripe.Product.search(
            query=f'metadata["openclaw_tier"]:"{tier}"',
            limit=1,
        )

        if products.data:
            product = products.data[0]
        else:
            product = stripe.Product.create(
                name=tier_info["name"],
                description=tier_info["description"],
                metadata={"openclaw_tier": tier},
            )
            log.info("stripe_product_created", tier=tier, product_id=product.id)

        # Search for existing price
        prices = stripe.Price.list(product=product.id, active=True, limit=1)
        if prices.data:
            price = prices.data[0]
        else:
            price = stripe.Price.create(
                product=product.id,
                unit_amount=tier_info["price_nok"] * 100,  # øre
                currency="nok",
                recurring={"interval": "month"},
            )
            log.info("stripe_price_created", tier=tier, price_id=price.id)

        self._price_cache[tier] = price.id
        return price.id

    async def create_checkout_session(
        self, user_id: int, email: str, tier: str
    ) -> dict:
        """Create a Stripe Checkout Session for subscription upgrade.

        The sync Stripe SDK + sync DB Session run in a worker thread so the
        event loop is never blocked (arch report P1).
        """
        if tier not in TIER_PRODUCTS:
            return {"error": f"Invalid tier: {tier}"}

        if not settings.stripe_secret_key:
            return {"error": "Stripe not configured", "demo_mode": True}

        return await asyncio.to_thread(
            self._create_checkout_session_sync, user_id, email, tier
        )

    def _create_checkout_session_sync(
        self, user_id: int, email: str, tier: str
    ) -> dict:
        stripe = self._get_stripe()
        price_id = self._ensure_price_sync(tier)

        # Get or create Stripe customer
        from core.models import Session as DBSession, User
        from sqlalchemy import select

        with DBSession() as s:
            user = s.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
            if not user:
                return {"error": "User not found"}

            customer_id = user.stripe_customer_id
            if not customer_id:
                customer = stripe.Customer.create(
                    email=email,
                    metadata={"openclaw_user_id": str(user_id)},
                )
                user.stripe_customer_id = customer.id
                s.commit()
                customer_id = customer.id

        session = stripe.checkout.Session.create(
            customer=customer_id,
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=settings.stripe_success_url,
            cancel_url=settings.stripe_cancel_url,
            metadata={"openclaw_user_id": str(user_id), "openclaw_tier": tier},
        )

        log.info("checkout_session_created", user_id=user_id, tier=tier)
        return {"checkout_url": session.url, "session_id": session.id}

    async def handle_webhook(self, payload: bytes, sig_header: str) -> dict:
        """Process Stripe webhook events."""
        stripe = self._get_stripe()

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.stripe_webhook_secret,
            )
        except (ValueError, stripe.error.SignatureVerificationError) as e:
            log.warning("webhook_signature_invalid", error=str(e))
            return {"error": "Invalid signature"}

        event_type = event["type"]
        data = event["data"]["object"]

        if event_type == "checkout.session.completed":
            await asyncio.to_thread(self._handle_checkout_completed_sync, data)
        elif event_type == "customer.subscription.updated":
            await asyncio.to_thread(self._handle_subscription_updated_sync, data)
        elif event_type == "customer.subscription.deleted":
            await asyncio.to_thread(self._handle_subscription_deleted_sync, data)
        elif event_type == "invoice.payment_failed":
            self._handle_payment_failed(data)

        log.info("webhook_processed", event_type=event_type)
        return {"status": "ok"}

    def _handle_checkout_completed_sync(self, session_data: dict) -> None:
        """Activate subscription after successful checkout."""
        from core.models import Session as DBSession, User, Subscription
        from sqlalchemy import select

        user_id = int(session_data["metadata"].get("openclaw_user_id", 0))
        tier = session_data["metadata"].get("openclaw_tier", "professional")
        subscription_id = session_data.get("subscription")

        with DBSession() as s:
            user = s.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
            if not user:
                return

            user.tier = tier

            # Update or create subscription record
            sub = s.execute(
                select(Subscription).where(Subscription.user_id == user_id)
            ).scalar_one_or_none()

            tier_price = TIER_PRODUCTS.get(tier, {}).get("price_nok", 0)

            if sub:
                sub.tier = tier
                sub.stripe_subscription_id = subscription_id
                sub.is_active = True
                sub.monthly_price_nok = tier_price
                sub.started_at = dt.datetime.now(dt.UTC)
            else:
                sub = Subscription(
                    user_id=user_id,
                    tier=tier,
                    stripe_subscription_id=subscription_id,
                    is_active=True,
                    monthly_price_nok=tier_price,
                    started_at=dt.datetime.now(dt.UTC),
                    api_calls_month=0,
                    api_calls_limit=TIER_PRODUCTS.get(tier, {}).get("api_calls_limit", 5000),
                )
                s.add(sub)

            s.commit()
        log.info("subscription_activated", user_id=user_id, tier=tier)

    def _handle_subscription_updated_sync(self, sub_data: dict) -> None:
        """Update subscription status on changes."""
        from core.models import Session as DBSession, Subscription
        from sqlalchemy import select

        stripe_sub_id = sub_data["id"]
        with DBSession() as s:
            sub = s.execute(
                select(Subscription).where(
                    Subscription.stripe_subscription_id == stripe_sub_id
                )
            ).scalar_one_or_none()
            if sub:
                sub.cancel_at_period_end = sub_data.get("cancel_at_period_end", False)
                if sub_data.get("current_period_end"):
                    sub.current_period_end = dt.datetime.fromtimestamp(
                        sub_data["current_period_end"]
                    )
                s.commit()

    def _handle_subscription_deleted_sync(self, sub_data: dict) -> None:
        """Deactivate subscription on cancellation."""
        from core.models import Session as DBSession, User, Subscription
        from sqlalchemy import select

        stripe_sub_id = sub_data["id"]
        with DBSession() as s:
            sub = s.execute(
                select(Subscription).where(
                    Subscription.stripe_subscription_id == stripe_sub_id
                )
            ).scalar_one_or_none()
            if sub:
                sub.is_active = False
                user = s.execute(select(User).where(User.id == sub.user_id)).scalar_one_or_none()
                if user:
                    user.tier = "free"
                s.commit()
        log.info("subscription_cancelled", stripe_sub_id=stripe_sub_id)

    def _handle_payment_failed(self, invoice_data: dict) -> None:
        """Log failed payment for follow-up."""
        customer_id = invoice_data.get("customer")
        log.warning("payment_failed", customer_id=customer_id, amount=invoice_data.get("amount_due"))

    async def get_subscription_status(self, user_id: int) -> dict:
        """Get current subscription status from local DB (sync Session runs
        in a worker thread — must not block the event loop)."""
        return await asyncio.to_thread(self._get_subscription_status_sync, user_id)

    def _get_subscription_status_sync(self, user_id: int) -> dict:
        from core.models import Session as DBSession, User, Subscription
        from sqlalchemy import select

        with DBSession() as s:
            user = s.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
            if not user:
                return {"error": "User not found"}

            sub = s.execute(
                select(Subscription).where(Subscription.user_id == user_id)
            ).scalar_one_or_none()

            return {
                "user_id": user_id,
                "email": user.email,
                "tier": user.tier or "free",
                "subscription": {
                    "is_active": sub.is_active if sub else False,
                    "started_at": sub.started_at.isoformat() if sub and sub.started_at else None,
                    "expires_at": sub.expires_at.isoformat() if sub and sub.expires_at else None,
                    "monthly_price_nok": sub.monthly_price_nok if sub else 0,
                    "cancel_at_period_end": sub.cancel_at_period_end if sub else False,
                    "current_period_end": (
                        sub.current_period_end.isoformat()
                        if sub and sub.current_period_end else None
                    ),
                    "api_calls_month": sub.api_calls_month if sub else 0,
                    "api_calls_limit": sub.api_calls_limit if sub else 100,
                } if sub else None,
                "available_tiers": {
                    k: {"name": v["name"], "price_nok": v["price_nok"], "description": v["description"]}
                    for k, v in TIER_PRODUCTS.items()
                },
            }

    async def cancel_subscription(self, user_id: int) -> dict:
        """Cancel subscription at period end (sync DB + Stripe SDK in a
        worker thread — must not block the event loop)."""
        return await asyncio.to_thread(self._cancel_subscription_sync, user_id)

    def _cancel_subscription_sync(self, user_id: int) -> dict:
        from core.models import Session as DBSession, Subscription
        from sqlalchemy import select

        with DBSession() as s:
            sub = s.execute(
                select(Subscription).where(Subscription.user_id == user_id)
            ).scalar_one_or_none()

            if not sub or not sub.stripe_subscription_id:
                return {"error": "No active subscription"}

            if not settings.stripe_secret_key:
                sub.cancel_at_period_end = True
                s.commit()
                return {"status": "cancelled_at_period_end", "demo_mode": True}

            stripe = self._get_stripe()
            stripe.Subscription.modify(
                sub.stripe_subscription_id,
                cancel_at_period_end=True,
            )
            sub.cancel_at_period_end = True
            s.commit()

        log.info("subscription_cancel_requested", user_id=user_id)
        return {"status": "cancelled_at_period_end"}

    async def get_invoice_history(self, user_id: int) -> dict:
        """Get invoice history from Stripe (sync DB + SDK in a worker
        thread — must not block the event loop)."""
        return await asyncio.to_thread(self._get_invoice_history_sync, user_id)

    def _get_invoice_history_sync(self, user_id: int) -> dict:
        from core.models import Session as DBSession, User
        from sqlalchemy import select

        with DBSession() as s:
            user = s.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
            if not user or not user.stripe_customer_id:
                return {"invoices": [], "demo_mode": not settings.stripe_secret_key}

        if not settings.stripe_secret_key:
            return {"invoices": [], "demo_mode": True}

        stripe = self._get_stripe()
        invoices = stripe.Invoice.list(customer=user.stripe_customer_id, limit=24)

        return {
            "invoices": [
                {
                    "id": inv.id,
                    "amount_nok": inv.amount_due / 100,
                    "status": inv.status,
                    "created": dt.datetime.fromtimestamp(inv.created).isoformat(),
                    "period_start": dt.datetime.fromtimestamp(inv.period_start).isoformat(),
                    "period_end": dt.datetime.fromtimestamp(inv.period_end).isoformat(),
                    "invoice_url": inv.hosted_invoice_url,
                }
                for inv in invoices.data
            ]
        }


# Singleton
stripe_billing = StripeBillingEngine()
