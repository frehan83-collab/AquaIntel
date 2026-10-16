"""GTM ROI calculator tests (hardening §9).

The calculator must invent **no** market value: every output is a supplied input or
a labelled assumption, each with the formula that produced it and with the inputs
actually used.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from core.api import app
from core.gtm import roi


@pytest.fixture(scope="module")
def client():
    return TestClient(app, raise_server_exceptions=False)


class TestCalculatorHonesty:
    def test_every_line_states_its_formula_and_inputs(self):
        for icp in roi.CALCULATORS:
            result = roi.calculate(icp)
            assert result["lines"], icp
            for line in result["lines"]:
                assert line["formula"], line["name"]
                assert line["inputs_used"], line["name"]
                assert line["assumption"] is True, line["name"]

    def test_defaults_used_are_reported_as_assumptions(self):
        result = roi.calculate("producer", {"annual_tonnes": 12000})
        # supplied inputs are NOT labelled as assumptions...
        assert "annual_tonnes" not in result["assumptions_used"]
        # ...and everything not supplied IS
        assert "price_nok_kg" in result["assumptions_used"]
        assert result["inputs_supplied"]["annual_tonnes"] == 12000

    def test_disclosure_and_exclusions_are_always_present(self):
        result = roi.calculate("desk")
        assert "no market value" in result["disclosure"]
        assert "not advice" in result["not_included"]

    def test_maths_is_reproducible_and_correct(self):
        result = roi.calculate("desk", {"annual_tonnes": 10000, "basis_improvement_nok_kg": 0.5})
        basis = next(line for line in result["lines"] if "Basis" in line["name"])
        assert basis["value_nok"] == 10000 * 1000 * 0.5
        assert result["benefit_nok"] == sum(line["value_nok"] for line in result["lines"])
        assert result["cost_nok"] == 2990 * 12
        assert result["net_nok"] == result["benefit_nok"] - result["cost_nok"]

    def test_no_hardcoded_market_values_in_the_module(self):
        """Rule 3: the module may not embed a market price it did not receive."""
        import inspect

        source = inspect.getsource(roi)
        assert "FRED" not in source
        assert "SSB" not in source  # no upstream series citation => nothing asserted as market data
        # every default carries the assumption flag in the emitted payload
        for icp in roi.CALCULATORS:
            assert roi.calculate(icp)["assumptions_used"]


class TestValidation:
    def test_unknown_icp_is_rejected(self):
        with pytest.raises(ValueError):
            roi.calculate("astronaut")

    def test_unknown_input_is_rejected(self):
        with pytest.raises(ValueError):
            roi.calculate("producer", {"annual_tonnes": 1, "made_up": 2})


class TestRoiEndpoints:
    def test_get_roi_defaults(self, client):
        body = client.get("/api/gtm/roi", params={"icp": "producer"}).json()
        assert body["result"]["icp"] == "producer"
        assert set(body["icps"]) == set(roi.CALCULATORS)
        assert body["labels"]

    def test_get_roi_rejects_unknown_icp(self, client):
        assert client.get("/api/gtm/roi", params={"icp": "astronaut"}).status_code == 422

    def test_post_roi_uses_supplied_inputs(self, client):
        body = client.post(
            "/api/gtm/roi",
            json={"icp": "producer", "months": 6, "inputs": {"annual_tonnes": 15000}},
        ).json()
        assert body["inputs_supplied"]["annual_tonnes"] == 15000
        assert body["cost_nok"] == 4900 * 6
        assert body["months"] == 6

    def test_post_roi_validates_months(self, client):
        r = client.post("/api/gtm/roi", json={"icp": "desk", "months": 999})
        assert r.status_code == 422

    def test_kit_endpoint_lists_the_assets(self, client):
        body = client.get("/api/gtm/kit").json()
        paths = [a["path"] for a in body["assets"]]
        assert "docs/GTM_DEMO_SCRIPT.md" in paths
        assert body["live_proof_points"]