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
  history: SSBPriceWeekRow[];
}

/** One SSB 03024 week row (shared by /ssb-price-history and /futures-curve) */
export interface SSBPriceWeekRow {
  /** "W13" style week code (SSBPriceClient.get_price_history) */
  week: string;
  year: number;
  /** NOK per kg (key is price_nok in the route payload) */
  price_nok: number;
  label?: string;
  volume_tonnes?: number;
}

/** /api/market/futures-curve — SSB price history used as the curve */
export interface SSBPriceCurve {
  spot_nok: number;
  source?: string;
  license?: string;
  history: SSBPriceWeekRow[];
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
  scenarios?: {
    p10: number;
    p25?: number;
    p50: number;
    p75?: number;
    p90: number;
  };
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

// ── Price outlook extras (post-review corrections) ───────────────────

/** /api/market/price-outlook/multi */
export interface PriceOutlookHorizonRow {
  horizon: number;
  predicted: number;
  lo80: number;
  hi80: number;
  lo95?: number;
  hi95?: number;
  direction: string;
  mape?: number | null;
  combined?: string;
}

export interface PriceOutlookMulti {
  current_spot_nok: number;
  generated_at?: string;
  horizons: PriceOutlookHorizonRow[];
}

/** /api/market/price-outlook/explain (TFT interpretability) */
export interface PriceOutlookExplain {
  horizon_weeks: number;
  predicted_nok: number;
  model: string;
  attention?: Record<string, unknown> | null;
  /** Sorted feature importances from encoder attention (real key!) */
  top_drivers: Array<{ feature: string; importance: number }>;
}

/** /api/market/prediction-history — a LIST of PricePrediction rows */
export interface PricePredictionRow {
  created_at?: string | null;
  predicted_nok: number;
  current_spot_nok?: number | null;
  direction?: string | null;
  combined_signal?: string | null;
  horizon_weeks?: number;
  model_version?: string | null;
}

/** /api/macro/snapshot */
export interface MacroSnapshot {
  timestamp?: string;
  indices: Record<string, { value: number; label?: string; scale?: string }>;
  benchmarks: Record<string, number>;
  yoy_changes?: Record<string, number>;
  /** Plain-language alert strings (macro_intelligence.MacroSnapshotData.alerts) */
  alerts?: string[];
}

/** /api/macro/series/{name} — history response */
export interface MacroSeriesHistory {
  name: string;
  months?: number;
  data: Array<{ date: string; value: number }>;
  /** Legacy aliases tolerated by pages. */
  latest_value?: number;
  value?: number;
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
  spot_nok_kg: number | null;
  spot_eur_kg: number | null;
  eur_nok_rate: number;
  is_live: boolean;
  is_synthetic: boolean;
  curve: Array<{
    month: string;
    price_eur_kg: number;
    price_nok_kg: number;
    months_ahead: number;
    source: "fishpool_forward" | "ssb_synthetic";
  }>;
  n_months: number;
  methodology: string;
  generated_at: string;
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
/** One row of /api/leaders/top100 (top50_engine.to_api_response) */
export interface LeaderEntry {
  rank: number;
  name: string;
  ticker?: string | null;
  is_public?: boolean;
  parent_group?: string | null;
  n_localities: number;
  production_areas: number[];
  production_volume_tonnes: number;
  performance_score: number;
  score_components?: Record<string, number>;
  outlook_index?: number;
  outlook_direction?: string;
  price_impact_pct?: number;
  price_impact_direction?: string;
  risk_level?: string;
  risk_factors?: string[];
  avg_lice: number;
  max_lice?: number;
  pct_above_threshold?: number;
  lice_trend?: string;
  n_lice_records?: number;
  lice_sparkline?: number[];
  lice_prediction?: number[];
  peer_percentile?: number;
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
/** Per-company active disease counts (real keys from
 *  mattilsynet_client.get_company_disease_counts) */
export interface DiseaseCompanyCounts {
  total: number;
  isa: number;
  pd: number;
  other: number;
  localities: number[];
}

/** /api/disease/by-company (envelope corrected post-review — provenance
 *  used to be mixed into the company map itself) */
export interface DiseaseByCompany {
  companies: Record<string, DiseaseCompanyCounts>;
  count: number;
  data_provenance?: DataProvenance;
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

/** Waves endpoint (CMEMS WAM 1/12°) — /api/ocean/waves/pa/{pa} */
export interface WaveRisk {
  production_area: number;
  lat: number;
  lon: number;
  hs_m: number;
  wave_direction_deg: number | null;
  peak_period_s: number | null;
  risk: "low" | "moderate" | "high" | "severe";
  operational_note: string;
  is_live: boolean;
  source: string;
  fallback_reason?: string;
  fetched_at?: string;
  data_provenance?: {
    source: string;
    is_live: boolean;
    freshness: string;
    confidence: number;
    fallback_reason?: string | null;
    schema_version?: string;
  };
}

/** Daily-mean wave timeline — /api/ocean/waves/pa/{pa}/forecast */
export interface WaveForecastDay {
  date: string;
  hs_m: number;
  risk: "low" | "moderate" | "high" | "severe";
  operational_note: string;
}

export interface WaveForecast {
  production_area: number;
  lat: number;
  lon: number;
  days: WaveForecastDay[];
  is_live: boolean;
  source: string;
  fallback_reason?: string;
  fetched_at?: string;
  data_provenance?: {
    source: string;
    is_live: boolean;
    freshness: string;
    confidence: number;
    fallback_reason?: string | null;
    schema_version?: string;
  };
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
/** /api/sentiment/summary (contract corrected post-review — was typed
 *  against fictional `overall_score`/`sentiment` keys) */
export interface SentimentSummary {
  generated_at?: string;
  articles_24h: number;
  articles_6h?: number;
  avg_sentiment_24h: number;
  avg_sentiment_6h?: number;
  sentiment_trend?: "improving" | "deteriorating" | "stable" | string;
  categories?: Record<string, number>;
  sources?: Record<string, number>;
  high_impact_articles?: number;
  last_poll?: string | null;
  /** Legacy alias tolerated by existing pages. */
  overall_score?: number;
}

/** /api/sentiment/articles */
export interface SentimentArticle {
  id?: string;
  title: string;
  summary?: string;
  source: string;
  url?: string;
  published_at?: string | null;
  sentiment: string;
  sentiment_score: number;
  category?: string;
  companies?: string[];
  tickers?: string[];
  production_areas?: number[];
  market_impact?: number;
  keywords?: string[];
  /** Legacy display aliases some pages read defensively. */
  headline?: string;
  score?: number;
}

/** One harvest-detection row (/api/ais/harvest-signals) */
export interface AISHarvestSignalRow {
  detected_at: string;
  vessel: string;
  mmsi?: string;
  farm_locality?: string;
  farm_name?: string;
  destination?: string;
  estimated_tonnes?: number;
  company?: string;
  production_area?: number | string;
  confidence?: string;
  signal_type?: string;
}

/** /api/ais/harvest-intelligence (macro_routes — contract corrected
 *  post-review; the old type described a different, nonexistent shape) */
export interface AISHarvestIntelligence {
  generated_at?: string;
  total_vessels: number;
  summary?: {
    at_farm?: number;
    harvesting?: number;
    treating?: number;
    transiting?: number;
  };
  supply_pressure?: string;
  treatment_pressure?: string;
  harvest_signals_72h?: Array<{
    vessel: string;
    farm: string | null;
    detected_at: string;
    confidence: string;
  }>;
  treatment_signals_72h?: Array<{
    vessel: string;
    farm: string | null;
    detected_at: string;
    type: string;
  }>;
  price_signal?: string;
  signal_rationale?: string;
  data_provenance?: DataProvenance;
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
// ── Supply (smolt pipeline) ──────────────────────────────────────────

/** One month of the cohort-based smolt → harvest pipeline
 *  (/api/supply/smolt-forecast, /api/supply/summary .pipeline) */
export interface SmoltPipelinePoint {
  year: number;
  month: number;
  month_label: string;
  projected_harvest_tonnes: number;
  lo80: number;
  hi80: number;
  /** Not emitted by the engine today; the UI derives 95% bands when
   *  absent. Reserved for a future interval upgrade. */
  lo95?: number;
  hi95?: number;
  demand_tonnes: number;
  balance: number;
  n_cohorts: number;
}

/** /api/supply/smolt-forecast (envelope corrected post-review) */
export interface SmoltForecastResponse {
  pipeline: SmoltPipelinePoint[];
  horizon_months: number;
  total_harvest_tonnes: number;
  data_provenance?: DataProvenance;
}

/** One active cohort (/api/supply/cohort-timeline) */
export interface SmoltCohortRow {
  intake: string;
  region: string;
  n_smolt_millions: number;
  current_weight_kg: number;
  months_at_sea: number;
  stage: string;
  harvest_month: string;
  harvest_tonnes: number;
}

/** /api/supply/cohort-timeline (envelope corrected post-review) */
export interface SmoltCohortTimeline {
  cohorts: SmoltCohortRow[];
  count: number;
  data_provenance?: DataProvenance;
}

/** Legacy smolt-model supply/demand balance block (unmodified by R7) */
export interface SmoltDemandBalance {
  horizon_months: number;
  total_supply_tonnes: number;
  total_demand_tonnes: number;
  balance_tonnes: number;
  balance_pct: number;
  signal: string;
  price_pressure: string;
}

/** /api/supply/summary */
export interface SupplySummary {
  next_quarter_harvest_tonnes: number;
  smolt_releases_ytd_millions: number;
  supply_growth_yoy_pct: number;
  mab_utilization_pct: number;
  price_pressure: string;
  pipeline: SmoltPipelinePoint[];
  cohorts: SmoltCohortRow[];
  demand_balance: SmoltDemandBalance;
  data_provenance?: DataProvenance;
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

/** /api/esg/company/{name} (esg_scorer._to_dict) */
export interface EsgCompanyScore {
  rank: number;
  company_name: string;
  ticker?: string | null;
  /** 0-100 composite (the "total_score" alias does not exist) */
  total: number;
  grade: string;
  environmental: number;
  social: number;
  governance: number;
  breakdown?: Record<string, number>;
  n_localities?: number;
  production_areas?: number[];
  computed_at?: string;
}

/** /api/esg/scores (list of the same rows) */
export type EsgCompanyScores = EsgCompanyScore[];

// ── Pairs Trading Types ──────────────────────────────────────────────

export interface PairsSignal {
  pair: string;
  z_score: number;
  direction: string;
  half_life_weeks: number;
  correlation: number;
}

// ── Supply-Demand Intelligence (R7 /api/supply/demand-balance) ───────

export interface SupplyDemandPricePoint {
  horizon_weeks: number;
  year: number;
  iso_week: number;
  mid_nok_kg: number;
  p10?: number;
  p25?: number;
  p75?: number;
  p90?: number;
}

export interface SupplyDemandBacktest {
  generated_at?: string;
  n_origins?: number;
  min_train_weeks?: number;
  history_weeks?: number;
  mape?: Record<string, number>;
  coverage_80_band_walk_forward?: Record<string, number>;
  components_backtested?: string[];
  components_not_backtested?: string[];
}

export interface SupplyDemandForecast {
  horizon_weeks: number;
  generated_week: string;
  horizon_reference?: string;
  spot_nok_kg: number;
  spot_week: string;
  spot_lag_weeks?: number;
  seasonal_median_nok_kg: number;
  gap_vs_seasonal_pct: number;
  global_deficit_tilt_pct: number;
  lice_tilt_pct: number;
  combined_tilt_pct: number;
  method: string;
  bands_source: string;
  components_backtested: string[];
  components_heuristic: string[];
  history_weeks_used: number;
  weekly: SupplyDemandPricePoint[];
  backtest: SupplyDemandBacktest | null;
}

export interface SupplyDemandBalance {
  // Legacy smolt-model fields (unchanged by R7)
  horizon_months: number;
  total_supply_tonnes: number;
  total_demand_tonnes: number;
  balance_tonnes: number;
  balance_pct: number;
  signal: string;
  price_pressure: string;
  // Additive R7 integration payload
  balance_label?: string;
  integration?: {
    engine: string;
    contract: string;
    composed_at: string;
    sources: string[];
    fallbacks: string[];
  };
  supply_breakdown?: Record<string, number | string | null>;
  demand_breakdown?: Record<string, number | string | null>;
  price_forecast?: SupplyDemandForecast | null;
  data_provenance?: DataProvenance;
}

// ── Market page contracts (post-review corrections) ──────────────────

/** One Market Hedger Agent row (/api/market/hedger-signals — a LIST) */
export interface HedgerSignalRow {
  id?: number;
  ticker: string;
  direction: string;
  strength?: number;
  rationale?: string;
  status?: string;
  created_at?: string | null;
}

/** /api/market/export-destinations — destinations is a DICT keyed by
 *  country code (SSB 08799), not a list */
export interface ExportDestinationsResponse {
  months_analyzed?: number;
  n_destinations?: number;
  destinations: Record<
    string,
    {
      name?: string;
      total_tonnes?: number;
      total_nok_millions?: number;
      avg_price_nok_kg?: number;
      trend_pct?: number;
      months_with_data?: number;
    }
  >;
  monthly_series?: Array<Record<string, unknown>>;
  source?: string;
  license?: string;
}

// ── China Demand (review L5 typing slice) ────────────────────────────

/** One month of Norwegian exports to China (SSB table 08799) */
export interface ChinaMonthlyExportPoint {
  month: string;
  tonnes: number;
  value_mnok: number;
}

export interface ChinaNorwayExports {
  tonnes_12m: number;
  nok_millions_12m?: number;
  avg_price_nok_kg?: number;
  yoy_trend_pct?: number;
  /** Structured liveness contract (review M3): records-based, never a
   *  rounded tonnage. Use this instead of parsing `data_source`. */
  is_live?: boolean;
  data_source?: string;
}

export interface ChinaSupplierRow {
  origin: string;
  flag: string;
  tonnes: number;
  share_pct: number;
  is_live?: boolean;
  data_source?: string;
  yoy_growth_pct?: number;
}

export interface ChinaTotalImports {
  tonnes_annual?: number;
  estimate_year?: number;
  data_source?: string;
}

/** /api/china/demand */
export interface ChinaDemandSnapshot {
  source?: string;
  fetched_at?: string;
  norway_exports_to_china?: ChinaNorwayExports;
  china_total_imports?: ChinaTotalImports;
  monthly_series?: ChinaMonthlyExportPoint[];
  suppliers?: ChinaSupplierRow[];
  norway_share_pct?: number;
  data_provenance?: DataProvenance;
}

/** /api/china/demand-signals */
export interface ChinaMomentumPoint {
  month: string;
  rolling_3m_tonnes: number;
  monthly_tonnes?: number;
}

export interface ChinaDemandSignals {
  yoy_growth_pct?: number;
  acceleration_pct?: number;
  seasonal_index?: number;
  seasonal_label?: string;
  market_growth_pct?: number;
  signal_score?: number;
  signal_label?: string;
  signal_direction?: string;
  momentum_chart?: ChinaMomentumPoint[];
  insights?: string[];
  data_provenance?: DataProvenance;
}

/** /api/china/demand-impact */
export interface ChinaDemandImpact {
  correlation_vol_price?: number;
  estimated_price_impact_pct?: number;
  impact_label?: string;
  demand_direction?: string;
  yoy_growth_pct?: number;
  china_share_of_norway_exports?: number;
  transmission_mechanism?: string;
  assessment?: string;
  data_provenance?: DataProvenance;
}
