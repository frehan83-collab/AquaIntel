"""
Tier daily-quota enforcement tests (review H2)
==============================================
Pins the enforcement half of the TIERS contract:

- `TierQuotaMiddleware` is actually registered on the app (the original
  bug: `check_tier_access`/TIERS had zero callers — nothing was enforced).
- Authenticated requests (Bearer JWT / X-API-Key) are capped at
  `TIERS[tier]["api_calls_per_day"]` with a structured 429 once exceeded.
- Anonymous "public demo" traffic is NOT quota-gated (the public site
  stays browsable) — that is the documented, honest scope.
- `/api/auth/*`, `/api/health`, `/api/billing/*` never consume quota.
- Tier surfaces (`/api/auth/tiers`, `/api/tiers`) honestly report
  `route_gating_enforced: false` (allow-lists not enforced yet) while
  the daily quota is enforced.
- `check_tier_access` (the future paywall predicate) logic is pinned.

Quotas are force-enabled per test via FISHINTEL_ENFORCE_QUOTAS (the
middleware reads it per request); counters are reset around each test.
"""
from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient

import core.tier_quota as tier_quota
from core.api import app
from core.auth import TIERS, TokenPayload, check_tier_access, create_token
from core.tier_quota import TierQuotaMiddleware


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _quota_on(monkeypatch):
    monkeypatch.setenv("FISHINTEL_ENFORCE_QUOTAS", "1")
    tier_quota.reset_counters()
    yield
    tier_quota.reset_counters()


def _bearer(tier: str, user_id: int) -> dict[str, str]:
    token = create_token(user_id, f"quota-{user_id}@fishintel.test", tier)
    return {"Authorization": f"Bearer {token}"}


def _payload(tier: str) -> TokenPayload:
    return TokenPayload(
        user_id=1,
        email="tier@test",
        tier=tier,
        exp=dt.datetime.now(dt.UTC) + dt.timedelta(hours=1),
    )


class TestMiddlewareWiring:
    def test_tier_quota_middleware_registered(self):
        # Regression net: enforcement middleware must stay wired.
        assert any(m.cls is TierQuotaMiddleware for m in app.user_middleware)

    def test_require_tier_dead_code_removed(self):
        # The unwired minimum-tier dependency factory was deleted (review
        # H2 + dead-code rule); the live enforcement lives in tier_quota.
        import core.auth as auth_mod

        assert not hasattr(auth_mod, "require_tier")


