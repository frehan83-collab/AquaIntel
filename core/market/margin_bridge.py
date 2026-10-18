"""Weekly margin bridge — the money view over the live price and cost feeds.

Why this module exists
----------------------
Feed cost (~40 % of the modelled production cost) and the export price are both
live on this platform, but until now no surface translated them into *money per
kilo with the assumptions named and every leg dated*. ``/feed-cost`` printed a
margin bar and three rows whose units did not agree (feed ingredient cost per kg
of **feed** next to the price per kg of **salmon**), and nothing said what had
moved since last week or how far the spot is from break-even.

The bridge answers, in one payload:

* **where the margin is** — the price leg minus four grouped cost legs, per kg of
  harvested round weight, plus the NOK totals when the caller supplies a volume;
* **what moved it** — the price leg week on week (SSB weekly), the feed leg month
  on month (FRED monthly, at today's FX; the FX effect is stated, not applied to
  the delta), the structural legs not at all;
* **how far break-even is** — and what feed or FCR improvement would close the gap;
* **which levers pay** — price, feed price, FCR, one avoided lice treatment and one
  point of survival, each in NOK/kg with the formula behind it.

Honesty rules (AGENTS.md rule 1, HANDOVER WS-14/WS-22)
------------------------------------------------------
* Every leg carries its own source, period and provenance; a leg built from a
  fallback is degraded **with the reason**, and the payload's overall provenance is
  degraded whenever any measured leg is.
* No volume is invented. The bridge is per kg until the caller supplies
  ``annual_tonnes`` (or ``standing_tonnes``); only then are NOK totals emitted, and
  they name the volume they were computed from.
* The cost base is the industry benchmark (Fiskeridirektoratet 2024 cost structure
  applied to live FRED ingredient prices), never the caller's accounts — the
  payload says so in ``method``, ``scope`` and ``assumptions``.
* Average treatment and lice spend is *inside* the modelled operations leg, which
  is why the absence of a farm-measured biological leg does not make the margin
  incomplete, and why the treatment lever prices a *marginal* extra event.
"""
from __future__ import annotations

import asyncio
import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Mapping

import structlog

from core.market.biomass_predictor import HARVEST_WEIGHT_KG
from core.market.data_provenance import DataProvenance
from core.market.feed_cost_engine import (
    DEFAULT_USDNOK as _DEFAULT_USDNOK,
    FEED_COMPOSITION,
    FEED_PRICE_MAX_AGE_DAYS as _FEED_PRICE_MAX_AGE_DAYS,
    feed_cost_engine,
)
from core.market.treatment_constants import TREATMENT_PROFILES
from core.market.ssb_price_client import PRICE_MAX_WEEKS_BEHIND as _PRICE_MAX_WEEKS_BEHIND

log = structlog.get_logger(__name__)

#: Bump when a formula, a leg grouping or an assumption changes, so a published
#: margin can be traced to the method that produced it (the WS-19 index rule).
MARGIN_METHOD_VERSION = "1.0.0"

#: How the eight Fiskeridirektoratet cost lines group into four readable legs.
#: Keys are the ``cost_breakdown`` keys produced by ``feed_cost_engine``.
COST_LEG_GROUPS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("fish_and_harvest", "Smolt and harvesting", ("smolt", "slaughter")),
    ("operations", "Operations, insurance and treatments", ("labour", "other_operating", "insurance")),
    ("capital", "Depreciation and finance", ("depreciation", "net_finance")),
)

#: Rounding tolerance when the grouped legs are reconciled against the feed
#: engine's own total (the engine rounds each line to two decimals).
_ROUNDING_TOLERANCE = 0.05

#: The one treatment event the biology lever prices. Mechanical is the most common
#: method and the cheapest per fish (Overton et al. 2019; Mowi Handbook 2024) —
#: using it keeps the lever conservative rather than dramatic.
BIOLOGY_LEVER_METHOD = "mechanical"

#: FRED's monthly commodity series publish with a lag; the rule lives with the feed
#: engine (``feed_cost_engine.FEED_PRICE_MAX_AGE_DAYS``) so `/api/feed-cost/latest`
#: and the bridge cannot disagree about whether a basket is current. Re-exported here
#: because this is where a reader looks for the bridge's threshold.
FEED_PRICE_MAX_AGE_DAYS = _FEED_PRICE_MAX_AGE_DAYS

#: SSB publishes weekly; a price week further behind than this means the cache is
#: answering for an old week. One definition, shared with the decision card
#: (``ssb_price_client.PRICE_MAX_WEEKS_BEHIND``), re-exported for readers here.
PRICE_MAX_WEEKS_BEHIND = _PRICE_MAX_WEEKS_BEHIND

#: How long the bridge waits for the month-on-month feed history before serving the
#: level alone. The change is secondary; the margin may not wait on it (WS-25 class).
#: Six seconds clears the ~2 s a warm FRED window takes without letting a cold one
#: hold the request; `feed_cost_engine.feed_index_change` negative-caches the failure.
FEED_CHANGE_TIMEOUT_S = 6.0

#: How far the modelled feed leg may sit from the last official realised feed cost
#: before the bridge calls its own level unvalidated. The modelled leg is a proxy
#: basket x a learned multiplier, so it is *never* a measurement; this threshold
#: only decides whether the payload says "close enough to the audited anchor" or
#: names the gap as a problem.
FEED_LEVEL_VALIDATION_TOLERANCE_PCT = 25.0

