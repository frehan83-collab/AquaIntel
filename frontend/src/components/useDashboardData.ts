"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useToast } from "@/components/Toast";
import { useApiError } from "@/lib/useApiError";
import { formatNumber } from "@/lib/i18n";
import type { Locale } from "@/lib/i18n";
import type {
  LiceSummary, AnomalyScores, RegimeAlert, AlertItem, AlertsResponse,
  SSBPriceHistory, MacroSnapshot, GlobalSupply, DiseaseByCompany,
  AISHarvestSignalRow, PairsSignal, Signal,
} from "@/types/api";

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

export type DashboardMacro = MacroSnapshot;

export interface DashboardAIS {
  signals?: AISHarvestSignalRow[];
  total_vessels?: number;
  summary?: Record<string, number>;
}

/** /api/global-supply is now fully typed; the dashboard layer used to
 *  re-declare balance/supply_deficit_pct as optional to patch a fiction. */
export type DashboardSupply = GlobalSupply;

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
  aisData: DashboardAIS | AISHarvestSignalRow[] | null;
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

/**
 * One dashboard resource as a TanStack Query.
 *
 * Shared defaults come from QueryProvider; every resource polls at the same
 * 60s cadence the hook used before, but now with request dedupe, stale-while-
 * revalidate across navigations, and retry(1). Errors route through the same
 * useApiError policy (critical contexts still toast).
 */
function useDashboardQuery<T>(
  queryKey: readonly unknown[],
  queryFn: () => Promise<T>,
  errorContext: string,
  opts?: { critical?: boolean }
) {
  const handleError = useApiError();
  const query = useQuery<T>({ queryKey, queryFn, refetchInterval: 60_000 });
  const lastError = useRef<unknown>(null);
  useEffect(() => {
    if (query.error && query.error !== lastError.current) {
      lastError.current = query.error;
      handleError(errorContext, { critical: opts?.critical })(query.error);
    }
  }, [query.error, errorContext, handleError, opts?.critical]);
  return query;
}

