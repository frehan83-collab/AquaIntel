"""
China Demand Indicators — Norwegian Salmon Export Intelligence
================================================================
Monitors Chinese salmon import demand and Norway's competitive position.

LIVE data:
  - Norwegian exports to China: SSB table 08799 (via ssb_exports.py)
  - Norwegian spot price: SSB table 03024 (via salmon_price.py)

Structured estimates (clearly marked):
  - Total Chinese salmon imports from all origins
  - Chilean, Scottish, Faroese, Canadian export volumes to China
  - Sources and dates noted; updatable dict at top of file

All growth rates, market shares, momentum computed DYNAMICALLY from data.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import numpy as np
import structlog

log = structlog.get_logger(__name__)


# ── STRUCTURED ESTIMATES — updatable, clearly marked ─────────────────
# These are NOT live data. Update quarterly from GACC / UN Comtrade / customs.
# Norwegian data is fetched LIVE from SSB and overrides any estimate here.
CHINA_IMPORT_ESTIMATES = {
    "meta": {
        "source": "UN Comtrade + GACC (General Administration of Customs of China)",
        "last_updated": "2025-Q4",
        "notes": "Total Chinese fresh+frozen Atlantic salmon imports by origin. "
                 "Norway data overridden by live SSB at runtime.",
        "unit": "tonnes_per_year",
    },
    # Annual import estimates (tonnes) — used for non-Norwegian origins
    "total_china_imports_tonnes": {
        2022: 52_000,
        2023: 68_000,
        2024: 82_000,
        2025: 95_000,  # Projected based on H1 2025 customs data
    },
    # Per-origin annual estimates (tonnes to China)
    "origins": {
        "Chile": {2022: 18_000, 2023: 24_000, 2024: 30_000, 2025: 35_000},
        "Scotland": {2022: 4_500, 2023: 5_200, 2024: 5_800, 2025: 6_500},
        "Faroe Islands": {2022: 3_000, 2023: 3_800, 2024: 4_200, 2025: 4_800},
        "Canada": {2022: 2_000, 2023: 2_500, 2024: 3_000, 2025: 3_500},
        "Australia/Tasmania": {2022: 1_500, 2023: 1_800, 2024: 2_000, 2025: 2_200},
        # Norway is computed LIVE — not estimated here
    },
    # Monthly seasonality index (1.0 = average month)
    # Chinese demand peaks around Chinese New Year (Jan-Feb) and National Day (Oct)
    "seasonality_index": {
        1: 1.35, 2: 1.25, 3: 0.90, 4: 0.85, 5: 0.88,
        6: 0.92, 7: 0.95, 8: 0.90, 9: 1.05, 10: 1.20,
        11: 1.00, 12: 0.95,
    },
}


@dataclass
class ChinaDemandSnapshot:
    """Full snapshot of China demand indicators."""
    fetched_at: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))
    # Live from SSB
    norway_to_china_tonnes_12m: float = 0
    norway_to_china_nok_millions: float = 0
    norway_to_china_avg_price: float = 0
    norway_to_china_trend_pct: float = 0
    norway_monthly_series: list = field(default_factory=list)
    # Estimated totals
    total_china_imports_tonnes: float = 0
    norway_share_pct: float = 0
    # Supplier breakdown
    suppliers: list = field(default_factory=list)


class ChinaDemandEngine:
    """
    China salmon demand intelligence engine.
    Fetches LIVE Norwegian export data from SSB, combines with
    structured estimates for total Chinese import demand.
    """

    def __init__(self) -> None:
        self._snapshot: ChinaDemandSnapshot | None = None
        self._last_fetch: dt.datetime | None = None
        self._cache_ttl = dt.timedelta(hours=2)

    async def _ensure_ssb_data(self) -> dict:
        """Fetch live Norway-to-China export data from SSB."""
        from core.market.ssb_exports import SSBClient
        client = SSBClient()
        try:
            records = await client.get_salmon_exports(
                months=24, destinations=["CN"]
            )
            if not records:
                log.warning("china_demand.no_ssb_data")
                return {}

            # Aggregate into 12-month and 24-month windows
            now = dt.datetime.now(dt.UTC)
            cutoff_12m = now - dt.timedelta(days=365)
            cutoff_24m = now - dt.timedelta(days=730)

            recent_12m_kg = 0.0
            recent_12m_nok = 0.0
            prior_12m_kg = 0.0
            prior_12m_nok = 0.0
            monthly: dict[str, dict] = {}

            for r in records:
                rec_date = dt.datetime(r.year, r.month, 15)
                month_key = f"{r.year}-{r.month:02d}"

                if month_key not in monthly:
                    monthly[month_key] = {"kg": 0.0, "nok": 0.0}
                monthly[month_key]["kg"] += r.quantity_kg
                monthly[month_key]["nok"] += r.value_nok

                if rec_date >= cutoff_12m:
                    recent_12m_kg += r.quantity_kg
                    recent_12m_nok += r.value_nok
                elif rec_date >= cutoff_24m:
                    prior_12m_kg += r.quantity_kg
                    prior_12m_nok += r.value_nok

            # Trend: YoY growth
            trend_pct = 0.0
            if prior_12m_kg > 0:
                trend_pct = (recent_12m_kg - prior_12m_kg) / prior_12m_kg * 100

            avg_price = recent_12m_nok / max(recent_12m_kg, 1)

            series = [
                {
                    "month": k,
                    "tonnes": round(v["kg"] / 1000, 1),
                    "value_mnok": round(v["nok"] / 1_000_000, 1),
                }
                for k, v in sorted(monthly.items())
            ]

            return {
                "tonnes_12m": round(recent_12m_kg / 1000, 0),
                "nok_millions_12m": round(recent_12m_nok / 1_000_000, 1),
                "avg_price_nok_kg": round(avg_price, 1),
                "trend_pct": round(trend_pct, 1),
                "prior_12m_tonnes": round(prior_12m_kg / 1000, 0),
                "monthly_series": series,
            }
        except Exception as e:
            log.warning("china_demand.ssb_error", error=str(e)[:100])
            return {}
        finally:
            await client.close()

    def _get_latest_estimate_year(self) -> int:
        """Return the most recent year in CHINA_IMPORT_ESTIMATES."""
        years = list(CHINA_IMPORT_ESTIMATES["total_china_imports_tonnes"].keys())
        return max(years) if years else 2024

    def _compute_total_imports(self, year: int) -> float:
        """Get total Chinese imports for a given year from estimates."""
        totals = CHINA_IMPORT_ESTIMATES["total_china_imports_tonnes"]
        if year in totals:
            return float(totals[year])
        # Extrapolate from last two years
        years = sorted(totals.keys())
        if len(years) >= 2:
            y1, y2 = years[-2], years[-1]
            growth = (totals[y2] - totals[y1]) / max(totals[y1], 1)
            return totals[y2] * (1 + growth) * (1 + growth * (year - y2))
        return float(totals.get(years[-1], 80_000)) if years else 80_000

    async def get_snapshot(self) -> dict:
        """
        Full China demand snapshot.
        LIVE Norwegian exports from SSB + structured estimates for total market.
        """
        now = dt.datetime.now(dt.UTC)
        if (
            self._last_fetch
            and (now - self._last_fetch) < self._cache_ttl
            and self._snapshot
        ):
            return self._format_snapshot(self._snapshot)

        ssb = await self._ensure_ssb_data()
        est_year = self._get_latest_estimate_year()
        total_imports = self._compute_total_imports(est_year)

        norway_tonnes = ssb.get("tonnes_12m", 0)
        norway_share = (norway_tonnes / max(total_imports, 1)) * 100 if total_imports > 0 else 0
        norway_live = bool(ssb.get("monthly_series"))

        snap = ChinaDemandSnapshot(
            norway_to_china_tonnes_12m=norway_tonnes,
            norway_to_china_nok_millions=ssb.get("nok_millions_12m", 0),
            norway_to_china_avg_price=ssb.get("avg_price_nok_kg", 0),
            norway_to_china_trend_pct=ssb.get("trend_pct", 0),
            norway_monthly_series=ssb.get("monthly_series", []),
            total_china_imports_tonnes=total_imports,
            norway_share_pct=round(norway_share, 1),
            suppliers=self._build_supplier_breakdown(
                norway_tonnes, est_year, total_imports, norway_live=norway_live
            ),
        )

        self._snapshot = snap
        self._last_fetch = now
        log.info("china_demand.snapshot", norway_t=norway_tonnes, total_t=total_imports)
        return self._format_snapshot(snap)

    def _build_supplier_breakdown(
        self, norway_tonnes: float, est_year: int, total_imports: float,
        norway_live: bool = True,
    ) -> list[dict]:
        """Build origin breakdown with Norway LIVE + others estimated.

        `norway_live=False` (SSB returned no records) downgrades the Norway
        entry to an estimate — never claim LIVE over missing data.
        """
        origins = CHINA_IMPORT_ESTIMATES["origins"]
        suppliers = []

        # Norway — LIVE from SSB (or estimate when the series is unavailable)
        suppliers.append({
            "origin": "Norway",
            "flag": "NO",
            "tonnes": norway_tonnes,
            "share_pct": round((norway_tonnes / max(total_imports, 1)) * 100, 1),
            "data_source": (
                "LIVE (SSB table 08799)" if norway_live
                else "Estimate (SSB 08799 returned no records)"
            ),
            "is_live": norway_live,
        })

        # Other origins — from estimates
        for origin, yearly in origins.items():
            tonnes = float(yearly.get(est_year, yearly.get(max(yearly.keys()), 0)))
            # Compute YoY growth from estimates
            years = sorted(yearly.keys())
            yoy = 0.0
            if len(years) >= 2:
                prev = yearly[years[-2]]
                curr = yearly[years[-1]]
                yoy = ((curr - prev) / max(prev, 1)) * 100

            suppliers.append({
                "origin": origin,
                "flag": self._origin_to_flag(origin),
                "tonnes": tonnes,
                "share_pct": round((tonnes / max(total_imports, 1)) * 100, 1),
                "yoy_growth_pct": round(yoy, 1),
                "data_source": f"Estimate ({CHINA_IMPORT_ESTIMATES['meta']['source']}, {CHINA_IMPORT_ESTIMATES['meta']['last_updated']})",
                "is_live": False,
            })

        # Sort by volume descending
        suppliers.sort(key=lambda s: s["tonnes"], reverse=True)
        return suppliers

    @staticmethod
    def _origin_to_flag(origin: str) -> str:
        flags = {
            "Chile": "CL", "Scotland": "GB", "Faroe Islands": "FO",
            "Canada": "CA", "Australia/Tasmania": "AU", "Norway": "NO",
        }
        return flags.get(origin, "??")

    def _format_snapshot(self, snap: ChinaDemandSnapshot) -> dict:
        # Liveness signal: records actually returned (not a rounded value).
        norway_live = bool(snap.norway_monthly_series)
        return {
            "source": (
                "SSB table 08799 (Norway LIVE) + GACC/Comtrade estimates"
                if norway_live
                else "GACC/Comtrade estimates (SSB table 08799 unavailable)"
            ),
            "fetched_at": snap.fetched_at.isoformat(),
            "norway_exports_to_china": {
                "tonnes_12m": snap.norway_to_china_tonnes_12m,
                "nok_millions_12m": snap.norway_to_china_nok_millions,
                "avg_price_nok_kg": snap.norway_to_china_avg_price,
                "yoy_trend_pct": snap.norway_to_china_trend_pct,
                "data_source": (
                    "LIVE — SSB table 08799" if norway_live
                    else "Unavailable — SSB 08799 returned no records"
                ),
            },
            "china_total_imports": {
                "tonnes_annual": snap.total_china_imports_tonnes,
                "estimate_year": self._get_latest_estimate_year(),
                "data_source": f"Estimate ({CHINA_IMPORT_ESTIMATES['meta']['source']})",
            },
            "norway_share_pct": snap.norway_share_pct,
            "suppliers": snap.suppliers,
            "monthly_series": snap.norway_monthly_series,
        }

    async def get_demand_signals(self) -> dict:
        """
        Momentum indicators computed DYNAMICALLY:
        - YoY growth rate (from SSB)
        - Acceleration (change in growth rate)
        - Seasonal pattern (current month vs average)
        - Demand signal (composite)
        """
        snap = await self.get_snapshot()
        norway_data = snap.get("norway_exports_to_china", {})
        series = snap.get("monthly_series", [])

        yoy_growth = norway_data.get("yoy_trend_pct", 0)

        # Compute acceleration from monthly series
        acceleration = 0.0
        if len(series) >= 6:
            recent_3m = sum(p["tonnes"] for p in series[-3:])
            prior_3m = sum(p["tonnes"] for p in series[-6:-3])
            if prior_3m > 0:
                recent_growth = (recent_3m - prior_3m) / prior_3m * 100
                # Compare to overall YoY
                acceleration = recent_growth - yoy_growth

        # Seasonal index for current month
        current_month = dt.datetime.now(dt.UTC).month
        seasonal_idx = CHINA_IMPORT_ESTIMATES["seasonality_index"].get(current_month, 1.0)

        # Total market growth from estimates
        est = CHINA_IMPORT_ESTIMATES["total_china_imports_tonnes"]
        years = sorted(est.keys())
        market_growth_pct = 0.0
        if len(years) >= 2:
            prev_yr = est[years[-2]]
            curr_yr = est[years[-1]]
            market_growth_pct = ((curr_yr - prev_yr) / max(prev_yr, 1)) * 100

        # Composite demand signal
        # Weighted: 40% YoY growth, 25% acceleration, 20% seasonal, 15% market growth
        signal_score = (
            0.40 * min(max(yoy_growth / 30, -1), 1)    # normalize to [-1, 1]
            + 0.25 * min(max(acceleration / 20, -1), 1)
            + 0.20 * (seasonal_idx - 1.0) * 2           # seasonal deviation
            + 0.15 * min(max(market_growth_pct / 20, -1), 1)
        )

        if signal_score > 0.3:
            signal_label = "Strong Demand"
            signal_direction = "bullish"
        elif signal_score > 0.1:
            signal_label = "Growing Demand"
            signal_direction = "moderately_bullish"
        elif signal_score > -0.1:
            signal_label = "Stable Demand"
            signal_direction = "neutral"
        elif signal_score > -0.3:
            signal_label = "Weakening Demand"
            signal_direction = "moderately_bearish"
        else:
            signal_label = "Declining Demand"
            signal_direction = "bearish"

        # Build momentum chart data from series
        momentum_chart = []
        for i, point in enumerate(series):
            if i >= 3:
                rolling_3m = sum(p["tonnes"] for p in series[i - 2:i + 1])
                momentum_chart.append({
                    "month": point["month"],
                    "rolling_3m_tonnes": round(rolling_3m, 0),
                    "monthly_tonnes": point["tonnes"],
                })

        return {
            "yoy_growth_pct": round(yoy_growth, 1),
            "acceleration_pct": round(acceleration, 1),
            "seasonal_index": seasonal_idx,
            "seasonal_label": self._seasonal_label(current_month),
            "market_growth_pct": round(market_growth_pct, 1),
            "signal_score": round(signal_score, 3),
            "signal_label": signal_label,
            "signal_direction": signal_direction,
            "momentum_chart": momentum_chart,
            "insights": self._generate_insights(yoy_growth, acceleration, seasonal_idx, market_growth_pct),
        }

    @staticmethod
    def _seasonal_label(month: int) -> str:
        labels = {
            1: "Chinese New Year peak",
            2: "Post-CNY elevated",
            3: "Spring slowdown",
            4: "Spring low season",
            5: "Pre-summer recovery",
            6: "Summer base",
            7: "Mid-year steady",
            8: "Late summer low",
            9: "Golden Week buildup",
            10: "National Day peak",
            11: "Post-holiday normalization",
            12: "Year-end steady",
        }
        return labels.get(month, "")

    @staticmethod
    def _generate_insights(
        yoy: float, accel: float, seasonal: float, market: float,
    ) -> list[str]:
        insights = []
        if yoy > 15:
            insights.append(f"Norwegian exports to China growing strongly at {yoy:+.1f}% YoY")
        elif yoy > 0:
            insights.append(f"Norwegian exports to China up {yoy:+.1f}% YoY")
        elif yoy < -10:
            insights.append(f"Warning: Norwegian exports to China declining {yoy:+.1f}% YoY")

        if accel > 5:
            insights.append("Growth is accelerating — recent months outpacing annual trend")
        elif accel < -5:
            insights.append("Growth is decelerating — recent momentum weakening")

        if seasonal > 1.15:
            insights.append("Currently in high-demand season for Chinese market")
        elif seasonal < 0.90:
            insights.append("Low season for Chinese salmon demand")

        if market > 10:
            insights.append(f"Total Chinese salmon market expanding rapidly ({market:.0f}% YoY)")

        if not insights:
            insights.append("China demand indicators are within normal ranges")

        return insights

    async def get_supply_impact(self) -> dict:
        """
        How China demand growth correlates with Norwegian spot price.
        Uses LIVE SSB price data + export volume data.
        """
        snap = await self.get_snapshot()
        signals = await self.get_demand_signals()
        series = snap.get("monthly_series", [])

        # Get SSB price data for correlation
        price_data = await self._get_ssb_prices()

        # Simple correlation: when China volumes rise, does price follow?
        correlation = 0.0
        if series and price_data:
            # Match price months to volume months
            price_months = {p["month"]: p["price"] for p in price_data}
            matched_prices = []
            matched_vols = []
            for point in series[-12:]:
                month = point["month"]
                if month in price_months:
                    matched_vols.append(point["tonnes"])
                    matched_prices.append(price_months[month])

            if len(matched_vols) >= 4:
                try:
                    vols = np.array(matched_vols, dtype=float)
                    prices = np.array(matched_prices, dtype=float)
                    if np.std(vols) > 0 and np.std(prices) > 0:
                        correlation = float(np.corrcoef(vols, prices)[0, 1])
                except Exception:
                    pass

        yoy = signals.get("yoy_growth_pct", 0)
        signal_dir = signals.get("signal_direction", "neutral")

        # Estimate price impact
        # Theory: 10% increase in China demand -> ~1-2% spot price uplift
        # (China is ~5-8% of Norwegian exports, so partial effect)
        price_sensitivity = 0.15  # 15% of demand growth transmits to price
        estimated_price_impact_pct = round(yoy * price_sensitivity, 1)

        if estimated_price_impact_pct > 2:
            impact_label = "Significant Upward Pressure"
        elif estimated_price_impact_pct > 0.5:
            impact_label = "Mild Upward Pressure"
        elif estimated_price_impact_pct > -0.5:
            impact_label = "Neutral Impact"
        elif estimated_price_impact_pct > -2:
            impact_label = "Mild Downward Pressure"
        else:
            impact_label = "Significant Downward Pressure"

        return {
            "correlation_vol_price": round(correlation, 3),
            "estimated_price_impact_pct": estimated_price_impact_pct,
            "impact_label": impact_label,
            "demand_direction": signal_dir,
            "yoy_growth_pct": round(yoy, 1),
            "china_share_of_norway_exports": snap.get("norway_share_pct", 0),
            "transmission_mechanism": (
                "China accounts for ~5-8% of Norwegian salmon exports. "
                "Demand growth in China creates incremental upward pressure on the global price, "
                "amplified during peak seasons (CNY, Golden Week)."
            ),
            "assessment": self._build_assessment(yoy, correlation, signal_dir),
        }

    @staticmethod
    def _build_assessment(yoy: float, corr: float, direction: str) -> str:
        parts = []
        if yoy > 10:
            parts.append(f"Chinese demand for Norwegian salmon is growing robustly ({yoy:+.1f}% YoY)")
        elif yoy > 0:
            parts.append(f"Chinese demand is positive ({yoy:+.1f}% YoY)")
        else:
            parts.append(f"Chinese demand is contracting ({yoy:+.1f}% YoY)")

        if abs(corr) > 0.5:
            parts.append(f"with {'strong' if abs(corr) > 0.7 else 'moderate'} "
                         f"price correlation ({corr:+.2f})")
        else:
            parts.append(f"though price correlation is weak ({corr:+.2f})")

        if direction in ("bullish", "moderately_bullish"):
            parts.append("— net bullish for Norwegian spot price")
        elif direction in ("bearish", "moderately_bearish"):
            parts.append("— net bearish pressure")
        else:
            parts.append("— neutral near-term impact")

        return ". ".join(parts) + "."

    async def _get_ssb_prices(self) -> list[dict]:
        """Fetch SSB salmon spot prices, aggregate to monthly."""
        try:
            from core.market.salmon_price import SalmonPriceClient
            client = SalmonPriceClient()
            weekly = await client.fetch_ssb_prices(weeks=52)
            if not weekly:
                return []

            # Group by month
            monthly: dict[str, list[float]] = {}
            for w in weekly:
                month_key = f"{w.date.year}-{w.date.month:02d}"
                if month_key not in monthly:
                    monthly[month_key] = []
                monthly[month_key].append(w.price_nok_kg)

            return [
                {"month": k, "price": round(np.mean(v), 1)}
                for k, v in sorted(monthly.items())
            ]
        except Exception as e:
            log.warning("china_demand.price_fetch_error", error=str(e)[:80])
            return []

    async def get_top_suppliers(self) -> dict:
        """Origin breakdown — Norway LIVE, others estimated."""
        snap = await self.get_snapshot()
        return {
            "suppliers": snap.get("suppliers", []),
            "total_china_imports_tonnes": snap.get("china_total_imports", {}).get("tonnes_annual", 0),
            "estimate_year": self._get_latest_estimate_year(),
            "notes": (
                "Norway data is LIVE from SSB table 08799. "
                "All other origins are structured estimates from "
                f"{CHINA_IMPORT_ESTIMATES['meta']['source']}, "
                f"last updated {CHINA_IMPORT_ESTIMATES['meta']['last_updated']}."
            ),
        }


# Singleton
china_demand_engine = ChinaDemandEngine()
