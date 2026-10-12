"use client";
import { useState } from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import {
  TrendingDown, TrendingUp, DollarSign, ArrowRight, Shield,
  Settings2, Printer,
} from "lucide-react";
import dynamic from "next/dynamic";
import GlassCard from "@/components/GlassCard";
import TickerStrip from "@/components/TickerStrip";
import SkeletonCard from "@/components/SkeletonCard";

const OceanAreaChart = dynamic(() => import("@/components/charts/OceanAreaChart"), { ssr: false, loading: () => <SkeletonCard variant="chart" className="h-48" /> });
const OceanBarChart = dynamic(() => import("@/components/charts/OceanBarChart"), { ssr: false, loading: () => <SkeletonCard variant="chart" className="h-48" /> });
const ChartContainer = dynamic(() => import("@/components/charts/ChartContainer"), { ssr: false, loading: () => <SkeletonCard variant="chart" className="h-48" /> });
import { useTranslation, formatNumber, formatCurrency } from "@/lib/i18n";
import ErrorBoundary from "@/components/ErrorBoundary";
import FreshnessIndicator from "@/components/FreshnessIndicator";
import DataQualityBadge from "@/components/DataQualityBadge";
import { useDashboardLayout } from "@/lib/useDashboardLayout";
import DashboardCustomizePanel from "@/components/DashboardCustomizePanel";
import { chartPalette } from "@/lib/design-tokens";

import { useDashboardData } from "@/components/useDashboardData";
import DashboardHeroAlert from "@/components/DashboardHeroAlert";
import DashboardKPIStrip from "@/components/DashboardKPIStrip";
import DashboardLiveIntelligence from "@/components/DashboardLiveIntelligence";
import DashboardProduction from "@/components/DashboardProduction";

/* eslint-disable @typescript-eslint/no-explicit-any */

