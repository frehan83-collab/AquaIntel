"""
Tier daily-quota enforcement (review H2)
========================================
Enforces `TIERS[tier]["api_calls_per_day"]` for AUTHENTICATED requests
(Bearer JWT or X-API-Key) via `TierQuotaMiddleware`, returning 429 with a
structured error once the per-UTC-day allowance is exhausted.

Honest scope (aligned with the platform's provenance discipline):
- Anonymous "public demo" traffic is NOT quota-gated — the public site
  stays browsable for unauthenticated visitors (it remains subject to
  the global rate limiter in core/api.py).
- Route-level tier gating (the `routes` allow-lists in core/auth.TIERS)
  is NOT enforced yet; `check_tier_access` is the tested predicate the
  future paywall middleware will use. Tier surfaces expose
  `route_gating_enforced: false` so no consumer is misled.
- `/api/auth/*` and `/api/health` never consume quota (auth/infra
  endpoints must stay reachable to log in and upgrade).
- Counters are in-process per UTC day (like slowapi's default memory
  storage): per worker. Swap in a shared store when the paywall ships.

Kill-switch for test/CI suites: `FISHINTEL_ENFORCE_QUOTAS=0` (read per
request so tests can toggle it; production default is on).
"""
from __future__ import annotations

import datetime as dt
import os
import threading

from fastapi import Request
from fastapi.security import HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


# ── Counter store (in-process; see module docstring) ──────────────────────────
_counts: dict[tuple[str, str], int] = {}
_lock = threading.Lock()

_MAX_TRACKED_KEYS = 50_000  # prune guard (user-tier x day)


def reset_counters() -> None:
    """Clear all quota counters (tests / ops reset)."""
    with _lock:
        _counts.clear()


def current_usage(user_id: int, tier: str) -> int:
    """Calls consumed today (UTC) by (user, tier). Test/inspection helper."""
    day = _utc_day()
    with _lock:
        return _counts.get((f"{user_id}:{tier}", day), 0)


def quotas_enabled() -> bool:
    """Quota enforcement is on unless FISHINTEL_ENFORCE_QUOTAS disables it."""
    return os.environ.get("FISHINTEL_ENFORCE_QUOTAS", "1").lower() not in (
        "0",
        "false",
        "no",
    )


def _utc_day() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%d")


def _seconds_until_utc_midnight() -> int:
    now = dt.datetime.now(dt.UTC)
    tomorrow = (now + dt.timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return max(1, int((tomorrow - now).total_seconds()))


async def _resolve_user(request: Request):
    """Best-effort authenticated-user resolution for quota counting.

    Returns None for anonymous requests or invalid/expired credentials
    (the route's own auth dependency decides the 401 in that case).
    """
    try:
        from core.auth import get_current_user

        creds = None
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            creds = HTTPAuthorizationCredentials(
                scheme="Bearer", credentials=auth[7:]
            )
        return await get_current_user(request, creds)
    except Exception:
        return None


class TierQuotaMiddleware(BaseHTTPMiddleware):
    """Enforce the per-tier daily API allowance for authenticated calls."""

    async def dispatch(self, request, call_next):
        if not quotas_enabled():
            return await call_next(request)

        if request.method == "OPTIONS":
            return await call_next(request)  # CORS preflight

        path = request.url.path
        # Auth/infra/billing endpoints never consume quota — users must
        # always be able to log in, check status, and upgrade.
        if path.startswith(("/api/auth/", "/api/health", "/api/billing/")):
            return await call_next(request)

        has_bearer = request.headers.get("Authorization", "").startswith("Bearer ")
        has_api_key = bool(
            request.headers.get("X-API-Key") or request.query_params.get("api_key")
        )
        if not (has_bearer or has_api_key):
            return await call_next(request)  # anonymous: not quota-gated

        payload = await _resolve_user(request)
        if payload is None:
            return await call_next(request)  # bad credentials: route decides

        from core.auth import TIERS, _resolve_tier

        tier = _resolve_tier(payload.tier)
        tier_config = TIERS.get(tier, TIERS["free"])
        quota = int(tier_config.get("api_calls_per_day", 0))
        if quota <= 0:
            return await call_next(request)  # unlimited tier

        key = (f"{payload.user_id}:{tier}", _utc_day())
        with _lock:
            used = _counts.get(key, 0) + 1
            _counts[key] = used
            if len(_counts) > _MAX_TRACKED_KEYS:
                day = key[1]
                for stale in [k for k in _counts if k[1] != day]:
                    del _counts[stale]

        if used > quota:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "tier_quota_exceeded",
                    "message": (
                        f"Daily API quota exceeded for tier '{tier}' "
                        f"({quota}/{quota} calls used today, UTC). "
                        "Upgrade your subscription tier for a higher quota."
                    ),
                    "tier": tier,
                    "quota_per_day": quota,
                    "used_today": quota,
                },
                headers={"Retry-After": str(_seconds_until_utc_midnight())},
            )

        return await call_next(request)
