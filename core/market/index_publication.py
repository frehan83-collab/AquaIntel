"""Weekly publication status and readiness for the named indices (WS-2).

``publish_week()`` (core/market/bio_price_weekly.py) computes and stores every
published index (``indices.PUBLISHED_INDICES``: AI-STI since method 2.0.0, AI-LPI
v1.0 being withdrawn — WS-19) for the ISO week of its ``as_of``; the unique constraint on
``index_observations`` makes that idempotent per (index, week, method version).
Until WS-2 nothing *scheduled* it, so the published history was populated only
by test runs and nothing could say whether the current week had been published.

This module answers that operational question from the store itself, and decides
when a built digest is fit to become the week's immutable observation. It is read
by the ``index_publisher`` agent, by ``publish_week()`` (so the admin endpoint
obeys the same gate), by ``GET /api/indices`` (so the product surface shows it)
and by the production-truth verifier (so a silent scheduler is a named warning,
never an assumption).

Contracts (one definition each — the agent, the publisher and the freshness
monitor import them):

* **Cadence** — one observation per index per ISO week; the agent checks hourly.
  The freshness monitor allows the cadence *plus the readiness grace plus one
  tick*, because a degraded week is stored only after the grace by design.
* **Interval** — a skipped week is two consecutive stored observations whose ISO
  weeks are more than one apart. Wall-clock gaps between ``as_of`` stamps are
  reported for information only: they drift with the hourly tick phase and must
  never raise an alarm on their own. With fewer than two observations the
  interval is *not measurable* (``None``), never "ok".
* **Readiness (per index)** — an observation is immutable for its (index, week,
  version), so the first computation of a week must not lock in an artefact of
  missing inputs. An index with no value is never stored (the store refuses it,
  whoever writes). Within the first ``READINESS_GRACE_HOURS`` of the week only a
  *live* index value is stored; after the grace a degraded value is stored with
  its provenance saying why. Indices are gated independently: a valid index is
  not withheld because another index's source is down.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
from typing import Any

import structlog

from core.market import indices
from core.source_lineage import parse_timestamp, to_utc

log = structlog.get_logger(__name__)

#: The published set (one definition in core.market.indices). A withdrawn index is
#: never built, stored or reported missing (WS-19).
INDEX_CODES: tuple[str, ...] = indices.PUBLISHED_INDICES

#: One observation per ISO week.
PUBLICATION_CADENCE_HOURS = 168
#: The publisher agent's check interval.
PUBLISH_TICK_HOURS = 1
#: Within the first N hours of a week only a live index value is stored.
READINESS_GRACE_HOURS = 72
#: What the freshness monitor treats as the expected cadence of the store. A
#: degraded week is legitimately stored up to the grace late, and the tick adds
#: up to an hour of phase, so neither may read as "stale" (one definition).
FRESHNESS_CADENCE_HOURS = PUBLICATION_CADENCE_HOURS + READINESS_GRACE_HOURS + PUBLISH_TICK_HOURS
#: Consecutive stored observations must be consecutive ISO weeks.
MAX_WEEK_STEP = 1
#: Gaps are reported for the most recent N observations.
GAP_HISTORY_LIMIT = 12

PUBLISHER = (
    "agents/index_publisher_agent.py (hourly check, one observation per index per "
    "ISO week, readiness-gated) or POST /api/indices/publish (same gate; "
    "force=true overrides the grace and is audited)"
)


_utc = to_utc  # one definition (core/source_lineage.to_utc)


def current_week_label(now: dt.datetime | None = None) -> str:
    """The ISO week label the indices stamp on a value, e.g. ``2026-W42`` (UTC)."""
    return _utc(now).strftime("%G-W%V")


def week_tuple(label: Any) -> tuple[int, int] | None:
    """Parse ``'2026-W42'`` into ``(2026, 42)``; None for anything else."""
    if not label or not isinstance(label, str):
        return None
    try:
        year_text, week_text = label.upper().split("-W")
        year, week = int(year_text), int(week_text)
        dt.date.fromisocalendar(year, week, 1)  # validates the week number
        return year, week
    except (ValueError, TypeError):
        return None


def week_start(now: dt.datetime) -> dt.datetime:
    """Monday 00:00 UTC of ``now``'s ISO week."""
    iso = _utc(now).isocalendar()
    return dt.datetime.combine(
        dt.date.fromisocalendar(iso[0], iso[1], 1), dt.time(), tzinfo=dt.UTC
    )


