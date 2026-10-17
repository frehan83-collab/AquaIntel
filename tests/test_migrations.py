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


def test_fresh_database_has_lice_year_week_index(tmp_path):
    """015 must leave ix_lice_year_week present (the /api/lice/summary fix)."""
    import sqlite3

    db_file = tmp_path / "fresh_migrations.db"
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{db_file}",
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
    assert result.returncode == 0, f"upgrade failed:\n{result.stderr}"

    conn = sqlite3.connect(db_file)
    try:
        names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index' "
                "AND tbl_name = 'lice_records'"
            )
        }
        assert "ix_lice_year_week" in names, f"missing 015 index; found: {sorted(names)}"
    finally:
        conn.close()


# ── WS-1: lice_records.source (migration 019) ─────────────────────────────────


def _alembic(db_file: Path, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db_file}", "FISHINTEL_ENV": ""}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=REPO_ROOT,
        timeout=180,
    )


def test_fresh_database_has_lice_source_column(tmp_path):
    """WS-1: 019 adds `lice_records.source VARCHAR(32) NOT NULL DEFAULT 'unverified'`."""
    import sqlite3

    db_file = tmp_path / "fresh_migrations.db"
    result = _alembic(db_file, "upgrade", "head")
    assert result.returncode == 0, f"upgrade failed:\n{result.stderr}"

    conn = sqlite3.connect(db_file)
    try:
        cols = {row[1]: row for row in conn.execute("PRAGMA table_info(lice_records)")}
    finally:
        conn.close()
    assert "source" in cols, f"lice_records has no source column; columns: {sorted(cols)}"
    _cid, _name, _type, notnull, default, _pk = cols["source"]
    assert notnull == 1, cols["source"]
    assert default == "'unverified'", cols["source"]


def test_019_backfills_demo_rows_and_never_a_real_source(tmp_path):
    """WS-1 backfill rule.

    Only rows provable as demo seed by construction (DEMO_LOCALITIES x the seed
    year) become 'demo_seed'; every other pre-existing row stays 'unverified'
    and nothing is ever backfilled as a real source. Downgrade removes the column
    and keeps the rows.
    """
    import sqlite3

    db_file = tmp_path / "backfill.db"
    result = _alembic(db_file, "upgrade", "018")
    assert result.returncode == 0, f"upgrade to 018 failed:\n{result.stderr}"

    conn = sqlite3.connect(db_file)
    try:
        conn.execute(
            "INSERT INTO localities (locality_no, name) VALUES (10001, 'Demo'), (20000, 'Real')"
        )
        conn.executemany(
            "INSERT INTO lice_records (locality_no, year, week, avg_adult_female_lice, fetched_at) "
            "VALUES (?, ?, ?, 0.1, '2026-01-01 00:00:00')",
            [(10001, 2025, 1), (10001, 2024, 1), (20000, 2025, 1)],
        )
        conn.commit()
    finally:
        conn.close()

    result = _alembic(db_file, "upgrade", "head")
    assert result.returncode == 0, f"upgrade 018->head failed:\n{result.stderr}"
    conn = sqlite3.connect(db_file)
    try:
        rows = conn.execute(
            "SELECT locality_no, year, source FROM lice_records ORDER BY locality_no, year"
        ).fetchall()
    finally:
        conn.close()
    assert rows == [
        (10001, 2024, "unverified"),
        (10001, 2025, "demo_seed"),
        (20000, 2025, "unverified"),
    ], rows
    assert all(source != "barentswatch" for _, _, source in rows)

    result = _alembic(db_file, "downgrade", "018")
    assert result.returncode == 0, f"downgrade failed:\n{result.stderr}"
    conn = sqlite3.connect(db_file)
    try:
        cols = [row[1] for row in conn.execute("PRAGMA table_info(lice_records)")]
        count = conn.execute("SELECT COUNT(*) FROM lice_records").fetchone()[0]
    finally:
        conn.close()
    assert "source" not in cols, cols
    assert count == 3


