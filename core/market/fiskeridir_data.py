"""
Fiskeridirektoratet Official Production Data Engine
=====================================================
Ingests the official biostat-total-flk.json dataset containing monthly
cohort-level production data for Norwegian salmon aquaculture.

Data: 8,333+ records (2005-2026), monthly granularity, per county, per species,
per cohort year. Contains:
  - BIOMASSE_KG: Standing biomass (kg live weight)
  - BEHFISK_STK: Fish count
  - UTTAK_KG / UTTAK_RUNDVEKT_KG: Harvest volume
  - FORFORBRUK_KG: Feed consumption
  - DØDFISK_STK: Mortality
  - UTSETT_SMOLT_STK: Smolt releases
  - RØMMING_STK: Escapes

Source: Fiskeridirektoratet (Directorate of Fisheries)
License: Public Norwegian government data (NLOD 2.0)
"""
from __future__ import annotations

import datetime as dt
import json
import os
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import structlog

log = structlog.get_logger(__name__)

# Default data file path — can be overridden
DATA_FILE = os.environ.get(
    "FISKERIDIR_BIOSTAT_JSON",
    str(Path.home() / "Downloads" / "biostat-total-flk.json"),
)


@dataclass
class MonthlyProduction:
    """Monthly national production summary."""
    year: int
    month: int
    biomass_tonnes: float = 0.0
    fish_count: int = 0
    harvest_tonnes: float = 0.0
    feed_tonnes: float = 0.0
    mortality_count: int = 0
    smolt_count: int = 0
    escape_count: int = 0


@dataclass
class AnnualSummary:
    """Annual production summary."""
    year: int
    avg_biomass_tonnes: float = 0.0
    total_harvest_tonnes: float = 0.0
    total_feed_tonnes: float = 0.0
    total_mortality: int = 0
    total_smolt: int = 0
    biological_fcr: float = 0.0
    mortality_rate_pct: float = 0.0
    months_reported: int = 0


