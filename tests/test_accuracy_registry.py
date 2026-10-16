"""Accuracy & Method contract tests (hardening §4).

The rule under test: a MAPE/coverage number may appear only if a REAL artifact
produced it, artifacts are validated against a published schema, demo/synthetic
rows can never back a claim, and an empty registry is reported as empty.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from core.api import app
from core.ml import accuracy_registry as reg

ROOT = Path(__file__).resolve().parents[1]


def _load_publish_script():
    spec = importlib.util.spec_from_file_location(
        "publish_accuracy", ROOT / "scripts" / "publish_accuracy.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def isolated_registry(monkeypatch, tmp_path):
    monkeypatch.setattr(reg, "ARTIFACT_DIR", tmp_path)
    return tmp_path


def _valid_artifact(**overrides) -> dict:
    artifact = {
        "artifact_id": "test_model",
        "schema_version": reg.ARTIFACT_SCHEMA_VERSION,
        "model": "unit-test model",
        "target": "test target",
        "method": "walk-forward",
        "window": "2025W01..2025W52",
        "n_obs": 52,
        "metrics": {"mape_pct": 7.5, "coverage_pct": 79.0},
        "produced_at": "2026-10-16T00:00:00+00:00",
        "source": "unit test",
        "fallback_used": False,
    }
    artifact.update(overrides)
    return artifact


class TestValidation:
    def test_valid_artifact_passes(self):
        assert reg.validate(_valid_artifact()) == []

    def test_missing_required_key_is_rejected(self):
        artifact = _valid_artifact()
        artifact.pop("model")
        assert any("model" in p for p in reg.validate(artifact))

    @pytest.mark.parametrize(
        "key,value",
        [
            ("metrics", {}),
            ("metrics", {"mape_pct": "7.5"}),
            ("fallback_used", "no"),
            ("n_obs", "52"),
            ("produced_at", "not-a-date"),
            ("schema_version", "0.1"),
        ],
    )
    def test_invalid_values_are_rejected(self, key, value):
        assert reg.validate(_valid_artifact(**{key: value})), key


class TestRegistry:
    def test_publish_then_read_back(self, isolated_registry):
        info = reg.publish(_valid_artifact())
        assert Path(info["path"]).exists()
        data = reg.registry()
        assert data["count"] == 1
        assert data["artifacts"][0]["artifact_id"] == "test_model"
        assert reg.has_published_metrics() is True

    def test_publish_refuses_an_invalid_artifact(self, isolated_registry):
        with pytest.raises(ValueError):
            reg.publish(_valid_artifact(metrics={}))

    def test_invalid_files_are_reported_not_hidden(self, isolated_registry):
        (isolated_registry / "broken.json").write_text(
            json.dumps({"artifact_id": "broken"}), encoding="utf-8"
        )
        assert reg.registry()["count"] == 0
        assert reg.registry()["invalid"], "invalid artifact must be reported"
        assert reg.summary()["invalid"] == 1

    def test_empty_registry_claims_nothing(self, isolated_registry):
        assert reg.has_published_metrics() is False
        assert reg.summary()["published"] == 0


class TestDemoSourceGuard:
    @pytest.mark.parametrize(
        "source,expected",
        [
            ("demo_seed", False),
            ("DEMO", False),
            ("synthetic", False),
            ("mock", False),
            ("", False),
            (None, False),
            ("ssb_api", True),
            ("SSB Table 03024", True),
        ],
    )
    def test_only_real_sources_count(self, source, expected):
        script = _load_publish_script()
        assert script._is_real_source(source) is expected

    def test_walk_forward_math_is_deterministic(self):
        """A known series must produce a known MAPE (no hidden randomness)."""
        script = _load_publish_script()
        series = [(2024, w, 100.0) for w in range(1, 53)] + [
            (2025, w, 110.0) for w in range(1, 53)
        ]
        pairs = script._seasonal_pairs(series)
        assert len(pairs) == 52
        # every 2025 point is forecast as the year-back 100.0 -> error of 10.0
        assert all(abs(a - f - 10.0) < 1e-9 for a, f in pairs)
        mape = sum(abs(a - f) / a for a, f in pairs) / len(pairs) * 100
        assert abs(mape - (10.0 / 110.0 * 100)) < 1e-6


class TestAccuracyEndpoints:
    def test_summary_never_invents_metrics(self, client, isolated_registry):
        body = client.get("/api/accuracy").json()
        assert body["published"] is False
        assert body["metrics"] == []
        assert "No accuracy artifact" in body["statement"]
        assert body["methodology_url"] == "/api/accuracy/method"
        assert body["fallback_disclosure"]["policy"]

    def test_published_artifact_is_surfaced(self, client, isolated_registry):
        reg.publish(_valid_artifact())
        body = client.get("/api/accuracy").json()
        assert body["published"] is True
        assert body["metrics"][0]["mape_pct"] == 7.5
        assert body["fallback_used_count"] == 0

    def test_fallback_artifacts_are_counted(self, client, isolated_registry):
        reg.publish(_valid_artifact(artifact_id="baseline", fallback_used=True))
        assert client.get("/api/accuracy").json()["fallback_used_count"] == 1

    def test_one_artifact_retrievable_verbatim(self, client, isolated_registry):
        reg.publish(_valid_artifact(artifact_id="retrievable"))
        body = client.get("/api/accuracy/artifacts/retrievable").json()
        assert body["artifact_id"] == "retrievable"
        assert body["metrics"]["mape_pct"] == 7.5

    def test_method_contract_is_published(self, client):
        body = client.get("/api/accuracy/method").json()
        assert "mape_pct" in body["artifact_contract"]["required_metrics"]
        assert "artifact_id" in body["artifact_contract"]["required_keys"]
        assert body["prohibited"]
        assert "publish_accuracy.py" in body["how_to_publish"]

    def test_missing_artifact_404s(self, client, isolated_registry):
        assert client.get("/api/accuracy/artifacts/nope").status_code == 404
