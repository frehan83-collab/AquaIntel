#!/usr/bin/env python3
"""
Figma → Code Token Sync Pipeline
=================================
Pulls design tokens from a Figma file via the REST API,
maps them to the local figma-tokens.json format, and
regenerates all downstream outputs (CSS, TypeScript, Tailwind).

Usage:
    python scripts/sync_figma_tokens.py
    python scripts/sync_figma_tokens.py --file-key YOUR_FIGMA_FILE_KEY
    python scripts/sync_figma_tokens.py --dry-run  # Show diff without writing

Environment:
    FIGMA_ACCESS_TOKEN — Required. Personal access token from figma.com/developers
    FIGMA_FILE_KEY     — Optional. Defaults to the project's design system file.
"""

import asyncio
import json
import os
import sys
import argparse
import difflib
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

TOKENS_FILE = PROJECT_ROOT / "docs" / "figma-tokens.json"
DEFAULT_FILE_KEY = os.getenv("FIGMA_FILE_KEY", "UklcflWFBHal5xPSrSQolq")


def _rgb_to_hex(r: float, g: float, b: float) -> str:
    """Convert Figma 0-1 RGB floats to #RRGGBB hex."""
    return f"#{int(r * 255):02X}{int(g * 255):02X}{int(b * 255):02X}"


def _map_figma_styles_to_tokens(styles: dict, file_data: dict) -> dict:
    """
    Map Figma file styles to our token format.

    Figma styles include fills (colors), text styles (typography),
    and effects (shadows). We extract what we can and merge with
    existing tokens for anything Figma doesn't cover.
    """
    tokens = {}

    # Extract color styles from the file tree
    if "styles" in file_data:
        for style_id, style_meta in file_data.get("styles", {}).items():
            name = style_meta.get("name", "")
            style_type = style_meta.get("styleType", "")

            if style_type == "FILL":
                # Map Figma style names to our token paths
                # e.g., "colors/accent" → {"colors": {"accent": "#00D4C8"}}
                path = name.replace("/", ".").replace(" ", "_").lower()
                tokens[path] = {"type": "color", "figma_style_id": style_id, "name": name}

    # Extract local variables if available (Enterprise/Org plan)
    # These map more directly to design tokens
    return tokens


def _map_figma_variables_to_tokens(variables_data: dict) -> dict:
    """Map Figma local variables to our token format."""
    tokens = {}

    if not variables_data or "meta" not in variables_data:
        return tokens

    variables = variables_data["meta"].get("variables", {})

    for var_id, var_data in variables.items():
        name = var_data.get("name", "")
        resolved_type = var_data.get("resolvedType", "")

        # Get the value from the default mode
        values_by_mode = var_data.get("valuesByMode", {})
        if not values_by_mode:
            continue

        # Use first mode as default value
        first_mode_id = next(iter(values_by_mode), None)
        if not first_mode_id:
            continue

        value = values_by_mode[first_mode_id]

        if resolved_type == "COLOR" and isinstance(value, dict):
            hex_color = _rgb_to_hex(
                value.get("r", 0),
                value.get("g", 0),
                value.get("b", 0),
            )
            path = name.replace("/", ".").replace(" ", "_").lower()
            tokens[path] = {
                "type": "color",
                "value": hex_color,
                "opacity": value.get("a", 1.0),
            }
        elif resolved_type == "FLOAT":
            path = name.replace("/", ".").replace(" ", "_").lower()
            tokens[path] = {
                "type": "number",
                "value": value,
            }
        elif resolved_type == "STRING":
            path = name.replace("/", ".").replace(" ", "_").lower()
            tokens[path] = {
                "type": "string",
                "value": value,
            }

    return tokens


def _merge_tokens(existing: dict, figma_tokens: dict) -> dict:
    """
    Merge Figma-sourced tokens into existing token file.
    Figma tokens override existing values for matching paths.
    Existing tokens not in Figma are preserved.
    """
    merged = json.loads(json.dumps(existing))  # deep copy

    for path, token_data in figma_tokens.items():
        parts = path.split(".")
        target = merged

        # Navigate to the parent
        for part in parts[:-1]:
            if part not in target:
                target[part] = {}
            target = target[part]

        # Update the value
        key = parts[-1]
        if "value" in token_data:
            if isinstance(target.get(key), dict) and "value" in target[key]:
                target[key]["value"] = token_data["value"]
            else:
                target[key] = token_data["value"]

    return merged


