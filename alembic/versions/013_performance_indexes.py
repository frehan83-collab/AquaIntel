"""Add performance indexes for production queries.

- Locality.production_area: indexed for PA-level aggregation queries
- AuditLog.user_id: indexed for per-user audit trail queries
- AuditLog.action: indexed for action-type filtering

These indexes improve query performance on the most frequently filtered columns
across analytics, compliance, and admin routes.

Revision ID: 013
Revises: 012
Create Date: 2026-04-08
"""
from __future__ import annotations

from alembic import op

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_localities_production_area", "localities", ["production_area"])
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_user_id", table_name="audit_logs")
    op.drop_index("ix_localities_production_area", table_name="localities")
