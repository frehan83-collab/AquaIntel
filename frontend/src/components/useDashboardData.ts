"use client";
import { useEffect, useState, useCallback, useRef } from "react";
import { api } from "@/lib/api";
import { useToast } from "@/components/Toast";
import { useApiError } from "@/lib/useApiError";
import { formatNumber } from "@/lib/i18n";
import type { Locale } from "@/lib/i18n";
import type {
  LiceSummary, AnomalyScores, RegimeAlert, AlertItem, AlertsResponse,
  SSBPriceHistory, MacroSnapshot, GlobalSupply, DiseaseByCompany,
  AISHarvestIntel, PairsSignal, Signal,
} from "@/types/api";

/* eslint-disable @typescript-eslint/no-explicit-any */

/** Extended LeaderEntry with sparkline data returned by /api/leaders/top100 */
export interface DashboardLeader {
  company_name: string;
  ticker?: string;
  lice_trend?: string;
  name: string;
  avg_lice: number;
  lice_sparkline: number[];
  lice_prediction?: number[];
  n_lice_records?: number;
  [key: string]: unknown;
}

/** Macro snapshot as returned by the dashboard endpoint */
export interface DashboardMacro extends MacroSnapshot {
  indices?: Record<string, { value: number; label?: string }>;
  benchmarks?: Record<string, number>;
  yoy_changes?: Record<string, number>;
}

/** Supply data as used by the dashboard */
export interface DashboardSupply extends GlobalSupply {
  balance?: string;
  supply_deficit_pct?: number;
}

/** AIS data as used by the dashboard */
export interface DashboardAIS extends AISHarvestIntel {
  signals?: Array<{ vessel: string; activity: string; location: string; timestamp: string }>;
}

/** Production summary from Fiskeridirektoratet */
export interface ProductionSummary {
  year?: number;
  latest_year?: number;
  total_harvest_tonnes?: number;
  total_tonnes?: number;
  salmon_tonnes?: number;
  total_feed_tonnes?: number;
  total_smolt_released?: number;
  avg_mortality_pct?: number;
  yoy_change_pct?: number;
  [key: string]: unknown;
}

export interface DashboardData {
  summary: LiceSummary | null;
  fetchedAt: Date | null;
  signals: Signal[];
  leaders: DashboardLeader[];
  ssbSpot: number;
  supplyData: Array<{ week: string; volume: number }>;
  regimeAlerts: RegimeAlert[];
  pairsSignals: PairsSignal[];
  aisData: DashboardAIS | null;
  macro: DashboardMacro | null;
  supply: DashboardSupply | null;
  diseaseCount: number;
  anomaly: AnomalyScores | null;
  production: ProductionSummary | null;
  counties: Array<{ county: string; harvest_tonnes: number }>;
  heroAlert: AlertItem | null;
  alertsLoaded: boolean;
  metricsExpanded: boolean;
  setMetricsExpanded: (v: boolean) => void;
}

