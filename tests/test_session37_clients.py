"""
Tests for Session 37 data clients — zero test coverage previously.

Covers:
  1. MUR SST Client (core/market/mur_sst_client.py)
  2. NorKyst v3 Client (core/market/norkyst_client.py)
  3. NASA PACE Client (core/market/nasa_pace_client.py)
  4. SEPA Scotland Client (core/market/sepa_client.py)

All HTTP calls are mocked — no real network requests.
"""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import asdict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ═══════════════════════════════════════════════════════════════════
# 1. MUR SST Client Tests
# ═══════════════════════════════════════════════════════════════════


class TestMURSSTClientImport:
    """Module-level import and structural tests."""

    def test_module_imports(self):
        import core.market.mur_sst_client as mod
        assert hasattr(mod, "MURSSTClient")
        assert hasattr(mod, "mur_sst_client")

    def test_singleton_exists(self):
        from core.market.mur_sst_client import mur_sst_client
        assert mur_sst_client is not None

    def test_pa_centers_all_13(self):
        from core.market.mur_sst_client import PA_CENTERS
        assert len(PA_CENTERS) == 13
        for pa in range(1, 14):
            assert pa in PA_CENTERS
            lat, lon = PA_CENTERS[pa]
            assert 55.0 <= lat <= 72.0, f"PA {pa} lat out of Norway range"
            assert 0.0 <= lon <= 35.0, f"PA {pa} lon out of Norway range"

    def test_pa_names_all_13(self):
        from core.market.mur_sst_client import PA_NAMES
        assert len(PA_NAMES) == 13
        for pa in range(1, 14):
            assert pa in PA_NAMES
            assert len(PA_NAMES[pa]) > 3

    def test_cache_ttl_is_6_hours(self):
        from core.market.mur_sst_client import CACHE_TTL
        assert CACHE_TTL == dt.timedelta(hours=6)

    def test_class_has_expected_methods(self):
        from core.market.mur_sst_client import MURSSTClient
        client = MURSSTClient()
        assert hasattr(client, "fetch_sst_for_date")
        assert hasattr(client, "fetch_sst_timeseries")
        assert hasattr(client, "fetch_sst_for_pa")
        assert hasattr(client, "close")


class TestMURSSTCacheHelpers:
    """Cache helper function tests."""

    def test_cache_set_and_get(self):
        from core.market.mur_sst_client import _cache, _cache_set, _cache_get
        _cache_set("test_key_mur", {"sst_c": 8.5})
        result = _cache_get("test_key_mur")
        assert result == {"sst_c": 8.5}
        # Cleanup
        _cache.pop("test_key_mur", None)

    def test_cache_get_missing_returns_none(self):
        from core.market.mur_sst_client import _cache_get
        assert _cache_get("nonexistent_key_xyz") is None

    def test_cache_expiry(self):
        from core.market.mur_sst_client import _cache, _cache_get
        # Insert an entry that is already expired
        expired_time = dt.datetime.now(dt.UTC) - dt.timedelta(hours=7)
        _cache["expired_key"] = (expired_time, {"old": True})
        assert _cache_get("expired_key") is None
        _cache.pop("expired_key", None)


