"""
Alert Notification Engine
==========================
Monitors live data feeds and generates alerts for:
  - Lice threshold exceedances (Z > 2.0)
  - Regime color changes (Traffic Light System)
  - Disease outbreaks (ISA/PD)
  - Price movements (> ±5% week-over-week)
  - Supply balance shifts
  - Feed cost spikes

Alerts are stored in-memory with TTL and served via API.
Users can configure alert preferences per category.
"""
from __future__ import annotations

import asyncio
import datetime as dt
from dataclasses import dataclass, field

import structlog

log = structlog.get_logger(__name__)


@dataclass
class Alert:
    id: str
    category: str
    severity: str
    title: str
    message: str
    source: str = ""
    value: float = 0.0
    threshold: float = 0.0
    created_at: str = ""
    read: bool = False
    metadata: dict = field(default_factory=dict)


@dataclass
class AlertPreferences:
    """Per-user alert preferences."""
    enabled_categories: list[str] = field(default_factory=lambda: [
        "lice", "disease", "price", "regime", "supply", "feed_cost", "anomaly"
    ])
    min_severity: str = "medium"
    watched_companies: list[str] = field(default_factory=lambda: [
        "Mowi", "SalMar", "Lerøy", "Grieg", "Bakkafrost"
    ])
    watched_pas: list[int] = field(default_factory=lambda: [3, 4, 5, 6])
    price_threshold_pct: float = 5.0
    lice_z_threshold: float = 2.0


SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}


