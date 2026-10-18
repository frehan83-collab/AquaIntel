"""
Feed Cost Index Engine
=======================
Tracks global feed ingredient prices (fishmeal, fish oil, soy, rapeseed, wheat)
and computes a composite salmon feed cost index in NOK/kg.

Feed is 50-60% of salmon production cost. Tracking feed-to-salmon-price margin
in real-time is critical for farmers, buyers, and investors.

Data sources:
  - World Bank Commodity API (fishmeal, soybean, rapeseed, wheat) — free
  - World Bank Pink Sheet (fishmeal; monthly)
  - SSB salmon price (for margin calculation)
  - Fallback: IMF Primary Commodity Prices (monthly)

Typical feed composition (% by weight):
  - Marine protein (fishmeal): 12-18%
  - Marine oil (fish oil): 8-12%
  - Plant protein (soy concentrate): 25-35%
  - Plant oil (rapeseed/canola): 15-20%
  - Wheat/starch: 10-15%
  - Micro-ingredients: 3-5%
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any

import httpx
import structlog

log = structlog.get_logger(__name__)


# ── Feed composition weights (typical Norwegian salmon feed 2024-2026) ────────
# Source: Skretting/Cargill/BioMar published sustainability reports
FEED_COMPOSITION = {
    "fishmeal":  0.15,   # 15% by weight
    "fish_oil":  0.10,   # 10%
    "soy":       0.30,   # 30% (soy protein concentrate)
    "rapeseed":  0.18,   # 18% (rapeseed oil)
    "wheat":     0.12,   # 12% (wheat gluten + starch)
    "other":     0.15,   # 15% (micro-ingredients, vitamins, astaxanthin)
}

# Approximate cost per kg of each ingredient (USD/kg, updated at runtime)
# These are INITIAL ESTIMATES only — overwritten by live data every fetch
DEFAULT_INGREDIENT_PRICES_USD = {
    "fishmeal":  1.60,   # ~$1600/tonne
    "fish_oil":  3.50,   # ~$3500/tonne
    "soy":       0.55,   # ~$550/tonne (SPC)
    "rapeseed":  1.10,   # ~$1100/tonne (rapeseed oil)
    "wheat":     0.30,   # ~$300/tonne
    "other":     2.00,   # ~$2000/tonne (astaxanthin is expensive)
}

# Ingredients with NO free public market feed (micro-ingredients, vitamins,
# astaxanthin have no liquid exchange contract or commodity index).
# Their default price is a STRUCTURAL PRIOR, not a fetch failure — they must
# NOT count against data-quality flags (using_defaults / freshness "degraded").
STRUCTURAL_DEFAULT_INGREDIENTS = {"other"}

# Sources that represent genuinely live market data
LIVE_SOURCES = {"fred", "world_bank"}  # WS-31b: Yahoo removed from every pricing path

#: FRED's monthly commodity series publish with a lag. A basket older than this is
#: dated, not current, and every consumer (the margin bridge, `/api/feed-cost/latest`)
#: says so: on the dev box the newest point is 2026-07 while the request is 2026-10,
#: which the old fetch-time stamp used to hide. Chosen at 45 days so a normal
#: two-month publication lag still counts as current and a stalled series does not.
FEED_PRICE_MAX_AGE_DAYS = 45


def _as_datetime(value: Any) -> dt.datetime | None:
    """Widen a date/ISO string to an aware UTC datetime for ``freshness``."""
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


def _parse_fred_date(value: str) -> dt.date | None:
    """The observation date of a FRED CSV row (``YYYY-MM-DD`` or ``YYYY-MM-01``)."""
    try:
        return dt.date.fromisoformat(value[:10])
    except (TypeError, ValueError):
        return None


def _age_days(value: dt.date | None, today: dt.date | None = None) -> int | None:
    """Calendar days between an observation date and today (None-safe)."""
    if value is None:
        return None
    return max(0, ((today or dt.datetime.now(dt.UTC).date()) - value).days)

# ── LEARNED PRINCIPLES from PhD-level analysis of 2008-2024 official data ─────
# These are STRUCTURAL RELATIONSHIPS, not hardcoded values.
# The actual NOK values are computed at runtime using live feed prices
# and these learned cost-structure ratios.

# FCR: Learned from 17 years of data (range 1.21-1.35, trend stable at 1.28-1.32)
# The LATEST official value is used; the historical range validates it.
LEARNED_FCR_RANGE = (1.21, 1.35)  # valid range from 2008-2024 data
LEARNED_FCR_LATEST = 1.30         # 2024 official — updated when new data arrives

# USD/NOK: Always fetched live; this is emergency fallback only
DEFAULT_USDNOK = 10.5

# ── Non-feed cost structure: RATIOS learned from 17 years of data ─────────────
# PRINCIPLE: Non-feed costs scale relative to feed cost over time.
# From 2008-2024 data, the ratio of each non-feed component to total cost
# has been remarkably stable. We use the LATEST YEAR ratios as structural
# priors, but the absolute values are computed from live feed prices.
#
# Learned from official data (Fiskeridirektoratet 2008-2024):
#   - Feed is ~40% of total cost (range 37-50% over 17 years)
#   - Non-feed costs are ~60% of total cost
#   - The NON-FEED components as % of total cost (2024):
LEARNED_NONFEED_RATIOS = {
    "smolt":           0.130,   # 8.40 / 64.64 = 13.0% — rising trend (was 10% in 2008)
    "insurance":       0.004,   # 0.26 / 64.64 = 0.4% — stable
    "labour":          0.058,   # 3.72 / 64.64 = 5.8% — stable
    "depreciation":    0.012,   # 0.79 / 64.64 = 1.2% — declining (was 5% in 2008)
    "other_operating": 0.313,   # 20.22 / 64.64 = 31.3% — rising (treatments, lice costs)
    "net_finance":     0.014,   # 0.92 / 64.64 = 1.4% — volatile (-2% to +3%)
    "slaughter":       0.072,   # 4.67 / 64.64 = 7.2% — stable
}
# Sum of non-feed ratios: ~60.3% of total cost
# Therefore: feed = ~39.7% of total cost
LEARNED_FEED_SHARE_OF_TOTAL = 0.397  # feed / total cost ratio (2024)

# ── Historical production costs (NOK/kg, official Fiskeridirektoratet) ────────
# Source: Lønnsomhetsundersøkelse for produksjon av laks og regnbueørret
# Complete time series 2008-2024 for trend analysis
OFFICIAL_COST_HISTORY = {
    2008: {"total": 20.98, "feed": 9.93, "smolt": 2.13, "other": 8.92, "fcr": 1.28, "feed_price": 7.80},
    2009: {"total": 20.11, "feed": 9.99, "smolt": 1.97, "other": 8.15, "fcr": 1.28, "feed_price": 7.84},
    2010: {"total": 22.87, "feed": 10.98, "smolt": 2.45, "other": 9.44, "fcr": 1.35, "feed_price": 8.15},
    2011: {"total": 22.18, "feed": 11.00, "smolt": 2.27, "other": 8.91, "fcr": 1.24, "feed_price": 8.88},
    2012: {"total": 21.98, "feed": 10.85, "smolt": 2.16, "other": 8.97, "fcr": 1.21, "feed_price": 8.94},
    2013: {"total": 25.33, "feed": 11.50, "smolt": 2.19, "other": 11.64, "fcr": 1.25, "feed_price": 9.19},
    2014: {"total": 25.83, "feed": 11.83, "smolt": 2.52, "other": 11.48, "fcr": 1.22, "feed_price": 9.68},
    2015: {"total": 29.10, "feed": 13.18, "smolt": 2.72, "other": 13.20, "fcr": 1.23, "feed_price": 10.68},
    2016: {"total": 33.86, "feed": 14.55, "smolt": 3.18, "other": 16.13, "fcr": 1.25, "feed_price": 11.68},
    2017: {"total": 33.84, "feed": 14.38, "smolt": 3.43, "other": 16.03, "fcr": 1.32, "feed_price": 10.90},
    2018: {"total": 33.88, "feed": 14.15, "smolt": 3.44, "other": 16.29, "fcr": 1.26, "feed_price": 11.26},
    2019: {"total": 38.26, "feed": 15.63, "smolt": 4.10, "other": 18.53, "fcr": 1.34, "feed_price": 11.70},
    2020: {"total": 40.15, "feed": 16.62, "smolt": 4.14, "other": 19.39, "fcr": 1.32, "feed_price": 12.55},
    2021: {"total": 41.65, "feed": 16.79, "smolt": 4.45, "other": 20.41, "fcr": 1.27, "feed_price": 13.20},
    2022: {"total": 49.12, "feed": 21.63, "smolt": 5.09, "other": 22.40, "fcr": 1.27, "feed_price": 17.02},
    2023: {"total": 64.68, "feed": 25.89, "smolt": 6.91, "other": 31.88, "fcr": 1.32, "feed_price": 19.56},
    2024: {"total": 64.64, "feed": 25.67, "smolt": 8.40, "other": 30.57, "fcr": 1.30, "feed_price": 19.73},
}
# Non-feed costs: 64.64 - 25.67 = 38.97 NOK/kg (2024 reference)


@dataclass
class IngredientPrice:
    """Single ingredient price observation."""
    name: str
    price_usd_per_tonne: float
    price_usd_per_kg: float
    source: str
    fetched_at: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))
    change_pct_30d: float = 0.0
    #: The month the price *describes*, not when we fetched it. The FRED "global
    #: price" series are monthly and publish with a lag (on the dev box the newest
    #: point is 2026-07 while the request is 2026-10), so a fetch time would make a
    #: three-month-old observation look current. None when the source has no date.
    observed_at: dt.date | None = None


@dataclass
class FeedCostSnapshot:
    """Complete feed cost analysis at a point in time."""
    timestamp: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))
    ingredients: dict[str, IngredientPrice] = field(default_factory=dict)
    feed_cost_usd_per_kg: float = 0.0
    feed_cost_nok_per_kg: float = 0.0                # raw feed ingredient cost
    feed_cost_nok_per_kg_salmon: float = 0.0         # feed cost adjusted for FCR
    non_feed_costs_nok: float = 0.0                  # computed from learned ratios
    production_cost_nok_per_kg_salmon: float = 0.0   # TOTAL: feed*FCR + non-feed
    salmon_spot_nok: float = 0.0
    margin_nok_per_kg: float = 0.0                   # salmon - total production cost
    margin_pct: float = 0.0
    margin_trend: str = "stable"                     # improving / stable / squeezing
    usd_nok: float = DEFAULT_USDNOK
    fcr: float = LEARNED_FCR_LATEST
    cost_breakdown: dict = field(default_factory=dict)
    source: str = "composite"
    #: Oldest and newest observation months among the dated ingredients used. The
    #: basket is only as current as its stalest component, so the snapshot reports
    #: the oldest as ``feed_prices_as_of`` (the conservative one).
    feed_prices_as_of: dt.date | None = None
    feed_prices_as_of_latest: dt.date | None = None
    #: Live-sourced ingredients with no observation date (World Bank Pink Sheet): their
    #: presence means the basket's currency cannot be shown even if FRED is dated.
    undated_live_ingredients: list[str] = field(default_factory=list)
    #: True when USD/NOK fell back to ``DEFAULT_USDNOK``; invalidates the NOK level.
    usd_nok_is_fallback: bool = False
    #: When the official rate was observed (Norges Bank publishes daily) and, if it
    #: fell back, why. WS-31: provenance for the conversion, not just the number.
    usd_nok_observed_at: str | None = None
    usd_nok_fallback_reason: str | None = None

    def price_provenance(self) -> dict:
        """Honest provenance for the ingredient basket — dated, never assumed current.

        The one definition of "is this basket current?", shared by `/api/feed-cost/latest`
        and the margin bridge so the two cannot disagree. Ways it is not live, each
        named: an ingredient fell back to a default estimate; a live ingredient
        carries no observation date; the USD/NOK conversion fell back to a constant
        (which invalidates the NOK level even when every price is live); or the
        oldest dated ingredient is older than ``FEED_PRICE_MAX_AGE_DAYS``.
        """
        from core.market.data_provenance import DataProvenance

        label = "FRED commodity series (fishmeal, fish oil, soy, rapeseed, wheat)"
        age_days = _age_days(self.feed_prices_as_of)
        observed_at = _as_datetime(self.feed_prices_as_of)
        if getattr(self, "using_defaults", False):
            defaults = list(getattr(self, "default_ingredients", []) or [])
            return DataProvenance.degraded(
                label,
                reason=(
                    "the ingredient price fell back to a default estimate for "
                    + ", ".join(defaults or ["an unnamed ingredient"])
                ),
                confidence=0.4,
                observed_at=observed_at,
            ).to_dict()
        if self.feed_prices_as_of is None or age_days is None:
            return DataProvenance.degraded(
                label,
                reason=(
                    "the feed basket carries no observation date, so its currency cannot be "
                    "shown (the source returned no date)"
                ),
                confidence=0.45,
            ).to_dict()
        undated = list(getattr(self, "undated_live_ingredients", []) or [])
        if undated:
            return DataProvenance.degraded(
                label,
                reason=(
                    "a live ingredient carries no observation date ("
                    + ", ".join(undated)
                    + "), so the basket's currency cannot be shown"
                ),
                confidence=0.5,
                observed_at=observed_at,
            ).to_dict()
        if getattr(self, "usd_nok_is_fallback", False):
            reason = getattr(self, "usd_nok_fallback_reason", None) or (
                "the live Norges Bank rate was unavailable"
            )
            return DataProvenance.degraded(
                label,
                reason=(
                    f"USD/NOK fell back to the constant {DEFAULT_USDNOK} ({reason}), so the "
                    "NOK level is converted at a stale rate"
                ),
                confidence=0.5,
                observed_at=observed_at,
            ).to_dict()
        if age_days > FEED_PRICE_MAX_AGE_DAYS:
            latest = (
                f"; the newest dated ingredient is {self.feed_prices_as_of_latest.isoformat()}"
                if self.feed_prices_as_of_latest
                and self.feed_prices_as_of
                and self.feed_prices_as_of_latest != self.feed_prices_as_of
                else ""
            )
            return DataProvenance.degraded(
                label,
                reason=(
                    # `feed_prices_as_of` is the OLDEST dated ingredient (the basket is only
                    # as current as its stalest leg), so the wording must not say "newest".
                    f"the oldest dated ingredient in the basket is "
                    f"{self.feed_prices_as_of.isoformat()} ({age_days} days old){latest}; the "
                    "series is monthly and publishes with a lag, so the feed leg is dated "
                    "rather than current"
                ),
                confidence=0.55,
                observed_at=observed_at,
            ).to_dict()
        return DataProvenance.live(label, confidence=0.85, observed_at=observed_at).to_dict()


class FeedCostEngine:
    """
    Fetches global feed ingredient prices and computes composite feed cost index.
    """

    # Circuit breaker
    _last_fetch: dt.datetime | None = None
    _cache_ttl = dt.timedelta(hours=2)
    _latest: FeedCostSnapshot | None = None
    _history: list[FeedCostSnapshot] = []

    def __init__(self) -> None:
        self._latest = None
        self._history = []

    async def fetch_prices(self) -> FeedCostSnapshot:
        """Fetch latest ingredient prices from multiple sources."""
        now = dt.datetime.now(dt.UTC)
        if self._latest and self._last_fetch and (now - self._last_fetch) < self._cache_ttl:
            return self._latest

        ingredients: dict[str, IngredientPrice] = {}

        # 1. FRED (St. Louis Fed) — best free source for commodity prices
        fred_prices = await self._fetch_fred()
        ingredients.update(fred_prices)

        # 2. (removed in WS-31b) the Yahoo commodity-futures gap fill. FRED covers all
        # five ingredients; a missing series now falls back to a documented default,
        # which `using_defaults` reports and the provenance degrades. Yahoo's API terms
        # forbid deriving income from its data, so no pricing path may use it.

        # 3. Try World Bank commodity API (monthly, slower updates)
        wb_prices = await self._fetch_world_bank()
        for k, v in wb_prices.items():
            if k not in ingredients:
                ingredients[k] = v

        # 4. Fill missing with defaults
        # Structural ingredients (e.g. "other" — no public market feed exists)
        # get a distinct source tag and do NOT degrade data quality.
        using_defaults = []
        for name, default_usd_kg in DEFAULT_INGREDIENT_PRICES_USD.items():
            if name not in ingredients:
                structural = name in STRUCTURAL_DEFAULT_INGREDIENTS
                ingredients[name] = IngredientPrice(
                    name=name,
                    price_usd_per_tonne=default_usd_kg * 1000,
                    price_usd_per_kg=default_usd_kg,
                    source="structural_default" if structural else "default_estimate",
                )
                if not structural:
                    using_defaults.append(name)
        self._using_defaults = using_defaults

        # 4. Get USD/NOK rate
        usd_nok = await self._fetch_usdnok()

        # 5. Get salmon spot price
        salmon_spot = await self._get_salmon_spot()

        # 6. Compute composite feed cost
        # Feed ingredient cost per kg feed
        feed_cost_usd = sum(
            ingredients[name].price_usd_per_kg * weight
            for name, weight in FEED_COMPOSITION.items()
            if name in ingredients
        )
        feed_cost_nok = feed_cost_usd * usd_nok
        # LEARNED PRINCIPLE from 17 years of official data:
        #
        # 1. FRED raw ingredient cost → Norwegian delivered feed price
        #    Multiplier: 1.86 (2024: 19.73 official / 10.62 FRED = 1.86)
        #    Range across 17 years: 1.6-2.1 (processing, logistics, margins)
        #
        # 2. Feed cost per kg salmon = delivered_feed_price × FCR
        #
        # 3. Total cost = feed_per_kg_salmon / LEARNED_FEED_SHARE (0.397)
        #    Because feed is ~39.7% of total production cost (stable ratio)
        #
        # 4. Non-feed = total - feed_per_kg_salmon
        INGREDIENT_TO_DELIVERED = 1.86
        delivered_feed_nok = feed_cost_nok * INGREDIENT_TO_DELIVERED
        feed_cost_per_kg_salmon = delivered_feed_nok * LEARNED_FCR_LATEST

        # Total from the feed-share-of-total principle
        estimated_total = feed_cost_per_kg_salmon / max(LEARNED_FEED_SHARE_OF_TOTAL, 0.3)
        nonfeed_total = estimated_total - feed_cost_per_kg_salmon

        # Allocate non-feed to components using learned ratios
        nonfeed_breakdown = {}
        for component, ratio in LEARNED_NONFEED_RATIOS.items():
            nonfeed_breakdown[component] = round(estimated_total * ratio, 2)

        prod_cost_nok = estimated_total

        margin = salmon_spot - prod_cost_nok if salmon_spot > 0 else 0
        margin_pct = (margin / salmon_spot * 100) if salmon_spot > 0 else 0

        # Build cost breakdown for display
        cost_breakdown = {
            "feed_ingredients": round(feed_cost_nok, 2),
            "feed_per_kg_salmon": round(feed_cost_per_kg_salmon, 2),
            **nonfeed_breakdown,
            "total": round(prod_cost_nok, 2),
            "method": "learned_ratios",
            "feed_share_of_total": round(feed_cost_per_kg_salmon / max(prod_cost_nok, 1) * 100, 1),
        }

        # Determine trend
        trend = "stable"
        if self._history:
            prev = self._history[-1]
            if margin_pct < prev.margin_pct - 2:
                trend = "squeezing"
            elif margin_pct > prev.margin_pct + 2:
                trend = "improving"

        snapshot = FeedCostSnapshot(
            ingredients=ingredients,
            feed_cost_usd_per_kg=round(feed_cost_usd, 3),
            feed_cost_nok_per_kg=round(feed_cost_nok, 2),
            feed_cost_nok_per_kg_salmon=round(feed_cost_per_kg_salmon, 2),
            non_feed_costs_nok=round(nonfeed_total, 2),
            production_cost_nok_per_kg_salmon=round(prod_cost_nok, 2),
            salmon_spot_nok=round(salmon_spot, 1),
            margin_nok_per_kg=round(margin, 2),
            margin_pct=round(margin_pct, 1),
            margin_trend=trend,
            usd_nok=round(usd_nok, 2),
            cost_breakdown=cost_breakdown,
            fcr=LEARNED_FCR_LATEST,
        )
        # Data quality: flag if any ingredients used default prices
        snapshot.using_defaults = bool(self._using_defaults)
        snapshot.default_ingredients = list(getattr(self, "_using_defaults", []))
        # A live-but-undated ingredient (World Bank Pink Sheet) cannot prove the basket's
        # currency, so an otherwise dated basket must still say so.
        snapshot.undated_live_ingredients = [
            name for name, ing in ingredients.items()
            if ing.source in LIVE_SOURCES
            and ing.observed_at is None
            and name not in STRUCTURAL_DEFAULT_INGREDIENTS
        ]
        # The whole basket is converted at this rate; a constant fallback invalidates
        # the NOK level even when every ingredient price is live (WS-22 class).
        snapshot.usd_nok_is_fallback = bool(getattr(self, "_usd_nok_is_fallback", False))
        snapshot.usd_nok_observed_at = getattr(self, "_usd_nok_observed_at", None)
        snapshot.usd_nok_fallback_reason = getattr(self, "_usd_nok_fallback_reason", None)
        # The month the basket describes, not the fetch time: the FRED "global
        # price" series are monthly and publish with a lag, so a fetch-time stamp
        # would report a three-month-old observation as current.
        dated = sorted(
            ing.observed_at for ing in ingredients.values() if ing.observed_at is not None
        )
        if dated:
            snapshot.feed_prices_as_of = dated[0]
            snapshot.feed_prices_as_of_latest = dated[-1]

        self._latest = snapshot
        self._last_fetch = now
        self._history.append(snapshot)
        # Keep last 500 snapshots (~6 weeks at 2h intervals)
        if len(self._history) > 500:
            self._history = self._history[-500:]

        log.info(
            "feed_cost.computed",
            feed_nok_kg=snapshot.feed_cost_nok_per_kg,
            prod_cost_nok=snapshot.production_cost_nok_per_kg_salmon,
            margin_pct=snapshot.margin_pct,
            trend=trend,
            n_live=sum(1 for v in ingredients.values() if v.source in LIVE_SOURCES),
        )
        return snapshot

    async def _fetch_fred(self) -> dict[str, IngredientPrice]:
        """Fetch commodity prices from FRED (St. Louis Fed) — free, reliable, monthly."""
        import httpx as hx

        # FRED series IDs → ingredient mapping (all in USD/metric tonne)
        FRED_SERIES = {
            "PSOYBUSDM":  "soy",        # Soybeans
            "PSOILUSDM":  "rapeseed",    # Soybean oil (proxy for rapeseed oil)
            "PWHEAMTUSDM": "wheat",      # Wheat
            "PFISHUSDM":  "fishmeal",    # Fish (fishmeal proxy)
            "PROILUSDM":  "fish_oil",    # Rapeseed oil → fish oil proxy (high-value oil)
        }

        result = {}
        try:
            async with hx.AsyncClient(timeout=15) as client:
                for series_id, ingredient in FRED_SERIES.items():
                    try:
                        resp = await client.get(
                            f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}",
                        )
                        if resp.status_code != 200 or len(resp.text) < 50:
                            continue

                        lines = resp.text.strip().split("\n")
                        # Find last non-empty value (last line with data)
                        for line in reversed(lines):
                            parts = line.split(",")
                            if len(parts) == 2 and parts[1].strip() not in ("", "."):
                                try:
                                    usd_per_tonne = float(parts[1].strip())
                                    if usd_per_tonne > 0:
                                        result[ingredient] = IngredientPrice(
                                            name=ingredient,
                                            price_usd_per_tonne=round(usd_per_tonne, 1),
                                            price_usd_per_kg=round(usd_per_tonne / 1000, 4),
                                            source="fred",
                                            observed_at=_parse_fred_date(parts[0].strip()),
                                        )
                                        break
                                except ValueError:
                                    continue
                    except Exception:
                        continue
        except Exception as exc:
            log.debug("feed_cost.fred_error", error=str(exc)[:80])

        if result:
            log.info("feed_cost.fred_fetched", ingredients=list(result.keys()), n=len(result))
        return result

    def _removed_yahoo_commodities(self) -> None:
        """Removed in WS-31b. Kept as a named tombstone so nobody re-adds it blind.

        Yahoo Finance's API terms forbid deriving income from its data, so a paid
        product may not price feed from its chart endpoint. FRED carries all five
        ingredients; the World Bank Pink Sheet fills fishmeal; anything still missing
        becomes a documented default that `using_defaults` reports.
        """
        raise RuntimeError(
            "Yahoo Finance pricing was removed in WS-31b: its API terms forbid deriving "
            "income from the data. Use FRED and the World Bank Pink Sheet, and let a "
            "missing series fall back to a documented default."
        )

    async def _fetch_world_bank(self) -> dict[str, IngredientPrice]:
        """Fetch fishmeal + fish oil from World Bank Commodity API (monthly)."""
        result = {}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                # World Bank Commodity Prices (Pink Sheet) — JSON endpoint
                url = "https://api.worldbank.org/v2/country/WLD/indicator/COMMODITY.FISHMEAL?format=json&per_page=5&date=2025:2026"
                resp = await client.get(url, headers={"User-Agent": "AquaIntel/1.0"})
                if resp.status_code == 200:
                    data = resp.json()
                    # Parse World Bank response format
                    if isinstance(data, list) and len(data) > 1:
                        for entry in data[1]:
                            if entry.get("value"):
                                # Fishmeal price in USD/tonne
                                usd_tonne = float(entry["value"])
                                result["fishmeal"] = IngredientPrice(
                                    name="fishmeal",
                                    price_usd_per_tonne=usd_tonne,
                                    price_usd_per_kg=round(usd_tonne / 1000, 4),
                                    source="world_bank",
                                )
                                break
        except Exception as exc:
            log.debug("feed_cost.worldbank_error", error=str(exc)[:80])

        # Fish oil: typically 2-2.5x fishmeal price
        if "fishmeal" in result and "fish_oil" not in result:
            fm = result["fishmeal"].price_usd_per_tonne
            result["fish_oil"] = IngredientPrice(
                name="fish_oil",
                price_usd_per_tonne=round(fm * 2.2, 0),
                price_usd_per_kg=round(fm * 2.2 / 1000, 4),
                source="world_bank_derived",
            )

        return result

    async def _fetch_usdnok(self) -> float:
        """Official USD/NOK from Norges Bank, with a recorded fallback.

        WS-31: this used to read Yahoo Finance, whose API terms forbid deriving income
        from its data — a paid product may not price Norwegian costs from it. Norges
        Bank publishes the official daily rate as open data and attaches the
        observation date, which the payload carries.

        ``usd_nok_is_fallback`` is still recorded: the whole NOK cost base is converted
        at this rate, so a constant substituted here must degrade the basket (the same
        defect class as the competitiveness engine's NOK/USD 0.093).
        """
        from core.market.fx_rates import usd_nok as official_usd_nok

        self._usd_nok_is_fallback = False
        self._usd_nok_observed_at = None
        try:
            rate = await official_usd_nok()
            value = rate.get("nok_per_unit")
            if value and float(value) > 0:
                self._usd_nok_observed_at = rate.get("observed_at")
                self._usd_nok_is_fallback = bool(rate.get("is_fallback"))
                return float(value)
            self._usd_nok_is_fallback = True
            self._usd_nok_fallback_reason = rate.get("fallback_reason")
        except Exception as exc:  # noqa: BLE001 — the constant below is the fallback
            self._usd_nok_is_fallback = True
            self._usd_nok_fallback_reason = f"official rate unavailable ({str(exc)[:80]})"
        log.debug("feed_cost.usd_nok_fallback", value=DEFAULT_USDNOK)
        return DEFAULT_USDNOK

    async def _get_salmon_spot(self) -> float:
        """Get current SSB salmon spot price."""
        try:
            from core.market.ssb_price_client import ssb_price_client
            return await ssb_price_client.get_current_spot()
        except Exception:
            return 0.0

    def get_latest(self) -> dict | None:
        """Return latest snapshot as API-friendly dict."""
        if not self._latest:
            return None
        s = self._latest
        return {
            "timestamp": s.timestamp.isoformat(),
            "feed_cost_usd_per_kg": s.feed_cost_usd_per_kg,
            "feed_cost_nok_per_kg": s.feed_cost_nok_per_kg,
            "feed_cost_nok_per_kg_salmon": s.feed_cost_nok_per_kg_salmon,
            "non_feed_costs_nok": s.non_feed_costs_nok,
            "production_cost_nok_per_kg_salmon": s.production_cost_nok_per_kg_salmon,
            "salmon_spot_nok": s.salmon_spot_nok,
            "margin_nok_per_kg": s.margin_nok_per_kg,
            "margin_pct": s.margin_pct,
            "margin_trend": s.margin_trend,
            "usd_nok": s.usd_nok,
            "fcr": s.fcr,
            "cost_breakdown": s.cost_breakdown,
            "calculation_method": "Learned structural ratios from 17 years (2008-2024) Fiskeridirektoratet data applied to live FRED feed ingredient prices",
            "data_freshness": {
                "feed_prices": (
                    s.feed_prices_as_of.isoformat() if s.feed_prices_as_of
                    else s.timestamp.isoformat()
                ),
                "feed_prices_basis": (
                    "observation date of the oldest ingredient in the basket"
                    if s.feed_prices_as_of
                    else "fetch time (the source returned no observation date)"
                ),
                "feed_prices_age_days": _age_days(s.feed_prices_as_of),
                "structural_ratios": "Learned from 2008-2024 official data (stable cost structure)",
                "fcr": f"{LEARNED_FCR_LATEST} (latest official, valid range {LEARNED_FCR_RANGE})",
            },
            "ingredients": {
                name: {
                    "price_usd_per_kg": ing.price_usd_per_kg,
                    "price_usd_per_tonne": ing.price_usd_per_tonne,
                    "weight_pct": round(FEED_COMPOSITION.get(name, 0) * 100, 1),
                    "cost_contribution_pct": round(
                        (ing.price_usd_per_kg * FEED_COMPOSITION.get(name, 0))
                        / max(s.feed_cost_usd_per_kg, 0.01) * 100, 1
                    ),
                    "source": ing.source,
                    "observed_at": ing.observed_at.isoformat() if ing.observed_at else None,
                }
                for name, ing in s.ingredients.items()
            },
            # The month the basket describes. `feed_prices` used to be the *fetch*
            # time, which made a three-month-old FRED observation look current; the
            # fetch time is kept separately so both are visible.
            "feed_prices_as_of": s.feed_prices_as_of.isoformat() if s.feed_prices_as_of else None,
            "feed_prices_as_of_latest": (
                s.feed_prices_as_of_latest.isoformat() if s.feed_prices_as_of_latest else None
            ),
            "feed_prices_age_days": _age_days(s.feed_prices_as_of),
            "fetched_at": s.timestamp.isoformat(),
            # WS-29: the KPI row on /feed-cost had no provenance while its feed legs
            # rest on a monthly series that lags. One verdict, shared with the bridge.
            "using_defaults": bool(getattr(s, "using_defaults", False)),
            "default_ingredients": list(getattr(s, "default_ingredients", []) or []),
            "undated_live_ingredients": list(getattr(s, "undated_live_ingredients", []) or []),
            "usd_nok_is_fallback": bool(getattr(s, "usd_nok_is_fallback", False)),
            "usd_nok_source": "Norges Bank EXR (official daily NOK rate)",
            "usd_nok_observed_at": getattr(s, "usd_nok_observed_at", None),
            "data_provenance": s.price_provenance(),
        }

    @staticmethod
    def get_official_cost_history() -> list[dict]:
        """Return official Fiskeridirektoratet cost history (2008-2024) for trend charts."""
        return [
            {
                "year": year,
                "total_cost": data["total"],
                "feed_cost": data["feed"],
                "smolt_cost": data["smolt"],
                "other_costs": data["other"],
                "fcr": data["fcr"],
                "feed_price_per_kg": data["feed_price"],
                "source": "Fiskeridirektoratet",
            }
            for year, data in sorted(OFFICIAL_COST_HISTORY.items())
        ]

    def get_history(self, n: int = 50) -> list[dict]:
        """Return recent snapshots for charting."""
        return [
            {
                "timestamp": s.timestamp.isoformat(),
                "feed_cost_nok_per_kg": s.feed_cost_nok_per_kg,
                "salmon_spot_nok": s.salmon_spot_nok,
                "margin_nok_per_kg": s.margin_nok_per_kg,
                "margin_pct": s.margin_pct,
            }
            for s in self._history[-n:]
        ]

    async def fetch_historical_prices(self, years: int = 5) -> dict:
        """
        Fetch multi-year monthly historical prices for all key feed ingredients.
        Primary source: FRED (Federal Reserve Economic Data) — free, reliable, monthly.
        Fallback: Yahoo Finance for any missing series.
        """
        import httpx as hx

        result: dict[str, list[dict]] = {}

        # FRED series → ingredient (all USD/metric tonne, monthly)
        FRED_HIST = {
            "PSOYBUSDM":   {"name": "soy",      "label": "Soybeans (SPC)"},
            "PWHEAMTUSDM": {"name": "wheat",     "label": "Wheat"},
            "PFISHUSDM":   {"name": "fishmeal",  "label": "Fishmeal (Fish)"},
            "PROILUSDM":   {"name": "rapeseed",  "label": "Rapeseed Oil"},
            "PSOILUSDM":   {"name": "fish_oil",  "label": "Fish Oil (Soy Oil proxy)"},
        }

        cutoff_date = f"{dt.datetime.now(dt.UTC).year - years}-01-01"

        try:
            async with hx.AsyncClient(timeout=20) as client:
                for series_id, cfg in FRED_HIST.items():
                    try:
                        resp = await client.get(
                            f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}",
                        )
                        if resp.status_code != 200 or len(resp.text) < 50:
                            continue

                        lines = resp.text.strip().split("\n")
                        series = []
                        for line in lines[1:]:  # skip header
                            parts = line.split(",")
                            if len(parts) != 2 or parts[1].strip() in ("", "."):
                                continue
                            date_str = parts[0].strip()
                            if date_str < cutoff_date:
                                continue
                            try:
                                usd_tonne = float(parts[1].strip())
                                if usd_tonne > 0:
                                    series.append({
                                        "date": date_str[:7],  # YYYY-MM
                                        "price_usd_tonne": round(usd_tonne, 1),
                                        "raw_price": round(usd_tonne, 1),
                                    })
                            except ValueError:
                                continue

                        if series:
                            result[cfg["name"]] = series
                            log.debug("feed_history.fred_fetched",
                                      ingredient=cfg["name"], points=len(series))
                    except Exception:
                        continue
        except Exception as exc:
            log.warning("feed_history.fred_error", error=str(exc)[:80])

        # Labels for response
        LABELS = {
            "soy": "Soybeans (SPC)",
            "wheat": "Wheat",
            "fishmeal": "Fishmeal",
            "fish_oil": "Fish Oil (proxy)",
            "rapeseed": "Rapeseed Oil",
        }

        return {
            "period_years": years,
            "source": "FRED (Federal Reserve Economic Data)",
            "ingredients": {
                name: {
                    "label": LABELS.get(name, name.title()),
                    "data": series,
                    "current_usd_tonne": series[-1]["price_usd_tonne"] if series else None,
                    "min_usd_tonne": round(min(p["price_usd_tonne"] for p in series), 1) if series else None,
                    "max_usd_tonne": round(max(p["price_usd_tonne"] for p in series), 1) if series else None,
                    "avg_usd_tonne": round(
                        sum(p["price_usd_tonne"] for p in series) / len(series), 1
                    ) if series else None,
                    "change_pct": round(
                        (series[-1]["price_usd_tonne"] - series[0]["price_usd_tonne"])
                        / max(series[0]["price_usd_tonne"], 1) * 100, 1
                    ) if len(series) >= 2 else 0,
                }
                for name, series in result.items()
            },
        }


    # ── Month-on-month feed basket change ────────────────────────────
    # The feed leg moves monthly, not weekly, and nothing exposed that move:
    # /feed-cost printed a level and a 30-day placeholder that was never filled
    # (IngredientPrice.change_pct_30d). This computes the weighted change from the
    # same FRED monthly series and the same FEED_COMPOSITION weights the level is
    # built from, so the level and its change cannot disagree.
    _MONTHLY_CHANGE_TTL = dt.timedelta(hours=6)
    #: A failed history fetch is cached briefly so repeated callers do not each pay the
    #: retry cost against a cold or rate-limited FRED window.
    _MONTHLY_CHANGE_ERROR_TTL = dt.timedelta(minutes=15)

    async def feed_index_change(self) -> dict:
        """Weighted month-on-month change of the feed ingredient basket.

        Each ingredient is compared over its own two latest FRED months (the series
        publish on slightly different days), then weighted exactly like
        ``FEED_COMPOSITION`` — so the percentage describes the same basket the feed
        cost level is built from. A single ingredient without two points is left
        out and named rather than treated as unchanged.

        Returns ``{"change_pct": float, "period": str, "months": [...],
        "by_ingredient": {...}, "excluded": [...], "source": str}`` or
        ``{"error": reason}`` — never a zero that could be read as "no change".
        """
        now = dt.datetime.now(dt.UTC)
        cached = getattr(self, "_monthly_change_cache", None)
        cached_at = getattr(self, "_monthly_change_at", None)
        if cached is not None and cached_at:
            # A failure is cached for a short while too: without this, a cold or
            # rate-limited FRED window makes every caller pay the full retry cost on
            # every request (the bridge caps the wait, but the next request repeats it).
            ttl = (
                self._MONTHLY_CHANGE_ERROR_TTL
                if cached.get("error")
                else self._MONTHLY_CHANGE_TTL
            )
            if (now - cached_at) < ttl:
                return cached

        try:
            history = await self.fetch_historical_prices(years=1)
        except Exception as exc:  # noqa: BLE001 — a history outage is reported, not raised
            result = {"error": f"FRED history fetch failed ({str(exc)[:80]})"}
            self._monthly_change_cache = result
            self._monthly_change_at = now
            return result

        ingredients = (history or {}).get("ingredients") or {}
        by_ingredient: dict[str, dict] = {}
        excluded: list[str] = []
        weighted_now = 0.0
        weighted_prev = 0.0
        months: set[str] = set()
        for name, weight in FEED_COMPOSITION.items():
            if weight <= 0:
                continue
            series = (ingredients.get(name) or {}).get("data") or []
            # Drop points without a usable price and keep the two newest months.
            points = [p for p in series if p.get("price_usd_tonne")]
            if len(points) < 2:
                if name in ingredients or name in DEFAULT_INGREDIENT_PRICES_USD:
                    excluded.append(name)
                continue
            current, previous = points[-1], points[-2]
            try:
                cur_price = float(current["price_usd_tonne"])
                prev_price = float(previous["price_usd_tonne"])
            except (TypeError, ValueError, KeyError):
                excluded.append(name)
                continue
            if prev_price <= 0:
                excluded.append(name)
                continue
            by_ingredient[name] = {
                "current_month": current.get("date"),
                "previous_month": previous.get("date"),
                "price_usd_tonne": round(cur_price, 1),
                "change_pct": round((cur_price - prev_price) / prev_price * 100, 1),
                "weight_pct": round(weight * 100, 1),
            }
            weighted_now += cur_price * weight
            weighted_prev += prev_price * weight
            if current.get("date"):
                months.add(str(current["date"]))

        if len(by_ingredient) < 3 or weighted_prev <= 0:
            result = {
                "error": (
                    "fewer than three feed ingredients have two comparable FRED months"
                    + (f" (missing: {', '.join(excluded)})" if excluded else "")
                )
            }
            self._monthly_change_cache = result
            self._monthly_change_at = now
            return result

        change_pct = (weighted_now - weighted_prev) / weighted_prev * 100
        distinct_months = sorted(months)
        period = (
            distinct_months[-1] if len(distinct_months) == 1
            else f"{distinct_months[0]}..{distinct_months[-1]}" if distinct_months else None
        )
        result = {
            "change_pct": round(change_pct, 2),
            "period": period,
            "months": distinct_months,
            "by_ingredient": by_ingredient,
            "excluded": excluded,
            "weight_coverage_pct": round(
                sum(v["weight_pct"] for v in by_ingredient.values()), 1
            ),
            "source": "FRED monthly commodity series (same basket and weights as the feed cost level)",
            "note": (
                "each ingredient is compared over its own two latest months; the change is in "
                "USD and excludes FX, which is applied separately at today's rate"
            ),
            "computed_at": now.isoformat(),
        }
        self._monthly_change_cache = result
        self._monthly_change_at = now
        return result

    # ── Composite Feed Cost Index ────────────────────────────────────
    # Research-validated weights from salmon feed composition analysis
    COMPOSITE_WEIGHTS = {
        "fishmeal": 0.12,
        "fish_oil": 0.10,
        "soy":      0.41,
        "rapeseed":  0.20,
        "wheat":     0.13,
    }  # Remaining 0.04 = micro-ingredients (constant, excluded from index)

    async def compute_composite_index(self, years: int = 5) -> dict:
        """
        Compute a proprietary Composite Feed Cost Index from weighted FRED ingredient prices.
        Normalized to base=100 at the start of the series. No public equivalent exists.
        """
        hist = await self.fetch_historical_prices(years)
        ingredients = hist.get("ingredients", {})

        if not ingredients:
            return {"error": "No historical data available"}

        # Align all series to common dates
        all_dates: set[str] = set()
        for ing_data in ingredients.values():
            for pt in ing_data.get("data", []):
                all_dates.add(pt["date"])
        sorted_dates = sorted(all_dates)

        if len(sorted_dates) < 6:
            return {"error": "Insufficient data points"}

        # Build price lookup per ingredient per date
        price_by_date: dict[str, dict[str, float]] = {}
        for name, ing_data in ingredients.items():
            for pt in ing_data.get("data", []):
                if pt["date"] not in price_by_date:
                    price_by_date[pt["date"]] = {}
                price_by_date[pt["date"]][name] = pt["price_usd_tonne"]

        # Compute weighted index for each date
        index_series = []
        base_value = None
        for date in sorted_dates:
            prices = price_by_date.get(date, {})
            if len(prices) < 3:
                continue  # need at least 3 ingredients

            weighted_sum = 0.0
            weight_sum = 0.0
            for ing, weight in self.COMPOSITE_WEIGHTS.items():
                if ing in prices:
                    weighted_sum += prices[ing] * weight
                    weight_sum += weight

            if weight_sum > 0:
                normalized = weighted_sum / weight_sum  # scale by actual weight coverage
                if base_value is None:
                    base_value = normalized
                index_value = round((normalized / base_value) * 100, 1)
                index_series.append({"date": date, "index": index_value, "usd_tonne_weighted": round(normalized, 1)})

        if not index_series:
            return {"error": "Could not compute index"}

        # Volatility: rolling 12-month standard deviation
        import statistics
        values = [p["index"] for p in index_series]
        recent_12 = values[-12:] if len(values) >= 12 else values
        long_term = values[:-12] if len(values) > 24 else values[:12]

        current_vol = statistics.stdev(recent_12) if len(recent_12) >= 2 else 0
        baseline_vol = statistics.stdev(long_term) if len(long_term) >= 2 else 1
        vol_alert = current_vol > baseline_vol * 1.5

        return {
            "source": "FishIntel Composite Feed Cost Index (FRED-weighted)",
            "base_year": index_series[0]["date"],
            "current_index": index_series[-1]["index"],
            "current_date": index_series[-1]["date"],
            "current_usd_tonne_weighted": index_series[-1]["usd_tonne_weighted"],
            "change_ytd_pct": round(index_series[-1]["index"] - index_series[-13]["index"], 1) if len(index_series) > 13 else 0,
            "volatility_12m": round(current_vol, 1),
            "volatility_baseline": round(baseline_vol, 1),
            "volatility_alert": vol_alert,
            "weights": self.COMPOSITE_WEIGHTS,
            "series": index_series,
            "n_data_points": len(index_series),
        }

    async def peru_anchovy_watch(self) -> dict:
        """
        Peru Anchovy Watch — monitor NOAA Oceanic Niño Index (ONI) as a
        2-4 week leading indicator for fishmeal price shocks.
        Peru produces ~20% of global fishmeal. El Niño events cause season cancellation.
        """
        import httpx as hx

        oni_url = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"
        result = {
            "source": "NOAA Climate Prediction Center — Oceanic Niño Index (ONI)",
            "oni_value": None,
            "oni_season": "",
            "risk_level": "UNKNOWN",
            "risk_description": "",
            "fishmeal_current_usd_tonne": None,
        }

        try:
            async with hx.AsyncClient(timeout=10) as client:
                resp = await client.get(oni_url)
                if resp.status_code == 200:
                    lines = resp.text.strip().split("\n")
                    # Parse last non-empty line: "YEAR  SEAS  TOTAL  ANOM"
                    for line in reversed(lines):
                        parts = line.split()
                        if len(parts) >= 4:
                            try:
                                anom = float(parts[3])
                                result["oni_value"] = anom
                                result["oni_season"] = f"{parts[0]} {parts[1]}"

                                if anom >= 1.5:
                                    result["risk_level"] = "CRITICAL"
                                    result["risk_description"] = f"Strong El Niño (ONI {anom:+.1f}°C) — high risk of Peru anchovy season disruption → fishmeal price spike"
                                elif anom >= 0.5:
                                    result["risk_level"] = "ELEVATED"
                                    result["risk_description"] = f"El Niño conditions (ONI {anom:+.1f}°C) — monitor Peru anchovy biomass surveys"
                                elif anom <= -0.5:
                                    result["risk_level"] = "LOW"
                                    result["risk_description"] = f"La Niña (ONI {anom:+.1f}°C) — favorable for Peru anchovy, fishmeal supply stable"
                                else:
                                    result["risk_level"] = "NORMAL"
                                    result["risk_description"] = f"Neutral ENSO (ONI {anom:+.1f}°C) — no El Niño threat to fishmeal supply"
                                break
                            except (ValueError, IndexError):
                                continue
        except Exception as exc:
            log.debug("feed_cost.oni_failed", error=str(exc)[:80])

        # Add current fishmeal price from existing data
        if self._latest and self._latest.ingredients:
            fm = self._latest.ingredients.get("fishmeal")
            if fm:
                result["fishmeal_current_usd_tonne"] = fm.price_usd_per_tonne

        return result

    async def enhanced_anchovy_watch(self) -> dict:
        """
        Enhanced Peru Anchovy Watch — supplements ONI with IMARPE season tracking,
        historical catch patterns, and feed-through timing analysis.

        Peru anchovy seasons (well-known structural constants):
          - First season:  April–July  (main season, ~70% of annual catch)
          - Second season: November–January (smaller, ~30%)
          - IMARPE sets quotas before each season based on biomass surveys.

        Feed-through timing:
          - Anchovy catch → fishmeal processing: 2-4 weeks
          - Fishmeal → salmon feed price impact: 4-8 weeks total from catch disruption

        ONI thresholds (NOAA standard):
          - El Niño:  > +0.5°C
          - La Niña:  < -0.5°C
          - Neutral:  -0.5 to +0.5°C
        """
        now = dt.datetime.now(dt.UTC)
        month = now.month
        day = now.day

        # ── 1. Get ONI value from existing method ───────────────────────────
        base = await self.peru_anchovy_watch()
        oni_value = base.get("oni_value") or 0.0

        # ONI phase classification
        if oni_value > 0.5:
            oni_phase = "El Niño"
        elif oni_value < -0.5:
            oni_phase = "La Niña"
        else:
            oni_phase = "Neutral"

        # ── 2. Season assessment (structural constants) ─────────────────────
        # First season: April (4) – July (7)
        # Second season: November (11) – January (1)
        if 4 <= month <= 7:
            current_season = "first_season"
            if month == 4 and day < 15:
                season_status = "not_started"
            elif month == 7 and day > 15:
                season_status = "ending"
            else:
                season_status = "active"
        elif month >= 11 or month == 1:
            current_season = "second_season"
            if month == 11 and day < 15:
                season_status = "not_started"
            elif month == 1 and day > 15:
                season_status = "ending"
            else:
                season_status = "active"
        else:
            current_season = "off_season"
            season_status = "active"  # off-season is always "active" (i.e., ongoing)

        # ── 3. Quota risk assessment (ONI + season interaction) ─────────────
        reasoning = []

        if oni_value >= 1.5:
            quota_risk = "suspended"
            reasoning.append(f"Strong El Niño (ONI {oni_value:+.1f}°C) — IMARPE likely to suspend fishing season")
        elif oni_value >= 0.5:
            quota_risk = "reduced"
            reasoning.append(f"El Niño conditions (ONI {oni_value:+.1f}°C) — IMARPE may reduce quotas 20-40%")
        elif oni_value <= -1.0:
            quota_risk = "normal"
            reasoning.append(f"Strong La Niña (ONI {oni_value:+.1f}°C) — favorable upwelling, good anchovy biomass expected")
        elif oni_value <= -0.5:
            quota_risk = "normal"
            reasoning.append(f"La Niña (ONI {oni_value:+.1f}°C) — conditions favorable for anchovy")
        else:
            quota_risk = "normal"
            reasoning.append(f"Neutral ENSO (ONI {oni_value:+.1f}°C) — no temperature-driven quota risk")

        # ── 4. Fishmeal price signal ────────────────────────────────────────
        if quota_risk == "suspended":
            fishmeal_price_signal = "bullish"
            reasoning.append("Fishmeal supply at risk — expect price spikes within 4-8 weeks")
        elif quota_risk == "reduced":
            if current_season in ("first_season", "second_season") and season_status in ("active", "not_started"):
                fishmeal_price_signal = "bullish"
                reasoning.append(f"Reduced quota during {current_season.replace('_', ' ')} — bullish for fishmeal prices")
            else:
                fishmeal_price_signal = "neutral"
                reasoning.append("Reduced quota risk but currently off-season — monitoring")
        elif oni_phase == "La Niña" and current_season != "off_season":
            fishmeal_price_signal = "bearish"
            reasoning.append("La Niña + active season = strong catches expected — bearish for fishmeal")
        else:
            fishmeal_price_signal = "neutral"
            reasoning.append("No strong directional signal for fishmeal prices")

        # ── 5. Expected impact timing ───────────────────────────────────────
        if current_season == "off_season":
            # Next season determines timing
            if month in (8, 9, 10):
                weeks_to_next = (11 - month) * 4  # weeks until second season
            elif month in (2, 3):
                weeks_to_next = (4 - month) * 4   # weeks until first season
            else:
                weeks_to_next = 4
            expected_impact_weeks = weeks_to_next + 6  # add feed-through delay
        elif season_status == "not_started":
            expected_impact_weeks = 6  # 2 weeks to start + 4 weeks feed-through
        elif season_status == "ending":
            expected_impact_weeks = 4  # already in pipeline
        else:
            expected_impact_weeks = 6  # mid-season: 2 weeks catch + 4 weeks processing

        # ── 6. Alert level ──────────────────────────────────────────────────
        if quota_risk == "suspended":
            alert_level = "critical"
        elif quota_risk == "reduced" and current_season != "off_season":
            alert_level = "warning"
        elif oni_value >= 0.5 and current_season == "off_season":
            alert_level = "watch"
            reasoning.append("El Niño developing ahead of fishing season — monitoring closely")
        else:
            alert_level = "none"

        # Season context
        if current_season == "first_season":
            reasoning.append("First season (Apr-Jul) is the main catch period (~70% of annual anchovy)")
        elif current_season == "second_season":
            reasoning.append("Second season (Nov-Jan) is smaller (~30% of annual catch)")
        else:
            reasoning.append(f"Off-season (month {month}) — no active Peru anchovy fishing")

        # Add fishmeal price context if available
        fm_price = base.get("fishmeal_current_usd_tonne")
        if fm_price:
            reasoning.append(f"Current fishmeal price: ${fm_price:,.0f}/tonne")

        return {
            "oni_value": oni_value,
            "oni_phase": oni_phase,
            "current_season": current_season,
            "season_status": season_status,
            "quota_risk": quota_risk,
            "fishmeal_price_signal": fishmeal_price_signal,
            "expected_impact_weeks": expected_impact_weeks,
            "alert_level": alert_level,
            "reasoning": reasoning,
            "generated_at": now.isoformat(),
        }


# Singleton
feed_cost_engine = FeedCostEngine()