def _compute_diff(old_json: str, new_json: str) -> str:
    """Compute a readable diff between old and new token files."""
    old_lines = old_json.splitlines(keepends=True)
    new_lines = new_json.splitlines(keepends=True)
    diff = difflib.unified_diff(old_lines, new_lines, fromfile="before", tofile="after", n=2)
    return "".join(diff)


async def sync_tokens(file_key: str, dry_run: bool = False) -> dict:
    """
    Main sync function: Figma API → figma-tokens.json → all outputs.

    Returns dict with sync results.
    """
    from core.integrations.figma_client import figma_client

    if not figma_client.is_configured:
        return {
            "status": "skipped",
            "reason": "FIGMA_ACCESS_TOKEN not set. Set it to enable Figma sync.",
            "tokens_changed": 0,
        }

    print(f"[sync] Connecting to Figma API for file {file_key}...")

    # Load existing tokens
    existing_tokens = {}
    if TOKENS_FILE.exists():
        existing_tokens = json.loads(TOKENS_FILE.read_text(encoding="utf-8"))
    old_json = json.dumps(existing_tokens, indent=2, sort_keys=True)

    # Fetch from Figma
    figma_tokens = {}

    try:
        # 1. Try variables first (most direct token mapping)
        print("[sync] Fetching Figma variables...")
        variables = await figma_client.get_local_variables(file_key)
        var_tokens = _map_figma_variables_to_tokens(variables)
        figma_tokens.update(var_tokens)
        print(f"[sync]   → {len(var_tokens)} variable tokens found")
    except Exception as e:
        print(f"[sync]   → Variables not available ({e.__class__.__name__}: {e})")

    try:
        # 2. Fetch file styles (colors, text styles)
        print("[sync] Fetching Figma styles...")
        file_data = await figma_client.get_file(file_key)
        styles = await figma_client.get_file_styles(file_key)
        style_tokens = _map_figma_styles_to_tokens(styles, file_data)
        figma_tokens.update(style_tokens)
        print(f"[sync]   → {len(style_tokens)} style tokens found")
    except Exception as e:
        print(f"[sync]   → Styles fetch failed ({e.__class__.__name__}: {e})")

    if not figma_tokens:
        print("[sync] No tokens extracted from Figma. Using existing tokens.")
        return {
            "status": "no_changes",
            "reason": "No extractable tokens from Figma file",
            "tokens_changed": 0,
            "figma_stats": figma_client.stats,
        }

    # Merge with existing
    merged = _merge_tokens(existing_tokens, figma_tokens)
    new_json = json.dumps(merged, indent=2, sort_keys=True)

    # Compute diff
    diff = _compute_diff(old_json, new_json)
    changes = diff.count("\n+") + diff.count("\n-") if diff else 0

    if not diff:
        print("[sync] Tokens are already in sync with Figma.")
        return {
            "status": "in_sync",
            "tokens_changed": 0,
            "figma_stats": figma_client.stats,
        }

    print(f"\n[sync] Token diff ({changes} lines changed):")
    print(diff[:2000])  # Truncate large diffs

    if dry_run:
        print("\n[sync] DRY RUN — no files written.")
        return {
            "status": "dry_run",
            "tokens_changed": changes,
            "diff": diff[:2000],
            "figma_stats": figma_client.stats,
        }

    # Write merged tokens
    TOKENS_FILE.write_text(new_json + "\n", encoding="utf-8")
    print(f"\n[sync] Updated {TOKENS_FILE}")

    # Run the design token pipeline to regenerate all outputs
    print("[sync] Regenerating downstream outputs...")
    from scripts.design_token_pipeline import main as pipeline_main
    pipeline_main(["--format", "all"])

    print(f"\n[sync] Done! {changes} token changes applied.")

    # Close the client
    await figma_client.close()

    return {
        "status": "updated",
        "tokens_changed": changes,
        "figma_stats": figma_client.stats,
    }


def main():
    parser = argparse.ArgumentParser(description="Sync design tokens from Figma")
    parser.add_argument("--file-key", default=DEFAULT_FILE_KEY, help="Figma file key")
    parser.add_argument("--dry-run", action="store_true", help="Show diff without writing")
    args = parser.parse_args()

    result = asyncio.run(sync_tokens(args.file_key, args.dry_run))

    print(f"\nResult: {json.dumps(result, indent=2)}")

    if result["status"] == "skipped":
        print("\nTo enable Figma sync, set FIGMA_ACCESS_TOKEN:")
        print("  export FIGMA_ACCESS_TOKEN=your_token_here")
        sys.exit(0)

    sys.exit(0 if result["status"] in ("in_sync", "updated", "no_changes", "dry_run") else 1)


if __name__ == "__main__":
    main()
