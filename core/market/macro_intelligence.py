"""
Macro Intelligence Engine — FRED Commodity & Currency Layer
=============================================================
Pulls 12 free FRED time series monthly and computes:
  1. Feed Cost Pressure Index (weighted composite)
  2. Energy Cost Index (Brent + NatGas)
  3. Currency Exposure (NOK/USD, USD/EUR)
  4. Global salmon price benchmark vs Norwegian SSB spot
  5. Plain-language actionable alerts

All data from FRED (Federal Reserve Economic Data) — free, no API key.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import httpx
import structlog

log = structlog.get_logger(__name__)

# ── FRED Series Configuration ────────────────────────────────────────────────
FRED_SERIES = {
    # Salmon & Seafood
    "PSALMUSDM":        {"name": "global_salmon",    "label": "Global Salmon (USD/kg)", "unit": "USD/kg"},
    # Feed ingredients (also used by feed_cost_engine)
    "PSOYBUSDM":        {"name": "soybeans",         "label": "Soybeans",               "unit": "USD/t"},
    "PWHEAMTUSDM":      {"name": "wheat",            "label": "Wheat",                  "unit": "USD/t"},
    "PFISHUSDM":        {"name": "fishmeal",         "label": "Fishmeal",               "unit": "USD/t"},
    "PROILUSDM":        {"name": "rapeseed_oil",     "label": "Rapeseed Oil",           "unit": "USD/t"},
    "PSOILUSDM":        {"name": "soybean_oil",      "label": "Soybean Oil",            "unit": "USD/t"},
    # Energy
    "POILBREUSDM":      {"name": "brent_crude",      "label": "Brent Crude",            "unit": "USD/bbl"},
    "PNGASEUUSDM":      {"name": "natgas_eu",        "label": "Natural Gas EU",         "unit": "USD/mmbtu"},
    # Currency
    "DEXNOUS":          {"name": "nok_usd",          "label": "NOK/USD",                "unit": "NOK"},
    "DEXUSEU":          {"name": "usd_eur",          "label": "USD/EUR",                "unit": "EUR"},
    # Norway macro
    "IRLTLT01NOM156N":  {"name": "norway_rate",      "label": "Norway Interest Rate",   "unit": "%"},
    "CPGRLE01NOM659N":  {"name": "norway_cpi",       "label": "Norway CPI",             "unit": "%"},
}


@dataclass
class MacroSnapshot:
    """Point-in-time macro intelligence snapshot."""
    timestamp: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))
    # Raw latest values
    series: dict[str, float] = field(default_factory=dict)
    # Computed indices
    feed_pressure_index: float = 0.0      # 0-100 (higher = more expensive)
    energy_cost_index: float = 0.0        # 0-100
    currency_exposure: float = 0.0        # NOK weakness = higher (bad for importers, good for exporters)
    global_vs_norway_premium_pct: float = 0.0  # positive = Norway trades at premium
    # YoY changes
    yoy_changes: dict[str, float] = field(default_factory=dict)
    # Alerts
    alerts: list[str] = field(default_factory=list)


class MacroIntelligenceEngine:
    """
    Fetches FRED macro data, computes composite indices, generates alerts.
    Designed for lightweight integration — one API call, one widget.
    """

    _cache: MacroSnapshot | None = None
    _cache_time: dt.datetime | None = None
    _cache_ttl = dt.timedelta(hours=3)
    _raw_series: dict[str, list[tuple[str, float]]] = {}  # name → [(date, value), ...]

    def __init__(self) -> None:
        self._cache = None
        self._raw_series = {}

    async def fetch(self) -> MacroSnapshot:
        """Fetch all FRED series and compute snapshot."""
        now = dt.datetime.now(dt.UTC)
        if self._cache and self._cache_time and (now - self._cache_time) < self._cache_ttl:
            return self._cache

        latest: dict[str, float] = {}
        yoy: dict[str, float] = {}

        async with httpx.AsyncClient(timeout=20) as client:
            for series_id, cfg in FRED_SERIES.items():
                try:
                    resp = await client.get(
                        f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}",
                    )
                    if resp.status_code != 200 or len(resp.text) < 50:
                        continue

                    lines = resp.text.strip().split("\n")[1:]  # skip header
                    parsed = []
                    for line in lines:
                        parts = line.split(",")
                        if len(parts) == 2 and parts[1].strip() not in ("", "."):
                            try:
                                parsed.append((parts[0].strip(), float(parts[1].strip())))
                            except ValueError:
                                continue

                    if not parsed:
                        continue

                    name = cfg["name"]
                    self._raw_series[name] = parsed[-120:]  # keep last 10 years

                    # Latest value
                    latest[name] = parsed[-1][1]

                    # YoY change
                    if len(parsed) >= 13:
                        old = parsed[-13][1]  # ~12 months ago
                        if old > 0:
                            yoy[name] = round((parsed[-1][1] - old) / old * 100, 1)

                except Exception:
                    continue

        # ── Additional FX rates from Yahoo Finance ─────────────────────
        # NOK/EUR and NOK/CNY (not available on FRED)
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                for ticker, name in [("NOKEUR=X", "nok_eur"), ("EURNOK=X", "eur_nok"), ("USDCNY=X", "usd_cny")]:
                    try:
                        resp = await client.get(
                            f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=5d",
                            headers={"User-Agent": "FishIntel/1.0"},
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            closes = data.get("chart", {}).get("result", [{}])[0] \
                                .get("indicators", {}).get("quote", [{}])[0].get("close", [])
                            valid = [c for c in closes if c is not None]
                            if valid:
                                latest[name] = valid[-1]
                    except Exception:
                        continue

                # Compute NOK/CNY = NOK/USD × USD/CNY
                if "nok_usd" in latest and "usd_cny" in latest:
                    nok_per_usd = latest["nok_usd"]  # e.g. 9.58
                    usd_per_cny = 1 / latest["usd_cny"]  # e.g. 1/6.91 = 0.145
                    latest["nok_cny"] = round(nok_per_usd * usd_per_cny, 4)  # NOK per 1 CNY

                # NOK/EUR from EURNOK (invert) or NOKEUR directly
                if "eur_nok" in latest and latest["eur_nok"] > 0:
                    latest["nok_eur"] = round(1 / latest["eur_nok"], 4)
                elif "nok_eur" not in latest and "nok_usd" in latest and "usd_eur" in latest:
                    # Derive: NOK/EUR = NOK/USD ÷ EUR/USD
                    latest["nok_eur"] = round(latest["nok_usd"] / latest["usd_eur"], 4) if latest["usd_eur"] > 0 else 0

        except Exception as exc:
            log.debug("macro.yahoo_fx_error", error=str(exc)[:80])

        n_fetched = len(latest)
        if n_fetched == 0:
            log.warning("macro.no_data_fetched")
            return self._cache or MacroSnapshot()

        # ── Compute composite indices ────────────────────────────────────
        # Feed Pressure Index (0-100): weighted by feed composition importance
        feed_components = {
            "fishmeal": (latest.get("fishmeal", 1500), 1500, 0.30),  # (value, baseline, weight)
            "soybeans": (latest.get("soybeans", 400), 400, 0.25),
            "rapeseed_oil": (latest.get("rapeseed_oil", 1100), 1100, 0.20),
            "soybean_oil": (latest.get("soybean_oil", 1100), 1100, 0.10),
            "wheat": (latest.get("wheat", 200), 200, 0.15),
        }
        feed_pressure = 0.0
        for _name, (val, baseline, weight) in feed_components.items():
            ratio = val / max(baseline, 1)
            feed_pressure += min(ratio * 50, 100) * weight  # normalize to 0-100 scale
        feed_pressure = round(min(100, feed_pressure), 1)

        # Energy Cost Index
        brent = latest.get("brent_crude", 70)
        natgas = latest.get("natgas_eu", 10)
        energy_idx = round(min(100, (brent / 120 * 50) + (natgas / 25 * 50)), 1)

        # Currency Exposure (NOK weakness relative to USD)
        nok_usd = latest.get("nok_usd", 10.0)
        # Higher NOK/USD = weaker NOK = good for exporters, bad for feed imports
        currency_exp = round(min(100, (nok_usd / 12) * 100), 1)

        # Global vs Norway premium
        global_salmon = latest.get("global_salmon", 0)
        try:
            from core.market.ssb_price_client import ssb_price_client
            ssb_spot = await ssb_price_client.get_current_spot()
        except Exception:
            ssb_spot = 0

        premium = 0.0
        if global_salmon > 0 and ssb_spot > 0 and nok_usd > 0:
            # Convert SSB NOK/kg to USD/kg for comparison
            ssb_usd = ssb_spot / nok_usd
            premium = round((ssb_usd - global_salmon) / max(global_salmon, 0.01) * 100, 1)

        # ── Generate alerts ──────────────────────────────────────────────
        alerts = []

        # Feed cost alerts
        feed_yoy = yoy.get("fishmeal", 0)
        if feed_yoy > 15:
            alerts.append(f"Fishmeal up {feed_yoy:+.0f}% YoY — feed cost pressure rising. Consider forward contracts on feed.")
        elif feed_yoy < -10:
            alerts.append(f"Fishmeal down {feed_yoy:+.0f}% YoY — favorable feed purchasing window.")

        soy_yoy = yoy.get("soybeans", 0)
        if soy_yoy > 15:
            alerts.append(f"Soybeans up {soy_yoy:+.0f}% YoY — plant protein costs elevated.")

        # Energy alerts
        brent_yoy = yoy.get("brent_crude", 0)
        if brent_yoy > 20:
            alerts.append(f"Brent crude up {brent_yoy:+.0f}% YoY — transport and processing costs rising.")
        elif brent_yoy < -15:
            alerts.append(f"Brent crude down {brent_yoy:+.0f}% YoY — logistics costs easing.")

        # Currency alerts
        nok_yoy = yoy.get("nok_usd", 0)
        if nok_yoy > 5:
            alerts.append(f"NOK weakened {nok_yoy:+.0f}% vs USD — export revenues boosted but feed imports costlier.")
        elif nok_yoy < -5:
            alerts.append(f"NOK strengthened {abs(nok_yoy):.0f}% vs USD — cheaper feed imports but lower export revenue in NOK.")

        # Premium alert
        if premium > 10:
            alerts.append(f"Norwegian salmon trades at {premium:+.0f}% premium to global benchmark — strong market position.")
        elif premium < -5:
            alerts.append(f"Norwegian salmon at {premium:.0f}% discount to global benchmark — potential margin pressure.")

        # Interest rate
        rate = latest.get("norway_rate", 0)
        rate_yoy = yoy.get("norway_rate", 0)
        if rate > 4.0 and rate_yoy > 0:
            alerts.append(f"Norway long-term rate at {rate:.1f}% — elevated financing costs for farm investments.")

        if not alerts:
            alerts.append("Macro environment stable — no significant cost pressures detected.")

        snapshot = MacroSnapshot(
            series=latest,
            feed_pressure_index=feed_pressure,
            energy_cost_index=energy_idx,
            currency_exposure=currency_exp,
            global_vs_norway_premium_pct=premium,
            yoy_changes=yoy,
            alerts=alerts,
        )

        self._cache = snapshot
        self._cache_time = now
        log.info("macro.computed", n_series=n_fetched, feed_pressure=feed_pressure,
                 energy=energy_idx, alerts=len(alerts))
        return snapshot

    def get_snapshot_dict(self) -> dict | None:
        """Return latest snapshot as API-friendly dict."""
        s = self._cache
        if not s:
            return None
        return {
            "timestamp": s.timestamp.isoformat(),
            "indices": {
                "feed_pressure": {"value": s.feed_pressure_index, "label": "Feed Cost Pressure", "scale": "0-100"},
                "energy_cost":   {"value": s.energy_cost_index, "label": "Energy Cost Index", "scale": "0-100"},
                "currency_exposure": {"value": s.currency_exposure, "label": "NOK Weakness", "scale": "0-100"},
            },
            "benchmarks": {
                "global_salmon_usd_kg": round(s.series.get("global_salmon", 0), 2),
                "ssb_spot_usd_kg": round(
                    (s.series.get("nok_usd", 10) and s.series.get("global_salmon", 0)) or 0, 2
                ),
                "norway_premium_pct": s.global_vs_norway_premium_pct,
                "nok_usd": round(s.series.get("nok_usd", 0), 4),
                "nok_eur": round(s.series.get("nok_eur", 0), 4),
                "nok_cny": round(s.series.get("nok_cny", 0), 4),
                "eur_nok": round(s.series.get("eur_nok", 0), 2),
                "usd_eur": round(s.series.get("usd_eur", 0), 4),
                "brent_crude_usd": round(s.series.get("brent_crude", 0), 1),
                "natgas_eu_usd": round(s.series.get("natgas_eu", 0), 2),
                "norway_rate_pct": round(s.series.get("norway_rate", 0), 2),
            },
            "yoy_changes": s.yoy_changes,
            "alerts": s.alerts,
        }

    def get_series_history(self, name: str, months: int = 60) -> list[dict]:
        """Get historical data for a specific series."""
        data = self._raw_series.get(name, [])
        return [
            {"date": d, "value": round(v, 4)}
            for d, v in data[-months:]
        ]


# Singleton
macro_intelligence = MacroIntelligenceEngine()
