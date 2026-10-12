/**
 * TypeScript API Response Types for AquaIntelligence (OpenClaw)
 * =============================================================
 * Organized by domain. Every interface mirrors the actual backend response shape.
 * Source: core/routers/*.py + core/schemas.py
 */

// ── Common Types ─────────────────────────────────────────────────────

/** Data provenance metadata attached to most API responses */
export interface DataProvenance {
  source: string;
  is_live: boolean;
  freshness: string;
  confidence: number;
  fallback_reason?: string;
}

/** Generic wrapper for endpoints that return {data: T, data_provenance: ...} */
export interface ProvenanceWrapped<T> {
  data: T;
  data_provenance: DataProvenance;
}

/** /api/health */
export interface HealthResponse {
  status: string;
  version: string;
  engines: number;
  routes: number;
  uptime_seconds: number;
  database: string;
  rate_limit_tier?: string;
}

// ── Lice & Farm Types ────────────────────────────────────────────────

/** /api/lice/summary */
export interface LiceSummary {
  year: number | null;
  week: number | null;
  avg_adult_female_lice: number;
  max_adult_female_lice: number;
  min_adult_female_lice: number;
  std_adult_female_lice: number;
  sites_above_threshold: number;
  count_above_05: number;
  threshold: number;
  records: number;
  above_threshold_pct: number;
  /** Optional per-PA breakdown returned in some response variants */
  production_areas?: Array<{ pa: number; avg_lice: number; count: number }>;
  areas?: Array<{ pa: number; avg_lice: number; count: number }>;
  overall?: { avg_lice: number; average_lice: number; threshold: number };
  summary?: { avg_lice: number; average_lice: number; threshold: number };
  data_provenance: DataProvenance;
}

/** /api/decision/{locality_no} */
export interface DecisionCard {
  locality_no: number;
  action: "TREAT_NOW" | "SCHEDULE_TREATMENT" | "MONITOR" | "NO_ACTION";
  urgency: "critical" | "high" | "medium" | "low";
  recommended_method: string;
  success_probability: number;
  roi_estimate: number;
  reasoning: string[];
  lice_current: number;
  lice_trend: "increasing" | "stable" | "decreasing";
  lice_predicted_next_week: number;
  sea_temp_c: number;
  cost_of_treatment_nok: number;
  cost_of_inaction_nok: number;
  ocean_forecast?: OceanForecast;
  explanation?: DecisionExplanation;
  generated_at: string;
  data_provenance: DataProvenance;
}

export interface DecisionExplanation {
  factors: Array<{
    name: string;
    importance: number;
    value: number;
    explanation_en: string;
    explanation_no: string;
  }>;
  summary_en: string;
  summary_no: string;
}

/** /api/farms/portfolio */
export interface FarmPortfolioResponse {
  farms: FarmPortfolioEntry[];
  summary: FarmPortfolioSummary;
  generated_at: string;
  data_provenance: DataProvenance;
}

export interface FarmPortfolioEntry {
  locality_no: number;
  name: string;
  production_area: number;
  company: string;
  lice_level: number;
  sea_temp_c: number;
  has_cleaner_fish: boolean;
  data_week: string;
  risk_level: "critical" | "high" | "moderate" | "low";
  decision: {
    action: string;
    urgency: string;
    recommended_method: string;
    roi_estimate: number;
    reasoning: string[];
  };
}

export interface FarmPortfolioSummary {
  total_farms: number;
  avg_lice_level: number;
  farms_needing_treatment: number;
  risk_breakdown: Record<string, number>;
}

/** /api/farms/biomass/national */
export interface BiomassNational {
  total_standing_tonnes: number;
  mab_utilization_pct: number;
  by_production_area: Record<string, {
    standing_tonnes: number;
    mab_tonnes: number;
    utilization_pct: number;
  }>;
  generated_at: string;
  data_provenance: DataProvenance;
}

// ── Market & Price Types ─────────────────────────────────────────────

/** /api/market/ssb-price-history */
export interface SSBPriceHistory {
  spot_nok: number;
  n_weeks: number;
  source: string;
  license: string;
  history: Array<{
    week: number;
    year: number;
    label?: string;
    price_nok_kg: number;
    volume_tonnes?: number;
  }>;
}

/** /api/market/price-outlook */
export interface PriceOutlook {
  horizon_weeks: number;
  current_spot_nok: number;
  predicted_nok: number;
  direction: "up" | "down" | "flat";
  confidence: number;
  bands?: {
    p95: [number, number];
    p80: [number, number];
    p50: [number, number];
  };
  scenarios?: Record<string, number[]>;
  signals: PriceSignals;
  model: {
    version: string;
    n_scenarios: number;
    /** Measured MAPE only when a validated backtest artifact matched; null = none on record */
    mape_backtest: number | null;
    /** Empirical band calibration from the validated backtest (per-horizon coverage + sample size) */
    band_trust?: {
      horizon_weeks: number;
      measured_coverage_80: number | null;
      n_eval_points: number | null;
      backtest_run?: string;
    } | null;
    accuracy_statement: string;
  };
  rationale: string;
  disclaimer: string;
  data_provenance: DataProvenance;
}

