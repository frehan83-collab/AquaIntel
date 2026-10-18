"""022: the grounded-chat meter (WS-38).

The chat became a paid product surface: each answer is grounded on the platform's verified
facts, costs real model tokens, and is metered against a per-plan monthly allowance. This
migration creates the one table that meter needs.

No existing data is touched. The table is additive, and the route treats an unreadable
meter as "unknown" rather than blocking an answer, so a missing table degrades instead of
failing.

Revision ID: 022
Revises: 021
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    return name in sa.inspect(bind).get_table_names()


def upgrade() -> None:
    if _has_table("chat_usage"):
        return
    op.create_table(
        "chat_usage",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_key", sa.String(length=128), nullable=False),
        sa.Column("month", sa.String(length=7), nullable=False),
        sa.Column("questions", sa.Integer(), server_default="0"),
        sa.Column("input_tokens", sa.Integer(), server_default="0"),
        sa.Column("output_tokens", sa.Integer(), server_default="0"),
        sa.Column("cost_usd", sa.Float(), server_default="0"),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("user_key", "month", name="uq_chat_usage_user_month"),
    )
    op.create_index("ix_chat_usage_month", "chat_usage", ["month"])


def downgrade() -> None:
    if not _has_table("chat_usage"):
        return
    op.drop_index("ix_chat_usage_month", table_name="chat_usage")
    op.drop_table("chat_usage")