def test_020_marks_method_1_observations_superseded_and_keeps_their_values(tmp_path):
    """WS-19: every index observation stored under method 1.0.0 is marked superseded
    by 2.0.0 (the quota component and AI-LPI v1.0 were withdrawn). Nothing is
    deleted and no stored value, band, component or provenance is edited; the
    downgrade removes the marks and keeps the rows."""
    import sqlite3

    db_file = tmp_path / "supersede.db"
    result = _alembic(db_file, "upgrade", "019")
    assert result.returncode == 0, f"upgrade to 019 failed:\n{result.stderr}"
    stored = [
        ("AI-LPI", "2026-W42", "1.0.0", 55.0, "moderate", '[{"name": "emission_pressure"}]', '{"is_live": true}'),
        ("AI-STI", "2026-W42", "1.0.0", 100.0, "severe", '[{"name": "quota_pressure"}]', '{"is_live": false}'),
        ("AI-STI", "2026-W41", "0.9.0", 50.0, "moderate", "[]", "{}"),
    ]
    conn = sqlite3.connect(db_file)
    try:
        conn.executemany(
            "INSERT INTO index_observations (index_code, week, as_of, version, value, band, "
            "components_json, provenance_json) VALUES (?, ?, '2026-10-16 15:36:20', ?, ?, ?, ?, ?)",
            stored,
        )
        conn.commit()
    finally:
        conn.close()

    result = _alembic(db_file, "upgrade", "head")
    assert result.returncode == 0, f"upgrade 019->head failed:\n{result.stderr}"
    conn = sqlite3.connect(db_file)
    try:
        rows = conn.execute(
            "SELECT index_code, week, version, value, band, components_json, provenance_json, "
            "superseded_by, superseded_reason, superseded_at FROM index_observations ORDER BY id"
        ).fetchall()
    finally:
        conn.close()
    assert [row[:7] for row in rows] == stored, "stored observations must not be edited"
    lpi, sti, older = rows
    for row in (lpi, sti):
        assert row[7] == "2.0.0", row
        assert row[8] and "WS-19" in row[8], row
        assert row[9] is not None, row
    assert "AI-LPI v1.0 withdrawn" in lpi[8]
    assert "quota_pressure" in sti[8]
    assert older[7:] == (None, None, None), "only method 1.0.0 rows are superseded here"

    result = _alembic(db_file, "downgrade", "019")
    assert result.returncode == 0, f"downgrade failed:\n{result.stderr}"
    conn = sqlite3.connect(db_file)
    try:
        cols = [row[1] for row in conn.execute("PRAGMA table_info(index_observations)")]
        count = conn.execute("SELECT COUNT(*) FROM index_observations").fetchone()[0]
    finally:
        conn.close()
    assert not {"superseded_by", "superseded_reason", "superseded_at"} & set(cols), cols
    assert count == 3


def test_019_repairs_a_reconciled_column_and_keeps_real_labels(tmp_path):
    """The shape a type-only reconciliation leaves (nullable, no default): 019 must
    relabel NULL demo-key rows as demo_seed, leave a real label at a demo locality
    untouched, and repair the column to NOT NULL DEFAULT 'unverified'."""
    import sqlite3

    db_file = tmp_path / "reconciled.db"
    result = _alembic(db_file, "upgrade", "018")
    assert result.returncode == 0, f"upgrade to 018 failed:\n{result.stderr}"

    conn = sqlite3.connect(db_file)
    try:
        conn.execute("ALTER TABLE lice_records ADD COLUMN source VARCHAR(32)")
        conn.execute(
            "INSERT INTO localities (locality_no, name) VALUES (10001, 'Demo'), (10002, 'Demo2')"
        )
        conn.executemany(
            "INSERT INTO lice_records (locality_no, year, week, avg_adult_female_lice, "
            "fetched_at, source) VALUES (?, ?, ?, 0.1, '2026-01-01 00:00:00', ?)",
            [(10001, 2025, 1, "barentswatch"), (10002, 2025, 1, None)],
        )
        conn.commit()
    finally:
        conn.close()

    result = _alembic(db_file, "upgrade", "head")
    assert result.returncode == 0, f"upgrade 018->head failed:\n{result.stderr}"
    conn = sqlite3.connect(db_file)
    try:
        rows = conn.execute(
            "SELECT locality_no, source FROM lice_records ORDER BY locality_no"
        ).fetchall()
        column = next(
            r for r in conn.execute("PRAGMA table_info(lice_records)") if r[1] == "source"
        )
    finally:
        conn.close()
    assert rows == [(10001, "barentswatch"), (10002, "demo_seed")], rows
    assert column[3] == 1 and column[4] == "'unverified'", column

