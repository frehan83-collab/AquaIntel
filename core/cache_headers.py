"""
HTTP caching middleware — ETag + Cache-Control for API responses.

Adds Cache-Control and ETag headers based on URL prefix rules, and handles
conditional requests (If-None-Match) by returning 304 Not Modified when the
client already has the current version.

Cache tiers:
  - Static / slow-changing (1 hour):  /api/health, /api/admin/status
  - Semi-static (5 min):              /api/leaders, /api/competitiveness, /api/global-supply
  - Moderate freshness (1 min):       /api/lice, /api/disease, /api/market, /api/feed-cost
  - Real-time (no-cache):             /api/alerts, /api/notifications, /ws
  - User-specific (private, no-store):/api/auth, /api/billing
"""

from __future__ import annotations

import hashlib

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


# ── Cache rules ────────────────────────────────────────────────────────
# Positive int  = public, max-age=<seconds>
# 0             = no-cache (real-time data)
# -1            = private, no-store (user-specific / sensitive)
#
# Rules are matched by longest-prefix-first so more specific paths win.
# For example "/api/admin/status" (3600) beats "/api/admin" if both existed.

CACHE_RULES: dict[str, int] = {
    # ── Static / slow-changing (1 hour) ─────────────────────────────
    "/api/health":                      3600,
    "/api/admin/status":                3600,
    "/api/admin/data-quality":          3600,

    # ── Semi-static (5 min) ─────────────────────────────────────────
    "/api/leaders":                     300,
    "/api/competitiveness":             300,
    "/api/global-supply":               300,
    "/api/global/":                     300,
    "/api/production":                  300,
    "/api/benchmark":                   300,
    "/api/esg":                         300,
    "/api/efficacy":                    300,

    # ── Moderate freshness (1 min) ──────────────────────────────────
    "/api/lice":                        60,
    "/api/disease":                     60,
    "/api/market":                      60,
    "/api/feed-cost":                   60,
    "/api/supply":                      60,
    "/api/brief":                       60,
    "/api/anomaly":                     60,
    "/api/ocean":                       60,
    "/api/bloom":                       60,
    "/api/bio-risk":                    60,
    "/api/climate":                     60,
    "/api/canada":                      60,
    "/api/scotland":                    60,
    "/api/faroe":                       60,
    "/api/iceland":                     60,
    "/api/chile":                       60,
    "/api/price":                       60,
    "/api/analytics":                   60,
    "/api/signals":                     60,

    # ── Real-time (no-cache) ────────────────────────────────────────
    "/api/alerts":                      0,
    "/api/notifications":               0,
    "/ws/":                             0,
    "/api/chat":                        0,
    "/api/command-centre":              0,

    # ── User-specific (private, no-store) ───────────────────────────
    "/api/auth":                        -1,
    "/api/billing":                     -1,
    "/api/scenarios/save":              -1,
    "/api/scenarios/list":              -1,
    "/api/treatment/log":               -1,
}

# Pre-sort rules by key length descending so longest prefix matches first.
_SORTED_RULES = sorted(CACHE_RULES.items(), key=lambda kv: len(kv[0]), reverse=True)


def _match_cache_rule(path: str) -> int | None:
    """Return the max-age for the first matching prefix rule, or None."""
    for prefix, max_age in _SORTED_RULES:
        if path.startswith(prefix):
            return max_age
    return None


def _build_cache_control(max_age: int) -> str:
    """Convert a max-age int to a Cache-Control header value."""
    if max_age < 0:
        return "private, no-store, no-cache"
    if max_age == 0:
        return "no-cache, no-store, must-revalidate"
    return f"public, max-age={max_age}"


class CacheHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds Cache-Control and ETag headers to GET responses
    and returns 304 Not Modified for conditional requests.

    Only applies to GET requests — mutations (POST/PUT/DELETE) are never cached.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Only cache GET requests.
        if request.method != "GET":
            return response

        path = request.url.path
        max_age = _match_cache_rule(path)

        if max_age is None:
            # No rule matched — skip (don't add headers).
            return response

        # Set Cache-Control.
        response.headers["Cache-Control"] = _build_cache_control(max_age)

        # For cacheable responses (max_age > 0), generate an ETag from the
        # response body and handle If-None-Match.
        if max_age > 0 and hasattr(response, "body"):
            etag_hash = hashlib.md5(response.body).hexdigest()
            etag = f'"{etag_hash}"'
            response.headers["ETag"] = etag

            if_none_match = request.headers.get("if-none-match")
            if if_none_match and if_none_match.strip() == etag:
                return Response(status_code=304, headers={
                    "ETag": etag,
                    "Cache-Control": response.headers["Cache-Control"],
                })

        return response