export interface PriceSignals {
  lice: number;
  supply: number;
  seasonal: number;
  export?: number;
  futures?: number;
  combined: number;
}

/** /api/macro/snapshot */
export interface MacroSnapshot {
  series: MacroSeries[];
  alerts: MacroAlert[];
}

export interface MacroSeries {
  name: string;
  value: number;
  unit: string;
  source: string;
  change_pct?: number;
}

export interface MacroAlert {
  level: string;
  message: string;
}

/** /api/feed-cost/latest */
export interface FeedCostLatest {
  production_cost_nok_per_kg_salmon: number;
  feed_cost_nok_per_kg: number;
  fcr: number;
  margin_pct: number;
  trend: string;
  ingredients: Record<string, {
    price_usd: number;
    weight: number;
    source: string;
    updated_at?: string;
  }>;
  data_provenance?: DataProvenance;
}

/** /api/competitiveness/origin-index */
export interface CompetitivenessIndex {
  origins: CompetitivenessOrigin[];
  fx_rates: Record<string, number>;
  generated_at: string;
}

export interface CompetitivenessOrigin {
  country: string;
  production_cost_nok_kg: number;
  freight_cost: number;
  tariff_usd_percent: number;
  total_cif_usd_kg: number;
  rank: number;
  competitiveness_vs_norway: number;
  insights: string;
}

/** /api/futures/forward-curve */
export interface FuturesForwardCurve {
  contracts: Array<{
    month: string;
    price_eur: number;
    price_nok: number;
    volume?: number;
  }>;
  spot_nok: number;
  fx_rate: number;
  source: string;
  is_synthetic: boolean;
  data_provenance: DataProvenance;
}

/** /api/futures/basis */
export interface FuturesBasis {
  spot_nok: number;
  nearest_future_nok: number;
  basis_nok: number;
  basis_pct: number;
  structure: "contango" | "backwardation" | "flat";
  data_provenance: DataProvenance;
}

// ── Leaders & Analytics Types ────────────────────────────────────────

/** Element of /api/leaders/top100 data array */
export interface LeaderEntry {
  rank: number;
  company_name: string;
  production_area: number;
  lice_percentile: number;
  production_tonnes: number;
  lice_avg: number;
  disease_status: string;
  esg_score: number;
  verdict: string;
}

/** /api/anomaly/scores */
export interface AnomalyScores {
  lice_zscore: number;
  lice_risk: string;
  disease_risk: string;
  mortality_risk: string;
  sst_anomaly: number;
  composite_score: number;
  risk_level: "LOW" | "ELEVATED" | "HIGH" | "CRITICAL";
  generated_at: string;
  data_provenance: DataProvenance;
}

/** /api/brief */
export interface MorningBrief {
  title: string;
  generated_at: string;
  sections: BriefSection[];
  market_sentiment: "bullish" | "neutral" | "bearish";
  key_risks: string[];
  data_provenance: DataProvenance;
}

export interface BriefSection {
  section_num: number;
  title: string;
  items: Array<{
    headline: string;
    detail: string;
    severity?: string;
  }>;
}

/** /api/analytics/yoy-comparison */
export interface YoYComparison {
  metric: string;
  production_area: number;
  current_year: number;
  current: number[];
  previous: number[];
  two_years_ago?: number[];
  delta_pct: number;
  data_provenance?: DataProvenance;
}

// ── Signals Types ────────────────────────────────────────────────────

/** Element of /api/signals response */
export interface Signal {
  id: number;
  ticker: string;
  direction: "long" | "short";
  strength: number;
  status: string;
  rationale: string;
  created_at: string;
  confirmed: boolean;
}

/** /api/regime/alerts */
export interface RegimeAlert {
  pa: number;
  pa_name?: string;
  regime: string;
  probability: number;
  message: string;
  description?: string;
}

// ── Disease & Compliance Types ───────────────────────────────────────

/** /api/disease/norway */
export interface DiseaseNorway {
  source: string;
  active_cases: number;
  active_outbreaks: DiseaseCase[];
  cases_by_disease: Record<string, number>;
  affected_companies: string[];
  total_sites_affected: number;
  data_provenance: DataProvenance;
}

export interface DiseaseCase {
  locality_no: number;
  locality_name: string;
  disease_type: string;
  suspicion_date: string;
  diagnosis_date?: string;
  status: string;
}

