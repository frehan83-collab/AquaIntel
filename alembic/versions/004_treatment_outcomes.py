"""Add treatment_outcomes table for farmer-reported treatment efficacy tracking.

Revision ID: 004
Revises: 003
Create Date: 2026-03-31
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "treatment_outcomes",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("locality_no", sa.Integer, sa.ForeignKey("localities.locality_no"), nullable=False),
        sa.Column("treatment_date", sa.DateTime, nullable=False),
        sa.Column("method", sa.String(64)),
        sa.Column("pre_lice_count", sa.Float),
        sa.Column("post_lice_count", sa.Float),
        sa.Column("mortality_observed", sa.Integer, default=0),
        sa.Column("cost_nok", sa.Float),
        sa.Column("notes", sa.Text),
        sa.Column("reported_at", sa.DateTime),
    )


def downgrade() -> None:
    op.drop_table("treatment_outcomes")