def _hours_into_week(now: dt.datetime) -> float:
    stamp = _utc(now)
    return (stamp - week_start(stamp)).total_seconds() / 3600.0


def hours_into_week(now: dt.datetime) -> float:
    return round(_hours_into_week(now), 2)


def _weeks_between(earlier: tuple[int, int], later: tuple[int, int]) -> int:
    start = dt.date.fromisocalendar(earlier[0], earlier[1], 1)
    end = dt.date.fromisocalendar(later[0], later[1], 1)
    return (end - start).days // 7


def readiness(digest: dict, now: dt.datetime | None = None) -> dict:
    """Decide, per index, whether a *built* digest's value should be stored now.

    Returns ``store`` (codes fit to store), ``withheld`` (code → reason),
    ``degraded`` (codes in ``store`` whose provenance is not live — stored because
    the grace has passed), ``ready`` (anything to store), ``within_grace`` and the
    hours into the week. The comparison uses the unrounded hour.
    """
    stamp = _utc(now)
    hours = _hours_into_week(stamp)
    within_grace = hours < READINESS_GRACE_HOURS
    results = digest.get("indices") or {}
    store: list[str] = []
    withheld: dict[str, str] = {}
    degraded: list[str] = []
    for code in INDEX_CODES:
        result = results.get(code) or {}
        if result.get("value") is None:
            withheld[code] = "no value computed — nothing to store"
            continue
        provenance = result.get("provenance") or {}
        if provenance.get("is_live"):
            store.append(code)
            continue
        if within_grace:
            withheld[code] = (
                f"degraded ({(provenance.get('fallback_reason') or 'provenance not live')[:160]}) "
                f"and only {hours:.0f} h into the week — waiting up to "
                f"{READINESS_GRACE_HOURS} h for a live computation"
            )
            continue
        store.append(code)
        degraded.append(code)
    return {
        "ready": bool(store),
        "store": store,
        "withheld": withheld,
        "degraded": degraded,
        "within_grace": within_grace,
        "hours_into_week": round(hours, 2),
        "grace_hours": READINESS_GRACE_HOURS,
        "reason": "; ".join(f"{code}: {why}" for code, why in withheld.items()) or None,
    }


def _read_latest(version: str, week: str) -> dict[str, dict[str, Any]]:
    """Per index: the newest observations at ``version`` (newest first, as
    ``(week, as_of, value, provenance_json)``) and the current week's row looked
    up directly, so a future-dated row can never hide it.

    Runs in a worker thread with the sync session, the same way
    ``indices.save_observation`` writes, so the two always see one store.
    """
    from sqlalchemy import inspect, select

    from core.models import IndexObservation, Session as DBSession

    columns = (
        IndexObservation.week,
        IndexObservation.as_of,
        IndexObservation.value,
        IndexObservation.provenance_json,
    )
    out: dict[str, dict[str, Any]] = {}
    with DBSession() as session:
        if not inspect(session.get_bind()).has_table("index_observations"):
            raise LookupError("index_observations table missing")
        for code in INDEX_CODES:
            scoped = (
                IndexObservation.index_code == code,
                IndexObservation.version == version,
            )
            rows = session.execute(
                select(*columns)
                .where(*scoped)
                .order_by(IndexObservation.as_of.desc())
                .limit(GAP_HISTORY_LIMIT + 1)
            ).all()
            current = session.execute(
                select(*columns).where(*scoped, IndexObservation.week == week).limit(1)
            ).first()
            out[code] = {
                "rows": [tuple(row) for row in rows],
                "current": tuple(current) if current else None,
            }
    return out


def _provenance(raw: Any) -> dict:
    try:
        data = json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        data = {}
    return data if isinstance(data, dict) else {}


