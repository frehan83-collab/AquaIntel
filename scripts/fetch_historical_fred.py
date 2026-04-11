#!/usr/bin/env python3
"""
Fetch Full Historical FRED Commodity Prices (1990-present)
==========================================================
Pulls complete monthly price history for all feed ingredients used by
the FishIntel platform from the FRED (Federal Reserve Economic Data) API.

Series pulled:
  - PFISHUSDM   : Fish (fishmeal) USD/metric tonne, monthly
  - PROILUSDM   : Rapeseed oil USD/metric tonne (fish oil proxy)
  - PSOYBUSDM   : Soybeans USD/metric tonne
  - PWHEAMTUSDM : Wheat USD/metric tonne
  - PSOILUSDM   : Soybean oil USD/metric tonne (rapeseed proxy)
  - DEXNOUS     : Norway/US exchange rate (NOK per 1 USD), daily

Requires: FRED_API_KEY environment variable
  Get one free at: https://fred.stlouisfed.org/docs/api/api_key.html

Output: data/historical/fred_commodities_1990_2026.csv
Columns: date, series_id, value

Usage:
    python scripts/fetch_historical_fred.py
    python scripts/fetch_historical_fred.py --start-year 2000
    python scripts/fetch_historical_fred.py --output data/custom.csv
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import logging
import os
import sys
import time
from pathlib import Path

import httpx

FRED_API_BASE = "https://api.stlouisfed.org/fred/series/observations"

# All FRED series used by the FishIntel platform
FRED_SERIES = {
    "PFISHUSDM": {
        "label": "Fish (fishmeal)",
        "unit": "USD/metric tonne",
        "frequency": "monthly",
        "ingredient": "fishmeal",
    },
    "PROILUSDM": {
        "label": "Rapeseed oil",
        "unit": "USD/metric tonne",
        "frequency": "monthly",
        "ingredient": "fish_oil",
    },
    "PSOYBUSDM": {
        "label": "Soybeans",
        "unit": "USD/metric tonne",
        "frequency": "monthly",
        "ingredient": "soy",
    },
    "PWHEAMTUSDM": {
        "label": "Wheat",
        "unit": "USD/metric tonne",
        "frequency": "monthly",
        "ingredient": "wheat",
    },
    "PSOILUSDM": {
        "label": "Soybean oil",
        "unit": "USD/metric tonne",
        "frequency": "monthly",
        "ingredient": "rapeseed",
    },
    "DEXNOUS": {
        "label": "NOK/USD exchange rate",
        "unit": "NOK per 1 USD",
        "frequency": "daily",
        "ingredient": "fx",
    },
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("fred_historical")


def fetch_series(
    client: httpx.Client,
    api_key: str,
    series_id: str,
    start_date: str,
) -> list[dict]:
    """
    Fetch one FRED series. Returns list of {date, value} dicts.
    Handles FRED pagination (limit=10000 per request, more than enough).
    """
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_start": start_date,
        "sort_order": "asc",
        "limit": 10000,
    }

    resp = client.get(FRED_API_BASE, params=params, timeout=30.0)

    if resp.status_code != 200:
        log.warning(
            "  %s: HTTP %d — %s",
            series_id,
            resp.status_code,
            resp.text[:200],
        )
        return []

    data = resp.json()
    observations = data.get("observations", [])

    records = []
    for obs in observations:
        date_str = obs.get("date", "")
        value_str = obs.get("value", ".")
        if value_str in (".", "", None):
            continue
        try:
            value = float(value_str)
        except ValueError:
            continue
        records.append({"date": date_str, "value": value})

    return records


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch full historical FRED commodity prices for ML training"
    )
    parser.add_argument(
        "--start-year",
        type=int,
        default=1990,
        help="First year to fetch (default: 1990)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output CSV path (default: data/historical/fred_commodities_1990_2026.csv)",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="FRED API key (default: from FRED_API_KEY env var)",
    )
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("FRED_API_KEY", "")
    if not api_key:
        log.error(
            "FRED_API_KEY not set. Get a free key at: "
            "https://fred.stlouisfed.org/docs/api/api_key.html\n"
            "  Set via: export FRED_API_KEY=your_key_here\n"
            "  Or pass: --api-key YOUR_KEY"
        )
        return 1

    current_year = dt.datetime.now(dt.UTC).year
    start_date = f"{args.start_year}-01-01"

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = (
            Path(__file__).resolve().parent.parent
            / "data"
            / "historical"
            / f"fred_commodities_{args.start_year}_{current_year}.csv"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    log.info(
        "Fetching %d FRED series from %s -> %s",
        len(FRED_SERIES),
        start_date,
        output_path,
    )

    all_records: list[dict] = []
    client = httpx.Client()

    try:
        for series_id, meta in FRED_SERIES.items():
            t0 = time.time()
            records = fetch_series(client, api_key, series_id, start_date)
            elapsed = time.time() - t0

            for r in records:
                all_records.append({
                    "date": r["date"],
                    "series_id": series_id,
                    "value": r["value"],
                })

            if records:
                log.info(
                    "  %s (%s): %d observations, %s to %s (%.1fs)",
                    series_id,
                    meta["label"],
                    len(records),
                    records[0]["date"],
                    records[-1]["date"],
                    elapsed,
                )
            else:
                log.warning("  %s (%s): no data returned", series_id, meta["label"])

            # FRED rate limit: 120 requests/minute — be polite
            time.sleep(0.6)
    finally:
        client.close()

    if not all_records:
        log.error("No data fetched. Check FRED_API_KEY and network connectivity.")
        return 1

    # Sort by date then series_id
    all_records.sort(key=lambda r: (r["date"], r["series_id"]))

    # Write CSV
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "series_id", "value"])
        for r in all_records:
            writer.writerow([r["date"], r["series_id"], round(r["value"], 4)])

    # Summary stats
    series_counts: dict[str, int] = {}
    for r in all_records:
        sid = r["series_id"]
        series_counts[sid] = series_counts.get(sid, 0) + 1

    log.info("Done: %d total observations written to %s", len(all_records), output_path)
    for sid, count in sorted(series_counts.items()):
        meta = FRED_SERIES[sid]
        log.info("  %s (%s): %d observations", sid, meta["label"], count)

    return 0


if __name__ == "__main__":
    sys.exit(main())
