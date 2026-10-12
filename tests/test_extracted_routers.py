"""
Session 39 router decomposition tests.

Guards the faithful split of misc_routes.py into domain modules:
- Structural: all 57 migrated paths remain registered exactly once.
- Functional: smoke tests per extracted module.
"""
import pytest
from starlette.testclient import TestClient

from core.api import app

# Every path migrated out of misc_routes.py (Session 39 split).
MIGRATED_PATHS = {
    # feed_cost_routes.py (8)
    "/api/feed-cost/latest",
    "/api/feed-cost/history",
    "/api/feed-cost/historical-prices",
    "/api/feed-cost/composite-index",
    "/api/feed-cost/peru-anchovy",
    "/api/feed-cost/enhanced-anchovy",
    "/api/feed-cost/alerts",
    "/api/feed-cost/official-history",
    # ocean_routes.py (13)
    "/api/ocean/currents/status",
    "/api/ocean/currents/refresh",
    "/api/ocean/temperature",
    "/api/ocean/forecast",
    "/api/ocean/forecast/pa/{pa}",
    "/api/ocean/norkyst/current",
    "/api/ocean/norkyst/pa/{pa}",
    "/api/satellite/status",
    "/api/satellite/products",
    "/api/satellite/scan",
    "/api/satellite/anomalies",
    "/api/satellite/pace/chlorophyll",
    "/api/satellite/pace/hab-risk",
    # macro_routes.py (20)
    "/api/ais/tracks",
    "/api/ais/harvest-signals",
    "/api/ais/treatment-signals",
    "/api/ais/supply-intelligence",
    "/api/ais/harvest-intelligence",
    "/api/regime/states",
    "/api/regime/alerts",
    "/api/regime/pa/{pa}",
    "/api/regime/company-risk",
    "/api/pairs/all",
    "/api/pairs/signals",
    "/api/pairs/{pair_name}",
    "/api/esg/scores",
    "/api/esg/summary",
    "/api/esg/company/{company_name}",
    "/api/macro/snapshot",
    "/api/macro/series/{name}",
    "/api/contracts/evaluate",
    "/api/contracts/portfolio",
    "/api/contracts/hedge-signals",
    # causal_routes.py (2)
    "/api/causal/summary",
    "/api/causal/granger",
    # ras_routes.py (3)
    "/api/ras/companies",
    "/api/ras/summary",
    "/api/ras/timeline",
    # misc_routes.py retained (11)
    "/api/tiers",
    "/api/climate/risk-scores",
    "/api/climate/pa/{pa}",
    "/api/climate/projections",
    "/api/climate/heatwave-risk",
    "/api/competitiveness/origin-index",
    "/api/competitiveness/tariff-scenario",
    "/api/global-supply",
    "/api/regulatory/traffic-light/current",
    "/api/regulatory/traffic-light/simulate",
    "/api/regulatory/traffic-light/all-scenarios",
}


@pytest.fixture(scope="module")
def client():
    return TestClient(app, raise_server_exceptions=False)


class TestRouteSurface:
    def test_all_migrated_paths_registered(self):
        registered = [r.path for r in app.routes]
        for path in MIGRATED_PATHS:
            assert path in registered, f"Missing route after decomposition: {path}"

    def test_no_duplicate_paths(self):
        pairs = [
            (r.path, m)
            for r in app.routes
            for m in getattr(r, "methods", None) or []
            if r.path.startswith("/api/")
        ]
        dupes = {p for p in pairs if pairs.count(p) > 1}
        assert not dupes, f"Duplicate (path, method) routes: {dupes}"


class TestFeedCostRoutes:
    def test_history(self, client):
        r = client.get("/api/feed-cost/history?n=5")
        assert r.status_code == 200
        assert isinstance(r.json(), (list, dict))

    def test_peru_anchovy(self, client):
        r = client.get("/api/feed-cost/peru-anchovy")
        assert r.status_code == 200

    def test_official_history(self, client):
        r = client.get("/api/feed-cost/official-history")
        assert r.status_code == 200
        assert "data" in r.json()


class TestOceanRoutes:
    def test_currents_status(self, client):
        r = client.get("/api/ocean/currents/status")
        assert r.status_code == 200

    def test_temperature_shape(self, client):
        r = client.get("/api/ocean/temperature?lat=60.39&lon=5.32")
        assert r.status_code == 200
        data = r.json()
        assert data["lat"] == 60.39 and data["lon"] == 5.32
        assert "temp_c" in data and "source" in data


class TestMacroRoutes:
    def test_regime_states(self, client):
        r = client.get("/api/regime/states")
        assert r.status_code == 200

    def test_pairs_all(self, client):
        r = client.get("/api/pairs/all")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_esg_scores_awaitable(self, client):
        """esg scorer getters are async — regression guard for missing-await."""
        r = client.get("/api/esg/scores")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


class TestRasRoutes:
    def test_summary(self, client):
        r = client.get("/api/ras/summary")
        assert r.status_code == 200
        assert isinstance(r.json(), dict)

    def test_companies(self, client):
        r = client.get("/api/ras/companies")
        assert r.status_code == 200


class TestPrunedMiscRoutes:
    def test_tiers(self, client):
        r = client.get("/api/tiers")
        assert r.status_code == 200
        assert isinstance(r.json(), dict) and r.json()

    def test_traffic_light_current(self, client):
        r = client.get("/api/regulatory/traffic-light/current")
        assert r.status_code == 200
        assert "data_provenance" in r.json()

    def test_climate_heatwave_risk_preserved(self, client):
        """Regression guard: heatwave-risk must stay on misc_routes."""
        r = client.get("/api/climate/heatwave-risk")
        assert r.status_code == 200
        data = r.json()
        assert "assessments" in data and "overall_status" in data


    def test_migrated_count(self):
        assert len(MIGRATED_PATHS) == 57
