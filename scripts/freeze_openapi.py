"""Freeze the current FastAPI OpenAPI schema to docs/openapi.frozen.json.

Run after any intentional route/schema change; tests/test_openapi_contract.py
fails when the live schema drifts from the frozen copy, so unintended API
changes (removed routes, renamed fields, dropped response models) are caught
in CI instead of by the frontend at runtime.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")

from core.api import app  # noqa: E402

OUT = Path("docs/openapi.frozen.json")


def main() -> int:
    spec = app.openapi()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    n_paths = len(spec.get("paths", {}))
    print(f"froze {n_paths} paths -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
