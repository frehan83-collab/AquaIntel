"""Accuracy & Method registry — versioned, published metric artifacts.

The honesty rule (AGENTS.md #1) forbids displaying MAPE/coverage unless a *real
artifact* produced it. This module is that artifact store: a tracked directory of
JSON files, each validated against a published schema, each carrying the model,
the target, the evaluation method, the sample size, the metrics, when it was
produced and **whether a fallback was used**.

Published artifacts live in ``artifacts/accuracy/`` — deliberately NOT under
``data/`` (which is gitignored), because a published accuracy claim that exists
only on one developer's laptop is exactly the kind of claim this platform refuses
to make. ``scripts/publish_accuracy.py`` regenerates them from real data.

Nothing here fabricates a number: an empty registry is reported as empty.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import structlog

log = structlog.get_logger(__name__)

ARTIFACT_SCHEMA_VERSION = "1.0"
ARTIFACT_DIR = Path("artifacts/accuracy")

# Every artifact must carry these (the contract published at /api/accuracy/method).
REQUIRED_KEYS = (
    "artifact_id",
    "schema_version",
    "model",
    "target",
    "method",
    "window",
    "n_obs",
    "metrics",
    "produced_at",
    "source",
    "fallback_used",
)
REQUIRED_METRICS = ("mape_pct",)


def validate(artifact: dict) -> list[str]:
    """Return a list of problems (empty = valid). Never silent about a gap."""
    problems: list[str] = []
    for key in REQUIRED_KEYS:
        if key not in artifact:
            problems.append(f"missing key '{key}'")
    if artifact.get("schema_version") not in (None, ARTIFACT_SCHEMA_VERSION):
        problems.append(
            f"schema_version '{artifact.get('schema_version')}' != {ARTIFACT_SCHEMA_VERSION}"
        )
    metrics = artifact.get("metrics")
    if not isinstance(metrics, dict):
        problems.append("metrics must be an object")
    else:
        for key in REQUIRED_METRICS:
            if key not in metrics:
                problems.append(f"metrics missing '{key}'")
            elif not isinstance(metrics[key], (int, float)):
                problems.append(f"metrics.{key} must be numeric")
    if "fallback_used" in artifact and not isinstance(artifact["fallback_used"], bool):
        problems.append("fallback_used must be a boolean")
    if "n_obs" in artifact and not isinstance(artifact["n_obs"], int):
        problems.append("n_obs must be an integer")
    if "produced_at" in artifact:
        try:
            dt.datetime.fromisoformat(str(artifact["produced_at"]))
        except ValueError:
            problems.append("produced_at must be ISO-8601")
    return problems


def publish(artifact: dict) -> dict:
    """Validate and write one artifact. Raises ValueError when invalid."""
    artifact = {**artifact, "schema_version": artifact.get("schema_version", ARTIFACT_SCHEMA_VERSION)}
    problems = validate(artifact)
    if problems:
        raise ValueError("invalid accuracy artifact: " + "; ".join(problems))
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    path = ARTIFACT_DIR / f"{artifact['artifact_id']}.json"
    path.write_text(json.dumps(artifact, indent=2, sort_keys=True), encoding="utf-8")
    log.info("accuracy_artifact_published", artifact_id=artifact["artifact_id"], path=str(path))
    return {"path": str(path), "artifact_id": artifact["artifact_id"]}


def _load_all() -> tuple[list[dict], list[dict]]:
    valid: list[dict] = []
    invalid: list[dict] = []
    if not ARTIFACT_DIR.exists():
        return valid, invalid
    for path in sorted(ARTIFACT_DIR.glob("*.json")):
        try:
            artifact = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            invalid.append({"path": path.name, "problems": [f"unreadable: {exc}"]})
            continue
        problems = validate(artifact)
        if problems:
            invalid.append({"path": path.name, "problems": problems})
        else:
            artifact["_path"] = path.name
            valid.append(artifact)
    valid.sort(key=lambda a: str(a.get("produced_at", "")), reverse=True)
    return valid, invalid


def registry() -> dict:
    """All published artifacts, plus anything invalid (reported, not hidden)."""
    valid, invalid = _load_all()
    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "directory": str(ARTIFACT_DIR),
        "count": len(valid),
        "artifacts": valid,
        "invalid": invalid,
    }


def has_published_metrics() -> bool:
    """True only when at least one real, valid artifact exists."""
    valid, _ = _load_all()
    return bool(valid)


def summary() -> dict:
    """Honest rollup: what is published, what used a fallback, what is missing."""
    valid, invalid = _load_all()
    surfaces = [
        {
            "artifact_id": a["artifact_id"],
            "model": a["model"],
            "target": a["target"],
            "method": a["method"],
            "window": a["window"],
            "n_obs": a["n_obs"],
            "mape_pct": a["metrics"].get("mape_pct"),
            "coverage_pct": a["metrics"].get("coverage_pct"),
            "fallback_used": a["fallback_used"],
            "produced_at": a["produced_at"],
            "source": a["source"],
        }
        for a in valid
    ]
    return {
        "published": len(valid),
        "invalid": len(invalid),
        "fallback_used_count": sum(1 for a in valid if a["fallback_used"]),
        "surfaces": surfaces,
        "invalid_artifacts": invalid,
        "note": (
            "Only these artifacts may back a published accuracy claim. Fewer than "
            "expected means the corresponding product surface must say "
            "'not yet published' rather than estimate."
        ),
    }