export function useDashboardData(locale: Locale): DashboardData {
  const { addToast } = useToast();
  const [metricsExpanded, setMetricsExpanded] = useState(true);
  const isFirstLoad = useRef(true);

  const summaryQ = useDashboardQuery<LiceSummary>(
    ["lice-summary"], () => api.liceSummary() as Promise<LiceSummary>, "lice_summary", { critical: true });
  const signalsQ = useDashboardQuery<Signal[]>(
    ["signals"], () => api.signals() as Promise<Signal[]>, "signals");
  const leadersQ = useDashboardQuery<unknown>(
    ["leaders-top30"], () => api.leadersTop30() as Promise<unknown>, "leaders_top30");
  const ssbQ = useDashboardQuery<SSBPriceHistory>(
    ["ssb-price-history", 8], () => api.ssbPriceHistory(8) as Promise<SSBPriceHistory>, "ssb_price", { critical: true });
  const regimeQ = useDashboardQuery<RegimeAlert[]>(
    ["regime-alerts"], () => api.regimeAlerts() as unknown as Promise<RegimeAlert[]>, "regime_alerts");
  const pairsQ = useDashboardQuery<PairsSignal[]>(
    ["pairs-signals", 7], () => api.pairsSignals(7) as unknown as Promise<PairsSignal[]>, "pairs_signals");
  const aisQ = useDashboardQuery<DashboardAIS | AISHarvestSignalRow[]>(
    ["ais-harvest", 72], () => api.aisHarvestSignals(72), "ais_data");
  const macroQ = useDashboardQuery<DashboardMacro>(
    ["macro-snapshot"], () => api.macroSnapshot() as unknown as Promise<DashboardMacro>, "macro_snapshot");
  const supplyQ = useDashboardQuery<DashboardSupply>(
    ["global-supply"], () => api.globalSupply() as unknown as Promise<DashboardSupply>, "global_supply");
  const diseaseQ = useDashboardQuery<DiseaseByCompany>(
    ["disease-by-company"], () => api.diseaseByCompany() as Promise<DiseaseByCompany>, "disease_count");
  const anomalyQ = useDashboardQuery<AnomalyScores>(
    ["anomaly-scores"], () => api.anomalyScores() as Promise<AnomalyScores>, "anomaly_scores", { critical: true });
  const alertsQ = useDashboardQuery<AlertsResponse | AlertItem[]>(
    ["active-alerts"], () => api.activeAlerts() as Promise<AlertsResponse | AlertItem[]>, "hero_alerts");
  const productionQ = useDashboardQuery<ProductionSummary>(
    ["production-summary"], () => api.productionSummary() as unknown as Promise<ProductionSummary>, "production_stats");
  const countiesQ = useDashboardQuery<unknown>(
    ["production-by-county"], () => api.productionByCounty() as Promise<unknown>, "counties");

  // ── Derived values (identical semantics to the pre-Query implementation) ──
  const leaders = useMemo<DashboardLeader[]>(() => {
    const raw = leadersQ.data as
      | DashboardLeader[]
      | { data?: DashboardLeader[]; companies?: DashboardLeader[] }
      | undefined;
    if (Array.isArray(raw)) return raw;
    if (Array.isArray(raw?.data)) return raw.data;
    if (Array.isArray(raw?.companies)) return raw.companies;
    return [];
  }, [leadersQ.data]);

  const ssbSpot = ssbQ.data?.spot_nok || 0;

  const supplyData = useMemo(() => {
    const history = ssbQ.data?.history;
    if (!history?.length) return [];
    return history.slice(-6).map((h) => ({
      week: h.label?.replace(/^\d{4}/, "") || String(h.week),
      volume: Math.round((h.volume_tonnes || 0) / 1000),
    }));
  }, [ssbQ.data]);

  const diseaseCount = useMemo(
    () => Object.values(diseaseQ.data?.companies ?? {}).reduce((sum, c) => sum + (c?.total || 0), 0),
    [diseaseQ.data]
  );

  const heroAlert = useMemo<AlertItem | null>(() => {
    const d = alertsQ.data;
    const alerts: AlertItem[] = Array.isArray(d) ? d : d?.alerts || [];
    if (!alerts.length) return null;
    const sevOrder: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };
    const sorted = [...alerts].sort(
      (a, b) => (sevOrder[a.severity] ?? 5) - (sevOrder[b.severity] ?? 5)
    );
    return sorted[0];
  }, [alertsQ.data]);

  const counties = useMemo<Array<{ county: string; harvest_tonnes: number }>>(() => {
    type CountyRow = { county: string; harvest_tonnes: number };
    const d = countiesQ.data as
      | CountyRow[]
      | { data?: CountyRow[]; counties?: CountyRow[] }
      | undefined;
    const arr = Array.isArray(d) ? d : d?.data || d?.counties || [];
    return [...arr]
      .sort((a, b) => (b.harvest_tonnes || 0) - (a.harvest_tonnes || 0))
      .slice(0, 5);
  }, [countiesQ.data]);

  const fetchedAt = summaryQ.dataUpdatedAt ? new Date(summaryQ.dataUpdatedAt) : null;

  // One-time anomaly toast (same policy as before: first load, score >= 60)
  useEffect(() => {
    const d = anomalyQ.data;
    if (isFirstLoad.current && d && d.composite_score >= 60) {
      addToast({
        type: "alert",
        title: "Elevated Risk Detected",
        message: `Anomaly score: ${formatNumber(d.composite_score, locale, 0)} — ${d.risk_level || "HIGH"}`,
        duration: 8000,
      });
    }
    if (anomalyQ.isFetched) isFirstLoad.current = false;
  }, [anomalyQ.data, anomalyQ.isFetched, addToast, locale]);

  return {
    summary: (summaryQ.data as LiceSummary) ?? null,
    fetchedAt,
    signals: (signalsQ.data as Signal[]) ?? [],
    leaders,
    ssbSpot,
    supplyData,
    regimeAlerts: (regimeQ.data as RegimeAlert[]) ?? [],
    pairsSignals: (pairsQ.data as PairsSignal[]) ?? [],
    aisData: (aisQ.data as DashboardAIS | AISHarvestSignalRow[]) ?? null,
    macro: (macroQ.data as DashboardMacro) ?? null,
    supply: (supplyQ.data as DashboardSupply) ?? null,
    diseaseCount,
    anomaly: (anomalyQ.data as AnomalyScores) ?? null,
    production: (productionQ.data as ProductionSummary) ?? null,
    counties,
    heroAlert,
    alertsLoaded: alertsQ.isFetched,
    metricsExpanded,
    setMetricsExpanded,
  };
}
