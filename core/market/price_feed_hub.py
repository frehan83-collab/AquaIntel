"""
Price Feed Hub — Unified Price Data Abstraction
==================================================
Priority cascade for salmon spot prices and forward curves.
Currently uses SSB as the authoritative spot source.
Synthesizes forward curves from SSB historical seasonality.

Ready for Fish Pool / LFEX / Euronext when commercial agreements are in place.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import structlog

log = structlog.get_logger(__name__)


class PriceFeedHub:
    """Singleton hub for price data from multiple sources."""

    def __init__(self) -> None:
        self._ssb_cache: dict | None = None
        self._cache_ts: dt.datetime | None = None
        self._cache_ttl = dt.timedelta(hours=1)

    async def _get_ssb_prices(self) -> list[dict]:
        """Get SSB weekly prices from the ssb_price_client."""
        now = dt.datetime.now(dt.UTC)
        if self._ssb_cache and self._cache_ts and (now - self._cache_ts) < self._cache_ttl:
            return self._ssb_cache

        try:
            from core.market.ssb_price_client import ssb_client
            data = await ssb_client.get_latest_prices(weeks=260)  # ~5 years
            self._ssb_cache = data if isinstance(data, list) else []
            self._cache_ts = now
        except Exception as e:
            log.warning("ssb_price_fetch_error", error=str(e))
            if self._ssb_cache is None:
                self._ssb_cache = []
        return self._ssb_cache

    async def get_spot_price(self, source: str = "auto") -> dict:
        """Get current spot price. Priority: Fish Pool → SSB."""
        # Fish Pool (if configured — currently no API available)
        if source in ("fishpool", "auto"):
            from config.settings import settings
            if settings.fishpool_api_key:
                log.info("fishpool_configured_but_api_dead")

        # SSB (always available)
        prices = await self._get_ssb_prices()
        if not prices:
            return {
                "source": "unavailable",
                "price_nok_kg": None,
                "error": "No price data available",
            }

        latest = prices[-1] if prices else {}
        return {
            "source": "ssb",
            "price_nok_kg": latest.get("price_nok_kg"),
            "year": latest.get("year"),
            "week": latest.get("week"),
            "volume_tonnes": latest.get("volume_tonnes"),
            "fetched_at": dt.datetime.now(dt.UTC).isoformat(),
        }

    async def get_forward_curve(self, months: int = 12) -> dict:
        """
        Synthesize forward curve from SSB spot + seasonal patterns.
        Uses historical seasonal adjustment factors computed from 5 years of SSB data.
        """
        prices = await self._get_ssb_prices()
        if len(prices) < 52:
            return {"error": "Insufficient price history for forward curve", "months": months}

        # Extract price values
        price_vals = [p.get("price_nok_kg", 0) for p in prices if p.get("price_nok_kg")]
        if not price_vals:
            return {"error": "No valid price data"}

        current_spot = price_vals[-1]

        # Compute seasonal factors from last 5 years (260 weeks)
        recent = price_vals[-260:] if len(price_vals) >= 260 else price_vals
        annual_avg = np.mean(recent)

        # Weekly seasonal factors (52 weeks → 12 monthly averages)
        weekly_avgs = []
        for w in range(52):
            week_prices = [recent[i] for i in range(w, len(recent), 52) if i < len(recent)]
            weekly_avgs.append(np.mean(week_prices) if week_prices else annual_avg)

        # Aggregate to monthly
        monthly_factors = []
        for m in range(12):
            start_week = int(m * 52 / 12)
            end_week = int((m + 1) * 52 / 12)
            month_avg = np.mean(weekly_avgs[start_week:end_week])
            monthly_factors.append(month_avg / annual_avg if annual_avg > 0 else 1.0)

        # Project forward curve
        now = dt.datetime.now(dt.UTC)
        current_month = now.month - 1  # 0-indexed

        curve = []
        for i in range(months):
            month_idx = (current_month + i) % 12
            factor = monthly_factors[month_idx]
            projected = current_spot * factor
            target_date = now + dt.timedelta(days=30 * (i + 1))

            curve.append({
                "month": target_date.strftime("%Y-%m"),
                "projected_nok_kg": round(projected, 2),
                "seasonal_factor": round(factor, 4),
                "months_ahead": i + 1,
            })

        return {
            "source": "ssb-seasonal-synthesis",
            "is_synthetic": True,
            "data_quality": "synthetic_model",
            "methodology": "Historical seasonal adjustment applied to current SSB spot",
            "current_spot_nok": round(current_spot, 2),
            "annual_average_nok": round(annual_avg, 2),
            "curve": curve,
            "generated_at": now.isoformat(),
        }

    async def list_feeds(self) -> dict:
        """List configured price data feeds and their status."""
        from config.settings import settings

        feeds = [
            {
                "name": "SSB Table 03024",
                "type": "spot",
                "status": "active",
                "frequency": "weekly",
                "auth_required": False,
                "description": "Official Norwegian salmon export prices",
            },
            {
                "name": "Fish Pool",
                "type": "futures",
                "status": "configured" if settings.fishpool_api_key else "not_configured",
                "frequency": "daily",
                "auth_required": True,
                "description": "Salmon futures (fishpool.eu API defunct since 2025)",
            },
            {
                "name": "LFEX",
                "type": "spot",
                "status": "not_configured",
                "frequency": "daily",
                "auth_required": True,
                "description": "London Fish Exchange — requires commercial agreement",
            },
            {
                "name": "Euronext ESF / Fish Pool Forward",
                "type": "futures",
                "status": "active",
                "frequency": "daily",
                "auth_required": False,
                "description": "Euronext ESF salmon futures — FPI + forward prices scraped from fishpool.eu, EUR->NOK converted",
            },
            {
                "name": "Nasdaq Salmon Index",
                "type": "spot",
                "status": "active",
                "frequency": "weekly",
                "auth_required": False,
                "description": "Nasdaq salmon spot price by weight class",
            },
        ]

        active_count = sum(1 for f in feeds if f["status"] == "active")

        return {
            "total_feeds": len(feeds),
            "active_feeds": active_count,
            "feeds": feeds,
        }

    async def feed_health(self) -> dict:
        """Health check for all configured feeds."""
        spot = await self.get_spot_price()
        ssb_ok = spot.get("price_nok_kg") is not None

        return {
            "ssb": {"healthy": ssb_ok, "last_price": spot.get("price_nok_kg")},
            "fishpool": {"healthy": False, "reason": "API defunct since 2025"},
            "lfex": {"healthy": False, "reason": "Not configured"},
            "euronext": {"healthy": False, "reason": "Not configured"},
            "overall_healthy": ssb_ok,
            "checked_at": dt.datetime.now(dt.UTC).isoformat(),
        }


# Singleton
price_feed_hub = PriceFeedHub()