class TestQuotaEnforcement:
    def test_anonymous_traffic_not_quota_gated(self, client, monkeypatch):
        monkeypatch.setitem(TIERS["free"], "api_calls_per_day", 2)
        for _ in range(5):
            assert client.get("/api/signals").status_code == 200

    def test_authenticated_free_user_capped_at_quota(self, client, monkeypatch):
        monkeypatch.setitem(TIERS["free"], "api_calls_per_day", 3)
        headers = _bearer("free", 91)
        for _ in range(3):
            assert client.get("/api/signals", headers=headers).status_code == 200
        r = client.get("/api/signals", headers=headers)
        assert r.status_code == 429
        body = r.json()
        assert body["error"] == "tier_quota_exceeded"
        assert body["tier"] == "free"
        assert body["quota_per_day"] == 3
        assert "retry-after" in {k.lower() for k in r.headers}

    def test_quota_buckets_are_per_user(self, client, monkeypatch):
        monkeypatch.setitem(TIERS["free"], "api_calls_per_day", 2)
        a = _bearer("free", 91)
        b = _bearer("free", 92)
        for _ in range(2):
            assert client.get("/api/signals", headers=a).status_code == 200
        assert client.get("/api/signals", headers=a).status_code == 429
        # A different user gets their own bucket
        assert client.get("/api/signals", headers=b).status_code == 200

    def test_professional_tier_gets_professional_quota(self, client, monkeypatch):
        monkeypatch.setitem(TIERS["professional"], "api_calls_per_day", 2)
        headers = _bearer("professional", 93)
        for _ in range(2):
            assert client.get("/api/signals", headers=headers).status_code == 200
        r = client.get("/api/signals", headers=headers)
        assert r.status_code == 429
        assert r.json()["tier"] == "professional"
        assert r.json()["quota_per_day"] == 2

    def test_tier_alias_pro_resolved(self, client, monkeypatch):
        # Old token tier names ("pro") resolve to "professional"
        monkeypatch.setitem(TIERS["professional"], "api_calls_per_day", 1)
        headers = _bearer("pro", 96)
        assert client.get("/api/signals", headers=headers).status_code == 200
        r = client.get("/api/signals", headers=headers)
        assert r.status_code == 429
        assert r.json()["tier"] == "professional"

    def test_unlimited_tier_not_gated(self, client, monkeypatch):
        # api_calls_per_day <= 0 means unlimited (e.g. a future tier)
        monkeypatch.setitem(TIERS["free"], "api_calls_per_day", 0)
        headers = _bearer("free", 97)
        for _ in range(6):
            assert client.get("/api/signals", headers=headers).status_code == 200

    def test_auth_health_billing_never_consume_quota(self, client, monkeypatch):
        monkeypatch.setitem(TIERS["free"], "api_calls_per_day", 1)
        headers = _bearer("free", 94)
        # quota-consuming call burns the 1-call allowance
        assert client.get("/api/signals", headers=headers).status_code == 200
        assert client.get("/api/signals", headers=headers).status_code == 429
        # auth/health/billing remain reachable despite the exhausted quota
        assert client.get("/api/health", headers=headers).status_code == 200
        assert client.get("/api/auth/tiers", headers=headers).status_code == 200
        status = client.get("/api/billing/subscription", headers=headers).status_code
        assert status in (200, 401, 404)  # reachable, never quota-blocked

    def test_invalid_credentials_pass_through(self, client):
        # Bad bearer / bad API key: middleware must not 500 — the route
        # (or its auth dependency) decides the response.
        r = client.get("/api/health", headers={"Authorization": "Bearer garbage"})
        assert r.status_code == 200
        r = client.get("/api/signals", headers={"X-API-Key": "oc_live_invalid"})
        assert r.status_code == 200  # public route; key simply unused here

    def test_quotas_disabled_via_env(self, client, monkeypatch):
        monkeypatch.setenv("FISHINTEL_ENFORCE_QUOTAS", "0")
        monkeypatch.setitem(TIERS["free"], "api_calls_per_day", 1)
        headers = _bearer("free", 95)
        for _ in range(5):
            assert client.get("/api/signals", headers=headers).status_code == 200

    def test_usage_helper_tracks_counts(self, client, monkeypatch):
        monkeypatch.setitem(TIERS["free"], "api_calls_per_day", 100)
        headers = _bearer("free", 98)
        client.get("/api/signals", headers=headers)
        client.get("/api/signals", headers=headers)
        assert tier_quota.current_usage(98, "free") == 2


class TestTierSurfacesHonesty:
    def test_auth_tiers_report_enforcement_flags(self, client):
        r = client.get("/api/auth/tiers")
        assert r.status_code == 200
        for tier in r.json():
            assert tier["daily_quota_enforced"] is True
            assert tier["route_gating_enforced"] is False
            assert isinstance(tier["api_calls_per_day"], int)

    def test_misc_tiers_mirror_enforced_values(self, client):
        r = client.get("/api/tiers")
        assert r.status_code == 200
        tiers = r.json()
        assert tiers["free"]["daily_quota_enforced"] is True
        assert tiers["free"]["route_gating_enforced"] is False
        # The enforced figure comes from core/auth.py, not the legacy
        # monthly api_calls_limit in core/valuechain/subscription.py.
        assert (
            tiers["free"]["enforced_api_calls_per_day"]
            == TIERS["free"]["api_calls_per_day"]
        )
        # Tiers unknown to the enforcement source fall back to the free quota
        assert (
            tiers["intelligence"]["enforced_api_calls_per_day"]
            == TIERS["free"]["api_calls_per_day"]
        )


class TestCheckTierAccessPredicate:
    """Pins the (not-yet-wired) allow-list predicate for the future paywall."""

    def test_anonymous_is_free_tier(self):
        assert check_tier_access(None, "/api/health") is True
        assert check_tier_access(None, "/api/signals/confirm") is True
        assert check_tier_access(None, "/api/market/prices") is False

    def test_professional_allow_list(self):
        user = _payload("professional")
        assert check_tier_access(user, "/api/bloom/forecast") is True
        assert check_tier_access(user, "/api/market/prices") is False

    def test_enterprise_allow_list(self):
        user = _payload("enterprise")
        assert check_tier_access(user, "/api/market/prices") is True

    def test_investor_all_routes(self):
        user = _payload("investor")
        assert check_tier_access(user, "/api/anything/at/all") is True

    def test_tier_alias_resolved(self):
        assert check_tier_access(_payload("pro"), "/api/bloom/x") is True

    def test_unknown_tier_falls_back_to_free(self):
        assert check_tier_access(_payload("intelligence"), "/api/market/x") is False
