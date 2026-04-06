"""
EUMOFA European Market Data Client
=====================================
Fetches European salmon market data from EUMOFA (European Market Observatory
for Fisheries and Aquaculture Products).

EUMOFA provides:
- Weekly European salmon prices by country (import/export)
- Import volumes by EU country
- Price differentials vs Norway (origin price)

Source: https://eumofa.eu
License: European Commission open data
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Optional

import httpx
import structlog

from core.market.data_provenance import DataProvenance

log = structlog.get_logger(__name__)

EUMOFA_BASE_URL = "https://eumofa.eu/api"

# Major EU salmon import markets with typical price differentials vs Norway
EU_SALMON_MARKETS = {
    "FR": {"name": "France", "typical_premium_pct": 5.0, "import_share_pct": 18.2},
    "PL": {"name": "Poland", "typical_premium_pct": -2.0, "import_share_pct": 12.5},
    "DE": {"name": "Germany", "typical_premium_pct": 3.5, "import_share_pct": 10.8},
    "IT": {"name": "Italy", "typical_premium_pct": 4.0, "import_share_pct": 8.3},
    "ES": {"name": "Spain", "typical_premium_pct": 2.5, "import_share_pct": 7.9},
    "DK": {"name": "Denmark", "typical_premium_pct": -1.0, "import_share_pct": 7.5},
    "NL": {"name": "Netherlands", "typical_premium_pct": 1.5, "import_share_pct": 6.8},
    "UK": {"name": "United Kingdom", "typical_premium_pct": 6.0, "import_share_pct": 5.2},
    "SE": {"name": "Sweden", "typical_premium_pct": 0.5, "import_share_pct": 4.1},
    "BE": {"name": "Belgium", "typical_premium_pct": 2.0, "import_share_pct": 3.7},
    "PT": {"name": "Portugal", "typical_premium_pct": 1.0, "import_share_pct": 2.5},
    "FI": {"name": "Finland", "typical_premium_pct": -0.5, "import_share_pct": 2.0},
}


@dataclass
class EUMOFAPricePoint:
    """Weekly salmon price for a specific EU market."""
    country_code: str
    country_name: str
    year: int
    week: int
    price_eur_kg: float
    volume_tonnes: float = 0.0
    price_vs_norway_pct: float = 0.0


@dataclass
class EUMOFASalmonData:
    """Collection of EUMOFA salmon market data."""
    prices: list[EUMOFAPricePoint] = field(default_factory=list)
    fetched_at: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))
    avg_eu_price_eur: float = 0.0
    norway_reference_eur: float = 0.0
    n_countries: int = 0


@dataclass
class EUMOFATradeFlow:
    """Import/export volume for a specific country."""
    country_code: str
    country_name: str
    import_volume_tonnes: float
    import_value_eur_m: float
    export_volume_tonnes: float
    export_value_eur_m: float
    avg_import_price_eur_kg: float
    period: str  # "2026-Q1", "2025", etc.


class EUMOFAClient:
    """
    Fetches European salmon market data from EUMOFA.

    Uses httpx with timeout/retry/fallback pattern.
    Caches results for 6 hours (EUMOFA updates weekly).
    """

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            timeout=30.0,
            headers={"Accept": "application/json", "User-Agent": "OpenClaw/2.1"},
        )
        self._price_cache: Optional[EUMOFASalmonData] = None
        self._price_cache_time: Optional[dt.datetime] = None
        self._trade_cache: Optional[list[EUMOFATradeFlow]] = None
        self._trade_cache_time: Optional[dt.datetime] = None
        self._cache_ttl = dt.timedelta(hours=6)

    def _cache_valid(self, cache_time: Optional[dt.datetime]) -> bool:
        """Check if cache is still within TTL."""
        if cache_time is None:
            return False
        return (dt.datetime.now(dt.UTC) - cache_time) < self._cache_ttl

    async def get_salmon_prices(self) -> dict:
        """
        Fetch weekly European salmon prices by country.

        Returns price data for major EU import markets with differentials
        vs Norway origin price. Attempts EUMOFA REST API first, then
        falls back to modeled data from SSB + known EU market premiums.
        """
        if self._cache_valid(self._price_cache_time) and self._price_cache:
            return self._format_price_response(self._price_cache, is_live=True)

        # Try EUMOFA API
        live_data = await self._fetch_eumofa_prices()
        if live_data and live_data.prices:
            self._price_cache = live_data
            self._price_cache_time = dt.datetime.now(dt.UTC)
            return self._format_price_response(live_data, is_live=True)

        # Fallback: model EU prices from SSB Norway reference + known premiums
        log.info("eumofa.fallback", reason="EUMOFA API unavailable, using SSB + premium model")
        fallback_data = await self._compute_fallback_prices()
        self._price_cache = fallback_data
        self._price_cache_time = dt.datetime.now(dt.UTC)
        return self._format_price_response(fallback_data, is_live=False)

    async def get_trade_flows(self) -> dict:
        """
        Fetch salmon import/export volumes by EU country.

        Returns trade flow data showing import volumes, values, and
        average prices per country. Falls back to modeled data from
        SSB export statistics + EU import share model.
        """
        if self._cache_valid(self._trade_cache_time) and self._trade_cache:
            return self._format_trade_response(self._trade_cache, is_live=True)

        # Try EUMOFA API
        live_flows = await self._fetch_eumofa_trade_flows()
        if live_flows:
            self._trade_cache = live_flows
            self._trade_cache_time = dt.datetime.now(dt.UTC)
            return self._format_trade_response(live_flows, is_live=True)

        # Fallback: model from SSB export data + EU import shares
        log.info("eumofa.trade_fallback", reason="EUMOFA API unavailable, using SSB + share model")
        fallback_flows = await self._compute_fallback_trade_flows()
        self._trade_cache = fallback_flows
        self._trade_cache_time = dt.datetime.now(dt.UTC)
        return self._format_trade_response(fallback_flows, is_live=False)

    # ── Private: EUMOFA API fetching ────────────────────────────────────

    async def _fetch_eumofa_prices(self) -> Optional[EUMOFASalmonData]:
        """Try to fetch live prices from EUMOFA REST API."""
        try:
            # EUMOFA provides salmon first-sale and import prices
            resp = await self._client.get(
                f"{EUMOFA_BASE_URL}/v1/prices",
                params={
                    "species": "SAL",
                    "presentation": "FRE",  # Fresh
                    "period": "weekly",
                    "limit": 100,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                return self._parse_price_response(data)
            log.debug("eumofa.price_fetch_status", status=resp.status_code)
        except httpx.TimeoutException:
            log.warning("eumofa.price_timeout")
        except httpx.ConnectError:
            log.warning("eumofa.price_connect_error")
        except Exception as e:
            log.debug("eumofa.price_error", error=str(e)[:100])
        return None

    async def _fetch_eumofa_trade_flows(self) -> Optional[list[EUMOFATradeFlow]]:
        """Try to fetch live trade flow data from EUMOFA REST API."""
        try:
            resp = await self._client.get(
                f"{EUMOFA_BASE_URL}/v1/trade",
                params={
                    "species": "SAL",
                    "flow": "import",
                    "period": "quarterly",
                    "limit": 50,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                return self._parse_trade_response(data)
            log.debug("eumofa.trade_fetch_status", status=resp.status_code)
        except httpx.TimeoutException:
            log.warning("eumofa.trade_timeout")
        except httpx.ConnectError:
            log.warning("eumofa.trade_connect_error")
        except Exception as e:
            log.debug("eumofa.trade_error", error=str(e)[:100])
        return None

    def _parse_price_response(self, data: dict) -> EUMOFASalmonData:
        """Parse EUMOFA API price response into structured data."""
        prices = []
        records = data.get("data", data.get("records", []))
        for rec in records:
            try:
                cc = rec.get("country_code", rec.get("reporting_country", ""))
                market = EU_SALMON_MARKETS.get(cc)
                if not market:
                    continue
                prices.append(EUMOFAPricePoint(
                    country_code=cc,
                    country_name=market["name"],
                    year=int(rec.get("year", 0)),
                    week=int(rec.get("week", 0)),
                    price_eur_kg=float(rec.get("price", rec.get("value", 0))),
                    volume_tonnes=float(rec.get("volume", 0)),
                ))
            except (ValueError, TypeError):
                continue

        result = EUMOFASalmonData(prices=prices, n_countries=len(set(p.country_code for p in prices)))
        if prices:
            result.avg_eu_price_eur = sum(p.price_eur_kg for p in prices) / len(prices)
        return result

    def _parse_trade_response(self, data: dict) -> list[EUMOFATradeFlow]:
        """Parse EUMOFA API trade flow response."""
        flows = []
        records = data.get("data", data.get("records", []))
        for rec in records:
            try:
                cc = rec.get("country_code", rec.get("reporting_country", ""))
                market = EU_SALMON_MARKETS.get(cc)
                if not market:
                    continue
                vol = float(rec.get("volume", 0))
                val = float(rec.get("value", 0))
                flows.append(EUMOFATradeFlow(
                    country_code=cc,
                    country_name=market["name"],
                    import_volume_tonnes=vol,
                    import_value_eur_m=val / 1_000_000 if val > 10_000 else val,
                    export_volume_tonnes=0,
                    export_value_eur_m=0,
                    avg_import_price_eur_kg=val / (vol * 1000) if vol > 0 else 0,
                    period=rec.get("period", ""),
                ))
            except (ValueError, TypeError):
                continue
        return flows

    # ── Private: Fallback computation ───────────────────────────────────

    async def _compute_fallback_prices(self) -> EUMOFASalmonData:
        """
        Model EU salmon prices from SSB Norway export price + known market premiums.

        The Norwegian export price (SSB Table 03024) is the benchmark for European
        salmon pricing. Each EU market trades at a premium/discount based on
        processing, logistics, and local demand.
        """
        # Get Norway reference price from SSB
        norway_nok = 0.0
        try:
            from core.market.ssb_price_client import ssb_price_client
            norway_nok = await ssb_price_client.get_current_spot()
        except Exception:
            norway_nok = 95.0  # fallback if SSB also unavailable

        # Convert to EUR (approximate, updated from macro intel)
        nok_eur_rate = 0.085  # ~11.7 NOK per EUR
        try:
            from core.market.macro_intelligence import macro_engine
            macro_data = macro_engine.get_macro_snapshot()
            if macro_data and "nok_usd" in macro_data:
                # Approximate EUR from USD: EUR ~= USD * 0.92
                nok_usd = macro_data["nok_usd"]
                if nok_usd and nok_usd > 0:
                    nok_eur_rate = 1.0 / (nok_usd * 1.09 / 1.0)  # NOK→EUR via USD
        except Exception:
            pass

        norway_eur = norway_nok * nok_eur_rate
        now = dt.datetime.now(dt.UTC)
        iso_cal = now.isocalendar()

        prices = []
        for cc, market in EU_SALMON_MARKETS.items():
            premium = 1.0 + (market["typical_premium_pct"] / 100.0)
            local_price = round(norway_eur * premium, 2)
            prices.append(EUMOFAPricePoint(
                country_code=cc,
                country_name=market["name"],
                year=iso_cal[0],
                week=iso_cal[1],
                price_eur_kg=local_price,
                volume_tonnes=0,  # unknown in fallback
                price_vs_norway_pct=round(market["typical_premium_pct"], 1),
            ))

        return EUMOFASalmonData(
            prices=prices,
            avg_eu_price_eur=round(sum(p.price_eur_kg for p in prices) / len(prices), 2) if prices else 0,
            norway_reference_eur=round(norway_eur, 2),
            n_countries=len(prices),
        )

    async def _compute_fallback_trade_flows(self) -> list[EUMOFATradeFlow]:
        """
        Model EU trade flows from SSB export data + EU import share estimates.

        Norway exports ~1.1M tonnes of salmon annually. EU is the dominant market,
        absorbing ~70% of Norwegian salmon exports.
        """
        # Get total Norway exports from SSB
        total_export_tonnes = 0.0
        avg_price_eur = 0.0
        try:
            from core.market.ssb_exports import SSBClient
            ssb = SSBClient()
            try:
                summary = await ssb.get_export_summary()
                total_export_tonnes = float(summary.get("total_volume_tonnes", 0))
                avg_nok = float(summary.get("avg_price_nok_kg", 95))
                avg_price_eur = avg_nok * 0.085  # approximate NOK→EUR
            finally:
                await ssb.close()
        except Exception:
            total_export_tonnes = 90_000  # ~monthly average
            avg_price_eur = 8.0

        # EU absorbs ~70% of Norwegian salmon
        eu_total = total_export_tonnes * 0.70

        now = dt.datetime.now(dt.UTC)
        quarter = f"{now.year}-Q{(now.month - 1) // 3 + 1}"

        flows = []
        for cc, market in EU_SALMON_MARKETS.items():
            share = market["import_share_pct"] / 100.0
            vol = round(eu_total * share, 1)
            premium = 1.0 + (market["typical_premium_pct"] / 100.0)
            price = round(avg_price_eur * premium, 2)
            value_m = round(vol * price / 1000, 2)  # tonnes * EUR/kg / 1000 = M EUR

            flows.append(EUMOFATradeFlow(
                country_code=cc,
                country_name=market["name"],
                import_volume_tonnes=vol,
                import_value_eur_m=value_m,
                export_volume_tonnes=0,
                export_value_eur_m=0,
                avg_import_price_eur_kg=price,
                period=quarter,
            ))

        flows.sort(key=lambda f: f.import_volume_tonnes, reverse=True)
        return flows

    # ── Response formatting ─────────────────────────────────────────────

    def _format_price_response(self, data: EUMOFASalmonData, is_live: bool) -> dict:
        """Format price data for API response."""
        prov = (
            DataProvenance.live("EUMOFA (European Commission)", confidence=0.85)
            if is_live
            else DataProvenance.degraded(
                "SSB Table 03024 + EU premium model",
                "EUMOFA API unavailable, using SSB Norway price with EU market premiums",
                confidence=0.65,
            )
        )

        # Group by country, latest week per country
        by_country = {}
        for p in data.prices:
            existing = by_country.get(p.country_code)
            if not existing or (p.year, p.week) > (existing.year, existing.week):
                by_country[p.country_code] = p

        countries = []
        for p in sorted(by_country.values(), key=lambda x: x.price_eur_kg, reverse=True):
            countries.append({
                "country_code": p.country_code,
                "country_name": p.country_name,
                "price_eur_kg": round(p.price_eur_kg, 2),
                "price_vs_norway_pct": round(p.price_vs_norway_pct, 1),
                "year": p.year,
                "week": p.week,
            })

        return {
            "avg_eu_price_eur": round(data.avg_eu_price_eur, 2),
            "norway_reference_eur": round(data.norway_reference_eur, 2),
            "n_countries": data.n_countries,
            "countries": countries,
            "generated_at": dt.datetime.now(dt.UTC).isoformat(),
            "source": "EUMOFA" if is_live else "SSB + EU premium model",
            "data_provenance": prov.to_dict(),
        }

    def _format_trade_response(self, flows: list[EUMOFATradeFlow], is_live: bool) -> dict:
        """Format trade flow data for API response."""
        prov = (
            DataProvenance.live("EUMOFA Trade Data (European Commission)", confidence=0.85)
            if is_live
            else DataProvenance.degraded(
                "SSB exports + EU import share model",
                "EUMOFA API unavailable, using SSB export stats with EU share estimates",
                confidence=0.60,
            )
        )

        total_volume = sum(f.import_volume_tonnes for f in flows)
        total_value = sum(f.import_value_eur_m for f in flows)

        countries = []
        for f in flows:
            countries.append({
                "country_code": f.country_code,
                "country_name": f.country_name,
                "import_volume_tonnes": round(f.import_volume_tonnes, 1),
                "import_value_eur_m": round(f.import_value_eur_m, 2),
                "avg_import_price_eur_kg": round(f.avg_import_price_eur_kg, 2),
                "import_share_pct": round(f.import_volume_tonnes / total_volume * 100, 1) if total_volume > 0 else 0,
                "period": f.period,
            })

        return {
            "total_import_volume_tonnes": round(total_volume, 1),
            "total_import_value_eur_m": round(total_value, 2),
            "n_countries": len(countries),
            "countries": countries,
            "generated_at": dt.datetime.now(dt.UTC).isoformat(),
            "source": "EUMOFA" if is_live else "SSB + EU share model",
            "data_provenance": prov.to_dict(),
        }

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()


# ── Singleton ────────────────────────────────────────────────────────────
eumofa_client = EUMOFAClient()
