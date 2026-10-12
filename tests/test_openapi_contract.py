"""
OpenAPI drift guard (arch report §7.3).

The live FastAPI schema must match docs/openapi.frozen.json exactly. Any
unintended API change (missing/renamed route, dropped response_model, changed
parameter) fails here — with a one-line fix for intentional changes:

    python scripts/freeze_openapi.py   # then review the diff and commit

This complements the generated TS client (frontend/src/types/generated.ts):
freeze -> review -> regenerate types keeps the whole chain in sync.
"""
import json
from pathlib import Path

from core.api import app

FROZEN = Path(__file__).resolve().parent.parent / "docs" / "openapi.frozen.json"


def _diff_summary(live: dict, frozen: dict) -> str:
    live_paths = set(live.get("paths", {}))
    frozen_paths = set(frozen.get("paths", {}))
    added = sorted(live_paths - frozen_paths)
    removed = sorted(frozen_paths - live_paths)
    parts = []
    if removed:
        parts.append(f"REMOVED paths: {removed[:5]}{'...' if len(removed) > 5 else ''}")
    if added:
        parts.append(f"ADDED paths: {added[:5]}{'...' if len(added) > 5 else ''}")
    if not parts:
        parts.append("paths match but schema details changed (fields/params/responses)")
    return "; ".join(parts)


def test_openapi_matches_frozen_contract():
    assert FROZEN.exists(), (
        "docs/openapi.frozen.json missing — run: python scripts/freeze_openapi.py"
    )
    frozen = json.loads(FROZEN.read_text(encoding="utf-8"))
    live = json.loads(json.dumps(app.openapi(), sort_keys=True))

    # Strip the informational version so platform bumps don't trip the guard;
    # schema shape is what this test protects.
    live.get("info", {}).pop("version", None)
    frozen.get("info", {}).pop("version", None)

    if live != frozen:
        raise AssertionError(
            "OpenAPI drifted from docs/openapi.frozen.json: "
            + _diff_summary(live, frozen)
            + "\nIntentional? run: python scripts/freeze_openapi.py and commit the diff."
        )
