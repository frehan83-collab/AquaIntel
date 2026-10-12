"""
SSB Salmon Export Intelligence — Real Destination-Level Trade Data
====================================================================
API: https://data.ssb.no/api/v0/en/table/08799/
Table 08799: External trade by HS commodity number, country, and month.

HS codes for fresh Atlantic salmon (Salmo salar):
  03021411_2012  — subgroup (2012+)
  03021419_2017  — subgroup (2017+)
  03021490_2017  — subgroup (2017+)

Free, no auth required. JSON-stat2 format.
Source: Statistics Norway (SSB), License: CC BY 4.0.
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass

import httpx
import structlog

log = structlog.get_logger(__name__)

SSB_API_URL = "https://data.ssb.no/api/v0/en/table/08799/"

# Fresh Atlantic salmon HS codes (from SSB dimension metadata)
SALMON_HS_CODES = [
    "03021411_2012",  # Atlantic salmon subgroup (2012+)
    "03021419_2017",  # Atlantic salmon subgroup (2017+)
    "03021490_2017",  # Atlantic salmon subgroup (2017+)
]

# Major salmon export destination countries
TOP_DESTINATIONS = [
    "PL", "FR", "DK", "ES", "GB", "US", "JP", "KR", "CN",
    "NL", "IT", "SE", "DE", "BE", "PT", "FI", "LT", "TH",
]


@dataclass
class SalmonExportRecord:
    year: int
    month: int
    destination: str       # country code (2-letter ISO)
    destination_name: str  # country name
    quantity_kg: float     # Q1 in kg
    value_nok: float       # NOK
    price_per_kg: float = 0.0  # computed

    @property
    def quantity_tonnes(self) -> float:
        return self.quantity_kg / 1000

    @property
    def value_nok_millions(self) -> float:
        return self.value_nok / 1_000_000


class SSBClient:
    """
    Fetches salmon export trade data from SSB table 08799.
    Provides destination-level export volumes, values, and trends.
    """

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=30.0)
        self._cache: list[SalmonExportRecord] | None = None
        self._cache_time: dt.datetime | None = None
        self._cache_ttl = dt.timedelta(hours=12)

    async def get_salmon_exports(
        self,
        months: int = 24,
        destinations: list[str] | None = None,
    ) -> list[SalmonExportRecord]:
        """
        Fetch salmon export data by destination from SSB table 08799.
        Returns per-country, per-month records with quantity (kg) and value (NOK).
        """
        now = dt.datetime.now(dt.UTC)

        if (
            self._cache
            and self._cache_time
            and (now - self._cache_time) < self._cache_ttl
        ):
            return self._cache

        dests = destinations or TOP_DESTINATIONS
        time_codes = self._build_month_codes(months)

        query = {
            "query": [
                {
                    "code": "Varekoder",
                    "selection": {"filter": "item", "values": SALMON_HS_CODES},
                },
                {
                    "code": "ImpEks",
                    "selection": {"filter": "item", "values": ["2"]},  # Exports only
                },
                {
                    "code": "Land",
                    "selection": {"filter": "item", "values": dests},
                },
                {
                    "code": "ContentsCode",
                    "selection": {"filter": "item", "values": ["Mengde1", "Verdi"]},
                },
                {
                    "code": "Tid",
                    "selection": {"filter": "item", "values": time_codes},
                },
            ],
            "response": {"format": "json-stat2"},
        }

        try:
            resp = await self._client.post(
                SSB_API_URL, json=query,
                headers={"Content-Type": "application/json"},
            )

            if resp.status_code == 200:
                records = self._parse_response(resp.json())
                self._cache = records
                self._cache_time = now
                log.info("ssb_exports.fetched", n_records=len(records))
                return records
            else:
                log.warning("ssb_exports.fetch_failed", status=resp.status_code)

        except Exception as e:
            log.warning("ssb_exports.error", error=str(e)[:100])

        return self._cache or []

    async def get_destination_breakdown(self, months: int = 12) -> dict:
        """
        Top destinations ranked by volume, with trend indicators.
        Returns {country_code: {name, total_kg, total_nok, avg_price, trend_pct}}.
        """
        records = await self.get_salmon_exports(months=months)
        if not records:
            return {}

        # Aggregate by destination
        by_dest: dict[str, dict] = defaultdict(lambda: {
            "name": "", "total_kg": 0, "total_nok": 0, "months": set(),
            "recent_kg": 0, "prior_kg": 0,
        })

        # Split into recent vs prior halves for trend
        all_months = sorted(set(f"{r.year}-{r.month:02d}" for r in records))
        mid = len(all_months) // 2
        recent_months = set(all_months[mid:])

        for r in records:
            d = by_dest[r.destination]
            d["name"] = r.destination_name
            d["total_kg"] += r.quantity_kg
            d["total_nok"] += r.value_nok
            d["months"].add(f"{r.year}-{r.month:02d}")

            month_key = f"{r.year}-{r.month:02d}"
            if month_key in recent_months:
                d["recent_kg"] += r.quantity_kg
            else:
                d["prior_kg"] += r.quantity_kg

        result = {}
        for code, d in sorted(by_dest.items(), key=lambda x: x[1]["total_kg"], reverse=True):
            total_kg = d["total_kg"]
            total_nok = d["total_nok"]
            avg_price = total_nok / max(total_kg, 1)

            trend_pct = 0.0
            if d["prior_kg"] > 0:
                trend_pct = (d["recent_kg"] - d["prior_kg"]) / d["prior_kg"] * 100

            result[code] = {
                "name": d["name"],
                "total_tonnes": round(total_kg / 1000, 0),
                "total_nok_millions": round(total_nok / 1_000_000, 1),
                "avg_price_nok_kg": round(avg_price, 1),
                "trend_pct": round(trend_pct, 1),
                "months_with_data": len(d["months"]),
            }

        return result

    async def get_monthly_volume_series(self, months: int = 24) -> list[dict]:
        """Monthly total export volume time series for charts."""
        records = await self.get_salmon_exports(months=months)

        by_month: dict[str, dict] = defaultdict(lambda: {"kg": 0, "nok": 0})
        for r in records:
            key = f"{r.year}-{r.month:02d}"
            by_month[key]["kg"] += r.quantity_kg
            by_month[key]["nok"] += r.value_nok

        return [
            {
                "month": k,
                "tonnes": round(v["kg"] / 1000, 0),
                "value_mnok": round(v["nok"] / 1_000_000, 0),
                "avg_price": round(v["nok"] / max(v["kg"], 1), 1),
            }
            for k, v in sorted(by_month.items())
        ]

    async def get_export_summary(self) -> dict:
        """High-level summary for the API."""
        breakdown = await self.get_destination_breakdown(months=12)
        series = await self.get_monthly_volume_series(months=12)

        if not breakdown:
            return {"status": "no_data", "source": "SSB table 08799"}

        total_tonnes = sum(d["total_tonnes"] for d in breakdown.values())
        total_nok_m = sum(d["total_nok_millions"] for d in breakdown.values())

        top_dests = list(breakdown.items())[:10]

        return {
            "source": "SSB table 08799 (Statistics Norway)",
            "period": f"Last 12 months",
            "total_export_tonnes": round(total_tonnes, 0),
            "total_export_nok_millions": round(total_nok_m, 0),
            "avg_price_nok_kg": round(total_nok_m * 1_000_000 / max(total_tonnes * 1000, 1), 1),
            "n_destinations": len(breakdown),
            "top_destinations": [
                {
                    "country_code": code,
                    "country_name": d["name"],
                    "tonnes": d["total_tonnes"],
                    "value_mnok": d["total_nok_millions"],
                    "avg_price": d["avg_price_nok_kg"],
                    "trend_pct": d["trend_pct"],
                }
                for code, d in top_dests
            ],
            "monthly_series": series,
        }

    @staticmethod
    def _build_month_codes(n_months: int) -> list[str]:
        """Build SSB month codes like '2025M06'."""
        now = dt.datetime.now(dt.UTC)
        codes = []
        for i in range(n_months, 0, -1):
            m = now.month - i
            y = now.year
            while m < 1:
                m += 12
                y -= 1
            codes.append(f"{y}M{m:02d}")
        return codes

    def _parse_response(self, data: dict) -> list[SalmonExportRecord]:
        """
        Parse SSB JSON-stat2 multi-dimensional response.

        Dimensions: [Varekoder, ImpEks, Land, ContentsCode, Tid]
        Size: [n_hs_codes, 1, n_countries, n_contents, n_months]
        Layout: flat array indexed as:
          idx = hs*s1*s2*s3*s4 + ie*s2*s3*s4 + land*s3*s4 + content*s4 + time
        """
        records_map: dict[str, dict] = {}

        try:
            dims = data.get("dimension", {})
            values = data.get("value", [])
            sizes = data.get("size", [])

            if not values or not sizes:
                return []

            # Extract dimension keys
            land_keys = list(dims.get("Land", {}).get("category", {}).get("label", {}).keys())
            land_labels = dims.get("Land", {}).get("category", {}).get("label", {})
            content_keys = list(dims.get("ContentsCode", {}).get("category", {}).get("label", {}).keys())
            time_keys = list(dims.get("Tid", {}).get("category", {}).get("label", {}).keys())

            s = sizes  # [n_hs, n_ie, n_land, n_content, n_time]
            if len(s) < 5:
                return []

            # Iterate all combinations
            for hs_i in range(s[0]):
                for ie_i in range(s[1]):
                    for land_i in range(s[2]):
                        country_code = land_keys[land_i] if land_i < len(land_keys) else "??"
                        country_name = land_labels.get(country_code, country_code)

                        for content_i in range(s[3]):
                            content_key = content_keys[content_i] if content_i < len(content_keys) else ""

                            for time_i in range(s[4]):
                                time_code = time_keys[time_i] if time_i < len(time_keys) else ""

                                # Flat index
                                idx = (
                                    hs_i * s[1] * s[2] * s[3] * s[4]
                                    + ie_i * s[2] * s[3] * s[4]
                                    + land_i * s[3] * s[4]
                                    + content_i * s[4]
                                    + time_i
                                )

                                if idx >= len(values) or values[idx] is None:
                                    continue

                                val = float(values[idx])

                                # Parse time code
                                year, month = 0, 0
                                if "M" in time_code:
                                    try:
                                        year = int(time_code[:4])
                                        month = int(time_code[5:7])
                                    except ValueError:
                                        continue

                                # Aggregate across HS subgroups per country/month
                                rec_key = f"{country_code}_{year}_{month}"
                                if rec_key not in records_map:
                                    records_map[rec_key] = {
                                        "year": year,
                                        "month": month,
                                        "dest_code": country_code,
                                        "dest_name": country_name,
                                        "quantity_kg": 0.0,
                                        "value_nok": 0.0,
                                    }

                                if "Mengde" in content_key:
                                    records_map[rec_key]["quantity_kg"] += val
                                elif "Verdi" in content_key:
                                    records_map[rec_key]["value_nok"] += val

        except Exception as e:
            log.warning("ssb_exports.parse_error", error=str(e)[:100])

        # Convert to sorted list
        result = []
        for rec_key in sorted(records_map.keys()):
            d = records_map[rec_key]
            if d["quantity_kg"] > 0 or d["value_nok"] > 0:
                price_per_kg = d["value_nok"] / max(d["quantity_kg"], 1)
                result.append(SalmonExportRecord(
                    year=d["year"],
                    month=d["month"],
                    destination=d["dest_code"],
                    destination_name=d["dest_name"],
                    quantity_kg=d["quantity_kg"],
                    value_nok=d["value_nok"],
                    price_per_kg=round(price_per_kg, 2),
                ))

        return result

    async def close(self) -> None:
        await self._client.aclose()