#: Cost-breakdown keys that are not cost lines (metadata or the feed line itself).
_NON_LEG_KEYS = frozenset(
    {"method", "feed_share_of_total", "total", "feed_ingredients", "feed_per_kg_salmon"}
)


def _as_datetime(value: Any) -> dt.datetime | None:
    """Coerce a date, datetime or ISO string to an aware UTC datetime.

    ``DataProvenance.freshness`` is an ISO **timestamp**; a bare ``date`` (the FRED
    observation month, the SSB week) must be widened to midnight UTC rather than
    passed through, which would raise on ``.tzinfo``.
    """
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value if value.tzinfo else value.replace(tzinfo=dt.UTC)
    if isinstance(value, dt.date):
        return dt.datetime.combine(value, dt.time.min, tzinfo=dt.UTC)
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.UTC)


def _age_days(value: Any, now: dt.datetime) -> int | None:
    """Whole days between an observation date and the bridge's instant."""
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        observed = value.date() if value.tzinfo is None else value.astimezone(dt.UTC).date()
    elif isinstance(value, dt.date):
        observed = value
    else:
        try:
            observed = dt.date.fromisoformat(str(value)[:10])
        except (TypeError, ValueError):
            return None
    return max(0, (now.date() - observed).days)


def _as_utc(moment: dt.datetime | None) -> dt.datetime | None:
    if moment is None:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=dt.UTC)


def _round(value: float | None, places: int = 2) -> float | None:
    return None if value is None else round(float(value), places)


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


@dataclass
class MarginLeg:
    """One line of the bridge, in NOK per kg of harvested round weight."""

    key: str
    label: str
    nok_per_kg: float | None
    kind: str  # revenue | cost | margin
    status: str  # measured | caller_supplied | structural | unpriced
    period: str | None = None
    source: str | None = None
    detail: str | None = None
    members: dict[str, float] = field(default_factory=dict)
    meta: dict = field(default_factory=dict)
    provenance: dict | None = None

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "nok_per_kg": _round(self.nok_per_kg),
            "kind": self.kind,
            "status": self.status,
            "period": self.period,
            "source": self.source,
            "detail": self.detail,
            "members": {k: _round(v) for k, v in self.members.items()},
            "meta": self.meta,
            "data_provenance": self.provenance,
        }


