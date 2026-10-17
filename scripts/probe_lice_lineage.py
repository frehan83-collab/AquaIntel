"""WS-14 diagnostic: print the provenance of every lice-lineage consumer.

One GET per wired route through a TestClient, reporting ``is_live``,
``freshness``, the degradation reason and the lineage week — so a lineage
regression shows up as a wrong verdict, not as a plausible-looking payload.

Usage: ``python scripts/probe_lice_lineage.py`` (needs the app importable; the
routes degrade honestly on an unverified/demo DB, which is the expected output).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from core.api import app  # noqa: E402

PATHS = [
    "/api/welfare/score/12071",
    "/api/welfare/pa/3",
    "/api/leaders/top30",
    "/api/esg/summary",
    "/api/treatment/optimize/12071",
    "/api/treatment/network-schedule/3",
    "/api/compliance/asc/readiness-summary",
    "/api/global-supply",
    "/api/supply/demand-balance",
]


def main() -> None:
    client = TestClient(app)
    for path in PATHS:
        try:
            r = client.get(path)
        except Exception as exc:  # noqa: BLE001 — report, don't abort the sweep
            print(path, "EXC", type(exc).__name__, str(exc)[:120])
            continue
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        prov = body.get("data_provenance") if isinstance(body, dict) else None
        lineage = (body.get("lineage") or body.get("lice_lineage")) if isinstance(body, dict) else None
        print(
            path,
            r.status_code,
            json.dumps(
                {
                    "is_live": (prov or {}).get("is_live"),
                    "freshness": (prov or {}).get("freshness"),
                    "reason": (prov or {}).get("fallback_reason"),
                    "lineage_live": (lineage or {}).get("is_live"),
                    "lineage_week": (lineage or {}).get("latest_week"),
                    "rows": (lineage or {}).get("rows_used"),
                },
                default=str,
            )[:400],
        )


if __name__ == "__main__":
    main()