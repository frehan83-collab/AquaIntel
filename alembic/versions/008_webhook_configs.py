"""Add webhook_configs table for external alert delivery.

Supports Slack, Teams, and generic webhook integrations
with event-based subscriptions and automatic failure tracking.

Revision ID: 008
Revises: 007
Create Date: 2026-04-04
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "webhook_configs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("name", sa.String(100)),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("webhook_type", sa.String(20), server_default="generic"),
        sa.Column("events", sa.Text),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("TRUE")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("last_triggered", sa.DateTime, nullable=True),
        sa.Column("failure_count", sa.Integer, server_default=sa.text("0")),
    )
    op.create_index("ix_webhook_configs_user_id", "webhook_configs", ["user_id"])
    op.create_index("ix_webhook_configs_is_active", "webhook_configs", ["is_active"])


def downgrade() -> None:
    op.drop_index("ix_webhook_configs_is_active", "webhook_configs")
    op.drop_index("ix_webhook_configs_user_id", "webhook_configs")
    op.drop_table("webhook_configs")
