"""Production truth checks — make the known production gaps *detectable*.

AGENTS.md lists operational gaps that stayed invisible until something failed:
production Docker ran API-only so the 12 agents never executed; model artifacts
live in the gitignored ``data/`` so they are absent in CI/prod; PG/Timescale was
never verified; freshness was unknowable. This module turns each into a check with
a verdict, so a deploy fails loudly instead of silently serving a degraded product.

Used by ``scripts/verify_production_truth.py`` and by tests.
"""
from __future__ import annotations

import os
from pathlib import Path

import structlog

log = structlog.get_logger(__name__)

ROOT = Path(__file__).resolve().parents[1]
PROD_COMPOSE = ROOT / "docker-compose.prod.yml"
MODEL_DIR = ROOT / "data" / "models"
ACCURACY_DIR = ROOT / "artifacts" / "accuracy"

COMPOSE_REQUIRED_SERVICES = ("api", "agents", "db")


def _verdict(status: str, name: str, detail: str, critical: bool = False) -> dict:
    return {"check": name, "status": status, "detail": detail, "critical": critical}


def check_environment() -> list[dict]:
    """Production environment must be explicit and safely configured."""
    env = os.environ.get("FISHINTEL_ENV", "development")
    secret = os.environ.get("FISHINTEL_JWT_SECRET", "")
    out = [_verdict("ok", "environment", f"FISHINTEL_ENV={env}")]
    if env != "production":
        out.append(
            _verdict(
                "info",
                "production_mode",
                "not production — production-only checks are advisory here",
            )
        )
        return out
    if len(secret) < 32:
        out.append(
            _verdict(
                "fail",
                "jwt_secret",
                f"FISHINTEL_JWT_SECRET is {len(secret)} chars; production requires >= 32",
                critical=True,
            )
        )
    else:
        out.append(_verdict("ok", "jwt_secret", ">= 32 chars"))
    return out


def check_agents_service(compose_path: Path = PROD_COMPOSE) -> list[dict]:
    """The agents must run as their own service (they never did in production)."""
    if not compose_path.exists():
        return [
            _verdict(
                "fail",
                "agents_service",
                f"{compose_path.name} is missing — production topology undefined",
                critical=True,
            )
        ]
    text = compose_path.read_text(encoding="utf-8")
    out: list[dict] = []
    for service in COMPOSE_REQUIRED_SERVICES:
        if f"\n  {service}:" in text:
            out.append(_verdict("ok", f"compose_service_{service}", "declared"))
        else:
            critical = service in ("agents", "db")
            out.append(
                _verdict(
                    "fail" if critical else "warn",
                    f"compose_service_{service}",
                    f"service '{service}' not declared in {compose_path.name}",
                    critical=critical,
                )
            )
    if "--agents-only" in text:
        out.append(
            _verdict("ok", "agents_entrypoint", "uses `python main.py --agents-only`")
        )
    else:
        out.append(
            _verdict(
                "warn",
                "agents_entrypoint",
                "agents service does not reference `--agents-only`; verify its command",
            )
        )
    return out


def _alembic_head() -> str | None:
    """Head revision from the versions directory (no alembic runtime needed)."""
    versions = ROOT / "alembic" / "versions"
    revisions: dict[str, str | None] = {}
    parents: set[str] = set()
    for path in versions.glob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        revision = None
        down = None
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("revision ="):
                revision = stripped.split("=", 1)[1].strip().strip("\"'")
            elif stripped.startswith("down_revision ="):
                raw = stripped.split("=", 1)[1].strip()
                down = None if raw.startswith("None") else raw.strip("\"'")
        if revision:
            revisions[revision] = down
            if down:
                parents.add(down)
    heads = sorted(rev for rev in revisions if rev not in parents)
    return heads[0] if heads else None


def _lice_source_column_verdict(engine) -> dict:
    """WS-1: the lice ingest writes `lice_records.source`.

    A database that never ran migration 019 — typically an empty `alembic_version`
    where the chain aborts at 001 (HANDOVER trap 7) — would fail every lice insert
    with "no such column". Recovery: `alembic stamp 018` then `alembic upgrade head`
    (never stamp head directly: that freezes the column out).
    """
    from sqlalchemy import inspect

    try:
        insp = inspect(engine)
        if not insp.has_table("lice_records"):
            return _verdict(
                "info", "lice_source_column", "lice_records table absent (never ingested here)"
            )
        column = next(
            (c for c in insp.get_columns("lice_records") if c["name"].lower() == "source"),
            None,
        )
    except Exception as exc:  # pragma: no cover - defensive
        return _verdict("warn", "lice_source_column", f"could not inspect lice_records: {exc}")
    if column is None:
        return _verdict(
            "fail",
            "lice_source_column",
            "lice_records has no `source` column — migration 019 never ran, every lice "
            "ingest insert will fail; recover with `alembic stamp 018` then "
            "`alembic upgrade head`",
            critical=True,
        )
    if column.get("nullable", True) or column.get("default") is None:
        # The shape a schema reconciliation (not 019) produces: NULL rows classify
        # as unverified (honest) but demo rows were never relabelled and the DDL
        # diverges from the ORM contract.
        return _verdict(
            "warn",
            "lice_source_column",
            "lice_records.source exists but is nullable or has no default — it was "
            "added by a schema reconciliation, not by migration 019; run "
            "`alembic stamp 018` then `alembic upgrade head` so 019 backfills and "
            "repairs it",
        )
    return _verdict(
        "ok", "lice_source_column", "lice_records.source present, NOT NULL with default (WS-1)"
    )


