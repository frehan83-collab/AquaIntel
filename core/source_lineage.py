"""Source lineage — ONE definition of what a `source` value on a data row means.

WS-1 (docs/HANDOVER.md): `lice_records` gained a `source` column so demo seeds,
reported BarentsWatch rows and pre-migration rows can be told apart. Every
consumer that reasons about lice lineage (the named indices, the lice quota
tracker, the freshness monitor, the production-truth verifier) imports from
here, so there is no second copy of the markers to drift (rule 8 spirit:
one definition, projections elsewhere).

Vocabulary for `lice_records.source` (closed):

  ``barentswatch``  written by agents/data_ingest.py on BOTH branches of its
                    upsert — the BarentsWatch Fishhealth API v2, which publishes
                    the weekly lice counts farms report to Mattilsynet. The
                    historical backfill agent reuses the same writer.
  ``demo_seed``     written by core/demo_seed.py (synthetic, never live-backing).
  ``unverified``    the server default. Pre-WS-1 rows carry it: their origin has
                    no row-level proof, so they never count as real.

NULL, '' and any string outside the vocabulary classify as ``unverified``: an
unknown origin is never real. Any value containing a synthetic marker
(``demo``, ``seed``, ``synthetic``, ``mock``, ``fallback``) is synthetic.

A lineage *summary* describes the rows a computation actually used, and a
value may claim ``is_live`` only when every used row is real, every production
area contributed rows without a fetch failure, the newest **observation week**
is current (reports are weekly, so the current or previous ISO week), and the
newest row was *fetched* within the upstream cadence — per production area as
well as overall. Anything else yields a ``note`` naming why (rule 1 of
AGENTS.md: a fallback is never presented as live). The observation-week gate
exists because ``fetched_at`` is a write time: a re-ingest of an old week bumps
it, and must not make six-month-old observations look current.
"""
from __future__ import annotations

import datetime as dt
from typing import Any, Iterable, Mapping

LICE_SOURCE_BARENTSWATCH = "barentswatch"
LICE_SOURCE_DEMO = "demo_seed"
LICE_SOURCE_UNVERIFIED = "unverified"

#: Source values that count as a verified, reported observation.
REAL_LICE_SOURCES: frozenset[str] = frozenset({LICE_SOURCE_BARENTSWATCH})

#: A `source` containing any of these is synthetic. The freshness monitor and
#: the accuracy publisher import this tuple — do not copy it elsewhere.
SYNTHETIC_MARKERS: tuple[str, ...] = ("demo", "seed", "synthetic", "mock", "fallback")

REAL = "real"
SYNTHETIC = "synthetic"
UNVERIFIED = "unverified"

#: Weekly upstream reporting (the freshness SourceSpec for lice reads this).
LICE_CADENCE_HOURS = 168
#: A reported week counts as current while it is the current or the previous
#: ISO week (this week's reports arrive during the week).
LICE_MAX_OBSERVATION_AGE_WEEKS = 1

LICE_SOURCE_LABEL = "BarentsWatch Fishhealth API v2 (Mattilsynet-reported lice counts)"


def classify_source(value: Any, real_sources: Iterable[str] = REAL_LICE_SOURCES) -> str:
    """Classify a raw `source` value as real | synthetic | unverified."""
    if value is None:
        return UNVERIFIED
    text = str(value).strip().lower()
    if not text:
        return UNVERIFIED
    if any(marker in text for marker in SYNTHETIC_MARKERS):
        return SYNTHETIC
    if text in {str(s).lower() for s in real_sources}:
        return REAL
    return UNVERIFIED


def classify_lice_source(value: Any) -> str:
    return classify_source(value, REAL_LICE_SOURCES)