export function useDashboardData(locale: Locale): DashboardData {
  const { addToast } = useToast();
  const handleError = useApiError();

  const [summary, setSummary] = useState<LiceSummary | null>(null);
  const [fetchedAt, setFetchedAt] = useState<Date | null>(null);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [leaders, setLeadersRaw] = useState<DashboardLeader[]>([]);
  const setLeaders = (v: unknown) => {
    try {
      const raw = v as DashboardLeader[] | { data?: DashboardLeader[]; companies?: DashboardLeader[] };
      const arr = Array.isArray(raw) ? raw : Array.isArray(raw?.data) ? raw.data : Array.isArray(raw?.companies) ? raw.companies : [];
      setLeadersRaw(arr);
    } catch { setLeadersRaw([]); }
  };
  const [ssbSpot, setSsbSpot] = useState<number>(0);
  const [supplyData, setSupplyData] = useState<Array<{ week: string; volume: number }>>([]);
  const [regimeAlerts, setRegimeAlerts] = useState<RegimeAlert[]>([]);
  const [pairsSignals, setPairsSignals] = useState<PairsSignal[]>([]);
  const [aisData, setAisData] = useState<DashboardAIS | null>(null);
  const [macro, setMacro] = useState<DashboardMacro | null>(null);
  const [supply, setSupply] = useState<DashboardSupply | null>(null);
  const [diseaseCount, setDiseaseCount] = useState<number>(0);
  const [anomaly, setAnomaly] = useState<AnomalyScores | null>(null);
  const [production, setProduction] = useState<ProductionSummary | null>(null);
  const [counties, setCounties] = useState<Array<{ county: string; harvest_tonnes: number }>>([]);
  const [heroAlert, setHeroAlert] = useState<AlertItem | null>(null);
  const [alertsLoaded, setAlertsLoaded] = useState(false);
  const [metricsExpanded, setMetricsExpanded] = useState(true);

  const isFirstLoad = useRef(true);

  const loadData = useCallback(() => {
    api.liceSummary().then(setSummary).catch(handleError("lice_summary", { critical: true }));
    api.signals().then((d: any) => setSignals(d)).catch(handleError("signals"));
    api.leadersTop30().then(setLeaders).catch(handleError("leaders_top30"));
    api.ssbPriceHistory(8).then((d: SSBPriceHistory) => {
      setSsbSpot(d.spot_nok || 0);
      if (d.history?.length) {
        setSupplyData(d.history.slice(-6).map((h) => ({
          week: h.label?.replace(/^\d{4}/, "") || String(h.week),
          volume: Math.round((h.volume_tonnes || 0) / 1000),
        })));
      }
    }).catch(handleError("ssb_price", { critical: true }));
    api.regimeAlerts().then((d: any) => setRegimeAlerts(d)).catch(handleError("regime_alerts"));
    api.pairsSignals(7).then((d: any) => setPairsSignals(d)).catch(handleError("pairs_signals"));
    api.aisHarvestSignals(72).then((d: any) => setAisData(d)).catch(handleError("ais_data"));
    api.macroSnapshot().then((d: any) => setMacro(d)).catch(handleError("macro_snapshot"));
    api.globalSupply().then((d: any) => setSupply(d)).catch(handleError("global_supply"));
    api.diseaseByCompany().then((d: DiseaseByCompany) => {
      const total = Object.values(d || {}).reduce((sum: number, c) => sum + (c?.total || 0), 0);
      setDiseaseCount(total);
    }).catch(handleError("disease_count"));
    api.anomalyScores().then((d: AnomalyScores) => {
      setAnomaly(d);
      if (isFirstLoad.current && d?.composite_score >= 60) {
        addToast({
          type: "alert",
          title: "Elevated Risk Detected",
          message: `Anomaly score: ${formatNumber(d.composite_score, locale, 0)} — ${d.risk_level || "HIGH"}`,
          duration: 8000,
        });
      }
    }).catch(handleError("anomaly_scores", { critical: true }));
    api.activeAlerts().then((d: AlertsResponse | AlertItem[]) => {
      const alerts: AlertItem[] = Array.isArray(d) ? d : d?.alerts || [];
      if (alerts.length > 0) {
        const sevOrder: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };
        const sorted = [...alerts].sort((a: AlertItem, b: AlertItem) =>
          (sevOrder[a.severity] ?? 5) - (sevOrder[b.severity] ?? 5)
        );
        setHeroAlert(sorted[0]);
      }
      setAlertsLoaded(true);
    }).catch((err: unknown) => { setAlertsLoaded(true); handleError("hero_alerts")(err); });
    api.productionSummary().then((d: any) => setProduction(d)).catch(handleError("production_stats"));
    api.productionByCounty().then((d: any) => {
      const arr = Array.isArray(d) ? d : d?.data || d?.counties || [];
      setCounties(arr.sort((a: any, b: any) => (b.harvest_tonnes || 0) - (a.harvest_tonnes || 0)).slice(0, 5));
    }).catch(handleError("counties"));
    setFetchedAt(new Date());
    isFirstLoad.current = false;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 60_000);
    return () => clearInterval(interval);
  }, [loadData]);

  return {
    summary, fetchedAt, signals, leaders, ssbSpot, supplyData,
    regimeAlerts, pairsSignals, aisData, macro, supply, diseaseCount,
    anomaly, production, counties, heroAlert, alertsLoaded,
    metricsExpanded, setMetricsExpanded,
  };
}
