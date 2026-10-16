"""Bio→Price Weekly v1 — the flagship weekly digest.

Composes the two named indices with the supply and price panels into one weekly,
versioned report whose every number carries its source. The point of the product
is the *link*: biomass and lice pressure are leading indicators for price, and the
report states the direction it reads — while refusing to claim causality it cannot
evidence.

Published by ``publish_week()`` (the weekly job / agent calls it); readable at
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
        biomass = await indices.national_totals("standing_biomass_tonnes")
        harvest = await indices.national_totals("harvest_tonnes")
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
            "source": source,
            "provenance": DataProvenance.live(source, 0.9).to_dict(),
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
    stamp = as_of or dt.datetime.now(dt.UTC)
    sti = await indices.compute(indices.AI_STI, as_of=stamp)
    lpi = await indices.compute(indices.AI_LPI, as_of=stamp)
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
            "Supply tension is elevated: biomass and lice pressure support a firmer "
            "price path."
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
    if sti["components_missing"]:
        caveats.append("AI-STI missing: " + ", ".join(sti["components_missing"]))
    if lpi["components_missing"]:
        caveats.append("AI-LPI missing: " + ", ".join(lpi["components_missing"]))
    if price["spot_nok_per_kg"] is None:
        caveats.append("no live spot quote — price panel degraded")
    if not supply["standing_biomass_tonnes"]:
        caveats.append("biomass panel degraded")

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
        "indices": {indices.AI_STI: sti, indices.AI_LPI: lpi},
        "supply": supply,
        "price": price,
        "caveats": caveats,
        "provenance": provenance.to_dict(),
        "permalink": "/indices#bio-price-weekly",
        "api": "/api/indices/bio-price-weekly",
    }


async def publish_week(as_of: dt.datetime | None = None) -> dict:
    """Build the digest AND store both index observations (the weekly job)."""
    digest = await build(as_of=as_of)
    for code in (indices.AI_STI, indices.AI_LPI):
        digest["indices"][code]["storage"] = await indices.save_observation(
            digest["indices"][code]
        )
    log.info(
        "bio_price_weekly_published",
        week=digest["week"],
        read=digest["transmission"]["read"],
        caveats=len(digest["caveats"]),
    )
    return digest
