"""Benchmark: lice weekly-summary read paths (RUN-1 R5 / P0-2 reopen).

Compares three implementations of the /api/lice/summary aggregate
(core/routers/lice_routes.py — four queries against the latest week):

  A. sqlite-baseline   — stdlib sqlite3 executing the same SQL SQLAlchemy emits
  B. duckdb-sqlite     — DuckDB ATTACHing the SQLite file (sqlite_scanner ext.)
  C. duckdb-rowload    — sqlite3 rows -> in-memory DuckDB -> aggregate
     (C1 latest-week rows, C2 full table — reproduces the 2026-10-13 evidence)

Why a script instead of a pytest: the P0-2 blocker was WINDOWS-ONLY (the
sqlite_scanner extension is blocked by an application-control policy on the
dev box). Run this on Linux for the real numbers:

  docker run --rm -v "${PWD}:/app" -w /app python:3.12-slim \
      sh -c "pip install -q duckdb && python scripts/bench_lice_read.py"

Decision gate (docs/AUTONOMOUS_RUN_PLAN.md R5): ship a DuckDB-backed read
path only if candidate B beats A by >= 1.5x on this workload; otherwise
close P0-2 with the Linux measurements. All candidates must return
identical summary values (checked, reported as `match`).

Self-contained by design: no app imports (stdlib sqlite3 + optional duckdb),
so it runs in any minimal Linux container with the repo mounted.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import statistics
import sys
import time
from pathlib import Path

# ── The exact four queries from core/routers/lice_routes.py::lice_summary ──

SQL_LATEST_WEEK = "SELECT year, week FROM lice_records ORDER BY year DESC, week DESC LIMIT 1"

SQL_MAIN_STATS = (
    "SELECT avg(avg_adult_female_lice), max(avg_adult_female_lice), "
    "count(id), min(avg_adult_female_lice) FROM lice_records "
    "WHERE year = ? AND week = ? AND avg_adult_female_lice IS NOT NULL"
)

SQL_ABOVE_THRESHOLD = (
    "SELECT count(id) FROM lice_records "
    "WHERE year = ? AND week = ? AND avg_adult_female_lice > 0.5"
)

SQL_SQ_SUM = (
    "SELECT sum(avg_adult_female_lice * avg_adult_female_lice) FROM lice_records "
    "WHERE year = ? AND week = ? AND avg_adult_female_lice IS NOT NULL"
)


def _summary_from_results(latest, main, above, sq_sum) -> dict:
    year, week = latest
    avg_lice = float(main[0] or 0)
    n = int(main[2] or 0)
    variance = max(0.0, float(sq_sum or 0) / n - avg_lice ** 2) if n > 1 else 0.0
    return {
        "year": year,
        "week": week,
        "avg": round(avg_lice, 4),
        "max": round(float(main[1] or 0), 4),
        "min": round(float(main[3] or 0), 4),
        "std": round(variance ** 0.5, 4),
        "above": int(above or 0),
        "records": n,
    }


def bench_sqlite(db_path: str) -> tuple[dict, list[float]]:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        latest = conn.execute(SQL_LATEST_WEEK).fetchone()
        if not latest:
            raise RuntimeError("lice_records is empty")
        year, week = latest

        def run() -> tuple[dict, float]:
            t0 = time.perf_counter()
            main = conn.execute(SQL_MAIN_STATS, (year, week)).fetchone()
            above = conn.execute(SQL_ABOVE_THRESHOLD, (year, week)).fetchone()[0]
            sq_sum = conn.execute(SQL_SQ_SUM, (year, week)).fetchone()[0]
            return _summary_from_results(latest, main, above, sq_sum), (time.perf_counter() - t0) * 1000

        _summary, _ = run()  # warmup (OS page cache)
        times = [run()[1] for _ in range(TIMING["runs"])]
        return run()[0] | {"_latest": latest}, times
    finally:
        conn.close()


def bench_duckdb_sqlite(db_path: str) -> tuple[dict, list[float]]:
    import duckdb  # noqa: PLC0415 — optional dependency

    conn = duckdb.connect()
    try:
        conn.execute("INSTALL sqlite; LOAD sqlite;")
        conn.execute(f"ATTACH '{db_path}' AS src (TYPE sqlite, READ_ONLY);")

        def q(sql: str) -> str:
            return sql.replace("lice_records", "src.lice_records")

        latest = conn.execute(q(SQL_LATEST_WEEK)).fetchone()
        if not latest:
            raise RuntimeError("lice_records is empty")
        year, week = latest

        def run() -> tuple[dict, float]:
            t0 = time.perf_counter()
            main = conn.execute(q(SQL_MAIN_STATS), [year, week]).fetchone()
            above = conn.execute(q(SQL_ABOVE_THRESHOLD), [year, week]).fetchone()[0]
            sq_sum = conn.execute(q(SQL_SQ_SUM), [year, week]).fetchone()[0]
            return _summary_from_results(latest, main, above, sq_sum), (time.perf_counter() - t0) * 1000

        _summary, _ = run()
        times = [run()[1] for _ in range(TIMING["runs"])]
        return run()[0] | {"_latest": latest}, times
    finally:
        conn.close()


TIMING: dict = {"runs": 5}

def bench_duckdb_rowload(db_path: str, full_table: bool) -> tuple[dict, list[float]]:
    import duckdb  # noqa: PLC0415

    conn = duckdb.connect()
    try:
        conn.execute(
            "CREATE TABLE lice_records (id BIGINT, year INTEGER, week INTEGER, "
            "avg_adult_female_lice DOUBLE)"
        )
        src = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            latest = src.execute(SQL_LATEST_WEEK).fetchone()
            if not latest:
                raise RuntimeError("lice_records is empty")
            year, week = latest

            def load_rows(rows: list) -> None:
                # Chunked multi-row INSERT: duckdb's executemany() inserts
                # row-by-row and is far too slow for the full-table variant.
                chunk_size = 20000
                for i in range(0, len(rows), chunk_size):
                    chunk = rows[i:i + chunk_size]
                    placeholders = ",".join("(?,?,?,?)" for _ in chunk)
                    flat = [v for row in chunk for v in row]
                    conn.execute(
                        f"INSERT INTO lice_records VALUES {placeholders}", flat
                    )

            def run() -> tuple[dict, float]:
                t0 = time.perf_counter()
                conn.execute("DELETE FROM lice_records")
                if full_table:
                    rows = src.execute(
                        "SELECT id, year, week, avg_adult_female_lice FROM lice_records"
                    ).fetchall()
                else:
                    rows = src.execute(
                        "SELECT id, year, week, avg_adult_female_lice FROM lice_records "
                        "WHERE year = ? AND week = ?",
                        (year, week),
                    ).fetchall()
                load_rows(rows)
                main = conn.execute(SQL_MAIN_STATS, [year, week]).fetchone()
                above = conn.execute(SQL_ABOVE_THRESHOLD, [year, week]).fetchone()[0]
                sq_sum = conn.execute(SQL_SQ_SUM, [year, week]).fetchone()[0]
                return (
                    _summary_from_results(latest, main, above, sq_sum) | {"_rows_loaded": len(rows)},
                    (time.perf_counter() - t0) * 1000,
                )

            _summary, _ = run()
            times = [run()[1] for _ in range(TIMING["runs"])]
            return run()[0] | {"_latest": latest}, times
        finally:
            src.close()
    finally:
        conn.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="lice weekly-summary read-path benchmark")
    ap.add_argument("--db", default="data/openclaw.db", help="SQLite database path")
    ap.add_argument("--runs", type=int, default=5, help="timed runs per candidate")
    args = ap.parse_args()
    TIMING["runs"] = max(1, args.runs)

    db_path = str(Path(args.db).resolve())
    if not Path(db_path).exists():
        print(f"ERROR: database not found: {db_path}")
        return 1

    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as c:
        n_rows = c.execute("SELECT count(*) FROM lice_records").fetchone()[0]

    candidates = [
        ("A. sqlite-baseline", "current /api/lice/summary SQL, stdlib sqlite3", bench_sqlite),
        ("B. duckdb-sqlite", "DuckDB sqlite_scanner ATTACH", bench_duckdb_sqlite),
        ("C1. duckdb-rowload-latest", "latest-week rows -> in-memory DuckDB",
         lambda p: bench_duckdb_rowload(p, False)),
        ("C2. duckdb-rowload-full", "full-table rows -> in-memory DuckDB",
         lambda p: bench_duckdb_rowload(p, True)),
    ]

    print(f"DB: {db_path}")
    print(f"lice_records rows: {n_rows:,}   runs per candidate: {TIMING['runs']} (after 1 warmup)\n")

    results: dict = {}
    reference: dict | None = None
    for name, desc, fn in candidates:
        entry: dict = {"description": desc}
        try:
            summary, times = fn(db_path)
            entry["status"] = "ok"
            entry["median_ms"] = round(statistics.median(times), 1)
            entry["min_ms"] = round(min(times), 1)
            entry["max_ms"] = round(max(times), 1)
            entry["runs_ms"] = [round(t, 1) for t in times]
            entry["summary"] = {k: v for k, v in summary.items() if not k.startswith("_")}
            if "_rows_loaded" in summary:
                entry["rows_loaded"] = summary["_rows_loaded"]
            comparable = entry["summary"]
            if reference is None:
                reference = comparable
                entry["match"] = True
            else:
                entry["match"] = comparable == reference
        except Exception as exc:  # noqa: BLE001 — a bench must report, never crash
            entry["status"] = f"FAILED: {type(exc).__name__}: {exc}"
        results[name] = entry
        status = entry["status"]
        line = f"{name:<28} {status}"
        if status == "ok":
            line += (
                f"  median {entry['median_ms']} ms"
                f"  (min {entry['min_ms']} / max {entry['max_ms']})  match={entry['match']}"
            )
        print(line)

    print("\n--- JSON ---")
    print(json.dumps(results, indent=2))

    ok_a = results["A. sqlite-baseline"].get("status") == "ok"
    ok_b = results["B. duckdb-sqlite"].get("status") == "ok"
    ok_matches = all(
        e.get("match") for e in results.values() if e.get("status") == "ok"
    )
    if ok_a and ok_b:
        speedup = results["A. sqlite-baseline"]["median_ms"] / results["B. duckdb-sqlite"]["median_ms"]
        if not ok_matches:
            verdict = "HOLD: candidates disagree (match=false) — fix before deciding"
        elif speedup >= 1.5:
            verdict = "SHIP candidate B"
        else:
            verdict = "CLOSE P0-2 (no >=1.5x win)"
        print(f"\nVerdict: B/A speedup = {speedup:.2f}x, all-match={ok_matches} -> {verdict}")
    else:
        print("\nVerdict: cannot compare (a candidate failed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

