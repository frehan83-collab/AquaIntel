"""024: the answer-receipt table (WS-49).

One row per model-backed answer a customer saw, holding what the model was given (the facts with
their as_of), which model answered, whether it was a free one, the claim-check verdict and the
cost. The question itself is hashed, not stored.

Additive only. A missing table degrades to "no receipt id" and never blocks an answer.

Revision ID: 024
Revises: 023
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    return name in sa.inspect(bind).get_table_names()


def upgrade() -> None:
    if _has_table("answer_receipts"):
        return
    op.create_table(
        "answer_receipts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_key", sa.String(length=128), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False, server_default="chat"),
        sa.Column("question_hash", sa.String(length=64), nullable=False),
        sa.Column("mode", sa.String(length=24), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("model_is_free", sa.Boolean(), server_default=sa.false()),
        sa.Column("sources_json", sa.Text(), nullable=True),
        sa.Column("verification_json", sa.Text(), nullable=True),
        sa.Column("cost_usd", sa.Float(), server_default="0"),
        sa.Column("latency_ms", sa.Float(), server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("retained_until", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_answer_receipts_user", "answer_receipts", ["user_key"])
    op.create_index("ix_answer_receipts_retained", "answer_receipts", ["retained_until"])


def downgrade() -> None:
    if not _has_table("answer_receipts"):
        return
    op.drop_index("ix_answer_receipts_retained", table_name="answer_receipts")
    op.drop_index("ix_answer_receipts_user", table_name="answer_receipts")
    op.drop_table("answer_receipts")
