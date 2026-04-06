"""Create custom_alert_rules table for user-defined threshold alerts.

Users can define rules like "alert me when lice_avg > 0.5 in PA 3"
with support for 5 metrics, 5 operators, and optional PA filtering.

Revision ID: 010
Revises: 009
Create Date: 2026-04-04
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "custom_alert_rules",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("metric", sa.String(50), nullable=False),
        sa.Column("operator", sa.String(5), nullable=False),
        sa.Column("threshold", sa.Float, nullable=False),
        sa.Column("production_area", sa.Integer, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("TRUE")),
        sa.Column("notify_webhook", sa.Boolean, server_default=sa.text("FALSE")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("last_triggered", sa.DateTime, nullable=True),
        sa.Column("trigger_count", sa.Integer, server_default="0"),
    )
    op.create_index("ix_custom_alert_rules_user_id", "custom_alert_rules", ["user_id"])
    op.create_index("ix_custom_alert_rules_metric", "custom_alert_rules", ["metric"])
    op.create_index("ix_custom_alert_rules_active", "custom_alert_rules", ["is_active"])


def downgrade() -> None:
    op.drop_index("ix_custom_alert_rules_active", "custom_alert_rules")
    op.drop_index("ix_custom_alert_rules_metric", "custom_alert_rules")
    op.drop_index("ix_custom_alert_rules_user_id", "custom_alert_rules")
    op.drop_table("custom_alert_rules")