/** /api/disease/by-company */
export interface DiseaseByCompany {
  [companyName: string]: {
    total: number;
    active_cases: number;
    isa_cases: number;
    pd_cases: number;
    other_cases: number;
    affected_localities: number[];
  };
}

/** /api/disease/resistance-map */
export interface ResistanceMap {
  matrix: Array<{
    production_area: number;
    method: string;
    treatment_count_12m: number;
    resistance_risk: string;
    frequency_risk: string;
  }>;
  overall_risk_pa: Record<number, string>;
  freshwater_resistance_flag: boolean;
  data_provenance: DataProvenance;
}

/** /api/compliance/asc/readiness/{locality_no} */
export interface ASCReadiness {
  locality_no: number;
  overall_score: number;
  checks: Array<{
    indicator: string;
    category: string;
    title: string;
    status: "pass" | "fail" | "partial";
    data_completeness_pct: number;
    detail: string;
  }>;
  mandatory_date: string;
  days_remaining: number;
  readiness_distribution?: Record<string, number>;
  data_provenance: DataProvenance;
}

// ── ML & Forecasting Types ───────────────────────────────────────────

/** Common forecast response from Chronos/TimesFM/MOIRAI */
export interface ForecastResponse {
  horizon_weeks: number;
  current_spot_nok?: number;
  current_lice?: number;
  predicted_nok?: number;
  median: number[];
  lo80: number[];
  hi80: number[];
  lo95?: number[];
  hi95?: number[];
  direction?: string;
  confidence?: number;
  model: string;
  data_provenance: DataProvenance;
}

/** /api/ml/ensemble/price-forecast */
export interface EnsembleForecast {
  model: string;
  models_used: string[];
  horizon: number;
  median: number[];
  lo80: number[];
  hi80: number[];
  lo95: number[];
  hi95: number[];
  individual_forecasts: Record<string, {
    median: number[];
    model: string;
  }>;
  generated_at: string;
  data_provenance: DataProvenance;
}

/** /api/ml/chronos/model-comparison */
export interface ModelComparison {
  series: string;
  horizon: number;
  models: Array<{
    name: string;
    mape: number;
    rmse: number;
    coverage_80: number;
    median: number[];
    lo80: number[];
    hi80: number[];
  }>;
  data_provenance: DataProvenance;
}

// ── Notification & Alert Types ───────────────────────────────────────

/** /api/notifications/alerts */
export interface AlertsResponse {
  alerts: AlertItem[];
  count: number;
  critical: number;
  high: number;
  data_provenance?: DataProvenance;
}

export interface AlertItem {
  id: string;
  category: string;
  severity: "info" | "warning" | "high" | "critical";
  title: string;
  message: string;
  description?: string;
  metric_value: number;
  threshold: number;
  production_area?: number;
  company?: string;
  locality_no?: number;
  created_at: string;
}

/** /api/notifications/history */
export interface NotificationHistory {
  notifications: NotificationItem[];
  total: number;
  unread_count: number;
  data_provenance?: DataProvenance;
}

export interface NotificationItem {
  id: string;
  title: string;
  message: string;
  severity: "info" | "warning" | "critical";
  category: string;
  timestamp: string;
  read: boolean;
  source: string;
  metric_value?: number;
  threshold?: number;
}

// ── Ocean & Climate Types ────────────────────────────────────────────

/** /api/ocean/forecast/pa/{pa} */
export interface OceanForecast {
  production_area?: number;
  current_sst_c: number;
  forecast_sst_c: number;
  current_speed_ms: number;
  wave_height_m: number;
  next_7_days?: Array<{
    day: number;
    forecast_sst_c: number;
    wave_height_m: number;
  }>;
  data_provenance?: DataProvenance;
}

/** /api/climate/risk-scores */
export interface ClimateRiskScores {
  scores: Array<{
    production_area: number;
    sst_score: number;
    bloom_score: number;
    lice_score: number;
    composite_risk: number;
    risk_level: string;
  }>;
  data_provenance: DataProvenance;
}

/** /api/climate/heatwave-risk */
export interface HeatwaveRisk {
  assessments: Array<{
    production_area: number;
    current_sst_c: number;
    baseline_sst_c: number;
    anomaly_c: number;
    classification: "NORMAL" | "WATCH" | "WARNING" | "CRITICAL";
  }>;
  data_provenance: DataProvenance;
}

// ── Country Monitor Types ────────────────────────────────────────────

/** Generic country snapshot (Iceland, Scotland, Faroe, Canada) */
export interface CountrySnapshot {
  country: string;
  production_tonnes?: number;
  num_farms?: number;
  disease_status?: string;
  avg_sst_c?: number;
  data: Record<string, unknown>;
  data_provenance: DataProvenance;
}

// ── Sentiment & AIS Types ────────────────────────────────────────────

