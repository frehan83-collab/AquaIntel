"""Per-source data freshness monitor.

Answers the question a paying customer actually asks: *is the data behind this
number current, and when did it last arrive?* One row per source with the latest
observation, observed staleness against the expected cadence, whether the table
holds ONLY synthetic rows, and a concrete refresh hint.

Honest by construction: a source whose timestamp column cannot be found, or whose
table is missing, is reported as ``unknown`` — never as "fresh".
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Iterable

import structlog
from sqlalchemy import inspect, text

from core.market.index_publication import FRESHNESS_CADENCE_HOURS, PUBLISHER
from core.source_lineage import (
    LICE_CADENCE_HOURS,
    LICE_SOURCE_LABEL,
    REAL_LICE_SOURCES,
    SYNTHETIC_MARKERS,
    parse_timestamp,
)

log = structlog.get_logger(__name__)

# Candidate timestamp columns, in preference order (the first present is used).
TIMESTAMP_CANDIDATES: tuple[str, ...] = (
    "observed_at",
    "assessed_at",
    "recorded_at",
    "fetched_at",
    "created_at",
    "updated_at",
    "timestamp",
    "updated",
    "date",
    "week_start",
)

# One definition (core/source_lineage.py); the SQL below is built from it so the
# Python tuple and the query can never disagree again (the SQL used to omit
# 'fallback').
DEMO_MARKERS = SYNTHETIC_MARKERS
_SYNTHETIC_SQL = " OR ".join(
    f"LOWER(TRIM(COALESCE(source, ''))) LIKE '%{marker}%'" for marker in DEMO_MARKERS
)


@dataclass(frozen=True)
class SourceSpec:
    """One monitored source. `expected_cadence_hours` drives the status."""

    key: str
    label: str
    table: str
    upstream: str
    expected_cadence_hours: int
    refresh_hint: str
    critical: bool = False
    #: Source values that count as verified for this table (WS-1 lineage
    #: contract). Empty = no contract declared: verified/unverified not measured.
    real_sources: frozenset = frozenset()
    #: Rows whose value in this column is set do not count (WS-19: an index
    #: observation of a withdrawn method is superseded, not current). Applied only
    #: when the column exists.
    excluded_when_set: str | None = None


SOURCES: tuple[SourceSpec, ...] = (
    SourceSpec(
        key="lice_records",
        label="Sea lice observations",
        table="lice_records",
        upstream=LICE_SOURCE_LABEL,
        expected_cadence_hours=LICE_CADENCE_HOURS,
        refresh_hint="agents: lice ingest (weekly upstream cadence)",
        critical=True,
        real_sources=REAL_LICE_SOURCES,
    ),
    SourceSpec(
        key="ssb_weekly_prices",
        label="SSB weekly salmon export prices",
        table="ssb_weekly_prices",
        upstream="Statistics Norway (SSB) API",
        expected_cadence_hours=168,
        refresh_hint="agents: SSB ingest",
        critical=True,
    ),
    SourceSpec(
        key="export_volumes",
        label="Export volumes",
        table="export_volumes",
        upstream="SSB / Norwegian Seafood Council",
        expected_cadence_hours=168,
        refresh_hint="agents: SSB ingest",
    ),
    SourceSpec(
        key="chlorophyll_readings",
        label="Chlorophyll / bloom indicators",
        table="chlorophyll_readings",
        upstream="Copernicus Marine / Sentinel-3",
        expected_cadence_hours=72,
        refresh_hint="agents: satellite ingest",
    ),
    SourceSpec(
        key="bloom_risk_assessments",
        label="Bloom risk assessments",
        table="bloom_risk_assessments",
        upstream="core.market.bloom engine",
        expected_cadence_hours=24,
        refresh_hint="agents: bloom engine",
    ),
    SourceSpec(
        key="futures_snapshots",
        label="Salmon futures snapshots",
        table="futures_snapshots",
        upstream="Fish Pool / Euronext (licensed)",
        expected_cadence_hours=24,
        refresh_hint="agents: futures feed",
    ),
    SourceSpec(
        key="supply_forecasts",
        label="Supply forecasts",
        table="supply_forecasts",
        upstream="core.market.supply_demand_engine",
        expected_cadence_hours=24,
        refresh_hint="agents: supply engine",
    ),
    SourceSpec(
        key="price_predictions",
        label="Price predictions",
        table="price_predictions",
        upstream="core.market.price_ml ensemble",
        # WS-23: the outlook stores at most one prediction per ISO week and horizon
        expected_cadence_hours=168,
        refresh_hint="GET /api/market/price-outlook stores one prediction per ISO week and horizon (live spot only)",
    ),
    SourceSpec(
        key="harvest_timing",
        label="Harvest timing recommendations",
        table="harvest_timing",
        upstream="core.market harvest optimizer",
        expected_cadence_hours=24,
        refresh_hint="agents: harvest optimizer",
    ),
    SourceSpec(
        key="index_observations",
        label="Published indices (AI-STI)",
        table="index_observations",
        upstream="core.market.indices",
        # weekly publication plus one hourly tick of phase (WS-2: one definition)
        expected_cadence_hours=FRESHNESS_CADENCE_HOURS,
        refresh_hint=PUBLISHER,
        critical=True,
        excluded_when_set="superseded_by",
    ),
    SourceSpec(
        key="treatment_outcomes",
        label="Treatment outcomes",
        table="treatment_outcomes",
        upstream="Producer-reported treatments",
        expected_cadence_hours=168,
        refresh_hint="farm/mobile capture",
    ),
    SourceSpec(
        key="eudr_compliance",
        label="EUDR compliance records",
        table="eudr_compliance",
        upstream="Producer / importer submissions",
        expected_cadence_hours=720,
        refresh_hint="compliance ingest",
    ),
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _status(staleness_hours: float | None, cadence_hours: int) -> str:
    if staleness_hours is None:
        return "unknown"
    if staleness_hours <= cadence_hours:
        return "fresh"
    if staleness_hours <= cadence_hours * 3:
        return "stale"
    return "dead"


def _has_source_column(columns: Iterable[str]) -> bool:
    return "source" in {c.lower() for c in columns}


def _is_synthetic(source: str | None) -> bool:
    if source is None:
        return False
    lowered = str(source).lower()
    return any(marker in lowered for marker in DEMO_MARKERS)


def _parse_timestamp(value) -> dt.datetime | None:
    """Coerce a DB timestamp to an aware datetime.

    SQLite returns ISO-8601 **strings** here while PostgreSQL returns datetimes —
    without this, every source reported "unknown" freshness on SQLite (found by
    running the monitor against the real dev database). One implementation:
    ``core.source_lineage.parse_timestamp``.
    """
    return parse_timestamp(value)


async def report(specs: tuple[SourceSpec, ...] = SOURCES) -> dict:
    """Freshness report for every monitored source (read-only)."""
    import asyncio

    return await asyncio.to_thread(_report_sync, specs)


def _report_sync(specs: tuple[SourceSpec, ...]) -> dict:
    from core.models import engine

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    now = dt.datetime.now(dt.UTC)
    rows: list[dict] = []

    for spec in specs:
        entry: dict = {
            "key": spec.key,
            "label": spec.label,
            "table": spec.table,
            "upstream": spec.upstream,
            "expected_cadence_hours": spec.expected_cadence_hours,
            "refresh_hint": spec.refresh_hint,
            "critical": spec.critical,
        }
        if spec.table not in tables:
            entry.update(
                {
                    "status": "unknown",
                    "reason": "table missing — never ingested in this environment",
                    "rows": 0,
                    "latest": None,
                    "staleness_hours": None,
                    "synthetic_rows": None,
                    "verified_rows": None,
                    "unverified_rows": None,
                    "no_verified_rows": False,
                }
            )
            rows.append(entry)
            continue

        columns = [c["name"] for c in inspector.get_columns(spec.table)]
        timestamp_column = next((c for c in TIMESTAMP_CANDIDATES if c in columns), None)
        scope = (
            f' WHERE "{spec.excluded_when_set}" IS NULL'
            if spec.excluded_when_set and spec.excluded_when_set in columns
            else ""
        )
        try:
            with engine.connect() as conn:
                count = (
                    conn.execute(text(f'SELECT COUNT(*) FROM "{spec.table}"{scope}')).scalar()
                    or 0
                )
                excluded = (
                    conn.execute(
                        text(
                            f'SELECT COUNT(*) FROM "{spec.table}" '
                            f'WHERE "{spec.excluded_when_set}" IS NOT NULL'
                        )
                    ).scalar()
                    or 0
                    if scope
                    else None
                )
                latest = None
                if timestamp_column:
                    latest = conn.execute(
                        text(f'SELECT MAX("{timestamp_column}") FROM "{spec.table}"{scope}')
                    ).scalar()
                synthetic = None
                verified = None
                if _has_source_column(columns) and count:
                    synthetic = (
                        conn.execute(
                            text(
                                f'SELECT COUNT(*) FROM "{spec.table}" WHERE ({_SYNTHETIC_SQL})'
                                + scope.replace(" WHERE ", " AND ")
                            )
                        ).scalar()
                        or 0
                    )
                    if spec.real_sources:
                        params = {
                            f"s{i}": str(value).lower()
                            for i, value in enumerate(sorted(spec.real_sources))
                        }
                        placeholders = ", ".join(f":{key}" for key in params)
                        verified = (
                            conn.execute(
                                text(
                                    f'SELECT COUNT(*) FROM "{spec.table}" '
                                    f"WHERE LOWER(TRIM(COALESCE(source, ''))) IN ({placeholders})"
                                    + scope.replace(" WHERE ", " AND ")
                                ),
                                params,
                            ).scalar()
                            or 0
                        )
        except Exception as exc:  # pragma: no cover - defensive
            entry.update(
                {
                    "status": "unknown",
                    "reason": f"query failed: {exc}",
                    "rows": 0,
                    "latest": None,
                    "staleness_hours": None,
                    "synthetic_rows": None,
                    "verified_rows": None,
                    "unverified_rows": None,
                    "no_verified_rows": False,
                }
            )
            rows.append(entry)
            continue

        staleness = None
        parsed_latest = _parse_timestamp(latest)
        if parsed_latest is not None:
            staleness = round((now - parsed_latest).total_seconds() / 3600.0, 2)

        entry.update(
            {
                "rows": count,
                "timestamp_column": timestamp_column,
                "latest": parsed_latest.isoformat()
                if parsed_latest is not None
                else (str(latest) if latest is not None else None),
                "staleness_hours": staleness,
                "synthetic_rows": synthetic,
                "synthetic_only": bool(count and synthetic == count),
                # WS-1 lineage contract: rows are verified (a declared real source),
                # synthetic, or unverified (NULL/'unverified'/unknown — never real).
                "verified_rows": verified,
                "unverified_rows": (
                    count - synthetic - verified
                    if synthetic is not None and verified is not None
                    else None
                ),
                "no_verified_rows": bool(count and verified == 0),
                # WS-19: rows marked in `excluded_when_set` (superseded) do not count
                "excluded_rows": excluded,
                "status": _status(staleness, spec.expected_cadence_hours),
            }
        )
        if entry["synthetic_only"]:
            entry["reason"] = (
                "contains only synthetic (demo/seed) rows — it cannot back a live "
                "data claim"
            )
        elif entry["no_verified_rows"]:
            entry["reason"] = (
                "holds no row with a verified source (rows are synthetic or "
                "unverified) — it cannot back a live data claim"
            )
        elif not count and excluded:
            entry["reason"] = (
                f"no current rows: all {excluded} row(s) are marked "
                f"{spec.excluded_when_set} and do not count"
            )
        if timestamp_column is None:
            entry["reason"] = "no timestamp column found — freshness not measurable"
        rows.append(entry)

    return {
        "as_of": now.isoformat(),
        "sources": rows,
        "counts": {
            "total": len(rows),
            "fresh": sum(1 for r in rows if r.get("status") == "fresh"),
            "stale": sum(1 for r in rows if r.get("status") == "stale"),
            "dead": sum(1 for r in rows if r.get("status") == "dead"),
            "unknown": sum(1 for r in rows if r.get("status") == "unknown"),
        },
        "critical_unknown": [
            r["key"] for r in rows if r.get("critical") and r.get("status") == "unknown"
        ],
        "synthetic_only": [r["key"] for r in rows if r.get("synthetic_only")],
        "no_verified_rows": [r["key"] for r in rows if r.get("no_verified_rows")],
        "note": (
            "'unknown' and 'synthetic_only' are reported as-is: a source with no "
            "measurable freshness, or backed only by synthetic rows, must never be "
            "presented as live. `unverified_rows` carry no verified source "
            "(neither synthetic nor live-backing); `no_verified_rows` lists sources "
            "that hold no verified row at all."
        ),
    }
