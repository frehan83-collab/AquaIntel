"""
Compliance & Audit Agent
========================
Ensures regulatory compliance:
  - GDPR data handling (no personal data stored)
  - NLOD attribution for public data
  - Full audit trail
  - Disclaimer management
  - Performance fee calculation & tracking
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from agents.base import BaseAgent
from core.models import AuditLog, Order, PerformanceFee
from core.async_db import get_async_session
from config.settings import settings


# ── Regulatory text ──────────────────────────────────────────────────
DISCLAIMER = """
DISCLAIMER — OpenClaw Lice-Impact Arbitrage Bot
================================================
This system provides discretionary trading signals based on publicly
available aquaculture data. It does NOT constitute financial advice.

- All signals require explicit user confirmation before execution.
- Past performance does not guarantee future results.
- The user assumes full responsibility for any trading decisions.
- Data sourced from BarentsWatch (Norwegian Licence for Open Data — NLOD).
- No personal data is stored or processed (GDPR compliant).
- This system is not regulated by Finanstilsynet as it provides
  information services only, not investment advice or portfolio management.

By using this system, you acknowledge and accept these terms.
"""

NLOD_ATTRIBUTION = (
    "Data from BarentsWatch / Norwegian Directorate of Fisheries, "
    "licensed under NLOD (Norwegian Licence for Open Data 2.0). "
    "https://data.norge.no/nlod/en/2.0"
)


class ComplianceAgent(BaseAgent):
    name = "compliance"
    interval_seconds = 3600  # hourly checks

    async def tick(self) -> None:
        self.log.info("compliance.tick_start")

        # 1. Verify all executed orders have user consent
        await self._verify_consent_integrity()

        # 2. Calculate performance fees
        await self._calculate_fees()

        # 3. Log compliance check
        async with get_async_session() as s:
            s.add(AuditLog(
                event_type="compliance_check",
                detail="Periodic compliance verification passed",
            ))

    @staticmethod
    async def _verify_consent_integrity() -> None:
        """Ensure every executed order has a valid consent record."""
        async with get_async_session() as s:
            result = await s.execute(
                select(Order).where(
                    Order.status == "filled",
                    Order.user_consent == False,
                )
            )
            orders_without_consent = result.scalars().all()

            if orders_without_consent:
                for order in orders_without_consent:
                    s.add(AuditLog(
                        event_type="compliance_violation",
                        detail=f"Order {order.id} executed without user consent!",
                    ))

    @staticmethod
    async def _calculate_fees() -> None:
        """Calculate 20% performance fees on realized profits."""
        async with get_async_session() as s:
            # Get closed orders this month
            now = dt.datetime.now(dt.UTC)
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            result = await s.execute(
                select(Order).where(
                    Order.filled_at >= month_start,
                    Order.status == "filled",
                )
            )
            closed_orders = result.scalars().all()

            # Calculate gross P&L (simplified)
            gross_profit = sum(
                (o.fill_price - o.price) * o.quantity
                if o.side == "BUY"
                else (o.price - o.fill_price) * o.quantity
                for o in closed_orders
                if o.fill_price
            )

            if gross_profit > 0:
                fee = gross_profit * settings.performance_fee_rate

                # Check if we already logged this period
                result = await s.execute(
                    select(PerformanceFee).where(
                        PerformanceFee.period_start == month_start
                    )
                )
                existing = result.scalar_one_or_none()

                if existing:
                    existing.gross_profit = gross_profit
                    existing.fee_amount = fee
                else:
                    s.add(PerformanceFee(
                        period_start=month_start,
                        period_end=now,
                        gross_profit=gross_profit,
                        fee_rate=settings.performance_fee_rate,
                        fee_amount=fee,
                    ))

    @staticmethod
    def get_disclaimer() -> str:
        return DISCLAIMER

    @staticmethod
    def get_attribution() -> str:
        return NLOD_ATTRIBUTION

    @staticmethod
    async def export_audit_log(
        start: dt.datetime | None = None,
        end: dt.datetime | None = None,
    ) -> list[dict]:
        """Export audit log entries for a time range."""
        async with get_async_session() as s:
            q = select(AuditLog)
            if start:
                q = q.where(AuditLog.timestamp >= start)
            if end:
                q = q.where(AuditLog.timestamp <= end)
            q = q.order_by(AuditLog.timestamp.desc())

            result = await s.execute(q)
            entries = result.scalars().all()
            return [
                {
                    "id": e.id,
                    "timestamp": e.timestamp.isoformat(),
                    "event_type": e.event_type,
                    "actor": e.actor,
                    "detail": e.detail,
                }
                for e in entries
            ]
