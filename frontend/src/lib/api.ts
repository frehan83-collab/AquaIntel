 
/**
 * FishIntel Backend API Client
 * ============================
 * Typed API client for AquaIntelligence platform.
 * Response types defined in @/types/api.ts
 *
 * NOTE: eslint-disable kept temporarily during incremental typing migration.
 * Target: remove once all 180+ methods are fully typed (Session 29+).
 */
import type {
  HealthResponse, LiceSummary, DecisionCard, FarmPortfolioResponse,
  BiomassNational, MarketBiomass, BillingCatalog, IndicesResponse, IndexResult, BioPriceWeekly,
  AccuracySummary, SSBPriceHistory, FeedCostLatest, CompetitivenessIndex,
  FuturesForwardCurve, FuturesBasis, LeaderEntry, AnomalyScores,
  MorningBrief, RegimeAlert, DiseaseNorway, DiseaseByCompany,
  ResistanceMap, ASCReadiness, ForecastResponse, EnsembleForecast,
  AlertsResponse, OceanForecast, ClimateRiskScores, HeatwaveRisk,
  SentimentSummary, AISHarvestIntelligence, AISHarvestSignalRow, SentimentArticle,
  HedgerSignalRow, ExportDestinationsResponse, MacroSnapshot, MacroSeriesHistory,
  PriceOutlook, PriceOutlookMulti, PriceOutlookExplain, PricePredictionRow, SSBPriceCurve,
  EsgCompanyScore,
  CausalSummary, GlobalSupply,
  WaveRisk,
  WaveForecast,
  SmoltForecastResponse, SmoltCohortTimeline, SupplySummary, SupplyDemandBalance,
  DiseaseAlerts, DiseaseTreatments,
  FeedSupplyChainSummary, FeedCompositionRow, FeedScenarioRow, FeedSankey,
  LoginResponse, SubscriptionStatus, EfficacyBenchmarks,
  TrafficLightCurrent, TrafficLightSimulation, TreatmentCostComparison,
  YoYComparison,
  ChinaDemandSnapshot, ChinaDemandSignals, ChinaDemandImpact,
  RegimeState, EquityPriceResponse, EsgCompanyScores,
  CompetitivenessScenarioResponse,
  MarketSpotPrice, MarketForwardCurve, FeedCostCompositeIndex,
  MarginBridge,
  ChatAnswerResponse, ChatHistoryTurn, ChatUsageStatus, ChatSaveAlertResponse,
  WorkbenchCatalog, WorkbenchDocument, CreditsStatus,
  EventImpactResult, SavedScenario, SignalsWithdrawn,
} from "@/types/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Auth wiring ──────────────────────────────────────────────────────────────
// The token is written at login and must be sent as a Bearer header on every
// request; before this the client never authenticated at all, so user-scoped
// routes (billing, API keys, webhooks) and the per-user tier quota could not
// work from the UI. Keys are exported so login/logout cannot drift from them.
export const AUTH_TOKEN_KEY = "aquaintel_token";
export const AUTH_USER_KEY = "aquaintel_user";

function authHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  try {
    const token = window.localStorage.getItem(AUTH_TOKEN_KEY);
    return token ? { Authorization: `Bearer ${token}` } : {};
  } catch {
    return {};
  }
}

/** Drop a server-rejected token and send the user to /login exactly once. */
function handleUnauthorized(): void {
  if (typeof window === "undefined") return;
  try {
    if (!window.localStorage.getItem(AUTH_TOKEN_KEY)) return; // anonymous user — stay put
    window.localStorage.removeItem(AUTH_TOKEN_KEY);
    window.localStorage.removeItem(AUTH_USER_KEY);
    if (!window.location.pathname.startsWith("/login")) {
      window.location.assign("/login");
    }
  } catch {
    /* storage unavailable — nothing to clear */
  }
}

async function fetchAPI<T = any>(
  path: string,
  options?: RequestInit,
  _retries = 3,
): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10_000);

  try {
    const res = await fetch(`${API_BASE}${path}`, {
      ...options,
      signal: controller.signal,
      headers: { ...authHeaders(), "Content-Type": "application/json", ...options?.headers },
    });

    if (!res.ok) {
      // A rejected token is stale: clear it and route to /login (once).
      if (res.status === 401) handleUnauthorized();
      // Only retry on 5xx (server errors), not 4xx (client errors)
      if (res.status >= 500 && _retries > 1) {
        const delay = [500, 1500, 3500][3 - _retries] ?? 500;
        await new Promise((r) => setTimeout(r, delay));
        return fetchAPI<T>(path, options, _retries - 1);
      }
      throw new Error(`API ${res.status}: ${res.statusText}`);
    }

    const json = await res.json();
    // Auto-unwrap provenance-wrapped responses: {data: T, data_provenance: {...}}
    if (json && typeof json === "object" && !Array.isArray(json) && "data" in json && "data_provenance" in json) {
      return json.data as T;
    }
    return json as T;
  } catch (err) {
    // Retry on network errors and timeouts, not on client errors
    if (_retries > 1 && (err instanceof TypeError || (err instanceof DOMException && err.name === "AbortError"))) {
      const delay = [500, 1500, 3500][3 - _retries] ?? 500;
      await new Promise((r) => setTimeout(r, delay));
      return fetchAPI<T>(path, options, _retries - 1);
    }
    throw err;
  } finally {
    clearTimeout(timeout);
  }
}

/** Like fetchAPI but never throws on 4xx: returns the status and parsed body.

 * The chat's 402 is a product surface (plan, allowance, upgrade path), not an error.
 */
export async function fetchAPIRaw<T = unknown>(
  path: string,
  options?: RequestInit,
): Promise<{ ok: boolean; status: number; body: T | null }> {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: { ...authHeaders(), "Content-Type": "application/json", ...options?.headers },
    });
    if (res.status === 401) handleUnauthorized();
    let body: T | null = null;
    try {
      body = (await res.json()) as T;
    } catch {
      body = null;
    }
    return { ok: res.ok, status: res.status, body };
  } catch {
    return { ok: false, status: 0, body: null };
  }
}