class TestMURSSTClientAsync:
    """Async method tests with mocked HTTP."""

    @pytest.mark.asyncio
    async def test_fetch_sst_for_date_fallback_to_met_no(self):
        """When CMEMS fails, falls back to MET.no and returns data."""
        from core.market.mur_sst_client import MURSSTClient, _cache
        client = MURSSTClient()

        met_response = {
            "properties": {
                "timeseries": [
                    {
                        "time": "2026-04-10T12:00:00Z",
                        "data": {
                            "instant": {
                                "details": {"sea_water_temperature": 7.5}
                            }
                        },
                    }
                ]
            }
        }

        mock_resp_cmr = MagicMock()
        mock_resp_cmr.status_code = 200
        mock_resp_cmr.raise_for_status = MagicMock()
        mock_resp_cmr.json.return_value = {"feed": {"entry": []}}

        mock_resp_cmems = MagicMock()
        mock_resp_cmems.status_code = 500

        mock_resp_met = MagicMock()
        mock_resp_met.status_code = 200
        mock_resp_met.json.return_value = met_response

        call_count = 0

        async def mock_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if "cmr.earthdata" in url:
                return mock_resp_cmr
            if "marine.copernicus" in url:
                return mock_resp_cmems
            if "met.no" in url:
                return mock_resp_met
            return mock_resp_cmems

        client._client.get = mock_get
        # Clear cache to force fetch
        _cache.clear()

        result = await client.fetch_sst_for_date(60.0, 5.0, dt.date(2026, 4, 10))
        assert result["sst_c"] == 7.5
        assert result["lat"] == 60.0
        assert result["lon"] == 5.0
        assert result["date"] == "2026-04-10"
        assert result["source"] == "MET.no OceanForecast 2.0"
        await client.close()

    @pytest.mark.asyncio
    async def test_fetch_sst_for_date_unavailable(self):
        """When all sources fail, returns sst_c=None."""
        from core.market.mur_sst_client import MURSSTClient, _cache
        client = MURSSTClient()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"feed": {"entry": []}}

        mock_resp_fail = MagicMock()
        mock_resp_fail.status_code = 500

        async def mock_get(url, **kwargs):
            if "cmr.earthdata" in url:
                return mock_resp
            if "met.no" in url:
                r = MagicMock()
                r.status_code = 503
                return r
            return mock_resp_fail

        client._client.get = mock_get
        _cache.clear()

        result = await client.fetch_sst_for_date(60.0, 5.0, dt.date(2026, 4, 10))
        assert result["sst_c"] is None
        assert result["mur_available"] is False
        assert result["source"] == "unavailable"
        await client.close()

    @pytest.mark.asyncio
    async def test_fetch_sst_for_pa_invalid_pa(self):
        """Invalid PA number returns error dict."""
        from core.market.mur_sst_client import MURSSTClient
        client = MURSSTClient()
        result = await client.fetch_sst_for_pa(99, dt.date(2026, 4, 1), dt.date(2026, 4, 10))
        assert "error" in result
        assert result["production_area"] == 99
        await client.close()

    @pytest.mark.asyncio
    async def test_fetch_sst_timeseries_clamps_range(self):
        """Timeseries clamps date range to 365 days max."""
        from core.market.mur_sst_client import MURSSTClient, _cache
        client = MURSSTClient()

        mock_resp_cmems = MagicMock()
        mock_resp_cmems.status_code = 500

        mock_resp_met = MagicMock()
        mock_resp_met.status_code = 200
        mock_resp_met.json.return_value = {"properties": {"timeseries": []}}

        async def mock_get(url, **kwargs):
            if "met.no" in url:
                return mock_resp_met
            return mock_resp_cmems

        client._client.get = mock_get
        _cache.clear()

        end = dt.date(2026, 4, 10)
        start = dt.date(2024, 1, 1)  # >365 days
        result = await client.fetch_sst_timeseries(60.0, 5.0, start, end)
        # Should still return successfully, just with clamped range
        assert "observations" in result
        assert result["start_date"] != "2024-01-01"  # Was clamped
        await client.close()

    @pytest.mark.asyncio
    async def test_fetch_sst_timeseries_statistics(self):
        """Timeseries computes correct min/max/mean statistics."""
        from core.market.mur_sst_client import MURSSTClient, _cache
        client = MURSSTClient()

        met_response = {
            "properties": {
                "timeseries": [
                    {"time": f"2026-04-0{i}T12:00:00Z",
                     "data": {"instant": {"details": {"sea_water_temperature": temp}}}}
                    for i, temp in [(1, 6.0), (2, 8.0), (3, 10.0)]
                ]
            }
        }
        mock_fail = MagicMock()
        mock_fail.status_code = 500
        mock_met = MagicMock()
        mock_met.status_code = 200
        mock_met.json.return_value = met_response

        async def mock_get(url, **kwargs):
            if "met.no" in url:
                return mock_met
            return mock_fail

        client._client.get = mock_get
        _cache.clear()

        result = await client.fetch_sst_timeseries(
            60.0, 5.0, dt.date(2026, 4, 1), dt.date(2026, 4, 3)
        )
        stats = result["statistics"]
        assert stats["min_c"] == 6.0
        assert stats["max_c"] == 10.0
        assert stats["mean_c"] == 8.0
        assert stats["count"] == 3
        await client.close()


# ═══════════════════════════════════════════════════════════════════
# 2. NorKyst v3 Client Tests
# ═══════════════════════════════════════════════════════════════════


class TestNorKystImport:
    """Module-level import and structural tests."""

    def test_module_imports(self):
        import core.market.norkyst_client as mod
        assert hasattr(mod, "NorKystClient")
        assert hasattr(mod, "norkyst_client")

    def test_singleton_exists(self):
        from core.market.norkyst_client import norkyst_client
        assert norkyst_client is not None

    def test_pa_centroids_all_13(self):
        from core.market.norkyst_client import PA_CENTROIDS
        assert len(PA_CENTROIDS) == 13
        for pa in range(1, 14):
            assert pa in PA_CENTROIDS

    def test_ocean_conditions_dataclass(self):
        from core.market.norkyst_client import OceanConditions
        oc = OceanConditions(
            latitude=63.5, longitude=8.5,
            timestamp="2026-04-10T12:00:00Z",
            temperature_c=7.2, salinity_psu=34.1,
        )
        d = oc.to_dict()
        assert d["latitude"] == 63.5
        assert d["temperature_c"] == 7.2

    def test_pa_ocean_summary_dataclass(self):
        from core.market.norkyst_client import PAOceanSummary
        s = PAOceanSummary(
            pa_number=5, pa_name="Test",
            latitude=63.5, longitude=8.5,
            timestamp="2026-04-10T12:00:00Z",
            conditions_assessment="optimal",
        )
        d = s.to_dict()
        assert d["pa_number"] == 5
        assert d["conditions_assessment"] == "optimal"


