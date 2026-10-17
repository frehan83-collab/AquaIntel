"""Bio→Price Weekly v1 — the flagship weekly digest.

Composes the published index (AI-STI) with the supply and price panels into one
weekly, versioned report whose every number carries its source. The point of the
product is the *link*: biomass and harvest momentum are leading indicators for
price, and the report states the direction it reads — while refusing to claim
causality it cannot evidence. AI-LPI v1.0 is withdrawn (WS-19) and named in
``withdrawn``; no lice input enters the read.

Published once per ISO week by the ``index_publisher`` agent (build → readiness
→ store_digest) or by ``publish_week()`` behind the admin endpoint; readable at
``/api/indices/bio-price-weekly`` and permalinked at ``/indices#bio-price-weekly``.
"""
from __future__ import annotations

import datetime as dt

import structlog

from core.market import indices
from core.market.data_provenance import DataProvenance

log = structlog.get_logger(__name__)

REPORT_VERSION = "1.0.0"


def _latest_and_prior(totals: dict) -> tuple[tuple[int, int], tuple[int, int] | None]:
    keys = sorted(totals)
    if not keys:
        return (0, 0), None
    return keys[-1], (keys[-2] if len(keys) > 1 else None)


async def _supply_panel() -> dict:
    """Standing biomass + harvest, with the momentum a trading desk reads."""
    source = "Fiskeridir biomass (SSB)"
    try:
        from core.market.biomass_tracker import biomass_tracker

        biomass = await indices.national_totals("standing_biomass_tonnes")
        harvest = await indices.national_totals("harvest_tonnes")
        # The tracker's OWN lineage decides the live claim (it filters synthetic
        # records and falls back to a historical-pattern estimate) — the same rule
        # the AI-STI momentum components follow.
        lineage_live = bool(getattr(biomass_tracker, "last_is_live", False))
        lineage_source = getattr(biomass_tracker, "last_source", None) or source
        latest, prior = _latest_and_prior(biomass)
        if latest == (0, 0):
            raise RuntimeError("no biomass periods")
        standing = biomass[latest]
        prev_standing = biomass.get(prior) if prior else None
        growth_pct = (
            (standing - prev_standing) / prev_standing * 100.0
            if prev_standing
            else None
        )
        return {
            "period": f"{latest[0]}-{latest[1]:02d}",
            "standing_biomass_tonnes": round(standing, 1),
            "harvest_tonnes": round(harvest.get(latest, 0.0), 1),
            "biomass_change_pct": None if growth_pct is None else round(growth_pct, 2),
            "prior_period": f"{prior[0]}-{prior[1]:02d}" if prior else None,
            "source": source if lineage_live else lineage_source,
            "provenance": (
                DataProvenance.live(source, 0.9)
                if lineage_live
                else DataProvenance.degraded(
                    source,
                    f"biomass panel used the fallback '{lineage_source}', not reported biomass",
                )
            ).to_dict(),
        }
    except Exception as exc:
        return {
            "period": None,
            "standing_biomass_tonnes": None,
            "harvest_tonnes": None,
            "biomass_change_pct": None,
            "prior_period": None,
            "source": source,
            "provenance": DataProvenance.degraded(source, str(exc)).to_dict(),
        }


async def _price_panel() -> dict:
    """Spot and 6-month forward read from the price feed hub."""
    try:
        from core.market.price_feed_hub import price_feed_hub

        spot = await price_feed_hub.get_spot_price()
        curve = await price_feed_hub.get_forward_curve(months=6)
        points = curve.get("curve") or curve.get("points") or []
        slope_pct = None
        if isinstance(points, list) and len(points) >= 2:
            first = points[0].get("price_nok") or points[0].get("price")
            last = points[-1].get("price_nok") or points[-1].get("price")
            if first and last:
                slope_pct = round((last - first) / first * 100.0, 2)
        spot_price = spot.get("price_nok") or spot.get("price")
        provenance = (
            DataProvenance.live(spot.get("source", "price_feed_hub"), 0.85)
            if spot_price
            else DataProvenance.degraded("price_feed_hub", "no live spot quote")
        )
        return {
            "spot_nok_per_kg": spot_price,
            "spot_source": spot.get("source"),
            "forward_6m_slope_pct": slope_pct,
            "forward_points": len(points) if isinstance(points, list) else 0,
            "provenance": provenance.to_dict(),
        }
    except Exception as exc:
        return {
            "spot_nok_per_kg": None,
            "spot_source": None,
            "forward_6m_slope_pct": None,
            "forward_points": 0,
            "provenance": DataProvenance.degraded("price_feed_hub", str(exc)).to_dict(),
        }


# ── The digest ───────────────────────────────────────────────────────────────