export const api = {
  health: () => fetchAPI<HealthResponse>("/api/health"),
  // WS-20: equity direction signals are withdrawn — the route serves the notice
  // only; confirm/reject answer 410 and have no client method.
  signals: () => fetchAPI<SignalsWithdrawn>("/api/signals"),
  liceSummary: () => fetchAPI<LiceSummary>("/api/lice/summary"),
  orders: () => fetchAPI("/api/orders"),
  audit: () => fetchAPI("/api/audit"),
  tiers: () => fetchAPI("/api/tiers"),
  supplyForecast: () => fetchAPI("/api/supply-forecast"),
  smoltForecast: (months?: number): Promise<SmoltForecastResponse> =>
    fetchAPI<SmoltForecastResponse>(`/api/supply/smolt-forecast?months=${months || 18}`),
  cohortTimeline: (): Promise<SmoltCohortTimeline> => fetchAPI<SmoltCohortTimeline>("/api/supply/cohort-timeline"),
  supplyDemandBalance: (): Promise<SupplyDemandBalance> => fetchAPI<SupplyDemandBalance>("/api/supply/demand-balance"),
  supplySummary: (): Promise<SupplySummary> => fetchAPI<SupplySummary>("/api/supply/summary"),
  farmerAdvisory: (localityNo: number) => fetchAPI(`/api/farmer-advisory/${localityNo}`),

  // ML Price Predictions
  priceOutlook: (horizon?: number, scenarios?: number): Promise<PriceOutlook> =>
    fetchAPI<PriceOutlook>(`/api/market/price-outlook?horizon=${horizon || 4}&scenarios=${scenarios || 1000}`),
  priceOutlookMulti: (): Promise<PriceOutlookMulti> =>
    fetchAPI<PriceOutlookMulti>("/api/market/price-outlook/multi"),
  futuresCurve: (): Promise<SSBPriceCurve> => fetchAPI<SSBPriceCurve>("/api/market/futures-curve"),
  hedgerSignals: () => fetchAPI<HedgerSignalRow[]>("/api/market/hedger-signals"),
  predictionHistory: (horizon?: number, days?: number): Promise<PricePredictionRow[]> =>
    fetchAPI<PricePredictionRow[]>(`/api/market/prediction-history?horizon=${horizon || 4}&days=${days || 30}`),
  priceOutlookExplain: (horizon?: number): Promise<PriceOutlookExplain> =>
    fetchAPI<PriceOutlookExplain>(`/api/market/price-outlook/explain?horizon=${horizon || 4}`),
  selfImprovementProposals: () => fetchAPI("/api/self-improvement/proposals"),

  // SSB Real Data
  ssbPriceHistory: (weeks?: number) =>
    fetchAPI<SSBPriceHistory>(`/api/market/ssb-price-history?weeks=${weeks || 52}`),
  ssbSeasonal: () => fetchAPI("/api/market/ssb-seasonal"),
  exportDestinations: (months?: number) =>
    fetchAPI<ExportDestinationsResponse>(`/api/market/export-destinations?months=${months || 12}`),

  // Top 100 Leaders — auto-unwrapped by fetchAPI
  leadersTop30: (): Promise<LeaderEntry[]> => fetchAPI<LeaderEntry[]>("/api/leaders/top100"),
  leaderDetail: (name: string) => fetchAPI(`/api/leaders/company/${encodeURIComponent(name)}`),
  paLeaderboard: () => fetchAPI("/api/leaders/pa-leaderboard"),
  exposureSites: () => fetchAPI("/api/exposure/sites"),

  // Digital Twin
  twinSync: () => fetchAPI("/api/twin/sync", { method: "POST" }),
  twinStatus: () => fetchAPI("/api/twin/status"),
  twinSimulate: (params: { weeks?: number; temp_delta?: number; treat_above?: number | null; treatment_type?: string; add_cleaner_fish_pct?: number }) =>
    fetchAPI("/api/twin/simulate", { method: "POST", body: JSON.stringify(params) }),
  // GLODAPv2 ocean chemistry removed — not useful for coastal salmon operations

  // Algal Bloom
  bloomRisk: () => fetchAPI("/api/bloom/risk"),
  bloomRiskLocality: (localityNo: number, days?: number) =>
    fetchAPI(`/api/bloom/risk/${localityNo}${days ? `?days=${days}` : ""}`),
  bloomAlerts: (riskLevel?: string) =>
    fetchAPI(`/api/bloom/alerts${riskLevel ? `?risk_level=${riskLevel}` : ""}`),
  bloomChlorophyll: (days?: number) =>
    fetchAPI(`/api/bloom/chlorophyll${days ? `?days=${days}` : ""}`),
  /** Dated context: IMR Algestatus link (manual, no API), regional event history,
   *  and the stated limits of a satellite chlorophyll band (WS-34). */
  bloomContext: () => fetchAPI("/api/bloom/context"),

  // Bio Risk Snapshot (time slider)
  bioRiskSnapshot: (weekOffset = 0) =>
    fetchAPI(`/api/bio-risk/snapshot?week_offset=${weekOffset}`),

  // AIS Vessel Tracking
  aisTracks: () => fetchAPI("/api/ais/tracks"),
  aisHarvestSignals: (hours?: number) => fetchAPI<AISHarvestSignalRow[]>(`/api/ais/harvest-signals?hours=${hours || 72}`),
  aisTreatmentSignals: (hours?: number) =>
    fetchAPI(`/api/ais/treatment-signals?hours=${hours || 72}`),
  aisSupplyIntel: () => fetchAPI("/api/ais/supply-intelligence"),

  // Sentiment Engine
  sentimentSignals: () => fetchAPI("/api/sentiment/signals"),
  sentimentArticles: (hours?: number, ticker?: string) =>
    fetchAPI<SentimentArticle[]>(`/api/sentiment/articles?hours=${hours || 24}${ticker ? `&ticker=${ticker}` : ""}`),
  sentimentSummary: () => fetchAPI<SentimentSummary>("/api/sentiment/summary"),

  // Farm Network Graph
  farmGraphSummary: () => fetchAPI("/api/farm-graph/summary"),
  farmGraphClusters: (riskLevel?: string) =>
    fetchAPI(`/api/farm-graph/clusters${riskLevel ? `?risk_level=${riskLevel}` : ""}`),
  farmGraphCascades: () => fetchAPI("/api/farm-graph/cascades"),
  farmGraphCompanyExposure: () => fetchAPI("/api/farm-graph/company-exposure"),
  farmGraphMapData: () => fetchAPI("/api/farm-graph/map-data"),
  farmGraphFarm: (localityNo: number) => fetchAPI(`/api/farm-graph/farm/${localityNo}`),

  // Regulatory Regime
  regimeStates: () => fetchAPI<RegimeState[]>("/api/regime/states"),
  regimeAlerts: () => fetchAPI<RegimeAlert[]>("/api/regime/alerts"),
  regimePaDetail: (pa: number) => fetchAPI(`/api/regime/pa/${pa}`),
  regimeCompanyRisk: () => fetchAPI("/api/regime/company-risk"),

  // Cross-Market Arbitrage (Chile)
  chileSnapshot: () => fetchAPI("/api/chile/snapshot"),
  chileSignals: (days?: number) => fetchAPI(`/api/chile/signals?days=${days || 30}`),
  chileGlobalSupply: () => fetchAPI("/api/chile/global-supply"),
  chileRefresh: () => fetchAPI("/api/chile/refresh", { method: "POST" }),

  // China Demand Indicators
  chinaDemand: (): Promise<ChinaDemandSnapshot> => fetchAPI<ChinaDemandSnapshot>("/api/china/demand"),
  chinaDemandSignals: (): Promise<ChinaDemandSignals> => fetchAPI<ChinaDemandSignals>("/api/china/demand-signals"),
  chinaDemandImpact: (): Promise<ChinaDemandImpact> => fetchAPI<ChinaDemandImpact>("/api/china/demand-impact"),

  // Statistical Pairs Trading
  pairsAll: () => fetchAPI("/api/pairs/all"),
  pairsSignals: (days?: number) => fetchAPI(`/api/pairs/signals?days=${days || 7}`),
  pairDetail: (pairName: string) => fetchAPI(`/api/pairs/${pairName}`),

  // Unified Intelligence
  intelligenceSummary: () => fetchAPI("/api/intelligence/summary"),
  intelligenceHealth: () => fetchAPI("/api/intelligence/health"),

  // Backtest Engine
  // backtest removed — mock data provides no value

  // Market data — Fish Pool Index + equity prices
  // fishPoolIndex removed — fishpool.eu dead since 2025
  equityPrices: () => fetchAPI<EquityPriceResponse>("/api/market/equity-prices"),

  // Lice GNN
  gnnStatus: () => fetchAPI("/api/gnn/status"),
  gnnBuildData: () =>
    fetchAPI("/api/gnn/build-training-data", { method: "POST" }),
  gnnTrain: (epochs?: number) =>
    fetchAPI(`/api/gnn/train?epochs=${epochs || 50}`, { method: "POST" }),
  gnnPredict: (localityNo: number) => fetchAPI(`/api/gnn/predict/${localityNo}`),
  gnnPredictAll: () => fetchAPI("/api/gnn/predict-all"),

  // Ocean currents (CMEMS NorKyst800)
  oceanCurrentsStatus: () => fetchAPI("/api/ocean/currents/status"),
  oceanCurrentsRefresh: () => fetchAPI("/api/ocean/currents/refresh", { method: "POST" }),
  oceanTemperature: (lat: number, lon: number) => fetchAPI(`/api/ocean/temperature?lat=${lat}&lon=${lon}`),

  // Causal inference engine
  causalSummary: (maxLag?: number) => fetchAPI<CausalSummary>(`/api/causal/summary?max_lag=${maxLag || 16}`),
  causalGranger: (maxLag?: number) => fetchAPI(`/api/causal/granger?max_lag=${maxLag || 16}`),

  // Feed Cost Index
  feedCostLatest: () => fetchAPI<FeedCostLatest>("/api/feed-cost/latest"),
  feedCostHistory: (n?: number) => fetchAPI(`/api/feed-cost/history?n=${n || 50}`),
  feedCostHistorical: (years?: number) => fetchAPI(`/api/feed-cost/historical-prices?years=${years || 5}`),
  /**
   * The margin bridge: price and cost as one margin per kg, with what moved, the
   * break-even and the levers. Every override is optional; without them the bridge
   * is the modelled industry cost base (flagged `modelled`, never `measured`).
   * Passing both `fcr`/`feed` and `spot` is what makes it your own margin.
   */
  marginBridge: (params?: {
    fcr?: number;
    feed?: number;
    spot?: number;
    annualTonnes?: number;
    standingTonnes?: number;
    localityNo?: number;
  }) => {
    const query = new URLSearchParams();
    if (params?.fcr) query.set("fcr", String(params.fcr));
    if (params?.feed) query.set("delivered_feed_nok_per_kg", String(params.feed));
    if (params?.spot) query.set("spot_nok_per_kg", String(params.spot));
    if (params?.annualTonnes) query.set("annual_tonnes", String(params.annualTonnes));
    if (params?.standingTonnes) query.set("standing_tonnes", String(params.standingTonnes));
    const path = params?.localityNo
      ? `/api/margin/bridge/${params.localityNo}`
      : "/api/margin/bridge";
    const suffix = query.toString();
    return fetchAPI<MarginBridge>(suffix ? `${path}?${suffix}` : path);
  },
  // Anomaly Detection
  anomalyScores: () => fetchAPI<AnomalyScores>("/api/anomaly/scores"),
  anomalyAlerts: () => fetchAPI("/api/anomaly/alerts"),

  feedCostCompositeIndex: (years?: number) => fetchAPI<FeedCostCompositeIndex>(`/api/feed-cost/composite-index?years=${years || 5}`),
  feedCostPeruAnchovy: () => fetchAPI("/api/feed-cost/peru-anchovy"),
  // Feed Intelligence
  enhancedAnchovyWatch: () => fetchAPI("/api/feed-cost/enhanced-anchovy"),
  feedCostAlerts: () => fetchAPI("/api/feed-cost/alerts"),
  feedCostOfficialHistory: () => fetchAPI("/api/feed-cost/official-history"),

  // Official Fiskeridirektoratet Production Data
  productionSummary: () => fetchAPI("/api/production/summary"),
  productionAnnual: () => fetchAPI("/api/production/annual"),
  productionMonthly: (year?: number) => fetchAPI(`/api/production/monthly${year ? `?year=${year}` : ""}`),
  productionByCounty: () => fetchAPI("/api/production/by-county"),

  // Macro Intelligence (FRED)
  macroSnapshot: () => fetchAPI<MacroSnapshot>("/api/macro/snapshot"),
  macroSeries: (name: string, months?: number) => fetchAPI<MacroSeriesHistory>(`/api/macro/series/${name}?months=${months || 60}`),

  // ESG Sustainability Scores
  esgScores: () => fetchAPI<EsgCompanyScores>("/api/esg/scores"),
  esgSummary: () => fetchAPI("/api/esg/summary"),
  esgCompany: (name: string): Promise<EsgCompanyScore> => fetchAPI<EsgCompanyScore>(`/api/esg/company/${encodeURIComponent(name)}`),

  // Ocean Forecast (MET.no)
  oceanForecast: (lat: number, lon: number) => fetchAPI(`/api/ocean/forecast?lat=${lat}&lon=${lon}`),
  oceanForecastPa: (pa: number) => fetchAPI<OceanForecast>(`/api/ocean/forecast/pa/${pa}`),

  // Waves (CMEMS WAM 1/12°) — per Production Area
  waveRiskPa: (pa: number) => fetchAPI<WaveRisk>(`/api/ocean/waves/pa/${pa}`),
  waveForecastPa: (pa: number, days = 5) =>
    fetchAPI<WaveForecast>(`/api/ocean/waves/pa/${pa}/forecast?days=${days}`),
  wavesStatus: () => fetchAPI<Record<string, unknown>>("/api/ocean/waves/status"),

  // AIS Harvest Intelligence
  aisHarvestIntelligence: () => fetchAPI<AISHarvestIntelligence>("/api/ais/harvest-intelligence"),

  // Advanced Biomass Prediction
  biomassOutlook: (horizon?: number, scenarios?: number, regulatory?: string) =>
    fetchAPI(`/api/biomass/outlook?horizon=${horizon || 20}&scenarios=${scenarios || 1000}&regulatory=${regulatory || "current"}`),
  biomassScenarios: () => fetchAPI("/api/biomass/scenarios"),

  // Benchmarking
  benchmarkLeaderboard: (limit?: number) => fetchAPI(`/api/benchmark/leaderboard?limit=${limit || 20}`),
  benchmarkCompany: (name: string) => fetchAPI(`/api/benchmark/company/${encodeURIComponent(name)}`),
  benchmarkPa: (pa: number) => fetchAPI(`/api/benchmark/pa/${pa}`),
  benchmarkSummary: () => fetchAPI("/api/benchmark/summary"),

  // Federated Benchmarking (Privacy-Preserving)
  federatedCompany: (name: string) => fetchAPI(`/api/federated/company/${encodeURIComponent(name)}`),
  federatedCohorts: () => fetchAPI("/api/federated/cohorts"),
  federatedCohortSummary: (id: string) => fetchAPI(`/api/federated/cohort/${encodeURIComponent(id)}/summary`),
  federatedPrivacyInfo: () => fetchAPI("/api/federated/privacy-info"),

  // Auth
  register: (email: string, password: string, company?: string, role?: string) =>
    fetchAPI("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, company: company || "", role: role || "farmer" }),
    }),
  login: (email: string, password: string) =>
    fetchAPI<LoginResponse>("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  authTiers: () => fetchAPI("/api/auth/tiers"),

  // Morning Brief
  brief: () => fetchAPI<MorningBrief>("/api/brief"),

  // Global Supply Balance
  globalSupply: () => fetchAPI<GlobalSupply>("/api/global-supply"),

  // Competitiveness Index
  competitivenessIndex: () => fetchAPI<CompetitivenessIndex>("/api/competitiveness/origin-index"),
  competitivenessTariffScenario: (tariffs: Record<string, number>) =>
    fetchAPI<CompetitivenessScenarioResponse>("/api/competitiveness/tariff-scenario", { method: "POST", body: JSON.stringify(tariffs) }),

  // Disease Alerts
  diseaseAlerts: (): Promise<DiseaseAlerts> => fetchAPI<DiseaseAlerts>("/api/disease/alerts"),
  diseaseNorway: (): Promise<DiseaseNorway> => fetchAPI<DiseaseNorway>("/api/disease/norway").then((r) => {
    // Ensure active_outbreaks is always an array for .filter() safety
    if (r && !Array.isArray(r.active_outbreaks)) r.active_outbreaks = [];
    return r;
  }),
  diseaseTreatments: (year?: number): Promise<DiseaseTreatments> =>
    fetchAPI<DiseaseTreatments>(`/api/disease/treatments?year=${year || 2026}`),
  diseaseByCompany: () => fetchAPI<DiseaseByCompany>("/api/disease/by-company"),
  resistanceMap: () => fetchAPI<ResistanceMap>("/api/disease/resistance-map"),
  resistanceByPA: (pa: number) => fetchAPI(`/api/disease/resistance/pa/${pa}`),

  // Iceland
  icelandSnapshot: () => fetchAPI("/api/iceland/snapshot"),
  icelandProduction: () => fetchAPI("/api/iceland/production"),
  icelandFarms: () => fetchAPI("/api/iceland/farms"),
  icelandExports: () => fetchAPI("/api/iceland/exports"),

  // Scotland
  scotlandSnapshot: () => fetchAPI("/api/scotland/snapshot"),
  scotlandFarms: () => fetchAPI("/api/scotland/farms"),

  // Faroe Islands
  faroeSnapshot: () => fetchAPI("/api/faroe/snapshot"),
  faroeFarms: () => fetchAPI("/api/faroe/farms"),

  // Chile farms
  chileFarms: () => fetchAPI("/api/chile/farms"),

  // Canada / BC
  canadaSnapshot: () => fetchAPI("/api/canada/snapshot"),
  canadaFarms: () => fetchAPI("/api/canada/farms"),
  canadaLice: () => fetchAPI("/api/canada/lice"),
  canadaLiceByRegion: () => fetchAPI("/api/canada/lice-by-region"),

  // Global merged data layers (all countries in one call each)
  globalFarms: () => fetchAPI("/api/global/farms"),
  globalBloomRisk: () => fetchAPI("/api/global/bloom-risk"),
  globalDiseaseGeo: () => fetchAPI("/api/global/disease-geo"),
  globalLice: () => fetchAPI("/api/global/lice"),

  // AI Chat (WS-38): one grounded path, metered against the plan allowance, and the
  // 402 body is returned rather than thrown so the page can explain the upgrade.
  chat: (message: string, history: ChatHistoryTurn[] = []) =>
    fetchAPIRaw<ChatAnswerResponse>("/api/chat", {
      method: "POST",
      body: JSON.stringify({ message, history }),
    }),
  chatUsage: () => fetchAPI<ChatUsageStatus>("/api/chat/usage"),
  chatSaveAlert: (question: string, name?: string) =>
    fetchAPI<ChatSaveAlertResponse>("/api/chat/save-alert", {
      method: "POST",
      body: JSON.stringify({ question, name }),
    }),
  // Deep analysis (WS-39): documents are bought with credits, chat is included.
  workbenchCatalog: () => fetchAPI<WorkbenchCatalog>("/api/workbench/catalog"),
  workbenchRun: (kind: string) =>
    fetchAPIRaw<WorkbenchDocument>("/api/workbench/run", {
      method: "POST",
      body: JSON.stringify({ kind }),
    }),
  creditsStatus: () => fetchAPI<CreditsStatus>("/api/billing/credits"),

  // Alert Notification System
  alerts: (category?: string, severity?: string, unreadOnly?: boolean, limit?: number) =>
    fetchAPI(`/api/alerts?${new URLSearchParams({
      ...(category ? { category } : {}),
      ...(severity ? { severity } : {}),
      ...(unreadOnly ? { unread_only: "true" } : {}),
      ...(limit ? { limit: String(limit) } : {}),
    }).toString()}`),
  alertsCheck: () => fetchAPI("/api/alerts/check", { method: "POST" }),
  alertsSummary: () => fetchAPI("/api/alerts/summary"),
  alertMarkRead: (id: string) => fetchAPI(`/api/alerts/${id}/read`, { method: "POST" }),
  alertsMarkAllRead: () => fetchAPI("/api/alerts/read-all", { method: "POST" }),
  alertPreferences: () => fetchAPI("/api/alerts/preferences"),
  alertUpdatePreferences: (prefs: Record<string, any>) =>
    fetchAPI("/api/alerts/preferences", { method: "POST", body: JSON.stringify(prefs) }),

  // Parametric Insurance
  parametricProducts: () => fetchAPI("/api/parametric/products"),
  parametricScan: () => fetchAPI("/api/parametric/scan", { method: "POST" }),
  parametricTriggers: (product?: string, confirmedOnly?: boolean) =>
    fetchAPI(`/api/parametric/triggers?${new URLSearchParams({
      ...(product ? { product } : {}),
      ...(confirmedOnly ? { confirmed_only: "true" } : {}),
    }).toString()}`),
  parametricDashboard: () => fetchAPI("/api/parametric/dashboard"),
  parametricRiskProfile: (localityNo?: number, pa?: number) =>
    fetchAPI(`/api/parametric/risk-profile?${new URLSearchParams({
      ...(localityNo ? { locality_no: String(localityNo) } : {}),
      ...(pa ? { pa: String(pa) } : {}),
    }).toString()}`),

  // Contract Risk Analyzer
  contractsEvaluate: (position: Record<string, any>) =>
    fetchAPI("/api/contracts/evaluate", { method: "POST", body: JSON.stringify(position) }),
  contractsPortfolio: (positions: Record<string, any>[]) =>
    fetchAPI("/api/contracts/portfolio", { method: "POST", body: JSON.stringify({ positions }) }),
  contractsHedgeSignals: () => fetchAPI("/api/contracts/hedge-signals"),

  // Climate Risk Scores
  climateRiskScores: () => fetchAPI<ClimateRiskScores>("/api/climate/risk-scores"),
  climatePa: (pa: number) => fetchAPI(`/api/climate/pa/${pa}`),
  climateProjections: (pa?: number, years?: number) =>
    fetchAPI(`/api/climate/projections?pa=${pa || 3}&years=${years || 5}`),
  marineHeatwaveRisk: () => fetchAPI<HeatwaveRisk>("/api/climate/heatwave-risk"),

  // Satellite Intelligence (Sentinel-2)
  satelliteStatus: () => fetchAPI("/api/satellite/status"),
  satelliteProducts: () => fetchAPI("/api/satellite/products"),
  satelliteScan: (nFarms?: number) =>
    fetchAPI(`/api/satellite/scan?n_farms=${nFarms || 50}`, { method: "POST" }),
  satelliteAnomalies: () => fetchAPI("/api/satellite/anomalies"),

  // Treatment Cost Optimizer
  treatmentOptimize: (localityNo: number, budget?: number) =>
    fetchAPI(`/api/treatment/optimize/${localityNo}${budget ? `?budget=${budget}` : ""}`),
  treatmentCompare: (localityNo: number) =>
    fetchAPI(`/api/treatment/compare/${localityNo}`),
  treatmentNetworkSchedule: (pa: number) =>
    fetchAPI(`/api/treatment/network-schedule/${pa}`),
  treatmentCostBenefit: (localityNo: number, treatmentType?: string) =>
    fetchAPI(`/api/treatment/cost-benefit/${localityNo}?treatment_type=${treatmentType || "mechanical"}`),
  treatmentCostComparison: (biomass?: number, liceLevel?: number, localityNo?: number) =>
    fetchAPI<TreatmentCostComparison>(`/api/treatment/cost-comparison?biomass_tonnes=${biomass || 500}&lice_level=${liceLevel || 0.5}${localityNo ? `&locality_no=${localityNo}` : ""}`),

  // RAS (Land-Based Salmon) Production Tracker
  rasCompanies: () => fetchAPI("/api/ras/companies"),
  rasSummary: () => fetchAPI("/api/ras/summary"),
  rasTimeline: () => fetchAPI("/api/ras/timeline"),

  // Harvest Optimizer (RL Foundation)
  harvestOptimize: (localityNo: number) =>
    fetchAPI(`/api/harvest/optimize/${localityNo}`),
  harvestPortfolio: (companyName: string) =>
    fetchAPI(`/api/harvest/portfolio/${encodeURIComponent(companyName)}`),
  harvestSimulate: (localityNo: number, weeks?: number) =>
    fetchAPI(`/api/harvest/simulate?locality_no=${localityNo}&weeks=${weeks || 12}`),

  // Chronos-2 ML Baselines
  chronosPriceForecast: (horizon?: number) =>
    fetchAPI<ForecastResponse>(`/api/ml/chronos/price-forecast?horizon=${horizon || 4}`),
  chronosLiceForecast: (localityNo: number, horizon?: number) =>
    fetchAPI(`/api/ml/chronos/lice-forecast/${localityNo}?horizon=${horizon || 8}`),
  chronosTemperatureForecast: (localityNo: number, horizon?: number) =>
    fetchAPI(`/api/ml/chronos/temperature-forecast/${localityNo}?horizon=${horizon || 8}`),
  chronosSupplyForecast: (horizon?: number) =>
    fetchAPI(`/api/ml/chronos/supply-forecast?horizon=${horizon || 6}`),
  chronosModelComparison: (series?: string, horizon?: number) =>
    fetchAPI(`/api/ml/chronos/model-comparison?series=${series || "price"}&horizon=${horizon || 4}`),
  chronosCustomForecast: (values: number[], horizon?: number) =>
    fetchAPI("/api/ml/chronos/custom-forecast", {
      method: "POST",
      body: JSON.stringify({ values, horizon: horizon || 8 }),
    }),

  // TimesFM 2.5 Zero-Shot Forecasting
  timesfmPriceForecast: (horizon?: number) =>
    fetchAPI<ForecastResponse>(`/api/ml/timesfm/price-forecast?horizon=${horizon || 4}`),
  timesfmLiceForecast: (localityNo: number, horizon?: number) =>
    fetchAPI(`/api/ml/timesfm/lice-forecast/${localityNo}?horizon=${horizon || 8}`),
  timesfmTemperatureForecast: (localityNo: number, horizon?: number) =>
    fetchAPI(`/api/ml/timesfm/temperature-forecast/${localityNo}?horizon=${horizon || 8}`),
  timesfmSupplyForecast: (horizon?: number) =>
    fetchAPI(`/api/ml/timesfm/supply-forecast?horizon=${horizon || 6}`),
  timesfmModelComparison: (series?: string, horizon?: number) =>
    fetchAPI(`/api/ml/timesfm/model-comparison?series=${series || "price"}&horizon=${horizon || 4}`),
  timesfmCustomForecast: (values: number[], horizon?: number, xreg?: number[][]) =>
    fetchAPI("/api/ml/timesfm/custom-forecast", {
      method: "POST",
      body: JSON.stringify({ values, horizon: horizon || 8, ...(xreg ? { xreg } : {}) }),
    }),

  // EU Traceability
  traceabilityDashboard: () => fetchAPI("/api/traceability/dashboard"),
  traceabilityCreateCertificate: (data: any) =>
    fetchAPI("/api/traceability/certificate", { method: "POST", body: JSON.stringify(data) }),
  traceabilityGetCertificate: (id: number) =>
    fetchAPI(`/api/traceability/certificate/${id}`),
  traceabilityListCertificates: (status?: string) =>
    fetchAPI(`/api/traceability/certificates${status ? `?status=${status}` : ""}`),
  traceabilityCreateLot: (data: any) =>
    fetchAPI("/api/traceability/lot", { method: "POST", body: JSON.stringify(data) }),
  traceabilityChainOfCustody: (lotId: string) =>
    fetchAPI(`/api/traceability/lot/${lotId}/chain`),
  traceabilityIUURisk: (data: any) =>
    fetchAPI("/api/traceability/iuu-risk", { method: "POST", body: JSON.stringify(data) }),
  traceabilityEUDRStatus: () => fetchAPI("/api/traceability/eudr-status"),

  // Offshore Farms (Session 28)
  offshoreFarms: () => fetchAPI("/api/farms/offshore"),
  offshoreRisk: (localityNo: number) => fetchAPI(`/api/farms/offshore/${localityNo}/risk`),
  offshoreLiceComparison: () => fetchAPI("/api/farms/offshore/lice-comparison"),

  // Fish Welfare Scoring (Session 32)
  welfareScore: (localityNo: number) => fetchAPI(`/api/welfare/score/${localityNo}`),
  welfarePaSummary: (pa: number) => fetchAPI(`/api/welfare/pa/${pa}`),

  // Decision Engine
  farmDecision: (localityNo: number) =>
    fetchAPI<DecisionCard>(`/api/decision/${localityNo}`),
  portfolioDecisions: (companyName: string) =>
    fetchAPI(`/api/decision/portfolio/${encodeURIComponent(companyName)}`),
  logTreatmentOutcome: (data: any) =>
    fetchAPI("/api/treatment/log-outcome", { method: "POST", body: JSON.stringify(data) }),
  treatmentEfficacyByMethod: () =>
    fetchAPI("/api/treatment/efficacy-by-method"),
  treatmentHistory: (localityNo: number) =>
    fetchAPI(`/api/treatment/history/${localityNo}`),

  // Farm Portfolio
  farmPortfolio: (localityNos: number[]) =>
    fetchAPI<FarmPortfolioResponse>(`/api/farms/portfolio?locality_nos=${localityNos.join(",")}`),

  // Biomass Status (Fiskeridirektoratet)
  biomassNational: () => fetchAPI<BiomassNational>("/api/farms/biomass/national"),
  // Derived supply model — estimated harvestable/outlook (see MarketBiomass type)
  marketBiomass: () => fetchAPI<MarketBiomass>("/api/market/biomass"),
  // Canonical plan catalog + Stripe prices (mock: true when Stripe is unset)
  billingCatalog: () => fetchAPI<BillingCatalog>("/api/billing/catalog"),
  // Published named index (AI-STI; AI-LPI v1.0 listed as withdrawn) with method version + provenance
  indices: () => fetchAPI<IndicesResponse>("/api/indices"),
  index: (code: string) => fetchAPI<IndexResult>(`/api/indices/${code.toLowerCase()}`),
  indexHistory: (code: string, limit = 52) =>
    fetchAPI<{ index: string; version: string; observations: Array<Record<string, unknown>> }>(
      `/api/indices/${code}/history?limit=${limit}`,
    ),
  bioPriceWeekly: () => fetchAPI<BioPriceWeekly>("/api/indices/bio-price-weekly"),
  // Published accuracy metrics backed by real artifacts (or an explicit none)
  accuracy: () => fetchAPI<AccuracySummary>("/api/accuracy"),
  accuracyMethod: () => fetchAPI<Record<string, unknown>>("/api/accuracy/method"),
  // Start a checkout for a canonical plan key (see /api/entitlements/plans)
  billingCheckout: (plan: string) =>
    fetchAPI<{ checkout_url: string; plan: string; demo_mode?: boolean }>(
      `/api/billing/create-checkout-session?plan=${encodeURIComponent(plan)}`,
      { method: "POST" },
    ),
  biomassByPA: (pa: number) => fetchAPI(`/api/farms/biomass/pa/${pa}`),
  biomassByLocality: (localityNo: number) => fetchAPI(`/api/farms/biomass/locality/${localityNo}`),

  // Traffic Light Simulator
  trafficLightCurrent: () => fetchAPI<TrafficLightCurrent>("/api/regulatory/traffic-light/current"),
  trafficLightSimulate: (pa?: number, color?: string) =>
    fetchAPI<TrafficLightSimulation>(`/api/regulatory/traffic-light/simulate?pa=${pa || 3}&color=${color || "red"}`),
  trafficLightAllScenarios: () =>
    fetchAPI("/api/regulatory/traffic-light/all-scenarios"),

  // Billing
  billingCreateCheckout: (tier: string) =>
    fetchAPI(`/api/billing/create-checkout-session?tier=${tier}`, { method: "POST" }),
  billingSubscriptionStatus: () =>
    fetchAPI<SubscriptionStatus>("/api/billing/subscription-status"),
  billingCancel: () =>
    fetchAPI("/api/billing/cancel-subscription", { method: "POST" }),
  billingInvoiceHistory: () =>
    fetchAPI("/api/billing/invoice-history"),

  // Event Impact Model (Investor/Trader)
  eventImpactISA: (pa?: number): Promise<EventImpactResult> =>
    fetchAPI<EventImpactResult>(`/api/investor/event-impact/isa?production_area=${pa || 3}`),
  eventImpactTrafficLight: (pa?: number, color?: string): Promise<EventImpactResult> =>
    fetchAPI<EventImpactResult>(`/api/investor/event-impact/traffic-light?pa=${pa || 3}&color=${color || "red"}`),
  eventImpactFeedShock: (pct?: number): Promise<EventImpactResult> =>
    fetchAPI<EventImpactResult>(`/api/investor/event-impact/feed-shock?fishmeal_change_pct=${pct || 15}`),

  // Saved Scenarios
  saveScenario: (data: {
    scenario_type: string;
    scenario_name: string;
    parameters: Record<string, unknown>;
    results: EventImpactResult;
    user_email?: string;
  }): Promise<{ id: number; status: string; name: string }> =>
    fetchAPI<{ id: number; status: string; name: string }>("/api/scenarios/save", { method: "POST", body: JSON.stringify(data), headers: { "Content-Type": "application/json" } }),
  listScenarios: (email?: string): Promise<SavedScenario[]> =>
    fetchAPI<SavedScenario[]>(`/api/scenarios/list?user_email=${email || "anonymous"}`),
  deleteScenario: (id: number): Promise<{ status: string; id: number }> =>
    fetchAPI<{ status: string; id: number }>(`/api/scenarios/${id}`, { method: "DELETE" }),

  // Compound Scenario Engine
  runCompoundScenario: (events: any[]) =>
    fetchAPI("/api/scenarios/compound", { method: "POST", body: JSON.stringify({ events }), headers: { "Content-Type": "application/json" } }),

  // Sentiment (Activated)
  sentimentPoll: () => fetchAPI("/api/sentiment/poll"),

  // YoY Analytics
  yoyComparison: (metric: string, pa?: number): Promise<YoYComparison> =>
    fetchAPI<YoYComparison>(`/api/analytics/yoy-comparison?metric=${metric}&production_area=${pa || 0}`),

  // Market Price Feed Hub
  spotPrice: (source?: string): Promise<MarketSpotPrice> =>
    fetchAPI<MarketSpotPrice>(`/api/market/spot-price${source ? `?source=${source}` : ""}`),
  forwardCurve: (months?: number): Promise<MarketForwardCurve> =>
    fetchAPI<MarketForwardCurve>(`/api/market/forward-curve?months=${months || 12}`),

  // Euronext Salmon Futures (ESF)
  futuresForwardCurve: (months?: number) =>
    fetchAPI<FuturesForwardCurve>(`/api/futures/forward-curve?months=${months || 12}`),
  futuresBasis: () => fetchAPI<FuturesBasis>("/api/futures/basis"),
  futuresSettlement: () => fetchAPI("/api/futures/settlement"),
  futuresTermStructure: () => fetchAPI("/api/futures/term-structure"),

  // EUMOFA European Market Data
  eumofaSalmonPrices: () => fetchAPI("/api/market/eumofa/salmon-prices"),
  eumofaTradeFlows: () => fetchAPI("/api/market/eumofa/trade-flows"),

  // Efficacy Marketplace
  efficacyBenchmarks: () => fetchAPI<EfficacyBenchmarks>("/api/efficacy/benchmarks"),
  efficacyByRegion: () => fetchAPI("/api/efficacy/by-region"),
  efficacyBySeason: () => fetchAPI("/api/efficacy/by-season"),
  efficacyExplore: (params?: Record<string, string>) =>
    fetchAPI(`/api/efficacy/explore?${new URLSearchParams(params || {})}`),
  learnedProfiles: () => fetchAPI("/api/efficacy/learned-profiles"),

  // Locality Search
  searchLocalities: (q?: string) => fetchAPI(`/api/localities/search?q=${encodeURIComponent(q || "")}`),

  // Threshold Notifications
  activeAlerts: () => fetchAPI<AlertsResponse>("/api/notifications/alerts"),
  alertThresholds: () => fetchAPI("/api/notifications/thresholds"),
  updateThresholds: (thresholds: Record<string, number>) =>
    fetchAPI("/api/notifications/thresholds", { method: "POST", body: JSON.stringify(thresholds), headers: { "Content-Type": "application/json" } }),

  // Notification Preferences
  getNotificationPreferences: (email: string) =>
    fetchAPI(`/api/notifications/preferences/${encodeURIComponent(email)}`),
  saveNotificationPreferences: (data: any) =>
    fetchAPI("/api/notifications/preferences", { method: "POST", body: JSON.stringify(data), headers: { "Content-Type": "application/json" } }),

  // Notification History (Notification Center)
  notificationHistory: (params?: { severity?: string; category?: string; limit?: number }) =>
    fetchAPI(`/api/notifications/history?${new URLSearchParams({
      ...(params?.severity ? { severity: params.severity } : {}),
      ...(params?.category ? { category: params.category } : {}),
      ...(params?.limit ? { limit: String(params.limit) } : {}),
    }).toString()}`),
  markNotificationsRead: (ids: string[]) =>
    fetchAPI("/api/notifications/mark-read", { method: "POST", body: JSON.stringify({ notification_ids: ids }) }),
  markAllNotificationsRead: () =>
    fetchAPI("/api/notifications/mark-all-read", { method: "POST" }),

  // Custom Alert Rules
  alertRulesList: (userId?: number) =>
    fetchAPI(`/api/notifications/alerts/rules${userId ? `?user_id=${userId}` : ""}`),
  alertRulesCreate: (rule: {
    name: string; metric: string; operator: string; threshold: number;
    production_area?: number | null; is_active?: boolean; notify_webhook?: boolean;
  }) =>
    fetchAPI("/api/notifications/alerts/rules", { method: "POST", body: JSON.stringify(rule) }),
  alertRulesUpdate: (id: number, updates: Record<string, any>) =>
    fetchAPI(`/api/notifications/alerts/rules/${id}`, { method: "PUT", body: JSON.stringify(updates) }),
  alertRulesDelete: (id: number) =>
    fetchAPI(`/api/notifications/alerts/rules/${id}`, { method: "DELETE" }),
  alertRulesEvaluate: () =>
    fetchAPI("/api/notifications/alerts/rules/evaluate"),

  // Admin / Ops Dashboard
  adminStatus: () => fetchAPI("/api/admin/status"),
  adminDataQuality: () => fetchAPI("/api/admin/data-quality"),
  adminExportSummary: () => fetchAPI("/api/admin/export-summary"),
  adminExportDataset: (dataset: string, format: string = "json", fromDate?: string, toDate?: string) => {
    const params = new URLSearchParams({ format });
    if (fromDate) params.set("from_date", fromDate);
    if (toDate) params.set("to_date", toDate);
    return `${API_BASE}/api/admin/export/${dataset}?${params.toString()}`;
  },
  adminAuditLog: (params?: { action?: string; user_id?: number; from_date?: string; to_date?: string; limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    if (params?.action) qs.set("action", params.action);
    if (params?.user_id !== undefined) qs.set("user_id", String(params.user_id));
    if (params?.from_date) qs.set("from_date", params.from_date);
    if (params?.to_date) qs.set("to_date", params.to_date);
    if (params?.limit) qs.set("limit", String(params.limit));
    if (params?.offset) qs.set("offset", String(params.offset));
    return fetchAPI(`/api/admin/audit-log?${qs.toString()}`);
  },

  // Webhooks
  webhooksList: () => fetchAPI("/api/webhooks"),
  webhooksCreate: (data: { name: string; url: string; webhook_type: string; events: string[] }) =>
    fetchAPI("/api/webhooks", { method: "POST", body: JSON.stringify(data) }),
  webhooksDelete: (id: number) =>
    fetchAPI(`/api/webhooks/${id}`, { method: "DELETE" }),
  webhooksTest: (id: number) =>
    fetchAPI(`/api/webhooks/${id}/test`, { method: "POST" }),
  webhooksEvents: () => fetchAPI("/api/webhooks/events"),

  // ASC Compliance
  ascReadiness: (localityNo: number) => fetchAPI<ASCReadiness>(`/api/compliance/asc/readiness/${localityNo}`),
  ascReadinessSummary: () => fetchAPI("/api/compliance/asc/readiness-summary"),
  ascChecklist: () => fetchAPI("/api/compliance/asc/checklist"),

  // Regulatory Reporting Automation
  complianceDeadlines: (localityNo?: number) =>
    fetchAPI(`/api/compliance/deadlines${localityNo ? `?locality_no=${localityNo}` : ""}`),
  weeklyLiceReport: (localityNo: number, week: number, year: number) =>
    fetchAPI(`/api/compliance/report/weekly-lice/${localityNo}?week=${week}&year=${year}`),
  monthlyTreatmentReport: (localityNo: number, year: number, month: number) =>
    fetchAPI(`/api/compliance/report/monthly-treatment/${localityNo}?year=${year}&month=${month}`),
  complianceScore: (localityNo: number) =>
    fetchAPI(`/api/compliance/score/${localityNo}`),

  // CSRD Export
  csrdExport: (year?: number) => fetchAPI(`/api/admin/export/csrd?year=${year || 2025}`),

  // API Key Management
  apiKeysList: () => fetchAPI("/api/keys"),
  apiKeysCreate: (data: { name?: string; tier?: string; expires_days?: number; rate_limit?: number }) =>
    fetchAPI("/api/keys", { method: "POST", body: JSON.stringify(data) }),
  apiKeysRevoke: (id: number) =>
    fetchAPI(`/api/keys/${id}`, { method: "DELETE" }),
  apiKeysRotate: (id: number) =>
    fetchAPI(`/api/keys/${id}/rotate`, { method: "POST" }),

  // Fishtalk 5 Integration (AKVA Group)
  fishtalkStatus: () => fetchAPI("/api/integrations/fishtalk/status"),
  fishtalkFarmData: (siteId: string) => fetchAPI(`/api/integrations/fishtalk/farm/${encodeURIComponent(siteId)}`),
  fishtalkLice: (siteId: string) => fetchAPI(`/api/integrations/fishtalk/lice/${encodeURIComponent(siteId)}`),
  fishtalkTreatments: (siteId: string) => fetchAPI(`/api/integrations/fishtalk/treatments/${encodeURIComponent(siteId)}`),

  // Lice Emission Quota Tracking
  liceEmission: (localityNo: number) => fetchAPI(`/api/analytics/lice-emission/${localityNo}`),
  liceQuotaPA: (pa: number) => fetchAPI(`/api/analytics/lice-quota/pa/${pa}`),
  liceQuotaNational: () => fetchAPI("/api/analytics/lice-quota/national"),

  // MOIRAI-2 Foundation Model (Salesforce, 30M params — fastest)
  moiraiPriceForecast: (horizon: number = 4) => fetchAPI<ForecastResponse>(`/api/ml/moirai/price-forecast?horizon=${horizon}`),
  moiraiLiceForecast: (localityNo: number, horizon: number = 8) => fetchAPI(`/api/ml/moirai/lice-forecast/${localityNo}?horizon=${horizon}`),
  moiraiSupplyForecast: (horizon: number = 6) => fetchAPI(`/api/ml/moirai/supply-forecast?horizon=${horizon}`),
  moiraiModelComparison: (series: string = "price", horizon: number = 4) => fetchAPI(`/api/ml/moirai/model-comparison?series=${series}&horizon=${horizon}`),
  moiraiCustomForecast: (values: number[], horizon?: number) =>
    fetchAPI("/api/ml/moirai/custom-forecast", {
      method: "POST",
      body: JSON.stringify({ values, horizon: horizon || 8 }),
    }),

  // Foundation Model Ensemble (combines TimesFM + Chronos + MOIRAI)
  ensemblePriceForecast: (horizon: number = 4) => fetchAPI<EnsembleForecast>(`/api/ml/ensemble/price-forecast?horizon=${horizon}`),

  // Feed Supply Chain
  feedSupplyChainSummary: (): Promise<FeedSupplyChainSummary> =>
    fetchAPI<FeedSupplyChainSummary>("/api/feed-supply-chain/summary"),
  feedSupplyChainEudrRisk: () => fetchAPI("/api/feed-supply-chain/eudr-risk"),
  feedSupplyChainScenarios: () => fetchAPI("/api/feed-supply-chain/scenarios"),
  feedSupplyChainLive: () => fetchAPI("/api/feed-supply-chain/live"),
};