def check_database() -> list[dict]:
    """Dialect, reachability and migration head (the ORM/migration drift check)."""
    out: list[dict] = []
    from config.settings import settings

    url = str(getattr(settings, "database_url", ""))
    scheme = url.split(":", 1)[0] if url else "unset"
    out.append(_verdict("info", "database_dialect", scheme))
    if os.environ.get("FISHINTEL_ENV") == "production" and scheme.startswith("sqlite"):
        out.append(
            _verdict(
                "fail",
                "database_production_sqlite",
                "production must not use SQLite",
                critical=True,
            )
        )
    try:
        from sqlalchemy import text

        from core.models import engine

        with engine.connect() as conn:
            db_version = conn.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar()
        out.append(_verdict("ok", "database_reachable", "connected"))
    except Exception as exc:
        out.append(
            _verdict("fail", "database_reachable", f"cannot query: {exc}", critical=True)
        )
        return out

    try:
        head = _alembic_head()
    except Exception as exc:  # pragma: no cover - defensive
        out.append(_verdict("warn", "alembic_head", f"could not read revisions: {exc}"))
        return out
    if db_version == head:
        out.append(_verdict("ok", "alembic_head", f"at head {head}"))
    else:
        out.append(
            _verdict(
                "fail",
                "alembic_head",
                f"DB at {db_version}, code head {head} — schema drift (the "
                "ORM-vs-migration gap AGENTS.md warns about)",
                critical=True,
            )
        )
    out.append(_lice_source_column_verdict(engine))
    return out


def check_artifacts() -> list[dict]:
    """Model weights + published accuracy artifacts: present, or declared absent."""
    out: list[dict] = []
    model_files = sorted(p.name for p in MODEL_DIR.glob("*.*")) if MODEL_DIR.exists() else []
    if model_files:
        out.append(
            _verdict("ok", "model_artifacts", f"{len(model_files)} file(s) in data/models")
        )
    else:
        out.append(
            _verdict(
                "warn",
                "model_artifacts",
                "no model weights in data/models — foundation models cannot load, so "
                "every forecast is the honest seasonal-naive fallback (disclosed via "
                "provenance). Ship them as a release artifact or mount a volume.",
            )
        )
    accuracy = (
        sorted(p.name for p in ACCURACY_DIR.glob("*.json")) if ACCURACY_DIR.exists() else []
    )
    if accuracy:
        out.append(
            _verdict("ok", "accuracy_artifacts", f"{len(accuracy)} published artifact(s)")
        )
    else:
        out.append(
            _verdict(
                "warn",
                "accuracy_artifacts",
                "no published accuracy artifact — /api/accuracy reports 'not yet "
                "published' (run scripts/publish_accuracy.py where real data exists)",
            )
        )
    return out


async def check_freshness() -> list[dict]:
    """Critical sources with unknown freshness, and synthetic-only tables."""
    from core.market.freshness_monitor import report

    data = await report()
    out: list[dict] = []
    unknown = data.get("critical_unknown") or []
    out.append(
        _verdict(
            "warn" if unknown else "ok",
            "freshness_critical_unknown",
            "unknown freshness for critical sources: " + ", ".join(unknown)
            if unknown
            else "all critical sources measurable",
        )
    )
    synthetic = data.get("synthetic_only") or []
    out.append(
        _verdict(
            "warn" if synthetic else "ok",
            "freshness_synthetic_only",
            "sources backed only by synthetic rows: " + ", ".join(synthetic)
            if synthetic
            else "no synthetic-only sources",
        )
    )
    no_verified = data.get("no_verified_rows") or []
    out.append(
        _verdict(
            "warn" if no_verified else "ok",
            "freshness_no_verified_rows",
            "sources holding no row with a verified source (synthetic or "
            "unverified only): " + ", ".join(no_verified)
            if no_verified
            else "every source with a lineage contract holds verified rows",
        )
    )
    counts = data.get("counts", {})
    out.append(
        _verdict(
            "info",
            "freshness_counts",
            f"fresh={counts.get('fresh')} stale={counts.get('stale')} "
            f"dead={counts.get('dead')} unknown={counts.get('unknown')}",
        )
    )
    return out


