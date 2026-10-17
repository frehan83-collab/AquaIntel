"""
FX-Adjusted Origin Competitiveness Index
==========================================
Computes USD-equivalent delivered cost of salmon from each producing origin,
incorporating live FX rates, production costs, US tariffs, and freight.

Rankings show which origins deliver cheapest to the US market in real-time.
Norway cost is LIVE from feed_cost_engine; others use industry benchmarks
in local currency, converted via live FX.

Data sources: FRED (via macro_intelligence), Yahoo Finance FX, feed_cost_engine.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import httpx
import structlog

from core.regulatory_facts import us_salmon_tariff

log = structlog.get_logger(__name__)


def _now() -> dt.datetime:
    """The clock (a seam for tests)."""
    return dt.datetime.now(dt.UTC)


# ── Per-Origin Baseline Costs (local currency) ──────────────────────────────
# Norway: LIVE from feed_cost_engine (validated to 0.1% vs official)
# Others: Industry estimates (SalmonChile, SSPO, Bakkafrost reports, DFO)
ORIGIN_BASELINES = {
    "Norway": {
        "local_cost": None,  # LIVE from feed_cost_engine
        "currency": "NOK",
        "freight_usd": 0.45,         # Air freight to US East Coast
        "flag": "\U0001f1f3\U0001f1f4",
        "notes": "Fiskeridirektoratet validated.",
    },
    "Chile": {
        "local_cost": 3400,          # CLP/kg
        "currency": "CLP",
        "freight_usd": 0.35,         # Shorter route to US West Coast
        "flag": "\U0001f1e8\U0001f1f1",
        "notes": "Largest supplier to the US market.",
    },
    "Scotland": {
        "local_cost": 4.10,          # GBP/kg
        "currency": "GBP",
        "freight_usd": 0.40,
        "flag": "\U0001f3f4\U000e0067\U000e0062\U000e0073\U000e0063\U000e0074\U000e007f",
        "notes": "PD endemic adds treatment cost.",
    },
    "Canada": {
        "local_cost": 5.80,          # CAD/kg
        "currency": "CAD",
        "freight_usd": 0.15,         # Short trucking distance
        "flag": "\U0001f1e8\U0001f1e6",
        "notes": "BC open net-pen ban June 2029.",
    },
    "Faroe Islands": {
        "local_cost": 42.0,          # DKK/kg
        "currency": "DKK",
        "freight_usd": 0.50,
        "flag": "\U0001f1eb\U0001f1f4",
        "notes": "Bakkafrost ~95%.",
    },
    "Iceland": {
        "local_cost": 900.0,         # ISK/kg
        "currency": "ISK",
        "freight_usd": 0.55,
        "flag": "\U0001f1ee\U0001f1f8",
        "notes": "Disease-free status. Fastest-growing origin.",
    },
}

# Yahoo Finance tickers for FX rates not in FRED
YAHOO_FX_TICKERS = {
    "CLP": "CLPUSD=X",
    "GBP": "GBPUSD=X",
    "DKK": "DKKUSD=X",
    "ISK": "ISKUSD=X",
    "CAD": "CADUSD=X",
}

# Fallback FX rates (approximate, used if Yahoo fails)
FALLBACK_FX = {
    "NOK": 0.093,   # 1 NOK = $0.093
    "CLP": 0.00105, # 1 CLP = $0.00105
    "GBP": 1.27,    # 1 GBP = $1.27
    "DKK": 0.145,   # 1 DKK = $0.145
    "ISK": 0.0072,  # 1 ISK = $0.0072
    "CAD": 0.74,    # 1 CAD = $0.74
}


@dataclass
class OriginCost:
    """Delivered cost breakdown for one origin."""
    country: str
    flag: str
    currency: str
    local_cost_per_kg: float
    fx_rate_to_usd: float
    production_cost_usd: float
    tariff_pct: float
    tariff_cost_usd: float
    freight_usd: float
    total_delivered_usd: float
    margin_usd: float
    margin_pct: float
    rank: int = 0
    notes: str = ""
    tariff_row: dict | None = None  # the dated, sourced row behind tariff_pct


@dataclass
class CompetitivenessSnapshot:
    """Full competitiveness index snapshot."""
    generated_at: str = ""
    us_spot_usd_kg: float = 0.0
    fx_rates: dict[str, float] = field(default_factory=dict)
    origins: list[OriginCost] = field(default_factory=list)
    insights: list[str] = field(default_factory=list)


class CompetitivenessEngine:
    """Computes FX-adjusted delivered cost ranking across salmon origins."""

    _cache: CompetitivenessSnapshot | None = None
    _cache_time: dt.datetime | None = None
    _cache_ttl = dt.timedelta(hours=2)

    async def _fetch_fx_rates(self) -> dict[str, float]:
        """Fetch live FX rates: NOK from macro engine, others from Yahoo."""
        rates: dict[str, float] = {}

        # Get NOK/USD from macro_intelligence (already cached)
        try:
            from core.market.macro_intelligence import macro_intelligence_engine
            macro = await macro_intelligence_engine.fetch()
            nok_usd = macro.series.get("nok_usd", 0)
            if nok_usd and nok_usd > 0:
                rates["NOK"] = 1.0 / nok_usd  # Convert NOK per USD → USD per NOK
            else:
                rates["NOK"] = FALLBACK_FX["NOK"]
        except Exception:
            rates["NOK"] = FALLBACK_FX["NOK"]

        # Fetch remaining currencies from Yahoo Finance
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                for currency, ticker in YAHOO_FX_TICKERS.items():
                    try:
                        resp = await client.get(
                            f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=5d",
                            headers={"User-Agent": "FishIntel/1.0"},
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            closes = (
                                data.get("chart", {}).get("result", [{}])[0]
                                .get("indicators", {}).get("quote", [{}])[0]
                                .get("close", [])
                            )
                            valid = [c for c in closes if c is not None]
                            if valid:
                                rates[currency] = valid[-1]
                                continue
                    except Exception:
                        pass
                    rates[currency] = FALLBACK_FX.get(currency, 0.01)
        except Exception:
            for currency in YAHOO_FX_TICKERS:
                if currency not in rates:
                    rates[currency] = FALLBACK_FX.get(currency, 0.01)

        return rates

    async def _get_norway_cost_nok(self) -> float:
        """Get live Norway production cost from feed_cost_engine."""
        self._norway_cost_is_fallback = False
        try:
            from core.market.feed_cost_engine import feed_cost_engine
            snapshot = await feed_cost_engine.fetch_prices()
            if snapshot and snapshot.production_cost_nok_per_kg_salmon > 0:
                return snapshot.production_cost_nok_per_kg_salmon
        except Exception as e:
            log.debug("competitiveness.norway_cost_fallback", error=str(e)[:80])
        self._norway_cost_is_fallback = True
        return 64.70  # Validated 2024 fallback

    async def _get_us_spot(self) -> float:
        """Get global salmon USD/kg from macro intelligence."""
        try:
            from core.market.macro_intelligence import macro_intelligence_engine
            macro = await macro_intelligence_engine.fetch()
            val = macro.series.get("global_salmon", 0)
            if val and val > 0:
                return val
        except Exception:
            pass
        return 8.50  # Reasonable fallback

    async def compute_index(self) -> dict:
        """Compute full competitiveness index with live FX and costs."""
        now = _now()
        if self._cache and self._cache_time and (now - self._cache_time) < self._cache_ttl:
            return self._to_dict(self._cache)

        log.info("competitiveness.computing")

        fx_rates = await self._fetch_fx_rates()
        norway_cost_nok = await self._get_norway_cost_nok()
        us_spot = await self._get_us_spot()

        origins: list[OriginCost] = []

        for country, cfg in ORIGIN_BASELINES.items():
            currency = cfg["currency"]
            fx = fx_rates.get(currency, FALLBACK_FX.get(currency, 0.01))

            # Local cost
            if country == "Norway":
                local_cost = norway_cost_nok
            else:
                local_cost = cfg["local_cost"]

            # Convert to USD
            prod_cost_usd = local_cost * fx

            # Tariff: rate and citation from ONE dated lookup (core/regulatory_facts.py)
            tariff_row = self.tariff_row(country, now)
            tariff_pct = (tariff_row["rate_pct"] / 100.0) if tariff_row else 0.0
            tariff_cost = prod_cost_usd * tariff_pct

            # Freight
            freight = cfg["freight_usd"]

            # Total delivered
            total = prod_cost_usd + tariff_cost + freight

            # Margin vs US spot
            margin = us_spot - total
            margin_pct = (margin / us_spot * 100) if us_spot > 0 else 0

            origins.append(OriginCost(
                country=country,
                flag=cfg["flag"],
                currency=currency,
                local_cost_per_kg=round(local_cost, 2),
                fx_rate_to_usd=round(fx, 6),
                production_cost_usd=round(prod_cost_usd, 2),
                tariff_pct=tariff_pct,
                tariff_cost_usd=round(tariff_cost, 2),
                freight_usd=freight,
                total_delivered_usd=round(total, 2),
                margin_usd=round(margin, 2),
                margin_pct=round(margin_pct, 1),
                notes=cfg["notes"],
                tariff_row=tariff_row,
            ))

        # Rank by delivered cost (ascending = most competitive)
        origins.sort(key=lambda o: o.total_delivered_usd)
        for i, o in enumerate(origins):
            o.rank = i + 1

        # Generate insights
        insights = self._generate_insights(origins, us_spot, fx_rates)

        snapshot = CompetitivenessSnapshot(
            generated_at=now.isoformat() + "Z",
            us_spot_usd_kg=round(us_spot, 2),
            fx_rates={k: round(v, 6) for k, v in fx_rates.items()},
            origins=origins,
            insights=insights,
        )

        self._cache = snapshot
        self._cache_time = now
        log.info("competitiveness.computed", n_origins=len(origins),
                 cheapest=origins[0].country if origins else "?")

        return self._to_dict(snapshot)

    def _generate_insights(self, origins: list[OriginCost], spot: float,
                           fx: dict[str, float]) -> list[str]:
        """Generate plain-language insights."""
        insights: list[str] = []
        if not origins:
            return insights

        cheapest = origins[0]
        most_expensive = origins[-1]
        norway = next((o for o in origins if o.country == "Norway"), None)

        insights.append(
            f"{cheapest.flag} {cheapest.country} is the most competitive origin at "
            f"${cheapest.total_delivered_usd:.2f}/kg delivered to US "
            f"({cheapest.tariff_pct*100:.1f}% US tariff, ${cheapest.freight_usd:.2f} freight)."
        )

        if norway:
            tariff_cost_total = norway.tariff_cost_usd
            insights.append(
                f"{norway.flag} Norway's {norway.tariff_pct * 100:.1f}% US tariff adds ${tariff_cost_total:.2f}/kg, "
                f"pushing delivered cost to ${norway.total_delivered_usd:.2f}/kg (rank #{norway.rank})."
            )

        spread = most_expensive.total_delivered_usd - cheapest.total_delivered_usd
        insights.append(
            f"Origin spread: ${spread:.2f}/kg between {cheapest.country} and {most_expensive.country}."
        )

        # Margin insight
        profitable = [o for o in origins if o.margin_usd > 0]
        if len(profitable) == len(origins):
            insights.append(f"All origins profitable at current spot ${spot:.2f}/kg.")
        elif profitable:
            unprofitable = [o for o in origins if o.margin_usd <= 0]
            insights.append(
                f"{', '.join(o.country for o in unprofitable)} "
                f"{'is' if len(unprofitable) == 1 else 'are'} margin-negative at current spot."
            )

        return insights

    def compute_tariff_scenarios(self, tariff_overrides: dict[str, float]) -> dict:
        """
        Recalculate origin competitiveness with modified tariff rates.
        Returns comparison vs baseline showing rank changes.
        """
        # Get baseline
        baseline = self._to_dict(self._cache) if self._cache else {}
        baseline_origins = baseline.get("origins", [])

        # Simplified: recalculate with overrides by modifying delivered costs
        scenario_origins = []
        for orig in baseline_origins:
            o = dict(orig)
            origin_name = o.get("origin", o.get("country", ""))
            if origin_name in tariff_overrides:
                old_tariff = o.get("tariff_pct", 0)
                new_tariff = tariff_overrides[origin_name] / 100.0  # Convert pct input to decimal
                # Adjust delivered cost: remove old tariff, add new
                base_cost = o.get("production_cost_usd", o.get("cost_usd", 0))
                freight = o.get("freight_usd", 0)
                # Recalculate: production_cost + new tariff + freight
                new_tariff_cost = base_cost * new_tariff
                new_delivered = base_cost + new_tariff_cost + freight
                o["tariff_pct"] = new_tariff
                o["tariff"] = None  # a scenario rate is not the official one
                o["tariff_scenario_override"] = True
                o["tariff_cost_usd"] = round(new_tariff_cost, 2)
                o["total_delivered_usd"] = round(new_delivered, 2)
                o["delivered_cost_usd"] = round(new_delivered, 2)
                o["tariff_change"] = round(new_tariff - old_tariff, 4)
            else:
                o["delivered_cost_usd"] = o.get("total_delivered_usd", 0)
                o["tariff_change"] = 0
            scenario_origins.append(o)

        # Re-rank by delivered cost
        scenario_origins.sort(key=lambda x: x.get("delivered_cost_usd", 999))
        for i, o in enumerate(scenario_origins):
            o["scenario_rank"] = i + 1

        # Compute rank changes
        baseline_ranks = {}
        for i, o in enumerate(baseline_origins):
            name = o.get("origin", o.get("country", "")) if isinstance(o, dict) else str(o)
            baseline_ranks[name] = i + 1

        for o in scenario_origins:
            name = o.get("origin", o.get("country", ""))
            o["baseline_rank"] = baseline_ranks.get(name, 0)
            o["rank_change"] = o["baseline_rank"] - o["scenario_rank"]

        return {
            "scenario_origins": scenario_origins,
            "tariff_overrides": tariff_overrides,
            "baseline_origins": baseline_origins,
        }

    @staticmethod
    def tariff_row(origin: str, as_of: dt.datetime | None = None) -> dict | None:
        """The dated, sourced US tariff behind an origin's rate (WS-21)."""
        try:
            return us_salmon_tariff(origin, as_of).as_dict()
        except LookupError:
            return None

    def _to_dict(self, snap: CompetitivenessSnapshot) -> dict:
        """Serialize snapshot to API-friendly dict."""
        norway_fallback = getattr(self, "_norway_cost_is_fallback", False)
        return {
            "generated_at": snap.generated_at,
            "us_spot_usd_kg": snap.us_spot_usd_kg,
            "fx_rates": snap.fx_rates,
            "data_quality": "stale_fallback" if norway_fallback else "live",
            "fallback_value": norway_fallback,
            "source_date": "2024" if norway_fallback else None,
            "origins": [
                {
                    "rank": o.rank,
                    "country": o.country,
                    "flag": o.flag,
                    "currency": o.currency,
                    "local_cost_per_kg": o.local_cost_per_kg,
                    "fx_rate_to_usd": o.fx_rate_to_usd,
                    "production_cost_usd": o.production_cost_usd,
                    "tariff_pct": o.tariff_pct,
                    "tariff": o.tariff_row,
                    "tariff_cost_usd": o.tariff_cost_usd,
                    "freight_usd": o.freight_usd,
                    "total_delivered_usd": o.total_delivered_usd,
                    "margin_usd": o.margin_usd,
                    "margin_pct": o.margin_pct,
                    "notes": o.notes,
                }
                for o in snap.origins
            ],
            "insights": snap.insights,
        }


# Singleton
competitiveness_engine = CompetitivenessEngine()
