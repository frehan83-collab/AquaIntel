"""
Webhook Configuration Routes
==============================
CRUD endpoints for managing external webhook integrations (Slack, Teams, generic).
Users can subscribe webhooks to specific event types and test delivery.
"""
from __future__ import annotations

import json
import datetime as dt

from fastapi import APIRouter, HTTPException, Request, Depends
from sqlalchemy import select, delete

from core.auth import get_current_user, TokenPayload

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


def _require_auth(user: TokenPayload | None = Depends(get_current_user)):
    """Require authenticated user for webhook management."""
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user

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


@router.get("/events")
async def list_event_types():
    """List all available webhook event types."""
    return {"events": WEBHOOK_EVENT_TYPES}


@router.get("")
async def list_webhooks(user: TokenPayload = Depends(_require_auth)):
    """List webhooks owned by the current user."""
    from core.async_db import get_async_session
    from core.models import WebhookConfig

    async with get_async_session() as s:
        result = await s.execute(
            select(WebhookConfig)
            .where(WebhookConfig.user_id == user.user_id)
            .order_by(WebhookConfig.created_at.desc())
        )
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
async def create_webhook(request: Request, user: TokenPayload = Depends(_require_auth)):
    """Create a new webhook configuration. user_id derived from JWT (never from body)."""
    from core.async_db import get_async_session
    from core.models import WebhookConfig

    data = await request.json()
    url = data.get("url", "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="url is required")
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="url must start with http:// or https://")

    name = data.get("name", "").strip() or "Unnamed Webhook"
    webhook_type = data.get("webhook_type", "generic")
    if webhook_type not in ("generic", "slack", "teams"):
        raise HTTPException(status_code=400, detail="webhook_type must be generic, slack, or teams")

    events = data.get("events", [])
    valid_ids = {e["id"] for e in WEBHOOK_EVENT_TYPES}
    for ev in events:
        if ev not in valid_ids:
            raise HTTPException(status_code=400, detail=f"Unknown event type: {ev}")

    async with get_async_session() as s:
        hook = WebhookConfig(
            name=name,
            url=url,
            webhook_type=webhook_type,
            events=json.dumps(events),
            is_active=True,
            user_id=user.user_id,  # From JWT, never from request body
        )
        s.add(hook)
        await s.flush()

        # Audit: webhook created
        from core.audit import log_action, get_client_ip
        await log_action(
            user.user_id, "create_webhook",
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
async def delete_webhook(webhook_id: int, request: Request, user: TokenPayload = Depends(_require_auth)):
    """Delete a webhook configuration. Only the owner can delete."""
    from core.async_db import get_async_session
    from core.models import WebhookConfig

    async with get_async_session() as s:
        hook = (await s.execute(
            select(WebhookConfig).where(WebhookConfig.id == webhook_id)
        )).scalar()
        if not hook:
            raise HTTPException(status_code=404, detail="Webhook not found")
        if hook.user_id != user.user_id:
            raise HTTPException(status_code=403, detail="Not your webhook")
        hook_name = hook.name
        hook_user = hook.user_id
        await s.delete(hook)

    # Audit: webhook deleted
    from core.audit import log_action, get_client_ip
    await log_action(
        hook_user, "delete_webhook",
        f"webhook:{webhook_id}",
        details={"name": hook_name},
        ip=get_client_ip(request),
    )

    return {"status": "deleted", "id": webhook_id}


@router.post("/{webhook_id}/test")
async def test_webhook(webhook_id: int, user: TokenPayload = Depends(_require_auth)):
    """Send a test payload to a webhook URL."""
    from core.async_db import get_async_session
    from core.models import WebhookConfig

    async with get_async_session() as s:
        hook = (await s.execute(
            select(WebhookConfig).where(WebhookConfig.id == webhook_id)
        )).scalar()
        if not hook:
            raise HTTPException(status_code=404, detail="Webhook not found")

        # Build test payload
        from core.market.webhook_dispatcher import webhook_dispatcher
        test_payload = {
            "event": "test",
            "title": "FishIntel Webhook Test",
            "message": "This is a test message from FishIntel. If you see this, your webhook is working correctly.",
            "severity": "info",
            "timestamp": dt.datetime.now(dt.UTC).isoformat(),
            "source": "FishIntel Aquaculture Intelligence",
        }

        success, detail = await webhook_dispatcher.send_to_webhook(hook, test_payload)
        if success:
            return {"status": "success", "message": "Test payload delivered successfully"}
        else:
            return {"status": "failed", "message": f"Delivery failed: {detail}"}
