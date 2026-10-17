"""
Global Salmon Supply Balance Engine
=====================================
Fuses production data from all major salmon-producing nations into a
single supply/demand model. No competitor offers this unified view.

Data sources:
  - Norway: BarentsWatch lice + SSB production volumes (LIVE)
  - Chile: Sernapesca scraper (LIVE — already implemented)
  - Scotland: Marine Scotland CKAN portal (public)
  - FRED: PSALMUSDM global salmon benchmark (LIVE)
  - Internal: Biomass predictor, regime detector, AIS harvest intel

Global production shares (2024 est, FAO):
  Norway: 52% (~1.65M tonnes)
  Chile: 25% (~0.80M tonnes)
  Scotland: 6% (~0.20M tonnes)
  Canada: 5% (~0.16M tonnes)
  Faroe Islands: 4% (~0.12M tonnes)
  Others: 8% (~0.25M tonnes)
  Total: ~3.18M tonnes

Model computes:
  - Per-country supply status (normal / disrupted / surplus)
  - Global supply balance (tight / balanced / oversupplied)
  - Price pressure direction from supply shifts
  - Cross-country arbitrage opportunities
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import structlog

log = structlog.get_logger(__name__)

# ── Global production baseline (updated annually from FAO) ────────────────────
# ── Global Atlantic salmon supply data ────────────────────────────────────────
# TWO datasets: 2025 ACTUAL (confirmed) + 2026 ESTIMATED (forecast)
#
# 2025 ACTUALS (verified sources):
#   Norway: Fiskeridirektoratet biostat = 1,839kt harvest (our DB, 12 months)
#   Chile: ~800kt (SalmonChile exports report, 14% growth in 2025)
#   Scotland: ~195kt (Scottish Gov Survey 2024=192kt, +2% growth)
#   Canada: ~115kt (Statistics Canada 2024=109kt, +5% est.)
#   Faroe Islands: 84kt (Bakkafrost 2025 actual: 83.6kt Faroes)
#   Iceland: ~48kt (2024 actual all aquaculture 55kt, salmon ~45-48kt)
#   TOTAL 2025: ~3,126kt
#
# 2026 ESTIMATES (Kontali, Rabobank, company guidance):
#   Norway: 1,640kt (Kontali: +5.3% from initial 2025 forecast of 1,560kt)
#     NOTE: Fiskeridirektoratet shows 2025 actual at 1,839kt which is HIGHER
#     The Kontali forecast may be WFE vs our biostat which incl. trout
#   Chile: 740-800kt (Kontali 740kt, IntraFish "record harvest forecast")
#   Scotland: 200-207kt (6% growth from 195kt base)
#   Canada: 115kt (BC closures offset Atlantic growth)
#   Faroe Islands: 92kt (Bakkafrost 2026 guidance, confirmed)
#   Iceland: 40kt salmon-only (Arnarlax 21kt + Arctic Fish 17.5kt)
#   TOTAL 2026E: ~2,870-2,900kt (Kontali/FAO range)
#
# Sources:
#   Fiskeridirektoratet: biostat-total-flk.json (our DB)
#   FAO Globefish Feb 2025: openknowledge.fao.org
#   Kontali/Rabobank: fishfarmingexpert.com
#   Bakkafrost Q4 2025: bakkafrost.com, investing.com
#   Mowi Q4 2025: mowi.com
#   Scottish Gov: gov.scot/publications/scottish-fish-farm-production-survey-2024
#   Statistics Canada: statcan.gc.ca
#   SalmonChile: seafoodsource.com

# 2025 ACTUAL production (confirmed, displayed as reference)
PRODUCTION_2025 = {
    "Norway":        {"tonnes": 1_731_000, "source": "Fiskeridirektoratet biostat (salmon only, excl. 109kt trout)"},
    "Chile":         {"tonnes":   800_000, "source": "SalmonChile/IntraFish est."},
    "Scotland":      {"tonnes":   195_000, "source": "Scottish Gov Survey + est."},
    "Canada":        {"tonnes":   115_000, "source": "Statistics Canada + est."},
    "Faroe Islands": {"tonnes":    84_000, "source": "Bakkafrost 2025 actual"},
    "Iceland":       {"tonnes":    48_000, "source": "Icelandic aquaculture est."},
    "Others":        {"tonnes":    45_000, "source": "Estimated"},
}

# 2026 ESTIMATED production (forecast, primary display)
PRODUCERS = {
    "Norway":        {"share": 0.55, "tonnes": 1_730_000, "currency": "NOK", "yoy_pct": 0.0,
                      "est_source": "Flat from 2025 actual (1,731kt). Kontali initial 1,640kt was pre-actual."},
    "Chile":         {"share": 0.27, "tonnes":   770_000, "currency": "CLP", "yoy_pct": -3.8,
                      "est_source": "Kontali 740kt / IntraFish 'record' — midpoint 770kt"},
    "Scotland":      {"share": 0.07, "tonnes":   207_000, "currency": "GBP", "yoy_pct": 6.2,
                      "est_source": "Kontali: 6% growth from 195kt"},
    "Canada":        {"share": 0.04, "tonnes":   115_000, "currency": "CAD", "yoy_pct": 0.0,
                      "est_source": "Flat — BC closures offset Atlantic growth"},
    "Faroe Islands": {"share": 0.03, "tonnes":    92_000, "currency": "DKK", "yoy_pct": 9.5,
                      "est_source": "Bakkafrost 2026 guidance confirmed"},
    "Iceland":       {"share": 0.01, "tonnes":    40_000, "currency": "ISK", "yoy_pct": -16.7,
                      "est_source": "Arnarlax 21kt + Arctic Fish 17.5kt (salmon only)"},
    "Others":        {"share": 0.02, "tonnes":    45_000, "currency": "USD", "yoy_pct": 0.0,
                      "est_source": "Tasmania, Ireland — estimated"},
}

TOTAL_2025 = sum(p["tonnes"] for p in PRODUCTION_2025.values())  # ~3,126kt
TOTAL_GLOBAL = sum(p["tonnes"] for p in PRODUCERS.values())      # 2026E total


@dataclass
class CountrySupply:
    """Supply status for a single producing country."""
    country: str
    production_share: float
    annual_tonnes: int
    status: str = "normal"        # normal / disrupted / elevated / unknown
    disruption_pct: float = 0.0   # % reduction from baseline
    disruption_reason: str = ""
    lice_pressure: str = "normal" # low / normal / elevated / critical
    disease_events: int = 0
    price_impact_pct: float = 0.0 # estimated impact on global price


@dataclass
class GlobalSupplyBalance:
    """Global supply balance model."""
    generated_at: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))
    countries: list[CountrySupply] = field(default_factory=list)
    total_production_tonnes: int = TOTAL_GLOBAL
    effective_production_tonnes: int = TOTAL_GLOBAL
    supply_deficit_pct: float = 0.0
    balance: str = "balanced"     # tight / balanced / oversupplied
    price_pressure: str = "neutral"  # bullish / bearish / neutral
    global_salmon_usd_kg: float = 0.0
    norway_spot_nok_kg: float = 0.0
    norway_premium_pct: float = 0.0
    insights: list[str] = field(default_factory=list)
    #: WS-14: lineage of the newest lice week behind Norway's lice_pressure.
    lice_lineage: dict = field(default_factory=dict)


class GlobalSupplyEngine:
    """Computes global supply balance from all available data."""

    _cache: GlobalSupplyBalance | None = None
    _cache_time: dt.datetime | None = None
    _cache_ttl = dt.timedelta(hours=2)

    async def compute(self) -> GlobalSupplyBalance:
        """Compute global supply balance."""
        now = dt.datetime.now(dt.UTC)
        if self._cache and self._cache_time and (now - self._cache_time) < self._cache_ttl:
            return self._cache

        countries: list[CountrySupply] = []

        # ── Norway ───────────────────────────────────────────────────
        norway = CountrySupply(
            country="Norway",
            production_share=PRODUCERS["Norway"]["share"],
            annual_tonnes=PRODUCERS["Norway"]["tonnes"],
        )
        lice_lineage: dict = {}
        try:
            from core.models import LiceRecord
            from core.async_db import get_async_session
            from core.source_lineage import summarise_rows
            from sqlalchemy import select, func
            async with get_async_session() as s:
                latest = (await s.execute(
                    select(LiceRecord.year, LiceRecord.week)
                    .order_by(LiceRecord.year.desc(), LiceRecord.week.desc())
                    .limit(1)
                )).first()
                if latest:
                    avg = (await s.execute(
                        select(func.avg(LiceRecord.avg_adult_female_lice))
                        .where(LiceRecord.year == latest[0], LiceRecord.week == latest[1],
                               LiceRecord.avg_adult_female_lice.isnot(None))
                    )).scalar() or 0
                    above = (await s.execute(
                        select(func.count(LiceRecord.id))
                        .where(LiceRecord.year == latest[0], LiceRecord.week == latest[1],
                               LiceRecord.avg_adult_female_lice > 0.5)
                    )).scalar() or 0
                    # WS-14: lineage of exactly the rows behind lice_pressure.
                    lice_rows = (await s.execute(
                        select(
                            LiceRecord.source,
                            LiceRecord.year,
                            LiceRecord.week,
                            LiceRecord.fetched_at,
                        ).where(
                            LiceRecord.year == latest[0],
                            LiceRecord.week == latest[1],
                            LiceRecord.avg_adult_female_lice.isnot(None),
                        )
                    )).all()
                    lice_lineage = summarise_rows(lice_rows, year=latest[0])
                    norway.lice_pressure = (
                        "critical" if avg > 0.5 else
                        "elevated" if avg > 0.2 else "normal"
                    )
                    if avg > 0.3:
                        norway.status = "disrupted"
                        norway.disruption_pct = min(15, avg * 20)
                        norway.disruption_reason = f"Elevated lice: avg {avg:.3f}, {above} sites >0.5"
        except Exception:
            pass

        # Regime alerts
        try:
            from core.market.regime_detector import regime_detector
            alerts = regime_detector.get_alerts()
            if alerts:
                norway.disease_events = len(alerts)
                if not norway.disruption_reason:
                    norway.status = "disrupted"
                    norway.disruption_pct = max(norway.disruption_pct, len(alerts) * 2)
                    norway.disruption_reason = f"{len(alerts)} regime color-change alerts"
        except Exception:
            pass

        # Mattilsynet disease outbreaks (ISA/PD) — direct disruption signal
        try:
            from core.market.mattilsynet_client import mattilsynet_client
            cases = await mattilsynet_client.fetch_disease_cases(limit=200)
            active_cases = [c for c in cases if c.status == "active"]
            isa_cases = [c for c in active_cases if "ILA" in c.disease_type or "LAKSEANEMI" in c.disease_type]
            n_active = len(active_cases)
            n_isa = len(isa_cases)
            norway.disease_events = max(norway.disease_events, n_active)

            # ISA is a notifiable disease with mandatory culling — significant disruption
            disease_disruption = n_isa * 1.5 + (n_active - n_isa) * 0.3  # ISA = 1.5% each, PD = 0.3%
            disease_disruption = min(disease_disruption, 10)  # cap at 10%
            if disease_disruption > norway.disruption_pct:
                norway.status = "disrupted"
                norway.disruption_pct = round(disease_disruption, 1)
                norway.disruption_reason = f"{n_active} disease outbreaks ({n_isa} ISA, {n_active - n_isa} PD/other)"
            elif disease_disruption > 0 and norway.disruption_reason:
                norway.disruption_pct = round(max(norway.disruption_pct, disease_disruption), 1)
                norway.disruption_reason += f" + {n_active} disease outbreaks"
        except Exception:
            pass

        countries.append(norway)

        # ── Chile ────────────────────────────────────────────────────
        chile = CountrySupply(
            country="Chile",
            production_share=PRODUCERS["Chile"]["share"],
            annual_tonnes=PRODUCERS["Chile"]["tonnes"],
        )
        try:
            from core.market.chile_monitor import chile_monitor
            snapshot = chile_monitor.get_latest_snapshot()
            if snapshot and snapshot.get("disruption_level"):
                level = snapshot["disruption_level"]
                chile.lice_pressure = "elevated" if level in ("moderate", "high") else "normal"
                if level in ("high", "critical"):
                    chile.status = "disrupted"
                    chile.disruption_pct = 10 if level == "high" else 20
                    chile.disruption_reason = f"ISA: {snapshot.get('isa_outbreaks', 0)}, SRS: {snapshot.get('srs_outbreaks', 0)}"
                    chile.disease_events = (snapshot.get("isa_outbreaks", 0) or 0) + (snapshot.get("srs_outbreaks", 0) or 0)
        except Exception:
            pass
        countries.append(chile)

        # ── Iceland (live data from iceland_monitor) ───────────────
        iceland = CountrySupply(
            country="Iceland",
            production_share=PRODUCERS["Iceland"]["share"],
            annual_tonnes=PRODUCERS["Iceland"]["tonnes"],
        )
        try:
            from core.market.iceland_monitor import iceland_monitor
            ic_snapshot = iceland_monitor.get_latest_snapshot()
            if ic_snapshot:
                iceland.disease_events = ic_snapshot.get("disease_events", 0)
                if ic_snapshot.get("disruption_level") in ("elevated", "disrupted"):
                    iceland.status = ic_snapshot["disruption_level"]
                    iceland.disruption_pct = ic_snapshot.get("disruption_pct", 0)
                    iceland.disruption_reason = f"Disease status: {ic_snapshot.get('disease_status', 'unknown')}"
                # Update production if newer data available
                prod_tonnes = ic_snapshot.get("latest_production_tonnes", 0)
                if prod_tonnes > 0:
                    iceland.annual_tonnes = int(prod_tonnes)
        except Exception:
            pass
        countries.append(iceland)

        # ── Scotland (live from scotland_monitor) ──────────────────
        scotland = CountrySupply(
            country="Scotland",
            production_share=PRODUCERS["Scotland"]["share"],
            annual_tonnes=PRODUCERS["Scotland"]["tonnes"],
        )
        try:
            from core.market.scotland_monitor import scotland_monitor
            sc_snap = scotland_monitor.get_latest_snapshot()
            if sc_snap:
                scotland.disease_events = sc_snap.get("disease_events", 0)
                if sc_snap.get("disruption_level") in ("elevated", "disrupted"):
                    scotland.status = sc_snap["disruption_level"]
                    scotland.disruption_pct = sc_snap.get("disruption_pct", 0)
                    scotland.disruption_reason = f"Bloom risk: {sc_snap.get('bloom_risk', 'unknown')}"
                scotland.lice_pressure = "elevated" if sc_snap.get("bloom_risk") in ("HIGH", "CRITICAL") else "normal"
        except Exception:
            pass
        countries.append(scotland)

        # ── Faroe Islands (live from faroe_monitor) ──────────────
        faroes = CountrySupply(
            country="Faroe Islands",
            production_share=PRODUCERS["Faroe Islands"]["share"],
            annual_tonnes=PRODUCERS["Faroe Islands"]["tonnes"],
        )
        try:
            from core.market.faroe_monitor import faroe_monitor
            fr_snap = faroe_monitor.get_latest_snapshot()
            if fr_snap:
                faroes.disease_events = fr_snap.get("disease_events", 0)
                if fr_snap.get("disruption_level") in ("elevated", "disrupted"):
                    faroes.status = fr_snap["disruption_level"]
                    faroes.disruption_pct = fr_snap.get("disruption_pct", 0)
                prod = fr_snap.get("latest_production_tonnes", 0)
                if prod > 0:
                    faroes.annual_tonnes = int(prod)
        except Exception:
            pass
        countries.append(faroes)

        # ── Canada (live from canada_monitor) ──────────────────────
        canada = CountrySupply(
            country="Canada",
            production_share=PRODUCERS["Canada"]["share"],
            annual_tonnes=PRODUCERS["Canada"]["tonnes"],
        )
        try:
            from core.market.canada_monitor import canada_monitor
            ca_snap = canada_monitor.get_latest_snapshot()
            if ca_snap:
                canada.disease_events = ca_snap.get("disease_events", 0)
                canada.lice_pressure = (
                    "elevated" if ca_snap.get("avg_lice", 0) > 3 else "normal"
                )
                if ca_snap.get("disruption_level") in ("elevated", "disrupted"):
                    canada.status = ca_snap["disruption_level"]
                    canada.disruption_pct = ca_snap.get("disruption_pct", 0)
                    canada.disruption_reason = (
                        f"Lice avg {ca_snap.get('avg_lice', 0):.1f}/fish, "
                        f"{ca_snap.get('disease_events', 0)} disease events"
                    )
        except Exception:
            pass
        countries.append(canada)

        # ── Others ─────────────────────────────────────────────────
        others = PRODUCERS["Others"]
        countries.append(CountrySupply(
            country="Others",
            production_share=others["share"],
            annual_tonnes=others["tonnes"],
            status="normal",
        ))

        # ── Global metrics ───────────────────────────────────────────
        effective = 0
        for c in countries:
            effective += c.annual_tonnes * (1 - c.disruption_pct / 100)
            c.price_impact_pct = round(c.disruption_pct * c.production_share, 1)

        deficit_pct = round((TOTAL_GLOBAL - effective) / TOTAL_GLOBAL * 100, 1)

        if deficit_pct > 5:
            balance = "tight"
            pressure = "bullish"
        elif deficit_pct > 2:
            balance = "moderately_tight"
            pressure = "bullish"
        elif deficit_pct < -2:
            balance = "oversupplied"
            pressure = "bearish"
        else:
            balance = "balanced"
            pressure = "neutral"

        # Get global salmon price from FRED
        global_price = 0.0
        norway_spot = 0.0
        premium = 0.0
        try:
            from core.market.macro_intelligence import macro_intelligence
            snap = await macro_intelligence.fetch()
            global_price = snap.series.get("global_salmon", 0)
            nok_usd = snap.series.get("nok_usd", 10)

            from core.market.ssb_price_client import ssb_price_client
            norway_spot = await ssb_price_client.get_current_spot()

            if global_price > 0 and norway_spot > 0 and nok_usd > 0:
                norway_usd = norway_spot / nok_usd
                premium = round((norway_usd - global_price) / max(global_price, 0.01) * 100, 1)
        except Exception:
            pass

        # ── Insights ─────────────────────────────────────────────────
        insights = []
        disrupted = [c for c in countries if c.status == "disrupted"]
        if disrupted:
            names = ", ".join(c.country for c in disrupted)
            insights.append(f"Supply disruption in {names} — {deficit_pct:.1f}% effective deficit. Price pressure: {pressure}.")
        if premium > 10:
            insights.append(f"Norwegian salmon at {premium:+.0f}% premium to global benchmark — strong demand for Norwegian origin.")
        elif premium < -5:
            insights.append(f"Norwegian salmon at {premium:.0f}% discount to global benchmark — potential buying opportunity.")
        if not insights:
            insights.append("Global supply balanced — no significant disruptions detected.")

        result = GlobalSupplyBalance(
            countries=countries,
            effective_production_tonnes=int(effective),
            supply_deficit_pct=deficit_pct,
            balance=balance,
            price_pressure=pressure,
            global_salmon_usd_kg=round(global_price, 2),
            norway_spot_nok_kg=round(norway_spot, 1),
            norway_premium_pct=premium,
            insights=insights,
            lice_lineage=lice_lineage,
        )

        self._cache = result
        self._cache_time = now
        log.info("global_supply.computed", balance=balance, deficit_pct=deficit_pct, disrupted=len(disrupted))
        return result

    def to_dict(self, gs: GlobalSupplyBalance) -> dict:
        return {
            "generated_at": gs.generated_at.isoformat(),
            "total_production_2025": TOTAL_2025,
            "total_production_2026e": gs.total_production_tonnes,
            "effective_production_tonnes": gs.effective_production_tonnes,
            "supply_deficit_pct": gs.supply_deficit_pct,
            "balance": gs.balance,
            "price_pressure": gs.price_pressure,
            "global_salmon_usd_kg": gs.global_salmon_usd_kg,
            "norway_spot_nok_kg": gs.norway_spot_nok_kg,
            "norway_premium_pct": gs.norway_premium_pct,
            "insights": gs.insights,
            "lice_lineage": gs.lice_lineage,
            "countries": [
                {
                    "country": c.country,
                    "share_pct": round(c.production_share * 100, 1),
                    "annual_tonnes_2026e": c.annual_tonnes,
                    "annual_tonnes_2025": PRODUCTION_2025.get(c.country, {}).get("tonnes", 0),
                    "source_2025": PRODUCTION_2025.get(c.country, {}).get("source", ""),
                    "yoy_growth_pct": PRODUCERS.get(c.country, {}).get("yoy_pct", 0),
                    "status": c.status,
                    "disruption_pct": c.disruption_pct,
                    "disruption_reason": c.disruption_reason,
                    "lice_pressure": c.lice_pressure,
                    "disease_events": c.disease_events,
                    "price_impact_pct": c.price_impact_pct,
                    "currency": PRODUCERS.get(c.country, {}).get("currency", "USD"),
                    "est_source": PRODUCERS.get(c.country, {}).get("est_source", ""),
                }
                for c in gs.countries
            ],
        }


# Singleton
global_supply_engine = GlobalSupplyEngine()
