"""
Cross-Market Arbitrage — Chile vs Norway Supply Model
========================================================
Monitors Chilean salmon supply (world's #2 producer) to detect
global supply imbalances that drive Norwegian salmon prices.

When Chile has problems (ISA outbreaks, algal blooms, high lice),
global supply drops → Norwegian prices rise → bullish signal.

Data sources:
  - Sernapesca (Chilean fisheries authority) — public reports
  - SalmonEx / IndexSalmon — Chilean spot prices
  - Multiexport, AquaChile, Cermaq Chile — public filings
  - USDA FAS — import/export data

Alpha: Chilean supply disruptions take 2-6 weeks to fully impact
Norwegian spot prices. Early detection = trading lead time.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Optional

import httpx
import numpy as np
import structlog

from config.settings import settings

log = structlog.get_logger(__name__)


@dataclass
class ChileanSupplySnapshot:
    """Snapshot of Chilean salmon supply conditions."""
    fetched_at: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))
    harvest_tonnes_month: float = 0
    harvest_trend: str = "stable"  # increasing/stable/decreasing
    mortality_pct: float = 0
    isa_outbreaks_active: int = 0
    caligus_avg: float = 0  # Chilean sea lice (Caligidus rogercresseyi)
    srs_outbreaks: int = 0  # Piscirickettsiosis
    algal_bloom_active: bool = False
    smolt_stocking_trend: str = "stable"
    estimated_spot_usd_kg: float = 0
    supply_disruption_score: float = 0  # 0-1, higher = more disrupted


@dataclass
class CrossMarketSignal:
    """Trading signal from cross-market analysis."""
    generated_at: dt.datetime
    signal_type: str  # supply_disruption, price_divergence, recovery
    direction: str  # bullish, bearish, neutral (for Norwegian stocks)
    strength: float  # 0-1
    chile_factor: str  # what's happening in Chile
    norway_implication: str  # what it means for Norway
    affected_tickers: list[str]
    estimated_price_impact_pct: float
    time_horizon_weeks: int
    confidence: float
    rationale: str


# Chilean salmon production regions with coordinates
CHILE_REGIONS = {
    "Los Lagos (Region X)": {"main_species": "atlantic", "share_pct": 35, "lat": -41.5, "lng": -73.0},
    "Aysén (Region XI)": {"main_species": "atlantic", "share_pct": 40, "lat": -45.5, "lng": -73.5},
    "Magallanes (Region XII)": {"main_species": "atlantic", "share_pct": 20, "lat": -52.0, "lng": -74.5},
    "Other": {"main_species": "coho/trout", "share_pct": 5, "lat": -39.0, "lng": -73.0},
}

# CMEMS bounding box for Chilean Patagonia
CHILE_BBOX = {"lat_min": -55.0, "lat_max": -39.0, "lon_min": -78.0, "lon_max": -70.0}

# Major Chilean salmon companies
CHILE_COMPANIES = {
    "Multiexport Foods": {"ticker": "MULTIFOOD", "exchange": "Santiago", "capacity_t": 80000},
    "AquaChile": {"ticker": "AQUACHILE", "exchange": "Santiago", "capacity_t": 95000},
    "Cermaq Chile": {"ticker": "CERMAQ", "exchange": "Private (Mitsubishi)", "capacity_t": 55000},
    "Mowi Chile": {"ticker": "MOWI", "exchange": "Oslo", "capacity_t": 30000},
    "Salmones Camanchaca": {"ticker": "SALMOCAM", "exchange": "Santiago/Oslo", "capacity_t": 50000},
    "Australis Seafoods": {"ticker": "AUSS", "exchange": "Santiago", "capacity_t": 40000},
    "Blumar": {"ticker": "BLUMAR", "exchange": "Santiago", "capacity_t": 35000},
}

# Historical supply disruption events and their Norwegian price impact
HISTORICAL_EVENTS = [
    {"year": 2016, "event": "Chilean algal bloom", "duration_weeks": 12, "norway_price_impact_pct": 25},
    {"year": 2019, "event": "Northern Norway algal bloom", "duration_weeks": 6, "norway_price_impact_pct": 15},
    {"year": 2021, "event": "Chile ISA cluster", "duration_weeks": 8, "norway_price_impact_pct": 8},
    {"year": 2023, "event": "Chile SRS mortality spike", "duration_weeks": 4, "norway_price_impact_pct": 5},
]

# Global salmon supply model parameters
GLOBAL_SUPPLY = {
    "norway_share": 0.52,  # % of global Atlantic salmon
    "chile_share": 0.25,
    "uk_share": 0.08,
    "canada_share": 0.06,
    "faroe_share": 0.04,
    "other_share": 0.05,
    "total_annual_tonnes": 2_800_000,  # approximate global Atlantic salmon
}

# Price elasticity: % change in Norwegian price per % change in global supply
SUPPLY_PRICE_ELASTICITY = -1.5  # 1% supply drop → 1.5% price increase


class ChileMonitor:
    """
    Monitors Chilean salmon supply conditions and generates
    cross-market arbitrage signals for Norwegian salmon stocks.

    Pipeline:
    1. Fetch Chilean supply data (Sernapesca, public sources)
    2. Assess supply disruption level
    3. Model global supply impact
    4. Generate Norwegian price impact signals
    """

    def __init__(self) -> None:
        self._snapshots: list[ChileanSupplySnapshot] = []
        self._signals: list[CrossMarketSignal] = []
        self._last_fetch: Optional[dt.datetime] = None
        self._client: Optional[httpx.AsyncClient] = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30,
                headers={"User-Agent": "OpenClaw/1.0 Research"},
                follow_redirects=True,
            )
        return self._client

    async def fetch_chile_data(self) -> ChileanSupplySnapshot:
        """
        Fetch latest Chilean salmon supply data from public sources.

        Primary source: Sernapesca public reports
        Backup: Chilean stock exchange filings, industry reports
        """
        client = await self._ensure_client()
        snapshot = ChileanSupplySnapshot()

        # 1. Try Sernapesca public data
        try:
            # Sernapesca publishes monthly harvest data
            resp = await client.get(
                "https://www.sernapesca.cl/informes/estadisticas",
                timeout=15,
            )
            if resp.status_code == 200:
                # Parse harvest and sanitary data from Sernapesca
                text = resp.text.lower()
                # Look for ISA/SRS outbreak indicators
                if "isa" in text or "anemia" in text:
                    snapshot.isa_outbreaks_active = max(1, snapshot.isa_outbreaks_active)
                if "srs" in text or "piscirickettsia" in text:
                    snapshot.srs_outbreaks = max(1, snapshot.srs_outbreaks)
                if "bloom" in text or "floración" in text:
                    snapshot.algal_bloom_active = True

        except Exception as e:
            log.debug("chile.sernapesca_error", error=str(e)[:80])

        # 2. Try IndexSalmon for Chilean spot prices
        try:
            resp = await client.get(
                "https://www.indexsalmon.com/",
                timeout=10,
            )
            if resp.status_code == 200:
                # Parse Chilean salmon price if available
                text = resp.text
                # Look for USD/kg price indicators
                import re
                price_matches = re.findall(r'USD\s*(\d+[\.,]\d+)', text)
                if price_matches:
                    snapshot.estimated_spot_usd_kg = float(price_matches[0].replace(',', '.'))

        except Exception as e:
            log.debug("chile.indexsalmon_error", error=str(e)[:80])

        # 3. Compute supply disruption score
        snapshot.supply_disruption_score = self._compute_disruption_score(snapshot)

        self._snapshots.append(snapshot)
        if len(self._snapshots) > 365:
            self._snapshots = self._snapshots[-365:]

        self._last_fetch = dt.datetime.now(dt.UTC)

        # Generate signals if disruption detected
        if snapshot.supply_disruption_score > 0.2:
            self._generate_cross_market_signal(snapshot)

        log.info(
            "chile.fetched",
            disruption=snapshot.supply_disruption_score,
            isa=snapshot.isa_outbreaks_active,
        )

        return snapshot

    def _compute_disruption_score(self, snapshot: ChileanSupplySnapshot) -> float:
        """Compute 0-1 supply disruption score."""
        score = 0.0

        # ISA outbreaks (most impactful)
        score += min(0.4, snapshot.isa_outbreaks_active * 0.15)

        # SRS outbreaks
        score += min(0.2, snapshot.srs_outbreaks * 0.05)

        # Algal bloom
        if snapshot.algal_bloom_active:
            score += 0.25

        # High mortality
        if snapshot.mortality_pct > 15:
            score += 0.15
        elif snapshot.mortality_pct > 10:
            score += 0.08

        # High lice
        if snapshot.caligus_avg > 6:
            score += 0.10
        elif snapshot.caligus_avg > 3:
            score += 0.05

        # Harvest trend
        if snapshot.harvest_trend == "decreasing":
            score += 0.10

        return min(1.0, score)

    def _generate_cross_market_signal(self, snapshot: ChileanSupplySnapshot) -> None:
        """Generate cross-market trading signal from Chilean disruption."""
        disruption = snapshot.supply_disruption_score

        # Estimate supply impact
        chile_supply_loss_pct = disruption * 15  # 0-15% reduction
        global_supply_impact = chile_supply_loss_pct * GLOBAL_SUPPLY["chile_share"]
        norway_price_impact = abs(global_supply_impact * SUPPLY_PRICE_ELASTICITY)

        # Determine signal
        if disruption > 0.5:
            direction = "bullish"
            strength = min(1.0, disruption)
            chile_factor = "Major supply disruption"
        elif disruption > 0.3:
            direction = "bullish"
            strength = disruption * 0.8
            chile_factor = "Moderate supply concern"
        else:
            direction = "bullish"
            strength = disruption * 0.5
            chile_factor = "Minor supply pressure"

        factors = []
        if snapshot.isa_outbreaks_active:
            factors.append(f"{snapshot.isa_outbreaks_active} ISA outbreaks")
        if snapshot.algal_bloom_active:
            factors.append("Algal bloom active")
        if snapshot.srs_outbreaks:
            factors.append(f"{snapshot.srs_outbreaks} SRS outbreaks")

        signal = CrossMarketSignal(
            generated_at=dt.datetime.now(dt.UTC),
            signal_type="supply_disruption",
            direction=direction,
            strength=round(strength, 3),
            chile_factor=chile_factor + ": " + ", ".join(factors) if factors else chile_factor,
            norway_implication=f"Chilean supply -{chile_supply_loss_pct:.1f}% → Norwegian price +{norway_price_impact:.1f}%",
            affected_tickers=["MOWI", "SALM", "LSG", "GSF"],
            estimated_price_impact_pct=round(norway_price_impact, 2),
            time_horizon_weeks=4,
            confidence=min(0.8, 0.3 + disruption * 0.5),
            rationale=(
                f"Chilean salmon supply disrupted ({disruption:.0%} score). "
                f"Chile produces {GLOBAL_SUPPLY['chile_share']:.0%} of global Atlantic salmon. "
                f"Estimated global supply impact: -{global_supply_impact:.1f}%. "
                f"Historical price elasticity suggests +{norway_price_impact:.1f}% Norwegian price impact."
            ),
        )

        self._signals.append(signal)
        if len(self._signals) > 50:
            self._signals = self._signals[-50:]

    # ── Public API ───────────────────────────────────────────────

    def get_latest_snapshot(self) -> Optional[dict]:
        """Get latest Chilean supply snapshot."""
        if not self._snapshots:
            return None

        s = self._snapshots[-1]
        return {
            "fetched_at": s.fetched_at.isoformat(),
            "harvest_tonnes_month": s.harvest_tonnes_month,
            "harvest_trend": s.harvest_trend,
            "mortality_pct": s.mortality_pct,
            "isa_outbreaks": s.isa_outbreaks_active,
            "caligus_avg": s.caligus_avg,
            "srs_outbreaks": s.srs_outbreaks,
            "algal_bloom": s.algal_bloom_active,
            "spot_usd_kg": s.estimated_spot_usd_kg,
            "disruption_score": s.supply_disruption_score,
            "disruption_level": (
                "critical" if s.supply_disruption_score > 0.6 else
                "high" if s.supply_disruption_score > 0.4 else
                "moderate" if s.supply_disruption_score > 0.2 else
                "low"
            ),
        }

    def get_signals(self, days: int = 30) -> list[dict]:
        """Get recent cross-market signals."""
        cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(days=days)
        return [
            {
                "generated_at": s.generated_at.isoformat(),
                "signal_type": s.signal_type,
                "direction": s.direction,
                "strength": s.strength,
                "chile_factor": s.chile_factor,
                "norway_implication": s.norway_implication,
                "tickers": s.affected_tickers,
                "price_impact_pct": s.estimated_price_impact_pct,
                "horizon_weeks": s.time_horizon_weeks,
                "confidence": s.confidence,
                "rationale": s.rationale,
            }
            for s in self._signals
            if s.generated_at > cutoff
        ]

    def get_global_supply_model(self) -> dict:
        """Get global salmon supply balance model."""
        latest = self._snapshots[-1] if self._snapshots else None
        chile_disruption = latest.supply_disruption_score if latest else 0

        chile_effective = GLOBAL_SUPPLY["chile_share"] * (1 - chile_disruption * 0.15)
        total_effective = (
            GLOBAL_SUPPLY["norway_share"] +
            chile_effective +
            GLOBAL_SUPPLY["uk_share"] +
            GLOBAL_SUPPLY["canada_share"] +
            GLOBAL_SUPPLY["faroe_share"] +
            GLOBAL_SUPPLY["other_share"]
        )
        supply_deficit = 1.0 - total_effective

        return {
            "generated_at": dt.datetime.now(dt.UTC).isoformat(),
            "total_annual_tonnes": GLOBAL_SUPPLY["total_annual_tonnes"],
            "producers": {
                "Norway": {"share": GLOBAL_SUPPLY["norway_share"], "status": "normal"},
                "Chile": {
                    "share": GLOBAL_SUPPLY["chile_share"],
                    "effective_share": round(chile_effective, 3),
                    "status": "disrupted" if chile_disruption > 0.2 else "normal",
                    "disruption_score": chile_disruption,
                },
                "UK/Scotland": {"share": GLOBAL_SUPPLY["uk_share"], "status": "normal"},
                "Canada": {"share": GLOBAL_SUPPLY["canada_share"], "status": "normal"},
                "Faroe Islands": {"share": GLOBAL_SUPPLY["faroe_share"], "status": "normal"},
            },
            "global_supply_balance": round(total_effective, 3),
            "supply_deficit_pct": round(supply_deficit * 100, 2),
            "implied_price_impact_pct": round(supply_deficit * 100 * abs(SUPPLY_PRICE_ELASTICITY), 2),
            "historical_events": HISTORICAL_EVENTS,
        }

    def get_farms_geojson(self) -> dict:
        """Chilean production regions as GeoJSON."""
        snapshot = self.get_latest_snapshot() or {}
        features = []
        for name, info in CHILE_REGIONS.items():
            if "lat" not in info:
                continue
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [info["lng"], info["lat"]]},
                "properties": {
                    "name": name,
                    "country": "Chile",
                    "share_pct": info["share_pct"],
                    "species": info["main_species"],
                    "isa_outbreaks": snapshot.get("isa_outbreaks", 0),
                    "srs_outbreaks": snapshot.get("srs_outbreaks", 0),
                    "disruption_level": snapshot.get("disruption_level", "unknown"),
                },
            })
        return {"type": "FeatureCollection", "features": features}

    async def shutdown(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# Singleton
chile_monitor = ChileMonitor()
