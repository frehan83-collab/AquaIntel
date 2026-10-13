"""
Router Module Tests
====================
Verify all extracted routers and key API endpoints work correctly.
Tests run against the actual FastAPI app using TestClient.
Run with: pytest tests/test_routers.py -v
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from core.api import app
    return TestClient(app)


# ---------------------------------------------------------------------------
# Bloom Routes
# ---------------------------------------------------------------------------
class TestBloomRoutes:
    def test_bloom_risk(self, client):
        r = client.get("/api/bloom/risk")
        assert r.status_code == 200

    def test_bloom_alerts(self, client):
        r = client.get("/api/bloom/alerts")
        assert r.status_code == 200

    def test_bloom_chlorophyll(self, client):
        r = client.get("/api/bloom/chlorophyll")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Country Routes
# ---------------------------------------------------------------------------
class TestCountryRoutes:
    def test_canada_snapshot(self, client):
        r = client.get("/api/canada/snapshot")
        assert r.status_code == 200

    def test_iceland_snapshot(self, client):
        r = client.get("/api/iceland/snapshot")
        assert r.status_code == 200

    def test_chile_snapshot(self, client):
        r = client.get("/api/chile/snapshot")
        assert r.status_code == 200

    def test_scotland_snapshot(self, client):
        r = client.get("/api/scotland/snapshot")
        assert r.status_code == 200

    def test_faroe_snapshot(self, client):
        r = client.get("/api/faroe/snapshot")
        assert r.status_code == 200

    def test_canada_lice_by_region(self, client):
        r = client.get("/api/canada/lice-by-region")
        assert r.status_code == 200

    def test_chile_signals(self, client):
        r = client.get("/api/chile/signals")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Supply Routes
# ---------------------------------------------------------------------------
class TestSupplyRoutes:
    def test_supply_forecast(self, client):
        r = client.get("/api/supply-forecast")
        assert r.status_code == 200

    def test_supply_demand_balance(self, client):
        r = client.get("/api/supply/demand-balance")
        assert r.status_code == 200

    def test_supply_smolt_forecast(self, client):
        r = client.get("/api/supply/smolt-forecast")
        assert r.status_code == 200
        body = r.json()
        # Contract corrected post-review (was a bare list, no provenance).
        assert isinstance(body["pipeline"], list)
        assert body["horizon_months"] == 18
        assert body["data_provenance"]["is_live"] is True

    def test_supply_cohort_timeline(self, client):
        r = client.get("/api/supply/cohort-timeline")
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body["cohorts"], list)
        assert body["count"] == len(body["cohorts"])
        assert "data_provenance" in body

    def test_supply_summary(self, client):
        r = client.get("/api/supply/summary")
        assert r.status_code == 200

    def test_biomass_outlook_computes(self, client):
        """Regression: compute_outlook was called without await (silent failure)."""
        r = client.get("/api/biomass/outlook?horizon=4&scenarios=100")
        assert r.status_code == 200
        data = r.json()
        assert data["current_biomass_tonnes"] > 0
        assert data["national_mab"] > 0
        assert "data_provenance" in data

    def test_biomass_scenarios_distinct(self, client):
        """Regression: scenario cache key collision returned identical MABs."""
        r = client.get("/api/biomass/scenarios")
        assert r.status_code == 200
        data = r.json()
        mabs = {
            data["current"]["national_mab"],
            data["all_green"]["national_mab"],
            data["all_red"]["national_mab"],
        }
        assert len(mabs) == 3, f"Scenario cache collision — identical MABs: {mabs}"
        assert data["all_green"]["national_mab"] > data["all_red"]["national_mab"]


# ---------------------------------------------------------------------------
# Market Routes
# ---------------------------------------------------------------------------
class TestMarketRoutes:
    def test_spot_price(self, client):
        r = client.get("/api/market/spot-price")
        assert r.status_code == 200

    def test_forward_curve(self, client):
        r = client.get("/api/market/forward-curve")
        assert r.status_code == 200

    def test_hedger_signals(self, client):
        r = client.get("/api/market/hedger-signals")
        assert r.status_code == 200

    def test_ssb_price_history(self, client):
        r = client.get("/api/market/ssb-price-history")
        assert r.status_code == 200

    def test_market_seasonal(self, client):
        r = client.get("/api/market/seasonal")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# ML Routes
# ---------------------------------------------------------------------------
class TestMLRoutes:
    def test_chronos_price(self, client):
        r = client.get("/api/ml/chronos/price-forecast")
        assert r.status_code == 200

    def test_chronos_model_comparison(self, client):
        r = client.get("/api/ml/chronos/model-comparison")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Traceability Routes
# ---------------------------------------------------------------------------
class TestTraceabilityRoutes:
    def test_traceability_dashboard(self, client):
        r = client.get("/api/traceability/dashboard")
        assert r.status_code == 200

    def test_eudr_status(self, client):
        r = client.get("/api/traceability/eudr-status")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Notification Routes
# ---------------------------------------------------------------------------
class TestNotificationRoutes:
    def test_active_alerts(self, client):
        r = client.get("/api/notifications/alerts")
        assert r.status_code == 200
        data = r.json()
        assert "alerts" in data
        assert "count" in data
        assert "data_provenance" in data

    def test_get_thresholds(self, client):
        r = client.get("/api/notifications/thresholds")
        assert r.status_code == 200
        data = r.json()
        assert "lice_critical" in data

    def test_update_thresholds(self, client):
        r = client.post("/api/notifications/thresholds", json={"lice_critical": 0.6})
        assert r.status_code == 200
        data = r.json()
        assert data["lice_critical"] == 0.6


# ---------------------------------------------------------------------------
# Scenario Routes
# ---------------------------------------------------------------------------
class TestScenarioRoutes:
    def test_compound_scenario(self, client):
        r = client.post("/api/scenarios/compound", json={
            "events": [
                {"type": "isa", "params": {"production_area": 3}},
                {"type": "feed_shock", "params": {"fishmeal_change_pct": 15}},
            ]
        })
        assert r.status_code == 200
        data = r.json()
        assert "compound_impact" in data or "individual_impacts" in data or "events" in data

    def test_scenario_list(self, client):
        r = client.get("/api/scenarios/list")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Analytics Routes
# ---------------------------------------------------------------------------
class TestAnalyticsRoutes:
    def test_yoy_lice(self, client):
        r = client.get("/api/analytics/yoy-comparison?metric=lice")
        assert r.status_code == 200

    def test_yoy_price(self, client):
        r = client.get("/api/analytics/yoy-comparison?metric=price")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Farm Routes
# ---------------------------------------------------------------------------
class TestFarmRoutes:
    def test_farm_graph_summary(self, client):
        r = client.get("/api/farm-graph/summary")
        assert r.status_code == 200

    def test_farm_graph_clusters(self, client):
        r = client.get("/api/farm-graph/clusters")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Efficacy Routes
# ---------------------------------------------------------------------------
class TestEfficacyRoutes:
    def test_efficacy_benchmarks(self, client):
        r = client.get("/api/efficacy/benchmarks")
        assert r.status_code == 200

    def test_efficacy_by_region(self, client):
        r = client.get("/api/efficacy/by-region")
        assert r.status_code == 200

    def test_efficacy_by_season(self, client):
        r = client.get("/api/efficacy/by-season")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Disease Routes
# ---------------------------------------------------------------------------
class TestDiseaseRoutes:
    def test_disease_alerts(self, client):
        r = client.get("/api/disease/alerts")
        assert r.status_code == 200

    def test_disease_by_company(self, client):
        r = client.get("/api/disease/by-company")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Signals Routes
# ---------------------------------------------------------------------------
class TestSignalsRoutes:
    def test_signals_list(self, client):
        r = client.get("/api/signals")
        assert r.status_code == 200

    def test_sentiment_summary(self, client):
        r = client.get("/api/sentiment/summary")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Twin Routes
# ---------------------------------------------------------------------------
class TestTwinRoutes:
    def test_twin_status(self, client):
        r = client.get("/api/twin/status")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Misc / Regulatory Routes
# ---------------------------------------------------------------------------
class TestMiscRoutes:
    def test_traffic_light_current(self, client):
        r = client.get("/api/regulatory/traffic-light/current")
        assert r.status_code == 200

    def test_climate_risk_scores(self, client):
        r = client.get("/api/climate/risk-scores")
        assert r.status_code == 200

    def test_ras_summary(self, client):
        r = client.get("/api/ras/summary")
        assert r.status_code == 200

    def test_china_demand(self, client):
        r = client.get("/api/china/demand")
        assert r.status_code == 200

    def test_disclaimer(self, client):
        r = client.get("/api/disclaimer")
        assert r.status_code == 200
