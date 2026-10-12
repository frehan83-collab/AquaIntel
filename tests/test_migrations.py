"""Migration chain smoke test — `alembic upgrade head` must succeed on a FRESH DB.

Regression for the 013_performance_indexes bug: it re-created
ix_audit_logs_user_id / _action, which 011_audit_logs had already created, so
the chain aborted with "index already exists" on every brand-new database
(production entrypoint runs migrations before gunicorn — a fresh deploy would
have failed). Runs in a subprocess so the DATABASE_URL override creates an
isolated SQLite file instead of touching the dev/test database.
"""
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_alembic_upgrade_head_on_fresh_database(tmp_path):
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{tmp_path / 'fresh_migrations.db'}",
        # Production guards must not kick in for a throwaway SQLite URL
        "FISHINTEL_ENV": "",
    }
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
        env=env,
        cwd=REPO_ROOT,
        timeout=180,
    )
    assert result.returncode == 0, (
        "alembic upgrade head failed on a fresh database:\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