def parse_timestamp(value: Any) -> dt.datetime | None:
    """Coerce a DB timestamp to an aware datetime.

    SQLite returns ISO-8601 **strings** and drops tzinfo while PostgreSQL returns
    datetimes (HANDOVER traps 2-3). Returns None when the value is not parseable.
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


def to_utc(now: dt.datetime | None) -> dt.datetime:
    """Normalise an instant to aware UTC: naive is taken as UTC, aware is converted.

    Every week label the platform stamps or compares (index observations, the
    publication status, the readiness hour) goes through this one function, so a
    non-UTC caller can never build one week and judge another.
    """
    if now is None:
        return dt.datetime.now(dt.UTC)
    if now.tzinfo is None:
        return now.replace(tzinfo=dt.UTC)
    return now.astimezone(dt.UTC)


def _pa_list(values: Iterable[Any]) -> str:
    return ", ".join("?" if v is None else str(v) for v in values)


def _week_tuple(value: Any) -> tuple[int, int] | None:
    """Accept (year, week), [year, week] or a 'YYYY-Www' label."""
    if value is None:
        return None
    try:
        if isinstance(value, str):
            year, week = value.upper().split("-W")
        else:
            year, week = value[0], value[1]
        year, week = int(year), int(week)
        dt.date.fromisocalendar(year, week, 1)  # validates
        return year, week
    except (TypeError, ValueError, IndexError):
        return None


def _weeks_stale(week: tuple[int, int], now: dt.datetime) -> int:
    """Whole ISO weeks between the observation week and the current week."""
    this_week = dt.date.fromisocalendar(*now.isocalendar()[:2], 1)
    observed = dt.date.fromisocalendar(week[0], week[1], 1)
    return max(0, (this_week - observed).days // 7)


def _hours_old(value: Any, now: dt.datetime) -> float | None:
    stamp = parse_timestamp(value)
    if stamp is None:
        return None
    return round((now - stamp).total_seconds() / 3600.0, 2)


def summarise_lineage(
    counts: Mapping[Any, int],
    *,
    year: int | None,
    latest_fetched_at: Any = None,
    latest_week: Any = None,
    pas: Iterable[Mapping[str, Any]] | None = None,
    now: dt.datetime | None = None,
) -> dict:
    """Describe the rows a computation used and whether they support a live claim.

    ``counts`` maps a raw source value (None allowed) to the number of rows used.
    ``latest_week`` is the newest observation week among them, ``(year, week)``.
    ``pas`` lists the production areas queried as ``{pa, rows_used, fetch_failed,
    latest_fetched_at?, latest_week?}`` — the per-PA fields let the national merge
    keep every PA's own staleness instead of hiding it behind the newest one.
    Fail-closed: an unknown observation week or fetch time can never be live.
    The result is JSON-serialisable and immutable in meaning: ``is_live`` is True
    only when ``note`` is None.
    """
    now = now or dt.datetime.now(dt.UTC)
    by_class = {REAL: 0, SYNTHETIC: 0, UNVERIFIED: 0}
    sources: dict[str, int] = {}
    for value, n in counts.items():
        n = int(n or 0)
        label = "null" if value is None else str(value)
        sources[label] = sources.get(label, 0) + n
        by_class[classify_lice_source(value)] += n
    rows_used = sum(by_class.values())

    latest = parse_timestamp(latest_fetched_at)
    staleness_hours = (
        round((now - latest).total_seconds() / 3600.0, 2) if latest is not None else None
    )
    week = _week_tuple(latest_week)
    week_label = f"{week[0]}-W{week[1]:02d}" if week else None
    weeks_stale = _weeks_stale(week, now) if week else None
    pa_rows = [dict(p) for p in (pas or [])]

    notes: list[str] = []
    if rows_used == 0:
        notes.append(
            "lineage unverifiable: no lice rows were used"
            + (f" (year {year})" if year else "")
        )
    else:
        if by_class[SYNTHETIC]:
            notes.append(
                f"lineage: {by_class[SYNTHETIC]}/{rows_used} lice rows used are synthetic "
                "(demo/seed), not reported observations"
            )
        if by_class[UNVERIFIED]:
            notes.append(
                f"lineage unverifiable: {by_class[UNVERIFIED]}/{rows_used} lice rows used "
                "carry no verified source (source='unverified' or NULL — pre-WS-1 rows)"
            )
    failed = [p.get("pa") for p in pa_rows if p.get("fetch_failed")]
    if failed:
        notes.append(f"lineage: lice fetch failed for PA {_pa_list(failed)}")
    empty = [
        p.get("pa") for p in pa_rows if not p.get("fetch_failed") and not p.get("rows_used")
    ]
    if empty and rows_used:
        notes.append(f"lineage: no lice rows in window for PA {_pa_list(empty)}")
    if rows_used:
        if week is None:
            notes.append("lineage unverifiable: newest lice observation week unknown")
        elif weeks_stale > LICE_MAX_OBSERVATION_AGE_WEEKS:
            notes.append(
                f"lineage: newest lice observation is {week_label}, {weeks_stale} weeks "
                "old (reports are weekly)"
            )
        if latest is None:
            notes.append("lineage unverifiable: newest lice row fetch time unknown")
        elif staleness_hours is not None and staleness_hours > LICE_CADENCE_HOURS:
            notes.append(
                f"lineage: newest lice row was fetched {staleness_hours:.0f} h ago "
                f"(cadence {LICE_CADENCE_HOURS} h)"
            )
        # Per-PA staleness: the national view must not hide one stale area behind
        # the newest one.
        stale_weeks = []
        stale_fetch = []
        for p in pa_rows:
            if p.get("fetch_failed") or not p.get("rows_used"):
                continue
            pa_week = _week_tuple(p.get("latest_week"))
            if pa_week is not None:
                age = _weeks_stale(pa_week, now)
                if age > LICE_MAX_OBSERVATION_AGE_WEEKS:
                    stale_weeks.append(f"{p.get('pa')} ({pa_week[0]}-W{pa_week[1]:02d})")
            hours = _hours_old(p.get("latest_fetched_at"), now)
            if hours is not None and hours > LICE_CADENCE_HOURS:
                stale_fetch.append(f"{p.get('pa')} ({hours:.0f} h)")
        if stale_weeks:
            notes.append("lineage: newest observation is older than a week for PA " + ", ".join(stale_weeks))
        if stale_fetch:
            notes.append("lineage: newest row was fetched outside the cadence for PA " + ", ".join(stale_fetch))

    is_live = not notes
    source = (
        LICE_SOURCE_LABEL
        if is_live
        else f"lice_records ({by_class[REAL]}/{rows_used} rows verified)"
    )
    return {
        "year": year,
        "rows_used": rows_used,
        "by_class": by_class,
        "sources": sources,
        "latest_fetched_at": latest.isoformat() if latest is not None else None,
        "staleness_hours": staleness_hours,
        "cadence_hours": LICE_CADENCE_HOURS,
        "latest_week": week_label,
        "weeks_stale": weeks_stale,
        "pas": pa_rows,
        "is_live": is_live,
        "source": source,
        "note": "; ".join(notes) if notes else None,
    }


def merge_lineages(
    items: Iterable[Mapping[str, Any] | None], *, now: dt.datetime | None = None
) -> dict:
    """Aggregate per-PA lineage summaries into one (the national view).

    Every PA's own staleness travels inside its ``pas`` entry, so the merged
    verdict degrades when any contributing area is stale — not only when the
    newest one is. A missing item (a PA that returned no lineage at all) is
    recorded as a failed fetch, never silently dropped.
    """
    counts: dict[Any, int] = {}
    pas: list[dict] = []
    years: list[int] = []
    latest: dt.datetime | None = None
    newest_week: tuple[int, int] | None = None
    for item in items:
        if not item:
            pas.append({"pa": None, "rows_used": 0, "fetch_failed": True})
            continue
        for label, n in (item.get("sources") or {}).items():
            key = None if label == "null" else label
            counts[key] = counts.get(key, 0) + int(n or 0)
        pas.extend(dict(p) for p in (item.get("pas") or []))
        if item.get("year"):
            years.append(int(item["year"]))
        stamp = parse_timestamp(item.get("latest_fetched_at"))
        if stamp is not None and (latest is None or stamp > latest):
            latest = stamp
        week = _week_tuple(item.get("latest_week"))
        if week is not None and (newest_week is None or week > newest_week):
            newest_week = week
    return summarise_lineage(
        counts,
        year=max(years) if years else None,
        latest_fetched_at=latest,
        latest_week=newest_week,
        pas=pas,
        now=now,
    )


def lineage_note(lineage: Mapping[str, Any] | None) -> str | None:
    """None only when the lineage supports a live claim; otherwise the reason.

    An **empty** mapping is not a live lineage: it means the engine recorded no
    rows at all (failed fetch, empty week, section skipped), so it must degrade
    exactly like a missing one (WS-14).
    """
    if not lineage:
        return "lineage unverifiable: no lice lineage was recorded for the rows used"
    return lineage.get("note")


def observation_time(lineage: Mapping[str, Any] | None) -> dt.datetime | None:
    """The instant a lineage's newest weekly observation refers to.

    Lice reports are weekly, so the observation time is the ISO week's Monday
    00:00 UTC — the earliest instant the week describes. Unknown weeks return
    None (callers then fall back to request time and stay degraded anyway).
    """
    week = _week_tuple((lineage or {}).get("latest_week"))
    if week is None:
        return None
    try:
        monday = dt.date.fromisocalendar(week[0], week[1], 1)
    except ValueError:
        return None
    return dt.datetime.combine(monday, dt.time.min, tzinfo=dt.UTC)


def _row_field(row: Any, name: str) -> Any:
    """Read ``name`` from an ORM object, a SQLAlchemy Row or a mapping."""
    if isinstance(row, Mapping):
        return row.get(name)
    try:
        return getattr(row, name)
    except AttributeError:
        mapping = getattr(row, "_mapping", None)
        return mapping.get(name) if mapping is not None else None


def summarise_rows(
    rows: Iterable[Any],
    *,
    year: int | None = None,
    pas: Iterable[Mapping[str, Any]] | None = None,
    now: dt.datetime | None = None,
) -> dict:
    """Summarise the lineage of rows a computation already selected.

    Each row must expose ``source``, ``year``, ``week`` and ``fetched_at``
    (attributes, Row fields or mapping keys). Pass the **same** rows the payload
    was computed from — a lineage over a different predicate set proves nothing.
    Rows with an unknown ``source`` classify as unverified, so an empty or
    pre-WS-1 result never claims live.
    """
    counts: dict[Any, int] = {}
    latest: dt.datetime | None = None
    newest_week: tuple[int, int] | None = None
    years: list[int] = []
    for row in rows:
        label = _row_field(row, "source")
        key = "null" if label is None else str(label)
        counts[key] = counts.get(key, 0) + 1
        stamp = parse_timestamp(_row_field(row, "fetched_at"))
        if stamp is not None and (latest is None or stamp > latest):
            latest = stamp
        row_year = _row_field(row, "year")
        week = _week_tuple((row_year, _row_field(row, "week")))
        if week is not None and (newest_week is None or week > newest_week):
            newest_week = week
        if row_year:
            years.append(int(row_year))
    return summarise_lineage(
        counts,
        year=year if year is not None else (max(years) if years else None),
        latest_fetched_at=latest,
        latest_week=newest_week,
        pas=pas,
        now=now,
    )


async def lineage_for(session: Any, *predicates: Any, year: int | None = None) -> dict:
    """Lineage summary for the lice rows matching ``predicates``.

    One query shape for every consumer: select the lineage columns with the
    same WHERE clause the payload used, then classify them. Imported lazily so
    this module stays importable without SQLAlchemy models (it is also used by
    scripts and agents).
    """
    from sqlalchemy import select

    from core.models import LiceRecord

    stmt = select(
        LiceRecord.source, LiceRecord.year, LiceRecord.week, LiceRecord.fetched_at
    )
    if predicates:
        stmt = stmt.where(*predicates)
    rows = (await session.execute(stmt)).all()
    return summarise_rows(rows, year=year)


async def latest_week_lineage(
    *, year: int | None = None, now: dt.datetime | None = None
) -> dict:
    """Lineage of the newest lice week — for composite payloads.

    Several endpoints aggregate whole engines (alerts, notifications, ML
    training) whose lice-derived numbers all come from the newest reported
    week. They have no row list of their own, so this helper applies the one
    "latest lice week" selection (``year DESC, week DESC``) and summarises it.
    Callers that already hold the rows must use :func:`summarise_rows` instead.
    """
    from sqlalchemy import select

    from core.async_db import get_async_session
    from core.models import LiceRecord

    async with get_async_session() as s:
        newest = (await s.execute(
            select(LiceRecord.year, LiceRecord.week)
            .order_by(LiceRecord.year.desc(), LiceRecord.week.desc())
            .limit(1)
        )).first()
        if not newest:
            return summarise_rows([], year=year, now=now)
        target_year, target_week = newest
        rows = (await s.execute(
            select(
                LiceRecord.source,
                LiceRecord.year,
                LiceRecord.week,
                LiceRecord.fetched_at,
            ).where(
                LiceRecord.year == target_year,
                LiceRecord.week == target_week,
            )
        )).all()
    return summarise_rows(rows, year=year or target_year, now=now)


def provenance_for(
    lineage: Mapping[str, Any] | None, label: str, confidence: float
) -> dict:
    """Provenance dict for a payload derived from ``lineage`` — ONE implementation.

    WS-1/WS-14: a value built on demo, unverified, stale or partially-fetched
    lice rows is degraded, with the lineage note as the reason. ``freshness`` is
    the newest observation's time, never the request time (widened rule).
    """
    from core.market.data_provenance import DataProvenance

    note = lineage_note(lineage)
    observed = observation_time(lineage)
    if note is None:
        return DataProvenance.live(label, confidence=confidence, observed_at=observed).to_dict()
    return DataProvenance.degraded(
        label, reason=note, confidence=min(confidence, 0.40), observed_at=observed
    ).to_dict()

