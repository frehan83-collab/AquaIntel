"""
Execution Layer Agent
=====================
Converts confirmed signals into orders. NEVER executes live orders
without explicit user consent. Supports paper and live broker modes.

Consent flow:
  1. Signal generated -> stored with status="pending"
  2. Dashboard shows signal, user clicks "Confirm"
  3. Signal.confirmed_by_user = True, consent_timestamp set
  4. This agent picks it up and places the order
  5. Full audit trail logged
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from agents.base import BaseAgent
from core.models import Signal, Order, AuditLog
from core.async_db import get_async_session
from config.settings import settings
from execution.paper_broker import PaperBroker

import structlog

log = structlog.get_logger(__name__)


class ExecutionAgent(BaseAgent):
    name = "execution"
    interval_seconds = 30  # check for confirmed signals frequently

    def __init__(self) -> None:
        super().__init__()
        self.paper_broker = PaperBroker()

    async def tick(self) -> None:
        """Process any user-confirmed signals."""
        async with get_async_session() as s:
            # Only process signals that the user has EXPLICITLY confirmed
            result = await s.execute(
                select(Signal).where(
                    Signal.status == "pending",
                    Signal.confirmed_by_user == True,
                )
            )
            confirmed = result.scalars().all()

            for signal in confirmed:
                self._execute_signal(s, signal)

    def _execute_signal(self, session, signal: Signal) -> None:
        """Place an order for a confirmed signal."""
        side = "SELL" if signal.direction == "SHORT" else "BUY"
        quantity = self._calculate_position_size(signal)

        # Fetch real-time market price for the ticker
        price = self._get_live_price(signal.ticker)
        if price <= 0:
            log.error("execution.skipped_no_price", ticker=signal.ticker, signal_id=signal.id)
            return

        if settings.broker_mode == "paper":
            result = self.paper_broker.execute_order(
                ticker=signal.ticker,
                side=side,
                quantity=quantity,
                price=price,
            )
        else:
            # Live broker integration point
            result = {"status": "rejected", "reason": "Live trading not yet enabled"}
            log.warning("execution.live_not_enabled", ticker=signal.ticker)

        # Record the order
        order = Order(
            signal_id=signal.id,
            ticker=signal.ticker,
            side=side,
            quantity=quantity,
            price=price,
            broker=settings.broker_mode,
            status=result.get("status", "error"),
            user_consent=True,
            consent_timestamp=signal.confirmed_at,
        )

        if result["status"] == "filled":
            order.fill_price = price
            order.filled_at = dt.datetime.now(dt.UTC)
            signal.status = "executed"
        else:
            signal.status = "failed"

        session.add(order)
        session.add(AuditLog(
            event_type="order_execution",
            detail=(
                f"{signal.ticker} {side} qty={quantity} price={price} "
                f"broker={settings.broker_mode} status={result['status']} "
                f"user_consent=True consent_at={signal.confirmed_at}"
            ),
        ))

        self.log.info(
            "execution.order",
            ticker=signal.ticker,
            side=side,
            quantity=quantity,
            status=result["status"],
        )

    @staticmethod
    def _calculate_position_size(signal: Signal) -> int:
        """Position sizing based on signal strength. Conservative."""
        base_size = 100  # shares
        strength_multiplier = signal.strength or 0.5
        return max(10, int(base_size * strength_multiplier))

    @staticmethod
    def _get_live_price(ticker: str) -> float:
        """Fetch real-time price for a ticker from Yahoo Finance / SSB."""
        import asyncio
        try:
            from core.market.salmon_price import get_latest_prices
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    prices = pool.submit(asyncio.run, get_latest_prices()).result()
            else:
                prices = asyncio.run(get_latest_prices())

            # Match ticker to price — try exact, then with .OL suffix
            ol_key = f"{ticker}.OL"
            if ticker in prices and prices[ticker]:
                return float(prices[ticker])
            if ol_key in prices and prices[ol_key]:
                return float(prices[ol_key])
            # Fallback: SSB spot price
            ssb = prices.get("SSB_NOK")
            if ssb and ssb > 0:
                return float(ssb)
        except Exception as exc:
            log.warning("execution.price_fetch_failed", ticker=ticker, error=str(exc)[:120])

        # If everything fails, refuse to trade at unknown price
        log.error("execution.no_live_price", ticker=ticker)
        return 0.0  # caller should check and skip order if 0

    @staticmethod
    async def confirm_signal(signal_id: int) -> bool:
        """Called by the dashboard when user clicks 'Confirm'."""
        async with get_async_session() as s:
            result = await s.execute(
                select(Signal).where(Signal.id == signal_id)
            )
            signal = result.scalar_one_or_none()
            if not signal or signal.status != "pending":
                return False

            signal.confirmed_by_user = True
            signal.confirmed_at = dt.datetime.now(dt.UTC)

            s.add(AuditLog(
                event_type="user_consent",
                detail=f"Signal {signal_id} ({signal.ticker} {signal.direction}) "
                       f"confirmed by user at {signal.confirmed_at}",
            ))
            log.info("execution.signal_confirmed", signal_id=signal_id)
            return True

    @staticmethod
    async def reject_signal(signal_id: int) -> bool:
        """Called by the dashboard when user clicks 'Reject'."""
        async with get_async_session() as s:
            result = await s.execute(
                select(Signal).where(Signal.id == signal_id)
            )
            signal = result.scalar_one_or_none()
            if not signal or signal.status != "pending":
                return False

            signal.status = "expired"
            s.add(AuditLog(
                event_type="user_rejection",
                detail=f"Signal {signal_id} ({signal.ticker} {signal.direction}) "
                       f"rejected by user",
            ))
            return True
