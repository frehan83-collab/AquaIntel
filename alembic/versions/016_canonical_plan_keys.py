"""016: normalise legacy tier strings to canonical plan keys.

`core/entitlements.py` is now the single source of truth for plans. Rows written
before it may still carry legacy or alias tier strings ("premium", "pro",
"basic", "pilot", "growth", "licence", "datapartner"). Without normalisation the
quota middleware and the paywall would treat them as unknown and silently fall
back to `free`, under-serving paying customers.

Revision ID: 016
Revises: 015
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None

# legacy -> canonical (mirrors core.entitlements.LEGACY_ALIASES)
_ALIASES = {
    "premium": "professional",
    "pro": "professional",
    "desk": "professional",
    "basic": "free",
    "starter": "free",
    "trial": "free",
    "pilot": "professional",
    "growth": "operator",
    "farm": "operator",
    "licence": "data",
    "license": "data",
    "datapartner": "data",
}
# Values that are neither canonical nor aliases fall back to free.
_CANONICAL = (
    "free",
    "operator",
    "professional",
    "enterprise",
    "investor",
    "intelligence",
    "data",
)

_TABLES = (
    ("users", "tier"),
    ("subscriptions", "tier"),
    ("api_keys", "tier"),
    ("performance_fees", "tier"),
)


def upgrade() -> None:
    """Normalise legacy tier strings to canonical plan keys.

    Dialect-agnostic: SQLAlchemy Core ``update()`` with bound parameters, because
    ``exec_driver_sql`` with ``%s`` placeholders is psycopg2 syntax and raises
    ``sqlite3.OperationalError: near "%": syntax error`` on SQLite — caught by
    ``tests/test_migrations.py`` (fresh-DB ``alembic upgrade head``).

    Tables that do not exist in this database are skipped (a fresh DB built by a
    subset of migrations must not fail here).
    """
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing = set(inspector.get_table_names())

    for table, column in _TABLES:
        if table not in existing:
            continue
        tbl = sa.table(table, sa.column(column, sa.String))
        for legacy, canonical in _ALIASES.items():
            conn.execute(
                sa.update(tbl)
                .where(sa.func.lower(sa.column(column)) == legacy)
                .values({column: canonical})
            )
        conn.execute(
            sa.update(tbl)
            .where(
                sa.and_(
                    sa.column(column).isnot(None),
                    ~sa.func.lower(sa.column(column)).in_(list(_CANONICAL)),
                )
            )
            .values({column: "free"})
        )


def downgrade() -> None:
    # Data normalisation is not reversible (the original aliases are unknown).
    pass
