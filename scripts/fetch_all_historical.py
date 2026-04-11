#!/usr/bin/env python3
"""
Fetch All Historical Data for ML Training
==========================================
Master script that runs all historical data fetchers in sequence.

Datasets:
  1. SSB 03024 — Weekly salmon export prices (2000-present, ~1300 weeks)
  2. FRED — Monthly commodity prices (1990-present, ~430 obs x 6 series)
  3. Fish Pool Index — Weekly spot prices (2006-2024, ~950 weeks)

Total: ~5000+ data points across 3 sources for TimesFM/Chronos/MOIRAI training.

Prerequisites:
  - pip install httpx (already in requirements.txt)
  - FRED_API_KEY env var set (free: https://fred.stlouisfed.org/docs/api/api_key.html)

Usage:
    python scripts/fetch_all_historical.py
    python scripts/fetch_all_historical.py --skip-fred   # if no API key
    python scripts/fetch_all_historical.py --dry-run     # show what would be fetched
"""
from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("fetch_all")

SCRIPTS_DIR = Path(__file__).resolve().parent


def run_script(name: str, args: list[str] | None = None) -> bool:
    """Run a fetcher script as a subprocess. Returns True on success."""
    script_path = SCRIPTS_DIR / name
    if not script_path.exists():
        log.error("Script not found: %s", script_path)
        return False

    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)

    log.info("=" * 60)
    log.info("Running: %s", " ".join(cmd))
    log.info("=" * 60)

    t0 = time.time()
    result = subprocess.run(cmd, capture_output=False)
    elapsed = time.time() - t0

    if result.returncode == 0:
        log.info("Completed %s in %.1f seconds", name, elapsed)
        return True
    else:
        log.error("FAILED %s (exit code %d) after %.1f seconds", name, result.returncode, elapsed)
        return False


def check_output_file(path: Path) -> str:
    """Check if output file exists and return summary."""
    if not path.exists():
        return "NOT FOUND"
    size = path.stat().st_size
    # Count lines
    with open(path, "r", encoding="utf-8") as f:
        lines = sum(1 for _ in f) - 1  # subtract header
    if size < 1024:
        size_str = f"{size} bytes"
    elif size < 1024 * 1024:
        size_str = f"{size / 1024:.1f} KB"
    else:
        size_str = f"{size / (1024 * 1024):.1f} MB"
    return f"{lines} records, {size_str}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch all historical data for ML training"
    )
    parser.add_argument(
        "--skip-ssb",
        action="store_true",
        help="Skip SSB 03024 price fetch",
    )
    parser.add_argument(
        "--skip-fred",
        action="store_true",
        help="Skip FRED commodity fetch (use if no API key)",
    )
    parser.add_argument(
        "--skip-fishpool",
        action="store_true",
        help="Skip Fish Pool Index fetch",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be fetched without actually fetching",
    )
    args = parser.parse_args()

    data_dir = SCRIPTS_DIR.parent / "data" / "historical"
    data_dir.mkdir(parents=True, exist_ok=True)

    tasks = []
    if not args.skip_ssb:
        tasks.append(("fetch_historical_ssb_prices.py", [], "SSB 03024 salmon prices"))
    if not args.skip_fred:
        if not os.environ.get("FRED_API_KEY"):
            log.warning(
                "FRED_API_KEY not set — FRED fetch will fail. "
                "Use --skip-fred or set the env var."
            )
        tasks.append(("fetch_historical_fred.py", [], "FRED commodity prices"))
    if not args.skip_fishpool:
        tasks.append(("fetch_historical_fishpool.py", [], "Fish Pool Index"))

    if not tasks:
        log.info("All fetchers skipped. Nothing to do.")
        return 0

    log.info("FishIntel Historical Data Fetcher")
    log.info("=" * 60)
    log.info("Tasks: %d", len(tasks))
    for script, _, desc in tasks:
        log.info("  - %s (%s)", desc, script)
    log.info("Output: %s", data_dir)
    log.info("")

    if args.dry_run:
        log.info("DRY RUN — no data will be fetched.")
        return 0

    t0_total = time.time()
    results: dict[str, bool] = {}

    for script, extra_args, desc in tasks:
        log.info("")
        success = run_script(script, extra_args)
        results[desc] = success
        log.info("")

    elapsed_total = time.time() - t0_total

    # Final summary
    log.info("")
    log.info("=" * 60)
    log.info("SUMMARY — Total time: %.1f seconds", elapsed_total)
    log.info("=" * 60)

    for desc, success in results.items():
        status = "OK" if success else "FAILED"
        log.info("  [%s] %s", status, desc)

    # Check output files
    log.info("")
    log.info("Output files:")
    for f in sorted(data_dir.glob("*.csv")):
        summary = check_output_file(f)
        log.info("  %s — %s", f.name, summary)

    failed = sum(1 for v in results.values() if not v)
    if failed:
        log.warning("%d of %d fetchers failed.", failed, len(results))
        return 1

    log.info("All %d fetchers completed successfully.", len(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
