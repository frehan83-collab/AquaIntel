"""Add Stripe billing columns to users and subscriptions.

Revision ID: 002
Revises: 001
Create Date: 2026-03-31
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users: add stripe_customer_id
    op.add_column("users", sa.Column("stripe_customer_id", sa.String(128)))

    # Subscriptions: add Stripe fields
    op.add_column("subscriptions", sa.Column("stripe_customer_id", sa.String(128)))
    op.add_column("subscriptions", sa.Column("stripe_subscription_id", sa.String(128)))
    op.add_column("subscriptions", sa.Column("stripe_price_id", sa.String(128)))
    op.add_column("subscriptions", sa.Column("cancel_at_period_end", sa.Boolean, server_default="false"))
    op.add_column("subscriptions", sa.Column("current_period_end", sa.DateTime))


def downgrade() -> None:
    op.drop_column("subscriptions", "current_period_end")
    op.drop_column("subscriptions", "cancel_at_period_end")
    op.drop_column("subscriptions", "stripe_price_id")
    op.drop_column("subscriptions", "stripe_subscription_id")
    op.drop_column("subscriptions", "stripe_customer_id")
    op.drop_column("users", "stripe_customer_id")
