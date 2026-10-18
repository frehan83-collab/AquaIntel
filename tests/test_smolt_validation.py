"""WS-36 — the smolt pipeline is a model, and its level must be checked before use.

`smolt_model` projects harvest from smolt releases × survival × yield × growth. On
2026-10-18 its 12-month total is 789 987 t against the module's own 1.7 M t national
reference (0.46×) — while SSB's weekly export volumes imply about 120 000 t/month
nationally. The pipeline is therefore useful for direction and seasonality, not as a
supply level, and the payload has to say so instead of wearing a live badge.

These tests pin the check, not the current number.
"""
from __future__ import annotations

import inspect

import pytest

from core.valuechain import smolt_model as smolt_module
from core.valuechain.smolt_model import smolt_model


# ── 1. The validation block ────────────────────────────────────────────


def test_the_model_reports_its_own_gap_to_the_reference():
    validation = smolt_model.validation()
    assert validation["reference_annual_tonnes"] == smolt_module.ANNUAL_PRODUCTION_TONNES
    assert validation["model_12m_tonnes"] > 0
    ratio = validation["model_12m_tonnes"] / validation["reference_annual_tonnes"]
    assert validation["ratio_to_reference"] == pytest.approx(ratio, abs=0.01)
    assert validation["measurement"].startswith("model projection")
    assert "not reported supply" in validation["measurement"]


def test_the_current_model_is_flagged_uncalibrated():
    """If this fails because the model was improved, that is good news — update it."""
    validation = smolt_model.validation()
    assert validation["within_tolerance"] is False, (
        "the model now agrees with the national reference; remove the uncalibrated "
        "warning from the payload and update docs/HANDOVER.md WS-36"
    )
    assert "uncalibrated" in validation["note"]


def test_a_calibrated_model_would_pass(monkeypatch):
    """The check must be about the gap, not a hard-coded verdict."""
    current = smolt_model.validation()["model_12m_tonnes"]
    monkeypatch.setattr(smolt_module, "ANNUAL_PRODUCTION_TONNES", current)
    validation = smolt_model.validation()
    assert validation["ratio_to_reference"] == pytest.approx(1.0, abs=0.01)
    assert validation["within_tolerance"] is True
    assert "inside the reference band" in validation["note"]


def test_the_tolerance_band_is_documented():
    assert 10 <= smolt_module.SMOLT_VALIDATION_TOLERANCE_PCT <= 50
    assert "Fiskeridirektoratet" in smolt_module.SMOLT_REFERENCE_SOURCE


# ── 2. The payload ─────────────────────────────────────────────────────


def test_the_summary_carries_the_validation_block():
    summary = smolt_model.get_summary()
    assert "validation" in summary
    assert summary["validation"]["ratio_to_reference"] is not None


def test_the_route_degrades_when_the_level_is_uncalibrated():
    from fastapi.testclient import TestClient

    from core.api import app

    body = TestClient(app).get("/api/supply/smolt-forecast").json()
    assert body["validation"]["within_tolerance"] is False
    provenance = body["data_provenance"]
    assert provenance["is_live"] is False
    assert "national reference" in provenance["fallback_reason"]
    assert "uncalibrated" in provenance["fallback_reason"]
    # The measurement label must not read as reported supply.
    assert "model projection" in provenance["source"]
    assert "not reported supply" in provenance["source"]


def test_the_calibrated_branch_would_serve_live(monkeypatch):
    from fastapi.testclient import TestClient

    from core.api import app

    current = smolt_model.validation()["model_12m_tonnes"]
    monkeypatch.setattr(smolt_module, "ANNUAL_PRODUCTION_TONNES", current)
    body = TestClient(app).get("/api/supply/smolt-forecast").json()
    assert body["data_provenance"]["is_live"] is True


def test_the_validation_reads_the_pipeline_rather_than_a_constant():
    from core.valuechain.smolt_model import SmoltModel

    source = inspect.getsource(SmoltModel.validation)
    assert "get_supply_pipeline(12)" in source
    assert "ANNUAL_PRODUCTION_TONNES" in source
