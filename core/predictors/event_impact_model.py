"""
Event-to-Financial Impact Model
=================================
Translates biological/regulatory events into financial impact estimates.
Used by investors to size positions and traders to identify arbitrage.

Cascade: EVENT -> BIOLOGICAL IMPACT -> PRODUCTION -> REVENUE -> EBIT -> STOCK

Reference data drawn from annual reports, Fiskeridirektoratet, and the
existing impact_translator.py constants where applicable.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import structlog

log = structlog.get_logger(__name__)


# ── Company production profiles (approximate, from annual reports) ─────
COMPANY_PROFILES = {
    "MOWI": {
        "name": "Mowi ASA",
        "annual_production_tonnes": 450_000,
        "avg_revenue_per_kg": 65.0,     # NOK
        "avg_cost_per_kg": 45.0,        # NOK production cost
        "market_cap_bnok": 120.0,
        "shares_outstanding_m": 517,
        "pe_ratio": 10.0,
        "production_areas": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
        "pa_weight": 1.0,  # present in all PAs
        "feed_cost_share": 0.52,  # % of total cost
    },
    "SALM": {
        "name": "SalMar ASA",
        "annual_production_tonnes": 280_000,
        "avg_revenue_per_kg": 62.0,
        "avg_cost_per_kg": 42.0,
        "market_cap_bnok": 85.0,
        "shares_outstanding_m": 565,
        "pe_ratio": 11.0,
        "production_areas": [6, 7, 8, 9, 10, 11, 12],
        "pa_weight": 0.7,
        "feed_cost_share": 0.50,
    },
    "LSG": {
        "name": "Leroy Seafood Group",
        "annual_production_tonnes": 190_000,
        "avg_revenue_per_kg": 60.0,
        "avg_cost_per_kg": 44.0,
        "market_cap_bnok": 40.0,
        "shares_outstanding_m": 596,
        "pe_ratio": 9.0,
        "production_areas": [3, 4, 5, 6, 7],
        "pa_weight": 0.5,
        "feed_cost_share": 0.50,
    },
    "GSF": {
        "name": "Grieg Seafood ASA",
        "annual_production_tonnes": 65_000,
        "avg_revenue_per_kg": 58.0,
        "avg_cost_per_kg": 46.0,
        "market_cap_bnok": 18.0,
        "shares_outstanding_m": 112,
        "pe_ratio": 12.0,
        "production_areas": [3, 4, 11, 12],
        "pa_weight": 0.4,
        "feed_cost_share": 0.48,
    },
    "BAKKA": {
        "name": "Bakkafrost P/F",
        "annual_production_tonnes": 100_000,
        "avg_revenue_per_kg": 64.0,
        "avg_cost_per_kg": 43.0,
        "market_cap_bnok": 50.0,
        "shares_outstanding_m": 59,
        "pe_ratio": 11.0,
        "production_areas": [],  # Faroe Islands - not in Norwegian PAs
        "pa_weight": 0.0,
        "feed_cost_share": 0.51,
    },
}

# ISA outbreak parameters
ISA_BIOMASS_LOSS_PCT_LOW = 0.01     # 1% mild case
ISA_BIOMASS_LOSS_PCT_HIGH = 0.05    # 5% severe case
ISA_BIOMASS_LOSS_PCT_MID = 0.025    # 2.5% typical
ISA_CULL_ZONE_KM = 10              # mandatory cull zone radius
ISA_FALLOWING_MONTHS = 6           # mandatory fallow after ISA

# Traffic-light MAB capacity changes
TRAFFIC_LIGHT_MAB_CHANGE = {
    "green": 0.06,    # +6% capacity increase
    "yellow": 0.0,    # no change
    "red": -0.06,     # -6% capacity reduction
}

# PA to approximate share of national production
PA_PRODUCTION_SHARE = {
    1: 0.04, 2: 0.06, 3: 0.10, 4: 0.08, 5: 0.07,
    6: 0.09, 7: 0.11, 8: 0.08, 9: 0.07, 10: 0.06,
    11: 0.08, 12: 0.10, 13: 0.06,
}

# Stock price elasticity to earnings surprise (P/E multiple effect)
EARNINGS_SURPRISE_MULTIPLIER = 10.0  # ~8-12x typical


@dataclass
class CompanyImpact:
    """Financial impact estimate for a single company."""
    ticker: str
    company_name: str
    exposure_pct: float = 0.0           # % of company production exposed
    production_impact_tonnes: float = 0.0
    revenue_impact_mnok: float = 0.0
    ebit_impact_mnok: float = 0.0
    ebit_impact_pct: float = 0.0
    expected_stock_move_pct: float = 0.0
    expected_stock_move_nok: float = 0.0
    confidence: float = 0.5
    notes: str = ""


@dataclass
class EventImpactResult:
    """Full event impact analysis result."""
    event_type: str
    event_description: str
    timestamp: str
    severity: str                       # low / medium / high / critical
    affected_production_area: int | None = None
    national_production_impact_pct: float = 0.0
    total_revenue_impact_mnok: float = 0.0
    price_impact_pct: float = 0.0       # expected spot price change
    company_impacts: list[dict] = field(default_factory=list)
    cascade_narrative: str = ""
    disclaimer: str = (
        "Synthetic model estimates based on historical patterns. "
        "Not investment advice. Actual impacts depend on outbreak severity, "
        "regulatory response, and market conditions."
    )


class EventImpactModel:
    """
    Models the cascade: EVENT -> BIO IMPACT -> PRODUCTION -> REVENUE -> EBIT -> STOCK.

    Provides scenario analysis for ISA outbreaks, traffic-light changes,
    and feed price shocks, translating each into per-company financial impacts.
    """

    def __init__(self):
        self._profiles = COMPANY_PROFILES

    def _get_company_pa_exposure(self, ticker: str, pa: int) -> float:
        """What fraction of a company's production is in the given PA."""
        profile = self._profiles.get(ticker)
        if not profile or not profile["production_areas"]:
            return 0.0
        if pa not in profile["production_areas"]:
            return 0.0
        # Approximate: equal distribution across PAs
        n_pas = len(profile["production_areas"])
        return 1.0 / n_pas

    def _share_price_est(self, ticker: str) -> float:
        """Estimated share price from market cap / shares."""
        p = self._profiles.get(ticker)
        if not p:
            return 0.0
        return p["market_cap_bnok"] * 1e3 / p["shares_outstanding_m"]

    def _company_margin_per_kg(self, ticker: str) -> float:
        """NOK margin per kg."""
        p = self._profiles.get(ticker)
        if not p:
            return 20.0
        return p["avg_revenue_per_kg"] - p["avg_cost_per_kg"]

    def _company_annual_ebit_mnok(self, ticker: str) -> float:
        """Approximate annual EBIT in MNOK."""
        p = self._profiles.get(ticker)
        if not p:
            return 0.0
        margin = self._company_margin_per_kg(ticker)
        return p["annual_production_tonnes"] * margin / 1000.0  # tonnes * NOK/kg / 1000 = MNOK

    async def model_isa_outbreak(self, production_area: int) -> dict:
        """
        Model financial impact of an ISA outbreak in a production area.

        ISA cascade:
          1. Affected farms culled (mandatory)
          2. Exclusion zone around outbreak site
          3. 6-month fallow period
          4. Biomass loss 1-5% of PA production
          5. Revenue loss = biomass loss * price
          6. Reduced supply -> slight price uplift for surviving producers
          7. Company stock impact proportional to exposure
        """
        pa_share = PA_PRODUCTION_SHARE.get(production_area, 0.05)
        national_prod = 1_400_000  # approximate total Norway tonnes

        # ISA typically affects a few sites in a PA
        affected_biomass_tonnes_mid = national_prod * pa_share * ISA_BIOMASS_LOSS_PCT_MID

        avg_price_nok = 85.0  # approximate current spot

        company_impacts = []
        for ticker, profile in self._profiles.items():
            exposure = self._get_company_pa_exposure(ticker, production_area)
            if exposure <= 0:
                continue

            # Mid-case scenario
            prod_loss = profile["annual_production_tonnes"] * exposure * ISA_BIOMASS_LOSS_PCT_MID
            rev_loss = prod_loss * profile["avg_revenue_per_kg"] / 1000.0  # MNOK
            margin = self._company_margin_per_kg(ticker)
            ebit_loss = prod_loss * margin / 1000.0
            annual_ebit = self._company_annual_ebit_mnok(ticker)
            ebit_pct = (ebit_loss / annual_ebit * 100) if annual_ebit > 0 else 0.0

            # Stock impact: earnings surprise * PE
            stock_move_pct = -ebit_pct * (profile["pe_ratio"] / EARNINGS_SURPRISE_MULTIPLIER)
            share_price = self._share_price_est(ticker)
            stock_move_nok = share_price * stock_move_pct / 100.0

            company_impacts.append(CompanyImpact(
                ticker=ticker,
                company_name=profile["name"],
                exposure_pct=round(exposure * 100, 1),
                production_impact_tonnes=round(prod_loss, 0),
                revenue_impact_mnok=round(rev_loss, 1),
                ebit_impact_mnok=round(ebit_loss, 1),
                ebit_impact_pct=round(ebit_pct, 2),
                expected_stock_move_pct=round(stock_move_pct, 2),
                expected_stock_move_nok=round(stock_move_nok, 1),
                confidence=0.55,
                notes=f"PA {production_area} exposure: {exposure*100:.0f}% of production",
            ))

        # Severity
        severity = "high" if pa_share >= 0.08 else "medium" if pa_share >= 0.05 else "low"
        national_impact_pct = pa_share * ISA_BIOMASS_LOSS_PCT_MID * 100

        # Supply reduction -> price uplift for non-affected
        supply_reduction_pct = affected_biomass_tonnes_mid / national_prod * 100
        price_uplift_pct = supply_reduction_pct * 0.5  # ~0.5x elasticity

        cascade = (
            f"ISA outbreak in PA {production_area} -> "
            f"mandatory cull of affected sites ({ISA_CULL_ZONE_KM}km zone) -> "
            f"~{affected_biomass_tonnes_mid:,.0f}t biomass destroyed (mid-case) -> "
            f"6-month fallow -> {supply_reduction_pct:.2f}% national supply reduction -> "
            f"~{price_uplift_pct:.1f}% spot price uplift for surviving producers"
        )

        result = EventImpactResult(
            event_type="isa_outbreak",
            event_description=f"ISA outbreak detected in Production Area {production_area}",
            timestamp=dt.datetime.now(dt.UTC).isoformat(),
            severity=severity,
            affected_production_area=production_area,
            national_production_impact_pct=round(national_impact_pct, 3),
            total_revenue_impact_mnok=round(affected_biomass_tonnes_mid * avg_price_nok / 1e6, 1),
            price_impact_pct=round(price_uplift_pct, 2),
            company_impacts=[vars(ci) for ci in company_impacts],
            cascade_narrative=cascade,
        )
        return vars(result)

    async def model_traffic_light_change(self, pa: int, new_color: str) -> dict:
        """
        Model financial impact of traffic light color change for a PA.

        Traffic-light cascade:
          1. New color assigned (green/yellow/red)
          2. MAB capacity adjustment (+6% / 0% / -6%)
          3. Production volume change proportional to capacity
          4. Revenue delta per company based on PA exposure
          5. Supply shift -> spot price impact
        """
        new_color = new_color.lower()
        if new_color not in TRAFFIC_LIGHT_MAB_CHANGE:
            return {"error": f"Invalid color: {new_color}. Use green/yellow/red."}

        mab_change_pct = TRAFFIC_LIGHT_MAB_CHANGE[new_color]
        pa_share = PA_PRODUCTION_SHARE.get(pa, 0.05)
        national_prod = 1_400_000

        # Production change for the PA
        pa_production = national_prod * pa_share
        production_delta = pa_production * mab_change_pct
        national_impact_pct = (production_delta / national_prod) * 100

        # Price impact from supply change (inverse)
        price_impact_pct = -national_impact_pct * 0.8  # price elasticity

        avg_price_nok = 85.0

        company_impacts = []
        for ticker, profile in self._profiles.items():
            exposure = self._get_company_pa_exposure(ticker, pa)
            if exposure <= 0:
                continue

            company_prod_delta = profile["annual_production_tonnes"] * exposure * mab_change_pct
            rev_delta = company_prod_delta * profile["avg_revenue_per_kg"] / 1000.0
            margin = self._company_margin_per_kg(ticker)
            ebit_delta = company_prod_delta * margin / 1000.0
            annual_ebit = self._company_annual_ebit_mnok(ticker)
            ebit_pct = (ebit_delta / annual_ebit * 100) if annual_ebit > 0 else 0.0

            stock_move_pct = ebit_pct * (profile["pe_ratio"] / EARNINGS_SURPRISE_MULTIPLIER)
            share_price = self._share_price_est(ticker)
            stock_move_nok = share_price * stock_move_pct / 100.0

            company_impacts.append(CompanyImpact(
                ticker=ticker,
                company_name=profile["name"],
                exposure_pct=round(exposure * 100, 1),
                production_impact_tonnes=round(company_prod_delta, 0),
                revenue_impact_mnok=round(rev_delta, 1),
                ebit_impact_mnok=round(ebit_delta, 1),
                ebit_impact_pct=round(ebit_pct, 2),
                expected_stock_move_pct=round(stock_move_pct, 2),
                expected_stock_move_nok=round(stock_move_nok, 1),
                confidence=0.65,
                notes=f"MAB capacity {mab_change_pct*100:+.0f}% in PA {pa}",
            ))

        direction = "bearish" if new_color == "red" else "bullish" if new_color == "green" else "neutral"
        severity = "high" if new_color == "red" else "medium" if new_color == "green" else "low"

        cascade = (
            f"PA {pa} traffic light -> {new_color.upper()} -> "
            f"MAB capacity {mab_change_pct*100:+.0f}% -> "
            f"production delta {production_delta:+,.0f}t/year -> "
            f"{national_impact_pct:+.3f}% national supply -> "
            f"spot price {price_impact_pct:+.2f}% -> "
            f"{direction} for exposed producers"
        )

        result = EventImpactResult(
            event_type="traffic_light_change",
            event_description=f"PA {pa} traffic light changed to {new_color.upper()}",
            timestamp=dt.datetime.now(dt.UTC).isoformat(),
            severity=severity,
            affected_production_area=pa,
            national_production_impact_pct=round(national_impact_pct, 3),
            total_revenue_impact_mnok=round(abs(production_delta) * avg_price_nok / 1e6, 1),
            price_impact_pct=round(price_impact_pct, 2),
            company_impacts=[vars(ci) for ci in company_impacts],
            cascade_narrative=cascade,
        )
        return vars(result)

    async def model_feed_price_shock(self, fishmeal_change_pct: float) -> dict:
        """
        Model financial impact of fishmeal/feed price spike.

        Feed cost cascade:
          1. Fishmeal price change (key ingredient ~30% of feed)
          2. Feed cost change = fishmeal change * 0.30
          3. Production cost increase per company (feed is ~50% of total cost)
          4. Margin erosion -> EBIT compression
          5. Earnings revision -> stock impact
        """
        # Fishmeal is ~30% of feed cost, feed is ~50% of production cost
        feed_cost_change_pct = fishmeal_change_pct * 0.30
        production_cost_change_pct = feed_cost_change_pct * 0.50

        company_impacts = []
        for ticker, profile in self._profiles.items():
            # Cost increase per kg
            feed_share = profile["feed_cost_share"]
            cost_increase_per_kg = profile["avg_cost_per_kg"] * feed_share * (fishmeal_change_pct / 100) * 0.30
            total_cost_increase_mnok = cost_increase_per_kg * profile["annual_production_tonnes"] / 1000.0

            margin = self._company_margin_per_kg(ticker)
            new_margin = margin - cost_increase_per_kg

            annual_ebit = self._company_annual_ebit_mnok(ticker)
            ebit_impact_mnok = -total_cost_increase_mnok
            ebit_pct = (-total_cost_increase_mnok / annual_ebit * 100) if annual_ebit > 0 else 0.0

            stock_move_pct = ebit_pct * (profile["pe_ratio"] / EARNINGS_SURPRISE_MULTIPLIER)
            share_price = self._share_price_est(ticker)
            stock_move_nok = share_price * stock_move_pct / 100.0

            company_impacts.append(CompanyImpact(
                ticker=ticker,
                company_name=profile["name"],
                exposure_pct=round(feed_share * 100, 1),
                production_impact_tonnes=0,
                revenue_impact_mnok=round(-total_cost_increase_mnok, 1),
                ebit_impact_mnok=round(ebit_impact_mnok, 1),
                ebit_impact_pct=round(ebit_pct, 2),
                expected_stock_move_pct=round(stock_move_pct, 2),
                expected_stock_move_nok=round(stock_move_nok, 1),
                confidence=0.60,
                notes=f"Feed cost +{feed_cost_change_pct:.1f}%, margin {new_margin:.1f} NOK/kg (was {margin:.1f})",
            ))

        severity = "critical" if fishmeal_change_pct >= 30 else "high" if fishmeal_change_pct >= 15 else "medium" if fishmeal_change_pct >= 5 else "low"

        cascade = (
            f"Fishmeal price {fishmeal_change_pct:+.0f}% -> "
            f"feed cost {feed_cost_change_pct:+.1f}% -> "
            f"production cost {production_cost_change_pct:+.1f}% -> "
            f"margin erosion across all producers -> "
            f"earnings revision negative -> sector-wide pressure"
        )

        result = EventImpactResult(
            event_type="feed_price_shock",
            event_description=f"Fishmeal price shock: {fishmeal_change_pct:+.0f}%",
            timestamp=dt.datetime.now(dt.UTC).isoformat(),
            severity=severity,
            national_production_impact_pct=0.0,
            total_revenue_impact_mnok=round(sum(
                vars(ci)["ebit_impact_mnok"] if isinstance(ci, CompanyImpact) else ci.ebit_impact_mnok
                for ci in company_impacts
            ), 1),
            price_impact_pct=round(production_cost_change_pct * 0.3, 2),
            company_impacts=[vars(ci) for ci in company_impacts],
            cascade_narrative=cascade,
        )
        return vars(result)

    async def model_custom_event(self, event_type: str, params: dict) -> dict:
        """
        Flexible event modeling for arbitrary event types.

        Supported event_type values:
          - "isa": requires production_area
          - "traffic_light": requires pa, color
          - "feed_shock": requires fishmeal_change_pct
          - "generic": requires production_loss_pct, affected_tickers
        """
        if event_type == "isa":
            return await self.model_isa_outbreak(params.get("production_area", 3))
        elif event_type == "traffic_light":
            return await self.model_traffic_light_change(
                params.get("pa", 3), params.get("color", "red")
            )
        elif event_type == "feed_shock":
            return await self.model_feed_price_shock(
                params.get("fishmeal_change_pct", 15.0)
            )
        elif event_type == "generic":
            return self._model_generic_event(params)
        else:
            return {"error": f"Unknown event type: {event_type}"}

    def _model_generic_event(self, params: dict) -> dict:
        """Model a generic production disruption event."""
        loss_pct = params.get("production_loss_pct", 1.0) / 100.0
        affected_tickers = params.get("affected_tickers", list(self._profiles.keys()))
        description = params.get("description", "Generic production disruption")

        company_impacts = []
        for ticker in affected_tickers:
            profile = self._profiles.get(ticker)
            if not profile:
                continue

            prod_loss = profile["annual_production_tonnes"] * loss_pct
            rev_loss = prod_loss * profile["avg_revenue_per_kg"] / 1000.0
            margin = self._company_margin_per_kg(ticker)
            ebit_loss = prod_loss * margin / 1000.0
            annual_ebit = self._company_annual_ebit_mnok(ticker)
            ebit_pct = (ebit_loss / annual_ebit * 100) if annual_ebit > 0 else 0.0

            stock_move_pct = -ebit_pct * (profile["pe_ratio"] / EARNINGS_SURPRISE_MULTIPLIER)
            share_price = self._share_price_est(ticker)
            stock_move_nok = share_price * stock_move_pct / 100.0

            company_impacts.append(vars(CompanyImpact(
                ticker=ticker,
                company_name=profile["name"],
                exposure_pct=round(loss_pct * 100, 1),
                production_impact_tonnes=round(prod_loss, 0),
                revenue_impact_mnok=round(rev_loss, 1),
                ebit_impact_mnok=round(ebit_loss, 1),
                ebit_impact_pct=round(ebit_pct, 2),
                expected_stock_move_pct=round(stock_move_pct, 2),
                expected_stock_move_nok=round(stock_move_nok, 1),
                confidence=0.40,
                notes="Generic model - lower confidence",
            )))

        return vars(EventImpactResult(
            event_type="generic",
            event_description=description,
            timestamp=dt.datetime.now(dt.UTC).isoformat(),
            severity="medium",
            national_production_impact_pct=round(loss_pct * 100, 2),
            company_impacts=company_impacts,
            cascade_narrative=f"{description} -> {loss_pct*100:.1f}% production loss -> earnings revision",
        ))


# Singleton
event_impact_model = EventImpactModel()
