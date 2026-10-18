"""Grounded platform context for the chat — every number carries its provenance.

The chat used to be handed a string-interpolated snapshot: a national lice average over
**every** row (including `demo_seed`), a latest week with no age, and a hardcoded
"traffic light: green < 0.2" sentence that is not how the Norwegian system works. A model
answering from that produces confident sentences about numbers nobody verified — the exact
failure the rest of the platform spent a cycle removing.

This module is the single source of chat context. Each fact is built by an engine the rest
of the platform already trusts, carries `as_of`, `source` and a `provenance`
(`live` / `degraded` / `stale` / `unavailable`), and is rendered into one block with the
rule attached: cite only these numbers, say when one is old, and never fill a gap.

Facts are gathered concurrently and independently: a dead engine degrades its own fact and
leaves the rest of the answer intact.
"""
from __future__ import annotations

import asyncio
import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

import structlog

log = structlog.get_logger(__name__)

#: A chlorophyll observation older than this is reported as degraded, not current.
BLOOM_MAX_AGE_DAYS = 7
#: A weekly SSB price older than this is degraded (two reporting weeks plus slack).
SPOT_MAX_AGE_DAYS = 14
#: Lice counts are weekly; two weeks behind is the last point that still reads as current.
LICE_MAX_AGE_DAYS = 14
#: A traffic-light decision older than this is reported as old news.
TRAFFIC_LIGHT_MAX_AGE_DAYS = 400
#: Above this many characters a question is truncated rather than sent (cost control).
MAX_QUESTION_CHARS = 2000

PROVENANCE_LIVE = "live"
PROVENANCE_DEGRADED = "degraded"
PROVENANCE_STALE = "stale"
PROVENANCE_UNAVAILABLE = "unavailable"


@dataclass
class Fact:
    """One verified statement the model may cite."""

    key: str
    label: str
    value: Any = None
    unit: str | None = None
    as_of: str | None = None
    source: str = ""
    provenance: str = PROVENANCE_LIVE
    age_days: int | None = None
    note: str | None = None
    detail: dict = field(default_factory=dict)

    @property
    def usable(self) -> bool:
        return self.provenance != PROVENANCE_UNAVAILABLE and self.value is not None

    def line(self) -> str:
        if self.provenance == PROVENANCE_UNAVAILABLE:
            return f"- {self.label}: UNAVAILABLE — {self.note or 'no data'}"
        rendered = self.value
        if isinstance(self.value, float):
            rendered = f"{self.value:,.2f}"
        elif isinstance(self.value, dict):
            pairs = [
                _pair(k, v) for k, v in list(self.value.items())[:10] if v is not None
            ]
            rendered = "; ".join(pairs)
        elif isinstance(self.value, (list, tuple)):
            rendered = ", ".join(str(v) for v in self.value[:12])
        unit = f" {self.unit}" if (self.unit and not isinstance(self.value, dict)) else ""
        meta = []
        if self.as_of:
            meta.append(f"as of {self.as_of}")
        if self.age_days is not None:
            meta.append(f"{self.age_days}d old")
        if self.provenance != PROVENANCE_LIVE:
            meta.append(self.provenance.upper())
        suffix = f" [{'; '.join(meta)}]" if meta else ""
        note = f" — {self.note}" if self.note else ""
        return f"- {self.label}: {rendered}{unit}{suffix}{note}"

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "value": self.value,
            "unit": self.unit,
            "as_of": self.as_of,
            "source": self.source,
            "provenance": self.provenance,
            "age_days": self.age_days,
            "note": self.note,
        }


