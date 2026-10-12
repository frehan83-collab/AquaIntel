"""
Euronext Salmon Futures Engine
================================
Fish Pool NOK salmon futures ceased end-2024. They were replaced by:
  - Euronext Cash-settled Salmon Future (ESF), EUR-denominated, traded on Euronext Paris
  - Settlement against the weekly SISALMONI spot index
  - Fish Pool Index (FPI) still published at fishpool.eu as settlement price
  - Forward prices still at fishpool.eu/forward-prices

This engine:
  1. Scrapes FPI monthly forward prices from fishpool.eu public pages
  2. Constructs a forward curve (spot + monthly forward prices 6-12 months)
  3. EUR -> NOK conversion using FRED or ECB rates
  4. Basis analysis: spot vs forward spread
  5. Term structure visualization (contango / backwardation)
  6. Fallback to SSB seasonal synthetic curve when scraping fails

Data provenance on all responses.
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from typing import Optional

import httpx
import numpy as np
import structlog

from core.market.data_provenance import DataProvenance

log = structlog.get_logger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

FISHPOOL_FORWARD_URL = "https://fishpool.eu/forward-prices/"
FISHPOOL_INDEX_URL = "https://fishpool.eu/price-information/spot-price-history/"
ECB_EURNOK_URL = "https://data.ecb.europa.eu/data-detail/EXR.D.NOK.EUR.SP00.A"
# Fallback: use FRED DEXNOUS (USD/NOK) + DEXUSEU (USD/EUR) to derive EUR/NOK
FRED_NOKUSD_URL = "https://api.stlouisfed.org/fred/series/observations"

# Reasonable EUR/NOK fallback (updated periodically)
DEFAULT_EUR_NOK = 11.50

# Circuit breaker state
_circuit_open = False
_circuit_open_until: dt.datetime | None = None
CIRCUIT_BREAK_SECONDS = 300  # 5 minutes


@dataclass
class ForwardPoint:
    """One month on the forward curve."""
    month: str  # "2026-05"
    price_eur_kg: float
    price_nok_kg: float
    months_ahead: int
    source: str  # "fishpool_forward" or "ssb_synthetic"


@dataclass
class SettlementData:
    """Latest FPI settlement info."""
    fpi_eur_kg: float
    fpi_nok_kg: float
    sisalmoni_reference: Optional[float]
    period: str
    source: str
    fetched_at: str


@dataclass
class BasisAnalysis:
    """Spot vs forward basis."""
    spot_nok_kg: float
    forward_avg_nok_kg: float
    basis_nok: float  # forward - spot
    basis_pct: float
    structure: str  # contango / backwardation / flat
    monthly_basis: list[dict]


class EuronextFuturesEngine:
    """
    Euronext salmon futures data engine.
    Scrapes Fish Pool forward prices, converts EUR->NOK, computes basis & term structure.
    Falls back to SSB-based synthetic forward curve when live data unavailable.
    """

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            timeout=20.0,
            follow_redirects=True,
            headers={
                "User-Agent": "OpenClaw-FishIntel/2.5 (aquaculture-intel)",
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        # Caches
        self._forward_cache: list[dict] | None = None
        self._forward_cache_ts: dt.datetime | None = None
        self._settlement_cache: dict | None = None
        self._settlement_cache_ts: dt.datetime | None = None
        self._eur_nok_rate: float = DEFAULT_EUR_NOK
        self._eur_nok_ts: dt.datetime | None = None
        self._cache_ttl = dt.timedelta(hours=2)
        self._fx_cache_ttl = dt.timedelta(hours=4)

    # ── EUR/NOK FX Rate ──────────────────────────────────────────────────────

    async def _fetch_eur_nok(self) -> float:
        """
        Get EUR/NOK exchange rate.
        Strategy: try to derive from FRED USD/NOK and live EUR/USD,
        or fall back to a reasonable default.
        """
        now = dt.datetime.now(dt.UTC)
        if self._eur_nok_ts and (now - self._eur_nok_ts) < self._fx_cache_ttl:
            return self._eur_nok_rate

        try:
            # Try Yahoo Finance for EURNOK=X
            resp = await self._client.get(
                "https://query1.finance.yahoo.com/v8/finance/chart/EURNOK=X",
                params={"interval": "1d", "range": "5d"},
                headers={"User-Agent": "OpenClaw-FishIntel/2.5"},
            )
            if resp.status_code == 200:
                data = resp.json()
                closes = (
                    data.get("chart", {})
                    .get("result", [{}])[0]
                    .get("indicators", {})
                    .get("quote", [{}])[0]
                    .get("close", [])
                )
                valid = [c for c in closes if c is not None and c > 0]
                if valid:
                    rate = valid[-1]
                    self._eur_nok_rate = round(rate, 4)
                    self._eur_nok_ts = now
                    log.info("euronext.fx_fetched", rate=self._eur_nok_rate, source="yahoo")
                    return self._eur_nok_rate
        except Exception as e:
            log.warning("euronext.fx_yahoo_error", error=str(e)[:80])

        # Fallback: try deriving from FRED NOK/USD if available
        try:
            from core.market.feed_cost_engine import feed_cost_engine
            nok_usd = getattr(feed_cost_engine, "_nok_usd_rate", None)
            if nok_usd and nok_usd > 0:
                # Approximate: EUR/NOK ~ NOK/USD * USD/EUR
                # USD/EUR ~ 0.92 (approximate)
                eur_nok_approx = nok_usd / 0.92
                if 9.0 < eur_nok_approx < 15.0:
                    self._eur_nok_rate = round(eur_nok_approx, 4)
                    self._eur_nok_ts = now
                    log.info("euronext.fx_derived", rate=self._eur_nok_rate, source="fred_derived")
                    return self._eur_nok_rate
        except Exception:
            pass

        log.info("euronext.fx_fallback", rate=DEFAULT_EUR_NOK)
        return DEFAULT_EUR_NOK

    # ── Circuit Breaker ───────────────────────────────────────────────────────

    def _is_circuit_open(self) -> bool:
        global _circuit_open, _circuit_open_until
        if not _circuit_open:
            return False
        if _circuit_open_until and dt.datetime.now(dt.UTC) > _circuit_open_until:
            _circuit_open = False
            _circuit_open_until = None
            log.info("euronext.circuit_closed")
            return False
        return True

    def _trip_circuit(self) -> None:
        global _circuit_open, _circuit_open_until
        _circuit_open = True
        _circuit_open_until = dt.datetime.now(dt.UTC) + dt.timedelta(seconds=CIRCUIT_BREAK_SECONDS)
        log.warning("euronext.circuit_tripped", reopen_at=_circuit_open_until.isoformat())

    # ── Fish Pool Forward Prices Scraper ──────────────────────────────────────

    async def _scrape_forward_prices(self) -> list[dict]:
        """
        Scrape Fish Pool forward prices table.
        Returns list of {month, price_eur_kg} dicts.
        Falls back to cache or empty on failure.
        """
        now = dt.datetime.now(dt.UTC)
        if (
            self._forward_cache
            and self._forward_cache_ts
            and (now - self._forward_cache_ts) < self._cache_ttl
        ):
            return self._forward_cache

        if self._is_circuit_open():
            log.info("euronext.scrape_skipped", reason="circuit_open")
            return self._forward_cache or []

        try:
            resp = await self._client.get(FISHPOOL_FORWARD_URL)
            if resp.status_code != 200:
                log.warning("euronext.scrape_failed", status=resp.status_code)
                self._trip_circuit()
                return self._forward_cache or []

            html = resp.text
            forwards = self._parse_forward_table(html)
            if forwards:
                self._forward_cache = forwards
                self._forward_cache_ts = now
                log.info("euronext.forwards_scraped", n_months=len(forwards))
            else:
                log.warning("euronext.parse_empty", url=FISHPOOL_FORWARD_URL)
                if not self._forward_cache:
                    self._trip_circuit()

            return self._forward_cache or []

        except Exception as e:
            log.warning("euronext.scrape_error", error=str(e)[:100])
            self._trip_circuit()
            return self._forward_cache or []

    def _parse_forward_table(self, html: str) -> list[dict]:
        """
        Parse forward price table from Fish Pool HTML.
        Looks for table rows with month labels and EUR prices.
        Handles various HTML table formats from fishpool.eu.
        """
        forwards = []

        # Strategy 1: Look for tabular price data with month patterns
        # Fish Pool typically shows "Month YYYY" with a price value
        month_pattern = re.compile(
            r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s\-]+(\d{4})",
            re.IGNORECASE,
        )

        # Find all numbers that look like EUR/kg prices (typically 5-15 range)
        price_pattern = re.compile(r"(\d{1,2}[.,]\d{1,2})")

        # Try to find table rows
        row_pattern = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL | re.IGNORECASE)
        cell_pattern = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.DOTALL | re.IGNORECASE)

        rows = row_pattern.findall(html)
        for row in rows:
            cells = cell_pattern.findall(row)
            cell_texts = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]

            for cell in cell_texts:
                month_match = month_pattern.search(cell)
                if month_match:
                    month_name = month_match.group(1)[:3].title()
                    year = int(month_match.group(2))

                    # Look for price in adjacent cells
                    for other_cell in cell_texts:
                        price_match = price_pattern.search(other_cell)
                        if price_match and other_cell != cell:
                            price_str = price_match.group(1).replace(",", ".")
                            price = float(price_str)
                            if 3.0 <= price <= 20.0:  # Reasonable EUR/kg range
                                month_num = {
                                    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4,
                                    "May": 5, "Jun": 6, "Jul": 7, "Aug": 8,
                                    "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
                                }.get(month_name, 0)
                                if month_num > 0:
                                    forwards.append({
                                        "month": f"{year}-{month_num:02d}",
                                        "price_eur_kg": round(price, 2),
                                    })
                                    break

        # Deduplicate and sort
        seen = set()
        unique = []
        for f in forwards:
            if f["month"] not in seen:
                seen.add(f["month"])
                unique.append(f)
        unique.sort(key=lambda x: x["month"])

        return unique

    # ── FPI Settlement Data ───────────────────────────────────────────────────

    async def _scrape_settlement(self) -> dict | None:
        """
        Scrape latest FPI settlement price from fishpool.eu.
        """
        now = dt.datetime.now(dt.UTC)
        if (
            self._settlement_cache
            and self._settlement_cache_ts
            and (now - self._settlement_cache_ts) < self._cache_ttl
        ):
            return self._settlement_cache

        if self._is_circuit_open():
            return self._settlement_cache

        try:
            resp = await self._client.get(FISHPOOL_INDEX_URL)
            if resp.status_code != 200:
                return self._settlement_cache

            html = resp.text
            # Look for FPI value — typically a prominent EUR/kg number
            fpi_pattern = re.compile(
                r"(?:FPI|Fish\s*Pool\s*Index|Settlement)[^<]*?(\d{1,2}[.,]\d{2})\s*(?:EUR|€)",
                re.IGNORECASE | re.DOTALL,
            )
            match = fpi_pattern.search(html)

            if match:
                fpi_eur = float(match.group(1).replace(",", "."))
                eur_nok = await self._fetch_eur_nok()

                self._settlement_cache = {
                    "fpi_eur_kg": round(fpi_eur, 2),
                    "fpi_nok_kg": round(fpi_eur * eur_nok, 2),
                    "eur_nok_rate": eur_nok,
                    "period": now.strftime("%Y-W%V"),
                    "source": "fishpool.eu",
                    "fetched_at": now.isoformat(),
                }
                self._settlement_cache_ts = now
                log.info("euronext.settlement_scraped", fpi_eur=fpi_eur)
            else:
                log.warning("euronext.settlement_parse_empty")

        except Exception as e:
            log.warning("euronext.settlement_error", error=str(e)[:80])

        return self._settlement_cache

    # ── Synthetic Fallback Curve (from SSB) ───────────────────────────────────

    async def _get_synthetic_curve(self, months: int = 12) -> list[dict]:
        """
        Build synthetic forward curve from SSB seasonal patterns.
        Used when Fish Pool scraping fails.
        """
        from core.market.price_feed_hub import price_feed_hub
        result = await price_feed_hub.get_forward_curve(months=months)
        if "error" in result:
            return []

        eur_nok = await self._fetch_eur_nok()
        curve = []
        for pt in result.get("curve", []):
            nok_price = pt.get("projected_nok_kg", 0)
            curve.append({
                "month": pt["month"],
                "price_eur_kg": round(nok_price / eur_nok, 2) if eur_nok > 0 else 0,
                "price_nok_kg": nok_price,
                "seasonal_factor": pt.get("seasonal_factor", 1.0),
                "source": "ssb_synthetic",
            })

        return curve

    # ── Public API Methods ────────────────────────────────────────────────────

    async def get_forward_curve(self, months: int = 12) -> dict:
        """
        Full forward curve with NOK conversion.
        Priority: Fish Pool live -> SSB synthetic fallback.
        """
        months = max(3, min(months, 24))
        eur_nok = await self._fetch_eur_nok()

        # Try live Fish Pool forwards
        raw_forwards = await self._scrape_forward_prices()
        is_live = bool(raw_forwards)

        if raw_forwards:
            curve = []
            for i, fwd in enumerate(raw_forwards[:months]):
                curve.append({
                    "month": fwd["month"],
                    "price_eur_kg": fwd["price_eur_kg"],
                    "price_nok_kg": round(fwd["price_eur_kg"] * eur_nok, 2),
                    "months_ahead": i + 1,
                    "source": "fishpool_forward",
                })
        else:
            # Fallback to synthetic
            synthetic = await self._get_synthetic_curve(months)
            curve = []
            for i, pt in enumerate(synthetic[:months]):
                curve.append({
                    "month": pt["month"],
                    "price_eur_kg": pt["price_eur_kg"],
                    "price_nok_kg": pt["price_nok_kg"],
                    "months_ahead": i + 1,
                    "source": "ssb_synthetic",
                })

        # Get current spot for reference
        from core.market.ssb_price_client import ssb_price_client
        spot_nok = await ssb_price_client.get_current_spot()
        spot_eur = round(spot_nok / eur_nok, 2) if eur_nok > 0 and spot_nok > 0 else 0

        provenance = (
            DataProvenance.live(
                "Fish Pool Forward Prices (fishpool.eu) + EUR/NOK FX",
                confidence=0.75,
            )
            if is_live
            else DataProvenance.degraded(
                "SSB Table 03024 Seasonal Synthesis",
                "Fish Pool forward prices unavailable — using SSB seasonal model",
                confidence=0.45,
            )
        )

        return {
            "spot_nok_kg": round(spot_nok, 2) if spot_nok else None,
            "spot_eur_kg": spot_eur if spot_eur else None,
            "eur_nok_rate": eur_nok,
            "is_live": is_live,
            "is_synthetic": not is_live,
            "curve": curve,
            "n_months": len(curve),
            "methodology": (
                "Scraped from Fish Pool published forward prices, converted EUR->NOK"
                if is_live
                else "Synthetic curve from SSB historical seasonal patterns applied to current spot"
            ),
            "generated_at": dt.datetime.now(dt.UTC).isoformat(),
            "data_provenance": provenance.to_dict(),
        }

    async def get_basis_analysis(self) -> dict:
        """
        Spot vs forward basis analysis.
        Positive basis = contango (forward > spot), negative = backwardation.
        """
        curve_data = await self.get_forward_curve(months=12)
        spot_nok = curve_data.get("spot_nok_kg") or 0
        curve = curve_data.get("curve", [])

        if not curve or spot_nok <= 0:
            return {
                "error": "Insufficient data for basis analysis",
                "data_provenance": DataProvenance.degraded(
                    "SSB + Fish Pool", "No curve or spot data available", confidence=0.1
                ).to_dict(),
            }

        # Compute monthly basis
        monthly_basis = []
        forward_prices = []
        for pt in curve:
            fwd = pt.get("price_nok_kg", 0)
            if fwd > 0:
                forward_prices.append(fwd)
                basis_nok = round(fwd - spot_nok, 2)
                basis_pct = round((fwd - spot_nok) / spot_nok * 100, 2) if spot_nok > 0 else 0
                monthly_basis.append({
                    "month": pt["month"],
                    "forward_nok": fwd,
                    "basis_nok": basis_nok,
                    "basis_pct": basis_pct,
                    "months_ahead": pt.get("months_ahead", 0),
                })

        forward_avg = round(float(np.mean(forward_prices)), 2) if forward_prices else 0
        overall_basis = round(forward_avg - spot_nok, 2)
        overall_basis_pct = round(overall_basis / spot_nok * 100, 2) if spot_nok > 0 else 0

        # Determine structure
        if abs(overall_basis_pct) < 1.0:
            structure = "flat"
        elif overall_basis > 0:
            structure = "contango"
        else:
            structure = "backwardation"

        is_live = curve_data.get("is_live", False)
        provenance = (
            DataProvenance.live("Fish Pool Forward Prices + SSB Spot", confidence=0.7)
            if is_live
            else DataProvenance.degraded(
                "SSB Seasonal Synthesis", "Using synthetic forward curve", confidence=0.4
            )
        )

        return {
            "spot_nok_kg": spot_nok,
            "forward_avg_nok_kg": forward_avg,
            "basis_nok": overall_basis,
            "basis_pct": overall_basis_pct,
            "structure": structure,
            "structure_description": {
                "contango": "Forward prices above spot — market expects higher future prices (normal carry cost)",
                "backwardation": "Forward prices below spot — market expects lower future prices or tight near-term supply",
                "flat": "Forward curve roughly flat — no strong directional signal",
            }.get(structure, ""),
            "monthly_basis": monthly_basis,
            "is_live": is_live,
            "generated_at": dt.datetime.now(dt.UTC).isoformat(),
            "data_provenance": provenance.to_dict(),
        }

    async def get_settlement_data(self) -> dict:
        """Latest FPI settlement data."""
        settlement = await self._scrape_settlement()

        if settlement:
            return {
                **settlement,
                "data_provenance": DataProvenance.live(
                    "Fish Pool Index (fishpool.eu)", confidence=0.7
                ).to_dict(),
            }

        # Fallback: use SSB spot as proxy
        from core.market.ssb_price_client import ssb_price_client
        spot_nok = await ssb_price_client.get_current_spot()
        eur_nok = await self._fetch_eur_nok()

        return {
            "fpi_eur_kg": round(spot_nok / eur_nok, 2) if eur_nok > 0 and spot_nok > 0 else None,
            "fpi_nok_kg": round(spot_nok, 2) if spot_nok > 0 else None,
            "eur_nok_rate": eur_nok,
            "sisalmoni_reference": None,
            "period": dt.datetime.now(dt.UTC).strftime("%Y-W%V"),
            "source": "ssb_proxy",
            "note": "FPI unavailable — using SSB weekly export price as proxy",
            "fetched_at": dt.datetime.now(dt.UTC).isoformat(),
            "data_provenance": DataProvenance.degraded(
                "SSB Table 03024 (proxy for FPI)",
                "Fish Pool settlement data unavailable",
                confidence=0.5,
            ).to_dict(),
        }

    async def get_term_structure(self) -> dict:
        """
        Contango/backwardation analysis with visualization data.
        Returns term structure slope, curvature, and monthly data for charting.
        """
        curve_data = await self.get_forward_curve(months=12)
        spot_nok = curve_data.get("spot_nok_kg") or 0
        curve = curve_data.get("curve", [])

        if len(curve) < 3 or spot_nok <= 0:
            return {
                "error": "Insufficient data for term structure analysis",
                "data_provenance": DataProvenance.degraded(
                    "SSB + Fish Pool", "Fewer than 3 forward months available", confidence=0.1
                ).to_dict(),
            }

        # Build term structure points
        nok_prices = [pt.get("price_nok_kg", 0) for pt in curve if pt.get("price_nok_kg", 0) > 0]

        if len(nok_prices) < 3:
            return {
                "error": "Insufficient valid price points",
                "data_provenance": DataProvenance.degraded(
                    "SSB + Fish Pool", "Not enough valid price points", confidence=0.1
                ).to_dict(),
            }

        # Near-term (1-3 months) vs far-term (9-12 months)
        near_term = nok_prices[:3]
        far_term = nok_prices[-3:] if len(nok_prices) >= 6 else nok_prices[-2:]
        near_avg = float(np.mean(near_term))
        far_avg = float(np.mean(far_term))

        # Slope: annualized % difference
        slope = (far_avg - near_avg) / near_avg * 100 if near_avg > 0 else 0

        # Curvature: check if curve is convex or concave
        mid_idx = len(nok_prices) // 2
        mid_price = nok_prices[mid_idx]
        linear_mid = (nok_prices[0] + nok_prices[-1]) / 2
        curvature = (mid_price - linear_mid) / linear_mid * 100 if linear_mid > 0 else 0

        # Structure classification
        if abs(slope) < 2.0:
            structure = "flat"
            signal = "neutral"
        elif slope > 0:
            structure = "contango"
            signal = "bearish_near_term" if slope > 5.0 else "mildly_bearish"
        else:
            structure = "backwardation"
            signal = "bullish_near_term" if abs(slope) > 5.0 else "mildly_bullish"

        # Term structure data for visualization
        term_points = []
        for pt in curve:
            fwd = pt.get("price_nok_kg", 0)
            if fwd > 0:
                term_points.append({
                    "month": pt["month"],
                    "price_nok_kg": fwd,
                    "premium_vs_spot_pct": round((fwd - spot_nok) / spot_nok * 100, 2)
                    if spot_nok > 0
                    else 0,
                    "months_ahead": pt.get("months_ahead", 0),
                })

        is_live = curve_data.get("is_live", False)
        provenance = (
            DataProvenance.live("Fish Pool Forwards + SSB Spot", confidence=0.7)
            if is_live
            else DataProvenance.degraded(
                "SSB Seasonal Synthesis", "Using synthetic term structure", confidence=0.4
            )
        )

        return {
            "spot_nok_kg": round(spot_nok, 2),
            "structure": structure,
            "signal": signal,
            "slope_pct": round(slope, 2),
            "curvature_pct": round(curvature, 2),
            "near_term_avg_nok": round(near_avg, 2),
            "far_term_avg_nok": round(far_avg, 2),
            "term_points": term_points,
            "interpretation": {
                "contango": "Market in contango — forwards above spot. Suggests expectation of higher future prices or normal cost-of-carry premium. Sellers may benefit from locking in forward prices.",
                "backwardation": "Market in backwardation — forwards below spot. Suggests tight near-term supply or expectation of lower future prices. Buyers may benefit from waiting.",
                "flat": "Flat term structure — minimal difference between near and far forwards. No strong directional signal from the curve.",
            }.get(structure, ""),
            "is_live": is_live,
            "generated_at": dt.datetime.now(dt.UTC).isoformat(),
            "data_provenance": provenance.to_dict(),
        }

    async def close(self) -> None:
        await self._client.aclose()


# Singleton
euronext_futures_engine = EuronextFuturesEngine()
