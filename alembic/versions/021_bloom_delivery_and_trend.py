"""021: bloom alert delivery truth and the self-compared chlorophyll trend (WS-33).

Two data defects made the algal-bloom surface claim more than it had:

1. **Alert delivery.** ``core/bloom/notifications.py`` set
   ``delivery_status = "sent"`` before dispatch, and the senders returned silently
   when Twilio/SMTP were unconfigured. On the dev box all 842 rows read "sent" with
   no channel configured. This migration adds ``delivered_at`` (nullable) and labels
   every pre-existing "sent"/"delivered" row ``legacy_unknown``: nobody can prove
   those were delivered, so the platform must not keep saying they were.

2. **The trend was computed against itself.** ``agents/bloom_agent.py`` committed the
   new reading, then computed the trend from "the previous reading", which was the row
   it had just written — so every stored ``chl_a_trend`` is 0.0 (all 123 045 rows on
   the dev box). The agent now reads the previous *distinct observation date* before
   writing, and this migration nulls the old values instead of presenting a computed
   zero as a measurement. ``NULL`` renders as "—"; it is not "no change".

Dialect notes: SQLAlchemy Core ``update()`` with bound parameters (HANDOVER trap 1);
existence-guarded so a ``create_all``-built or conftest-reconciled DB still migrates;
batch mode for the downgrade. Nothing is deleted.

Revision ID: 021
Revises: 020
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None

ALERTS = "bloom_alerts"
ASSESSMENTS = "bloom_risk_assessments"
LEGACY_STATUS = "legacy_unknown"


def _columns(table: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(table):
        return set()
    return {column["name"] for column in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()

    if "delivered_at" not in _columns(ALERTS):
        with op.batch_alter_table(ALERTS) as batch:
            batch.add_column(sa.Column("delivered_at", sa.DateTime(), nullable=True))

    if _columns(ALERTS):
        alerts = sa.table(
            ALERTS,
            sa.column("delivery_status", sa.String),
            sa.column("delivered_at", sa.DateTime),
        )
        bind.execute(
            alerts.update()
            .where(
                alerts.c.delivery_status.in_(("sent", "delivered")),
                alerts.c.delivered_at.is_(None),
            )
            .values(delivery_status=LEGACY_STATUS)
        )

    if _columns(ASSESSMENTS):
        assessments = sa.table(
            ASSESSMENTS,
            sa.column("chl_a_trend", sa.Float),
        )
        bind.execute(
            assessments.update()
            .where(assessments.c.chl_a_trend == 0.0)
            .values(chl_a_trend=None)
        )


def downgrade() -> None:
    """Undo the schema change only.

    The relabelled rows and the nulled trends are deliberately **not** restored: the
    original values were never measurements, and putting them back would recreate the
    false claim this migration exists to remove.
    """
    if "delivered_at" in _columns(ALERTS):
        with op.batch_alter_table(ALERTS) as batch:
            batch.drop_column("delivered_at")
