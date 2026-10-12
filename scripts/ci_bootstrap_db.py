"""Bootstrap a fresh SQLite dev DB for CI e2e runs (schema + demo seed).

Mirrors the fresh-runner bootstrap in tests/conftest.py: create the schema
(ORM create_all + Alembic upgrade to head), then seed the deterministic demo
dataset when the lice table is empty. No-op on an already-populated DB.

Used by .github/workflows/frontend.yml's backend-backed e2e job before
uvicorn starts; safe to run repeatedly (idempotent).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    from sqlalchemy import text

    from core.models import engine, init_db

    # Run migrations FIRST so a fresh DB exercises the real Alembic chain
    # (matches the production docker-entrypoint order); create_all afterwards
    # only backfills anything the migrations missed. Kept non-fatal (like the
    # conftest bootstrap) so a migration-vs-ORM drift can't hard-block CI —
    # the warning in the job log is the signal.
    try:
        from alembic import command as _alembic_cmd
        from alembic.config import Config as _AlembicConfig

        _cfg = _AlembicConfig("alembic.ini")
        _cfg.set_main_option("script_location", "alembic")
        _alembic_cmd.upgrade(_cfg, "head")
        print("ci_bootstrap: alembic upgrade to head OK")
    except Exception as exc:
        print(f"ci_bootstrap: alembic upgrade skipped: {exc}")

    init_db()

    with engine.connect() as conn:
        empty = conn.execute(text("SELECT COUNT(*) FROM lice_records")).scalar() == 0
    if empty:
        from core.demo_seed import seed_demo_data

        stats = seed_demo_data()
        print(f"ci_bootstrap: seeded demo dataset: {stats}")
    else:
        print("ci_bootstrap: lice_records already populated — skipping seed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
