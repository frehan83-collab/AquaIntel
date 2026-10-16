"""
Tier daily-quota enforcement (review H2)
========================================
Enforces `core.entitlements.PLANS[plan].api_calls_per_day` for AUTHENTICATED requests
(Bearer JWT or X-API-Key) via `TierQuotaMiddleware`, returning 429 with a
structured error once the per-UTC-day allowance is exhausted.

Honest scope (aligned with the platform's provenance discipline):
- Anonymous "public demo" traffic is NOT quota-gated — the public site
  stays browsable for unauthenticated visitors (it remains subject to
  the global rate limiter in core/api.py).
- Premium route gating IS enforced for authenticated accounts on the curated
  `core.entitlements.PREMIUM_PREFIXES` outputs (HTTP 402 + upgrade payload).
  The tier listing surfaces now report `route_gating_enforced: true`.
- `/api/auth/*` and `/api/health` never consume quota (auth/infra
  endpoints must stay reachable to log in and upgrade).
- Counters are in-process per UTC day (like slowapi's default memory
  storage): per worker. Swap in a shared store when the paywall ships.

Kill-switch for test/CI suites: `FISHINTEL_ENFORCE_QUOTAS=0` (read per
request so tests can toggle it; production default is on). The paywall has its
own switch: `FISHINTEL_ENFORCE_ROUTE_GATING=0`.
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


def gating_enabled() -> bool:
    """Premium route gating unless FISHINTEL_ENFORCE_ROUTE_GATING disables it."""
    return os.environ.get("FISHINTEL_ENFORCE_ROUTE_GATING", "1").lower() not in (
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
        # NOTE: the two enforcement layers have INDEPENDENT switches. Gating must
        # not be nested inside the quota switch — a suite-wide
        # FISHINTEL_ENFORCE_QUOTAS=0 would otherwise silently disable the paywall
        # (found by tests/test_entitlements.py).
        if request.method == "OPTIONS":
            return await call_next(request)  # CORS preflight

        path = request.url.path
        # Auth/infra/billing endpoints never consume quota and are never gated —
        # users must always be able to log in, check status, and upgrade.
        if path.startswith(("/api/auth/", "/api/health", "/api/billing/")):
            return await call_next(request)

        has_bearer = request.headers.get("Authorization", "").startswith("Bearer ")
        has_api_key = bool(
            request.headers.get("X-API-Key") or request.query_params.get("api_key")
        )
        if not (has_bearer or has_api_key):
            return await call_next(request)  # anonymous: ungated public browsing

        payload = await _resolve_user(request)
        if payload is None:
            return await call_next(request)  # bad credentials: route decides

        from core.entitlements import get_plan, route_allowed, upgrade_hint

        # 1) Premium route gating — authenticated accounts only (docstring).
        if gating_enabled() and not route_allowed(payload.tier, path):
            return JSONResponse(
                status_code=402,
                content=upgrade_hint(
                    payload.tier,
                    error="plan_upgrade_required",
                    reason=(
                        f"'{path}' is a premium output that your plan does not "
                        "include. Upgrade to unlock it."
                    ),
                    path=path,
                ),
            )

        # 2) Daily quota — from the single entitlements table (own switch).
        if not quotas_enabled():
            return await call_next(request)

        plan = get_plan(payload.tier)
        quota = plan.api_calls_per_day
        if quota <= 0:
            return await call_next(request)  # unlimited plan

        key = (f"{payload.user_id}:{plan.key}", _utc_day())
        with _lock:
            used = _counts.get(key, 0) + 1
            _counts[key] = used
            if len(_counts) > _MAX_TRACKED_KEYS:
                day = key[1]
                for stale in [k for k in _counts if k[1] != day]:
                    del _counts[stale]

        if used > quota:
            hint = upgrade_hint(
                plan.key,
                error="tier_quota_exceeded",
                reason=(
                    f"Daily API quota reached for plan '{plan.key}' "
                    f"({used - 1}/{quota} calls today, UTC). Upgrade for a higher quota."
                ),
            )
            hint.update({"quota_per_day": quota, "used_today": used - 1})
            return JSONResponse(
                status_code=429,
                content=hint,
                headers={"Retry-After": str(_seconds_until_utc_midnight())},
            )

        return await call_next(request)
