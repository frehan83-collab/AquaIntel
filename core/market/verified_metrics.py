"""One definition of "the current value" for alert rules — verified, dated, or absent.

The council's rank 5. The alert evaluator was the last consumer that skipped the lineage work
the rest of the platform enforces:

* `lice_avg` took the newest (year, week) with **no source filter**, so a `demo_seed` row could
  be "the current lice level" while the chat excluded exactly those rows;
* `disease_count` returned `0.0` on any exception, so a dead feed evaluated as "no outbreaks"
  and could fire an "all clear" rule;
* nothing checked recency, so a seven-month-old lice row was compared and reported "OK" as if it
  were today's number, with no age anywhere in the result.

This module is the single answer to "what is the current value of this metric": the same source
filters and the same age limits the chat uses, a `provenance` verdict, an `age_days`, and `None`
rather than a fabricated zero. Callers that cannot get a verified current value must not evaluate
a rule or seed a threshold — "we do not know" is a valid answer and a much better one than a
confident comparison against a stale row.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import structlog

log = structlog.get_logger(__name__)

#: How old a metric may be and still count as current. Weekly feeds get two periods.
MAX_AGE_DAYS: dict[str, int] = {
    "lice_avg": 14,
    "spot_price": 14,
    "disease_count": 30,
    "bloom_risk": 7,
}

LIVE = "live"
STALE = "stale"
UNAVAILABLE = "unavailable"


@dataclass
class VerifiedMetric:
    metric: str
    value: float | None = None
    as_of: str | None = None
    age_days: int | None = None
    source: str = ""
    provenance: str = UNAVAILABLE
    production_area: int | None = None
    note: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def current(self) -> bool:
        return self.provenance == LIVE and self.value is not None

    def to_dict(self) -> dict:
        return {
            "metric": self.metric,
            "value": self.value,
            "as_of": self.as_of,
            "age_days": self.age_days,
            "source": self.source,
            "provenance": self.provenance,
            "production_area": self.production_area,
            "note": self.note,
            "current": self.current,
            **self.extra,
        }


def _age(moment: dt.datetime | None, now: dt.datetime) -> int | None:
    if moment is None:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt.UTC)
    return max(0, (now - moment).days)


def _week_monday(year: int, week: int) -> dt.datetime | None:
    try:
        return dt.datetime.fromisocalendar(int(year), int(week), 1).replace(tzinfo=dt.UTC)
    except (TypeError, ValueError):
        return None


async def _lice(production_area: int | None, now: dt.datetime) -> VerifiedMetric:
    from sqlalchemy import func, select

    from core.async_db import get_async_session
    from core.models import LiceRecord, Locality
    from core.source_lineage import LICE_SOURCE_LABEL, REAL_LICE_SOURCES

    metric = VerifiedMetric(
        metric="lice_avg", production_area=production_area, source=LICE_SOURCE_LABEL
    )
    try:
        async with get_async_session() as session:
            newest = (
                await session.execute(
                    select(LiceRecord.year, LiceRecord.week)
                    .where(LiceRecord.source.in_(tuple(REAL_LICE_SOURCES)))
                    .order_by(LiceRecord.year.desc(), LiceRecord.week.desc())
                    .limit(1)
                )
            ).first()
            if newest is None:
                metric.note = "no verified lice row exists on this deployment"
                return metric
            year, week = newest
            query = select(func.avg(LiceRecord.avg_adult_female_lice)).where(
                LiceRecord.source.in_(tuple(REAL_LICE_SOURCES)),
                LiceRecord.year == year,
                LiceRecord.week == week,
                LiceRecord.avg_adult_female_lice.isnot(None),
            )
            if production_area is not None:
                query = query.join(
                    Locality, Locality.locality_no == LiceRecord.locality_no
                ).where(Locality.production_area == production_area)
            value = (await session.execute(query)).scalar()
    except Exception as exc:  # noqa: BLE001 — reported, never a zero
        log.warning("verified_metric.lice_failed", error=str(exc)[:120])
        metric.note = f"the lice query failed: {type(exc).__name__}"
        return metric

    if value is None:
        metric.note = "no verified lice value for that production area"
        return metric

    moment = _week_monday(year, week)
    age = _age(moment, now)
    limit = MAX_AGE_DAYS["lice_avg"]
    metric.value = round(float(value), 3)
    metric.as_of = f"{year}-W{int(week):02d}"
    metric.age_days = age
    metric.provenance = LIVE if (age is not None and age <= limit) else STALE
    if metric.provenance == STALE:
        metric.note = (
            f"the newest verified lice report is {metric.as_of}"
            + (f" ({age} days old)" if age is not None else " and cannot be dated")
            + "; a rule cannot be evaluated against it"
        )
    return metric


async def _spot(now: dt.datetime) -> VerifiedMetric:
    from core.market.ssb_price_client import ssb_price_client

    metric = VerifiedMetric(
        metric="spot_price", source="Statistics Norway table 03024 (CC BY 4.0)"
    )
    try:
        spot = await ssb_price_client.get_current_spot()
        history = await ssb_price_client.get_price_history(n_weeks=1)
    except Exception as exc:  # noqa: BLE001
        log.warning("verified_metric.spot_failed", error=str(exc)[:120])
        metric.note = f"the SSB price could not be read: {type(exc).__name__}"
        return metric
    if not spot:
        metric.note = "no SSB week price is available"
        return metric
    latest = history[-1] if history else None
    age = None
    if latest:
        raw = str(latest.get("week") or "").lstrip("Ww")
        if raw.isdigit():
            age = _age(_week_monday(latest.get("year"), int(raw)), now)
            metric.as_of = f"{latest.get('year')}-W{int(raw):02d}"
    metric.value = round(float(spot), 2)
    metric.age_days = age
    metric.provenance = (
        LIVE if (age is not None and age <= MAX_AGE_DAYS["spot_price"]) else STALE
    )
    if metric.provenance == STALE:
        metric.note = "the SSB week price is older than the current or previous week"
    return metric


async def _disease(production_area: int | None, now: dt.datetime) -> VerifiedMetric:
    from core.market.mattilsynet_client import mattilsynet_client

    metric = VerifiedMetric(
        metric="disease_count",
        production_area=production_area,
        source="Mattilsynet (fishhealth API)",
    )
    try:
        cases = await mattilsynet_client.fetch_disease_cases()
    except Exception as exc:  # noqa: BLE001 — a dead feed is not "zero outbreaks"
        log.warning("verified_metric.disease_failed", error=str(exc)[:120])
        metric.note = f"the disease feed could not be read: {type(exc).__name__}"
        return metric
    if not isinstance(cases, list):
        metric.note = "the disease feed returned an unexpected payload"
        return metric
    rows = cases
    if production_area is not None:
        rows = [c for c in rows if c.get("production_area") == production_area]
    metric.value = float(len(rows))
    metric.as_of = now.date().isoformat()
    metric.age_days = 0
    metric.provenance = LIVE
    metric.note = "count of case reports returned by the feed"
    return metric


async def _bloom(now: dt.datetime) -> VerifiedMetric:
    from sqlalchemy import func, select

    from core.async_db import get_async_session
    from core.bloom.models import BloomRiskAssessment

    metric = VerifiedMetric(
        metric="bloom_risk", source="core/bloom risk model over CMEMS chlorophyll"
    )
    try:
        async with get_async_session() as session:
            row = (
                await session.execute(
                    select(
                        func.avg(BloomRiskAssessment.risk_score),
                        func.max(BloomRiskAssessment.assessed_at),
                    ).where(BloomRiskAssessment.risk_score.isnot(None))
                )
            ).one()
    except Exception as exc:  # noqa: BLE001
        log.warning("verified_metric.bloom_failed", error=str(exc)[:120])
        metric.note = f"the bloom assessment query failed: {type(exc).__name__}"
        return metric
    if row is None or row[0] is None:
        metric.note = "no bloom assessment is stored"
        return metric
    age = _age(row[1], now)
    metric.value = round(float(row[0]), 2)
    metric.as_of = row[1].date().isoformat() if row[1] else None
    metric.age_days = age
    metric.provenance = LIVE if (age is not None and age <= MAX_AGE_DAYS["bloom_risk"]) else STALE
    if metric.provenance == STALE:
        metric.note = (
            "the newest bloom assessment is not from this week; the chlorophyll feed behind it "
            "may be older still"
        )
    return metric


async def verified_current(
    metric: str,
    *,
    production_area: int | None = None,
    now: dt.datetime | None = None,
) -> VerifiedMetric:
    """The current value of an alert metric, or a dated reason why there is none."""
    moment = now or dt.datetime.now(dt.UTC)
    if metric == "lice_avg":
        return await _lice(production_area, moment)
    if metric == "spot_price":
        return await _spot(moment)
    if metric == "disease_count":
        return await _disease(production_area, moment)
    if metric == "bloom_risk":
        return await _bloom(moment)
    return VerifiedMetric(metric=metric, note=f"unknown metric {metric!r}")


def plausibility(metric: str, threshold: float) -> tuple[bool, str]:
    """Is this threshold a plausible value for this metric at all?

    A rule seeded from a question can ask for nonsense ("lice above 40"), and a rule that can
    never fire is worse than no rule: the customer believes they are watched when they are not.
    """
    bounds = {
        "lice_avg": (0.0, 10.0),
        "spot_price": (10.0, 400.0),
        "disease_count": (0.0, 5000.0),
        "bloom_risk": (0.0, 100.0),
    }
    low, high = bounds.get(metric, (float("-inf"), float("inf")))
    if not (low <= threshold <= high):
        return False, (
            f"{threshold:g} is outside the plausible range for {metric} "
            f"({low:g} to {high:g}), so the rule would never fire as intended"
        )
    return True, ""