class FiskeridirDataEngine:
    """
    Loads and serves official Fiskeridirektoratet production data.
    """

    _loaded: bool = False
    _monthly: list[MonthlyProduction] = []
    _annual: list[AnnualSummary] = []
    _by_county: dict = {}
    _raw_records: int = 0

    def __init__(self) -> None:
        self._monthly = []
        self._annual = []
        self._by_county = {}
        self._loaded = False

    def load(self, filepath: str | None = None) -> bool:
        """Load the biostat JSON dataset."""
        path = filepath or DATA_FILE
        if not os.path.exists(path):
            log.warning("fiskeridir.file_not_found", path=path)
            return False

        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)

            data = raw.get("Data", raw) if isinstance(raw, dict) else raw
            if not isinstance(data, list):
                log.warning("fiskeridir.invalid_format")
                return False

            self._raw_records = len(data)

            # Aggregate by year-month (national totals)
            monthly_agg: dict[tuple[int, int], dict] = defaultdict(
                lambda: {"biomass": 0, "fish": 0, "harvest": 0, "feed": 0, "dead": 0, "smolt": 0, "escape": 0}
            )

            for r in data:
                key = (r["ÅR"], r["MÅNED_KODE"])
                monthly_agg[key]["biomass"] += r.get("BIOMASSE_KG", 0) or 0
                monthly_agg[key]["fish"] += r.get("BEHFISK_STK", 0) or 0
                monthly_agg[key]["harvest"] += r.get("UTTAK_KG", 0) or 0
                monthly_agg[key]["feed"] += r.get("FORFORBRUK_KG", 0) or 0
                monthly_agg[key]["dead"] += r.get("DØDFISK_STK", 0) or 0
                monthly_agg[key]["smolt"] += r.get("UTSETT_SMOLT_STK", 0) or 0
                monthly_agg[key]["escape"] += r.get("RØMMING_STK", 0) or 0

            self._monthly = [
                MonthlyProduction(
                    year=k[0], month=k[1],
                    biomass_tonnes=v["biomass"] / 1000,
                    fish_count=v["fish"],
                    harvest_tonnes=v["harvest"] / 1000,
                    feed_tonnes=v["feed"] / 1000,
                    mortality_count=v["dead"],
                    smolt_count=v["smolt"],
                    escape_count=v["escape"],
                )
                for k, v in sorted(monthly_agg.items())
            ]

            # Annual summaries
            annual_agg: dict[int, dict] = defaultdict(
                lambda: {"biomass": [], "harvest": 0, "feed": 0, "dead": 0, "smolt": 0, "months": 0}
            )
            for m in self._monthly:
                annual_agg[m.year]["biomass"].append(m.biomass_tonnes)
                annual_agg[m.year]["harvest"] += m.harvest_tonnes
                annual_agg[m.year]["feed"] += m.feed_tonnes
                annual_agg[m.year]["dead"] += m.mortality_count
                annual_agg[m.year]["smolt"] += m.smolt_count
                annual_agg[m.year]["months"] += 1

            self._annual = []
            for year, v in sorted(annual_agg.items()):
                avg_bio = sum(v["biomass"]) / max(len(v["biomass"]), 1)
                fcr = v["feed"] / max(v["harvest"], 1) if v["harvest"] > 100 else 0
                mort_rate = v["dead"] / max(v["dead"] + v["harvest"] / 4.5, 1) * 100 if v["harvest"] > 0 else 0
                self._annual.append(AnnualSummary(
                    year=year,
                    avg_biomass_tonnes=round(avg_bio, 0),
                    total_harvest_tonnes=round(v["harvest"], 0),
                    total_feed_tonnes=round(v["feed"], 0),
                    total_mortality=v["dead"],
                    total_smolt=v["smolt"],
                    biological_fcr=round(fcr, 2),
                    mortality_rate_pct=round(mort_rate, 1),
                    months_reported=v["months"],
                ))

            # County aggregation for latest year
            latest_year = max(r["ÅR"] for r in data)
            county_agg: dict[str, dict] = defaultdict(
                lambda: {"biomass": 0, "harvest": 0, "feed": 0, "dead": 0}
            )
            for r in data:
                if r["ÅR"] == latest_year:
                    c = r["FYLKE"]
                    county_agg[c]["biomass"] += (r.get("BIOMASSE_KG", 0) or 0) / 1000
                    county_agg[c]["harvest"] += (r.get("UTTAK_KG", 0) or 0) / 1000
                    county_agg[c]["feed"] += (r.get("FORFORBRUK_KG", 0) or 0) / 1000
                    county_agg[c]["dead"] += r.get("DØDFISK_STK", 0) or 0
            self._by_county = dict(county_agg)

            self._loaded = True
            log.info("fiskeridir.loaded", records=self._raw_records,
                     years=len(self._annual), months=len(self._monthly))
            return True

        except Exception as exc:
            log.error("fiskeridir.load_error", error=str(exc)[:200])
            return False

    def get_monthly(self, year: int | None = None) -> list[dict]:
        """Get monthly production data."""
        if not self._loaded:
            self.load()
        data = self._monthly
        if year:
            data = [m for m in data if m.year == year]
        return [
            {
                "year": m.year,
                "month": m.month,
                "biomass_tonnes": round(m.biomass_tonnes, 0),
                "fish_count_millions": round(m.fish_count / 1e6, 1),
                "harvest_tonnes": round(m.harvest_tonnes, 0),
                "feed_tonnes": round(m.feed_tonnes, 0),
                "mortality_thousands": round(m.mortality_count / 1000, 0),
                "smolt_thousands": round(m.smolt_count / 1000, 0),
            }
            for m in data
        ]

    def get_annual(self) -> list[dict]:
        """Get annual production summaries."""
        if not self._loaded:
            self.load()
        return [
            {
                "year": a.year,
                "avg_biomass_tonnes": a.avg_biomass_tonnes,
                "harvest_tonnes": a.total_harvest_tonnes,
                "feed_tonnes": a.total_feed_tonnes,
                "mortality_millions": round(a.total_mortality / 1e6, 1),
                "smolt_millions": round(a.total_smolt / 1e6, 1),
                "biological_fcr": a.biological_fcr,
                "mortality_rate_pct": a.mortality_rate_pct,
                "months_reported": a.months_reported,
            }
            for a in self._annual
            if a.months_reported >= 6  # only complete years
        ]

    def get_latest_summary(self) -> dict:
        """Get the most recent complete annual summary."""
        if not self._loaded:
            self.load()
        complete = [a for a in self._annual if a.months_reported >= 10]
        if not complete:
            return {"error": "No complete year data available"}
        latest = complete[-1]
        return {
            "year": latest.year,
            "avg_biomass_tonnes": latest.avg_biomass_tonnes,
            "harvest_tonnes": latest.total_harvest_tonnes,
            "feed_tonnes": latest.total_feed_tonnes,
            "mortality_millions": round(latest.total_mortality / 1e6, 1),
            "smolt_millions": round(latest.total_smolt / 1e6, 1),
            "biological_fcr": latest.biological_fcr,
            "utilization_pct": round(latest.avg_biomass_tonnes / 947_943 * 100, 1),
            "source": "Fiskeridirektoratet biostat",
            "records": self._raw_records,
        }

    def get_by_county(self) -> list[dict]:
        """Get latest year data by county."""
        if not self._loaded:
            self.load()
        return [
            {
                "county": c,
                "biomass_tonnes": round(v["biomass"], 0),
                "harvest_tonnes": round(v["harvest"], 0),
                "feed_tonnes": round(v["feed"], 0),
                "mortality_thousands": round(v["dead"] / 1000, 0),
            }
            for c, v in sorted(self._by_county.items())
        ]


# Singleton
fiskeridir_data = FiskeridirDataEngine()