@dataclass
class PlatformContext:
    """The fact set a chat answer must be built from."""

    facts: list[Fact] = field(default_factory=list)
    generated_at: str = ""

    def add(self, fact: Fact | None) -> None:
        if fact is not None:
            self.facts.append(fact)

    def get(self, key: str) -> Fact | None:
        return next((f for f in self.facts if f.key == key), None)

    @property
    def degraded(self) -> bool:
        return any(f.provenance != PROVENANCE_LIVE for f in self.facts)

    @property
    def unavailable(self) -> list[str]:
        return [f.key for f in self.facts if f.provenance == PROVENANCE_UNAVAILABLE]

    @property
    def stale(self) -> list[str]:
        return [f.key for f in self.facts if f.provenance in (PROVENANCE_STALE, PROVENANCE_DEGRADED)]

    def block(self) -> str:
        """The text handed to the model as its only permitted number source."""
        if not self.facts:
            return "VERIFIED DATA: none available for this deployment."
        usable = [f for f in self.facts if f.usable]
        lines = [f.line() for f in self.facts]
        header = (
            f"VERIFIED DATA (assembled {self.generated_at}). These are the only numbers "
            "you may state. "
        )
        rules = (
            "Rules: (1) cite only the figures in this block or returned by a tool; never "
            "estimate, average or recall a number that is not here. (2) When a line says "
            "STALE, DEGRADED or UNAVAILABLE, say so explicitly with its age instead of "
            "speaking in the present tense. (3) If the question needs a number that is not "
            "here, say which data is missing and what would be needed. "
            f"({len(usable)} of {len(self.facts)} facts usable.)"
        )
        return header + rules + "\n" + "\n".join(lines)

    def sources(self) -> list[dict]:
        """What the UI shows under an answer."""
        return [
            {
                "key": f.key,
                "label": f.label,
                "source": f.source,
                "as_of": f.as_of,
                "provenance": f.provenance,
                "age_days": f.age_days,
            }
            for f in self.facts
        ]

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at,
            "degraded": self.degraded,
            "stale": self.stale,
            "unavailable": self.unavailable,
            "facts": [f.to_dict() for f in self.facts],
        }


def _pair(key: str, value: Any) -> str:
    """One ``key: value`` pair for the prompt, with floats rounded to two places."""
    label = key.replace("_", " ")
    if isinstance(value, float):
        return f"{label} {value:,.2f}"
    return f"{label} {value}"


def _age_days(moment: Any, now: dt.datetime | None = None) -> int | None:
    """Whole days between an observation and now; None when undatable."""
    if moment is None:
        return None
    if isinstance(moment, dt.date) and not isinstance(moment, dt.datetime):
        moment = dt.datetime(moment.year, moment.month, moment.day, tzinfo=dt.UTC)
    if not isinstance(moment, dt.datetime):
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt.UTC)
    now = now or dt.datetime.now(dt.UTC)
    return max(0, (now - moment).days)


def _grade(age: int | None, limit: int) -> str:
    if age is None:
        return PROVENANCE_DEGRADED
    return PROVENANCE_LIVE if age <= limit else PROVENANCE_STALE


# ── fact builders ───────────────────────────────────────────────────────


