"""Add indexes on Signal, Order, and Subscription for query performance.

- Signal.ticker: filtered in signal listing and trading views
- Order.ticker, Order.signal_id, Order.created_at: filtered in order history
- Subscription.user_id: filtered for per-user subscription lookup

Revision ID: 014
Revises: 013
Create Date: 2026-04-11
"""
from __future__ import annotations

from alembic import op

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_signals_ticker", "signals", ["ticker"])
    op.create_index("ix_orders_ticker", "orders", ["ticker"])
    op.create_index("ix_orders_signal_id", "orders", ["signal_id"])
    op.create_index("ix_orders_created_at", "orders", ["created_at"])
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_subscriptions_user_id", table_name="subscriptions")
    op.drop_index("ix_orders_created_at", table_name="orders")
    op.drop_index("ix_orders_signal_id", table_name="orders")
    op.drop_index("ix_orders_ticker", table_name="orders")
    op.drop_index("ix_signals_ticker", table_name="signals")
