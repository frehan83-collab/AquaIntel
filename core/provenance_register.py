"""Rule-3 provenance register and ratchet.

AGENTS.md rule 3: *live data only — with `DataProvenance` on every engine
response.* The provenance sweep left a residue of routes that either carry
provenance, or are **explicitly exempt** because they return no measured data.

This module is the formal register of those exemptions, plus the ratchet that keeps
the boundary from silently eroding: `tests/test_provenance_ratchet.py` fails when a
route appears that is neither exempt here nor present in the frozen baseline. A new
route therefore cannot ship without someone making a *deliberate* provenance
decision, and every exemption carries a written reason.

Baseline: ``docs/provenance_baseline.json`` (regenerate with
``python scripts/provenance_ratchet.py --update`` after adding provenance).
"""
from __future__ import annotations

import json
from pathlib import Path

BASELINE_PATH = Path(__file__).resolve().parents[1] / "docs" / "provenance_baseline.json"

# Prefix → {category, reason}. Nothing here may return measured data.
EXEMPT: dict[str, dict[str, str]] = {
    "/api/health": {"category": "infrastructure", "reason": "liveness probe; returns no data"},
    "/api/openapi.json": {"category": "infrastructure", "reason": "schema document"},
    "/api/auth/": {"category": "auth_and_billing", "reason": "identity/session plumbing"},
    "/api/billing/": {
        "category": "auth_and_billing",
        "reason": "catalog and subscription state, not measured data",
    },
    "/api/keys": {"category": "auth_and_billing", "reason": "API-key management"},
    "/api/webhooks": {"category": "auth_and_billing", "reason": "webhook configuration"},
    "/api/entitlements": {
        "category": "catalogue_and_meta",
        "reason": "plan catalogue (prices/quotas), not data",
    },
    "/api/tiers": {"category": "catalogue_and_meta", "reason": "plan catalogue"},
    "/api/disclaimer": {"category": "catalogue_and_meta", "reason": "static legal text"},
    "/api/meta/": {"category": "catalogue_and_meta", "reason": "build/version metadata"},
    "/api/legal/": {
        "category": "catalogue_and_meta",
        "reason": "licence register and policy text",
    },
    "/api/accuracy/method": {
        "category": "publication_metadata",
        "reason": "artifact contract, not a measurement",
    },
    "/api/accuracy/artifacts": {
        "category": "publication_metadata",
        "reason": "artifact metadata (the artifact itself is the provenance)",
    },
    "/api/indices/methodology": {
        "category": "publication_metadata",
        "reason": "published method document",
    },
    "/api/data-freshness": {
        "category": "operational",
        "reason": "freshness metadata about other routes",
    },
    "/api/admin/": {
        "category": "admin",
        "reason": "admin operational endpoints (auth-gated)",
    },
    "/api/cache/": {"category": "admin", "reason": "cache administration (auth-gated)"},
    "/api/audit": {
        "category": "admin",
        "reason": "audit log (auth-gated, operational)",
    },
}

CATEGORIES = (
    "infrastructure",
    "auth_and_billing",
    "catalogue_and_meta",
    "publication_metadata",
    "operational",
    "admin",
)


def matching_exemption(path: str) -> dict | None:
    """Longest-prefix exemption for a path, or None."""
    best: tuple[str, dict] | None = None
    for prefix, entry in EXEMPT.items():
        if path == prefix or path.startswith(prefix):
            if best is None or len(prefix) > len(best[0]):
                best = (prefix, entry)
    if best is None:
        return None
    return {"prefix": best[0], **best[1]}


def is_exempt(path: str) -> bool:
    return matching_exemption(path) is not None


def data_routes() -> list[str]:
    """Every GET route under /api that could return data (sorted, unique)."""
    from core.api import app

    paths: set[str] = set()
    for route in app.routes:
        methods = getattr(route, "methods", None) or set()
        path = getattr(route, "path", "")
        if "GET" in methods and path.startswith("/api") and "{" not in path:
            paths.add(path)
    return sorted(paths)


def load_baseline() -> dict:
    if not BASELINE_PATH.exists():
        return {"version": None, "registered": []}
    try:
        return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"version": None, "registered": [], "error": "unreadable"}


def inventory() -> dict:
    """The current picture: exempt, registered (baselined), and unregistered."""
    routes = data_routes()
    exempt = [p for p in routes if is_exempt(p)]
    known = set(load_baseline().get("registered", []))
    registered = [p for p in routes if not is_exempt(p) and p in known]
    unregistered = [p for p in routes if not is_exempt(p) and p not in known]
    return {
        "total": len(routes),
        "exempt": exempt,
        "registered": registered,
        "unregistered": unregistered,
        "baseline_version": load_baseline().get("version"),
    }


def write_baseline(note: str = "") -> dict:
    """Freeze the current non-exempt route set (after a provenance decision)."""
    data = inventory()
    frozen = sorted(data["registered"] + data["unregistered"])
    payload = {
        "version": "1.0",
        "note": note
        or (
            "Non-exempt /api GET routes. A route may only be added here after a "
            "deliberate provenance decision (provenance attached, or an exemption "
            "added to core/provenance_register.py). Regenerate with "
            "`python scripts/provenance_ratchet.py --update`."
        ),
        "counts": {
            "total_routes": data["total"],
            "exempt": len(data["exempt"]),
            "registered": len(frozen),
        },
        "exempt_prefixes": sorted(EXEMPT),
        "registered": frozen,
    }
    BASELINE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload