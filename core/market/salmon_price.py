"""
Salmon Price Intelligence
==========================
1. Nasdaq Salmon Index scraper (weekly spot price by weight class)
2. Fish Pool forward curve (historical settled FPI)
3. Lice-to-Price prediction model
4. Seasonal anomaly detector
5. Supply-driven price forecaster
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import numpy as np
import httpx
import structlog

log = structlog.get_logger(__name__)


@dataclass
class SalmonPricePoint:
    date: dt.date
    price_nok_kg: float
    weight_class: str = "superior"  # or "2-3", "3-4", "4-5", "5-6", "6-7", "7+"
    source: str = "nasdaq"


@dataclass
class PriceForecast:
    generated_at: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))
    horizon_weeks: int = 4
    current_spot: float = 0.0
    predicted_price: float = 0.0
    direction: str = "neutral"  # bullish / neutral / bearish
    confidence: float = 0.0
    price_lo80: float = 0.0
    price_hi80: float = 0.0

    # Drivers
    lice_signal: str = ""
    supply_signal: str = ""
    seasonal_signal: str = ""
    combined_signal: str = ""

    rationale: str = ""


# ── Seasonal pattern — shared with price_ml.py (SSB-updated at runtime) ──
from core.market.price_ml import SEASONAL_PATTERN  # noqa: E402

# ── Lice-to-price elasticity (estimated from historical data) ────────
# When national avg lice increases by 0.1, price moves by this % over N weeks
LICE_PRICE_RESPONSE = {
    2: -1.5,   # week 2: initial harvest acceleration → price dip
    4: -0.5,   # week 4: supply normalizing
    6: +2.0,   # week 6: supply shortage emerging → price rise
    8: +3.5,   # week 8: full supply impact → significant price rise
    10: +2.5,  # week 10: starting to fade
    12: +1.0,  # week 12: mostly absorbed
}


class SalmonPriceEngine:
    """Salmon price intelligence and prediction."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=30.0)
        self.price_history: list[SalmonPricePoint] = []
        self.latest_spot: float = 0.0

    async def fetch_nasdaq_index(self) -> list[SalmonPricePoint]:
        """
        Fetch Nasdaq Salmon Index (weekly spot prices).
        Scrapes from the public price page.
        """
        try:
            resp = await self._client.get(
                "https://salmonprice.nasdaqomx.com/",
                headers={"User-Agent": "AquaIntel/1.0"},
            )

            if resp.status_code == 200:
                prices = self._parse_nasdaq_page(resp.text)
                if prices:
                    self.price_history.extend(prices)
                    self.latest_spot = prices[-1].price_nok_kg
                    log.info("nasdaq.fetched", prices=len(prices), latest=self.latest_spot)
                return prices
            else:
                log.warning("nasdaq.fetch_fail", status=resp.status_code)

        except Exception as exc:
            log.warning("nasdaq.error", error=str(exc)[:100])

        return []

    def _parse_nasdaq_page(self, html: str) -> list[SalmonPricePoint]:
        """Parse salmon prices from Nasdaq page HTML."""
        import re
        prices = []

        # Look for price values in the HTML
        # The page typically shows current week price and recent history
        # Pattern: look for NOK values in typical range (40-120)
        price_matches = re.findall(r'(\d{2,3}[.,]\d{2})\s*(?:NOK|kr)', html)

        if price_matches:
            for match in price_matches[:1]:  # take latest
                try:
                    price = float(match.replace(",", "."))
                    if 30 < price < 200:  # reasonable salmon price range
                        prices.append(SalmonPricePoint(
                            date=dt.date.today(),
                            price_nok_kg=price,
                            weight_class="superior",
                            source="nasdaq",
                        ))
                except ValueError:
                    pass

        return prices

    def predict_price(
        self,
        current_spot: float,
        national_avg_lice: float,
        lice_trend: str,  # increasing / decreasing / stable
        pct_above_threshold: float,
        biomass_vs_normal: float,  # ratio: 1.0 = normal, 0.9 = 10% below
        horizon_weeks: int = 4,
    ) -> PriceForecast:
        """
        Multi-factor salmon price prediction.

        Combines:
          1. Seasonal pattern (where are we vs typical year?)
          2. Lice-to-price signal (treatment cascade → supply impact)
          3. Biomass supply model (standing stock vs normal)
          4. Trend momentum
        """
        now = dt.datetime.now(dt.UTC)
        _, current_week, _ = now.isocalendar()

        if current_spot <= 0:
            current_spot = SEASONAL_PATTERN.get(current_week, 75)

        # ── 1. Seasonal component ────────────────────────────────────
        future_week = current_week + horizon_weeks
        if future_week > 52:
            future_week -= 52

        seasonal_expected = SEASONAL_PATTERN.get(future_week, 75)
        seasonal_current = SEASONAL_PATTERN.get(current_week, 75)
        seasonal_change_pct = (seasonal_expected - seasonal_current) / seasonal_current * 100

        if seasonal_change_pct > 3:
            seasonal_signal = "bullish"
        elif seasonal_change_pct < -3:
            seasonal_signal = "bearish"
        else:
            seasonal_signal = "neutral"

        # ── 2. Lice-to-price signal ──────────────────────────────────
        lice_response = LICE_PRICE_RESPONSE.get(
            min(LICE_PRICE_RESPONSE.keys(), key=lambda k: abs(k - horizon_weeks)),
            0
        )
        # Scale by actual lice severity
        lice_severity = national_avg_lice / 0.5  # normalize to threshold
        lice_impact_pct = lice_response * lice_severity

        if lice_trend == "increasing":
            lice_impact_pct *= 1.5  # amplify if worsening
        elif lice_trend == "decreasing":
            lice_impact_pct *= 0.5  # dampen if improving

        if lice_impact_pct > 1:
            lice_signal = "bullish"
        elif lice_impact_pct < -1:
            lice_signal = "bearish"
        else:
            lice_signal = "neutral"

        # ── 3. Supply/biomass signal ─────────────────────────────────
        supply_impact_pct = (1 - biomass_vs_normal) * 15  # 10% below normal → 1.5% price up
        supply_impact_pct += pct_above_threshold * 10  # more farms in crisis → supply disruption

        if supply_impact_pct > 2:
            supply_signal = "bullish"
        elif supply_impact_pct < -2:
            supply_signal = "bearish"
        else:
            supply_signal = "neutral"

        # ── 4. Combined forecast ─────────────────────────────────────
        total_change_pct = (
            0.35 * seasonal_change_pct +
            0.35 * lice_impact_pct +
            0.30 * supply_impact_pct
        )

        predicted = current_spot * (1 + total_change_pct / 100)

        # Uncertainty widens with horizon
        base_std = current_spot * 0.04  # ~4% weekly volatility
        horizon_std = base_std * np.sqrt(horizon_weeks)
        lo80 = predicted - 1.28 * horizon_std
        hi80 = predicted + 1.28 * horizon_std

        # Direction
        if total_change_pct > 2:
            direction = "bullish"
        elif total_change_pct < -2:
            direction = "bearish"
        else:
            direction = "neutral"

        # Confidence decreases with horizon
        confidence = max(0.2, 0.7 - horizon_weeks * 0.025)

        # Build rationale
        rationale_parts = []
        if seasonal_signal != "neutral":
            rationale_parts.append(
                f"Seasonal pattern {seasonal_signal} ({seasonal_change_pct:+.1f}% typical move to W{future_week})"
            )
        if lice_signal != "neutral":
            rationale_parts.append(
                f"Lice signal {lice_signal} (avg lice {national_avg_lice:.2f}, {lice_trend} trend → "
                f"{lice_impact_pct:+.1f}% supply impact at {horizon_weeks}w)"
            )
        if supply_signal != "neutral":
            rationale_parts.append(
                f"Supply {supply_signal} (biomass {biomass_vs_normal:.0%} of normal, "
                f"{pct_above_threshold:.0%} farms in crisis)"
            )

        signals = [seasonal_signal, lice_signal, supply_signal]
        bullish_count = signals.count("bullish")
        bearish_count = signals.count("bearish")
        if bullish_count >= 2:
            combined = "STRONG BULLISH"
        elif bearish_count >= 2:
            combined = "STRONG BEARISH"
        elif bullish_count > bearish_count:
            combined = "LEAN BULLISH"
        elif bearish_count > bullish_count:
            combined = "LEAN BEARISH"
        else:
            combined = "NEUTRAL"

        return PriceForecast(
            horizon_weeks=horizon_weeks,
            current_spot=round(current_spot, 1),
            predicted_price=round(predicted, 1),
            direction=direction,
            confidence=round(confidence, 2),
            price_lo80=round(lo80, 1),
            price_hi80=round(hi80, 1),
            lice_signal=lice_signal,
            supply_signal=supply_signal,
            seasonal_signal=seasonal_signal,
            combined_signal=combined,
            rationale=". ".join(rationale_parts) if rationale_parts else "No strong directional signals.",
        )

    def get_seasonal_analysis(self) -> dict:
        """Compare current price to seasonal expectation."""
        now = dt.datetime.now(dt.UTC)
        _, week, _ = now.isocalendar()

        expected = SEASONAL_PATTERN.get(week, 75)
        spot = self.latest_spot or expected

        deviation_pct = (spot - expected) / expected * 100

        # Forward seasonal outlook (next 8 weeks)
        forward = []
        for w in range(1, 9):
            fw = week + w
            if fw > 52:
                fw -= 52
            forward.append({
                "week": fw,
                "expected_nok": SEASONAL_PATTERN.get(fw, 75),
                "change_from_now_pct": round(
                    (SEASONAL_PATTERN.get(fw, 75) - expected) / expected * 100, 1
                ),
            })

        return {
            "current_week": week,
            "current_spot": round(spot, 1),
            "seasonal_expected": expected,
            "deviation_pct": round(deviation_pct, 1),
            "is_above_seasonal": deviation_pct > 0,
            "forward_outlook": forward,
        }

    async def close(self) -> None:
        await self._client.aclose()


# Singleton
price_engine = SalmonPriceEngine()


async def get_latest_prices() -> dict[str, float]:
    """
    Convenience function for the IntelligenceAgent to get latest
    salmon-related stock prices for the PairsEngine.

    Priority waterfall:
    1. Yahoo Finance v8 API (Oslo Børs .OL tickers) — daily, ~15min delay
    2. SSB Table 03024 — weekly NOK/kg spot as proxy if equities fail

    Returns dict mapping short ticker → price (NOK for equities).
    """
    import httpx as hx
    prices: dict[str, float] = {}

    # 1. Yahoo Finance v8 for Oslo-listed salmon equities
    # Confirmed: Oslo Børs suffix is .OL (not .OS)
    # Confirmed tickers as of 2025: MOWI.OL, SALM.OL, LSG.OL, GSF.OL, BAKKA.OL
    _OL_TICKERS = {
        "MOWI.OL": "MOWI",
        "SALM.OL": "SALM",
        "LSG.OL": "LSG",
        "GSF.OL": "GSF",
        "BAKKA.OL": "BAKKA",  # Bakkafrost (Faroe/Oslo dual-listed)
    }

    try:
        async with hx.AsyncClient(
            timeout=20,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; AquaIntel/1.0)",
                "Accept": "application/json",
            },
        ) as client:
            for ol_ticker, short in _OL_TICKERS.items():
                try:
                    resp = await client.get(
                        f"https://query1.finance.yahoo.com/v8/finance/chart/{ol_ticker}",
                        params={"interval": "1d", "range": "5d"},
                        timeout=8,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        result = data.get("chart", {}).get("result")
                        if result:
                            closes = result[0]["indicators"]["quote"][0].get("close", [])
                            closes = [c for c in closes if c is not None]
                            if closes:
                                prices[short] = round(closes[-1], 2)
                except Exception:
                    continue
    except Exception as exc:
        log.debug("prices.yahoo_error", error=str(exc)[:80])

    # 2. SSB spot price (primary salmon price benchmark)
    if len(prices) < 2:
        try:
            from core.market.ssb_price_client import ssb_price_client
            spot = await ssb_price_client.get_current_spot()
            if spot > 0:
                prices["SSB_NOK"] = round(spot, 2)
                # Derive approximate equity prices using historical price-to-spot multiples
                # WARNING: These are rough proxies only — use Yahoo equity prices when available
                log.warning("prices.using_ssb_proxies", msg="Yahoo Finance unavailable; deriving equity proxies from SSB spot")
                _SPOT_MULTIPLES = {"MOWI": 2.8, "SALM": 3.4, "LSG": 0.95, "GSF": 1.15}
                for tk, mult in _SPOT_MULTIPLES.items():
                    if tk not in prices:
                        prices[tk] = round(spot * mult, 2)
        except Exception:
            pass

    log.debug("prices.fetched", tickers=list(prices.keys()), n=len(prices))
    return prices


# Fish Pool Index history removed — fishpool.eu dead since late 2025.
# Use SSB price history + FRED PSALMUSDM global salmon benchmark instead.
