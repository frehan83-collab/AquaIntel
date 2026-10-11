"""
Webhook Configuration Routes
==============================
CRUD endpoints for managing external webhook integrations (Slack, Teams, generic).
Users can subscribe webhooks to specific event types and test delivery.

Security model (Session 38 CRITICAL #2):
- Read/list, create, delete, and test all require authentication.
- Ownership: non-admin users only see/mutate their own webhooks; user_id is
  taken from the verified token, never from the request body (IDOR fix).
  Hooks with a NULL owner (legacy rows) are admin-only.
- SSRF: destination URLs pass core.security.validate_public_url (DNS-
  resolving) at creation and again immediately before dispatch.
- GET /events is public (static catalogue, no user data).
"""
from __future__ import annotations

import json
import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, delete

from core.auth import get_current_user, is_admin, TokenPayload
from core.security import validate_public_url

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

# Available event types that can trigger webhooks
WEBHOOK_EVENT_TYPES = [
    {"id": "lice_alert", "label": "Lice Threshold Alert", "description": "Triggered when lice counts exceed configured thresholds"},
    {"id": "price_alert", "label": "Price Movement Alert", "description": "Triggered on significant salmon price changes"},
    {"id": "disease_alert", "label": "Disease Outbreak Alert", "description": "Triggered on new ISA/PD disease notifications"},
    {"id": "temperature_alert", "label": "Sea Temperature Alert", "description": "Triggered when SST exceeds safe thresholds"},
    {"id": "supply_alert", "label": "Supply Disruption Alert", "description": "Triggered on supply chain disruption events"},
    {"id": "treatment_due", "label": "Treatment Due Reminder", "description": "Triggered when scheduled treatment is approaching"},
    {"id": "bloom_alert", "label": "Algal Bloom Alert", "description": "Triggered on elevated chlorophyll/bloom risk"},
]

# SSRF guard lives in core.security (DNS-resolving); thin HTTP wrapper here.
async def validate_webhook_url(url: str) -> str:
    """Validate an outbound webhook URL (400 on internal/unresolvable targets)."""
    try:
        await validate_public_url(url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return url


async def _require_user(user: TokenPayload | None) -> TokenPayload:
    """401 when no valid credential was presented."""
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


@router.get("/events")
async def list_event_types():
    """List all available webhook event types (public static catalogue)."""
    return {"events": WEBHOOK_EVENT_TYPES}


@router.get("")
async def list_webhooks(user: TokenPayload = Depends(get_current_user)):
    """List configured webhooks visible to the caller (own only, unless admin)."""
    user = await _require_user(user)
    from core.async_db import get_async_session
    from core.models import WebhookConfig

    async with get_async_session() as s:
        stmt = select(WebhookConfig).order_by(WebhookConfig.created_at.desc())
        if not await is_admin(user):
            # Own hooks only — legacy NULL-owner rows are admin-visible only
            stmt = stmt.where(WebhookConfig.user_id == user.user_id)
        result = await s.execute(stmt)
        hooks = result.scalars().all()
        return {
            "webhooks": [
                {
                    "id": h.id,
                    "name": h.name,
                    "url": h.url,
                    "webhook_type": h.webhook_type,
                    "events": json.loads(h.events) if h.events else [],
                    "is_active": h.is_active,
                    "created_at": h.created_at.isoformat() if h.created_at else None,
                    "last_triggered": h.last_triggered.isoformat() if h.last_triggered else None,
                    "failure_count": h.failure_count,
                }
                for h in hooks
            ],
            "total": len(hooks),
        }


@router.post("")
async def create_webhook(request: Request, user: TokenPayload = Depends(get_current_user)):
    """Create a new webhook configuration (authenticated; owner = token user)."""
    user = await _require_user(user)
    from core.async_db import get_async_session
    from core.models import WebhookConfig

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="request body must be valid JSON")
    url = data.get("url", "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="url is required")
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="url must start with http:// or https://")
    await validate_webhook_url(url)

    name = data.get("name", "").strip() or "Unnamed Webhook"
    webhook_type = data.get("webhook_type", "generic")
    if webhook_type not in ("generic", "slack", "teams"):
        raise HTTPException(status_code=400, detail="webhook_type must be generic, slack, or teams")

    events = data.get("events", [])
    valid_ids = {e["id"] for e in WEBHOOK_EVENT_TYPES}
    for ev in events:
        if ev not in valid_ids:
            raise HTTPException(status_code=400, detail=f"Unknown event type: {ev}")

    owner_id = user.user_id  # from verified token — never from the body (IDOR fix)
    async with get_async_session() as s:
        hook = WebhookConfig(
            name=name,
            url=url,
            webhook_type=webhook_type,
            events=json.dumps(events),
            is_active=True,
            user_id=owner_id,
        )
        s.add(hook)
        await s.flush()

        # Audit: webhook created
        from core.audit import log_action, get_client_ip
        await log_action(
            owner_id, "create_webhook",
            f"webhook:{hook.id}",
            details={"name": name, "type": webhook_type, "events": events},
            ip=get_client_ip(request),
        )

        return {
            "status": "created",
            "webhook": {
                "id": hook.id,
                "name": hook.name,
                "url": hook.url,
                "webhook_type": hook.webhook_type,
                "events": events,
                "is_active": True,
            },
        }


