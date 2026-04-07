"use client";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import {
  Activity, TrendingDown, TrendingUp, AlertTriangle, Fish,
  BarChart3, DollarSign, ArrowRight, Ship, GitBranch, Network,
  BarChart2, Zap, Globe2, Shield, Wheat, CheckCircle2, ChevronDown, ChevronUp,
  Settings2,
} from "lucide-react";
import KPICard from "@/components/KPICard";
import GlassCard from "@/components/GlassCard";
import { OceanAreaChart, OceanBarChart, ChartContainer } from "@/components/charts";
import { api } from "@/lib/api";
import { useTranslation, formatNumber, formatCurrency } from "@/lib/i18n";
import { useToast } from "@/components/Toast";
import { useApiError } from "@/lib/useApiError";
import ErrorBoundary from "@/components/ErrorBoundary";
import FreshnessIndicator from "@/components/FreshnessIndicator";
import { useDashboardLayout } from "@/lib/useDashboardLayout";
import DashboardCustomizePanel from "@/components/DashboardCustomizePanel";
import type { LiceSummary, LeaderEntry, AnomalyScores, RegimeAlert, AlertItem } from "@/types/api";

/* eslint-disable @typescript-eslint/no-explicit-any */

export default function DashboardPage() {
  const { addToast } = useToast();
  const { t, locale } = useTranslation();
  const handleError = useApiError();
  const [summary, setSummary] = useState<LiceSummary | null>(null);
  const [fetchedAt, setFetchedAt] = useState<Date | null>(null);
  const [signals, setSignals] = useState<any[]>([]);
  const [leaders, setLeadersRaw] = useState<any[]>([]);
  const setLeaders = (v: any) => {
    try {
      const arr = Array.isArray(v) ? v : Array.isArray(v?.data) ? v.data : Array.isArray(v?.companies) ? v.companies : [];
      setLeadersRaw(arr);
    } catch { setLeadersRaw([]); }
  };
  const [ssbSpot, setSsbSpot] = useState<number>(0);
  const [supplyData, setSupplyData] = useState<Array<{ week: string; volume: number }>>([]);
  // Intelligence modules
  const [regimeAlerts, setRegimeAlerts] = useState<RegimeAlert[]>([]);
  const [pairsSignals, setPairsSignals] = useState<any[]>([]);
  const [aisData, setAisData] = useState<any>(null);
  // Macro context
  const [macro, setMacro] = useState<any>(null);
  const [supply, setSupply] = useState<any>(null);
  const [diseaseCount, setDiseaseCount] = useState<number>(0);
  // Anomaly Detection
  const [anomaly, setAnomaly] = useState<AnomalyScores | null>(null);
  // Production statistics
  const [production, setProduction] = useState<any>(null);
  const [counties, setCounties] = useState<Array<{ county: string; harvest_tonnes: number }>>([]);
  // Hero Alert Zone
  const [heroAlert, setHeroAlert] = useState<AlertItem | null>(null);
  const [alertsLoaded, setAlertsLoaded] = useState(false);
  const [metricsExpanded, setMetricsExpanded] = useState(true);
  // Dashboard customization
  const { widgets, moveWidget, toggleWidget, resetLayout } = useDashboardLayout();
  const [customizeOpen, setCustomizeOpen] = useState(false);
  const isVisible = (id: string) => widgets.find((w) => w.id === id)?.visible !== false;
  const widgetOrder = (id: string) => {
    const idx = widgets.findIndex((w) => w.id === id);
    return idx >= 0 ? idx : 99;
  };

  useEffect(() => {
    api.liceSummary().then(setSummary).catch(handleError("lice_summary", { critical: true }));
    api.signals().then(setSignals).catch(handleError("signals"));
    api.leadersTop30().then(setLeaders).catch(handleError("leaders_top30"));
    api.ssbPriceHistory(8).then((d: any) => {
      setSsbSpot(d.spot_nok || 0);
      if (d.history?.length) {
        setSupplyData(d.history.slice(-6).map((h: any) => ({
          week: h.label?.replace(/^\d{4}/, "") || h.week,
          volume: Math.round(h.volume_tonnes / 1000),
        })));
      }
    }).catch(handleError("ssb_price", { critical: true }));
    // Intelligence modules
    api.regimeAlerts().then(setRegimeAlerts).catch(handleError("regime_alerts"));
    api.pairsSignals(7).then(setPairsSignals).catch(handleError("pairs_signals"));
    api.aisHarvestSignals(72).then((d: any) => setAisData(d)).catch(handleError("ais_data"));
    // Macro context (Change 1: Dashboard wire-up)
    api.macroSnapshot().then(setMacro).catch(handleError("macro_snapshot"));
    api.globalSupply().then(setSupply).catch(handleError("global_supply"));
    api.diseaseByCompany().then((d: any) => {
      const total = Object.values(d || {}).reduce((sum: number, c: any) => sum + (c?.total || 0), 0);
      setDiseaseCount(total as number);
    }).catch(handleError("disease_count"));
    api.anomalyScores().then((d: any) => {
      setAnomaly(d);
      if (d?.composite_score >= 60) {
        addToast({
          type: "alert",
          title: "Elevated Risk Detected",
          message: `Anomaly score: ${formatNumber(d.composite_score, locale, 0)} — ${d.risk_level || "HIGH"}`,
          duration: 8000,
        });
      }
    }).catch(handleError("anomaly_scores", { critical: true }));
    // Hero Alert Zone — fetch highest-severity alert
    api.activeAlerts().then((d: any) => {
      const alerts = Array.isArray(d) ? d : d?.alerts || [];
      if (alerts.length > 0) {
        // Sort by severity: critical > high > medium > low
        const sevOrder: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };
        const sorted = [...alerts].sort((a: any, b: any) =>
          (sevOrder[a.severity] ?? 5) - (sevOrder[b.severity] ?? 5)
        );
        setHeroAlert(sorted[0]);
      }
      setAlertsLoaded(true);
    }).catch((err: unknown) => { setAlertsLoaded(true); handleError("hero_alerts")(err); });

    api.productionSummary().then(setProduction).catch(handleError("production_stats"));
    api.productionByCounty().then((d: any) => {
      const arr = Array.isArray(d) ? d : d?.data || d?.counties || [];
      setCounties(arr.sort((a: any, b: any) => (b.harvest_tonnes || 0) - (a.harvest_tonnes || 0)).slice(0, 5));
    }).catch(handleError("counties"));
    setFetchedAt(new Date());
  }, []);

  // Build Top 10 area chart from real leader sparklines
  const safeLeaders = Array.isArray(leaders) ? leaders : [];
  let top10: any[] = [];
  if (safeLeaders.length > 0) {
    top10 = safeLeaders.filter((c: any) => c?.lice_sparkline?.length >= 6 && c?.avg_lice > 0).slice(0, 10);
  }

  const COLORS = ["#00D4C8", "#F59E0B", "#8B5CF6", "#EC4899", "#10B981", "#6366F1", "#F43F5E", "#14B8A6", "#A855F7", "#EF4444"];

  const liceChartData = top10.length >= 2
    ? top10[0].lice_sparkline.map((_: number, i: number) => {
        const row: any = { week: `W${i + 1}` };
        top10.forEach((c: any) => {
          const label = c.name.replace(/ AS$| ASA$/i, "").replace(/OPPDRETT|FARMING|SEAFOOD|SJØFARM|FISKEOPPDRETT/gi, "").trim().slice(0, 14);
          row[label] = c.lice_sparkline[i] || 0;
        });
        return row;
      })
    : [];

  const companiesWithData = safeLeaders.filter((c: any) => c.n_lice_records > 0).length;

  return (
    <ErrorBoundary fallbackTitle="Dashboard error">
    <div className="flex flex-col gap-6">
      {/* Header — always first, not reorderable */}
      <motion.div style={{ order: -1 }}
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between"
      >
        <div>
          <h1 className="text-2xl font-display text-[var(--text-primary)] tracking-tight">
            {t("dashboard.title")}
          </h1>
          <div className="flex items-center gap-2 mt-1">
            <p className="text-[13px] text-[var(--text-secondary)]">
              Norwegian salmon aquaculture intelligence &mdash; {companiesWithData || "123"} companies tracked
            </p>
            <FreshnessIndicator lastUpdated={fetchedAt} />
          </div>
        </div>
        <div className="flex items-center gap-3">
          {/* Customize Button */}
          <button
            onClick={() => setCustomizeOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white/[0.03] backdrop-blur border border-white/[0.06] hover:bg-white/[0.06] hover:border-white/[0.1] transition-colors"
            aria-label="Customize dashboard layout"
          >
            <Settings2 className="w-3.5 h-3.5 text-[var(--text-secondary)]" />
            <span className="text-xs text-[var(--text-secondary)] hidden sm:inline">{t("dashboard.customize")}</span>
          </button>
          {/* Anomaly Risk Badge */}
          {anomaly && (
            <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full border ${
              anomaly.risk_level === "CRITICAL" ? "bg-rose-500/[0.08] border-rose-500/[0.15]" :
              anomaly.risk_level === "HIGH" ? "bg-orange-500/[0.08] border-orange-500/[0.15]" :
              anomaly.risk_level === "ELEVATED" ? "bg-amber-500/[0.08] border-amber-500/[0.15]" :
              "bg-emerald-500/[0.06] border-emerald-500/[0.1]"
            }`}>
              <Shield className={`w-3.5 h-3.5 ${
                anomaly.risk_level === "CRITICAL" ? "text-rose-400" :
                anomaly.risk_level === "HIGH" ? "text-orange-400" :
                anomaly.risk_level === "ELEVATED" ? "text-amber-400" :
                "text-emerald-400"
              }`} />
              <span className={`text-xs font-semibold ${
                anomaly.risk_level === "CRITICAL" ? "text-rose-400" :
                anomaly.risk_level === "HIGH" ? "text-orange-400" :
                anomaly.risk_level === "ELEVATED" ? "text-amber-400" :
                "text-emerald-400"
              }`}>
                Risk: {formatNumber(anomaly.composite_score, locale, 0)}/100
              </span>
            </div>
          )}
          {ssbSpot > 0 && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-amber-500/[0.06] border border-amber-500/[0.1]">
              <DollarSign className="w-3.5 h-3.5 text-amber-400" />
              <span className="text-xs text-amber-400 font-semibold">{formatCurrency(ssbSpot, locale)} /kg</span>
            </div>
          )}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/[0.03] backdrop-blur border border-white/[0.06]">
            <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.5)]" />
            <span className="text-xs text-emerald-400 font-medium">
              {summary ? `W${summary.week} ${summary.year}` : "Connecting..."}
            </span>
          </div>
        </div>
      </motion.div>

      {/* Hero Alert Zone */}
      {isVisible("hero-alert") && alertsLoaded && (<div style={{ order: widgetOrder("hero-alert") }}>
        <motion.div
          initial={{ opacity: 0, y: -6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
        >
          {heroAlert && (heroAlert.severity === "critical" || heroAlert.severity === "high") ? (
            <div className={`rounded-2xl p-5 mb-1 border ${
              heroAlert.severity === "critical"
                ? "bg-rose-500/[0.08] border-rose-500/20"
                : "bg-amber-500/[0.08] border-amber-500/20"
            }`}>
              <div className="flex items-center gap-4">
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${
                  heroAlert.severity === "critical"
                    ? "bg-rose-500/15"
                    : "bg-amber-500/15"
                }`}>
                  <AlertTriangle className={`w-6 h-6 ${
                    heroAlert.severity === "critical" ? "text-rose-400" : "text-amber-400"
                  }`} />
                </div>
                <div className="min-w-0 flex-1">
                  <h2 className={`text-base font-bold ${
                    heroAlert.severity === "critical" ? "text-rose-300" : "text-amber-300"
                  }`}>
                    {heroAlert.title || heroAlert.message?.slice(0, 60) || "Alert Triggered"}
                  </h2>
                  <p className={`text-sm mt-0.5 ${
                    heroAlert.severity === "critical" ? "text-rose-200/70" : "text-amber-200/70"
                  }`}>
                    {heroAlert.message || heroAlert.description || "A threshold breach has been detected that may require attention."}
                  </p>
                </div>
                <Link
                  href="/farmer-daily"
                  className={`ml-auto flex-shrink-0 px-4 py-2 rounded-xl text-sm font-semibold transition-colors ${
                    heroAlert.severity === "critical"
                      ? "bg-rose-500/20 text-rose-300 hover:bg-rose-500/30 border border-rose-500/30"
                      : "bg-amber-500/20 text-amber-300 hover:bg-amber-500/30 border border-amber-500/30"
                  }`}
                >
                  Take Action &rarr;
                </Link>
              </div>
            </div>
          ) : (
            <div className="rounded-2xl bg-emerald-500/[0.06] border border-emerald-500/15 p-4 mb-1">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-emerald-500/15 flex items-center justify-center flex-shrink-0">
                  <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                </div>
                <div>
                  <h2 className="text-sm font-semibold text-emerald-300">All Clear</h2>
                  <p className="text-xs text-emerald-200/60">No critical alerts. Operations are running within normal parameters.</p>
                </div>
              </div>
            </div>
          )}
        </motion.div>
      </div>)}

      {/* Key Metrics — collapsible */}
      {isVisible("kpi-strip") && <div style={{ order: widgetOrder("kpi-strip") }}><div>
        <button
          onClick={() => setMetricsExpanded(!metricsExpanded)}
          className="flex items-center gap-2 mb-3 text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
        >
          {metricsExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          {t("dashboard.key_metrics")}
        </button>
      </div>

      {metricsExpanded && <>
      {/* Hero KPI + Supporting Metrics — asymmetric layout */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_1fr_1fr_1fr] gap-4">
        <KPICard
          label={t("dashboard.spot_price")}
          value={ssbSpot > 0 ? formatNumber(ssbSpot, locale, 1) : "\u2014"}
          unit="NOK/kg"
          delta="Live SSB data"
          deltaType="positive"
          icon={DollarSign}
          delay={0}
          hero
        />
        <KPICard
          label={t("dashboard.lice_avg")}
          value={summary?.avg_adult_female_lice != null ? formatNumber(summary.avg_adult_female_lice, locale, 3) : "\u2014"}
          delta={(summary?.avg_adult_female_lice ?? 0) < 0.5 ? "Below threshold" : "ABOVE LIMIT"}
          deltaType={(summary?.avg_adult_female_lice ?? 0) < 0.5 ? "positive" : "negative"}
          icon={Fish}
          delay={0.04}
        />
        <KPICard
          label="Max Lice"
          value={summary?.max_adult_female_lice != null ? formatNumber(summary.max_adult_female_lice, locale, 2) : "\u2014"}
          delta={(summary?.max_adult_female_lice ?? 0) > 0.5 ? "ABOVE LIMIT" : "Within limit"}
          deltaType={(summary?.max_adult_female_lice ?? 0) > 0.5 ? "negative" : "positive"}
          icon={AlertTriangle}
          delay={0.08}
        />
        <KPICard
          label="Companies"
          value={companiesWithData || "\u2014"}
          delta={`${Array.isArray(safeLeaders) ? safeLeaders.length : 0} ranked`}
          deltaType="neutral"
          icon={BarChart3}
          delay={0.12}
        />
      </div>

      {/* Macro Context Row (Change 1: Dashboard wire-up) */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          label={t("dashboard.feed_pressure")}
          value={macro?.indices?.feed_pressure?.value != null ? `${formatNumber(macro.indices.feed_pressure.value, locale, 1)}/100` : "\u2014"}
          delta={macro?.indices?.feed_pressure?.value > 65 ? "Elevated — margin risk" : macro?.indices?.feed_pressure?.value > 45 ? "Moderate" : "Low pressure"}
          deltaType={macro?.indices?.feed_pressure?.value > 65 ? "negative" : macro?.indices?.feed_pressure?.value > 45 ? "neutral" : "positive"}
          icon={Wheat}
          delay={0.1}
        />
        <KPICard
          label={t("dashboard.nok_usd")}
          value={macro?.benchmarks?.nok_usd != null ? formatNumber(macro.benchmarks.nok_usd, locale, 2) : "\u2014"}
          delta={macro?.yoy_changes?.nok_usd ? `${macro.yoy_changes.nok_usd > 0 ? "+" : ""}${macro.yoy_changes.nok_usd}% YoY` : undefined}
          deltaType={macro?.yoy_changes?.nok_usd > 0 ? "negative" : "positive"}
          icon={DollarSign}
          delay={0.13}
        />
        <KPICard
          label={t("dashboard.supply_balance")}
          value={supply?.balance ? supply.balance.charAt(0).toUpperCase() + supply.balance.slice(1).replace(/_/g, " ") : "—"}
          delta={supply?.supply_deficit_pct != null ? `Deficit: ${supply.supply_deficit_pct}%` : undefined}
          deltaType={supply?.supply_deficit_pct > 2 ? "negative" : "positive"}
          icon={Globe2}
          delay={0.16}
        />
        <KPICard
          label={t("dashboard.disease_outbreaks")}
          value={diseaseCount > 0 ? `${formatNumber(diseaseCount, locale)} active` : "Clear"}
          delta="Mattilsynet + WOAH"
          deltaType={diseaseCount > 3 ? "negative" : diseaseCount > 0 ? "neutral" : "positive"}
          icon={Shield}
          delay={0.19}
        />
      </div>
      </>}</div>}

      {/* Live Intelligence Summary */}
      {isVisible("intelligence") && <div style={{ order: widgetOrder("intelligence") }}><GlassCard delay={0.2} accent="ocean">
        <div className="flex items-center gap-2 mb-3">
          <Network className="w-4 h-4 text-ocean-400" />
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">
            {t("dashboard.live_intelligence")}
          </h3>
          <span className="ml-auto text-[9px] px-1.5 py-0.5 rounded-full bg-ocean-500/10 text-ocean-400 border border-ocean-500/20">
            Real-time
          </span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {/* Regime Alerts Summary */}
          <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06]">
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle className={`w-3.5 h-3.5 ${regimeAlerts.length > 0 ? "text-amber-400" : "text-emerald-400"}`} />
              <span className="text-[11px] font-semibold text-[var(--text-primary)]">{t("dashboard.regime_alerts")}</span>
              <span className={`ml-auto text-xs font-bold tabular-nums ${regimeAlerts.length > 0 ? "text-amber-400" : "text-emerald-400"}`}>
                {regimeAlerts.length}
              </span>
            </div>
            {regimeAlerts.length > 0 ? (
              <p className="text-[10px] text-[var(--text-secondary)] leading-relaxed">
                Top: {regimeAlerts[0]?.pa_name || `PA ${regimeAlerts[0]?.pa}`} &mdash;{" "}
                {regimeAlerts[0]?.message?.slice(0, 80) || "Regime change detected"}
              </p>
            ) : (
              <p className="text-[10px] text-[var(--text-secondary)] opacity-60">All production areas nominal</p>
            )}
          </div>

          {/* Pairs Signals Summary */}
          <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06]">
            <div className="flex items-center gap-2 mb-2">
              <GitBranch className={`w-3.5 h-3.5 ${pairsSignals.length > 0 ? "text-purple-400" : "text-emerald-400"}`} />
              <span className="text-[11px] font-semibold text-[var(--text-primary)]">{t("dashboard.pairs_signals")}</span>
              <span className={`ml-auto text-xs font-bold tabular-nums ${pairsSignals.length > 0 ? "text-purple-400" : "text-emerald-400"}`}>
                {pairsSignals.length}
              </span>
            </div>
            {pairsSignals.length > 0 ? (
              <div className="flex flex-wrap gap-1">
                {pairsSignals.slice(0, 3).map((ps: any, i: number) => (
                  <span key={i} className={`text-[9px] font-semibold px-1.5 py-0.5 rounded ${
                    ps.signal?.includes("LONG") ? "bg-emerald-500/10 text-emerald-400" :
                    ps.signal?.includes("SHORT") ? "bg-rose-500/10 text-rose-400" :
                    "bg-white/5 text-[var(--text-secondary)]"
                  }`}>
                    {ps.pair} z={ps.z_score != null ? formatNumber(ps.z_score, locale, 1) : "\u2014"}
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-[10px] text-[var(--text-secondary)] opacity-60">Spreads at normal levels</p>
            )}
          </div>

          {/* AIS Vessel Summary */}
          <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06]">
            <div className="flex items-center gap-2 mb-2">
              <Ship className="w-3.5 h-3.5 text-cyan-400" />
              <span className="text-[11px] font-semibold text-[var(--text-primary)]">{t("dashboard.ais_vessels")}</span>
              <span className="ml-auto text-xs font-bold tabular-nums text-cyan-400">
                {aisData ? (Array.isArray(aisData) ? aisData.length : (aisData?.signals?.length || 0)) : 0}
              </span>
            </div>
            {aisData && (Array.isArray(aisData) ? aisData.length : (aisData?.signals?.length || 0)) > 0 ? (
              <p className="text-[10px] text-[var(--text-secondary)] leading-relaxed">
                {(() => {
                  const vessels = Array.isArray(aisData) ? aisData : (aisData?.signals || []);
                  const topVessel = vessels[0];
                  return topVessel
                    ? `${topVessel.vessel_name || "Wellboat"} near ${topVessel.locality_name || topVessel.farm_name || "farm"} (${topVessel.signal_type || "harvest"})`
                    : "Active vessel signals detected";
                })()}
              </p>
            ) : (
              <p className="text-[10px] text-[var(--text-secondary)] opacity-60">No harvest vessel activity</p>
            )}
          </div>
        </div>
      </GlassCard></div>}

      {/* Top 50 Companies Chart + Weekly Export */}
      {isVisible("lice-chart") && <div style={{ order: widgetOrder("lice-chart") }}><div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <ChartContainer
          title={`${t("dashboard.top_companies")} — Adult Female Lice Levels`}
          subtitle="Real data · 8-week trend from BarentsWatch (NLOD 2.0)"
          className="lg:col-span-2"
          delay={0.1}
          badge={
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              REAL DATA
            </span>
          }
          footer={
            <div className="flex items-center justify-between">
              <p className="text-[10px] text-[var(--text-secondary)]">
                Regulatory threshold: 0.5 adult female lice per fish.
              </p>
              <Link
                href="/leaders"
                className="flex items-center gap-1 text-[10px] text-ocean-400 hover:text-ocean-300 transition-colors"
              >
                View all {companiesWithData} companies <ArrowRight className="w-3 h-3" />
              </Link>
            </div>
          }
        >
          {liceChartData.length > 0 ? (
            <OceanAreaChart
              data={liceChartData}
              xKey="week"
              series={Object.keys(liceChartData[0] || {}).filter(k => k !== "week").map((key, i) => ({
                key,
                name: key,
                color: COLORS[i % COLORS.length],
                filled: true,
              }))}
              height={300}
              threshold={0.5}
              thresholdLabel="Regulatory Limit"
            />
          ) : (
            <div className="h-[300px] flex items-center justify-center text-sm text-[var(--text-secondary)]">
              {t("common.loading")}
            </div>
          )}
        </ChartContainer>

        {/* Weekly Export Volume */}
        <ChartContainer
          title={`${t("dashboard.weekly_volume")} (kt)`}
          subtitle="SSB table 03024"
          delay={0.12}
          accent="emerald"
          badge={ssbSpot > 0 ? (
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">
              {formatCurrency(ssbSpot, locale)} /kg
            </span>
          ) : undefined}
        >
          {supplyData.length > 0 ? (
            <OceanBarChart
              data={supplyData}
              categoryKey="week"
              bars={[
                { key: "volume", name: "Export (kt)", color: "rgba(16,185,129,0.55)" },
              ]}
              height={300}
              showLegend={false}
            />
          ) : (
            <div className="h-[300px] flex items-center justify-center text-sm text-[var(--text-secondary)]">
              {t("common.loading")}
            </div>
          )}
        </ChartContainer>
      </div></div>}

      {/* Signals Table */}
      {isVisible("signals") && <div style={{ order: widgetOrder("signals") }}><GlassCard delay={0.15}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">
            Recent Signals
          </h3>
          <Link
            href="/signals"
            className="text-[10px] px-2 py-0.5 rounded-full bg-white/[0.04] text-[var(--text-secondary)] border border-white/[0.06] hover:text-ocean-400 transition-colors"
          >
            {signals.length} total
          </Link>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/[0.06]">
                <th className="text-left py-2.5 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Time</th>
                <th className="text-left py-2.5 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Ticker</th>
                <th className="text-left py-2.5 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Direction</th>
                <th className="text-left py-2.5 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Strength</th>
                <th className="text-left py-2.5 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Status</th>
              </tr>
            </thead>
            <tbody>
              {signals.slice(0, 8).map((sig, i) => (
                <motion.tr
                  key={sig.id || i}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.18 + i * 0.03 }}
                  className="border-b border-white/[0.04] hover:bg-white/[0.02] transition-colors"
                >
                  <td className="py-3 px-3 text-[var(--text-secondary)] text-xs font-mono">
                    {sig.created_at?.slice(0, 16)?.replace("T", " ") || "—"}
                  </td>
                  <td className="py-3 px-3 font-semibold text-[var(--text-primary)]">{sig.ticker}</td>
                  <td className="py-3 px-3">
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-semibold ${
                      sig.direction === "SHORT"
                        ? "bg-rose-500/10 text-rose-400 border border-rose-500/15"
                        : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/15"
                    }`}>
                      {sig.direction === "SHORT" ? <TrendingDown className="w-3 h-3" /> : <TrendingUp className="w-3 h-3" />}
                      {sig.direction}
                    </span>
                  </td>
                  <td className="py-3 px-3">
                    <div className="flex items-center gap-2.5">
                      <div className="w-20 h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
                        <motion.div
                          className="h-full rounded-full bg-gradient-to-r from-ocean-600 to-ocean-400"
                          initial={{ width: 0 }}
                          animate={{ width: `${(sig.strength || 0) * 100}%` }}
                          transition={{ delay: 0.2 + i * 0.03, duration: 0.4 }}
                        />
                      </div>
                      <span className="text-xs text-[var(--text-secondary)] font-mono tabular-nums">
                        {formatNumber((sig.strength || 0) * 100, locale, 0)}%
                      </span>
                    </div>
                  </td>
                  <td className="py-3 px-3">
                    <span className={`text-[11px] font-medium px-2 py-0.5 rounded-md ${
                      sig.status === "confirmed" ? "bg-emerald-500/10 text-emerald-400" :
                      sig.status === "rejected" ? "bg-rose-500/10 text-rose-400" :
                      "bg-amber-500/10 text-amber-400"
                    }`}>
                      {sig.status}
                    </span>
                  </td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
      </GlassCard></div>}

      {/* Intelligence Row: Regime Alerts · Pairs Signals · AIS · Production */}
      {isVisible("detail-cards") && <div style={{ order: widgetOrder("detail-cards") }}><div className="grid grid-cols-1 lg:grid-cols-4 gap-4">

        {/* Regime Alerts */}
        <GlassCard delay={0.22}>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-400" />
              {t("dashboard.regime_alerts")}
            </h3>
            <Link href="/lice" className="text-[10px] text-ocean-400 hover:text-ocean-300 transition-colors flex items-center gap-1">
              View all <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
          {regimeAlerts.length === 0 ? (
            <p className="text-xs text-[var(--text-secondary)] py-4 text-center opacity-60">No active regime alerts</p>
          ) : (
            <div className="space-y-1.5">
              {regimeAlerts.slice(0, 4).map((alert: any, i: number) => (
                <div key={i} className="flex items-start gap-2 p-2 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                  <div className={`w-2 h-2 rounded-full flex-shrink-0 mt-1 ${
                    alert.severity === "critical" ? "bg-rose-400" :
                    alert.severity === "high" ? "bg-amber-400" : "bg-yellow-400"
                  }`} />
                  <div className="min-w-0">
                    <p className="text-[11px] font-medium text-[var(--text-primary)] truncate">{alert.pa_name || `PA ${alert.pa}`}</p>
                    <p className="text-[10px] text-[var(--text-secondary)] truncate">{alert.message?.slice(0, 60)}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </GlassCard>

        {/* Pairs Signals */}
        <GlassCard delay={0.24}>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold flex items-center gap-2">
              <GitBranch className="w-4 h-4 text-purple-400" />
              {t("dashboard.pairs_signals")}
            </h3>
            <Link href="/signals" className="text-[10px] text-ocean-400 hover:text-ocean-300 transition-colors flex items-center gap-1">
              View all <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
          {pairsSignals.length === 0 ? (
            <p className="text-xs text-[var(--text-secondary)] py-4 text-center opacity-60">No pairs signals — neutral spread</p>
          ) : (
            <div className="space-y-1.5">
              {pairsSignals.slice(0, 4).map((ps: any, i: number) => (
                <div key={i} className="flex items-center justify-between p-2 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                  <div>
                    <p className="text-[11px] font-semibold text-[var(--text-primary)]">{ps.pair}</p>
                    <p className="text-[10px] text-[var(--text-secondary)]">z={ps.z_score != null ? formatNumber(ps.z_score, locale, 2) : "\u2014"} · {ps.signal?.replace(/_/g, " ")}</p>
                  </div>
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-md ${
                    ps.signal?.includes("LONG") ? "bg-emerald-500/10 text-emerald-400" :
                    ps.signal?.includes("SHORT") ? "bg-rose-500/10 text-rose-400" :
                    "bg-white/5 text-[var(--text-secondary)]"
                  }`}>
                    {ps.signal?.split("_").pop()}
                  </span>
                </div>
              ))}
            </div>
          )}
        </GlassCard>

        {/* AIS Activity */}
        <GlassCard delay={0.26}>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold flex items-center gap-2">
              <Ship className="w-4 h-4 text-ocean-400" />
              {t("dashboard.ais_vessels")}
            </h3>
            <span className="text-[10px] text-[var(--text-secondary)]">72h window</span>
          </div>
          {!aisData ? (
            <p className="text-xs text-[var(--text-secondary)] py-4 text-center opacity-60">{t("common.loading")}</p>
          ) : (
            <div className="space-y-2">
              <div className="flex items-center justify-between p-2.5 rounded-lg bg-ocean-500/[0.04] border border-ocean-500/[0.1]">
                <span className="text-xs text-[var(--text-secondary)]">Harvest signals</span>
                <span className="text-sm font-bold text-ocean-400">{Array.isArray(aisData) ? aisData.length : (aisData?.signals?.length || 0)}</span>
              </div>
              {Array.isArray(aisData) && aisData.slice(0, 3).map((sig: any, i: number) => (
                <div key={i} className="flex items-center gap-2 p-1.5 rounded-md bg-white/[0.02]">
                  <Zap className="w-3 h-3 text-amber-400 flex-shrink-0" />
                  <div className="min-w-0">
                    <p className="text-[11px] text-[var(--text-primary)] truncate">{sig.vessel_name || sig.locality_name || "Wellboat"}</p>
                    <p className="text-[10px] text-[var(--text-secondary)]">{sig.signal_type || "harvest"}</p>
                  </div>
                </div>
              ))}
              <Link href="/command-centre" className="flex items-center gap-1 text-[10px] text-ocean-400 hover:text-ocean-300 transition-colors mt-1">
                <BarChart2 className="w-3 h-3" />
                Open Command Centre
              </Link>
            </div>
          )}
        </GlassCard>

        {/* Production */}
        <GlassCard delay={0.28}>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-emerald-400" />
              {t("dashboard.production_stats")}
            </h3>
          </div>
          {!production ? (
            <p className="text-xs text-[var(--text-secondary)] py-4 text-center opacity-60">{t("common.loading")}</p>
          ) : (
            <div className="space-y-2">
              <div className="flex items-center justify-between p-2.5 rounded-lg bg-emerald-500/[0.04] border border-emerald-500/[0.1]">
                <span className="text-xs text-[var(--text-secondary)]">Annual (latest)</span>
                <span className="text-sm font-bold text-emerald-400">
                  {production.total_tonnes ? `${formatNumber(production.total_tonnes / 1000, locale, 0)}k t` : production.latest_year || "\u2014"}
                </span>
              </div>
              {production.salmon_tonnes && (
                <div className="flex items-center justify-between p-1.5 rounded-md bg-white/[0.02]">
                  <span className="text-[10px] text-[var(--text-secondary)]">Salmon</span>
                  <span className="text-[11px] font-mono">{formatNumber(production.salmon_tonnes / 1000, locale, 0)}k t</span>
                </div>
              )}
              {production.yoy_change_pct != null && (
                <div className="flex items-center justify-between p-1.5 rounded-md bg-white/[0.02]">
                  <span className="text-[10px] text-[var(--text-secondary)]">YoY Change</span>
                  <span className={`text-[11px] font-mono ${production.yoy_change_pct > 0 ? "text-emerald-400" : "text-rose-400"}`}>
                    {production.yoy_change_pct > 0 ? "+" : ""}{production.yoy_change_pct}%
                  </span>
                </div>
              )}
              {counties.length > 0 && (
                <div className="mt-2 pt-2 border-t border-white/[0.06]">
                  <p className="text-[9px] text-[var(--text-secondary)] uppercase tracking-wider mb-1.5">Top Counties</p>
                  {counties.map((c: any, i: number) => {
                    const h = c.harvest_tonnes || 0;
                    const maxH = counties[0]?.harvest_tonnes || 1;
                    return (
                      <div key={i} className="flex items-center gap-2 py-0.5">
                        <span className="text-[10px] text-[var(--text-secondary)] w-20 truncate">{c.county || c.name || `#${i + 1}`}</span>
                        <div className="flex-1 h-2 bg-white/[0.04] rounded-full overflow-hidden">
                          <div className="h-full bg-emerald-500/40 rounded-full" style={{ width: `${(h / maxH) * 100}%` }} />
                        </div>
                        <span className="text-[10px] text-[var(--text-primary)] tabular-nums w-12 text-right">{formatNumber(h / 1000, locale, 0)}k</span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </GlassCard>
      </div></div>}

      {/* Disclaimer */}
      {isVisible("disclaimer") && (
      <div style={{ order: widgetOrder("disclaimer") }}>
      <p className="text-[10px] text-[var(--text-secondary)] text-center opacity-60">
        Data: BarentsWatch (NLOD 2.0), SSB, Fiskeridirektoratet, FRED, Mattilsynet, WOAH.
        7 countries tracked. Not financial advice.
      </p>
      </div>
      )}

      {/* Customize Panel — always last */}
      <DashboardCustomizePanel
        open={customizeOpen}
        onClose={() => setCustomizeOpen(false)}
        widgets={widgets}
        moveWidget={moveWidget}
        toggleWidget={toggleWidget}
        resetLayout={resetLayout}
      />
    </div>
    </ErrorBoundary>
  );
}
