"""
Threshold Alert Engine
========================
Monitors key metrics and generates alerts when thresholds are breached.
Configurable per user via alert preferences.
"""
from __future__ import annotations
import datetime as dt
from dataclasses import dataclass, field, asdict
from typing import Optional
import structlog
from sqlalchemy import select, func
from core.models import LiceRecord, Locality

log = structlog.get_logger(__name__)


@dataclass
class Alert:
    id: str
    category: str  # lice, disease, price, supply, weather
    severity: str  # critical, high, medium, low
    title: str
    message: str
    metric_value: float
    threshold: float
    production_area: Optional[int] = None
    company: Optional[str] = None
    created_at: str = field(default_factory=lambda: dt.datetime.now(dt.UTC).isoformat())

    def to_dict(self):
        return asdict(self)


DEFAULT_THRESHOLDS = {
    "lice_critical": 0.5,      # adult female lice per fish
    "lice_warning": 0.3,
    "price_drop_pct": 10.0,    # weekly price drop percentage
    "disease_outbreak": True,   # any new ISA case
    "sst_high": 16.0,          # sea surface temperature (Celsius)
    "sst_low": 4.0,
}


class ThresholdAlertEngine:
    def __init__(self):
        self._thresholds = dict(DEFAULT_THRESHOLDS)

    async def check_all(self) -> list[Alert]:
        """Run all threshold checks and return active alerts."""
        alerts = []
        alerts.extend(await self._check_lice())
        alerts.extend(await self._check_price())
        alerts.extend(await self._check_temperature())
        # Sort by severity
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        alerts.sort(key=lambda a: severity_order.get(a.severity, 99))
        return alerts

    async def _check_lice(self) -> list[Alert]:
        """Check lice levels against thresholds."""
        alerts = []
        try:
            from core.async_db import get_async_session
            async with get_async_session() as s:
                latest = (await s.execute(
                    select(LiceRecord.year, LiceRecord.week)
                    .order_by(LiceRecord.year.desc(), LiceRecord.week.desc())
                    .limit(1)
                )).first()
                if not latest:
                    return alerts

                # Find localities above critical threshold
                critical = (await s.execute(
                    select(LiceRecord.locality_no, LiceRecord.avg_adult_female_lice, Locality.owner_company)
                    .join(Locality, Locality.locality_no == LiceRecord.locality_no, isouter=True)
                    .where(
                        LiceRecord.year == latest[0],
                        LiceRecord.week == latest[1],
                        LiceRecord.avg_adult_female_lice > self._thresholds["lice_critical"],
                    )
                    .order_by(LiceRecord.avg_adult_female_lice.desc())
                    .limit(20)
                )).fetchall()

                for row in critical:
                    alerts.append(Alert(
                        id=f"lice-{row[0]}-w{latest[1]}",
                        category="lice",
                        severity="critical" if row[1] > 1.0 else "high",
                        title=f"Lice Alert: Locality {row[0]}",
                        message=f"Adult female lice at {row[1]:.2f} (threshold: {self._thresholds['lice_critical']})",
                        metric_value=float(row[1]),
                        threshold=self._thresholds["lice_critical"],
                        company=row[2],
                    ))

                # National average check
                avg = (await s.execute(
                    select(func.avg(LiceRecord.avg_adult_female_lice))
                    .where(LiceRecord.year == latest[0], LiceRecord.week == latest[1], LiceRecord.avg_adult_female_lice.isnot(None))
                )).scalar()
                if avg and avg > self._thresholds["lice_warning"]:
                    alerts.append(Alert(
                        id=f"lice-national-w{latest[1]}",
                        category="lice",
                        severity="high",
                        title="National Lice Average Elevated",
                        message=f"National avg {avg:.3f} exceeds warning threshold {self._thresholds['lice_warning']}",
                        metric_value=float(avg),
                        threshold=self._thresholds["lice_warning"],
                    ))
        except Exception as e:
            log.error("threshold_alerts.lice_check_error", error=str(e))
        return alerts

    async def _check_price(self) -> list[Alert]:
        """Check for significant price movements."""
        alerts = []
        try:
            from core.market.ssb_price_client import ssb_price_client
            recent = await ssb_price_client.fetch_prices(n_weeks=4)
            if hasattr(recent, 'prices') and len(recent.prices) >= 2:
                prices = recent.prices
                current = prices[-1].price_nok_kg if hasattr(prices[-1], 'price_nok_kg') else prices[-1].get('price_nok_kg', 0)
                previous = prices[-2].price_nok_kg if hasattr(prices[-2], 'price_nok_kg') else prices[-2].get('price_nok_kg', 0)
                if previous > 0:
                    change_pct = ((current - previous) / previous) * 100
                    if abs(change_pct) > self._thresholds["price_drop_pct"]:
                        direction = "drop" if change_pct < 0 else "spike"
                        alerts.append(Alert(
                            id=f"price-{direction}-{dt.date.today().isoformat()}",
                            category="price",
                            severity="high" if abs(change_pct) > 15 else "medium",
                            title=f"Price {direction.title()}: {abs(change_pct):.1f}%",
                            message=f"Salmon spot price moved from {previous:.1f} to {current:.1f} NOK/kg ({change_pct:+.1f}%)",
                            metric_value=float(current),
                            threshold=self._thresholds["price_drop_pct"],
                        ))
        except Exception as e:
            log.error("threshold_alerts.price_check_error", error=str(e))
        return alerts

    async def _check_temperature(self) -> list[Alert]:
        """Check sea temperature extremes."""
        alerts = []
        try:
            from core.async_db import get_async_session
            async with get_async_session() as s:
                latest = (await s.execute(
                    select(LiceRecord.year, LiceRecord.week)
                    .order_by(LiceRecord.year.desc(), LiceRecord.week.desc())
                    .limit(1)
                )).first()
                if not latest:
                    return alerts

                extremes = (await s.execute(
                    select(LiceRecord.locality_no, LiceRecord.sea_temp_c, Locality.production_area)
                    .join(Locality, Locality.locality_no == LiceRecord.locality_no, isouter=True)
                    .where(
                        LiceRecord.year == latest[0],
                        LiceRecord.week == latest[1],
                        LiceRecord.sea_temp_c.isnot(None),
                    )
                    .where(
                        (LiceRecord.sea_temp_c > self._thresholds["sst_high"]) |
                        (LiceRecord.sea_temp_c < self._thresholds["sst_low"])
                    )
                    .limit(10)
                )).fetchall()

                for row in extremes:
                    is_high = row[1] > self._thresholds["sst_high"]
                    pa_value = row[2]
                    pa_int = None
                    if pa_value is not None:
                        try:
                            pa_int = int(str(pa_value).replace('PA-', '').replace('PA', '').strip())
                        except (ValueError, TypeError):
                            pa_int = None
                    alerts.append(Alert(
                        id=f"sst-{'high' if is_high else 'low'}-{row[0]}",
                        category="weather",
                        severity="medium",
                        title=f"SST {'High' if is_high else 'Low'}: {row[1]:.1f} C",
                        message=f"Locality {row[0]} (PA {pa_value}): sea temp {row[1]:.1f} C {'exceeds' if is_high else 'below'} threshold",
                        metric_value=float(row[1]),
                        threshold=self._thresholds["sst_high"] if is_high else self._thresholds["sst_low"],
                        production_area=pa_int,
                    ))
        except Exception as e:
            log.error("threshold_alerts.temp_check_error", error=str(e))
        return alerts

    def update_thresholds(self, updates: dict) -> dict:
        """Update threshold values."""
        for k, v in updates.items():
            if k in self._thresholds:
                self._thresholds[k] = v
        return dict(self._thresholds)

    def get_thresholds(self) -> dict:
        return dict(self._thresholds)


threshold_alert_engine = ThresholdAlertEngine()
