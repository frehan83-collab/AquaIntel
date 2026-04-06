"""
Audit Logging Utility
======================
Lightweight, fire-and-forget audit trail for user actions.
Never blocks or breaks the main request flow.
"""
from __future__ import annotations

import json
import datetime as dt
from typing import Any

import structlog

log = structlog.get_logger(__name__)


async def log_action(
    user_id: int | None,
    action: str,
    resource: str | None = None,
    details: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    """Insert an audit log entry. Fire-and-forget — exceptions are caught and logged.

    Args:
        user_id: ID of the acting user (None for anonymous/system actions)
        action: Short verb, e.g. "login", "create_webhook", "export"
        resource: What was acted on, e.g. "webhook:5", "api_key:oc_live_"
        details: Optional JSON-serialisable dict with extra context
        ip: Client IP address
    """
    try:
        from core.async_db import get_async_session
        from core.models import AuditLog

        details_str = json.dumps(details, default=str) if details else None

        async with get_async_session() as s:
            entry = AuditLog(
                user_id=user_id,
                action=action,
                resource=resource,
                details=details_str,
                ip_address=ip,
                timestamp=dt.datetime.now(dt.UTC),
            )
            s.add(entry)
            # Session auto-commits via context manager
    except Exception:
        # Never let audit logging break the main flow
        log.warning("audit_log_failed", action=action, user_id=user_id, exc_info=True)


def get_client_ip(request) -> str | None:
    """Extract client IP from a FastAPI Request, respecting X-Forwarded-For."""
    try:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client:
            return request.client.host
    except Exception:
        pass
    return None
