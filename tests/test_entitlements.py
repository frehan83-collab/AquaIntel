"""Entitlement single-source-of-truth + paywall tests (commercial hardening §1).

These replace assertions that used to *pin the conflict*: before
``core/entitlements.py``, ``core/auth.py`` (4 tiers, per-DAY quota) and
``core/valuechain/subscription.py`` (5 tiers, per-MONTH limit) were two
divergent tables and ``/api/tiers`` served both. ``intelligence`` existed in one
table only and silently fell back to the free quota.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import core.tier_quota as tier_quota
from core.api import app
from core.auth import create_token
from core.entitlements import (
    PLAN_HIERARCHY,
    PLANS,
    PREMIUM_PREFIXES,
    auth_tiers,
    catalog_tiers,
    get_plan,
    normalize_plan,
    route_allowed,
    upgrade_hint,
)


@pytest.fixture(scope="module")
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _counters():
    tier_quota.reset_counters()
    yield
    tier_quota.reset_counters()


def _bearer(tier: str, user_id: int) -> dict[str, str]:
    token = create_token(user_id, f"plan-{user_id}@x.test", tier)
    return {"Authorization": f"Bearer {token}"}


class TestSingleSourceOfTruth:
    """The two projections must be derived from one table, so they agree."""

    def test_projections_agree_on_price_and_quota(self):
        a, c = auth_tiers(), catalog_tiers()
        assert set(a) <= set(c)
        for key, cfg in a.items():
            assert cfg["price_nok"] == c[key]["monthly_price_nok"], key
            assert cfg["api_calls_per_day"] * 30 == c[key]["api_calls_limit"], key

    def test_monthly_limit_is_derived_not_stored(self):
        for key, plan in PLANS.items():
            expected = plan.api_calls_per_day * 30 if plan.api_calls_per_day > 0 else -1
            assert plan.api_calls_per_month == expected, key

    def test_plan_keys_are_canonical(self):
        for key, plan in PLANS.items():
            assert key == plan.key

    def test_tier_endpoints_report_the_same_quota(self, client):
        """/api/tiers and /api/auth/tiers must not contradict each other."""
        tiers = client.get("/api/tiers").json()
        for entry in client.get("/api/auth/tiers").json():
            key = entry["id"]
            assert (
                entry["api_calls_per_day"] == tiers[key]["enforced_api_calls_per_day"]
            ), key

    def test_intelligence_has_its_own_quota_not_the_free_fallback(self, client):
        """The observable symptom of the old conflict."""
        tiers = client.get("/api/tiers").json()
        assert (
            tiers["intelligence"]["enforced_api_calls_per_day"]
            == get_plan("intelligence").api_calls_per_day
        )
        assert (
            tiers["intelligence"]["enforced_api_calls_per_day"]
            != get_plan("free").api_calls_per_day
        )


class TestAliasNormalisation:
    @pytest.mark.parametrize("raw,expected", [
        ("premium", "professional"),
        ("pro", "professional"),
        ("desk", "professional"),
        ("pilot", "professional"),
        ("growth", "operator"),
        ("farm", "operator"),
        ("basic", "free"),
        ("PREMIUM", "professional"),
        ("licence", "data"),
        ("datapartner", "data"),
        ("nonsense", "free"),
        ("", "free"),
        (None, "free"),
    ])
    def test_aliases_resolve(self, raw, expected):
        assert normalize_plan(raw) == expected


class TestPaywallPolicy:
    @pytest.mark.parametrize("path", PREMIUM_PREFIXES)
    def test_free_account_cannot_reach_premium_outputs(self, path):
        assert route_allowed("free", path) is False

    @pytest.mark.parametrize(
        "tier", ["professional", "enterprise", "investor", "intelligence", "data"]
    )
    def test_paid_plans_reach_premium_outputs(self, tier):
        for path in PREMIUM_PREFIXES:
            assert route_allowed(tier, path) is True

    def test_anonymous_browsing_is_never_gated(self):
        """Anonymous visitors are not an account — the funnel stays open."""
        for path in ("/api/market/price-outlook", "/api/ais/tracks", "/api/lice/summary"):
            assert route_allowed(None, path) is True

    def test_never_gated_paths_stay_open_for_everyone(self):
        for path in (
            "/api/auth/login",
            "/api/billing/subscription-status",
            "/api/health",
            "/api/tiers",
            "/api/entitlements/plans",
        ):
            assert route_allowed("free", path) is True


class TestWallIsEnforced:
    def test_free_account_gets_402_with_upgrade_payload(self, client, monkeypatch):
        monkeypatch.setenv("FISHINTEL_ENFORCE_ROUTE_GATING", "1")
        r = client.get("/api/market/price-outlook", headers=_bearer("free", 9001))
        assert r.status_code == 402, r.text
        body = r.json()
        assert body["error"] == "plan_upgrade_required"
        assert body["suggested_plan"] in PLANS
        assert body["upgrade_url"].startswith("/billing?plan=")

    def test_gating_kill_switch_restores_access(self, client, monkeypatch):
        monkeypatch.setenv("FISHINTEL_ENFORCE_ROUTE_GATING", "0")
        r = client.get("/api/market/price-outlook", headers=_bearer("free", 9002))
        assert r.status_code != 402

    def test_quota_429_carries_the_upgrade_payload(self, client, monkeypatch):
        monkeypatch.setenv("FISHINTEL_ENFORCE_QUOTAS", "1")
        monkeypatch.setenv("FISHINTEL_ENFORCE_ROUTE_GATING", "0")
        # The quota now comes from the SSOT (core.entitlements.PLANS), which is
        # frozen — replace the entry rather than mutating a copy in core/auth.
        from dataclasses import replace

        monkeypatch.setitem(PLANS, "free", replace(PLANS["free"], api_calls_per_day=1))
        headers = _bearer("free", 9003)
        assert client.get("/api/signals", headers=headers).status_code == 200
        r = client.get("/api/signals", headers=headers)
        assert r.status_code == 429, r.text
        assert r.json()["suggested_plan"] in PLANS
        assert r.headers.get("Retry-After")


class TestUpgradePayload:
    def test_hint_is_actionable(self):
        hint = upgrade_hint("free", error="plan_upgrade_required", reason="x", path="/p")
        for key in (
            "error", "message", "current_plan", "current_plan_name",
            "suggested_plan", "suggested_plan_name", "upgrade_url", "plans_url",
        ):
            assert key in hint
        assert hint["suggested_plan"] in PLANS
        assert hint["upgrade_url"] == f"/billing?plan={hint['suggested_plan']}"


class TestCatalogEndpoints:
    def test_plans_endpoint_returns_the_canonical_catalog(self, client):
        body = client.get("/api/entitlements/plans").json()
        assert [p["key"] for p in body["plans"]] == list(PLAN_HIERARCHY) + ["data"]
        assert body["premium_prefixes"] == list(PREMIUM_PREFIXES)
        assert body["currency"] == "NOK"

    def test_me_endpoint_anonymous(self, client):
        body = client.get("/api/entitlements/me").json()
        assert body["authenticated"] is False
        assert body["plan"] == "free"

    def test_check_endpoint_reports_the_boundary(self, client):
        """Anonymous is ungated by design, so the boundary shows for a free
        account (which is what the UI needs to render a locked state)."""
        headers = _bearer("free", 9101)
        blocked = client.get(
            "/api/entitlements/check",
            params={"path": "/api/market/price-outlook"},
            headers=headers,
        ).json()
        allowed = client.get(
            "/api/entitlements/check",
            params={"path": "/api/lice/summary"},
            headers=headers,
        ).json()
        assert blocked["allowed"] is False
        assert allowed["allowed"] is True
        anon = client.get(
            "/api/entitlements/check", params={"path": "/api/market/price-outlook"}
        ).json()
        assert anon["allowed"] is True, "anonymous browsing is never gated"

