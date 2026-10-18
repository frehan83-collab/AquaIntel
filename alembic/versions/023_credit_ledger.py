"""023: the credit ledger for deep-analysis runs (WS-39).

A credit is one rendered document (margin dossier, origin landed-cost comparison, lice
review). The ledger is append-only: every grant, purchase, refund and spend is a signed row,
so a balance is always reconstructable and a support question has an answer.

Additive only; no existing data is touched. A route that cannot read the ledger reports the
balance as unknown rather than assuming credits.

Revision ID: 023
Revises: 022
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    return name in sa.inspect(bind).get_table_names()


def upgrade() -> None:
    if _has_table("credit_ledger"):
        return
    op.create_table(
        "credit_ledger",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_key", sa.String(length=128), nullable=False),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=False),
        sa.Column("ref", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_credit_ledger_user", "credit_ledger", ["user_key"])
    op.create_index("ix_credit_ledger_created", "credit_ledger", ["created_at"])


def downgrade() -> None:
    if not _has_table("credit_ledger"):
        return
    op.drop_index("ix_credit_ledger_created", table_name="credit_ledger")
    op.drop_index("ix_credit_ledger_user", table_name="credit_ledger")
    op.drop_table("credit_ledger")