/** /api/sentiment/summary */
export interface SentimentSummary {
  overall_score: number;
  sentiment: "positive" | "neutral" | "negative";
  articles_24h: number;
  top_headline?: string;
  data_provenance: DataProvenance;
}

/** /api/sentiment/articles */
export interface SentimentArticle {
  title: string;
  source: string;
  url: string;
  published_at: string;
  sentiment_score: number;
  sentiment: string;
}

/** /api/ais/harvest-intelligence */
export interface AISHarvestIntel {
  active_vessels: number;
  harvest_activity: string;
  supply_impact: string;
  recent_signals: Array<{
    vessel: string;
    activity: string;
    location: string;
    timestamp: string;
  }>;
  data_provenance: DataProvenance;
}

// ── Causal & Graph Types ─────────────────────────────────────────────

/** /api/causal/summary */
export interface CausalSummary {
  dominant_relationship?: {
    source: string;
    target: string;
    lag_weeks: number;
    correlation: number;
  };
  relationships: Array<{
    source: string;
    target: string;
    correlation: number;
    lag: number;
  }>;
  data_provenance: DataProvenance;
}

// ── Global Supply Types ──────────────────────────────────────────────

/** /api/global-supply */
export interface GlobalSupply {
  countries: Array<{
    country: string;
    production_2025_kt: number;
    production_2026e_kt: number;
    yoy_growth_pct: number;
    disruption: string;
    source: string;
    currency: string;
  }>;
  total_global_kt: number;
  data_provenance: DataProvenance;
}

/** /api/supply/smolt-forecast */
export interface SmoltForecast {
  forecast_months: number;
  cohorts: Array<{
    id: string;
    smolt_date: string;
    expected_harvest: string;
    expected_weight_kg: number;
    survival_pct: number;
    volume_tonnes: number;
  }>;
  monthly_supply: Array<{
    month: string;
    tonnes: number;
    confidence_lo: number;
    confidence_hi: number;
  }>;
  demand_balance: {
    status: "surplus" | "deficit" | "balanced";
    pressure: string;
  };
  data_provenance: DataProvenance;
}

// ── Auth & Billing Types ─────────────────────────────────────────────

export interface LoginResponse {
  access_token: string;
  token_type: string;
  email: string;
  tier: string;
}

export interface SubscriptionStatus {
  tier: string;
  active: boolean;
  cancel_at_period_end: boolean;
  current_period_end?: string;
}

// ── Efficacy Marketplace Types ───────────────────────────────────────

/** /api/efficacy/benchmarks */
export interface EfficacyBenchmarks {
  methods: Array<{
    method: string;
    avg_reduction_pct: number;
    sample_size: number;
    avg_cost_nok: number;
    avg_mortality: number;
    baseline_efficacy_pct: number;
    learned_efficacy_pct?: number;
    confidence: string;
  }>;
  total_outcomes: number;
  data_provenance: DataProvenance;
}

// ── Traffic Light Types ──────────────────────────────────────────────

/** /api/regulatory/traffic-light/current */
export interface TrafficLightCurrent {
  production_areas: Array<{
    pa: number;
    color: "green" | "yellow" | "red";
    lice_avg: number;
    mab_change_pct: number;
  }>;
  data_provenance: DataProvenance;
}

/** /api/regulatory/traffic-light/simulate */
export interface TrafficLightSimulation {
  pa: number;
  from_color: string;
  to_color: string;
  mab_change_pct: number;
  companies_affected: Array<{
    company: string;
    farms_affected: number;
    tonnes_change: number;
    revenue_delta_nok: number;
  }>;
  data_provenance: DataProvenance;
}

// ── ESG Types ────────────────────────────────────────────────────────

export interface ESGScores {
  companies: Array<{
    company_name: string;
    overall_score: number;
    environmental: number;
    social: number;
    governance: number;
    rank: number;
  }>;
  data_provenance: DataProvenance;
}

// ── Treatment Types ──────────────────────────────────────────────────

export interface TreatmentCostComparison {
  methods: Array<{
    method: string;
    cost_nok: number;
    efficacy_pct: number;
    mortality_risk_pct: number;
    roi_score: number;
    recommendation_score: number;
    environmental_impact: string;
    notes: string;
  }>;
  biomass_tonnes: number;
  lice_level: number;
  data_provenance: DataProvenance;
}

export interface TreatmentOutcomeRequest {
  locality_no: number;
  method: string;
  pre_lice_count: number;
  post_lice_count: number;
  mortality_observed: number;
  cost_nok: number;
  notes?: string;
  resistance_observed?: boolean;
}

// ── Pairs Trading Types ──────────────────────────────────────────────

export interface PairsSignal {
  pair: string;
  z_score: number;
  direction: string;
  half_life_weeks: number;
  correlation: number;
}
