"""Index lice_records by (year, week) for the weekly-summary read path.

/api/lice/summary (core/routers/lice_routes.py) filters every query by
(year, week) and finds the latest week via ORDER BY year DESC, week DESC.
Before this index all three aggregates were full table scans over ~186k rows
plus a temp b-tree sort for the latest week; the only existing index
(ix_lice_lookup) leads with locality_no, so it cannot serve those predicates.

EXPLAIN QUERY PLAN evidence (RUN-1 R6, 2026-10-13, 186,139 rows):
  before: SCAN lice_records + USE TEMP B-TREE FOR ORDER BY
  after:  SEARCH lice_records USING INDEX ix_lice_year_week (year=? AND week=?)

Benchmark (scripts/bench_lice_read.py): the summary read path drops from
~19-30 ms warm (Linux/Windows) to <0.1 ms with this index. The same
measurement closed the DuckDB P0-2 question (DuckDB was 4x SLOWER).

The create is existence-guarded (013 pattern): a create_all-first database
already carries the model-declared index, so `alembic upgrade head` must not
abort with "index already exists" on it.

Revision ID: 015
Revises: 014
Create Date: 2026-10-13
"""
from __future__ import annotations

from alembic import op

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def _index_exists(name: str, table: str) -> bool:
    from sqlalchemy import inspect

    insp = inspect(op.get_bind())
    return any(ix["name"] == name for ix in insp.get_indexes(table))


def upgrade() -> None:
    if not _index_exists("ix_lice_year_week", "lice_records"):
        op.create_index("ix_lice_year_week", "lice_records", ["year", "week"])


def downgrade() -> None:
    if _index_exists("ix_lice_year_week", "lice_records"):
        op.drop_index("ix_lice_year_week", table_name="lice_records")
