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

DEMO_MARKERS = ("demo", "seed", "synthetic", "mock", "fallback")


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


SOURCES: tuple[SourceSpec, ...] = (
    SourceSpec(
        key="lice_records",
        label="Sea lice observations",
        table="lice_records",
        upstream="Fiskeridir / Mattilsynet lice reporting",
        expected_cadence_hours=168,
        refresh_hint="agents: lice ingest (weekly upstream cadence)",
        critical=True,
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
        expected_cadence_hours=24,
        refresh_hint="python scripts/backtest_price_ml.py, then the price agent",
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
        label="Published indices (AI-STI / AI-LPI)",
        table="index_observations",
        upstream="core.market.indices",
        expected_cadence_hours=168,
        refresh_hint="publish_week() via POST /api/indices/publish or the weekly job",
        critical=True,
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
    running the monitor against the real dev database).
    """
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value if value.tzinfo else value.replace(tzinfo=dt.UTC)
    if isinstance(value, dt.date):
        return dt.datetime(value.year, value.month, value.day, tzinfo=dt.UTC)
    if isinstance(value, (int, float)):
        try:
            return dt.datetime.fromtimestamp(float(value), tz=dt.UTC)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        text_value = value.strip().replace("Z", "+00:00")
        if text_value.endswith(" UTC"):
            text_value = text_value[:-4] + "+00:00"
        for candidate in (text_value, text_value.replace(" ", "T")):
            try:
                parsed = dt.datetime.fromisoformat(candidate)
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.UTC)
            except ValueError:
                continue
    return None


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
                }
            )
            rows.append(entry)
            continue

        columns = [c["name"] for c in inspector.get_columns(spec.table)]
        timestamp_column = next((c for c in TIMESTAMP_CANDIDATES if c in columns), None)
        try:
            with engine.connect() as conn:
                count = (
                    conn.execute(text(f'SELECT COUNT(*) FROM "{spec.table}"')).scalar()
                    or 0
                )
                latest = None
                if timestamp_column:
                    latest = conn.execute(
                        text(f'SELECT MAX("{timestamp_column}") FROM "{spec.table}"')
                    ).scalar()
                synthetic = None
                if _has_source_column(columns) and count:
                    synthetic = conn.execute(
                        text(
                            f'SELECT COUNT(*) FROM "{spec.table}" '
                            "WHERE LOWER(COALESCE(source, '')) LIKE '%demo%' "
                            "OR LOWER(COALESCE(source, '')) LIKE '%seed%' "
                            "OR LOWER(COALESCE(source, '')) LIKE '%synthetic%' "
                            "OR LOWER(COALESCE(source, '')) LIKE '%mock%'"
                        )
                    ).scalar()
        except Exception as exc:  # pragma: no cover - defensive
            entry.update(
                {
                    "status": "unknown",
                    "reason": f"query failed: {exc}",
                    "rows": 0,
                    "latest": None,
                    "staleness_hours": None,
                    "synthetic_rows": None,
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
                "status": _status(staleness, spec.expected_cadence_hours),
            }
        )
        if entry["synthetic_only"]:
            entry["reason"] = (
                "contains only synthetic (demo/seed) rows — it cannot back a live "
                "data claim"
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
        "note": (
            "'unknown' and 'synthetic_only' are reported as-is: a source with no "
            "measurable freshness, or backed only by synthetic rows, must never be "
            "presented as live."
        ),
    }
