"""Add saved_scenarios table.

Revision ID: 005
Revises: 004
Create Date: 2026-04-03
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "saved_scenarios",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_email", sa.String, index=True),
        sa.Column("scenario_type", sa.String),
        sa.Column("scenario_name", sa.String),
        sa.Column("parameters", sa.Text),
        sa.Column("results", sa.Text),
        sa.Column("notes", sa.Text, default=""),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("saved_scenarios")
