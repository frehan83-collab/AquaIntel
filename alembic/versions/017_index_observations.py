"""017: published index observations (AI-STI / AI-LPI history).

Backs `core.market.indices.history()` — the published, versioned series behind
the two named indices. Unique per (index_code, week, version) so a published
value is immutable and a method change (new version) is visible rather than
silently restating history.

Revision ID: 017
Revises: 016
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "index_observations",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("index_code", sa.String(16), nullable=False),
        sa.Column("week", sa.String(12), nullable=False),
        sa.Column("as_of", sa.DateTime, nullable=False),
        sa.Column("version", sa.String(16), nullable=False),
        sa.Column("value", sa.Float),
        sa.Column("band", sa.String(16)),
        sa.Column("components_json", sa.Text),
        sa.Column("provenance_json", sa.Text),
        sa.Column("created_at", sa.DateTime),
        sa.UniqueConstraint(
            "index_code", "week", "version", name="uq_index_observations_week_version"
        ),
    )
    op.create_index(
        "ix_index_observations_index_code", "index_observations", ["index_code"]
    )


def downgrade() -> None:
    op.drop_index("ix_index_observations_index_code", table_name="index_observations")
    op.drop_table("index_observations")