class MarginBridgeEngine:
    """Compose the live price and cost feeds into one margin bridge.

    Singleton (``margin_bridge``); read-only over the other engines' cached state,
    so it adds no cache of its own beyond the feed history it borrows.
    """

    async def build(
        self,
        *,
        fcr: float | None = None,
        delivered_feed_nok_per_kg: float | None = None,
        spot_nok_per_kg: float | None = None,
        annual_tonnes: float | None = None,
        standing_tonnes: float | None = None,
        locality_no: int | None = None,
        as_of: dt.datetime | None = None,
    ) -> dict:
        """Build the bridge.

        ``fcr`` and ``delivered_feed_nok_per_kg`` let a farm substitute its own
        numbers; only the feed leg moves with them (the other legs stay the modelled
        industry values) and the payload says so. ``spot_nok_per_kg`` overrides the
        SSB week price for a contract-priced seller. Volumes are optional and never
        defaulted.
        """
        now = _as_utc(as_of) or dt.datetime.now(dt.UTC)

        # ── Input 1: the feed / cost engine (live FRED ingredients) ──────────
        snapshot = await feed_cost_engine.fetch_prices()
        breakdown: dict[str, Any] = dict(getattr(snapshot, "cost_breakdown", {}) or {})
        model_feed_per_kg_salmon = _finite(snapshot.feed_cost_nok_per_kg_salmon)
        model_total_cost = _finite(snapshot.production_cost_nok_per_kg_salmon)

        # ── Input 2: the price leg (live SSB week, with week on week) ────────
        price = await self._price_leg(spot_nok_per_kg=spot_nok_per_kg, now=now)

        # ── Feed leg: delivered feed x FCR, optionally the caller's numbers ──
        model_fcr = _finite(getattr(snapshot, "fcr", None))
        model_delivered_feed = (
            model_feed_per_kg_salmon / model_fcr if model_feed_per_kg_salmon and model_fcr else None
        )
        used_fcr = _finite(fcr) or model_fcr
        used_delivered = _finite(delivered_feed_nok_per_kg) or model_delivered_feed
        feed_per_kg_salmon = (
            used_delivered * used_fcr if used_delivered is not None and used_fcr else None
        )
        if feed_per_kg_salmon is None:
            feed_per_kg_salmon = model_feed_per_kg_salmon
        caller_feed = _finite(fcr) is not None or _finite(delivered_feed_nok_per_kg) is not None

        # ── Input 3: what the feed basket did month on month (FRED monthly) ──
        feed_change = await self._feed_change()
        feed_as_of = getattr(snapshot, "feed_prices_as_of", None)
        feed_age_days = _age_days(feed_as_of, now)

        legs: list[MarginLeg] = [price]
        feed_detail = (
            f"FCR {used_fcr:.2f} x delivered feed {used_delivered:.2f} NOK/kg, from the FRED "
            "ingredient basket x the learned 1.86 delivered multiplier"
            if used_delivered is not None and used_fcr
            else "delivered feed x FCR unavailable"
        )
        if caller_feed:
            feed_detail += " (caller-supplied; the other legs remain the modelled industry values)"
        legs.append(
            MarginLeg(
                key="feed",
                label="Feed (FCR-adjusted)",
                nok_per_kg=-feed_per_kg_salmon if feed_per_kg_salmon else None,
                kind="cost",
                status="modelled" if feed_per_kg_salmon else "unpriced",
                period=(
                    feed_as_of.strftime("%Y-%m") if feed_as_of
                    else feed_change.get("period") or "latest FRED month"
                ),
                source=(
                    "FRED commodity series via feed_cost_engine "
                    "(fishmeal, fish oil, soy, rapeseed, wheat)"
                ),
                detail=feed_detail,
                meta={
                    "fcr": _round(used_fcr),
                    "delivered_feed_nok_per_kg": _round(used_delivered),
                    "caller_supplied": caller_feed,
                    "observed_at": feed_as_of.isoformat() if feed_as_of else None,
                    "age_days": feed_age_days,
                    "month_on_month_change_pct": feed_change.get("change_pct"),
                },
                provenance=self._feed_provenance(snapshot, feed_change),
            )
        )

        grouped = {k: 0.0 for k, _, _ in COST_LEG_GROUPS}
        members: dict[str, dict[str, float]] = {k: {} for k, _, _ in COST_LEG_GROUPS}
        ungrouped: dict[str, float] = {}
        for key, value in breakdown.items():
            if key in _NON_LEG_KEYS:
                continue
            amount = _finite(value)
            if amount is None:
                continue
            for leg_key, _, keys in COST_LEG_GROUPS:
                if key in keys:
                    grouped[leg_key] += amount
                    members[leg_key][key] = amount
                    break
            else:
                ungrouped[key] = amount

        for leg_key, label, _ in COST_LEG_GROUPS:
            legs.append(
                MarginLeg(
                    key=leg_key,
                    label=label,
                    nok_per_kg=-grouped[leg_key] if grouped[leg_key] else None,
                    kind="cost",
                    status="structural",
                    period="Fiskeridirektoratet 2024 cost structure",
                    source="Fiskeridirektoratet lonnsomhetsundersokelse 2024 (via feed_cost_engine)",
                    detail=(
                        "modelled from the official 2024 cost structure applied to the live feed "
                        "base; includes average treatment and lice spend"
                    ),
                    members=members[leg_key],
                )
            )
        if ungrouped:
            legs.append(
                MarginLeg(
                    key="other",
                    label="Other modelled cost",
                    nok_per_kg=-sum(ungrouped.values()),
                    kind="cost",
                    status="structural",
                    period="Fiskeridirektoratet 2024 cost structure",
                    source="Fiskeridirektoratet lonnsomhetsundersokelse 2024",
                    detail="cost lines the grouping does not name yet",
                    members=ungrouped,
                )
            )

        # ── Reconcile against the engine's own total ─────────────────────────
        cost_legs = [leg for leg in legs if leg.kind == "cost" and leg.nok_per_kg is not None]
        modelled_cost = -sum(leg.nok_per_kg for leg in cost_legs)
        reconcile = None if model_total_cost is None else round(modelled_cost - model_total_cost, 2)
        # Only the rounding the feed engine applies, not a percentage of the total: a
        # 1 % tolerance (~0.74 NOK/kg) would let a genuinely mis-grouped line pass.
        reconciliation_ok = reconcile is not None and abs(reconcile) <= _ROUNDING_TOLERANCE

        # ── Margin ───────────────────────────────────────────────────────────
        spot = price.nok_per_kg
        margin_nok_per_kg = (
            round(spot - modelled_cost, 2) if spot is not None and modelled_cost else None
        )
        margin_pct = (
            round(margin_nok_per_kg / spot * 100, 1)
            if margin_nok_per_kg is not None and spot
            else None
        )
        legs.append(
            MarginLeg(
                key="margin",
                label="Margin over modelled cost",
                nok_per_kg=margin_nok_per_kg,
                kind="margin",
                # The margin inherits its status from the two sides it was built from:
                # "measured" only when both were the caller's own numbers, never just
                # because the subtraction produced a value.
                status=(
                    "measured"
                    if price.status == "caller_supplied" and caller_feed
                    else "modelled" if margin_nok_per_kg is not None
                    else "unpriced"
                ),
                period=price.period,
                source="derived: the price leg minus the cost legs",
            )
        )

        # ── What moved ───────────────────────────────────────────────────────
        feed_change_nok_per_kg = None
        pct = _finite(feed_change.get("change_pct"))
        if pct is not None and feed_per_kg_salmon:
            # current = previous x (1 + p)  ->  delta = current x p / (1 + p)
            feed_change_nok_per_kg = round(feed_per_kg_salmon * pct / (100 + pct), 2)
        price_wow = _finite(price.meta.get("week_on_week_nok_per_kg"))
        # The price delta raises the margin and the feed delta is a COST delta (positive =
        # dearer feed = lower margin), so the margin change subtracts one from the other.
        # Adding them (the first version did) reported -0.79 where the margin moved -1.71.
        # Both sides are needed: with the feed move unknown, reporting the price-only move
        # as "the margin change" would quietly overstate it (review round 2).
        margin_change = (
            None
            if price_wow is None or feed_change_nok_per_kg is None
            else round(price_wow - feed_change_nok_per_kg, 2)
        )
        changes = {
            "price_wow_nok_per_kg": price_wow,
            "price_previous_week": price.meta.get("previous_week"),
            "feed_mom_nok_per_kg": feed_change_nok_per_kg,
            "feed_mom_pct": pct,
            "feed_period": feed_change.get("period"),
            "margin_change_nok_per_kg": margin_change,
            # A move built from part of the basket must say so (WS-29 review).
            "feed_weight_coverage_pct": feed_change.get("weight_coverage_pct"),
            "feed_excluded_ingredients": feed_change.get("excluded") or [],
            "structural_legs": (
                "held at the modelled 2024 structure; they do not move week to week"
            ),
            "note": (
                "the price leg moves weekly and the feed leg monthly, so the two deltas cover "
                "different periods; each is labelled with its own. The margin change is the "
                "price delta minus the feed cost delta"
            ),
        }

        # ── Break-even and the lever table ───────────────────────────────────
        break_even = self._break_even(
            spot=spot,
            cost=modelled_cost,
            feed_per_kg_salmon=feed_per_kg_salmon,
            delivered_feed=used_delivered,
            fcr=used_fcr,
        )
        levers = self._levers(
            spot=spot,
            delivered_feed=used_delivered,
            fcr=used_fcr,
            annual_tonnes=annual_tonnes,
        )

        # ── Provenance and scope ─────────────────────────────────────────────
        leg_provenances = [leg.provenance for leg in legs if leg.provenance]
        degraded_reasons = [
            str(p.get("fallback_reason")) for p in leg_provenances
            if p and not p.get("is_live") and p.get("fallback_reason")
        ]
        observed = self._price_observation_time(price)
        label = (
            "SSB weekly export price + FRED commodity series + "
            "Fiskeridirektoratet cost structure"
        )
        if degraded_reasons:
            provenance = DataProvenance.degraded(
                label,
                reason="; ".join(dict.fromkeys(degraded_reasons)),  # de-duplicate, keep order
                confidence=0.45,
                observed_at=observed,
            ).to_dict()
        else:
            provenance = DataProvenance.live(label, confidence=0.75, observed_at=observed).to_dict()

        return {
            "method_version": MARGIN_METHOD_VERSION,
            "generated_at": now.isoformat(),
            "week": price.period,
            "locality_no": locality_no,
            "currency": "NOK",
            "unit": "NOK per kg harvested round weight",
            "legs": [leg.to_dict() for leg in legs],
            "margin": {
                "nok_per_kg": margin_nok_per_kg,
                "pct": margin_pct,
                "modelled_cost_nok_per_kg": _round(modelled_cost) if modelled_cost else None,
                "spot_nok_per_kg": _round(spot),
                # "measured" only when the caller supplied both the price and the
                # feed numbers; the industry defaults are a model, never a measurement.
                "quality": (
                    "measured" if price.status == "caller_supplied" and caller_feed
                    else "modelled" if margin_nok_per_kg is not None
                    else "unpriced"
                ),
                "quality_basis": (
                    "price and feed inputs supplied by the caller"
                    if price.status == "caller_supplied" and caller_feed
                    else "industry cost model with the live SSB week price"
                ),
            },
            "changes": changes,
            "break_even": break_even,
            "levers": levers,
            "validation": self._feed_level_validation(
                modelled_feed_per_kg_salmon=model_feed_per_kg_salmon,
                caller_feed_per_kg_salmon=feed_per_kg_salmon if caller_feed else None,
                as_of=feed_as_of,
            ),
            "volume": self._volume(
                annual_tonnes=annual_tonnes,
                standing_tonnes=standing_tonnes,
                margin_nok_per_kg=margin_nok_per_kg,
                cost_nok_per_kg=modelled_cost,
            ),
            "method": (
                "Feed ingredient prices (FRED, monthly, live) x the learned "
                "ingredient-to-delivered multiplier x FCR give the feed leg per kg salmon; the "
                "remaining cost legs apply the Fiskeridirektoratet 2024 cost structure (feed "
                "39.7 % of total cost) to that live feed base; the price leg is the SSB 03024 "
                "weekly export price for the week named on the leg. Every leg states its own "
                "period because the feeds publish on different cadences."
            ),
            "assumptions": self._assumptions(snapshot, used_fcr, used_delivered),
            "reconciliation": {
                "modelled_cost_nok_per_kg": _round(modelled_cost) if modelled_cost else None,
                "engine_total_nok_per_kg": _round(model_total_cost),
                "difference_nok_per_kg": reconcile,
                # A caller-supplied feed leg is on a different basis, so the check does not
                # apply and must not report a false "a cost line was renamed" diagnosis.
                "ok": None if caller_feed else bool(reconciliation_ok),
                "applicable": not caller_feed,
                "note": (
                    "not applicable: the feed leg is caller-supplied, so the total is no longer "
                    "the modelled cost base"
                    if caller_feed else
                    "the grouped legs must re-add to the feed engine's total; a difference means "
                    "a cost line was added or renamed without updating the grouping"
                ),
            },
            "scope": {
                "biological_drag_priced": False,
                "reason": (
                    "average treatment and lice spend sits inside the modelled operations leg "
                    "(Fiskeridirektoratet 'other operating costs'); the treatment lever prices an "
                    "extra event on top of it. A farm-measured biological leg is not included "
                    "because no verified, current lice count is available for this farm."
                ),
                "notes": [
                    "per kg only unless a volume is supplied",
                    "the cost base is an industry benchmark, not the caller's accounts",
                    "the price is the all-size export average, not a size-class or contract price",
                ],
            },
            "data_provenance": provenance,
        }

    async def for_farm(self, locality_no: int, **overrides: Any) -> dict:
        """The bridge plus this farm's regulatory position for the week.

        The farm block is deliberately narrow: the production area, and the lice
        limit in force this ISO week (``core.regulatory_facts``, a dated official
        fact) together with the farm's distance to it **only when verified, current
        lice rows exist**. With no verified count the position is ``unknown`` with
        the reason — the bridge never infers a lice level from stale rows.
        """
        payload = await self.build(locality_no=locality_no, **overrides)
        payload["farm"] = await self._farm_block(locality_no)
        return payload

    async def _farm_block(self, locality_no: int) -> dict:
        # Lazy imports: the farm block is the only part of the bridge that touches
        # the database, and importing the decision engine at module scope would make
        # every arithmetic test pay for the ORM. `_oslo_iso_week` is the one
        # definition of "ISO week in Norwegian time" used for § 8 windows.
        from core.market.decision_engine import _oslo_iso_week
        from core.regulatory_facts import breaches_limit
        from core.regulatory_facts import lice_limit as _lice_limit
        from core.source_lineage import summarise_rows

        block: dict[str, Any] = {"locality_no": locality_no}
        try:
            from sqlalchemy import desc, select

            from core.async_db import get_async_session
            from core.models import LiceRecord, Locality

            async with get_async_session() as session:
                row = (
                    await session.execute(
                        select(
                            Locality.name,
                            Locality.production_area,
                            Locality.municipality,
                            Locality.county,
                            Locality.owner_company,
                        ).where(Locality.locality_no == locality_no)
                    )
                ).first()
                if row:
                    block.update(
                        {
                            "name": row[0],
                            "production_area": row[1],
                            "municipality": row[2],
                            "county": row[3],
                            "owner_company": row[4],
                        }
                    )
                lice_rows = (
                    await session.execute(
                        select(
                            LiceRecord.avg_adult_female_lice,
                            LiceRecord.sea_temp_c,
                            LiceRecord.year,
                            LiceRecord.week,
                            LiceRecord.source,
                            LiceRecord.fetched_at,
                        )
                        .where(LiceRecord.locality_no == locality_no)
                        .order_by(desc(LiceRecord.year), desc(LiceRecord.week))
                        .limit(4)
                    )
                ).all()
        except Exception as exc:  # noqa: BLE001 — a diagnostic block never 500s the bridge
            log.debug("margin_bridge.farm_block_failed", locality_no=locality_no, error=str(exc)[:120])
            block["error"] = f"farm position unavailable ({str(exc)[:80]})"
            return block

        pa = block.get("production_area")
        year, week = _oslo_iso_week(dt.datetime.now(dt.UTC))
        limit = _lice_limit(
            pa, week,
            municipality=block.get("municipality"),
            county=block.get("county"),
        )
        block["lice_limit"] = {
            **limit.as_dict(),
            "evaluated_for": f"{year}-W{week:02d}",
        }

        lineage = summarise_rows(lice_rows, year=lice_rows[0][2] if lice_rows else None)
        block["lice_lineage"] = lineage
        if lineage.get("is_live") and lice_rows:
            current = _finite(lice_rows[0][0])
            if current is not None:
                block["lice_position"] = {
                    "status": "measured",
                    "current_adult_female": round(current, 3),
                    "distance_to_limit": round(limit.limit - current, 3),
                    "at_or_above_limit": breaches_limit(current, limit.limit),
                    "week": f"{lice_rows[0][2]}-W{int(lice_rows[0][3]):02d}",
                    "sea_temp_c": _round(_finite(lice_rows[0][1]), 1),
                }
            else:
                block["lice_position"] = {
                    "status": "unknown",
                    "reason": "the newest verified row carries no adult-female count",
                }
        else:
            block["lice_position"] = {
                "status": "unknown",
                "reason": lineage.get("note") or "no verified lice rows for this farm",
            }
        return block

    # ── Price leg ────────────────────────────────────────────────────────────

    async def _price_leg(self, *, spot_nok_per_kg: float | None, now: dt.datetime) -> MarginLeg:
        """The revenue leg: the SSB week price, with the previous week for the delta."""
        history: list[dict] = []
        error: str | None = None
        try:
            from core.market.ssb_price_client import ssb_price_client

            history = await ssb_price_client.get_price_history(3) or []
        except Exception as exc:  # noqa: BLE001 — a price outage degrades, never 500s
            error = f"SSB price history unavailable ({str(exc)[:80]})"

        current = history[-1] if history else None
        previous = history[-2] if len(history) >= 2 else None
        week = _week_label(current)
        prev_week = _week_label(previous)
        caller_price = _finite(spot_nok_per_kg) is not None
        spot = (
            _finite(spot_nok_per_kg) if caller_price
            else _finite(current.get("price_nok")) if current else None
        )
        if spot is None and error is None:
            error = "no SSB week price was returned"
        wow = (
            round(float(current["price_nok"]) - float(previous["price_nok"]), 2)
            if current and previous
            and _finite(current.get("price_nok")) is not None
            and _finite(previous.get("price_nok")) is not None
            else None
        )
        observed_at = _week_monday(current)

        weeks_behind = _weeks_behind(current, now)
        if spot is not None and not caller_price and weeks_behind is not None and (
            weeks_behind > PRICE_MAX_WEEKS_BEHIND
        ):
            # SSB publishes weekly. A cache that keeps answering months after the last
            # successful fetch must not be served as the current week's price.
            provenance = DataProvenance.degraded(
                "SSB table 03024 weekly salmon export price",
                reason=(
                    f"the newest SSB week on hand is {week}, {weeks_behind} weeks behind "
                    f"(SSB publishes weekly; more than {PRICE_MAX_WEEKS_BEHIND} weeks is stale)"
                ),
                confidence=0.45,
                observed_at=observed_at,
            ).to_dict()
        elif spot is not None and not caller_price:
            provenance = DataProvenance.live(
                "SSB table 03024 weekly salmon export price",
                confidence=0.95,
                observed_at=observed_at,
            ).to_dict()
        elif spot is not None:
            provenance = DataProvenance.degraded(
                "caller-supplied price (contract or own assumption)",
                reason="the price leg is caller-supplied; the SSB week price is not used here",
                confidence=0.5,
                observed_at=observed_at,
            ).to_dict()
        else:
            provenance = DataProvenance.degraded(
                "SSB table 03024 weekly salmon export price",
                reason=error or "price unavailable",
                confidence=0.2,
                observed_at=observed_at,
            ).to_dict()

        return MarginLeg(
            key="price",
            label="Salmon price (SSB weekly export)",
            nok_per_kg=spot,
            kind="revenue",
            status="measured" if spot is not None and not caller_price else (
                "caller_supplied" if spot is not None else "unpriced"
            ),
            period=week,
            source="SSB table 03024",
            detail=(
                "all-size weekly average export price at the Norwegian border — the industry "
                "benchmark, not a size-class or contract price"
            ),
            meta={
                "week_on_week_nok_per_kg": wow,
                "previous_week": prev_week,
                "reported_volume_tonnes": _round(current.get("volume_tonnes")) if current else None,
                "weeks_behind": _weeks_behind(current, now),
            },
            provenance=provenance,
        )

    # ── Feed change month on month ───────────────────────────────────────────

    async def _feed_change(self) -> dict:
        """Weighted month-on-month move of the feed ingredient basket.

        Weighted exactly like the feed cost itself (``FEED_COMPOSITION``), each
        ingredient over its own two latest FRED months. The caller converts it to
        NOK per kg salmon at today's FX and FCR — the FX effect is *not* inside this
        number, and the payload says so.

        **Bounded:** the change is a secondary field, so it may not hold the margin
        hostage. It fetches a second FRED history, which on a cold cache is five more
        requests; when that is slow the bridge serves the level (cached for two hours
        by the feed engine) and says the change was unavailable. Found while a whole
        suite run stalled on a slow FRED window (WS-25 class: upstream fetches must not
        sit unbounded on the request path).
        """
        try:
            return await asyncio.wait_for(
                feed_cost_engine.feed_index_change(), timeout=FEED_CHANGE_TIMEOUT_S
            ) or {}
        except asyncio.TimeoutError:
            log.warning("margin_bridge.feed_change_timeout", timeout_s=FEED_CHANGE_TIMEOUT_S)
            return {
                "error": f"feed history did not answer within {FEED_CHANGE_TIMEOUT_S:.1f} s"
            }
        except Exception as exc:  # noqa: BLE001 — a history outage must not sink the bridge
            log.debug("margin_bridge.feed_change_failed", error=str(exc)[:120])
            return {"error": f"feed history unavailable ({str(exc)[:80]})"}

    @staticmethod
    def _feed_provenance(snapshot: Any, feed_change: Mapping[str, Any]) -> dict:
        """The feed engine's provenance rule, plus the month-on-month disclosure.

        The dated/undated/defaulted verdict is ``FeedCostSnapshot.price_provenance``
        (one definition shared with `/api/feed-cost/latest`); the bridge only adds
        what that surface does not know: whether the *change* could be computed.
        """
        provenance = snapshot.price_provenance()
        if feed_change.get("error"):
            clause = (
                "the level is dated but its month-on-month change is unavailable: "
                + str(feed_change["error"])
            )
            existing = provenance.get("fallback_reason")
            provenance["is_live"] = False
            provenance["confidence"] = min(float(provenance.get("confidence") or 0.5), 0.55)
            provenance["fallback_reason"] = f"{existing}; {clause}" if existing else clause
        return provenance

    @staticmethod
    def _price_observation_time(leg: MarginLeg) -> dt.datetime | None:
        """The instant the price leg describes (its provenance freshness)."""
        from core.source_lineage import parse_timestamp

        return parse_timestamp((leg.provenance or {}).get("freshness"))

    # ── Break-even and levers ────────────────────────────────────────────────

    @staticmethod
    def _break_even(
        *,
        spot: float | None,
        cost: float,
        feed_per_kg_salmon: float | None,
        delivered_feed: float | None,
        fcr: float | None,
    ) -> dict:
        gap = None if spot is None or not cost else round(spot - cost, 2)
        needed_pct = None
        if gap is not None and gap < 0 and feed_per_kg_salmon:
            # How far the feed leg alone would have to fall, every other leg held.
            needed_pct = round(abs(gap) / feed_per_kg_salmon * 100, 1)
        fcr_needed = None
        if delivered_feed and spot is not None and fcr and cost:
            # The FCR that would put the modelled cost base at the spot price,
            # holding every non-feed leg constant.
            non_feed = cost - delivered_feed * fcr
            candidate = (spot - non_feed) / delivered_feed
            fcr_needed = round(candidate, 2) if candidate > 0 else None
        return {
            "cost_nok_per_kg": _round(cost) if cost else None,
            "spot_nok_per_kg": _round(spot),
            "distance_nok_per_kg": gap,
            "above_break_even": None if gap is None else gap >= 0,
            "feed_leg_reduction_needed_pct": needed_pct,
            "fcr_at_break_even": fcr_needed,
            "note": (
                "break-even is the modelled cost base, so it moves with the feed basket; the "
                "FCR figure holds every non-feed leg constant"
            ),
        }

    @staticmethod
    def _feed_level_validation(
        *,
        modelled_feed_per_kg_salmon: float | None,
        caller_feed_per_kg_salmon: float | None,
        as_of: Any,
    ) -> dict:
        """Compare the modelled feed leg with the last audited realised cost.

        The feed leg is a FRED proxy basket times a learned multiplier, so its
        *level* is a model. The last audited anchor is Fiskeridirektoratet's realised
        feed cost per kg salmon. Publishing the gap lets a buyer see whether the
        level is drifting away from the audited series instead of trusting a number
        with no external check — the deltas, the break-even relationship and the
        levers are differential and survive a level error, the level does not.
        """
        from core.market.feed_cost_engine import OFFICIAL_COST_HISTORY

        if not OFFICIAL_COST_HISTORY:
            return {"available": False, "reason": "no official cost series is loaded"}
        anchor_year = max(OFFICIAL_COST_HISTORY)
        anchor = OFFICIAL_COST_HISTORY[anchor_year]
        official_feed = _finite(anchor.get("feed"))
        # The check is about the MODEL. When the caller supplied the feed leg there is
        # nothing to validate against the audited series, so say which one was compared.
        compared = "caller_inputs" if caller_feed_per_kg_salmon else "model"
        measured = caller_feed_per_kg_salmon if compared == "caller_inputs" else modelled_feed_per_kg_salmon
        gap_pct = None
        if measured and official_feed:
            gap_pct = round((measured - official_feed) / official_feed * 100, 1)
        within = None if gap_pct is None else abs(gap_pct) <= FEED_LEVEL_VALIDATION_TOLERANCE_PCT
        return {
            "available": True,
            "compared": compared,
            "anchor_year": anchor_year,
            "official_feed_nok_per_kg_salmon": official_feed,
            "official_total_nok_per_kg_salmon": _finite(anchor.get("total")),
            "modelled_feed_nok_per_kg_salmon": _round(modelled_feed_per_kg_salmon),
            "caller_feed_nok_per_kg_salmon": _round(caller_feed_per_kg_salmon),
            "gap_pct": gap_pct,
            "within_tolerance": within,
            "tolerance_pct": FEED_LEVEL_VALIDATION_TOLERANCE_PCT,
            "observed_at": as_of.isoformat() if hasattr(as_of, "isoformat") else None,
            "source": "Fiskeridirektoratet lonnsomhetsundersokelse (feed_cost_engine.OFFICIAL_COST_HISTORY)",
            "note": (
                (
                    "the caller supplied the feed leg, so the gap compares your figure with the "
                    f"{anchor_year} audited realised cost, not the model"
                    if compared == "caller_inputs" else
                    "the modelled feed leg is a FRED proxy basket x a learned multiplier; the "
                    f"audited anchor is the {anchor_year} realised cost"
                )
                + f". A gap outside {FEED_LEVEL_VALIDATION_TOLERANCE_PCT:.0f} % means the level is "
                "indicative only — the week-on-week and month-on-month deltas, the break-even "
                "relationship and the levers are differential and do not depend on it"
            ),
        }

    @staticmethod
    def _levers(
        *,
        spot: float | None,
        delivered_feed: float | None,
        fcr: float | None,
        annual_tonnes: float | None,
    ) -> list[dict]:
        """The five things that move this margin, in NOK/kg, with their formulas."""
        treatment_cost = TREATMENT_PROFILES[BIOLOGY_LEVER_METHOD].cost_per_fish_nok
        levers: list[dict] = []

        def add(key: str, label: str, nok_per_kg: float | None, formula: str, basis: str) -> None:
            if nok_per_kg is None:
                return
            item: dict = {
                "key": key,
                "label": label,
                "nok_per_kg": round(nok_per_kg, 2),
                "formula": formula,
                "basis": basis,
            }
            if annual_tonnes:
                item["nok_per_year"] = round(nok_per_kg * float(annual_tonnes) * 1000)
            levers.append(item)

        add(
            "price",
            "Spot price, +1 NOK/kg",
            1.0,
            "1 NOK/kg of harvested round weight",
            "the price leg passes through one for one",
        )
        if fcr:
            add(
                "feed_price",
                "Delivered feed price, -1 NOK/kg",
                fcr,
                "feed price saving x FCR",
                f"FCR {fcr:.2f}",
            )
        if delivered_feed:
            add(
                "fcr",
                "FCR, -0.05",
                0.05 * delivered_feed,
                "0.05 kg feed per kg fish x delivered feed price",
                f"delivered feed {delivered_feed:.2f} NOK/kg",
            )
        add(
            "treatment",
            "One avoided lice treatment event",
            treatment_cost / HARVEST_WEIGHT_KG,
            "treatment cost per fish / harvest weight",
            (
                f"{BIOLOGY_LEVER_METHOD} at {treatment_cost:.2f} NOK/fish, "
                f"{HARVEST_WEIGHT_KG:.1f} kg harvest weight "
                "(Overton et al. 2019; Mowi Handbook 2024)"
            ),
        )
        if spot:
            add(
                "survival",
                "One point of survival",
                0.01 * spot,
                "1 % of biomass value",
                "a point of survival keeps 1 % of the standing value that would otherwise be lost",
            )
        return levers

    @staticmethod
    def _volume(
        *,
        annual_tonnes: float | None,
        standing_tonnes: float | None,
        margin_nok_per_kg: float | None,
        cost_nok_per_kg: float,
    ) -> dict:
        """NOK totals — only from volumes the caller supplied, never a default."""
        annual = _finite(annual_tonnes)
        standing = _finite(standing_tonnes)
        out: dict = {
            "annual_tonnes": annual,
            "standing_tonnes": standing,
            "annual_margin_nok": None,
            "standing_cost_nok": None,
            "basis": "no volume supplied — the bridge is per kg only",
        }
        if annual and margin_nok_per_kg is not None:
            out["annual_margin_nok"] = round(margin_nok_per_kg * annual * 1000)
            out["basis"] = f"annual volume {annual:,.0f} t supplied by the caller"
        if standing and cost_nok_per_kg:
            out["standing_cost_nok"] = round(cost_nok_per_kg * standing * 1000)
        return out

    @staticmethod
    def _assumptions(snapshot: Any, fcr: float | None, delivered_feed: float | None) -> list[dict]:
        """Every structural number the bridge used, with where it comes from."""
        model_fcr = _finite(getattr(snapshot, "fcr", None))
        return [
            {
                "key": "feed_composition",
                "value": {k: round(v * 100, 1) for k, v in FEED_COMPOSITION.items()},
                "unit": "% of feed by weight",
                "source": (
                    "Skretting / Cargill / BioMar published sustainability reports "
                    "(feed_cost_engine.FEED_COMPOSITION)"
                ),
            },
            {
                "key": "fcr",
                "value": _round(fcr),
                "unit": "kg feed per kg fish",
                "source": (
                    "caller-supplied"
                    if fcr is not None and (model_fcr is None or abs(fcr - model_fcr) > 1e-9)
                    else "Fiskeridirektoratet 2024 (latest official, valid range 1.21-1.35)"
                ),
            },
            {
                "key": "delivered_feed_price",
                "value": _round(delivered_feed),
                "unit": "NOK/kg feed",
                "source": (
                    "live FRED ingredient basket x 1.86 ingredient-to-delivered multiplier "
                    "(2024: 19.73 official / 10.62 FRED; range 1.6-2.1 across 17 years)"
                ),
            },
            {
                "key": "cost_structure",
                "value": "Fiskeridirektoratet 2024",
                "unit": "share of total cost",
                "source": (
                    "Lonnsomhetsundersokelsen 2024: feed 25.67 of 64.64 NOK/kg = 39.7 %, which "
                    "fixes the non-feed legs"
                ),
            },
            {
                "key": "harvest_weight",
                "value": HARVEST_WEIGHT_KG,
                "unit": "kg",
                "source": "core.market.biomass_predictor.HARVEST_WEIGHT_KG (target harvest weight)",
            },
            {
                "key": "fx",
                "value": _round(_finite(getattr(snapshot, "usd_nok", None))),
                "unit": "NOK/USD",
                "source": (
                    "live Yahoo Finance USDNOK; when the fetch fails the constant "
                    f"{_DEFAULT_USDNOK} is used and the feed leg's provenance degrades naming it"
                ),
            },
        ]


def _week_label(entry: Mapping[str, Any] | None) -> str | None:
    if not entry:
        return None
    try:
        week = int(str(entry.get("week")).lstrip("W"))
        year = int(entry.get("year"))
    except (TypeError, ValueError):
        return None
    return f"{year}-W{week:02d}"


def _week_monday(entry: Mapping[str, Any] | None) -> dt.datetime | None:
    """The Monday 00:00 UTC of the ISO week an SSB row describes."""
    if not entry:
        return None
    try:
        monday = dt.date.fromisocalendar(
            int(entry.get("year")), int(str(entry.get("week")).lstrip("W")), 1
        )
    except (TypeError, ValueError):
        return None
    return dt.datetime.combine(monday, dt.time.min, tzinfo=dt.UTC)


def _weeks_behind(entry: Mapping[str, Any] | None, now: dt.datetime) -> int | None:
    """Whole ISO weeks between an SSB row's week and the current week."""
    monday = _week_monday(entry)
    if monday is None:
        return None
    this_week = dt.date.fromisocalendar(*now.isocalendar()[:2], 1)
    return max(0, (this_week - monday.date()).days // 7)


margin_bridge = MarginBridgeEngine()