async def _lice_fact(now: dt.datetime) -> Fact:
    """Lice: verified rows only, newest week, with the age of that week."""
    from sqlalchemy import func, select

    from core.async_db import get_async_session
    from core.models import LiceRecord
    from core.source_lineage import REAL_LICE_SOURCES, LICE_SOURCE_LABEL

    async with get_async_session() as session:
        newest = (
            await session.execute(
                select(LiceRecord.year, LiceRecord.week)
                .where(LiceRecord.source.in_(tuple(REAL_LICE_SOURCES)))
                .order_by(LiceRecord.year.desc(), LiceRecord.week.desc())
                .limit(1)
            )
        ).first()
        if not newest:
            return Fact(
                key="lice.national",
                label="National adult female lice",
                source=LICE_SOURCE_LABEL,
                provenance=PROVENANCE_UNAVAILABLE,
                note=(
                    "no verified lice row exists on this deployment (rows imported from "
                    "the demo seeder are excluded because they are not observations)"
                ),
            )
        year, week = newest
        stats = (
            await session.execute(
                select(
                    func.count(LiceRecord.id),
                    func.avg(LiceRecord.avg_adult_female_lice),
                    func.max(LiceRecord.avg_adult_female_lice),
                    func.count(func.distinct(LiceRecord.locality_no)),
                ).where(
                    LiceRecord.source.in_(tuple(REAL_LICE_SOURCES)),
                    LiceRecord.year == year,
                    LiceRecord.week == week,
                    LiceRecord.avg_adult_female_lice.isnot(None),
                )
            )
        ).one()
        above = (
            await session.execute(
                select(func.count(LiceRecord.id)).where(
                    LiceRecord.source.in_(tuple(REAL_LICE_SOURCES)),
                    LiceRecord.year == year,
                    LiceRecord.week == week,
                    LiceRecord.avg_adult_female_lice > 0.5,
                )
            )
        ).scalar() or 0

    # ISO week -> the Monday that starts it, so the age is honest.
    try:
        observed = dt.datetime.fromisocalendar(int(year), int(week), 1).replace(tzinfo=dt.UTC)
    except ValueError:
        observed = None
    age = _age_days(observed, now)
    count, avg, peak, sites = stats
    return Fact(
        key="lice.national",
        label="National adult female lice (verified rows only)",
        value={
            "week": f"{year}-W{int(week):02d}",
            "average_per_fish": round(float(avg or 0), 3),
            "max_per_fish": round(float(peak or 0), 3),
            "sites_reporting": int(sites or 0),
            "sites_above_0.5": int(above),
            "rows": int(count or 0),
        },
        as_of=f"{year}-W{int(week):02d}",
        source=LICE_SOURCE_LABEL,
        provenance=_grade(age, LICE_MAX_AGE_DAYS),
        age_days=age,
        note=(
            None if (age is not None and age <= LICE_MAX_AGE_DAYS)
            else "the newest verified report is not from the current reporting period; "
                 "treat every lice statement as historical"
        ),
    )


async def _lice_limit_fact(now: dt.datetime) -> Fact:
    """The § 8 limit that applies to the current week (both windows differ)."""
    from core.regulatory_facts import LICE_LIMIT_DEFAULT, LICE_LIMIT_SPRING, lice_limit

    week = now.isocalendar().week
    default = lice_limit(iso_week=week)
    spring = lice_limit(pa=3, iso_week=week)  # PA 3 belongs to the southern spring window
    value = {
        "current_week": week,
        "default_limit": LICE_LIMIT_DEFAULT,
        "spring_window_limit": LICE_LIMIT_SPRING,
        "this_week_default": default.limit,
        "this_week_in_spring_window": bool(default.in_spring_window),
        "pa3_this_week": spring.limit,
    }
    return Fact(
        key="lice.limit",
        label="Lakselusforskriften § 8 limit",
        value=value,
        unit="adult female lice per fish (weekly average)",
        as_of=f"ISO week {week}",
        source="lakselusforskriften § 8 via core/regulatory_facts.py",
        provenance=PROVENANCE_LIVE,
        note=(
            "the limit is 0.2 in the spring window and 0.5 outside it; the window differs "
            "by region, so a breach can only be assessed per site"
        ),
    )


async def _price_fact(now: dt.datetime) -> Fact:
    from core.market.ssb_price_client import ssb_price_client

    spot = await ssb_price_client.get_current_spot()
    history = await ssb_price_client.get_price_history(n_weeks=2)
    latest = history[-1] if history else None
    observed = None
    week_label = None
    if latest:
        raw_week = str(latest.get("week") or "").lstrip("Ww")
        week_no = int(raw_week) if raw_week.isdigit() else 0
        week_label = f"{latest.get('year')}-W{week_no:02d}"
        try:
            observed = dt.datetime.fromisocalendar(
                int(latest["year"]), week_no, 1
            ).replace(tzinfo=dt.UTC)
        except (KeyError, TypeError, ValueError):
            observed = None
    age = _age_days(observed, now)
    previous = history[-2].get("price_nok") if len(history) > 1 else None
    change = None
    if previous and spot:
        change = round((spot - float(previous)) / float(previous) * 100, 1)
    return Fact(
        key="price.spot",
        label="SSB salmon export price",
        value={
            "nok_per_kg": round(float(spot), 2) if spot else None,
            "week_on_week_pct": change,
        },
        unit="NOK/kg",
        as_of=week_label,
        source="Statistics Norway table 03024 (CC BY 4.0)",
        provenance=_grade(age, SPOT_MAX_AGE_DAYS),
        age_days=age,
        note=None if change is None else f"week on week {change:+.1f} %",
    )


