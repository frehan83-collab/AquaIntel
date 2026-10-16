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
    conn = op.get_bind()
    for table, column in _TABLES:
        for legacy, canonical in _ALIASES.items():
            conn.exec_driver_sql(
                f"UPDATE {table} SET {column} = %s WHERE LOWER({column}) = %s",
                (canonical, legacy),
            )
        conn.exec_driver_sql(
            f"UPDATE {table} SET {column} = 'free' "
            f"WHERE {column} IS NOT NULL AND LOWER({column}) NOT IN "
            f"({', '.join(['%s'] * len(_CANONICAL))})",
            tuple(_CANONICAL),
        )


def downgrade() -> None:
    # Data normalisation is not reversible (the original aliases are unknown).
    pass
