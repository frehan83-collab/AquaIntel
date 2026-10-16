"""Route liveness probe — measure, don't assert.

The platform's selling point is *live, traceable* data, and AGENTS.md rule 1
forbids presenting synthetic/fallback output as live. Today that is asserted in
prose (115 `DataProvenance.live(` sites vs 7 `simulated(`), not measured:
`/api/market/biomass` advertised a "national biomass and supply model" while
returning hardcoded placeholders.

This walks every registered GET route with no path parameters, calls it
in-process, and records the provenance the response actually carries. It
changes nothing.

Outputs: docs/REPORT_LIVENESS.md + docs/liveness_report.json
Usage:  python scripts/probe_liveness.py [--timeout 12] [--concurrency 8]
        [--limit N] [--only /api/market]
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import os
import sys
from pathlib import Path

# Mirror tests/conftest.py: raise the limiter *before* core.api import so the
# burst is not itself rate-limited (would poison results); quotas off.
os.environ.setdefault("FISHINTEL_RATE_LIMIT", "100000/minute")
os.environ.setdefault("FISHINTEL_ENFORCE_QUOTAS", "0")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402
from fastapi.routing import APIRoute  # noqa: E402

from core.api import app  # noqa: E402
from core.models import init_db  # noqa: E402

REPORT_MD = ROOT / "docs" / "REPORT_LIVENESS.md"
REPORT_JSON = ROOT / "docs" / "liveness_report.json"
_PROV_KEYS = ("data_provenance", "provenance")


def _collect_routes(only: str | None) -> list[str]:
    paths: list[str] = []
    for route in app.routes:
        if not isinstance(route, APIRoute) or "GET" not in (route.methods or set()):
            continue
        path = route.path
        if "{" in path or path.startswith("/api/test"):
            continue
        if only and only not in path:
            continue
        paths.append(path)
    return sorted(set(paths))


def _walk_provenance(node, found: list[dict]) -> None:
    """Collect any provenance-shaped dict anywhere in the payload."""
    if isinstance(node, dict):
        if isinstance(node.get("is_live"), bool):
            found.append(node)
        else:
            for k in _PROV_KEYS:
                if k in node:
                    _walk_provenance(node[k], found)
            for v in node.values():
                if isinstance(v, (dict, list)):
                    _walk_provenance(v, found)
    elif isinstance(node, list):
        for v in node:
            _walk_provenance(v, found)


def _classify(status: int | None, prov: dict | None, error: str | None) -> str:
    if error:
        return "error"
    if status is None:
        return "unknown"
    if status == 401:
        return "auth_401"
    if status == 403:
        return "auth_403"
    if status == 404:
        return "not_found"
    if status >= 500:
        return "http_5xx"
    if status != 200:
        return f"http_{status}"
    if not prov:
        return "no_provenance"
    if str(prov.get("source", "")).lower() == "simulated":
        return "simulated"
    return "live" if prov.get("is_live") is True else "degraded"


async def _probe_one(client: httpx.AsyncClient, path: str, timeout: float, sem: asyncio.Semaphore) -> dict:
    async with sem:
        started = dt.datetime.now(dt.UTC)
        status: int | None = None
        error: str | None = None
        provs: list[dict] = []
        try:
            resp = await asyncio.wait_for(client.get(path), timeout=timeout)
            status = resp.status_code
            try:
                _walk_provenance(resp.json(), provs)
            except Exception:
                provs = []
        except asyncio.TimeoutError:
            error = "timeout"
        except Exception as exc:  # noqa: BLE001 - a probe must never abort the sweep
            error = f"{type(exc).__name__}: {str(exc)[:120]}"
        elapsed = (dt.datetime.now(dt.UTC) - started).total_seconds()
        order = {"simulated": 0, "degraded": 1, "live": 2}
        prov = min(provs, key=lambda p: order.get(_classify(200, p, None), 3)) if provs else None
        return {
            "path": path,
            "status": status,
            "elapsed_s": round(elapsed, 2),
            "state": _classify(status, prov, error),
            "source": (prov or {}).get("source"),
            "is_live": (prov or {}).get("is_live"),
            "fallback_reason": (prov or {}).get("fallback_reason"),
            "provenance_count": len(provs),
            "error": error,
        }


async def main() -> int:
    ap = argparse.ArgumentParser(description="Probe every GET route's data provenance.")
    ap.add_argument("--timeout", type=float, default=12.0, help="per-request timeout (s)")
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0, help="cap routes probed (0 = all)")
    ap.add_argument("--only", default=None, help="path substring filter")
    args = ap.parse_args()

    init_db()
    paths = _collect_routes(args.only)
    if args.limit:
        paths = paths[: args.limit]
    print(f"probing {len(paths)} parameterless GET routes (timeout={args.timeout}s)...")

    sem = asyncio.Semaphore(args.concurrency)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://probe", timeout=args.timeout) as client:
        rows = await asyncio.gather(*(_probe_one(client, p, args.timeout, sem) for p in paths))

    rows = sorted(rows, key=lambda r: (r["state"], r["path"]))
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["state"]] = counts.get(r["state"], 0) + 1

    REPORT_JSON.write_text(
        json.dumps({"generated_at": dt.datetime.now(dt.UTC).isoformat(), "counts": counts, "rows": rows}, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# Route Liveness Report",
        "",
        f"> Generated {dt.datetime.now(dt.UTC).strftime('%Y-%m-%d %H:%M UTC')} by `scripts/probe_liveness.py`.",
        "> Parameterless GET routes only. The weakest nested provenance governs a",
        "> route's headline state, so the report is conservative.",
        "",
        "## Summary",
        "",
        "| State | Routes |",
        "|---|---|",
    ]
    for state in sorted(counts, key=lambda s: counts[s], reverse=True):
        lines.append(f"| `{state}` | {counts[state]} |")
    lines += ["", f"**Probed:** {len(rows)} routes.", "", "## Not claiming live", "",
              "| Path | State | HTTP | Source | Reason |", "|---|---|---|---|---|"]
    for r in rows:
        if r["state"] == "live":
            continue
        reason = (r.get("fallback_reason") or r.get("error") or "")[:110]
        lines.append(f"| `{r['path']}` | {r['state']} | {r['status']} | {r.get('source') or ''} | {reason} |")
    lines += ["", "## Claiming live", "", "| Path | Source |", "|---|---|"]
    for r in rows:
        if r["state"] == "live":
            lines.append(f"| `{r['path']}` | {r.get('source') or ''} |")
    lines += [
        "",
        "## Known limitations & backlog",
        "",
        "- **Timeouts** are the bulk of `error`: they are network-bound upstreams",
        "  (CMEMS/DFO/DNS-blocked hosts on this box), not necessarily broken in",
        "  production. Re-run where the upstreams are reachable.",
        "- **`no_provenance`** routes return data with no provenance envelope at all;",
        "  each needs an audit against AGENTS.md rule 3 (source + freshness on every",
        "  number shown to users).",
        "- **HTTP 503 is used honestly** by model-backed routes (`torch_geometric not",
        "  installed`, TFT weights missing) — degraded, not a bug.",
        "- Parametrised routes (path parameters) are not probed; add fixtures before",
        "  trusting coverage.",
        "",
    ]
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(counts, indent=2))
    print(f"wrote {REPORT_MD.relative_to(ROOT)} and {REPORT_JSON.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