class TestNorKystHelpers:
    """Pure helper function tests."""

    def test_current_speed_and_dir_both_none(self):
        from core.market.norkyst_client import _current_speed_and_dir
        speed, direction = _current_speed_and_dir(None, None)
        assert speed is None
        assert direction is None

    def test_current_speed_and_dir_one_none(self):
        from core.market.norkyst_client import _current_speed_and_dir
        speed, direction = _current_speed_and_dir(0.5, None)
        assert speed is None

    def test_current_speed_and_dir_zero(self):
        from core.market.norkyst_client import _current_speed_and_dir
        speed, direction = _current_speed_and_dir(0.0, 0.0)
        assert speed == 0.0

    def test_current_speed_and_dir_positive(self):
        from core.market.norkyst_client import _current_speed_and_dir
        speed, direction = _current_speed_and_dir(3.0, 4.0)
        assert speed == 5.0  # 3-4-5 triangle
        assert 0 <= direction <= 360

    def test_current_speed_and_dir_due_north(self):
        from core.market.norkyst_client import _current_speed_and_dir
        speed, direction = _current_speed_and_dir(0.0, 1.0)
        assert speed == 1.0
        assert direction == 0.0  # Due north

    def test_current_speed_and_dir_due_east(self):
        from core.market.norkyst_client import _current_speed_and_dir
        speed, direction = _current_speed_and_dir(1.0, 0.0)
        assert speed == 1.0
        assert direction == 90.0  # Due east

    def test_assess_conditions_none_temp(self):
        from core.market.norkyst_client import _assess_conditions
        assert _assess_conditions(None, None) == "unknown"

    def test_assess_conditions_cold(self):
        from core.market.norkyst_client import _assess_conditions
        assert _assess_conditions(3.0, None) == "cold_stress"

    def test_assess_conditions_warm_stress(self):
        from core.market.norkyst_client import _assess_conditions
        assert _assess_conditions(19.0, None) == "warm_stress"

    def test_assess_conditions_optimal(self):
        from core.market.norkyst_client import _assess_conditions
        assert _assess_conditions(10.0, 0.1) == "optimal"

    def test_assess_conditions_strong_current(self):
        from core.market.norkyst_client import _assess_conditions
        # temp must be <= 14.0 for strong_current to take precedence over "warm"
        assert _assess_conditions(12.0, 0.6) == "strong_current"

    def test_assess_conditions_warm(self):
        from core.market.norkyst_client import _assess_conditions
        assert _assess_conditions(15.0, 0.2) == "warm"

    def test_assess_conditions_suboptimal(self):
        from core.market.norkyst_client import _assess_conditions
        # 5.0 is above 4.0 cold threshold but below 8.0 optimal
        assert _assess_conditions(5.0, 0.1) == "suboptimal"


class TestNorKystCSVParser:
    """Tests for _parse_ncss_csv."""

    def test_parse_valid_csv(self):
        from core.market.norkyst_client import NorKystClient
        client = NorKystClient()
        csv_text = (
            'date,latitude[unit="degrees_north"],longitude[unit="degrees_east"],'
            'temperature[unit="Celsius"],salinity[unit="1e-3"],u[unit="m/s"],v[unit="m/s"]\n'
            "2026-04-11T12:00:00Z,63.5,8.5,7.23,34.1,0.05,-0.02\n"
        )
        rows = client._parse_ncss_csv(csv_text)
        assert len(rows) == 1
        assert rows[0]["date"] == "2026-04-11T12:00:00Z"
        assert rows[0]["temperature"] == 7.23
        assert rows[0]["salinity"] == 34.1
        assert rows[0]["u"] == 0.05
        assert rows[0]["v"] == -0.02

    def test_parse_empty_csv(self):
        from core.market.norkyst_client import NorKystClient
        client = NorKystClient()
        assert client._parse_ncss_csv("") == []
        assert client._parse_ncss_csv("header_only") == []

    def test_parse_csv_mismatched_columns(self):
        from core.market.norkyst_client import NorKystClient
        client = NorKystClient()
        csv_text = "date,temp\n2026-04-11,7.2,extra_col\n"
        rows = client._parse_ncss_csv(csv_text)
        assert len(rows) == 0  # Mismatched columns skipped

    def test_parse_csv_multiple_rows(self):
        from core.market.norkyst_client import NorKystClient
        client = NorKystClient()
        csv_text = (
            "date,temperature\n"
            "2026-04-11T12:00:00Z,7.0\n"
            "2026-04-11T13:00:00Z,7.5\n"
            "2026-04-11T14:00:00Z,8.0\n"
        )
        rows = client._parse_ncss_csv(csv_text)
        assert len(rows) == 3
        assert rows[2]["temperature"] == 8.0