export default function DashboardPage() {
  const { t, locale } = useTranslation();
  const data = useDashboardData(locale);
  const { widgets, moveWidget, toggleWidget, resetLayout } = useDashboardLayout();
  const [customizeOpen, setCustomizeOpen] = useState(false);
  const isVisible = (id: string) => widgets.find((w) => w.id === id)?.visible !== false;
  const widgetOrder = (id: string) => { const idx = widgets.findIndex((w) => w.id === id); return idx >= 0 ? idx : 99; };

  const { summary, fetchedAt, signals, leaders, ssbSpot, supplyData,
    regimeAlerts, pairsSignals, aisData, macro, supply, diseaseCount,
    anomaly, production, counties, heroAlert, alertsLoaded,
    metricsExpanded, setMetricsExpanded } = data;

  // Build Top 10 area chart from real leader sparklines
  const safeLeaders = Array.isArray(leaders) ? leaders : [];
  const top10 = safeLeaders.filter((c) => c?.lice_sparkline?.length >= 6 && c?.avg_lice > 0).slice(0, 10);
  const COLORS = [...chartPalette, "#A855F7", "#EF4444"];
  const liceChartData = top10.length >= 2
    ? top10[0].lice_sparkline.map((_: number, i: number) => {
        const row: Record<string, string | number> = { week: `W${i + 1}` };
        top10.forEach((c) => {
          const label = (c.name || c.company_name).replace(/ AS$| ASA$/i, "").replace(/OPPDRETT|FARMING|SEAFOOD|SJØFARM|FISKEOPPDRETT/gi, "").trim().slice(0, 14);
          row[label] = c.lice_sparkline[i] || 0;
        });
        return row;
      })
    : [];
  const companiesWithData = safeLeaders.filter((c: any) => c.n_lice_records > 0).length;

  return (
    <ErrorBoundary fallbackTitle="Dashboard error">
    <div className="flex flex-col gap-6">
      {/* Header */}
      <motion.div style={{ order: -1 }} initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-display text-[var(--text-primary)] tracking-tight">{t("dashboard.title")}</h1>
          <div className="flex items-center gap-2 mt-1">
            <p className="text-[13px] text-[var(--text-secondary)]">Norwegian salmon aquaculture intelligence &mdash; {companiesWithData || "123"} companies tracked</p>
            <FreshnessIndicator lastUpdated={fetchedAt} />
            <DataQualityBadge source="BarentsWatch + SSB" quality="live" />
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={() => window.print()} className="print:hidden flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white/[0.03] backdrop-blur border border-white/[0.06] hover:bg-white/[0.06] hover:border-white/[0.1] transition-colors" title="Export as PDF">
            <Printer className="w-3.5 h-3.5 text-[var(--text-secondary)]" /><span className="text-xs text-[var(--text-secondary)] hidden sm:inline">PDF</span>
          </button>
          <button onClick={() => setCustomizeOpen(true)} className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white/[0.03] backdrop-blur border border-white/[0.06] hover:bg-white/[0.06] hover:border-white/[0.1] transition-colors" aria-label="Customize dashboard layout">
            <Settings2 className="w-3.5 h-3.5 text-[var(--text-secondary)]" /><span className="text-xs text-[var(--text-secondary)] hidden sm:inline">{t("dashboard.customize")}</span>
          </button>
          {anomaly && (
            <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full border ${anomaly.risk_level === "CRITICAL" ? "bg-rose-500/[0.08] border-rose-500/[0.15]" : anomaly.risk_level === "HIGH" ? "bg-orange-500/[0.08] border-orange-500/[0.15]" : anomaly.risk_level === "ELEVATED" ? "bg-amber-500/[0.08] border-amber-500/[0.15]" : "bg-emerald-500/[0.06] border-emerald-500/[0.1]"}`}>
              <Shield className={`w-3.5 h-3.5 ${anomaly.risk_level === "CRITICAL" ? "text-rose-400" : anomaly.risk_level === "HIGH" ? "text-orange-400" : anomaly.risk_level === "ELEVATED" ? "text-amber-400" : "text-emerald-400"}`} />
              <span className={`text-xs font-semibold ${anomaly.risk_level === "CRITICAL" ? "text-rose-400" : anomaly.risk_level === "HIGH" ? "text-orange-400" : anomaly.risk_level === "ELEVATED" ? "text-amber-400" : "text-emerald-400"}`}>Risk: {formatNumber(anomaly.composite_score, locale, 0)}/100</span>
            </div>
          )}
          {ssbSpot > 0 && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-amber-500/[0.06] border border-amber-500/[0.1]">
              <DollarSign className="w-3.5 h-3.5 text-amber-400" /><span className="text-xs text-amber-400 font-semibold">{formatCurrency(ssbSpot, locale)} /kg</span>
            </div>
          )}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/[0.03] backdrop-blur border border-white/[0.06]">
            <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.5)]" />
            <span className="text-xs text-emerald-400 font-medium">{summary ? `W${summary.week} ${summary.year}` : "Connecting..."}</span>
          </div>
        </div>
      </motion.div>

      <DashboardHeroAlert heroAlert={heroAlert} alertsLoaded={alertsLoaded} isVisible={isVisible("hero-alert")} order={widgetOrder("hero-alert")} />

      <TickerStrip items={[
        { label: "SSB Spot", value: ssbSpot ? `NOK ${formatNumber(ssbSpot, locale, 1)}` : "\u2014", change: 0, trend: "flat" as const },
        { label: "Avg Lice", value: summary?.avg_adult_female_lice != null ? formatNumber(summary.avg_adult_female_lice, locale, 3) : "\u2014", trend: (summary?.avg_adult_female_lice ?? 0) > 0.3 ? "up" as const : "down" as const },
        { label: "Companies", value: leaders.length ? `${leaders.length}` : "\u2014", trend: "flat" as const },
        { label: "Anomaly", value: anomaly?.composite_score != null ? formatNumber(anomaly.composite_score, locale, 0) : "\u2014", trend: (anomaly?.composite_score ?? 0) > 50 ? "up" as const : "flat" as const },
        { label: "Signals", value: signals.length ? `${signals.length}` : "\u2014", trend: "flat" as const },
      ]} />

      <DashboardKPIStrip isVisible={isVisible("kpi-strip")} order={widgetOrder("kpi-strip")} metricsExpanded={metricsExpanded} setMetricsExpanded={setMetricsExpanded}
        ssbSpot={ssbSpot} summary={summary} safeLeaders={safeLeaders} companiesWithData={companiesWithData} macro={macro} supply={supply} diseaseCount={diseaseCount} locale={locale} t={t} />

      <DashboardLiveIntelligence isVisible={isVisible("intelligence")} order={widgetOrder("intelligence")} regimeAlerts={regimeAlerts} pairsSignals={pairsSignals} aisData={aisData} locale={locale} t={t} />

      {/* Top Companies Chart + Weekly Export */}
      {isVisible("lice-chart") && <div style={{ order: widgetOrder("lice-chart") }}><div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <ChartContainer title={`${t("dashboard.top_companies")} \u2014 Adult Female Lice Levels`} subtitle="Real data \u00B7 8-week trend from BarentsWatch (NLOD 2.0)" className="lg:col-span-2" delay={0.1}
          badge={<span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">REAL DATA</span>}
          footer={<div className="flex items-center justify-between"><p className="text-[10px] text-[var(--text-secondary)]">Regulatory threshold: 0.5 adult female lice per fish.</p><Link href="/leaders" className="flex items-center gap-1 text-[10px] text-ocean-400 hover:text-ocean-300 transition-colors">View all {companiesWithData} companies <ArrowRight className="w-3 h-3" /></Link></div>}>
          {liceChartData.length > 0 ? (
            <OceanAreaChart data={liceChartData} xKey="week" series={Object.keys(liceChartData[0] || {}).filter(k => k !== "week").map((key, i) => ({ key, name: key, color: COLORS[i % COLORS.length], filled: true }))} height={300} threshold={0.5} thresholdLabel="Regulatory Limit" />
          ) : (<div className="h-[300px] flex items-center justify-center text-sm text-[var(--text-secondary)]">{t("common.loading")}</div>)}
        </ChartContainer>
        <ChartContainer title={`${t("dashboard.weekly_volume")} (kt)`} subtitle="SSB table 03024" delay={0.12} accent="emerald"
          badge={ssbSpot > 0 ? <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">{formatCurrency(ssbSpot, locale)} /kg</span> : undefined}>
          {supplyData.length > 0 ? (
            <OceanBarChart data={supplyData} categoryKey="week" bars={[{ key: "volume", name: "Export (kt)", color: "rgba(16,185,129,0.55)" }]} height={300} showLegend={false} />
          ) : (<div className="h-[300px] flex items-center justify-center text-sm text-[var(--text-secondary)]">{t("common.loading")}</div>)}
        </ChartContainer>
      </div></div>}

      {/* Signals Table */}
      {isVisible("signals") && <div style={{ order: widgetOrder("signals") }}><GlassCard delay={0.15}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">Recent Signals</h3>
          <Link href="/signals" className="text-[10px] px-2 py-0.5 rounded-full bg-white/[0.04] text-[var(--text-secondary)] border border-white/[0.06] hover:text-ocean-400 transition-colors">{signals.length} total</Link>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-white/[0.06]">
              <th className="text-left py-2.5 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Time</th>
              <th className="text-left py-2.5 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Ticker</th>
              <th className="text-left py-2.5 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Direction</th>
              <th className="text-left py-2.5 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Strength</th>
              <th className="text-left py-2.5 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Status</th>
            </tr></thead>
            <tbody>{signals.slice(0, 8).map((sig, i) => (
              <motion.tr key={sig.id || i} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.18 + i * 0.03 }} className="border-b border-white/[0.04] hover:bg-white/[0.02] transition-colors">
                <td className="py-3 px-3 text-[var(--text-secondary)] text-xs font-mono">{sig.created_at?.slice(0, 16)?.replace("T", " ") || "\u2014"}</td>
                <td className="py-3 px-3 font-semibold text-[var(--text-primary)]">{sig.ticker}</td>
                <td className="py-3 px-3"><span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-semibold ${sig.direction?.toLowerCase() === "short" ? "bg-rose-500/10 text-rose-400 border border-rose-500/15" : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/15"}`}>{sig.direction?.toLowerCase() === "short" ? <TrendingDown className="w-3 h-3" /> : <TrendingUp className="w-3 h-3" />}{sig.direction}</span></td>
                <td className="py-3 px-3"><div className="flex items-center gap-2.5"><div className="w-20 h-1.5 rounded-full bg-white/[0.06] overflow-hidden"><motion.div className="h-full rounded-full bg-gradient-to-r from-ocean-600 to-ocean-400" initial={{ width: 0 }} animate={{ width: `${(sig.strength || 0) * 100}%` }} transition={{ delay: 0.2 + i * 0.03, duration: 0.4 }} /></div><span className="text-xs text-[var(--text-secondary)] font-mono tabular-nums">{formatNumber((sig.strength || 0) * 100, locale, 0)}%</span></div></td>
                <td className="py-3 px-3"><span className={`text-[11px] font-medium px-2 py-0.5 rounded-md ${sig.status === "confirmed" ? "bg-emerald-500/10 text-emerald-400" : sig.status === "rejected" ? "bg-rose-500/10 text-rose-400" : "bg-amber-500/10 text-amber-400"}`}>{sig.status}</span></td>
              </motion.tr>
            ))}</tbody>
          </table>
        </div>
      </GlassCard></div>}

      <DashboardProduction isVisible={isVisible("detail-cards")} order={widgetOrder("detail-cards")} regimeAlerts={regimeAlerts} pairsSignals={pairsSignals} aisData={aisData} production={production} counties={counties} locale={locale} t={t} />

      {/* Disclaimer */}
      {isVisible("disclaimer") && (<div style={{ order: widgetOrder("disclaimer") }}><p className="text-[10px] text-[var(--text-secondary)] text-center opacity-60">Data: BarentsWatch (NLOD 2.0), SSB, Fiskeridirektoratet, FRED, Mattilsynet, WOAH. 7 countries tracked. Not financial advice.</p></div>)}

      <DashboardCustomizePanel open={customizeOpen} onClose={() => setCustomizeOpen(false)} widgets={widgets} moveWidget={moveWidget} toggleWidget={toggleWidget} resetLayout={resetLayout} />
    </div>
    </ErrorBoundary>
  );
}
