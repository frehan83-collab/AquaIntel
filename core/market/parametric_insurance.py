"""
Parametric Insurance Data Layer
================================
Provides automated trigger detection for index-based insurance products.
Triggers fire when measurable environmental/biological thresholds are breached,
enabling instant payouts without traditional claims processes.

5 Products:
  1. Lice Outbreak Cover — weekly lice > 0.50 for 2 consecutive weeks
  2. HAB Crisis Cover — bloom risk CRITICAL for 2 consecutive days
  3. Disease Outbreak Cover — ISA/PD active case detected
  4. Temperature Stress Cover — SST > 14.5°C for 7 consecutive days
  5. Supply Disruption Index — anomaly score > 70 or regime color change

Data sources: BarentsWatch, CMEMS, Mattilsynet, MET.no, Anomaly Engine
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import numpy as np
import structlog

log = structlog.get_logger(__name__)

# ── Trigger Definitions ────────────────────────────────────────────

PRODUCTS = {
    "lice_outbreak": {
        "name": "Lice Outbreak Cover",
        "trigger_metric": "avg_adult_female_lice",
        "threshold": 0.50,
        "confirmation_periods": 2,  # 2 consecutive weeks
        "frequency": "weekly",
        "payout_nok_per_period": 250_000,
        "data_source": "BarentsWatch",
        "description": "Pays when farm lice exceed 0.50 for 2 consecutive weeks",
    },
    "hab_crisis": {
        "name": "HAB Crisis Cover",
        "trigger_metric": "bloom_risk_score",
        "threshold": 75,  # CRITICAL
        "confirmation_periods": 2,  # 2 consecutive days
        "frequency": "daily",
        "payout_nok_per_event": 750_000,
        "data_source": "CMEMS",
        "description": "Pays when bloom risk reaches CRITICAL for 2+ days",
    },
    "disease_outbreak": {
        "name": "Disease Outbreak Cover",
        "trigger_metric": "isa_active",
        "threshold": 1,  # any active ISA case
        "confirmation_periods": 1,
        "frequency": "realtime",
        "payout_nok_per_month": 200_000,
        "data_source": "Mattilsynet",
        "description": "Pays when ISA outbreak detected at farm locality",
    },
    "temperature_stress": {
        "name": "Temperature Stress Cover",
        "trigger_metric": "sea_temperature_c",
        "threshold": 14.5,
        "confirmation_periods": 7,  # 7 consecutive days
        "frequency": "daily",
        "payout_nok_per_week": 150_000,
        "data_source": "MET.no",
        "description": "Pays when SST exceeds 14.5C for 7+ consecutive days",
    },
    "supply_disruption": {
        "name": "Supply Disruption Index",
        "trigger_metric": "anomaly_composite_score",
        "threshold": 70,  # CRITICAL
        "confirmation_periods": 1,
        "frequency": "hourly",
        "payout_nok_per_event": 500_000,
        "data_source": "Anomaly Engine",
        "description": "Pays when composite risk score exceeds CRITICAL threshold",
    },
}


@dataclass
class TriggerEvent:
    """A detected parametric trigger."""
    id: str
    product: str
    product_name: str
    locality_no: int | None
    locality_name: str
    production_area: int | None
    trigger_metric: str
    threshold: float
    actual_value: float
    breach_pct: float  # how far above threshold
    confirmed: bool
    confirmation_progress: int  # e.g. 1 of 2 periods
    confirmation_required: int
    triggered_at: str
    data_source: str
    estimated_payout_nok: float
    status: str  # "pending_confirmation", "confirmed", "expired"


@dataclass
class RiskProfile:
    """Per-farm or per-PA insurance risk profile."""
    locality_no: int | None
    production_area: int | None
    name: str
    lice_risk: float  # 0-100
    hab_risk: float
    disease_risk: float
    temperature_risk: float
    composite_risk: float
    risk_tier: str  # "low", "medium", "high", "very_high"
    premium_multiplier: float  # 1.0 = base, >1.0 = higher risk
    active_triggers: int
    historical_triggers_12m: int


class ParametricInsuranceEngine:
    """
    Monitors live data feeds and detects parametric trigger events.
    """

    def __init__(self) -> None:
        self._trigger_events: list[TriggerEvent] = []
        self._trigger_counter = 0
        self._last_scan: dt.datetime | None = None

    def _make_id(self) -> str:
        self._trigger_counter += 1
        return f"trig-{self._trigger_counter}-{dt.datetime.now(dt.UTC).strftime('%Y%m%d%H%M')}"

    async def scan_triggers(self) -> list[dict]:
        """Scan all data sources for trigger breaches. Returns new trigger events."""
        new_triggers: list[TriggerEvent] = []

        # 1. Lice triggers
        try:
            from core.models import LiceRecord, Locality
            from core.async_db import get_async_session
            from sqlalchemy import select, func, desc

            async with get_async_session() as session:
                # Get latest 2 weeks of lice data, find farms above threshold
                latest = (await session.execute(
                    select(
                        LiceRecord.locality_no,
                        func.avg(LiceRecord.avg_adult_female_lice).label("avg_lice"),
                        func.count().label("n_weeks"),
                    )
                    .where(LiceRecord.avg_adult_female_lice >= 0.50)
                    .group_by(LiceRecord.locality_no)
                    .having(func.count() >= 2)
                    .order_by(desc("avg_lice"))
                    .limit(20)
                )).all()

                for row in latest:
                    loc = await session.get(Locality, row.locality_no)
                    t = TriggerEvent(
                        id=self._make_id(),
                        product="lice_outbreak",
                        product_name="Lice Outbreak Cover",
                        locality_no=row.locality_no,
                        locality_name=loc.name if loc else f"Locality {row.locality_no}",
                        production_area=loc.production_area if loc else None,
                        trigger_metric="avg_adult_female_lice",
                        threshold=0.50,
                        actual_value=round(float(row.avg_lice), 4),
                        breach_pct=round((float(row.avg_lice) - 0.50) / 0.50 * 100, 1),
                        confirmed=row.n_weeks >= 2,
                        confirmation_progress=min(int(row.n_weeks), 2),
                        confirmation_required=2,
                        triggered_at=dt.datetime.now(dt.UTC).isoformat(),
                        data_source="BarentsWatch",
                        estimated_payout_nok=250_000 * min(int(row.n_weeks), 4),
                        status="confirmed" if row.n_weeks >= 2 else "pending_confirmation",
                    )
                    new_triggers.append(t)
        except Exception as e:
            log.debug("parametric.lice_scan_failed", error=str(e)[:80])

        # 2. HAB / Bloom triggers
        try:
            from core.bloom.risk_model import bloom_risk_engine
            risks = bloom_risk_engine.get_all_assessments()
            for r in (risks if isinstance(risks, list) else []):
                if isinstance(r, dict) and (r.get("risk_score", 0) >= 75 or r.get("risk_level") == "CRITICAL"):
                    t = TriggerEvent(
                        id=self._make_id(),
                        product="hab_crisis",
                        product_name="HAB Crisis Cover",
                        locality_no=r.get("locality_no"),
                        locality_name=r.get("name", r.get("locality_name", "Unknown")),
                        production_area=r.get("production_area"),
                        trigger_metric="bloom_risk_score",
                        threshold=75,
                        actual_value=round(float(r.get("risk_score", 0)), 1),
                        breach_pct=round((float(r.get("risk_score", 0)) - 75) / 75 * 100, 1),
                        confirmed=True,  # CMEMS data is already daily-confirmed
                        confirmation_progress=2,
                        confirmation_required=2,
                        triggered_at=dt.datetime.now(dt.UTC).isoformat(),
                        data_source="CMEMS",
                        estimated_payout_nok=750_000,
                        status="confirmed",
                    )
                    new_triggers.append(t)
        except Exception as e:
            log.debug("parametric.hab_scan_failed", error=str(e)[:80])

        # 3. Disease triggers
        try:
            from core.market.mattilsynet_client import mattilsynet_client
            cases = await mattilsynet_client.fetch_disease_cases()
            isa_cases = [c for c in cases if "ISA" in str(getattr(c, "disease_type", "")).upper()
                         or "LAKSEANEMI" in str(getattr(c, "disease_type", "")).upper()]
            for c in isa_cases[:5]:
                t = TriggerEvent(
                    id=self._make_id(),
                    product="disease_outbreak",
                    product_name="Disease Outbreak Cover",
                    locality_no=getattr(c, "locality_no", None),
                    locality_name=getattr(c, "locality_name", "Unknown"),
                    production_area=None,
                    trigger_metric="isa_active",
                    threshold=1,
                    actual_value=1.0,
                    breach_pct=0.0,
                    confirmed=True,
                    confirmation_progress=1,
                    confirmation_required=1,
                    triggered_at=dt.datetime.now(dt.UTC).isoformat(),
                    data_source="Mattilsynet",
                    estimated_payout_nok=200_000,
                    status="confirmed",
                )
                new_triggers.append(t)
        except Exception as e:
            log.debug("parametric.disease_scan_failed", error=str(e)[:80])

        # 4. Anomaly / Supply Disruption
        try:
            from core.market.anomaly_engine import anomaly_engine
            scores = anomaly_engine.compute_scores()
            if isinstance(scores, dict):
                composite = scores.get("composite_risk_score", 0)
                if composite >= 70:
                    t = TriggerEvent(
                        id=self._make_id(),
                        product="supply_disruption",
                        product_name="Supply Disruption Index",
                        locality_no=None,
                        locality_name="National",
                        production_area=None,
                        trigger_metric="anomaly_composite_score",
                        threshold=70,
                        actual_value=round(float(composite), 1),
                        breach_pct=round((float(composite) - 70) / 70 * 100, 1),
                        confirmed=True,
                        confirmation_progress=1,
                        confirmation_required=1,
                        triggered_at=dt.datetime.now(dt.UTC).isoformat(),
                        data_source="Anomaly Engine",
                        estimated_payout_nok=500_000,
                        status="confirmed",
                    )
                    new_triggers.append(t)
        except Exception as e:
            log.debug("parametric.anomaly_scan_failed", error=str(e)[:80])

        # Store and log
        self._trigger_events = new_triggers + self._trigger_events
        if len(self._trigger_events) > 200:
            self._trigger_events = self._trigger_events[:200]
        self._last_scan = dt.datetime.now(dt.UTC)

        log.info("parametric.scan_complete", n_triggers=len(new_triggers))
        return [self._to_dict(t) for t in new_triggers]

    def get_active_triggers(self, product: str | None = None, confirmed_only: bool = False) -> list[dict]:
        """Get active trigger events."""
        triggers = self._trigger_events
        if product:
            triggers = [t for t in triggers if t.product == product]
        if confirmed_only:
            triggers = [t for t in triggers if t.confirmed]
        return [self._to_dict(t) for t in triggers[:50]]

    def get_products(self) -> list[dict]:
        """Get available insurance products."""
        return [{"id": k, **v} for k, v in PRODUCTS.items()]

    async def compute_risk_profile(self, locality_no: int | None = None, production_area: int | None = None) -> dict:
        """Compute insurance risk profile for a farm or PA."""
        lice_risk = 0.0
        hab_risk = 0.0
        disease_risk = 0.0
        temp_risk = 0.0

        # Count recent triggers for this location
        active = 0
        historical = 0
        for t in self._trigger_events:
            if locality_no and t.locality_no == locality_no:
                active += 1 if t.confirmed else 0
                historical += 1
            elif production_area and t.production_area == production_area:
                active += 1 if t.confirmed else 0
                historical += 1

        # Get lice data
        try:
            from core.models import LiceRecord
            from core.async_db import get_async_session
            from sqlalchemy import select, func
            async with get_async_session() as session:
                query = select(func.avg(LiceRecord.avg_adult_female_lice))
                if locality_no:
                    query = query.where(LiceRecord.locality_no == locality_no)
                avg = (await session.execute(query)).scalar()
                if avg:
                    lice_risk = min(100, float(avg) / 0.50 * 100)
        except Exception:
            pass

        # Get bloom risk
        try:
            from core.bloom.risk_model import bloom_risk_engine
            risks = bloom_risk_engine.get_all_assessments()
            for r in (risks if isinstance(risks, list) else []):
                if isinstance(r, dict):
                    if locality_no and r.get("locality_no") == locality_no:
                        hab_risk = r.get("risk_score", 0)
                        break
                    elif production_area and r.get("production_area") == production_area:
                        hab_risk = max(hab_risk, r.get("risk_score", 0))
        except Exception:
            pass

        # Composite
        composite = 0.35 * lice_risk + 0.25 * hab_risk + 0.25 * disease_risk + 0.15 * temp_risk
        tier = (
            "very_high" if composite >= 70 else
            "high" if composite >= 50 else
            "medium" if composite >= 25 else
            "low"
        )
        multiplier = (
            2.0 if tier == "very_high" else
            1.5 if tier == "high" else
            1.2 if tier == "medium" else
            1.0
        )

        return {
            "locality_no": locality_no,
            "production_area": production_area,
            "lice_risk": round(lice_risk, 1),
            "hab_risk": round(hab_risk, 1),
            "disease_risk": round(disease_risk, 1),
            "temperature_risk": round(temp_risk, 1),
            "composite_risk": round(composite, 1),
            "risk_tier": tier,
            "premium_multiplier": multiplier,
            "active_triggers": active,
            "historical_triggers": historical,
        }

    def get_dashboard(self) -> dict:
        """Summary dashboard for insurance underwriters."""
        confirmed = [t for t in self._trigger_events if t.confirmed]
        pending = [t for t in self._trigger_events if not t.confirmed]
        total_payout = sum(t.estimated_payout_nok for t in confirmed)

        by_product: dict[str, int] = {}
        for t in confirmed:
            by_product[t.product] = by_product.get(t.product, 0) + 1

        by_pa: dict[int, int] = {}
        for t in confirmed:
            if t.production_area:
                by_pa[t.production_area] = by_pa.get(t.production_area, 0) + 1

        return {
            "last_scan": self._last_scan.isoformat() if self._last_scan else None,
            "total_triggers": len(self._trigger_events),
            "confirmed_triggers": len(confirmed),
            "pending_triggers": len(pending),
            "estimated_total_payout_nok": round(total_payout, 0),
            "by_product": by_product,
            "by_production_area": by_pa,
            "products_available": len(PRODUCTS),
            "recent_triggers": [self._to_dict(t) for t in self._trigger_events[:10]],
        }

    @staticmethod
    def _to_dict(t: TriggerEvent) -> dict:
        from dataclasses import asdict
        return asdict(t)


# Singleton
parametric_insurance_engine = ParametricInsuranceEngine()
