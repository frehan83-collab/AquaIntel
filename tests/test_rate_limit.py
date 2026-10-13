"""
Rate limiting enforcement tests (review H1)
===========================================
Pins the wiring that makes the configured SlowAPI limits actually run.
The original bug: `Limiter(default_limits=["200/minute"])` +
`app.state.limiter` + the 429 handler existed in core/api.py, but
SlowAPIMiddleware was never registered and no route used `@limiter.limit`,
so nothing was ever limited.

Covered here:
- SlowAPIMiddleware is registered on the app (the wiring itself),
- a burst over the limit returns 429 with the standard error body,
- X-RateLimit-* headers are emitted (headers_enabled=True),
- 429 responses still pass through CORS/SecurityHeaders (CORS stays
  outermost: the middleware is registered before the CORS middleware,
  and later add_middleware calls wrap earlier ones),
- the key function buckets by X-API-Key / JWT user / client IP.

The burst tests swap `app.state.limiter` for a strict limiter
("3/minute"); the middleware resolves the limiter per request, so this
exercises the real middleware path end-to-end.
"""
from __future__ import annotations

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from core.api import _get_rate_limit_key, app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def _strict_limiter(limit: str = "3/minute") -> Limiter:
    return Limiter(
        key_func=_get_rate_limit_key,
        default_limits=[limit],
        strategy="moving-window",
        headers_enabled=True,
    )


class TestMiddlewareWiring:
    def test_slowapi_middleware_registered(self):
        # Regression net: the limiter existed but was never wired before.
        assert any(m.cls is SlowAPIMiddleware for m in app.user_middleware)

    def test_rate_limit_exception_handler_registered(self):
        assert RateLimitExceeded in app.exception_handlers


class TestBurstEnforcement:
    def test_burst_exceeding_limit_returns_429(self, client, monkeypatch):
        monkeypatch.setattr(app.state, "limiter", _strict_limiter())
        codes = [client.get("/api/health").status_code for _ in range(4)]
        assert codes[:3] == [200, 200, 200]
        assert codes[3] == 429

    def test_429_body_and_rate_limit_headers(self, client, monkeypatch):
        monkeypatch.setattr(app.state, "limiter", _strict_limiter())
        for _ in range(3):
            client.get("/api/health")
        r = client.get("/api/health")
        assert r.status_code == 429
        # standard slowapi 429 body
        assert "rate limit" in r.text.lower()
        # headers_enabled=True -> clients can self-throttle
        assert "x-ratelimit-limit" in {k.lower() for k in r.headers}
        assert "retry-after" in {k.lower() for k in r.headers}

    def test_429_keeps_outer_middleware_headers(self, client, monkeypatch):
        # The rate-limit middleware is registered BEFORE CORS/SecurityHeaders
        # (later add_middleware calls wrap earlier ones), so a 429 raised
        # inside the limiter still flows outward through them.
        monkeypatch.setattr(app.state, "limiter", _strict_limiter())
        for _ in range(4):
            client.get("/api/health")
        r = client.get("/api/health")
        assert r.status_code == 429
        assert r.headers.get("x-content-type-options") == "nosniff"
        assert r.headers.get("x-request-id")  # CorrelationIDMiddleware

    def test_limit_independent_per_key(self, client, monkeypatch):
        # Different keys (here: different API keys) get separate buckets,
        # so one client exceeding its limit does not block another.
        monkeypatch.setattr(app.state, "limiter", _strict_limiter())
        a = {"X-API-Key": "key-alpha"}
        b = {"X-API-Key": "key-beta"}
        for _ in range(3):
            client.get("/api/health", headers=a)
        assert client.get("/api/health", headers=a).status_code == 429
        assert client.get("/api/health", headers=b).status_code == 200


class TestRateLimitKey:
    @staticmethod
    def _request(headers: dict[str, str]) -> Request:
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/health",
            "headers": [
                (k.lower().encode(), v.encode()) for k, v in headers.items()
            ],
            "client": ("203.0.113.7", 1234),
        }
        return Request(scope)

    def test_api_key_header_buckets_by_key(self):
        r = self._request({"X-API-Key": "oc_live_0123456789abcdef"})
        assert _get_rate_limit_key(r) == "apikey:oc_live_01234567"

    def test_invalid_bearer_falls_back_to_ip(self):
        r = self._request({"Authorization": "Bearer not-a-jwt"})
        assert _get_rate_limit_key(r) == "203.0.113.7"

    def test_anonymous_buckets_by_ip(self):
        r = self._request({})
        assert _get_rate_limit_key(r) == "203.0.113.7"
