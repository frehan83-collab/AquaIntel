"""
WOAH Disease Alert Engine
==========================
Monitors the World Organisation for Animal Health (WOAH/OIE) WAHIS database
for notifiable fish disease outbreaks relevant to salmon aquaculture.

Key diseases monitored:
  - ISA (Infectious Salmon Anaemia) — OIE-listed, trade-restricting
  - IHN (Infectious Haematopoietic Necrosis) — OIE-listed
  - VHS (Viral Haemorrhagic Septicaemia) — OIE-listed
  - PD (Pancreas Disease) — major Norwegian concern
  - BKD (Bacterial Kidney Disease) — chronic
  - SRS (Salmonid Rickettsial Septicemia) — Chile's major issue

Data sources:
  - WOAH WAHIS API (free, JSON)
  - Norwegian Veterinary Institute reports (via BarentsWatch)
  - Sernapesca Chile (already integrated)

Value: Disease outbreaks cause immediate production cuts, trade restrictions,
       and supply shocks. Early warning = trading edge + farm biosecurity.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import httpx
import structlog

log = structlog.get_logger(__name__)

# Target countries and diseases
SALMON_COUNTRIES = ["NOR", "CHL", "GBR", "CAN", "FRO", "ISL"]
SALMON_DISEASES = [
    "Infectious salmon anaemia",
    "Infectious haematopoietic necrosis",
    "Viral haemorrhagic septicaemia",
]


@dataclass
class DiseaseAlert:
    """A single disease outbreak notification."""
    disease: str
    country: str
    country_code: str
    report_date: str
    status: str = "ongoing"     # ongoing / resolved / suspected
    cases: int = 0
    deaths: int = 0
    source: str = "woah"
    severity: str = "moderate"  # low / moderate / high / critical
    trade_impact: bool = False  # does this trigger trade restrictions?
    supply_impact_pct: float = 0.0


@dataclass
class DiseaseIntelligence:
    """Complete disease intelligence snapshot."""
    generated_at: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))
    alerts: list[DiseaseAlert] = field(default_factory=list)
    active_outbreaks: int = 0
    countries_affected: list[str] = field(default_factory=list)
    risk_level: str = "low"     # low / moderate / elevated / high
    insights: list[str] = field(default_factory=list)


class DiseaseAlertEngine:
    """Monitors global fish disease outbreaks from multiple sources."""

    _cache: DiseaseIntelligence | None = None
    _cache_time: dt.datetime | None = None
    _cache_ttl = dt.timedelta(hours=6)

    async def fetch_alerts(self) -> DiseaseIntelligence:
        """Fetch disease alerts from all sources."""
        now = dt.datetime.now(dt.UTC)
        if self._cache and self._cache_time and (now - self._cache_time) < self._cache_ttl:
            return self._cache

        alerts: list[DiseaseAlert] = []

        # 1. WOAH WAHIS API
        woah_alerts = await self._fetch_woah()
        alerts.extend(woah_alerts)

        # 2. Chile disease data (from existing chile_monitor)
        chile_alerts = self._get_chile_alerts()
        alerts.extend(chile_alerts)

        # 3. Norway disease data (from BarentsWatch/regime)
        norway_alerts = self._get_norway_alerts()
        alerts.extend(norway_alerts)

        # Compute summary
        active = [a for a in alerts if a.status in ("ongoing", "suspected")]
        countries = list(set(a.country for a in active))

        risk = "low"
        if len(active) >= 5 or any(a.severity == "critical" for a in active):
            risk = "high"
        elif len(active) >= 3 or any(a.severity == "high" for a in active):
            risk = "elevated"
        elif len(active) >= 1:
            risk = "moderate"

        insights = []
        if active:
            for a in active:
                if a.trade_impact:
                    insights.append(
                        f"{a.disease} in {a.country} — trade restrictions may affect supply. "
                        f"Estimated {a.supply_impact_pct:.0f}% regional supply impact."
                    )
        if any(a.country_code == "NOR" for a in active):
            insights.append("Norwegian disease events detected — monitor lice pressure and regime alerts closely.")
        if any(a.country_code == "CHL" for a in active):
            insights.append("Chilean outbreak activity — potential supply disruption supporting Norwegian prices.")
        if not insights:
            insights.append("No significant disease outbreaks detected across major salmon-producing nations.")

        result = DiseaseIntelligence(
            alerts=alerts,
            active_outbreaks=len(active),
            countries_affected=countries,
            risk_level=risk,
            insights=insights,
        )

        self._cache = result
        self._cache_time = now
        log.info("disease.alerts_fetched", total=len(alerts), active=len(active), risk=risk)
        return result

    async def _fetch_woah(self) -> list[DiseaseAlert]:
        """Fetch from WOAH WAHIS API."""
        alerts = []
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                # WAHIS API v1 — disease event list
                resp = await client.get(
                    "https://wahis.woah.org/api/v1/pi/getReport/list",
                    params={
                        "reportType": "I",  # Immediate notifications
                        "diseaseId": "",     # All diseases
                        "year": str(dt.datetime.now(dt.UTC).year),
                    },
                    headers={"User-Agent": "OpenClaw/1.0 Research"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    reports = data if isinstance(data, list) else data.get("reports", data.get("data", []))
                    for report in (reports or [])[:50]:
                        disease = report.get("diseaseName", report.get("disease", ""))
                        country = report.get("countryName", report.get("country", ""))
                        code = report.get("countryIso3", report.get("iso3", ""))

                        # Only salmon-relevant diseases in salmon countries
                        is_salmon_disease = any(d.lower() in disease.lower() for d in [
                            "salmon", "haematopoietic", "septicaemia", "anaemia",
                        ])
                        is_salmon_country = code in SALMON_COUNTRIES

                        if is_salmon_disease or is_salmon_country:
                            alerts.append(DiseaseAlert(
                                disease=disease,
                                country=country,
                                country_code=code,
                                report_date=report.get("reportDate", report.get("date", "")),
                                status="ongoing",
                                source="woah_wahis",
                                severity="high" if "salmon" in disease.lower() else "moderate",
                                trade_impact="salmon" in disease.lower(),
                                supply_impact_pct=2.0 if is_salmon_country else 0.5,
                            ))
                else:
                    log.debug("disease.woah_status", status=resp.status_code)
        except Exception as exc:
            log.debug("disease.woah_error", error=str(exc)[:80])

        return alerts

    def _get_chile_alerts(self) -> list[DiseaseAlert]:
        """Get Chile disease data from existing chile_monitor."""
        alerts = []
        try:
            from core.market.chile_monitor import chile_monitor
            snapshot = chile_monitor.get_latest_snapshot()
            if snapshot:
                isa = snapshot.get("isa_outbreaks", 0) or 0
                srs = snapshot.get("srs_outbreaks", 0) or 0
                if isa > 0:
                    alerts.append(DiseaseAlert(
                        disease="Infectious Salmon Anaemia (ISA)",
                        country="Chile",
                        country_code="CHL",
                        report_date=dt.datetime.now(dt.UTC).strftime("%Y-%m-%d"),
                        status="ongoing",
                        cases=isa,
                        source="sernapesca",
                        severity="high" if isa > 3 else "moderate",
                        trade_impact=True,
                        supply_impact_pct=min(5, isa * 1.5),
                    ))
                if srs > 0:
                    alerts.append(DiseaseAlert(
                        disease="Salmonid Rickettsial Septicemia (SRS)",
                        country="Chile",
                        country_code="CHL",
                        report_date=dt.datetime.now(dt.UTC).strftime("%Y-%m-%d"),
                        status="ongoing",
                        cases=srs,
                        source="sernapesca",
                        severity="moderate",
                        trade_impact=False,
                        supply_impact_pct=min(3, srs * 0.5),
                    ))
        except Exception:
            pass
        return alerts

    def _get_norway_alerts(self) -> list[DiseaseAlert]:
        """Get Norway disease signals from regime detector and lice data."""
        alerts = []
        try:
            from core.market.regime_detector import regime_detector
            regime_alerts = regime_detector.get_alerts()
            for ra in (regime_alerts or []):
                if ra.get("predicted") == "red":
                    alerts.append(DiseaseAlert(
                        disease=f"Regulatory regime change PA{ra['production_area']}",
                        country="Norway",
                        country_code="NOR",
                        report_date=dt.datetime.now(dt.UTC).strftime("%Y-%m-%d"),
                        status="predicted",
                        source="regime_detector",
                        severity="moderate",
                        trade_impact=False,
                        supply_impact_pct=ra.get("probability", 0.5) * 2,
                    ))
        except Exception:
            pass
        return alerts

    def to_dict(self, di: DiseaseIntelligence) -> dict:
        return {
            "generated_at": di.generated_at.isoformat(),
            "active_outbreaks": di.active_outbreaks,
            "countries_affected": di.countries_affected,
            "risk_level": di.risk_level,
            "insights": di.insights,
            "alerts": [
                {
                    "disease": a.disease,
                    "country": a.country,
                    "country_code": a.country_code,
                    "report_date": a.report_date,
                    "status": a.status,
                    "cases": a.cases,
                    "deaths": a.deaths,
                    "source": a.source,
                    "severity": a.severity,
                    "trade_impact": a.trade_impact,
                    "supply_impact_pct": a.supply_impact_pct,
                }
                for a in di.alerts
            ],
        }


# Singleton
disease_alert_engine = DiseaseAlertEngine()
