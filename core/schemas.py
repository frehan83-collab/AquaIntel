"""
API Response Schemas
=====================
Pydantic v2 models for type-safe API responses.
Used as response_model on endpoints for validation and OpenAPI docs.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Any, Optional, Literal

from core.version import API_SCHEMA_VERSION, PLATFORM_VERSION


class DataProvenanceSchema(BaseModel):
    source: str
    is_live: bool
    freshness: str
    confidence: float = Field(ge=0.0, le=1.0)
    fallback_reason: Optional[str] = None
    schema_version: str = API_SCHEMA_VERSION


class LiceSummaryResponse(BaseModel):
    year: Optional[int]
    week: Optional[int]
    avg_adult_female_lice: float
    max_adult_female_lice: float
    min_adult_female_lice: float = 0.0
    std_adult_female_lice: float = 0.0
    sites_above_threshold: int
    count_above_05: int
    threshold: float = 0.5
    records: int
    above_threshold_pct: float = 0.0
    data_provenance: Optional[DataProvenanceSchema] = None


class HealthResponse(BaseModel):
    status: str
    database: str = "ok"
    routes: int = 0
    version: str = PLATFORM_VERSION


class DecisionCardResponse(BaseModel):
    locality_no: int
    action: str  # TREAT_NOW, SCHEDULE_TREATMENT, MONITOR, NO_ACTION
    urgency: Optional[str] = None
    recommended_method: Optional[str] = None
    success_probability: Optional[float] = None
    roi_estimate: Optional[float] = None
    reasoning: Optional[str] = None
    lice_current: Optional[float] = None
    lice_trend: Optional[str] = None
    lice_predicted_next_week: Optional[float] = None
    sea_temp_c: Optional[float] = None
    cost_of_treatment_nok: Optional[float] = None
    cost_of_inaction_nok: Optional[float] = None
    ocean_forecast: Optional[dict] = None
    generated_at: Optional[str] = None
    data_provenance: Optional[DataProvenanceSchema] = None


class AlertResponse(BaseModel):
    id: str
    category: str
    severity: str
    title: str
    message: str
    metric_value: float
    threshold: float
    production_area: Optional[int] = None
    company: Optional[str] = None
    created_at: Optional[str] = None


class AlertsListResponse(BaseModel):
    alerts: list[AlertResponse] = []
    count: int = 0
    critical: int = 0
    high: int = 0
    data_provenance: Optional[DataProvenanceSchema] = None


class PriceOutlookResponse(BaseModel):
    horizon_weeks: int
    current_spot_nok: float
    predicted_nok: float
    direction: str
    confidence: float
    bands: dict
    scenarios: Optional[dict] = None
    signals: Optional[dict] = None
    model: Optional[dict] = None
    rationale: Optional[str] = None
    disclaimer: Optional[str] = None
    data_provenance: Optional[DataProvenanceSchema] = None


class MorningBriefSectionSchema(BaseModel):
    title: str
    icon: str = ""
    headline: str = ""
    detail: str = ""
    sentiment: str = "neutral"
    value: str = ""


class MorningBriefResponse(BaseModel):
    """GET /api/brief (morning_brief_engine.to_dict + provenance)."""
    model_config = ConfigDict(extra="allow")
    generated_at: str
    greeting: str = ""
    market_mood: str = "neutral"
    top_insight: str = ""
    sections: list[MorningBriefSectionSchema] = []
    data_provenance: Optional[DataProvenanceSchema] = None


class BiomassOutlookResponse(BaseModel):
    """GET /api/biomass/outlook (biomass_predictor.get_outlook_dict + provenance)."""
    model_config = ConfigDict(extra="allow")
    generated_at: str
    current_biomass_tonnes: float
    national_mab: float
    utilization_pct: float
    horizon_weeks: int
    forecast_biomass: list[float] = []
    forecast_harvest: list[float] = []
    p10_biomass: list[float] = []
    p50_biomass: list[float] = []
    p90_biomass: list[float] = []
    n_scenarios: int = 0
    scenario_green_impact_pct: float = 0.0
    scenario_red_impact_pct: float = 0.0
    recommendations: list[str] = []
    data_provenance: Optional[DataProvenanceSchema] = None


class CausalTeResult(BaseModel):
    lag: int
    te_value: float
    p_value: Optional[float] = None
    z_score: Optional[float] = None
    significant: Optional[bool] = None


class CausalSummaryResponse(BaseModel):
    """GET /api/causal/summary (causal_engine.get_causal_summary)."""
    model_config = ConfigDict(extra="allow")
    dominant_lag_weeks: Any = None
    method_used: Optional[str] = None
    confidence: Optional[str] = None
    interpretation: Optional[str] = None
    recommended_lag_range: Any = None
    asymmetry_detected: Any = None
    pcmci_available: Optional[bool] = None
    granger_results: Any = None
    te_results: list[CausalTeResult] = []
    pcmci_results: Any = None
    meta: Any = None


class CompoundScenarioResponse(BaseModel):
    events: list[dict]
    individual_impacts: list[dict]
    compound_impact: dict
    interaction_effects: list[dict] = []
    total_revenue_delta_mnok: Optional[float] = None
    severity: Optional[str] = None
    cascade_narrative: Optional[str] = None
    data_provenance: Optional[DataProvenanceSchema] = None


class SignalResponse(BaseModel):
    id: int
    ticker: Optional[str] = None
    direction: Optional[str] = None
    confidence: Optional[float] = None
    strategy: Optional[str] = None
    status: Optional[str] = None
    created_at: Optional[str] = None


class SignalsListResponse(BaseModel):
    signals: list[SignalResponse] = []
    count: int = 0


class CountrySnapshotResponse(BaseModel):
    country: str
    production_tonnes: Optional[float] = None
    lice_avg: Optional[float] = None
    disease_cases: Optional[int] = None
    farms_active: Optional[int] = None
    data_provenance: Optional[DataProvenanceSchema] = None


class FeedCostResponse(BaseModel):
    composite_index: Optional[float] = None
    fishmeal_usd_tonne: Optional[float] = None
    soybean_usd_tonne: Optional[float] = None
    trend: Optional[str] = None
    data_provenance: Optional[DataProvenanceSchema] = None


class BloomRiskResponse(BaseModel):
    localities: list[dict] = []
    high_risk_count: int = 0
    data_provenance: Optional[DataProvenanceSchema] = None


class SupplyForecastResponse(BaseModel):
    forecast_months: int = 18
    total_supply_tonnes: Optional[float] = None
    demand_balance: Optional[str] = None
    cohorts: list[dict] = []
    data_provenance: Optional[DataProvenanceSchema] = None


class TreatmentEfficacyResponse(BaseModel):
    methods: list[dict] = []
    total_outcomes: int = 0
    generated_at: Optional[str] = None
    data_provenance: Optional[DataProvenanceSchema] = None


ALLOWED_TREATMENT_METHODS = (
    "mechanical", "thermal", "freshwater", "medicinal", "biological",
)


class TreatmentOutcomeRequest(BaseModel):
    """Validated request body for POST /api/treatment/log-outcome."""
    locality_no: int = Field(..., gt=0, description="Farm locality number")
    treatment_date: Optional[str] = Field(None, description="ISO date string (defaults to today)")
    method: str = Field(..., description="Treatment method used")
    pre_lice_count: float = Field(..., gt=0, description="Avg adult female lice before treatment")
    post_lice_count: float = Field(..., ge=0, description="Avg adult female lice after treatment")
    mortality_observed: float = Field(0, ge=0, le=100, description="Mortality % observed")
    cost_nok: Optional[float] = Field(None, ge=0, description="Treatment cost in NOK per kg")
    notes: Optional[str] = Field(None, max_length=1000, description="Free-text notes")
    resistance_observed: bool = Field(False, description="Was treatment resistance observed?")

    @field_validator("method")
    @classmethod
    def method_must_be_allowed(cls, v: str) -> str:
        v_lower = v.lower().strip()
        if v_lower not in ALLOWED_TREATMENT_METHODS:
            raise ValueError(
                f"method must be one of {ALLOWED_TREATMENT_METHODS}, got '{v}'"
            )
        return v_lower

    @field_validator("post_lice_count")
    @classmethod
    def post_must_not_exceed_pre(cls, v: float, info) -> float:
        pre = info.data.get("pre_lice_count")
        if pre is not None and v > pre:
            raise ValueError(
                f"post_lice_count ({v}) cannot exceed pre_lice_count ({pre})"
            )
        return v


class TreatmentOutcomeResponse(BaseModel):
    id: int
    status: str = "recorded"
    reduction_pct: float
    method: str
    locality_no: int


class ScenarioSaveResponse(BaseModel):
    id: int
    status: str = "saved"
    name: str


# ── Custom Alert Rule Schemas ─────────────────────────────────────────

ALLOWED_METRICS = ("lice_avg", "spot_price", "sst", "disease_count", "bloom_risk")
ALLOWED_OPERATORS = (">", "<", ">=", "<=", "==")


class CustomAlertRuleCreate(BaseModel):
    """Request body for creating a custom alert rule."""
    name: str = Field(..., min_length=1, max_length=100, description="Rule name")
    metric: str = Field(..., description="Metric to monitor")
    operator: str = Field(..., description="Comparison operator")
    threshold: float = Field(..., description="Threshold value")
    production_area: Optional[int] = Field(None, ge=1, le=13, description="PA 1-13 filter")
    is_active: bool = Field(True, description="Whether the rule is active")
    notify_webhook: bool = Field(False, description="Send webhook on trigger")

    @field_validator("metric")
    @classmethod
    def metric_must_be_allowed(cls, v: str) -> str:
        v_lower = v.lower().strip()
        if v_lower not in ALLOWED_METRICS:
            raise ValueError(f"metric must be one of {ALLOWED_METRICS}, got '{v}'")
        return v_lower

    @field_validator("operator")
    @classmethod
    def operator_must_be_allowed(cls, v: str) -> str:
        v_stripped = v.strip()
        if v_stripped not in ALLOWED_OPERATORS:
            raise ValueError(f"operator must be one of {ALLOWED_OPERATORS}, got '{v}'")
        return v_stripped


class CustomAlertRuleUpdate(BaseModel):
    """Request body for updating a custom alert rule (partial)."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    metric: Optional[str] = None
    operator: Optional[str] = None
    threshold: Optional[float] = None
    production_area: Optional[int] = Field(None, ge=1, le=13)
    is_active: Optional[bool] = None
    notify_webhook: Optional[bool] = None

    @field_validator("metric")
    @classmethod
    def metric_must_be_allowed_update(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v_lower = v.lower().strip()
        if v_lower not in ALLOWED_METRICS:
            raise ValueError(f"metric must be one of {ALLOWED_METRICS}, got '{v}'")
        return v_lower

    @field_validator("operator")
    @classmethod
    def operator_must_be_allowed_update(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v_stripped = v.strip()
        if v_stripped not in ALLOWED_OPERATORS:
            raise ValueError(f"operator must be one of {ALLOWED_OPERATORS}, got '{v}'")
        return v_stripped


class CustomAlertRuleResponse(BaseModel):
    """Response for a single custom alert rule."""
    id: int
    user_id: Optional[int] = None
    name: str
    metric: str
    operator: str
    threshold: float
    production_area: Optional[int] = None
    is_active: bool = True
    notify_webhook: bool = False
    created_at: Optional[str] = None
    last_triggered: Optional[str] = None
    trigger_count: int = 0


class CustomAlertRuleEvaluation(BaseModel):
    """Result of evaluating a single rule against current data."""
    rule_id: int
    rule_name: str
    metric: str
    operator: str
    threshold: float
    current_value: Optional[float] = None
    triggered: bool = False
    production_area: Optional[int] = None
    message: Optional[str] = None


class CustomAlertRulesEvaluateResponse(BaseModel):
    """Response from evaluating all active rules."""
    evaluated: int = 0
    triggered: int = 0
    results: list[CustomAlertRuleEvaluation] = []
    data_provenance: Optional[DataProvenanceSchema] = None


class ThresholdConfig(BaseModel):
    lice_critical: float = 0.5
    lice_warning: float = 0.3
    price_drop_pct: float = 10.0
    sst_high: float = 16.0
    sst_low: float = 4.0


class YoYComparisonResponse(BaseModel):
    metric: str
    production_area: int = 0
    current_year: list[dict] = []
    previous_year: list[dict] = []
    two_years_ago: list[dict] = []
    years: list[int] = []
    data_provenance: Optional[DataProvenanceSchema] = None


class CacheStatsResponse(BaseModel):
    entries: int = 0
    hits: int = 0
    misses: int = 0
    hit_rate: float = 0.0


class MetricsResponse(BaseModel):
    cache: CacheStatsResponse = CacheStatsResponse()
    process: dict = {}
    routes: int = 0
    version: str = PLATFORM_VERSION


__all__ = [
    cls.__name__
    for cls in [
        DataProvenanceSchema,
        LiceSummaryResponse,
        HealthResponse,
        DecisionCardResponse,
        AlertResponse,
        AlertsListResponse,
        PriceOutlookResponse,
        MorningBriefSectionSchema,
        MorningBriefResponse,
        BiomassOutlookResponse,
        CausalTeResult,
        CausalSummaryResponse,
        CompoundScenarioResponse,
        SignalResponse,
        SignalsListResponse,
        CountrySnapshotResponse,
        FeedCostResponse,
        BloomRiskResponse,
        SupplyForecastResponse,
        TreatmentEfficacyResponse,
        TreatmentOutcomeRequest,
        TreatmentOutcomeResponse,
        ScenarioSaveResponse,
        ThresholdConfig,
        YoYComparisonResponse,
        CacheStatsResponse,
        MetricsResponse,
        CustomAlertRuleCreate,
        CustomAlertRuleUpdate,
        CustomAlertRuleResponse,
        CustomAlertRuleEvaluation,
        CustomAlertRulesEvaluateResponse,
    ]
]
