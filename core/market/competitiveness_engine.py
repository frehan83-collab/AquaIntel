"""
FX-Adjusted Origin Competitiveness Index
==========================================
Computes USD-equivalent delivered cost of salmon from each producing origin,
incorporating live FX rates, production costs, US tariffs, and freight.

Rankings show which origins deliver cheapest to the US market in real-time.
Norway cost is LIVE from feed_cost_engine; others use industry benchmarks
in local currency, converted via live FX.

Data sources: Norges Bank official FX, FRED/SSB via macro_intelligence, feed_cost_engine.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

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

# Undated approximate constants, used only when a live quote is unavailable.
# They are never silent: `_to_dict` reports `data_quality: partial_fallback`,
# names the currencies in `fx_fallbacks` and degrades `data_provenance`.
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
    # WS-37: which value the rate was applied to. US duty is assessed on the transaction
    # value (the importer's price), not the producer's cost, so the cost-base figure is a
    # lower bound; where a live export price exists the statutory duty is shown beside it.
    tariff_base: str = "production_cost"
    export_price_usd: float | None = None
    tariff_at_export_price_usd: float | None = None
    duty_base_note: str = ""


@dataclass
class CompetitivenessSnapshot:
    """Full competitiveness index snapshot."""
    generated_at: str = ""
    us_spot_usd_kg: float = 0.0
    fx_rates: dict[str, float] = field(default_factory=dict)
    origins: list[OriginCost] = field(default_factory=list)
    insights: list[str] = field(default_factory=list)
    tariff_basis: str = ""


class CompetitivenessEngine:
    """Computes FX-adjusted delivered cost ranking across salmon origins."""

    _cache: CompetitivenessSnapshot | None = None
    _cache_time: dt.datetime | None = None
    _cache_ttl = dt.timedelta(hours=2)

    async def _fetch_fx_rates(self) -> dict[str, float]:
        """Fetch live FX rates: Norges Bank for NOK and the crosses it quotes, documented constants otherwise (WS-31b)."""
        rates: dict[str, float] = {}
        self._fx_fallbacks: list[str] = []
        self._fx_observations: dict[str, str | None] = getattr(self, "_fx_observations", {})
        self._fx_reasons: dict[str, str | None] = getattr(self, "_fx_reasons", {})

        # NOK/USD from the official Norges Bank rate (WS-31). The macro series it
        # used to read is derived from the same kind of upstream quote, and the Yahoo
        # terms forbid deriving income from their data in a paid product.
        try:
            from core.market.fx_rates import usd_nok as official_usd_nok
            official = await official_usd_nok()
            nok_per_usd = official.get("nok_per_unit")
            if nok_per_usd and nok_per_usd > 0:
                rates["NOK"] = 1.0 / float(nok_per_usd)  # NOK per USD → USD per NOK
                self._fx_observations["NOK"] = official.get("observed_at")
            else:
                rates["NOK"] = FALLBACK_FX["NOK"]
                self._fx_fallbacks.append("NOK")
        except Exception:
            rates["NOK"] = FALLBACK_FX["NOK"]
            self._fx_fallbacks.append("NOK")

        # Remaining currencies from the licensed FX module (Norges Bank where it
        # quotes the currency, otherwise a documented constant flagged as a fallback).
        # WS-31b: the Yahoo Finance chart calls are gone — its terms forbid deriving
        # income from the data, and a paid product cannot rest on them.
        from core.market.fx_rates import rate_to_usd

        for currency in FALLBACK_FX:
            if currency == "NOK" or currency in rates:
                continue
            try:
                converted = await rate_to_usd(currency)
            except Exception:  # noqa: BLE001 — reported through the fallback list
                converted = {}
            value = converted.get("usd_per_unit")
            if value and value > 0:
                rates[currency] = float(value)
                if converted.get("observed_at"):
                    self._fx_observations[currency] = converted.get("observed_at")
                if converted.get("is_fallback"):
                    self._fx_fallbacks.append(currency)
                    self._fx_reasons[currency] = converted.get("fallback_reason")
                continue
            rates[currency] = FALLBACK_FX[currency]
            self._fx_fallbacks.append(currency)
            self._fx_reasons[currency] = converted.get("fallback_reason") or (
                "no licensed quote available"
            )

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
        """Get global salmon USD/kg from macro intelligence.

        The 8.50 constant is undated; `_to_dict` reports it as a partial
        fallback rather than letting it drive margins as if it were live.
        """
        self._us_spot_is_fallback = True
        try:
            from core.market.macro_intelligence import macro_intelligence
            macro = await macro_intelligence.fetch()
            val = macro.series.get("global_salmon", 0)
            if val and val > 0:
                self._us_spot_is_fallback = False
                return val
        except Exception:
            pass
        return 8.50  # Undated fallback

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
            fx = fx_rates.get(currency)
            if fx is None:
                fx = FALLBACK_FX.get(currency, 0.01)
                self._fx_fallbacks.append(currency)

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

            # WS-37: US duty is assessed on the transaction value of the imported good
            # (the price the importer pays), not on the producer's cost. We hold a live
            # export price for Norway (SSB) and none for the other origins, so the duty is
            # charged on the best available declared value and the basis is labelled on
            # every row — never silently on cost.
            export_price_usd = None
            if country == "Norway":
                try:
                    from core.market.ssb_price_client import ssb_price_client

                    ssb_nok = await ssb_price_client.get_current_spot()
                    nok_usd = fx_rates.get("NOK")
                    if ssb_nok and ssb_nok > 0 and nok_usd:
                        export_price_usd = round(float(ssb_nok) * float(nok_usd), 2)
                except Exception as exc:  # noqa: BLE001 — a missing price is not fatal
                    log.debug("competitiveness.export_price_failed", error=str(exc)[:80])

            duty_base_usd = export_price_usd if export_price_usd else prod_cost_usd
            tariff_base = "export_price" if export_price_usd else "production_cost"
            tariff_cost = duty_base_usd * tariff_pct
            tariff_at_export_price = (
                round(export_price_usd * tariff_pct, 2) if export_price_usd else None
            )
            duty_base_note = ""
            if tariff_pct and export_price_usd:
                cost_base_duty = prod_cost_usd * tariff_pct
                duty_base_note = (
                    "US duty is assessed on the transaction value of the imported good, "
                    f"not the producer's cost: {tariff_pct * 100:.1f} % is charged here on "
                    f"the live SSB export price of ${export_price_usd:.2f}/kg "
                    f"(${tariff_cost:.2f}/kg). On production cost the same rate would give "
                    f"${cost_base_duty:.2f}/kg "
                    f"({'higher' if cost_base_duty > tariff_cost else 'lower'} — the export "
                    "price is "
                    f"{'above' if export_price_usd > prod_cost_usd else 'below'} cost)."
                )
            elif tariff_pct:
                duty_base_note = (
                    "US duty is assessed on the transaction value of the imported good, "
                    f"not the producer's cost. No live export price exists for this origin, "
                    f"so {tariff_pct * 100:.1f} % is charged on production cost — the true "
                    "duty is higher by the exporter's margin."
                )

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
                tariff_base=tariff_base,
                export_price_usd=export_price_usd,
                tariff_at_export_price_usd=tariff_at_export_price,
                duty_base_note=duty_base_note,
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
            tariff_basis=(
                "US duty is assessed on the transaction value of the imported good, not "
                "the producer's cost. Rows marked tariff_base=production_cost are a lower "
                "bound; Norway also publishes the statutory duty at its live SSB export "
                "price (tariff_at_export_price_usd)."
            ),
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
        """Serialize snapshot to API-friendly dict.

        Honesty: ``data_quality`` is ``live`` only when the Norway production
        cost, the US spot price and every FX rate all came from a live source.
        FX fallbacks used to be invisible here, so a snapshot priced with
        NOK/USD 0.093 (about 10.75 NOK/USD) still called itself live.
        """
        norway_fallback = bool(getattr(self, "_norway_cost_is_fallback", False))
        spot_fallback = bool(getattr(self, "_us_spot_is_fallback", False))
        fx_fallbacks = sorted(set(getattr(self, "_fx_fallbacks", None) or []))

        reasons: list[str] = []
        if norway_fallback:
            reasons.append("Norway production cost fell back to the 2024 value (NOK 64.70/kg)")
        if spot_fallback:
            reasons.append("US spot price fell back to the undated constant (USD 8.50/kg)")
        if fx_fallbacks:
            reasons.append(
                "FX rate(s) fell back to undated approximate constants: "
                + ", ".join(fx_fallbacks)
            )
        if norway_fallback:
            quality = "stale_fallback"
        elif fx_fallbacks or spot_fallback:
            quality = "partial_fallback"
        else:
            quality = "live"

        from core.market.data_provenance import DataProvenance

        source = (
            "Norges Bank official FX + macro intelligence (FRED/SSB) + feed-cost engine "
            "+ US salmon tariff register (core/regulatory_facts.py)"
        )
        provenance = (
            DataProvenance.degraded(source, "; ".join(reasons), confidence=0.4)
            if reasons
            else DataProvenance.live(source, confidence=0.75)
        )
        return {
            "generated_at": snap.generated_at,
            "us_spot_usd_kg": snap.us_spot_usd_kg,
            "fx_rates": snap.fx_rates,
            "data_quality": quality,
            "fallback_value": norway_fallback,
            "fx_fallbacks": fx_fallbacks,
            "us_spot_fallback": spot_fallback,
            "fx_fallback_values": {c: FALLBACK_FX[c] for c in fx_fallbacks if c in FALLBACK_FX},
            "fallback_reason": "; ".join(reasons) or None,
            "data_provenance": provenance.to_dict(),
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
                    "tariff_base": o.tariff_base,
                    "export_price_usd": o.export_price_usd,
                    "tariff_at_export_price_usd": o.tariff_at_export_price_usd,
                    "duty_base_note": o.duty_base_note,
                }
                for o in snap.origins
            ],
            "insights": snap.insights,
            "tariff_basis": snap.tariff_basis,
        }


# Singleton
competitiveness_engine = CompetitivenessEngine()
