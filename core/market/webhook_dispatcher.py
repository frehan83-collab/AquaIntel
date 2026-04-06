"""
Webhook Dispatcher Engine
===========================
Dispatches alert payloads to all active webhooks matching the event type.
Formats payloads for Slack (blocks), Teams (adaptive card), and generic (JSON).
Auto-disables webhooks after 5 consecutive failures.
"""
from __future__ import annotations

import json
import datetime as dt
from typing import Any

import httpx
import structlog

log = structlog.get_logger(__name__)

MAX_FAILURES = 5
TIMEOUT_SECONDS = 5.0


class WebhookDispatcher:
    """Dispatches alerts to configured webhooks with type-specific formatting."""

    def _format_slack(self, payload: dict[str, Any]) -> dict:
        """Format payload as Slack Block Kit message."""
        severity = payload.get("severity", "info")
        emoji = {"critical": ":red_circle:", "high": ":orange_circle:", "warning": ":large_yellow_circle:", "info": ":large_blue_circle:"}.get(severity, ":white_circle:")

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"{emoji} {payload.get('title', 'FishIntel Alert')}"},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": payload.get("message", "")},
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"*Severity:* {severity} | *Event:* {payload.get('event', 'unknown')} | *Time:* {payload.get('timestamp', '')}"},
                ],
            },
        ]

        # Add metric value if present
        if payload.get("metric_value") is not None:
            blocks.insert(2, {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Current Value:* {payload['metric_value']}"},
                    {"type": "mrkdwn", "text": f"*Threshold:* {payload.get('threshold', 'N/A')}"},
                ],
            })

        return {"blocks": blocks, "text": payload.get("title", "FishIntel Alert")}

    def _format_teams(self, payload: dict[str, Any]) -> dict:
        """Format payload as Microsoft Teams Adaptive Card."""
        severity = payload.get("severity", "info")
        color_map = {"critical": "attention", "high": "warning", "warning": "warning", "info": "accent"}
        color = color_map.get(severity, "default")

        card = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard",
                        "version": "1.4",
                        "body": [
                            {
                                "type": "TextBlock",
                                "text": payload.get("title", "FishIntel Alert"),
                                "weight": "bolder",
                                "size": "large",
                                "color": color,
                            },
                            {
                                "type": "TextBlock",
                                "text": payload.get("message", ""),
                                "wrap": True,
                            },
                            {
                                "type": "FactSet",
                                "facts": [
                                    {"title": "Severity", "value": severity.upper()},
                                    {"title": "Event", "value": payload.get("event", "unknown")},
                                    {"title": "Time", "value": payload.get("timestamp", "")},
                                ],
                            },
                        ],
                    },
                }
            ],
        }

        if payload.get("metric_value") is not None:
            card["attachments"][0]["content"]["body"][2]["facts"].extend([
                {"title": "Value", "value": str(payload["metric_value"])},
                {"title": "Threshold", "value": str(payload.get("threshold", "N/A"))},
            ])

        return card

    def _format_generic(self, payload: dict[str, Any]) -> dict:
        """Format as plain JSON payload."""
        return {
            "source": "FishIntel",
            "event": payload.get("event", "unknown"),
            "title": payload.get("title", ""),
            "message": payload.get("message", ""),
            "severity": payload.get("severity", "info"),
            "timestamp": payload.get("timestamp", dt.datetime.now(dt.UTC).isoformat()),
            "data": {
                "metric_value": payload.get("metric_value"),
                "threshold": payload.get("threshold"),
                "category": payload.get("category"),
            },
        }

    async def send_to_webhook(self, hook: Any, payload: dict[str, Any]) -> tuple[bool, str]:
        """Send a formatted payload to a single webhook. Returns (success, detail)."""
        try:
            if hook.webhook_type == "slack":
                body = self._format_slack(payload)
            elif hook.webhook_type == "teams":
                body = self._format_teams(payload)
            else:
                body = self._format_generic(payload)

            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                resp = await client.post(
                    hook.url,
                    json=body,
                    headers={"Content-Type": "application/json", "User-Agent": "FishIntel-Webhook/1.0"},
                )

            if resp.status_code < 300:
                # Reset failure count on success
                hook.failure_count = 0
                hook.last_triggered = dt.datetime.now(dt.UTC)
                log.info("webhook_delivered", webhook_id=hook.id, name=hook.name, status=resp.status_code)
                return True, f"HTTP {resp.status_code}"
            else:
                hook.failure_count = (hook.failure_count or 0) + 1
                if hook.failure_count >= MAX_FAILURES:
                    hook.is_active = False
                    log.warning("webhook_auto_disabled", webhook_id=hook.id, name=hook.name, failures=hook.failure_count)
                log.warning("webhook_delivery_failed", webhook_id=hook.id, status=resp.status_code, body=resp.text[:200])
                return False, f"HTTP {resp.status_code}: {resp.text[:200]}"

        except httpx.TimeoutException:
            hook.failure_count = (hook.failure_count or 0) + 1
            if hook.failure_count >= MAX_FAILURES:
                hook.is_active = False
            log.warning("webhook_timeout", webhook_id=hook.id, name=hook.name)
            return False, "Request timed out"
        except Exception as exc:
            hook.failure_count = (hook.failure_count or 0) + 1
            if hook.failure_count >= MAX_FAILURES:
                hook.is_active = False
            log.error("webhook_error", webhook_id=hook.id, error=str(exc))
            return False, str(exc)

    async def dispatch_alert(self, event_type: str, payload: dict[str, Any]) -> dict:
        """
        Send alert to all active webhooks subscribed to this event type.
        Returns summary of delivery results.
        """
        from core.async_db import get_async_session
        from core.models import WebhookConfig
        from sqlalchemy import select

        results = {"sent": 0, "failed": 0, "skipped": 0, "details": []}

        async with get_async_session() as s:
            hooks = (await s.execute(
                select(WebhookConfig).where(WebhookConfig.is_active == True)  # noqa: E712
            )).scalars().all()

            for hook in hooks:
                # Check if this hook subscribes to this event type
                subscribed_events = json.loads(hook.events) if hook.events else []
                if event_type not in subscribed_events:
                    results["skipped"] += 1
                    continue

                payload["event"] = event_type
                success, detail = await self.send_to_webhook(hook, payload)
                if success:
                    results["sent"] += 1
                else:
                    results["failed"] += 1
                results["details"].append({
                    "webhook_id": hook.id,
                    "name": hook.name,
                    "success": success,
                    "detail": detail,
                })

        log.info("webhook_dispatch_complete", event=event_type, **{k: v for k, v in results.items() if k != "details"})
        return results


# Singleton
webhook_dispatcher = WebhookDispatcher()