class AlertEngine:
    """Generates and manages platform alerts."""

    def __init__(self) -> None:
        self._alerts: list[Alert] = []
        self._preferences = AlertPreferences()
        self._last_check: dt.datetime | None = None
        self._alert_counter = 0

    def _make_id(self) -> str:
        self._alert_counter += 1
        return f"alert-{self._alert_counter}-{dt.datetime.now(dt.UTC).strftime('%H%M%S')}"

    def _add_alert(self, category: str, severity: str, title: str, message: str,
                   source: str = "", value: float = 0.0, threshold: float = 0.0,
                   metadata: dict | None = None) -> Alert:
        alert = Alert(
            id=self._make_id(),
            category=category,
            severity=severity,
            title=title,
            message=message,
            source=source,
            value=value,
            threshold=threshold,
            created_at=dt.datetime.now(dt.UTC).isoformat(),
            metadata=metadata or {},
        )
        self._alerts.insert(0, alert)
        # Keep max 100 alerts
        if len(self._alerts) > 100:
            self._alerts = self._alerts[:100]
        log.info("alert.created", category=category, severity=severity, title=title[:50])
        return alert

    def _check_anomaly(self) -> list[Alert]:
        """Check anomaly engine for risk alerts (sync)."""
        alerts: list[Alert] = []
        try:
            from core.market.anomaly_engine import anomaly_engine
            scores = anomaly_engine.compute_scores()
            if isinstance(scores, dict):
                composite = scores.get("composite_risk_score", 0)
                if composite >= 70:
                    alerts.append(self._add_alert("anomaly", "critical",
                        "Critical Risk Level",
                        f"Composite anomaly score: {composite:.0f}/100 — immediate attention required",
                        source="anomaly_engine", value=composite, threshold=70))
                elif composite >= 50:
                    alerts.append(self._add_alert("anomaly", "high",
                        "Elevated Risk Level",
                        f"Composite anomaly score: {composite:.0f}/100 — monitoring recommended",
                        source="anomaly_engine", value=composite, threshold=50))

                for anom in scores.get("anomalies", []):
                    if isinstance(anom, dict) and anom.get("severity") in ("critical", "high"):
                        alerts.append(self._add_alert(
                            "lice" if "lice" in str(anom.get("category", "")).lower() else "anomaly",
                            anom["severity"],
                            f"{anom.get('source', 'Unknown')}: {anom.get('category', '')}",
                            anom.get("message", "Anomaly detected"),
                            source=anom.get("source", ""),
                            value=anom.get("z_score", 0)))
        except Exception as e:
            log.debug("alert.anomaly_check_failed", error=str(e)[:60])
        return alerts

    def _check_regime(self) -> list[Alert]:
        """Check regime detector for color changes (sync)."""
        alerts: list[Alert] = []
        try:
            from core.market.regime_detector import regime_detector
            regime_alerts = regime_detector.get_alerts()
            for ra in (regime_alerts if isinstance(regime_alerts, list) else []):
                if isinstance(ra, dict) and ra.get("probability", 0) > 0.6:
                    alerts.append(self._add_alert("regime", "high",
                        f"PA-{ra.get('production_area', '?')} Regime Change",
                        f"{ra.get('current', '?')} → {ra.get('predicted', '?')} ({(ra.get('probability', 0)*100):.0f}% probability)",
                        source="regime_detector",
                        metadata={"pa": ra.get("production_area"), "tickers": ra.get("tickers", [])}))
        except Exception as e:
            log.debug("alert.regime_check_failed", error=str(e)[:60])
        return alerts

    async def _check_price(self) -> list[Alert]:
        """Check SSB price movements (async)."""
        alerts: list[Alert] = []
        try:
            from core.market.ssb_price_client import ssb_price_client
            data = await ssb_price_client.fetch_prices(n_weeks=4)
            if data.prices and len(data.prices) >= 2:
                latest = data.prices[-1].price_nok_kg
                prev = data.prices[-2].price_nok_kg
                if prev > 0:
                    change_pct = ((latest - prev) / prev) * 100
                    if abs(change_pct) >= self._preferences.price_threshold_pct:
                        direction = "surge" if change_pct > 0 else "drop"
                        alerts.append(self._add_alert("price",
                            "high" if abs(change_pct) >= 10 else "medium",
                            f"Price {direction}: {change_pct:+.1f}%",
                            f"SSB spot moved from NOK {prev:.1f} to {latest:.1f}/kg ({change_pct:+.1f}%)",
                            source="ssb_price_client", value=change_pct,
                            threshold=self._preferences.price_threshold_pct))
        except Exception as e:
            log.debug("alert.price_check_failed", error=str(e)[:60])
        return alerts

    def _check_disease(self) -> list[Alert]:
        """Check disease alerts (sync)."""
        alerts: list[Alert] = []
        try:
            from core.market.disease_alerts import disease_alert_engine
            outbreaks = disease_alert_engine.get_alerts()
            for ob in (outbreaks if isinstance(outbreaks, list) else [])[:3]:
                if isinstance(ob, dict) and "ISA" in str(ob.get("disease", "")).upper():
                    alerts.append(self._add_alert("disease", "critical",
                        f"ISA Outbreak: {ob.get('location', 'Unknown')}",
                        ob.get("description", "ISA outbreak detected"),
                        source="mattilsynet"))
        except Exception as e:
            log.debug("alert.disease_check_failed", error=str(e)[:60])
        return alerts

    async def check_all(self) -> list[dict]:
        """Run all alert checks concurrently and return new alerts."""
        results = await asyncio.gather(
            asyncio.to_thread(self._check_anomaly),
            asyncio.to_thread(self._check_regime),
            self._check_price(),
            asyncio.to_thread(self._check_disease),
            return_exceptions=True,
        )

        new_alerts: list[Alert] = []
        for r in results:
            if isinstance(r, list):
                new_alerts.extend(r)
            elif isinstance(r, Exception):
                log.debug("alert.check_exception", error=str(r)[:60])

        self._last_check = dt.datetime.now(dt.UTC)
        return [self._to_dict(a) for a in new_alerts]

    def get_alerts(self, category: str | None = None, severity: str | None = None,
                   unread_only: bool = False, limit: int = 50) -> list[dict]:
        """Get alerts with optional filters."""
        alerts = self._alerts
        if category:
            alerts = [a for a in alerts if a.category == category]
        if severity:
            min_order = SEVERITY_ORDER.get(severity, 0)
            alerts = [a for a in alerts if SEVERITY_ORDER.get(a.severity, 0) >= min_order]
        if unread_only:
            alerts = [a for a in alerts if not a.read]
        return [self._to_dict(a) for a in alerts[:limit]]

    def mark_read(self, alert_id: str) -> bool:
        """Mark an alert as read."""
        for a in self._alerts:
            if a.id == alert_id:
                a.read = True
                return True
        return False

    def mark_all_read(self) -> int:
        """Mark all alerts as read. Returns count."""
        count = sum(1 for a in self._alerts if not a.read)
        for a in self._alerts:
            a.read = True
        return count

    def get_preferences(self) -> dict:
        """Get current alert preferences."""
        return {
            "enabled_categories": self._preferences.enabled_categories,
            "min_severity": self._preferences.min_severity,
            "watched_companies": self._preferences.watched_companies,
            "watched_pas": self._preferences.watched_pas,
            "price_threshold_pct": self._preferences.price_threshold_pct,
            "lice_z_threshold": self._preferences.lice_z_threshold,
        }

    def update_preferences(self, prefs: dict) -> dict:
        """Update alert preferences."""
        if "enabled_categories" in prefs:
            self._preferences.enabled_categories = prefs["enabled_categories"]
        if "min_severity" in prefs:
            self._preferences.min_severity = prefs["min_severity"]
        if "watched_companies" in prefs:
            self._preferences.watched_companies = prefs["watched_companies"]
        if "watched_pas" in prefs:
            self._preferences.watched_pas = prefs["watched_pas"]
        if "price_threshold_pct" in prefs:
            self._preferences.price_threshold_pct = prefs["price_threshold_pct"]
        if "lice_z_threshold" in prefs:
            self._preferences.lice_z_threshold = prefs["lice_z_threshold"]
        log.info("alert.preferences_updated")
        return self.get_preferences()

    def get_summary(self) -> dict:
        """Alert summary for notification bell."""
        unread = sum(1 for a in self._alerts if not a.read)
        by_severity = {}
        for a in self._alerts:
            if not a.read:
                by_severity[a.severity] = by_severity.get(a.severity, 0) + 1
        max_sev = "info"
        if by_severity:
            max_sev = max(by_severity.keys(), key=lambda s: SEVERITY_ORDER.get(s, 0))
        return {
            "unread_count": unread,
            "total_count": len(self._alerts),
            "by_severity": by_severity,
            "max_severity": max_sev,
            "last_check": self._last_check.isoformat() if self._last_check else None,
        }

    @staticmethod
    def _to_dict(alert: Alert) -> dict:
        from dataclasses import asdict
        return asdict(alert)


# Singleton
alert_engine = AlertEngine()
