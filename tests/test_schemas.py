"""
Schema Validation Tests
========================
Verifies Pydantic v2 response models enforce constraints correctly.
Run with: pytest tests/test_schemas.py -v
"""
import pytest
from pydantic import ValidationError
from core.schemas import (
    DataProvenanceSchema,
    LiceSummaryResponse,
    HealthResponse,
    DecisionCardResponse,
    AlertResponse,
    PriceOutlookResponse,
    CompoundScenarioResponse,
    AlertsListResponse,
    TreatmentOutcomeRequest,
    SignalResponse,
    SignalsListResponse,
    CountrySnapshotResponse,
    FeedCostResponse,
    BloomRiskResponse,
    SupplyForecastResponse,
    TreatmentEfficacyResponse,
    TreatmentOutcomeResponse,
    ScenarioSaveResponse,
    ThresholdConfig,
    YoYComparisonResponse,
    CacheStatsResponse,
    MetricsResponse,
)


class TestDataProvenanceSchema:
    def test_valid_provenance(self):
        p = DataProvenanceSchema(
            source="SSB", is_live=True, freshness="2026-04-03", confidence=0.95
        )
        assert p.confidence == 0.95
        assert p.source == "SSB"
        assert p.is_live is True
        assert p.fallback_reason is None

    def test_confidence_upper_bound(self):
        with pytest.raises(Exception):
            DataProvenanceSchema(
                source="x", is_live=True, freshness="x", confidence=1.5
            )

    def test_confidence_lower_bound(self):
        with pytest.raises(Exception):
            DataProvenanceSchema(
                source="x", is_live=True, freshness="x", confidence=-0.1
            )

    def test_confidence_zero_valid(self):
        p = DataProvenanceSchema(
            source="simulated", is_live=False, freshness="n/a", confidence=0.0
        )
        assert p.confidence == 0.0

    def test_confidence_one_valid(self):
        p = DataProvenanceSchema(
            source="live", is_live=True, freshness="today", confidence=1.0
        )
        assert p.confidence == 1.0

    def test_fallback_reason_optional(self):
        p = DataProvenanceSchema(
            source="SSB",
            is_live=False,
            freshness="stale",
            confidence=0.3,
            fallback_reason="API timeout",
        )
        assert p.fallback_reason == "API timeout"


class TestLiceSummaryResponse:
    def test_valid_response(self):
        r = LiceSummaryResponse(
            year=2026,
            week=14,
            avg_adult_female_lice=0.15,
            max_adult_female_lice=2.3,
            sites_above_threshold=45,
            count_above_05=45,
            records=1500,
        )
        assert r.threshold == 0.5
        assert r.year == 2026
        assert r.records == 1500

    def test_defaults(self):
        r = LiceSummaryResponse(
            year=None,
            week=None,
            avg_adult_female_lice=0.0,
            max_adult_female_lice=0.0,
            sites_above_threshold=0,
            count_above_05=0,
            records=0,
        )
        assert r.min_adult_female_lice == 0.0
        assert r.std_adult_female_lice == 0.0
        assert r.above_threshold_pct == 0.0
        assert r.data_provenance is None


class TestHealthResponse:
    def test_defaults(self):
        from core.version import PLATFORM_VERSION
        r = HealthResponse(status="healthy")
        assert r.database == "ok"
        assert r.version == PLATFORM_VERSION
        assert r.routes == 0

    def test_custom_values(self):
        r = HealthResponse(status="degraded", database="error", routes=229, version="3.0.0")
        assert r.status == "degraded"
        assert r.database == "error"
        assert r.routes == 229


class TestDecisionCardResponse:
    def test_minimal(self):
        r = DecisionCardResponse(locality_no=10469, action="MONITOR")
        assert r.locality_no == 10469
        assert r.action == "MONITOR"
        assert r.urgency is None
        assert r.roi_estimate is None

    def test_full(self):
        r = DecisionCardResponse(
            locality_no=10469,
            action="TREAT_NOW",
            urgency="high",
            recommended_method="mechanical",
            success_probability=0.85,
            roi_estimate=3.2,
            reasoning="Lice above 0.5 threshold",
            lice_current=0.7,
            lice_trend="rising",
            sea_temp_c=12.5,
        )
        assert r.success_probability == 0.85
        assert r.lice_trend == "rising"


