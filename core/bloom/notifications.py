"""
Bloom alert notification dispatch.

Sends SMS (Twilio) and email (SMTP) alerts to fish farmers when bloom
risk crosses thresholds. Includes deduplication to avoid alert fatigue.

Escalation policy:
  CRITICAL → SMS + email
  HIGH     → email only
  ELEVATED → dashboard only (no push notification)
  LOW      → no alert
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

import structlog
from sqlalchemy import select, and_

from config.settings import settings
from core.async_db import get_async_session
from core.bloom.models import BloomAlert

log = structlog.get_logger(__name__)

ESCALATION = {
    "CRITICAL": ["sms", "email"],
    "HIGH": ["email"],
    "ELEVATED": ["dashboard"],
    "LOW": [],
}


async def send_bloom_alert(
    locality_no: int,
    locality_name: str,
    risk_level: str,
    risk_score: float,
    chl_a: float,
    user_id: Optional[int] = None,
    cooldown_hours: int = 24,
) -> list[BloomAlert]:
    """
    Send bloom alerts through appropriate channels based on risk level.

    Returns list of BloomAlert records created (may be empty if deduplicated).
    """
    channels = ESCALATION.get(risk_level, [])
    if not channels:
        return []

    # Deduplication: check if same locality + risk level was alerted recently
    cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(hours=cooldown_hours)
    async with get_async_session() as session:
        result = await session.execute(
            select(BloomAlert).where(
                and_(
                    BloomAlert.locality_no == locality_no,
                    BloomAlert.risk_level == risk_level,
                    BloomAlert.sent_at >= cutoff,
                )
            )
        )
        existing = result.scalars().first()

        if existing:
            log.debug(
                "bloom.alert_deduplicated",
                locality_no=locality_no,
                risk_level=risk_level,
                last_alert=existing.sent_at.isoformat(),
            )
            return []

    alerts: list[BloomAlert] = []
    message = _format_message(locality_name, locality_no, risk_level, risk_score, chl_a)

    for channel in channels:
        status = "sent"
        try:
            if channel == "sms":
                await _send_sms(message)
            elif channel == "email":
                await _send_email(locality_name, risk_level, message)
            # "dashboard" channel requires no push — just stored in DB
        except Exception as exc:
            log.error("bloom.alert_send_failed", channel=channel, error=str(exc))
            status = "failed"

        alert = BloomAlert(
            locality_no=locality_no,
            user_id=user_id,
            risk_level=risk_level,
            sent_at=dt.datetime.now(dt.UTC),
            channel=channel,
            delivery_status=status,
            message_text=message,
        )
        alerts.append(alert)

    # Persist alert records
    async with get_async_session() as session:
        session.add_all(alerts)
        log.info(
            "bloom.alerts_sent",
            locality_no=locality_no,
            risk_level=risk_level,
            channels=[a.channel for a in alerts],
        )

    return alerts


def _format_message(
    name: str, locality_no: int, risk_level: str, score: float, chl_a: float
) -> str:
    emoji = {"CRITICAL": "!!!", "HIGH": "!!", "ELEVATED": "!"}.get(risk_level, "")
    return (
        f"BLOOM ALERT {emoji}\n"
        f"Locality: {name} ({locality_no})\n"
        f"Risk: {risk_level} (score {score:.0f}/100)\n"
        f"Chl-a: {chl_a:.1f} mg/m3\n"
        f"Check dashboard for details and recommended actions."
    )


async def _send_sms(message: str) -> None:
    """Send SMS via Twilio."""
    if not settings.twilio_sid:
        log.warning("bloom.twilio_not_configured")
        return

    from twilio.rest import Client

    client = Client(settings.twilio_sid, settings.twilio_token)
    client.messages.create(
        body=message,
        from_=settings.twilio_from,
        to=settings.twilio_to,
    )
    log.info("bloom.sms_sent")


async def _send_email(locality_name: str, risk_level: str, body: str) -> None:
    """Send email via SMTP."""
    if not settings.smtp_user:
        log.warning("bloom.smtp_not_configured")
        return

    import aiosmtplib
    from email.message import EmailMessage

    msg = EmailMessage()
    msg["Subject"] = f"Bloom Alert [{risk_level}] — {locality_name}"
    msg["From"] = settings.smtp_user
    msg["To"] = settings.alert_email_to or settings.smtp_user
    msg.set_content(body)

    await aiosmtplib.send(
        msg,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user,
        password=settings.smtp_password,
        start_tls=True,
    )
    log.info("bloom.email_sent", to=msg["To"])
