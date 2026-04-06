"""Add EU traceability tables: catch_certificates, lot_traces, iuu_risk_assessments, eudr_compliance.

Revision ID: 003
Revises: 002
Create Date: 2026-03-31
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "catch_certificates",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("certificate_no", sa.String(64), unique=True, nullable=False),
        sa.Column("vessel_name", sa.String(256)),
        sa.Column("flag_state", sa.String(64)),
        sa.Column("catch_area", sa.String(128)),
        sa.Column("species", sa.String(128)),
        sa.Column("quantity_kg", sa.Float),
        sa.Column("catch_date", sa.DateTime),
        sa.Column("landing_port", sa.String(128)),
        sa.Column("validation_authority", sa.String(256)),
        sa.Column("status", sa.String(32)),
        sa.Column("issued_at", sa.DateTime),
        sa.Column("expires_at", sa.DateTime),
        sa.Column("notes", sa.Text),
    )

    op.create_table(
        "lot_traces",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("lot_id", sa.String(64), unique=True, nullable=False),
        sa.Column("certificate_id", sa.Integer, sa.ForeignKey("catch_certificates.id")),
        sa.Column("origin_locality_no", sa.Integer, sa.ForeignKey("localities.locality_no")),
        sa.Column("product_type", sa.String(64)),
        sa.Column("quantity_kg", sa.Float),
        sa.Column("chain_of_custody", sa.Text),
        sa.Column("current_holder", sa.String(256)),
        sa.Column("status", sa.String(32)),
        sa.Column("created_at", sa.DateTime),
        sa.Column("delivered_at", sa.DateTime),
    )

    op.create_table(
        "iuu_risk_assessments",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("vessel_name", sa.String(256), nullable=False),
        sa.Column("imo_number", sa.String(32)),
        sa.Column("flag_state", sa.String(64)),
        sa.Column("risk_score", sa.Float),
        sa.Column("risk_level", sa.String(16)),
        sa.Column("factors", sa.Text),
        sa.Column("assessed_at", sa.DateTime),
        sa.Column("assessed_by", sa.String(64)),
    )

    op.create_table(
        "eudr_compliance",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("supplier_name", sa.String(256), nullable=False),
        sa.Column("product", sa.String(64)),
        sa.Column("country_of_origin", sa.String(128)),
        sa.Column("geolocation", sa.String(256)),
        sa.Column("deforestation_free", sa.Boolean),
        sa.Column("certification_body", sa.String(256)),
        sa.Column("certification_valid_until", sa.DateTime),
        sa.Column("status", sa.String(32)),
        sa.Column("last_verified", sa.DateTime),
        sa.Column("notes", sa.Text),
    )


def downgrade() -> None:
    op.drop_table("eudr_compliance")
    op.drop_table("iuu_risk_assessments")
    op.drop_table("lot_traces")
    op.drop_table("catch_certificates")