async def status(now: dt.datetime | None = None) -> dict:
    """Is the current ISO week published for every index at the current method?

    Per index: the latest stored week with its value and provenance verdict,
    whether the current week is stored (and live), how many weeks behind the
    latest is (negative = the store is ahead of the clock, flagged), the ISO-week
    steps between consecutive observations (``interval_ok`` None until there are
    two), and the wall-clock gaps for information. Never raises for a missing or
    unreadable store: that is reported as ``reason`` with every index missing.
    """
    stamp = _utc(now)
    version = indices.INDEX_METHOD_VERSION
    week = current_week_label(stamp)
    current = week_tuple(week)
    reason: str | None = None
    try:
        latest = await asyncio.to_thread(_read_latest, version, week)
    except LookupError as exc:  # our own, secret-free message ("table missing")
        latest = {code: {"rows": [], "current": None} for code in INDEX_CODES}
        reason = f"index_observations unreadable: {exc}"
    except Exception as exc:
        # status() is served on the public GET /api/indices: log the driver's
        # message (it may name hosts, users or SQL) and publish only the class.
        log.warning("index_publication.store_unreadable", error=str(exc))
        latest = {code: {"rows": [], "current": None} for code in INDEX_CODES}
        reason = f"index_observations unreadable: {type(exc).__name__}"

    per_index: dict[str, dict] = {}
    skipped: list[str] = []
    for code in INDEX_CODES:
        rows = latest.get(code, {}).get("rows") or []
        current_row = latest.get(code, {}).get("current")
        stamps = [parse_timestamp(row[1]) for row in rows]
        latest_tuple = week_tuple(rows[0][0]) if rows else None
        provenance = _provenance(rows[0][3]) if rows else {}
        gaps = [
            round((stamps[i] - stamps[i + 1]).total_seconds() / 86400.0, 2)
            for i in range(len(stamps) - 1)
            if stamps[i] is not None and stamps[i + 1] is not None
        ]
        steps: list[int] = []
        for newer, older in zip(rows, rows[1:]):
            newer_week, older_week = week_tuple(newer[0]), week_tuple(older[0])
            if newer_week is None or older_week is None:
                continue
            step = _weeks_between(older_week, newer_week)
            steps.append(step)
            if step > MAX_WEEK_STEP:
                skipped.append(f"{code} {older[0]}→{newer[0]}")
        weeks_behind = (
            _weeks_between(latest_tuple, current) if latest_tuple and current else None
        )
        per_index[code] = {
            "latest_week": rows[0][0] if rows else None,
            "latest_as_of": stamps[0].isoformat() if rows and stamps[0] else None,
            "latest_value": rows[0][2] if rows else None,
            "latest_is_live": bool(provenance.get("is_live")) if rows else None,
            "latest_fallback_reason": provenance.get("fallback_reason") if rows else None,
            "current_week_published": current_row is not None,
            "current_week_is_live": (
                bool(_provenance(current_row[3]).get("is_live")) if current_row else None
            ),
            "weeks_behind": weeks_behind,
            "store_ahead_of_clock": bool(weeks_behind is not None and weeks_behind < 0),
            "week_steps": steps,
            "max_week_step": max(steps) if steps else None,
            "interval_ok": (all(step <= MAX_WEEK_STEP for step in steps) if steps else None),
            "gaps_days": gaps,
        }

    missing = [code for code in INDEX_CODES if not per_index[code]["current_week_published"]]
    degraded_current = [
        code
        for code in INDEX_CODES
        if per_index[code]["current_week_published"]
        and not per_index[code]["current_week_is_live"]
    ]
    measured = [v["interval_ok"] for v in per_index.values() if v["interval_ok"] is not None]
    hours = _hours_into_week(stamp)
    return {
        "week": week,
        "version": version,
        "checked_at": stamp.isoformat(),
        "hours_into_week": round(hours, 2),
        "within_grace": hours < READINESS_GRACE_HOURS,
        "indices": per_index,
        "current_week_published": not missing,
        "missing": missing,
        "degraded_current": degraded_current,
        "max_week_step": max(
            (v["max_week_step"] for v in per_index.values() if v["max_week_step"] is not None),
            default=None,
        ),
        # None = not measurable (fewer than two observations, or the store unreadable)
        "interval_ok": (None if reason or not measured else not skipped),
        "skipped_weeks": skipped,
        "cadence_hours": PUBLICATION_CADENCE_HOURS,
        "readiness_grace_hours": READINESS_GRACE_HOURS,
        "reason": reason,
        "publisher": PUBLISHER,
    }