class TestAlertResponse:
    def test_valid_alert(self):
        a = AlertResponse(
            id="alert-001",
            category="lice",
            severity="critical",
            title="Lice spike PA3",
            message="Average lice above 0.5",
            metric_value=0.72,
            threshold=0.5,
            production_area=3,
        )
        assert a.severity == "critical"
        assert a.metric_value == 0.72
        assert a.production_area == 3

    def test_optional_fields(self):
        a = AlertResponse(
            id="a1",
            category="price",
            severity="high",
            title="Price drop",
            message="Spot below forecast",
            metric_value=70.0,
            threshold=75.0,
        )
        assert a.production_area is None
        assert a.company is None
        assert a.created_at is None


class TestAlertsListResponse:
    def test_empty(self):
        r = AlertsListResponse()
        assert r.alerts == []
        assert r.count == 0
        assert r.critical == 0

    def test_with_alerts(self):
        alert = AlertResponse(
            id="a1", category="lice", severity="high",
            title="t", message="m", metric_value=1.0, threshold=0.5,
        )
        r = AlertsListResponse(alerts=[alert], count=1, high=1)
        assert len(r.alerts) == 1
        assert r.high == 1


class TestPriceOutlookResponse:
    def test_valid(self):
        r = PriceOutlookResponse(
            horizon_weeks=4,
            current_spot_nok=94.4,
            predicted_nok=97.0,
            direction="up",
            confidence=0.82,
            bands={"low": 90.0, "high": 102.0},
        )
        assert r.direction == "up"
        assert r.bands["low"] == 90.0
        assert r.scenarios is None
        assert r.disclaimer is None


class TestCompoundScenarioResponse:
    def test_valid(self):
        r = CompoundScenarioResponse(
            events=[{"type": "isa"}],
            individual_impacts=[{"pa": 3, "loss": 500}],
            compound_impact={"total": 600},
        )
        assert len(r.events) == 1
        assert r.severity is None
        assert r.cascade_narrative is None


class TestTreatmentOutcomeRequest:
    def test_valid_request(self):
        req = TreatmentOutcomeRequest(
            locality_no=10001,
            treatment_date="2026-03-15",
            method="thermal",
            pre_lice_count=8.0,
            post_lice_count=2.0,
        )
        assert req.method == "thermal"

    def test_valid_mechanical(self):
        req = TreatmentOutcomeRequest(
            locality_no=10001,
            treatment_date="2026-03-15",
            method="mechanical",
            pre_lice_count=5.0,
            post_lice_count=1.0,
            mortality_observed=2.5,
            cost_nok=18.5,
            resistance_observed=False,
        )
        assert req.mortality_observed == 2.5
        assert req.cost_nok == 18.5

    def test_invalid_method_rejected(self):
        with pytest.raises(ValidationError):
            TreatmentOutcomeRequest(
                locality_no=10001,
                treatment_date="2026-03-15",
                method="laser",
                pre_lice_count=8.0,
                post_lice_count=2.0,
            )

    def test_post_greater_than_pre_rejected(self):
        with pytest.raises(ValidationError):
            TreatmentOutcomeRequest(
                locality_no=10001,
                treatment_date="2026-03-15",
                method="mechanical",
                pre_lice_count=2.0,
                post_lice_count=5.0,
            )

    def test_zero_pre_lice_rejected(self):
        with pytest.raises(ValidationError):
            TreatmentOutcomeRequest(
                locality_no=10001,
                treatment_date="2026-03-15",
                method="thermal",
                pre_lice_count=0.0,
                post_lice_count=0.0,
            )

    def test_negative_locality_rejected(self):
        with pytest.raises(ValidationError):
            TreatmentOutcomeRequest(
                locality_no=-1,
                treatment_date="2026-03-15",
                method="thermal",
                pre_lice_count=5.0,
                post_lice_count=1.0,
            )


