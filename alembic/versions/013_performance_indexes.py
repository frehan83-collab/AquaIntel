"""Add performance indexes for production queries.

- Locality.production_area: indexed for PA-level aggregation queries
- AuditLog.user_id: indexed for per-user audit trail queries
- AuditLog.action: indexed for action-type filtering

These indexes improve query performance on the most frequently filtered columns
across analytics, compliance, and admin routes.

NOTE: 011_audit_logs already creates ix_audit_logs_user_id / _action on fresh
installs; the creates below are guarded so `alembic upgrade head` completes on
a fresh database (it used to abort with "index already exists") while still
back-filling databases that ran an older 011 without the indexes.

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


def _index_exists(name: str, table: str) -> bool:
    from sqlalchemy import inspect

    insp = inspect(op.get_bind())
    return any(ix["name"] == name for ix in insp.get_indexes(table))


def upgrade() -> None:
    if not _index_exists("ix_localities_production_area", "localities"):
        op.create_index("ix_localities_production_area", "localities", ["production_area"])
    if not _index_exists("ix_audit_logs_user_id", "audit_logs"):
        op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    if not _index_exists("ix_audit_logs_action", "audit_logs"):
        op.create_index("ix_audit_logs_action", "audit_logs", ["action"])


def downgrade() -> None:
    # Guarded drops: absent indexes (fresh path where 011 owns them and this
    # migration created nothing) must not abort a downgrade.
    if _index_exists("ix_audit_logs_action", "audit_logs"):
        op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    if _index_exists("ix_audit_logs_user_id", "audit_logs"):
        op.drop_index("ix_audit_logs_user_id", table_name="audit_logs")
    if _index_exists("ix_localities_production_area", "localities"):
        op.drop_index("ix_localities_production_area", table_name="localities")
