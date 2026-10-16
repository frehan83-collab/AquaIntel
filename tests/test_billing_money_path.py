"""Money-path proof (commercial hardening §2).

Proves the WHOLE chain end to end without Stripe credentials:
catalog → checkout → webhook → entitlement → previously-gated route.

The valuable assertion is the last one in `TestMoneyPath`: a free account gets
402 on a premium output, pays (mock), and then gets through — with the plan key
resolved server-side from the price id, never from a client-supplied tier string.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from core.api import app
from core.auth import create_token
from core.billing import stripe_catalog
from core.entitlements import PLANS
from core.models import Session as DBSession, Subscription, User

PREMIUM_PATH = "/api/ais/tracks"


@pytest.fixture(scope="module")
def client():
    return TestClient(app, raise_server_exceptions=False)


def _bearer(user_id: int, tier: str = "free") -> dict[str, str]:
    return {
        "Authorization": f"Bearer {create_token(user_id, f'buyer-{user_id}@x.test', tier)}"
    }


@pytest.fixture
def buyer():
    """A real user row (Subscription.user_id is a FK)."""
    with DBSession() as s:
        user = User(
            email=f"money-path-{id(object())}@x.test",
            hashed_password="x",
            role="buyer",
            tier="free",
        )
        s.add(user)
        s.commit()
        s.refresh(user)
        uid = user.id

    yield uid

    with DBSession() as s:
        s.query(Subscription).filter(Subscription.user_id == uid).delete()
        s.query(User).filter(User.id == uid).delete()
        s.commit()


class TestCatalog:
    def test_catalog_is_public_and_marks_mock_mode(self, client):
        body = client.get("/api/billing/catalog").json()
        assert body["currency"] == "nok"
        plans = {p["plan"]: p for p in body["plans"]}
        assert set(plans) == set(stripe_catalog.SELF_SERVE_PLANS)
        for plan in plans.values():
            assert plan["amount_nok"] == PLANS[plan["plan"]].price_nok_month
            # Mock ids must never be mistakable for live prices.
            assert plan["mock"] is (not stripe_catalog.is_configured())

    def test_licensed_tier_is_not_self_serve(self, client):
        body = client.get("/api/billing/catalog").json()
        assert body["licensed_tier"]["plan"] == "data"
        assert "data" not in {p["plan"] for p in body["plans"]}


class TestPriceToPlanMapping:
    def test_mock_price_ids_resolve_to_plan_keys(self):
        for key in stripe_catalog.SELF_SERVE_PLANS:
            assert stripe_catalog.plan_from_price_id(f"price_mock_{key}") == key

    def test_unknown_price_ids_do_not_resolve(self):
        assert stripe_catalog.plan_from_price_id("price_live_unknown") is None
        assert stripe_catalog.plan_from_price_id(None) is None

    def test_legacy_metadata_key_still_resolves(self):
        assert (
            stripe_catalog.plan_from_metadata({"openclaw_tier": "premium"})
            == "professional"
        )
        assert (
            stripe_catalog.plan_from_metadata({"aquaintel_plan": "operator"})
            == "operator"
        )


class TestMoneyPath:
    def test_free_user_blocked_then_pays_then_gets_through(self, client, buyer, monkeypatch):
        monkeypatch.setenv("FISHINTEL_ENFORCE_ROUTE_GATING", "1")
        monkeypatch.setenv("FISHINTEL_ENFORCE_QUOTAS", "0")

        # 1) free account cannot reach the premium output
        blocked = client.get(PREMIUM_PATH, headers=_bearer(buyer))
        assert blocked.status_code == 402, blocked.text
        assert blocked.json()["suggested_plan"] in PLANS

        # 2) request a checkout (mock mode: no Stripe key required)
        checkout = client.post(
            "/api/billing/create-checkout-session",
            params={"plan": "professional"},
            headers=_bearer(buyer),
        )
        assert checkout.status_code == 200, checkout.text
        assert checkout.json()["plan"] == "professional"
        assert "checkout_url" in checkout.json()

        # 3) the (mock) webhook activates the entitlement
        hook = client.post(
            "/api/billing/webhook/mock",
            json={
                "event": "checkout.session.completed",
                "user_id": buyer,
                "plan": "professional",
            },
        )
        assert hook.status_code == 200, hook.text
        assert hook.json()["plan"] == "professional"

        # 4) the same request now passes the paywall
        allowed = client.get(PREMIUM_PATH, headers=_bearer(buyer, "professional"))
        assert allowed.status_code != 402, allowed.text

    def test_entitlement_is_persisted(self, client, buyer):
        client.post(
            "/api/billing/webhook/mock",
            json={"event": "checkout.session.completed", "user_id": buyer,
                  "plan": "enterprise"},
        )
        with DBSession() as s:
            user = s.execute(select(User).where(User.id == buyer)).scalar_one()
            sub = s.execute(
                select(Subscription).where(Subscription.user_id == buyer)
            ).scalar_one_or_none()
            assert user.tier == "enterprise"
            assert sub is not None
            assert sub.tier == "enterprise"
            assert sub.is_active is True
            assert sub.monthly_price_nok == PLANS["enterprise"].price_nok_month
            assert sub.api_calls_limit == PLANS["enterprise"].api_calls_per_month

    def test_cancellation_returns_the_user_to_free(self, client, buyer):
        client.post(
            "/api/billing/webhook/mock",
            json={"event": "checkout.session.completed", "user_id": buyer,
                  "plan": "investor"},
        )
        client.post(
            "/api/billing/webhook/mock",
            json={"event": "customer.subscription.deleted", "user_id": buyer},
        )
        with DBSession() as s:
            user = s.execute(select(User).where(User.id == buyer)).scalar_one()
            assert user.tier == "free"

    def test_checkout_rejects_a_non_self_serve_plan(self, client, buyer):
        r = client.post(
            "/api/billing/create-checkout-session",
            params={"plan": "data"},
            headers=_bearer(buyer),
        )
        assert r.status_code == 400

    def test_checkout_requires_authentication(self, client):
        r = client.post(
            "/api/billing/create-checkout-session", params={"plan": "professional"}
        )
        assert r.status_code == 401

    def test_mock_webhook_validates_the_plan(self, client, buyer):
        r = client.post(
            "/api/billing/webhook/mock",
            json={"event": "checkout.session.completed", "user_id": buyer,
                  "plan": "not-a-plan"},
        )
        assert r.status_code == 422

    def test_mock_webhook_requires_the_token_when_configured(self, client, buyer, monkeypatch):
        monkeypatch.setenv("FISHINTEL_MOCK_BILLING_TOKEN", "s3cret")
        body = {"event": "checkout.session.completed", "user_id": buyer,
                "plan": "professional"}
        assert client.post("/api/billing/webhook/mock", json=body).status_code == 403
        ok = client.post(
            "/api/billing/webhook/mock",
            json=body,
            headers={"X-Mock-Billing-Token": "s3cret"},
        )
        assert ok.status_code == 200