async def build(as_of: dt.datetime | None = None) -> dict:
    """Build the weekly digest (compute-only; nothing is stored)."""
    from core.source_lineage import to_utc

    stamp = to_utc(as_of)  # one week label, in UTC, for the digest and the store
    published = {
        code: await indices.compute(code, as_of=stamp) for code in indices.PUBLISHED_INDICES
    }
    sti = published[indices.AI_STI]
    supply = await _supply_panel()
    price = await _price_panel()

    tension = sti["value"]
    if tension is None:
        read = "unknown"
        headline = (
            "Index inputs are unavailable this week — no transmission read is claimed."
        )
    elif tension >= 60:
        read = "elevated"
        headline = (
            "Supply tension is elevated: biomass and harvest momentum point to tighter "
            "supply, which supports a firmer price path."
        )
    elif tension >= 40:
        read = "balanced"
        headline = "Supply tension is balanced: no strong directional read from the bio side."
    else:
        read = "loose"
        headline = (
            "Supply looks comfortable: bio-side pressure argues for a softer price path."
        )

    caveats: list[str] = []
    for code, result in published.items():
        if result["components_missing"]:
            caveats.append(f"{code} missing: " + ", ".join(result["components_missing"]))
        # a value computed from a fallback is degraded too, and the read rests on it
        caveats.extend(f"{code}: {note}" for note in result.get("lineage_notes") or [])
    if price["spot_nok_per_kg"] is None:
        caveats.append("no live spot quote — price panel degraded")
    if not supply["provenance"].get("is_live"):
        caveats.append(
            "biomass panel degraded: "
            + str(supply["provenance"].get("fallback_reason") or "no reported biomass")
        )

    provenance = (
        DataProvenance.degraded(
            "core.market.bio_price_weekly", "; ".join(caveats), 0.6
        )
        if caveats
        else DataProvenance.live("core.market.bio_price_weekly", 0.85)
    )

    return {
        "report": "Bio>Price Weekly",
        "version": REPORT_VERSION,
        "week": stamp.strftime("%G-W%V"),
        "as_of": stamp.isoformat(),
        "headline": headline,
        "transmission": {
            "read": read,
            "basis": "AI-STI supply tension",
            "note": (
                "A descriptive read of leading indicators, not a causal claim and not "
                "investment advice; see /api/indices/methodology."
            ),
        },
        "indices": published,
        "withdrawn": {
            code: entry["reason"] for code, entry in indices.WITHDRAWN_INDICES.items()
        },
        "supply": supply,
        "price": price,
        "caveats": caveats,
        "provenance": provenance.to_dict(),
        "permalink": "/indices#bio-price-weekly",
        "api": "/api/indices/bio-price-weekly",
    }


async def store_digest(digest: dict, codes: tuple[str, ...] | list[str] | None = None) -> dict[str, str]:
    """Store the index observations of a BUILT digest (idempotent per index +
    week + method version), for ``codes`` (default: the published set). Returns
    ``{index_code: "stored" | "duplicate"}`` and annotates each stored index
    result with its ``storage`` outcome. Callers gate on
    ``index_publication.readiness()`` first — the store itself refuses only a
    null value."""
    from core.market import index_publication

    statuses: dict[str, str] = {}
    targets = tuple(index_publication.INDEX_CODES) if codes is None else tuple(codes)
    for code in targets:
        storage = await indices.save_observation(digest["indices"][code])
        digest["indices"][code]["storage"] = storage
        statuses[code] = storage["status"]
    return statuses


async def publish_week(as_of: dt.datetime | None = None, *, force: bool = False) -> dict:
    """Build the digest and store the indices that are READY (the admin endpoint;
    the agent uses build/readiness/store_digest directly).

    The same readiness gate as the agent applies: an index with no value is never
    stored; within the readiness grace only a live value is stored. ``force=True``
    overrides the grace (a degraded value is stored early, provenance disclosed) —
    it can never store a null value. The digest carries ``readiness`` and, per
    index, a ``storage`` outcome of ``stored`` / ``duplicate`` / ``withheld``.
    """
    from core.market.index_publication import INDEX_CODES, readiness
    from core.source_lineage import to_utc

    stamp = to_utc(as_of)  # ONE instant: the built week, the readiness hour, the store
    digest = await build(as_of=stamp)
    ready = dict(readiness(digest, now=stamp))
    original_withheld = dict(ready["withheld"])  # the verdict before force
    withheld = dict(original_withheld)
    if force:
        # the grace may be overridden; a missing value may not
        codes = [code for code in INDEX_CODES if (digest["indices"][code] or {}).get("value") is not None]
        withheld = {code: why for code, why in withheld.items() if code not in codes}
    else:
        codes = list(ready["store"])
    if codes:
        await store_digest(digest, codes=codes)
    for code, why in withheld.items():
        digest["indices"][code]["storage"] = {"status": "withheld", "reason": why}
    # the readiness block reports what happened, not only the pre-force verdict:
    # overridden = grace-withheld indices actually STORED because of force (a
    # duplicate was not a write, so it is not a forced publication)
    overridden = [
        code for code in codes
        if code in original_withheld
        and (digest["indices"][code].get("storage") or {}).get("status") == "stored"
    ]
    ready["overridden"] = overridden
    ready["withheld"] = withheld
    ready["store"] = list(codes)
    ready["ready"] = bool(codes)
    digest["readiness"] = ready
    digest["forced"] = bool(force and overridden)
    log.info(
        "bio_price_weekly_published",
        week=digest.get("week"),
        read=(digest.get("transmission") or {}).get("read"),
        caveats=len(digest.get("caveats") or []),
        stored=codes,
        withheld=sorted(withheld),
        forced=digest["forced"],
    )
    return digest