@router.delete("/{webhook_id}")
async def delete_webhook(webhook_id: int, request: Request, user: TokenPayload = Depends(get_current_user)):
    """Delete a webhook configuration (authenticated; ownership enforced)."""
    user = await _require_user(user)
    from core.audit import log_action, get_client_ip
    from core.async_db import get_async_session
    from core.models import WebhookConfig

    admin = await is_admin(user)
    async with get_async_session() as s:
        hook = (await s.execute(
            select(WebhookConfig).where(WebhookConfig.id == webhook_id)
        )).scalar()
        if not hook:
            raise HTTPException(status_code=404, detail="Webhook not found")
        if hook.user_id != user.user_id and not admin:
            # NULL-owner (legacy) hooks are admin-only as well
            raise HTTPException(status_code=403, detail="Not your webhook")
        hook_name = hook.name
        hook_user = hook.user_id
        await s.delete(hook)
        await s.flush()

    # Audit: webhook deleted
    await log_action(
        hook_user, "delete_webhook",
        f"webhook:{webhook_id}",
        details={"name": hook_name},
        ip=get_client_ip(request),
    )

    return {"status": "deleted", "id": webhook_id}


@router.post("/{webhook_id}/test")
async def test_webhook(webhook_id: int, user: TokenPayload = Depends(get_current_user)):
    """Send a test payload to a webhook URL (authenticated; ownership enforced)."""
    user = await _require_user(user)
    from core.async_db import get_async_session
    from core.models import WebhookConfig

    admin = await is_admin(user)
    # Session stays open during dispatch: the dispatcher updates
    # failure_count/last_triggered/is_active on the row, and the session
    # context manager commits those writes on exit.
    async with get_async_session() as s:
        hook = (await s.execute(
            select(WebhookConfig).where(WebhookConfig.id == webhook_id)
        )).scalar()
        if not hook:
            raise HTTPException(status_code=404, detail="Webhook not found")
        if hook.user_id != user.user_id and not admin:
            raise HTTPException(status_code=403, detail="Not your webhook")

        # Re-validate destination at dispatch time (DNS may have changed since creation)
        await validate_webhook_url(hook.url)

        test_payload = {
            "event": "test",
            "title": "FishIntel Webhook Test",
            "message": "This is a test message from FishIntel. If you see this, your webhook is working correctly.",
            "severity": "info",
            "timestamp": dt.datetime.now(dt.UTC).isoformat(),
            "source": "FishIntel Aquaculture Intelligence",
        }

        from core.market.webhook_dispatcher import webhook_dispatcher
        success, detail = await webhook_dispatcher.send_to_webhook(hook, test_payload)

    if success:
        return {"status": "success", "message": "Test payload delivered successfully"}
    else:
        return {"status": "failed", "message": f"Delivery failed: {detail}"}