async def check_index_publication() -> list[dict]:
    """WS-2: the weekly index publication must actually have run this ISO week.

    Reads the store (not the scheduler), so a scheduler that silently stopped is
    a named warning instead of an assumption.
    """
    from core.market import index_publication

    try:
        state = await index_publication.status()
    except Exception as exc:  # pragma: no cover - status() reports, not raises
        return [
            _verdict(
                "warn",
                "index_publication_current_week",
                f"could not read the index publication status: {exc}",
            )
        ]
    out: list[dict] = []
    if state.get("current_week_published"):
        degraded = state.get("degraded_current") or []
        out.append(
            _verdict(
                "ok",
                "index_publication_current_week",
                f"{state['week']} published for {', '.join(index_publication.INDEX_CODES)} "
                f"(method {state['version']})"
                + (
                    f"; degraded this week: {', '.join(degraded)} (provenance says why)"
                    if degraded
                    else ""
                ),
            )
        )
    else:
        missing_codes = list(state.get("missing") or [])
        missing = ", ".join(missing_codes)
        reason = state.get("reason")
        entries = state.get("indices") or {}
        stored_now = [
            code for code, entry in entries.items() if (entry or {}).get("current_week_published")
        ]
        # The wait is judged per MISSING index: last week stored for each of them.
        previous_present = bool(missing_codes) and all(
            (entries.get(code) or {}).get("weeks_behind") == 1 for code in missing_codes
        )
        remedy = (
            "; start the agents service, or POST /api/indices/publish (same readiness "
            "gate; force=true with a reason overrides the grace, audited)"
        )
        no_history = bool(missing_codes) and all(
            (entries.get(code) or {}).get("weeks_behind") is None for code in missing_codes
        )
        if state.get("within_grace") and no_history and not reason and not stored_now:
            # First week at this method version (or a fresh store): a waiting
            # publisher and a stopped one look the same from the store — say so.
            out.append(
                _verdict(
                    "warn",
                    "index_publication_current_week",
                    f"{state['week']} not published for: {missing} and there is no "
                    f"observation at method {state.get('version')} yet; within the "
                    f"{state.get('readiness_grace_hours')} h readiness grace the store cannot "
                    "tell a waiting publisher from a stopped one — check the publisher's "
                    "health (`waiting` / `last_failure`)" + remedy,
                )
            )
        elif state.get("within_grace") and previous_present and not reason:
            # Designed state: last week is stored and this week's value is still
            # within the readiness grace — the agent is waiting for a live value.
            out.append(
                _verdict(
                    "info",
                    "index_publication_current_week",
                    f"{state['week']} not yet published for: {missing} — within the "
                    f"{state.get('readiness_grace_hours')} h readiness grace "
                    f"({state.get('hours_into_week')} h into the week); last week is stored"
                    + (f"; already stored this week: {', '.join(stored_now)}" if stored_now else ""),
                )
            )
        elif stored_now and not reason:
            # The agent demonstrably ran (an index is stored this week): the other
            # is withheld or failed — say that, never "the agent has not run".
            out.append(
                _verdict(
                    "warn",
                    "index_publication_current_week",
                    f"{state['week']} stored for {', '.join(stored_now)} but not for: {missing} "
                    "— withheld (no value, or degraded past the grace) or its store failed; "
                    "see the publisher's `waiting` / `last_failure`" + remedy,
                )
            )
        else:
            out.append(
                _verdict(
                    "warn",
                    "index_publication_current_week",
                    f"{state['week']} not published for: {missing} — the index_publisher "
                    "agent has not run (or failed) this week"
                    + (f" ({reason})" if reason else "")
                    + remedy,
                )
            )
    ahead = [
        code for code, entry in (state.get("indices") or {}).items()
        if (entry or {}).get("store_ahead_of_clock")
    ]
    if ahead:
        out.append(
            _verdict(
                "warn",
                "index_publication_store_ahead_of_clock",
                "the store holds observations for a FUTURE week for: " + ", ".join(ahead)
                + " — clock skew or an as_of override; those rows are immutable",
            )
        )
    skipped = state.get("skipped_weeks") or []
    interval_ok = state.get("interval_ok")
    if interval_ok is None:
        out.append(
            _verdict(
                "info",
                "index_publication_interval",
                "interval not measurable yet (fewer than two observations, or the store "
                "unreadable)",
            )
        )
    elif interval_ok:
        out.append(
            _verdict(
                "ok",
                "index_publication_interval",
                "consecutive stored observations are consecutive ISO weeks",
            )
        )
    else:
        out.append(
            _verdict(
                "warn",
                "index_publication_interval",
                "a week was skipped in the stored series: " + ", ".join(skipped)
                + " — the publisher did not run (or failed all week); skipped weeks are "
                "never backfilled",
            )
        )
    return out


async def run_checks(*, include_freshness: bool = True) -> dict:
    """Run every check and summarise the truth gaps."""
    checks: list[dict] = []
    checks += check_environment()
    checks += check_agents_service()
    checks += check_database()
    checks += check_artifacts()
    checks += await check_index_publication()
    if include_freshness:
        checks += await check_freshness()

    failures = [c for c in checks if c["status"] == "fail"]
    warnings = [c for c in checks if c["status"] == "warn"]
    return {
        "checks": checks,
        "failed": len(failures),
        "warnings": len(warnings),
        "critical_failures": [c["check"] for c in failures if c["critical"]],
        "truth_gaps": [c["detail"] for c in checks if c["status"] in ("fail", "warn")],
    }
