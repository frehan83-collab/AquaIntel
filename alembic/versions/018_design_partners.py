"""018: design-partner (paid pilot) infrastructure.

Two tables: `design_partners` (the pilot grant, its expiry, ICP, the plan granted
and the data-reciprocity terms) and `partner_metrics` (the success metrics a pilot
is judged on). Pilots deliberately reference a canonical plan key rather than
introducing a new tier, so `core/entitlements.py` stays the single plan table.

Revision ID: 018
Revises: 017
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    conn = op.get_bind()
    return sa.inspect(conn).has_table(name)


def upgrade() -> None:
    if not _has_table("design_partners"):
        op.create_table(
            "design_partners",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("company", sa.String(256), nullable=False),
            sa.Column("contact_email", sa.String(256)),
            sa.Column("contact_name", sa.String(256)),
            sa.Column("icp", sa.String(64)),
            sa.Column("sector", sa.String(128)),
            sa.Column("country", sa.String(8)),
            sa.Column("plan_granted", sa.String(32)),
            sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id")),
            sa.Column("starts_at", sa.DateTime),
            sa.Column("ends_at", sa.DateTime),
            sa.Column("status", sa.String(24), server_default="prospect"),
            sa.Column("is_paid", sa.Boolean, server_default=sa.false()),
            sa.Column("monthly_price_nok", sa.Float, server_default="0"),
            sa.Column("reciprocity_json", sa.Text),
            sa.Column("notes", sa.Text),
            sa.Column("created_at", sa.DateTime),
        )
        op.create_index("ix_design_partners_user_id", "design_partners", ["user_id"])

    if not _has_table("partner_metrics"):
        op.create_table(
            "partner_metrics",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column(
                "partner_id",
                sa.Integer,
                sa.ForeignKey("design_partners.id"),
                nullable=False,
            ),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("value", sa.Float),
            sa.Column("target", sa.Float),
            sa.Column("unit", sa.String(32)),
            sa.Column("note", sa.Text),
            sa.Column("recorded_at", sa.DateTime),
        )
        op.create_index("ix_partner_metrics_partner_id", "partner_metrics", ["partner_id"])


def downgrade() -> None:
    if _has_table("partner_metrics"):
        op.drop_index("ix_partner_metrics_partner_id", table_name="partner_metrics")
        op.drop_table("partner_metrics")
    if _has_table("design_partners"):
        op.drop_index("ix_design_partners_user_id", table_name="design_partners")
        op.drop_table("design_partners")
