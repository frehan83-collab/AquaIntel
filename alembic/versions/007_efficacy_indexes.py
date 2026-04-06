"""Add indexes and resistance_observed column to treatment_outcomes.

Indexes improve query performance for the Efficacy Marketplace
aggregations which filter by method and (locality_no, method).

New column: resistance_observed (BOOLEAN DEFAULT FALSE) tracks
whether the farmer observed reduced treatment efficacy suggesting
chemical resistance.

Revision ID: 007
Revises: 006
Create Date: 2026-04-04
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Performance indexes for Efficacy Marketplace queries
    op.create_index(
        "ix_treatment_outcomes_method",
        "treatment_outcomes",
        ["method"],
    )
    op.create_index(
        "ix_treatment_outcomes_locality_method",
        "treatment_outcomes",
        ["locality_no", "method"],
    )

    # New column: was treatment resistance observed?
    op.add_column(
        "treatment_outcomes",
        sa.Column("resistance_observed", sa.Boolean, server_default=sa.text("FALSE")),
    )


def downgrade() -> None:
    op.drop_column("treatment_outcomes", "resistance_observed")
    op.drop_index("ix_treatment_outcomes_locality_method", "treatment_outcomes")
    op.drop_index("ix_treatment_outcomes_method", "treatment_outcomes")