class TestNorKystClientAsync:
    """Async method tests with mocked HTTP."""

    @pytest.mark.asyncio
    async def test_fetch_current_conditions_success(self):
        from core.market.norkyst_client import NorKystClient
        client = NorKystClient()
        csv_text = (
            "date,temperature,salinity,u,v\n"
            "2026-04-11T12:00:00Z,7.23,34.1,0.05,-0.02\n"
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = csv_text
        mock_resp.raise_for_status = MagicMock()

        async def mock_get(url, **kw):
            return mock_resp

        client._client.get = mock_get
        client._cache.clear()

        result = await client.fetch_current_conditions(63.5, 8.5)
        assert result is not None
        assert result.temperature_c == 7.23
        assert result.salinity_psu == 34.1
        assert result.current_speed_ms is not None
        assert result.current_speed_ms == round(math.sqrt(0.05**2 + 0.02**2), 3)

    @pytest.mark.asyncio
    async def test_fetch_current_conditions_error(self):
        from core.market.norkyst_client import NorKystClient
        client = NorKystClient()

        async def mock_get(url, **kw):
            raise Exception("Network error")

        client._client.get = mock_get
        client._cache.clear()

        result = await client.fetch_current_conditions(63.5, 8.5)
        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_pa_ocean_summary_invalid_pa(self):
        from core.market.norkyst_client import NorKystClient
        client = NorKystClient()
        result = await client.fetch_pa_ocean_summary(99)
        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_pa_ocean_summary_success(self):
        from core.market.norkyst_client import NorKystClient
        client = NorKystClient()
        csv_text = (
            "date,temperature,salinity,u,v\n"
            "2026-04-11T12:00:00Z,10.0,34.5,0.1,0.1\n"
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = csv_text
        mock_resp.raise_for_status = MagicMock()

        async def mock_get(url, **kw):
            return mock_resp

        client._client.get = mock_get
        client._cache.clear()

        result = await client.fetch_pa_ocean_summary(5)
        assert result is not None
        assert result.pa_number == 5
        assert result.temperature_c == 10.0
        assert result.conditions_assessment == "optimal"

    @pytest.mark.asyncio
    async def test_fetch_current_forecast_caps_hours(self):
        from core.market.norkyst_client import NorKystClient
        client = NorKystClient()

        csv_text = "date,temperature,salinity,u,v\n"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = csv_text
        mock_resp.raise_for_status = MagicMock()

        async def mock_get(url, **kw):
            return mock_resp

        client._client.get = mock_get
        client._cache.clear()

        # hours=500 should be capped at 240
        result = await client.fetch_current_forecast(63.5, 8.5, hours=500)
        assert isinstance(result, list)


# ═══════════════════════════════════════════════════════════════════
# 3. NASA PACE Client Tests
# ═══════════════════════════════════════════════════════════════════


class TestNASAPACEImport:
    """Module-level import and structural tests."""

    def test_module_imports(self):
        import core.market.nasa_pace_client as mod
        assert hasattr(mod, "NASAPACEClient")
        assert hasattr(mod, "nasa_pace_client")

    def test_singleton_exists(self):
        from core.market.nasa_pace_client import nasa_pace_client
        assert nasa_pace_client is not None

    def test_chl_thresholds_ordered(self):
        from core.market.nasa_pace_client import (
            CHL_BACKGROUND, CHL_ELEVATED, CHL_BLOOM, CHL_SEVERE,
        )
        assert CHL_BACKGROUND < CHL_ELEVATED < CHL_BLOOM < CHL_SEVERE

    def test_hab_species_context(self):
        from core.market.nasa_pace_client import HAB_SPECIES_CONTEXT
        assert "Chrysochromulina_leadbeateri" in HAB_SPECIES_CONTEXT
        assert "Karenia_mikimotoi" in HAB_SPECIES_CONTEXT
        assert "Pseudo_nitzschia" in HAB_SPECIES_CONTEXT

    def test_dataclasses_exist(self):
        from core.market.nasa_pace_client import (
            ChlorophyllReading, HABRiskAssessment, BloomMapPoint,
        )
        reading = ChlorophyllReading(latitude=60.0, longitude=5.0, date="2026-04-10")
        assert reading.to_dict()["source"] == "NASA_PACE_OCI"

    def test_hab_risk_defaults(self):
        from core.market.nasa_pace_client import HABRiskAssessment
        assessment = HABRiskAssessment(latitude=60.0, longitude=5.0, date="2026-04-10")
        assert assessment.hab_species_possible == []
        assert assessment.risk_level == "unknown"
        assert assessment.risk_score == 0.0


class TestPACEClassifyChlRisk:
    """Tests for _classify_chl_risk pure function."""

    def test_none_returns_unknown(self):
        from core.market.nasa_pace_client import _classify_chl_risk
        level, score, prob = _classify_chl_risk(None)
        assert level == "unknown"
        assert score == 0.0
        assert prob == 0.0

    def test_very_low_returns_low(self):
        from core.market.nasa_pace_client import _classify_chl_risk
        level, score, prob = _classify_chl_risk(0.5)
        assert level == "low"
        assert score == 0.05
        assert prob == 0.02

    def test_background_range_returns_low(self):
        from core.market.nasa_pace_client import _classify_chl_risk
        level, score, prob = _classify_chl_risk(3.0)
        assert level == "low"
        assert 0.1 <= score <= 0.3
        assert prob == 0.05

    def test_elevated_range(self):
        from core.market.nasa_pace_client import _classify_chl_risk
        level, score, prob = _classify_chl_risk(7.5)
        assert level == "elevated"
        assert 0.3 <= score <= 0.6
        assert 0.1 <= prob <= 0.4

    def test_bloom_range(self):
        from core.market.nasa_pace_client import _classify_chl_risk
        level, score, prob = _classify_chl_risk(15.0)
        assert level == "bloom"
        assert 0.6 <= score <= 0.8
        assert 0.5 <= prob <= 0.8

    def test_severe_range(self):
        from core.market.nasa_pace_client import _classify_chl_risk
        level, score, prob = _classify_chl_risk(25.0)
        assert level == "severe"
        assert score == 0.95
        assert prob == 0.9

    def test_monotonic_risk_score(self):
        """Risk score increases monotonically with chlorophyll."""
        from core.market.nasa_pace_client import _classify_chl_risk
        prev_score = -1.0
        for chl in [0.1, 0.5, 1.0, 3.0, 5.0, 8.0, 10.0, 15.0, 20.0, 25.0]:
            _, score, _ = _classify_chl_risk(chl)
            assert score >= prev_score, f"Score decreased at chl={chl}"
            prev_score = score


class TestPACEAssessSpeciesRisk:
    """Tests for _assess_species_risk pure function."""

    def test_low_chl_returns_empty(self):
        from core.market.nasa_pace_client import _assess_species_risk
        note, species = _assess_species_risk(2.0, 60.0, 5.0, 6)
        assert note == ""
        assert species == []

    def test_none_chl_returns_empty(self):
        from core.market.nasa_pace_client import _assess_species_risk
        note, species = _assess_species_risk(None, 60.0, 5.0, 6)
        assert species == []

    def test_chrysochromulina_risk_may_bloom(self):
        """Chrysochromulina should be flagged for Norwegian waters in May with high chl."""
        from core.market.nasa_pace_client import _assess_species_risk
        note, species = _assess_species_risk(12.0, 65.0, 10.0, 5)
        assert "Chrysochromulina_leadbeateri" in species

    def test_karenia_risk_late_summer(self):
        """Karenia flagged in warmer Norwegian waters in late summer."""
        from core.market.nasa_pace_client import _assess_species_risk
        note, species = _assess_species_risk(6.0, 60.0, 5.0, 8)
        assert "Karenia_mikimotoi" in species

    def test_pseudo_nitzschia_spring(self):
        """Pseudo-nitzschia flagged during spring bloom."""
        from core.market.nasa_pace_client import _assess_species_risk
        note, species = _assess_species_risk(12.0, 60.0, 5.0, 4)
        assert "Pseudo_nitzschia" in species

    def test_no_species_outside_season(self):
        """No species flagged in winter with moderate chl."""
        from core.market.nasa_pace_client import _assess_species_risk
        note, species = _assess_species_risk(6.0, 60.0, 5.0, 1)
        assert species == []


class TestNASAPACEClientAsync:
    """Async method tests with mocked HTTP."""

    @pytest.mark.asyncio
    async def test_fetch_chlorophyll_no_granules(self):
        from core.market.nasa_pace_client import NASAPACEClient
        client = NASAPACEClient()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"feed": {"entry": []}}

        async def mock_get(url, **kw):
            return mock_resp

        client._client.get = mock_get
        client._cache.clear()

        result = await client.fetch_chlorophyll(60.0, 5.0, "2026-04-10")
        assert result is not None
        assert result.chlorophyll_a_mg_m3 is None
        assert "no coverage" in result.source

    @pytest.mark.asyncio
    async def test_fetch_chlorophyll_with_granule_no_auth(self):
        from core.market.nasa_pace_client import NASAPACEClient
        client = NASAPACEClient()

        cmr_response = {
            "feed": {
                "entry": [
                    {
                        "id": "GRANULE_001",
                        "links": [
                            {"href": "https://oceandata.sci.gsfc.nasa.gov/opendap/PACE_OCI/file.nc"}
                        ],
                    }
                ]
            }
        }

        call_urls = []

        async def mock_get(url, **kw):
            call_urls.append(url)
            resp = MagicMock()
            if "cmr.earthdata" in url:
                resp.status_code = 200
                resp.raise_for_status = MagicMock()
                resp.json.return_value = cmr_response
            else:
                # OPeNDAP returns 401 (no auth)
                resp.status_code = 401
                resp.raise_for_status = MagicMock(side_effect=Exception("401"))
            return resp

        client._client.get = mock_get
        client._cache.clear()

        result = await client.fetch_chlorophyll(60.0, 5.0, "2026-04-10")
        assert result is not None
        assert result.granule_id == "GRANULE_001"
        # No actual chl value since OPeNDAP auth fails
        assert result.chlorophyll_a_mg_m3 is None

    @pytest.mark.asyncio
    async def test_fetch_hab_risk_with_low_chl(self):
        from core.market.nasa_pace_client import NASAPACEClient
        client = NASAPACEClient()

        # Mock fetch_chlorophyll to return a known low value
        from core.market.nasa_pace_client import ChlorophyllReading

        async def mock_fetch_chl(lat, lon, date=None):
            return ChlorophyllReading(
                latitude=lat, longitude=lon, date=date or "2026-04-10",
                chlorophyll_a_mg_m3=0.8,
            )

        client.fetch_chlorophyll = mock_fetch_chl
        client._cache.clear()

        result = await client.fetch_hab_risk(60.0, 5.0, "2026-04-10")
        assert result is not None
        assert result.risk_level == "low"
        assert result.chlorophyll_a_mg_m3 == 0.8
        assert result.hab_species_possible == []

    @pytest.mark.asyncio
    async def test_fetch_hab_risk_severe(self):
        from core.market.nasa_pace_client import NASAPACEClient, ChlorophyllReading
        client = NASAPACEClient()

        async def mock_fetch_chl(lat, lon, date=None):
            return ChlorophyllReading(
                latitude=lat, longitude=lon, date=date or "2026-05-15",
                chlorophyll_a_mg_m3=25.0,
            )

        client.fetch_chlorophyll = mock_fetch_chl
        client._cache.clear()

        result = await client.fetch_hab_risk(65.0, 10.0, "2026-05-15")
        assert result is not None
        assert result.risk_level == "severe"
        assert result.risk_score == 0.95
        assert len(result.hab_species_possible) > 0

    @pytest.mark.asyncio
    async def test_extract_opendap_url(self):
        from core.market.nasa_pace_client import NASAPACEClient
        client = NASAPACEClient()
        granule = {
            "links": [
                {"href": "https://some-url.com/metadata.html"},
                {"href": "https://oceandata.sci.gsfc.nasa.gov/opendap/file.nc"},
            ]
        }
        url = client._extract_opendap_url(granule)
        assert url is not None
        assert "opendap" in url

    @pytest.mark.asyncio
    async def test_extract_opendap_url_missing(self):
        from core.market.nasa_pace_client import NASAPACEClient
        client = NASAPACEClient()
        granule = {"links": [{"href": "https://example.com/html"}]}
        url = client._extract_opendap_url(granule)
        assert url is None


# ═══════════════════════════════════════════════════════════════════
# 4. SEPA Scotland Client Tests
# ═══════════════════════════════════════════════════════════════════


class TestSEPAImport:
    """Module-level import and structural tests."""

    def test_module_imports(self):
        import core.market.sepa_client as mod
        assert hasattr(mod, "SEPAClient")
        assert hasattr(mod, "sepa_client")

    def test_singleton_exists(self):
        from core.market.sepa_client import sepa_client
        assert sepa_client is not None

    def test_scotland_regions_all_7(self):
        from core.market.sepa_client import SCOTLAND_REGIONS
        assert len(SCOTLAND_REGIONS) == 7
        expected = {
            "Shetland", "Orkney", "NW Highlands", "Skye",
            "Argyll", "Outer Hebrides", "Loch Linnhe",
        }
        assert set(SCOTLAND_REGIONS.keys()) == expected

    def test_region_station_hints_all_7(self):
        from core.market.sepa_client import SEPA_REGION_STATION_HINTS
        assert len(SEPA_REGION_STATION_HINTS) == 7

    def test_region_coords_plausible(self):
        from core.market.sepa_client import SCOTLAND_REGIONS
        for name, info in SCOTLAND_REGIONS.items():
            assert 55.0 <= info["lat"] <= 62.0, f"{name} lat out of Scotland range"
            assert -8.0 <= info["lng"] <= 0.0, f"{name} lng out of Scotland range"
            assert info["search_radius_km"] > 0

    def test_dataclass_sepa_station(self):
        from core.market.sepa_client import SEPAStation
        s = SEPAStation(
            station_id="123", station_name="Test Station",
            latitude=57.0, longitude=-5.0,
        )
        assert s.station_id == "123"
        assert s.region == ""

    def test_dataclass_sepa_timeseries(self):
        from core.market.sepa_client import SEPATimeSeries
        ts = SEPATimeSeries(
            station_id="123", station_name="Test",
            parameter="Water Temperature", unit="C",
            timestamps=["2026-04-10"], values=[8.5],
        )
        assert len(ts.values) == 1

    def test_dataclass_region_water_quality(self):
        from core.market.sepa_client import RegionWaterQuality
        rq = RegionWaterQuality(region="Shetland")
        assert rq.assessment == "unknown"
        assert rq.stations == []
        assert rq.n_temperature_stations == 0


class TestSEPAAssessConditions:
    """Tests for _assess_conditions static method."""

    def test_no_data(self):
        from core.market.sepa_client import SEPAClient, RegionWaterQuality
        rq = RegionWaterQuality(region="Test", avg_temperature_c=None)
        assert SEPAClient._assess_conditions(rq) == "no_data"

    def test_critical_high_temp(self):
        from core.market.sepa_client import SEPAClient, RegionWaterQuality
        rq = RegionWaterQuality(region="Test", avg_temperature_c=23.0)
        assert SEPAClient._assess_conditions(rq) == "critical_high_temp"

    def test_stress_high_temp(self):
        from core.market.sepa_client import SEPAClient, RegionWaterQuality
        rq = RegionWaterQuality(region="Test", avg_temperature_c=19.0)
        assert SEPAClient._assess_conditions(rq) == "stress_high_temp"

    def test_stress_low_temp(self):
        from core.market.sepa_client import SEPAClient, RegionWaterQuality
        rq = RegionWaterQuality(region="Test", avg_temperature_c=1.5)
        assert SEPAClient._assess_conditions(rq) == "stress_low_temp"

    def test_critical_low_oxygen(self):
        from core.market.sepa_client import SEPAClient, RegionWaterQuality
        rq = RegionWaterQuality(
            region="Test", avg_temperature_c=10.0,
            avg_dissolved_oxygen_mgl=3.5,
        )
        assert SEPAClient._assess_conditions(rq) == "critical_low_oxygen"

    def test_stress_low_oxygen(self):
        from core.market.sepa_client import SEPAClient, RegionWaterQuality
        rq = RegionWaterQuality(
            region="Test", avg_temperature_c=10.0,
            avg_dissolved_oxygen_mgl=5.5,
        )
        assert SEPAClient._assess_conditions(rq) == "stress_low_oxygen"

    def test_optimal(self):
        from core.market.sepa_client import SEPAClient, RegionWaterQuality
        rq = RegionWaterQuality(
            region="Test", avg_temperature_c=10.0,
            avg_dissolved_oxygen_mgl=8.0,
        )
        assert SEPAClient._assess_conditions(rq) == "optimal"

    def test_optimal_no_do(self):
        from core.market.sepa_client import SEPAClient, RegionWaterQuality
        rq = RegionWaterQuality(region="Test", avg_temperature_c=10.0)
        assert SEPAClient._assess_conditions(rq) == "optimal"

    def test_suboptimal_oxygen(self):
        from core.market.sepa_client import SEPAClient, RegionWaterQuality
        rq = RegionWaterQuality(
            region="Test", avg_temperature_c=10.0,
            avg_dissolved_oxygen_mgl=6.5,
        )
        assert SEPAClient._assess_conditions(rq) == "suboptimal_oxygen"

    def test_acceptable_warm_side(self):
        from core.market.sepa_client import SEPAClient, RegionWaterQuality
        rq = RegionWaterQuality(region="Test", avg_temperature_c=16.0)
        assert SEPAClient._assess_conditions(rq) == "acceptable"

    def test_acceptable_cool_side(self):
        from core.market.sepa_client import SEPAClient, RegionWaterQuality
        rq = RegionWaterQuality(region="Test", avg_temperature_c=5.0)
        assert SEPAClient._assess_conditions(rq) == "acceptable"


class TestSEPAStationMatching:
    """Tests for _match_station_to_region."""

    def test_match_by_name_hint(self):
        from core.market.sepa_client import SEPAClient
        client = SEPAClient()
        result = client._match_station_to_region("Lerwick Coastal", "", 0.0, 0.0)
        assert result == "Shetland"

    def test_match_by_catchment_hint(self):
        from core.market.sepa_client import SEPAClient
        client = SEPAClient()
        result = client._match_station_to_region("Station X", "Loch Fyne Basin", 0.0, 0.0)
        assert result == "Argyll"

    def test_match_by_proximity(self):
        from core.market.sepa_client import SEPAClient
        client = SEPAClient()
        # Close to Shetland coordinates (60.40, -1.20)
        result = client._match_station_to_region("Unknown", "", 60.35, -1.15)
        assert result == "Shetland"

    def test_no_match_far_away(self):
        from core.market.sepa_client import SEPAClient
        client = SEPAClient()
        # London coordinates — far from any Scottish region
        result = client._match_station_to_region("London", "", 51.5, -0.1)
        assert result is None

    def test_match_by_skye_hint(self):
        from core.market.sepa_client import SEPAClient
        client = SEPAClient()
        result = client._match_station_to_region("Portree Harbour", "", 0.0, 0.0)
        assert result == "Skye"


class TestSEPACacheValidity:
    """Tests for cache validity helper."""

    def test_cache_invalid_when_none(self):
        from core.market.sepa_client import SEPAClient
        client = SEPAClient()
        assert client._cache_valid(None) is False

    def test_cache_valid_recent(self):
        from core.market.sepa_client import SEPAClient
        client = SEPAClient()
        recent = dt.datetime.now(dt.UTC) - dt.timedelta(minutes=30)
        assert client._cache_valid(recent) is True

    def test_cache_invalid_expired(self):
        from core.market.sepa_client import SEPAClient
        client = SEPAClient()
        old = dt.datetime.now(dt.UTC) - dt.timedelta(hours=7)
        assert client._cache_valid(old) is False


class TestSEPAClientAsync:
    """Async method tests with mocked HTTP."""

    @pytest.mark.asyncio
    async def test_get_region_water_quality_unknown_region(self):
        from core.market.sepa_client import SEPAClient
        client = SEPAClient()
        result = await client.get_region_water_quality("Narnia")
        assert "error" in result
        assert "valid_regions" in result

    @pytest.mark.asyncio
    async def test_get_region_water_quality_case_insensitive(self):
        from core.market.sepa_client import SEPAClient
        client = SEPAClient()
        # Should match "Shetland" even when lowercase
        # We need to mock the inner calls
        client._quality_cache = None
        client._quality_cache_time = None

        async def mock_fetch_stations(region=None):
            return []

        client.fetch_water_quality_stations = mock_fetch_stations

        result = await client.get_region_water_quality("shetland")
        # Should not return error since "shetland" matches "Shetland"
        assert "error" not in result
        assert result["region"] == "Shetland"

    @pytest.mark.asyncio
    async def test_fetch_water_quality_stations_parses_response(self):
        from core.market.sepa_client import SEPAClient
        client = SEPAClient()
        client._station_cache = None
        client._station_cache_time = None

        kiwis_response = [
            ["station_id", "station_name", "station_latitude",
             "station_longitude", "station_no", "catchment_name"],
            ["101", "Lerwick Coastal", "60.38", "-1.15", "S001", "Shetland"],
            ["102", "Oban Harbour", "56.41", "-5.47", "S002", "Argyll"],
        ]

        async def mock_kiwis(params):
            return kiwis_response

        client._kiwis_request = mock_kiwis

        stations = await client.fetch_water_quality_stations()
        assert len(stations) >= 1
        names = [s.station_name for s in stations]
        assert "Lerwick Coastal" in names

    @pytest.mark.asyncio
    async def test_format_summary_provenance_live(self):
        from core.market.sepa_client import SEPAClient, RegionWaterQuality
        client = SEPAClient()
        regions = {
            "Shetland": RegionWaterQuality(
                region="Shetland", avg_temperature_c=9.0,
                n_temperature_stations=3,
            ),
        }
        result = client._format_summary(regions, from_cache=False)
        assert result["data_provenance"]["is_live"] is True
        assert result["n_regions_with_data"] == 1

    @pytest.mark.asyncio
    async def test_format_summary_provenance_cached(self):
        from core.market.sepa_client import SEPAClient, RegionWaterQuality
        client = SEPAClient()
        regions = {
            "Shetland": RegionWaterQuality(
                region="Shetland", avg_temperature_c=9.0,
            ),
        }
        result = client._format_summary(regions, from_cache=True)
        assert result["data_provenance"]["is_live"] is False
