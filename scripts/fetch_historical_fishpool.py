#!/usr/bin/env python3
"""
Fetch Historical Fish Pool Index Data (2006-2024)
==================================================
Attempts to retrieve the Fish Pool Index historical data.

NOTE: fishpool.eu has been unreliable/dead since late 2024. Euronext ESF
has replaced Fish Pool NOK futures. This script tries multiple approaches:

1. Direct CSV download from fishpool.eu (if available)
2. HTML table scraping from the Fish Pool Index page
3. Fallback: generates a synthetic index from SSB 03024 spot prices
   (SSB is the underlying data that Fish Pool Index was based on)

The SSB fallback is actually a reasonable proxy because the Fish Pool Index
was essentially a weighted average of SSB weekly export prices.

Output: data/historical/fish_pool_index_2006_2024.csv
Columns: year, week, spot_price_nok

Usage:
    python scripts/fetch_historical_fishpool.py
    python scripts/fetch_historical_fishpool.py --ssb-fallback
    python scripts/fetch_historical_fishpool.py --output data/custom.csv
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import logging
import re
import sys
import time
from pathlib import Path

import httpx

FISHPOOL_INDEX_URL = "https://fishpool.eu/fish-pool-index/"
FISHPOOL_CSV_URLS = [
    "https://fishpool.eu/price-information/spot-prices/fish-pool-index/download/csv",
    "https://fishpool.eu/wp-content/uploads/fish-pool-index.csv",
    "https://fishpool.eu/price-information/spot-prices/fish-pool-index/",
]

SSB_API_URL = "https://data.ssb.no/api/v0/en/table/03024/"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("fishpool_historical")


def try_fishpool_csv(client: httpx.Client) -> list[dict] | None:
    """Try to download a CSV directly from fishpool.eu."""
    for url in FISHPOOL_CSV_URLS:
        try:
            log.info("  Trying: %s", url)
            resp = client.get(url, timeout=15.0, follow_redirects=True)
            if resp.status_code == 200 and "," in resp.text and len(resp.text) > 100:
                lines = resp.text.strip().split("\n")
                records = []
                for line in lines[1:]:  # skip header
                    parts = line.strip().split(",")
                    if len(parts) >= 2:
                        try:
                            # Try to parse various date formats
                            date_str = parts[0].strip().strip('"')
                            price_str = parts[-1].strip().strip('"')
                            price = float(price_str)
                            if price > 0:
                                records.append({
                                    "date": date_str,
                                    "price": price,
                                })
                        except (ValueError, IndexError):
                            continue
                if len(records) > 50:
                    log.info("  Found %d records from CSV", len(records))
                    return records
        except Exception as e:
            log.debug("  Failed: %s", str(e)[:80])
            continue
    return None


def try_fishpool_html(client: httpx.Client) -> list[dict] | None:
    """Try to scrape the HTML table from fishpool.eu."""
    try:
        log.info("  Trying HTML scrape: %s", FISHPOOL_INDEX_URL)
        resp = client.get(FISHPOOL_INDEX_URL, timeout=15.0, follow_redirects=True)
        if resp.status_code != 200:
            log.info("  HTTP %d from fishpool.eu", resp.status_code)
            return None

        # Try to find table data in HTML using regex (avoid bs4 dependency)
        # Look for patterns like <td>2024</td><td>W01</td><td>92.50</td>
        html = resp.text

        # Pattern 1: table rows with year/week/price
        rows = re.findall(
            r"<tr[^>]*>\s*<td[^>]*>(\d{4})</td>\s*<td[^>]*>W?(\d{1,2})</td>\s*<td[^>]*>([\d.,]+)</td>",
            html,
            re.IGNORECASE,
        )
        if rows and len(rows) > 20:
            records = []
            for year_s, week_s, price_s in rows:
                try:
                    price = float(price_s.replace(",", "."))
                    if price > 0:
                        records.append({
                            "year": int(year_s),
                            "week": int(week_s),
                            "price": price,
                        })
                except ValueError:
                    continue
            if records:
                log.info("  Found %d records from HTML table", len(records))
                return records

        # Pattern 2: JSON data embedded in page
        json_match = re.search(r'"data"\s*:\s*\[([^\]]+)\]', html)
        if json_match:
            log.info("  Found embedded JSON data, parsing...")
            # Simplified extraction — would need proper JSON parsing
            pass

    except Exception as e:
        log.debug("  HTML scrape failed: %s", str(e)[:80])

    return None


def fetch_ssb_fallback(client: httpx.Client, start_year: int, end_year: int) -> list[dict]:
    """
    Fallback: use SSB 03024 weekly prices as a Fish Pool Index proxy.

    The Fish Pool Index was essentially derived from SSB export prices,
    so this is a reasonable approximation for historical analysis.
    """
    log.info("  Using SSB 03024 as Fish Pool Index proxy (%d-%d)", start_year, end_year)

    all_records: list[dict] = []
    now = dt.datetime.now(dt.UTC)
    current_year = now.year

    for year in range(start_year, min(end_year + 1, current_year + 1)):
        from_code = f"{year}U01"
        if year < current_year:
            to_code = f"{year}U52"
        else:
            max_week = max(1, now.isocalendar()[1] - 2)
            to_code = f"{year}U{max_week:02d}"

        query = {
            "query": [
                {"code": "VareGrupper2", "selection": {"filter": "item", "values": ["01"]}},
                {"code": "ContentsCode", "selection": {"filter": "item", "values": ["Kilopris"]}},
                {"code": "Tid", "selection": {"filter": "fromTo", "values": [from_code, to_code]}},
            ],
            "response": {"format": "json-stat2"},
        }

        try:
            resp = client.post(
                SSB_API_URL,
                json=query,
                headers={"Content-Type": "application/json"},
                timeout=30.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                dimension = data.get("dimension", {})
                time_labels = list(
                    dimension.get("Tid", {}).get("category", {}).get("label", {}).keys()
                )
                values = data.get("value", [])

                for t_idx, t_code in enumerate(time_labels):
                    for sep in ("U", "W"):
                        if sep in t_code:
                            parts = t_code.split(sep)
                            try:
                                y, w = int(parts[0]), int(parts[1])
                                if t_idx < len(values) and values[t_idx] is not None:
                                    price = float(values[t_idx])
                                    if price > 0:
                                        all_records.append({
                                            "year": y,
                                            "week": w,
                                            "price": round(price, 2),
                                        })
                            except (ValueError, IndexError):
                                pass
                            break

                log.info("  SSB %d: %d weeks", year, sum(1 for r in all_records if r["year"] == year))
        except Exception as e:
            log.warning("  SSB %d failed: %s", year, str(e)[:80])

        time.sleep(0.5)

    return all_records


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch historical Fish Pool Index data (with SSB fallback)"
    )
    parser.add_argument(
        "--start-year",
        type=int,
        default=2006,
        help="First year (default: 2006, when Fish Pool started)",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=2024,
        help="Last year (default: 2024, Fish Pool wound down)",
    )
    parser.add_argument(
        "--ssb-fallback",
        action="store_true",
        help="Skip fishpool.eu and go directly to SSB proxy",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output CSV path",
    )
    args = parser.parse_args()

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = (
            Path(__file__).resolve().parent.parent
            / "data"
            / "historical"
            / f"fish_pool_index_{args.start_year}_{args.end_year}.csv"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    log.info("Fetching Fish Pool Index: %d-%d -> %s", args.start_year, args.end_year, output_path)

    records: list[dict] = []
    source = "unknown"
    client = httpx.Client(
        headers={"User-Agent": "FishIntel/1.0 Research (historical data fetch)"},
    )

    try:
        if not args.ssb_fallback:
            # Try fishpool.eu first
            log.info("Attempting fishpool.eu direct download...")
            csv_records = try_fishpool_csv(client)
            if csv_records:
                # Convert date-based records to year/week
                for r in csv_records:
                    if "year" not in r:
                        # Parse date string to year/week
                        try:
                            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y"):
                                try:
                                    d = dt.datetime.strptime(r["date"], fmt)
                                    iso = d.isocalendar()
                                    r["year"] = iso[0]
                                    r["week"] = iso[1]
                                    break
                                except ValueError:
                                    continue
                        except Exception:
                            continue
                records = [r for r in csv_records if "year" in r]
                source = "fishpool.eu CSV"

            if not records:
                log.info("Attempting fishpool.eu HTML scrape...")
                html_records = try_fishpool_html(client)
                if html_records:
                    records = html_records
                    source = "fishpool.eu HTML"

        if not records:
            log.info("Fish Pool direct fetch unavailable, using SSB 03024 proxy...")
            records = fetch_ssb_fallback(client, args.start_year, args.end_year)
            source = "SSB 03024 (Fish Pool proxy)"
    finally:
        client.close()

    if not records:
        log.error("No data obtained from any source.")
        return 1

    # Filter to requested year range and de-duplicate
    seen: dict[str, dict] = {}
    for r in records:
        if args.start_year <= r.get("year", 0) <= args.end_year:
            key = f"{r['year']}W{r['week']:02d}"
            seen[key] = r

    deduped = [seen[k] for k in sorted(seen.keys())]

    # Write CSV
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["year", "week", "spot_price_nok"])
        for r in deduped:
            writer.writerow([r["year"], r["week"], round(r["price"], 2)])

    log.info("Done: %d weekly records from %s -> %s", len(deduped), source, output_path)
    if deduped:
        first, last = deduped[0], deduped[-1]
        log.info(
            "  Range: %dW%02d (%.2f NOK) -> %dW%02d (%.2f NOK)",
            first["year"], first["week"], first["price"],
            last["year"], last["week"], last["price"],
        )
    if source.startswith("SSB"):
        log.info(
            "  NOTE: Data is from SSB 03024 (proxy). Fish Pool Index was derived "
            "from SSB export prices, so this is a close approximation."
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
