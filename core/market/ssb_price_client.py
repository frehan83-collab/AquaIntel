"""
SSB Salmon Price Client — Real Price Data
============================================
Fetches actual weekly salmon export prices from Statistics Norway (SSB)
Table 03024: "Export of farm-bred salmon"

This is the REAL price used by the entire Norwegian salmon industry.
Data goes back to year 2000, updated weekly.

Source: https://data.ssb.no/api/v0/en/table/03024/
License: Open data (CC BY 4.0)
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
import structlog

log = structlog.get_logger(__name__)

SSB_API_URL = "https://data.ssb.no/api/v0/en/table/03024/"


@dataclass
class SalmonPriceWeek:
    """One week of real SSB salmon export price."""
    year: int
    week: int
    price_nok_kg: float
    volume_tonnes: float = 0.0
    source: str = "ssb_03024"


@dataclass
class SSBPriceData:
    """Collection of SSB price data with metadata."""
    prices: list[SalmonPriceWeek] = field(default_factory=list)
    fetched_at: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))
    latest_price: float = 0.0
    latest_week: str = ""
    n_weeks: int = 0


class SSBPriceClient:
    """
    Fetches real salmon prices from SSB API (Statistics Norway).

    No API key required — fully public data.
    """

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=30.0)
        self._cache: SSBPriceData | None = None
        self._cache_time: dt.datetime | None = None
        self._cache_ttl = dt.timedelta(hours=6)  # SSB updates weekly

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30), reraise=True)
    async def _fetch_remote(self, n_weeks: int) -> list[SalmonPriceWeek]:
        """Fetch + parse one SSB 03024 response.

        Retries transient failures (network errors, 5xx) with exponential
        backoff, matching the BarentsWatch client pattern.
        """
        query = {
            "query": [
                {
                    "code": "VareGrupper2",
                    "selection": {
                        "filter": "item",
                        "values": ["01"],  # Fresh salmon
                    },
                },
                {
                    "code": "ContentsCode",
                    "selection": {
                        "filter": "item",
                        "values": ["Kilopris", "Vekt"],  # Price + Volume
                    },
                },
                {
                    "code": "Tid",
                    "selection": {
                        # "top" always returns the last N available weeks,
                        # avoiding 400 errors when SSB hasn't published the
                        # current week yet (typically 1-2 week reporting lag).
                        "filter": "top",
                        "values": [str(n_weeks)],
                    },
                },
            ],
            "response": {"format": "json-stat2"},
        }

        resp = await self._client.post(
            SSB_API_URL,
            json=query,
            headers={"Content-Type": "application/json"},
        )
        if resp.status_code != 200:
            raise RuntimeError(f"ssb_http_{resp.status_code}")
        return self._parse_response(resp.json())

    async def fetch_prices(self, n_weeks: int = 52) -> SSBPriceData:
        """
        Fetch the last n_weeks of salmon export prices from SSB.
        Returns real NOK/kg prices.
        """
        now = dt.datetime.now(dt.UTC)

        # Use cache if fresh
        if (
            self._cache
            and self._cache_time
            and (now - self._cache_time) < self._cache_ttl
        ):
            return self._cache

        try:
            prices = await self._fetch_remote(n_weeks)

            result = SSBPriceData(
                prices=prices,
                n_weeks=len(prices),
            )

            if prices:
                result.latest_price = prices[-1].price_nok_kg
                result.latest_week = f"{prices[-1].year}W{prices[-1].week:02d}"

            self._cache = result
            self._cache_time = now

            log.info(
                "ssb_price.fetched",
                n_weeks=len(prices),
                latest=result.latest_price,
                latest_week=result.latest_week,
            )
            return result

        except Exception as e:
            log.warning("ssb_price.fetch_failed", error=str(e)[:100])

        # Serve-stale: an old real price beats an empty one.
        if self._cache is not None:
            log.warning(
                "ssb_price.serving_stale",
                age_hours=round((now - (self._cache_time or now)).total_seconds() / 3600, 1),
                latest=self._cache.latest_price,
            )
            return self._cache
        return SSBPriceData()

    async def get_current_spot(self) -> float:
        """Get the latest weekly salmon price (NOK/kg)."""
        data = await self.fetch_prices(n_weeks=8)
        return data.latest_price if data.latest_price > 0 else 0.0

    async def get_price_history(self, n_weeks: int = 52) -> list[dict]:
        """Get price history as list of dicts for charts."""
        data = await self.fetch_prices(n_weeks=n_weeks)
        return [
            {
                "week": f"W{p.week}",
                "year": p.year,
                "price_nok": p.price_nok_kg,
                "volume_tonnes": p.volume_tonnes,
                "label": f"{p.year}W{p.week}",
            }
            for p in data.prices
        ]

    def _build_week_codes(self, n_weeks: int) -> list[str]:
        """Build SSB week codes like '2025U13' for the last n weeks."""
        now = dt.datetime.now(dt.UTC)
        _, current_week, _ = now.isocalendar()
        current_year = now.year

        codes = []
        for i in range(n_weeks, 0, -1):
            w = current_week - i
            y = current_year
            while w < 1:
                w += 52
                y -= 1
            codes.append(f"{y}U{w:02d}")

        return codes

    def _parse_response(self, data: dict) -> list[SalmonPriceWeek]:
        """
        Parse SSB JSON-stat2 response into price records.

        SSB layout for size=[1, 2, 3] (1 commodity x 2 contents x N weeks):
          values = [Vekt_W1, Vekt_W2, ..., Vekt_WN, Kilopris_W1, ..., Kilopris_WN]
          i.e. all values for first content type, then all for second.
        """
        prices_by_week: dict[str, dict] = {}

        try:
            dimension = data.get("dimension", {})
            time_labels = list(
                dimension.get("Tid", {}).get("category", {}).get("label", {}).keys()
            )
            contents_keys = list(
                dimension.get("ContentsCode", {}).get("category", {}).get("label", {}).keys()
            )
            values = data.get("value", [])
            sizes = data.get("size", [])

            if not values or not time_labels:
                return []

            n_commodities = sizes[0] if len(sizes) > 0 else 1
            n_contents = sizes[1] if len(sizes) > 1 else 1
            n_times = sizes[2] if len(sizes) > 2 else len(time_labels)

            # Layout: values[commodity_idx * n_contents * n_times + content_idx * n_times + time_idx]
            for t_idx, t_code in enumerate(time_labels):
                year, week = self._parse_week_code(t_code)
                if year == 0:
                    continue

                week_key = f"{year}W{week:02d}"
                prices_by_week[week_key] = {
                    "year": year, "week": week, "price": 0.0, "volume": 0.0,
                }

                for c_idx, c_key in enumerate(contents_keys):
                    val_idx = c_idx * n_times + t_idx  # content-major order
                    if val_idx < len(values) and values[val_idx] is not None:
                        val = float(values[val_idx])
                        if "Kilopris" in c_key or "pris" in c_key.lower():
                            prices_by_week[week_key]["price"] = val
                        elif "Vekt" in c_key or "vekt" in c_key.lower():
                            prices_by_week[week_key]["volume"] = val

        except Exception as e:
            log.warning("ssb_price.parse_error", error=str(e)[:100])

        # Convert to sorted list
        result = []
        for week_key in sorted(prices_by_week.keys()):
            d = prices_by_week[week_key]
            if d["price"] > 0:
                result.append(SalmonPriceWeek(
                    year=d["year"],
                    week=d["week"],
                    price_nok_kg=round(d["price"], 2),
                    volume_tonnes=round(d["volume"], 1),
                ))

        return result

    @staticmethod
    def _parse_week_code(code: str) -> tuple[int, int]:
        """Parse '2025U13' into (2025, 13)."""
        try:
            if "U" in code:
                parts = code.split("U")
                return int(parts[0]), int(parts[1])
            elif "W" in code:
                parts = code.split("W")
                return int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            pass
        return 0, 0

    # ── Bulk historical fetch (6+ years) ────────────────────────

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30), reraise=True)
    async def _fetch_all_history(self, start_year: int) -> list[SalmonPriceWeek]:
        """Fetch the full 03024 series in ONE request, filter client-side.

        The SSB ``fromTo`` time filter is unreliable for this table (returns
        1-2 rows per request — it silently starved bulk history to 14 weeks
        instead of ~350 before2026-10). ``filter:all`` returns the complete
        series and is the validated path since
        scripts/fetch_historical_ssb_prices.py and the price backtest.
        """
        query = {
            "query": [
                {"code": "VareGrupper2", "selection": {"filter": "item", "values": ["01"]}},
                {"code": "ContentsCode", "selection": {"filter": "item", "values": ["Kilopris", "Vekt"]}},
                {"code": "Tid", "selection": {"filter": "all", "values": ["*"]}},
            ],
            "response": {"format": "json-stat2"},
        }
        resp = await self._client.post(
            SSB_API_URL, json=query,
            headers={"Content-Type": "application/json"},
        )
        if resp.status_code != 200:
            raise RuntimeError(f"ssb_http_{resp.status_code}")
        return [p for p in self._parse_response(resp.json()) if p.year >= start_year]

    async def fetch_bulk_history(self, start_year: int = 2020) -> SSBPriceData:
        """
        Fetch multi-year weekly price history from SSB.
        Single filter:all request (see _fetch_all_history).
        Caches for 24 hours (data only updates weekly).
        """
        now = dt.datetime.now(dt.UTC)
        if (
            self._bulk_cache
            and self._bulk_cache_time
            and (now - self._bulk_cache_time) < dt.timedelta(hours=24)
        ):
            return self._bulk_cache

        all_prices: list[SalmonPriceWeek] = []
        current_year = now.year

        try:
            all_prices = await self._fetch_all_history(start_year)
        except Exception as e:
            log.warning("ssb_price.bulk_fetch_failed", error=str(e)[:100])
            if self._bulk_cache is not None:
                log.warning(
                    "ssb_price.bulk_serving_stale",
                    n_weeks=self._bulk_cache.n_weeks,
                    age_hours=round((now - (self._bulk_cache_time or now)).total_seconds() / 3600, 1),
                )
                return self._bulk_cache
            return SSBPriceData()

        # Sort chronologically
        all_prices.sort(key=lambda p: (p.year, p.week))

        if not all_prices:
            log.warning("ssb_price.bulk_empty", start_year=start_year)

        result = SSBPriceData(
            prices=all_prices,
            n_weeks=len(all_prices),
        )
        if all_prices:
            result.latest_price = all_prices[-1].price_nok_kg
            result.latest_week = f"{all_prices[-1].year}W{all_prices[-1].week}"

        self._bulk_cache = result
        self._bulk_cache_time = now

        log.info("ssb_price.bulk_done", total_weeks=len(all_prices), years=f"{start_year}-{current_year}")
        return result

    # ── Seasonal pattern computation ──────────────────────────

    @staticmethod
    def compute_seasonal_pattern(prices: list[SalmonPriceWeek]) -> dict[int, float]:
        """
        Compute median price per ISO week from multi-year data.
        Returns {week_number: median_nok_kg} for weeks 1-52.
        This replaces the hardcoded SEASONAL_PATTERN.
        """
        import numpy as np
        from collections import defaultdict

        by_week: dict[int, list[float]] = defaultdict(list)
        for p in prices:
            if 1 <= p.week <= 52 and p.price_nok_kg > 0:
                by_week[p.week].append(p.price_nok_kg)

        pattern = {}
        for week in range(1, 53):
            vals = by_week.get(week, [])
            if vals:
                pattern[week] = round(float(np.median(vals)), 1)
            else:
                # Interpolate from neighbors
                prev = pattern.get(week - 1, 75)
                pattern[week] = prev

        return pattern

    # ── Export volume trend ────────────────────────────────────

    @staticmethod
    def compute_export_volume_trend(
        prices: list[SalmonPriceWeek], lookback_weeks: int = 13
    ) -> float:
        """
        Compute % change in total export volume (tonnes):
          recent 13 weeks vs prior 13 weeks.
        Returns signed float (e.g. +3.2 or -1.8).
        """
        if len(prices) < lookback_weeks * 2:
            return 0.0

        recent = prices[-lookback_weeks:]
        prior = prices[-lookback_weeks * 2:-lookback_weeks]

        recent_vol = sum(p.volume_tonnes for p in recent)
        prior_vol = sum(p.volume_tonnes for p in prior)

        if prior_vol <= 0:
            return 0.0

        trend = (recent_vol - prior_vol) / prior_vol * 100
        return round(trend, 1)

    # ── Single-week price lookup ──────────────────────────────

    async def get_price_for_week(self, year: int, week: int) -> float | None:
        """Look up actual SSB price for a specific year/week. For model validation."""
        bulk = await self.fetch_bulk_history()
        for p in bulk.prices:
            if p.year == year and p.week == week:
                return p.price_nok_kg
        return None

    # ── DB persistence ────────────────────────────────────────

    async def persist_to_db(self, prices: list[SalmonPriceWeek] | None = None) -> int:
        """Store SSB prices in the database for offline access and retraining."""
        if prices is None:
            bulk = await self.fetch_bulk_history()
            prices = bulk.prices

        from core.models import SSBWeeklyPrice
        from core.async_db import get_async_session
        stored = 0
        async with get_async_session() as s:
            for p in prices:
                from sqlalchemy import select
                existing = (await s.execute(
                    select(SSBWeeklyPrice).where(
                        SSBWeeklyPrice.year == p.year,
                        SSBWeeklyPrice.week == p.week,
                    )
                )).scalar_one_or_none()
                if not existing:
                    s.add(SSBWeeklyPrice(
                        year=p.year,
                        week=p.week,
                        price_nok_kg=p.price_nok_kg,
                        volume_tonnes=p.volume_tonnes,
                    ))
                    stored += 1

        if stored > 0:
            log.info("ssb_price.persisted", new_records=stored)
        return stored

    async def close(self) -> None:
        await self._client.aclose()


# Add bulk cache fields to __init__
_original_init = SSBPriceClient.__init__


def _patched_init(self) -> None:
    _original_init(self)
    self._bulk_cache: SSBPriceData | None = None
    self._bulk_cache_time: dt.datetime | None = None


SSBPriceClient.__init__ = _patched_init  # type: ignore

# Singleton
ssb_price_client = SSBPriceClient()
