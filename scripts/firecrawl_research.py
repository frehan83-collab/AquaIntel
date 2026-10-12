"""
Firecrawl research helper for the satellite / stack / MCP research workstreams.

Usage (from repo root):
    python scripts/firecrawl_research.py search "Sentinel-2 L2A pricing" --limit 5
    python scripts/firecrawl_research.py scrape "https://example.com/page" --out docs/raw/page.md
    python scripts/firecrawl_research.py search "ICEYE SAR pricing" --limit 5 --json --out docs/raw/iceye.json

Reads FIRECRAWL_API_KEY from environment or .env (never commit the key).
Uses the v2 API with graceful v1 fallback on 404.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://api.firecrawl.dev"


def load_key() -> str:
    key = os.getenv("FIRECRAWL_API_KEY", "").strip()
    if key:
        return key
    env = Path(".env")
    if env.exists():
        for line in env.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("FIRECRAWL_API_KEY="):
                return line.split("=", 1)[1].strip()
    sys.exit("FIRECRAWL_API_KEY not set (env or .env)")


def call(version: str, endpoint: str, payload: dict) -> dict:
    req = urllib.request.Request(
        f"{BASE}/{version}/{endpoint}",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {load_key()}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:1500]
        if exc.code == 404 and version == "v2":
            return call("v1", endpoint, payload)
        return {"error": exc.code, "body": body}
    except Exception as exc:  # network/timeout
        return {"error": "network", "body": str(exc)[:300]}


def main() -> int:
    ap = argparse.ArgumentParser(description="Firecrawl research helper")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("search", help="Web search via Firecrawl")
    sp.add_argument("query")
    sp.add_argument("--limit", type=int, default=5)
    sp.add_argument("--json", action="store_true", help="Full JSON output")
    sp.add_argument("--out", help="Write result to file")

    sc = sub.add_parser("scrape", help="Scrape one URL to markdown")
    sc.add_argument("url")
    sc.add_argument("--out", help="Write markdown to file")

    args = ap.parse_args()

    if args.cmd == "search":
        data = call("v2", "search", {"query": args.query, "limit": args.limit})
        if "error" in data:
            print(f"ERROR {data['error']}: {data.get('body', '')[:500]}")
            return 1
        if args.out:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(json.dumps(data, indent=2), encoding="utf-8")
        if args.json:
            print(json.dumps(data, indent=2)[:12000])
        else:
            for item in (data.get("data") or {}).get("web", data.get("data") or []):
                if isinstance(item, dict):
                    print(f"- {item.get('title', '?')}\n  {item.get('url', '')}\n  {(item.get('description') or '')[:160]}")
        return 0

    if args.cmd == "scrape":
        data = call("v2", "scrape", {"url": args.url, "formats": ["markdown"], "onlyMainContent": True})
        if "error" in data:
            print(f"ERROR {data['error']}: {data.get('body', '')[:500]}")
            return 1
        md = ((data.get("data") or {}).get("markdown") or "")
        if args.out:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(md, encoding="utf-8")
            print(f"wrote {len(md)} chars -> {args.out}")
        else:
            print(md[:8000])
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