async def _margin_fact(now: dt.datetime) -> Fact:
    """The margin bridge's headline, with its own quality verdict."""
    from core.market.margin_bridge import margin_bridge

    bridge = await margin_bridge.build()
    margin = bridge.get("margin") or {}
    legs = {leg.get("key"): leg for leg in (bridge.get("legs") or [])}
    feed = legs.get("feed") or {}
    price = legs.get("price") or {}
    changes = bridge.get("changes") or {}
    value = {
        "week": bridge.get("week"),
        "spot_nok_per_kg": margin.get("spot_nok_per_kg"),
        "modelled_cost_nok_per_kg": margin.get("modelled_cost_nok_per_kg"),
        "margin_nok_per_kg": margin.get("nok_per_kg"),
        "margin_pct": margin.get("pct"),
        "quality": margin.get("quality"),
        "feed_cost_nok_per_kg_salmon": round(abs(float(feed.get("nok_per_kg"))), 2) if feed.get("nok_per_kg") else None,
        "feed_period": feed.get("period"),
        "price_week_on_week_nok": (price.get("meta") or {}).get("week_on_week_nok_per_kg"),
        "feed_month_on_month_nok": (changes.get("feed_change_nok_per_kg")),
    }
    quality = str(margin.get("quality") or "unknown")
    return Fact(
        key="margin.bridge",
        label="Margin bridge (price minus feed, operations and capital)",
        value=value,
        unit="NOK/kg",
        as_of=(feed.get("period") or bridge.get("week")),
        source="core/market/margin_bridge.py (method "
               + str(bridge.get("method_version") or "?") + ")",
        provenance=PROVENANCE_LIVE if quality == "measured" else PROVENANCE_DEGRADED,
        note=(
            "every leg except the feed leg is a modelled industry value"
            if quality != "measured" else
            "price and feed were supplied by the caller"
        ),
    )


async def _bloom_fact(now: dt.datetime) -> Fact:
    from sqlalchemy import func, select

    from core.async_db import get_async_session
    from core.bloom.models import ChlorophyllReading

    async with get_async_session() as session:
        newest = (
            await session.execute(select(func.max(ChlorophyllReading.date)))
        ).scalar()
        mean = (
            await session.execute(
                select(func.avg(ChlorophyllReading.chl_a_mg_m3)).where(
                    ChlorophyllReading.date == newest
                )
            )
        ).scalar()
    age = _age_days(newest, now)
    return Fact(
        key="bloom.chlorophyll",
        label="Satellite chlorophyll-a (Norwegian coast)",
        value={
            "mean_mg_m3": round(float(mean), 2) if mean is not None else None,
            "newest_observation": newest.date().isoformat() if hasattr(newest, "date") else None,
        },
        unit="mg/m³",
        as_of=newest.date().isoformat() if hasattr(newest, "date") else None,
        source="Copernicus Marine (CMEMS) gap-free chlorophyll",
        provenance=_grade(age, BLOOM_MAX_AGE_DAYS),
        age_days=age,
        note=(
            "chlorophyll is biomass, not a toxicity measurement; an algal bloom cannot be "
            "confirmed or ruled out from this number alone"
        ),
    )


