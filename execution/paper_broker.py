"""
Paper Trading Broker
====================
Simulates order execution for paper-trading mode.
Maintains a virtual portfolio with P&L tracking.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import structlog

log = structlog.get_logger(__name__)


@dataclass
class PaperPosition:
    ticker: str
    side: str  # LONG / SHORT
    quantity: int
    entry_price: float
    entry_time: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))
    exit_price: float | None = None
    exit_time: dt.datetime | None = None
    pnl: float = 0.0
    is_open: bool = True


class PaperBroker:
    """Simulated broker for paper trading."""

    def __init__(self, initial_capital: float = 1_000_000.0) -> None:
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: list[PaperPosition] = []
        self.trade_log: list[dict] = []

    def execute_order(
        self,
        ticker: str,
        side: str,
        quantity: int,
        price: float,
    ) -> dict:
        """Execute a paper trade."""
        cost = quantity * price

        if side == "BUY":
            if cost > self.cash:
                return {"status": "rejected", "reason": "Insufficient capital"}
            self.cash -= cost
            pos = PaperPosition(
                ticker=ticker, side="LONG", quantity=quantity, entry_price=price
            )
            self.positions.append(pos)
        elif side == "SELL":
            # For short-selling in paper mode, we just track the position
            self.cash += cost
            pos = PaperPosition(
                ticker=ticker, side="SHORT", quantity=quantity, entry_price=price
            )
            self.positions.append(pos)
        else:
            return {"status": "rejected", "reason": f"Unknown side: {side}"}

        trade = {
            "status": "filled",
            "ticker": ticker,
            "side": side,
            "quantity": quantity,
            "price": price,
            "timestamp": dt.datetime.now(dt.UTC).isoformat(),
            "broker": "paper",
        }
        self.trade_log.append(trade)
        log.info("paper_broker.fill", **trade)
        return trade

    def close_position(self, position_idx: int, price: float) -> dict:
        """Close an open position at the given price."""
        if position_idx >= len(self.positions):
            return {"status": "error", "reason": "Invalid position index"}

        pos = self.positions[position_idx]
        if not pos.is_open:
            return {"status": "error", "reason": "Position already closed"}

        if pos.side == "LONG":
            pos.pnl = (price - pos.entry_price) * pos.quantity
            self.cash += price * pos.quantity
        else:  # SHORT
            pos.pnl = (pos.entry_price - price) * pos.quantity
            self.cash -= price * pos.quantity

        pos.exit_price = price
        pos.exit_time = dt.datetime.now(dt.UTC)
        pos.is_open = False

        log.info("paper_broker.close", ticker=pos.ticker, pnl=pos.pnl)
        return {
            "status": "closed",
            "ticker": pos.ticker,
            "pnl": pos.pnl,
            "exit_price": price,
        }

    @property
    def open_positions(self) -> list[PaperPosition]:
        return [p for p in self.positions if p.is_open]

    @property
    def total_pnl(self) -> float:
        return sum(p.pnl for p in self.positions if not p.is_open)

    @property
    def portfolio_value(self) -> float:
        return self.cash + sum(
            p.entry_price * p.quantity for p in self.positions if p.is_open
        )

    def summary(self) -> dict:
        return {
            "initial_capital": self.initial_capital,
            "cash": self.cash,
            "portfolio_value": self.portfolio_value,
            "open_positions": len(self.open_positions),
            "closed_trades": len([p for p in self.positions if not p.is_open]),
            "total_realized_pnl": self.total_pnl,
            "return_pct": (self.portfolio_value - self.initial_capital)
            / self.initial_capital
            * 100,
        }
