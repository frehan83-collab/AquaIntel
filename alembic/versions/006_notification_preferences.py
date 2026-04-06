"""Add notification_preferences table for per-user alert configuration.

Revision ID: 006
Revises: 005
Create Date: 2026-04-03
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_email", sa.String, index=True, unique=True),
        sa.Column("lice_critical_threshold", sa.Float, default=0.5),
        sa.Column("lice_warning_threshold", sa.Float, default=0.3),
        sa.Column("price_change_pct", sa.Float, default=10.0),
        sa.Column("sst_high_threshold", sa.Float, default=16.0),
        sa.Column("sst_low_threshold", sa.Float, default=4.0),
        sa.Column("email_alerts", sa.Boolean, default=False),
        sa.Column("push_alerts", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, onupdate=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("notification_preferences")
