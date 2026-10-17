"""020: mark index observations of a withdrawn method superseded (WS-19).

Method 2.0.0 (core.market.indices) removes AI-STI's quota_pressure component and
withdraws AI-LPI v1.0: both read the lice-quota tracker's national utilisation,
which divides a lice count by constants labelled tonnes for a quota regime that
is still a proposal. Every observation stored under method 1.0.0 is therefore
marked superseded by 2.0.0.

Revision policy (docs/INDICES.md): a stored observation is never edited and never
deleted. This migration adds three nullable annotation columns and fills them for
the 1.0.0 rows only; value, band, components_json and provenance_json are not
touched. On the dev box the two 1.0.0 rows (2026-W42) were written by the test
suite before the lineage guard (HANDOVER trap 16).

Dialect notes: SQLAlchemy Core update() with bound parameters (trap 1).
Existence-guarded: a create_all-built DB, or one tests/conftest.py reconciled,
already has the columns from the ORM — the marks are still written (only where
superseded_by is NULL, so a rerun changes nothing). The downgrade uses batch mode
so SQLite and PostgreSQL take the same path, and keeps every row.

Revision ID: 020
Revises: 019
"""
from __future__ import annotations

import datetime as dt

import sqlalchemy as sa
from alembic import op

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None

TABLE = "index_observations"
COLUMNS = (
    ("superseded_by", sa.String(16)),
    ("superseded_reason", sa.Text()),
    ("superseded_at", sa.DateTime()),
)
WITHDRAWN_VERSION = "1.0.0"
SUCCESSOR_VERSION = "2.0.0"
# Frozen copies of the reasons published in core.market.indices (a migration must
# not import application code that may change after it ran).
REASONS = {
    "AI-STI": (
        "superseded by method 2.0.0 (WS-19, 2026-10-17): quota_pressure removed — it "
        "read the lice-quota tracker's national utilisation, a lice count divided by "
        "constants labelled tonnes for a quota regime that is still a proposal"
    ),
    "AI-LPI": (
        "AI-LPI v1.0 withdrawn by method 2.0.0 (WS-19, 2026-10-17): built only on the "
        "lice-quota tracker's national utilisation (a lice count divided by constants "
        "labelled tonnes), and its quota_headroom component was inverted"
    ),
}
GENERIC_REASON = "method 1.0.0 superseded by 2.0.0 (WS-19, 2026-10-17)"


def _columns(insp) -> set[str]:
    return {col["name"] for col in insp.get_columns(TABLE)}


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if not insp.has_table(TABLE):
        return
    have = _columns(insp)
    for name, type_ in COLUMNS:
        if name not in have:
            op.add_column(TABLE, sa.Column(name, type_, nullable=True))

    tbl = sa.table(
        TABLE,
        sa.column("index_code", sa.String),
        sa.column("version", sa.String),
        sa.column("superseded_by", sa.String),
        sa.column("superseded_reason", sa.Text),
        sa.column("superseded_at", sa.DateTime),
    )
    marked_at = dt.datetime.now(dt.UTC).replace(tzinfo=None)  # stored naive UTC, like as_of
    pending = sa.and_(tbl.c.version == WITHDRAWN_VERSION, tbl.c.superseded_by.is_(None))
    for code, reason in REASONS.items():
        conn.execute(
            sa.update(tbl)
            .where(sa.and_(pending, tbl.c.index_code == code))
            .values(superseded_by=SUCCESSOR_VERSION, superseded_reason=reason, superseded_at=marked_at)
        )
    conn.execute(
        sa.update(tbl)
        .where(pending)
        .values(superseded_by=SUCCESSOR_VERSION, superseded_reason=GENERIC_REASON, superseded_at=marked_at)
    )


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if not insp.has_table(TABLE):
        return
    present = [name for name, _type in COLUMNS if name in _columns(insp)]
    if not present:
        return
    with op.batch_alter_table(TABLE) as batch_op:
        for name in present:
            batch_op.drop_column(name)
