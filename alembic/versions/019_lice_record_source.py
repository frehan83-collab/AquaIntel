"""019: lice_records.source — make the lice lineage verifiable (WS-1).

Column contract (mirrors core.models.LiceRecord.source / core.source_lineage):
  'barentswatch'  written by agents/data_ingest.py on BOTH branches of its upsert
  'demo_seed'     written by core/demo_seed.py
  'unverified'    server default; every pre-existing row gets it — its origin has
                  no row-level proof, so it must never count as live.

Backfill rule: only rows provable as demo seed by construction (the seed writes
DEMO_LOCALITIES x weeks 1-52 x year 2025, core/demo_seed.py) are relabelled
'demo_seed'. Nothing is backfilled as a real source (HANDOVER trap: "never
backfill rows as a real source without proof"). The error direction is
conservative: a real 2025 row at a demo locality number would be labelled demo,
which can only lower a live claim.

Dialect notes: SQLAlchemy Core update() with bound parameters only — 016's
exec_driver_sql + '%s' is a SQLite syntax error. ALTER TABLE ... ADD COLUMN ...
DEFAULT 'unverified' NOT NULL renders identically on SQLite and PostgreSQL.
Existence-guarded (013/015/018 pattern): a create_all-built DB already has the
column from the ORM, and tests/conftest.py's reconciliation may have added it as
a type-only nullable column — that shape is repaired here (NULL -> 'unverified',
then NOT NULL + default) so the DDL cannot diverge from the ORM. The downgrade
uses batch mode so SQLite and PostgreSQL take the same code path.

Revision ID: 019
Revises: 018
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None

TABLE = "lice_records"
COLUMN = "source"
DEFAULT_SOURCE = "unverified"
DEMO_SOURCE = "demo_seed"
DEMO_YEAR = 2025
# Frozen copy of core/demo_seed.py DEMO_LOCALITIES (10001..10022). A migration
# must not import application code that may change after it ran.
DEMO_LOCALITY_NOS = tuple(range(10001, 10023))


def _column(insp) -> dict | None:
    for col in insp.get_columns(TABLE):
        if col["name"] == COLUMN:
            return col
    return None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if not insp.has_table(TABLE):
        return
    existing = _column(insp)
    if existing is None:
        op.add_column(
            TABLE,
            sa.Column(COLUMN, sa.String(32), nullable=False, server_default=DEFAULT_SOURCE),
        )

    tbl = sa.table(
        TABLE,
        sa.column(COLUMN, sa.String),
        sa.column("locality_no", sa.Integer),
        sa.column("year", sa.Integer),
    )
    # A type-only ADD COLUMN (conftest reconciliation) leaves NULLs: make them explicit.
    conn.execute(sa.update(tbl).where(tbl.c.source.is_(None)).values({COLUMN: DEFAULT_SOURCE}))
    # Demo rows are provable by construction; a label written by a real ingest wins.
    conn.execute(
        sa.update(tbl)
        .where(
            sa.and_(
                tbl.c.year == DEMO_YEAR,
                tbl.c.locality_no.in_(list(DEMO_LOCALITY_NOS)),
                tbl.c.source == DEFAULT_SOURCE,
            )
        )
        .values({COLUMN: DEMO_SOURCE})
    )

    if existing is not None and (existing.get("nullable", True) or existing.get("default") is None):
        # Repair a reconciled (nullable, no default) column to the ORM contract.
        with op.batch_alter_table(TABLE) as batch_op:
            batch_op.alter_column(
                COLUMN,
                existing_type=sa.String(32),
                nullable=False,
                server_default=DEFAULT_SOURCE,
            )


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if not insp.has_table(TABLE) or _column(insp) is None:
        return
    with op.batch_alter_table(TABLE) as batch_op:
        batch_op.drop_column(COLUMN)