class TestSignalResponse:
    def test_minimal(self):
        s = SignalResponse(id=1)
        assert s.id == 1
        assert s.ticker is None
        assert s.direction is None

    def test_full(self):
        s = SignalResponse(
            id=42, ticker="MOWI", direction="long",
            confidence=0.85, strategy="pairs", status="active",
        )
        assert s.ticker == "MOWI"
        assert s.confidence == 0.85


class TestSignalsListResponse:
    def test_empty(self):
        r = SignalsListResponse()
        assert r.signals == []
        assert r.count == 0

    def test_with_signals(self):
        sig = SignalResponse(id=1, ticker="SALM", direction="short")
        r = SignalsListResponse(signals=[sig], count=1)
        assert len(r.signals) == 1
        assert r.signals[0].ticker == "SALM"


class TestCountrySnapshotResponse:
    def test_valid(self):
        r = CountrySnapshotResponse(
            country="Iceland",
            production_tonnes=45000.0,
            farms_active=12,
        )
        assert r.country == "Iceland"
        assert r.disease_cases is None
        assert r.data_provenance is None


class TestFeedCostResponse:
    def test_valid(self):
        r = FeedCostResponse(
            composite_index=112.5,
            fishmeal_usd_tonne=1450.0,
            soybean_usd_tonne=380.0,
            trend="rising",
        )
        assert r.composite_index == 112.5
        assert r.trend == "rising"


class TestBloomRiskResponse:
    def test_empty(self):
        r = BloomRiskResponse()
        assert r.localities == []
        assert r.high_risk_count == 0

    def test_with_data(self):
        r = BloomRiskResponse(
            localities=[{"pa": 3, "risk": "high"}],
            high_risk_count=1,
        )
        assert len(r.localities) == 1


class TestSupplyForecastResponse:
    def test_defaults(self):
        r = SupplyForecastResponse()
        assert r.forecast_months == 18
        assert r.total_supply_tonnes is None
        assert r.cohorts == []


class TestTreatmentEfficacyResponse:
    def test_valid(self):
        r = TreatmentEfficacyResponse(
            methods=[{"name": "mechanical", "efficacy": 0.92}],
            total_outcomes=150,
        )
        assert r.total_outcomes == 150
        assert len(r.methods) == 1


class TestTreatmentOutcomeResponse:
    def test_valid(self):
        r = TreatmentOutcomeResponse(
            id=1, reduction_pct=75.0,
            method="thermal", locality_no=10469,
        )
        assert r.status == "recorded"
        assert r.reduction_pct == 75.0


class TestScenarioSaveResponse:
    def test_valid(self):
        r = ScenarioSaveResponse(id=1, name="ISA PA3 + Feed Shock")
        assert r.status == "saved"
        assert r.name == "ISA PA3 + Feed Shock"


class TestThresholdConfig:
    def test_defaults(self):
        t = ThresholdConfig()
        assert t.lice_critical == 0.5
        assert t.lice_warning == 0.3
        assert t.price_drop_pct == 10.0
        assert t.sst_high == 16.0
        assert t.sst_low == 4.0

    def test_custom(self):
        t = ThresholdConfig(lice_critical=0.6, sst_high=18.0)
        assert t.lice_critical == 0.6
        assert t.sst_high == 18.0


class TestYoYComparisonResponse:
    def test_defaults(self):
        r = YoYComparisonResponse(metric="lice")
        assert r.metric == "lice"
        assert r.production_area == 0
        assert r.current_year == []
        assert r.years == []


class TestCacheStatsResponse:
    def test_defaults(self):
        r = CacheStatsResponse()
        assert r.entries == 0
        assert r.hit_rate == 0.0


class TestMetricsResponse:
    def test_defaults(self):
        from core.version import PLATFORM_VERSION
        r = MetricsResponse()
        assert r.routes == 0
        assert r.version == PLATFORM_VERSION
        assert isinstance(r.cache, CacheStatsResponse)
