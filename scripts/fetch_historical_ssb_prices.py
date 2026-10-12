#!/usr/bin/env python3
"""
Fetch Full Historical SSB 03024 Salmon Export Prices (2000-present)
===================================================================
Pulls the complete weekly price + volume history from Statistics Norway
Table 03024 "Export of farm-bred salmon" via the PxWeb JSON-stat2 API.

Source: https://data.ssb.no/api/v0/en/table/03024/
License: Open data (CC BY 4.0)
No API key required.

Output: data/historical/ssb_prices_2000_2026.csv
Columns: year, week, price_nok_per_kg, volume_tonnes

Usage:
    python scripts/fetch_historical_ssb_prices.py
    python scripts/fetch_historical_ssb_prices.py --start-year 2010
    python scripts/fetch_historical_ssb_prices.py --output data/custom_path.csv
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import logging
import sys
import time
from pathlib import Path

import httpx

SSB_API_URL = "https://data.ssb.no/api/v0/en/table/03024/"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ssb_historical")


def parse_week_code(code: str) -> tuple[int, int]:
    """Parse SSB week codes like '2025U13' or '2025W13' into (year, week)."""
    for sep in ("U", "W"):
        if sep in code:
            parts = code.split(sep)
            try:
                return int(parts[0]), int(parts[1])
            except (ValueError, IndexError):
                pass
    return 0, 0


def parse_json_stat2(data: dict) -> list[dict]:
    """
    Parse SSB JSON-stat2 response into list of dicts.

    SSB layout for size=[n_commodities, n_contents, n_times]:
      values are in content-major order:
      [content0_time0, content0_time1, ..., content1_time0, content1_time1, ...]
    """
    records: dict[str, dict] = {}

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

    n_contents = sizes[1] if len(sizes) > 1 else 1
    n_times = sizes[2] if len(sizes) > 2 else len(time_labels)

    for t_idx, t_code in enumerate(time_labels):
        year, week = parse_week_code(t_code)
        if year == 0:
            continue

        key = f"{year}W{week:02d}"
        records[key] = {"year": year, "week": week, "price": 0.0, "volume": 0.0}

        for c_idx, c_key in enumerate(contents_keys):
            val_idx = c_idx * n_times + t_idx
            if val_idx < len(values) and values[val_idx] is not None:
                try:
                    val = float(values[val_idx])
                except (ValueError, TypeError):
                    continue
                if "Kilopris" in c_key or "pris" in c_key.lower():
                    records[key]["price"] = val
                elif "Vekt" in c_key or "vekt" in c_key.lower():
                    records[key]["volume"] = val

    # Sort by week code and filter out zero-price entries
    result = []
    for key in sorted(records.keys()):
        r = records[key]
        if r["price"] > 0:
            result.append(r)

    return result


def fetch_year_batch(client: httpx.Client, year: int, current_year: int) -> list[dict]:
    """Fetch SSB 03024 history in one request.

    NOTE: SSB's API no longer honours `fromTo` as a range filter — it returns
    only the two boundary weeks (verified 2026-10). `filter: all` returns the
    complete weekly history (2000U01..present) in a single response, so the
    per-year loop is gone; `year` is kept for CLI compatibility and filters
    client-side below.
    """
    query = {
        "query": [
            {
                "code": "VareGrupper2",
                "selection": {"filter": "item", "values": ["01"]},  # Fresh salmon
            },
            {
                "code": "ContentsCode",
                "selection": {"filter": "item", "values": ["Kilopris", "Vekt"]},
            },
            {
                "code": "Tid",
                "selection": {"filter": "all", "values": ["*"]},
            },
        ],
        "response": {"format": "json-stat2"},
    }

    resp = client.post(
        SSB_API_URL,
        json=query,
        headers={"Content-Type": "application/json"},
        timeout=30.0,
    )

    if resp.status_code == 200:
        return parse_json_stat2(resp.json())
    elif resp.status_code == 400:
        log.warning("Year %d: HTTP 400 — SSB rejected the query", year)
        return []
    else:
        log.warning("Year %d: HTTP %d", year, resp.status_code)
        return []


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch full historical SSB 03024 salmon export prices"
    )
    parser.add_argument(
        "--start-year",
        type=int,
        default=2000,
        help="First year to fetch (default: 2000)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output CSV path (default: data/historical/ssb_prices_2000_2026.csv)",
    )
    args = parser.parse_args()

    current_year = dt.datetime.now(dt.UTC).year
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = (
            Path(__file__).resolve().parent.parent
            / "data"
            / "historical"
            / f"ssb_prices_{args.start_year}_{current_year}.csv"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    log.info(
        "Fetching SSB 03024 prices: %d-%d -> %s",
        args.start_year,
        current_year,
        output_path,
    )

    all_records: list[dict] = []
    client = httpx.Client()

    try:
        t0 = time.time()
        records = fetch_year_batch(client, args.start_year, current_year)
        # One request returns full history — filter client-side to --start-year
        all_records.extend(r for r in records if r["year"] >= args.start_year)
        log.info(
            "  %d weeks fetched in one request (%.1fs), kept %d since %d",
            len(records),
            time.time() - t0,
            len(all_records),
            args.start_year,
        )
    finally:
        client.close()

    if not all_records:
        log.error("No data fetched. Check network connectivity and SSB API status.")
        return 1

    # De-duplicate by (year, week) — keep last occurrence
    seen: dict[str, dict] = {}
    for r in all_records:
        key = f"{r['year']}W{r['week']:02d}"
        seen[key] = r

    deduped = [seen[k] for k in sorted(seen.keys())]

    # Write CSV
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["year", "week", "price_nok_per_kg", "volume_tonnes"])
        for r in deduped:
            writer.writerow([
                r["year"],
                r["week"],
                round(r["price"], 2),
                round(r["volume"], 1),
            ])

    log.info(
        "Done: %d weekly records written to %s",
        len(deduped),
        output_path,
    )
    if deduped:
        first = deduped[0]
        last = deduped[-1]
        log.info(
            "  Range: %dW%02d (%.2f NOK/kg) -> %dW%02d (%.2f NOK/kg)",
            first["year"], first["week"], first["price"],
            last["year"], last["week"], last["price"],
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