async def _traffic_light_fact(now: dt.datetime) -> Fact:
    from core.regulatory_facts import traffic_light_decision

    decision = traffic_light_decision(now.date())
    colours: dict[str, list[int]] = {"green": [], "yellow": [], "red": []}
    for pa, colour in sorted(decision.colours.items()):
        colours.setdefault(str(colour), []).append(pa)
    age = _age_days(decision.decided_on, now)
    return Fact(
        key="regulatory.traffic_light",
        label="Traffic-light colours (official decision)",
        value={
            "decided_on": decision.decided_on.isoformat(),
            "red_areas": colours.get("red", []),
            "yellow_areas": colours.get("yellow", []),
            "green_areas": colours.get("green", []),
        },
        as_of=decision.decided_on.isoformat(),
        source=f"{decision.regulation} ({decision.source_url})",
        provenance=_grade(age, TRAFFIC_LIGHT_MAX_AGE_DAYS),
        age_days=age,
        note=(
            "the colours decide production-capacity adjustments after lice-induced "
            "mortality — they are not a lice-level scale"
        ),
    )


async def _tariff_fact(now: dt.datetime) -> Fact:
    from core.regulatory_facts import us_salmon_tariff

    row = us_salmon_tariff("Norway", now.date())
    return Fact(
        key="tariff.us_norway",
        label="US tariff on Norwegian salmon",
        value={
            "rate_pct": round(float(row.rate) * 100, 2),
            "basis": row.basis,
            "effective_from": row.effective_from.isoformat(),
            "caveat": row.caveat,
        },
        unit="%",
        as_of=row.effective_from.isoformat(),
        source=row.source_url,
        provenance=PROVENANCE_LIVE,
        note="duty is assessed on the transaction value, not on production cost",
    )


_FACT_LABELS: dict[str, str] = {
    "lice.national": "National adult female lice (verified rows only)",
    "lice.limit": "Lakselusforskriften section 8 limit",
    "price.spot": "SSB salmon export price",
    "margin.bridge": "Margin bridge (price minus feed, operations and capital)",
    "bloom.chlorophyll": "Satellite chlorophyll-a (Norwegian coast)",
    "regulatory.traffic_light": "Traffic-light colours (official decision)",
    "tariff.us_norway": "US tariff on Norwegian salmon",
}

_FACT_BUILDERS: tuple[tuple[str, Callable[[dt.datetime], Awaitable[Fact]]], ...] = (
    ("lice.national", _lice_fact),
    ("lice.limit", _lice_limit_fact),
    ("price.spot", _price_fact),
    ("margin.bridge", _margin_fact),
    ("bloom.chlorophyll", _bloom_fact),
    ("regulatory.traffic_light", _traffic_light_fact),
    ("tariff.us_norway", _tariff_fact),
)


async def _safe_build(
    key: str, builder: Callable[[dt.datetime], Awaitable[Fact]], now: dt.datetime
) -> Fact:
    try:
        return await builder(now)
    except Exception as exc:  # noqa: BLE001 — one dead engine must not kill the answer
        log.warning("chat.grounding_failed", fact=key, error=str(exc)[:160])
        return Fact(
            key=key,
            label=_FACT_LABELS.get(key, key),
            provenance=PROVENANCE_UNAVAILABLE,
            note=f"the engine behind this fact failed: {type(exc).__name__}",
        )


async def build_context(*, now: dt.datetime | None = None) -> PlatformContext:
    """Assemble every fact concurrently; a failure degrades only its own fact."""
    moment = now or dt.datetime.now(dt.UTC)
    results = await asyncio.gather(
        *(_safe_build(key, builder, moment) for key, builder in _FACT_BUILDERS)
    )
    context = PlatformContext(
        facts=list(results),
        generated_at=moment.isoformat(timespec="seconds"),
    )
    log.info(
        "chat.grounding_built",
        facts=len(context.facts),
        stale=len(context.stale),
        unavailable=len(context.unavailable),
    )
    return context
