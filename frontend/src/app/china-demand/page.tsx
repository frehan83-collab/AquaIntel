"use client";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Globe2, RefreshCw, TrendingUp, TrendingDown,
  Activity, BarChart3, Zap, Flag, Info,
} from "lucide-react";
import KPICard from "@/components/KPICard";
import GlassCard from "@/components/GlassCard";
import { OcButton } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";
import DataQualityBadge from "@/components/DataQualityBadge";

/* eslint-disable @typescript-eslint/no-explicit-any */

const FLAG_EMOJI: Record<string, string> = {
  NO: "\uD83C\uDDF3\uD83C\uDDF4", CL: "\uD83C\uDDE8\uD83C\uDDF1",
  GB: "\uD83C\uDDEC\uD83C\uDDE7", FO: "\uD83C\uDDEB\uD83C\uDDF4",
  CA: "\uD83C\uDDE8\uD83C\uDDE6", AU: "\uD83C\uDDE6\uD83C\uDDFA",
};

export default function ChinaDemandPage() {
  const { t } = useTranslation();
  const [snapshot, setSnapshot] = useState<any>(null);
  const [signals, setSignals] = useState<any>(null);
  const [impact, setImpact] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  // Distinct fetch-failure state (review H4): the page must never claim
  // "estimates are shown" while loading or when nothing could be loaded.
  const [snapshotError, setSnapshotError] = useState(false);

  const load = async () => {
    setLoading(true);
    setSnapshotError(false);
    try {
      const [snapRes, sigRes, impRes] = await Promise.allSettled([
        api.chinaDemand(),
        api.chinaDemandSignals(),
        api.chinaDemandImpact(),
      ]);
      if (snapRes.status === "fulfilled") {
        setSnapshot(snapRes.value);
      } else {
        // Keep any stale snapshot for context, but mark the failure so no
        // provenance claim is made about data that was not (re)loaded.
        setSnapshotError(true);
      }
      if (sigRes.status === "fulfilled") setSignals(sigRes.value);
      if (impRes.status === "fulfilled") setImpact(impRes.value);
    } catch {
      setSnapshotError(true);
    }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const norExp = snapshot?.norway_exports_to_china || {};
  // Structured liveness contract (review M3): the engine exposes
  // norway_exports_to_china.is_live keyed on records actually returned —
  // no more parsing the data_source display string for "LIVE".
  const norwayLive = norExp.is_live === true;
  const chinaTotal = snapshot?.china_total_imports || {};
  const suppliers = snapshot?.suppliers || [];
  const monthlySeries = snapshot?.monthly_series || [];
  const momentum = signals?.momentum_chart || [];
  const insights = signals?.insights || [];

  // Sparkline from monthly series
  const sparkVols = monthlySeries.slice(-12).map((p: any) => p.tonnes);

  // Signal color
  const signalColor = (dir: string) => {
    if (dir?.includes("bullish")) return "text-emerald-400";
    if (dir?.includes("bearish")) return "text-rose-400";
    return "text-amber-400";
  };

  // Impact color
  const impactColor = (label: string) => {
    if (label?.includes("Upward")) return "text-emerald-400";
    if (label?.includes("Downward")) return "text-rose-400";
    return "text-amber-400";
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] flex items-center gap-3">
            <Globe2 className="w-6 h-6 text-ocean-400" />
            {t("nav.china_demand")}
          </h1>
          <p className="text-sm text-[var(--text-secondary)] mt-1 flex items-center gap-2">
            Norwegian salmon exports to China &mdash; SSB series + global market estimates
            {snapshot?.data_provenance && <DataQualityBadge provenance={snapshot.data_provenance} />}
          </p>
        </div>
        <OcButton variant="secondary" size="sm" onClick={load} loading={loading}
          leftIcon={<RefreshCw className="w-3.5 h-3.5" />}>Refresh</OcButton>
      </motion.div>

      {/* Fetch-failure banner (review H4): distinct from loading; states
          exactly what is (not) on screen instead of claiming estimates. */}
      {snapshotError && !loading && (
        <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 flex items-center justify-between gap-3">
          <p className="text-sm text-rose-300">
            {snapshot
              ? "Failed to refresh China demand data — showing the previously loaded snapshot."
              : "Failed to load China demand data — no figures are currently shown. The API could not be reached."}
          </p>
          <OcButton variant="secondary" size="sm" onClick={load}
            leftIcon={<RefreshCw className="w-3.5 h-3.5" />}>Retry</OcButton>
        </div>
      )}

      {/* KPI Row */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <KPICard
          label="China Total Imports"
          value={chinaTotal.tonnes_annual ? `${(chinaTotal.tonnes_annual / 1000).toFixed(0)}k t` : "\u2014"}
          delta={chinaTotal.estimate_year ? `${chinaTotal.estimate_year} estimate` : ""}
          deltaType="neutral"
          icon={Globe2}
          delay={0}
        />
        <KPICard
          label="Norway \u2192 China (12m)"
          value={norExp.tonnes_12m ? `${Number(norExp.tonnes_12m).toLocaleString()} t` : "\u2014"}
          delta={norExp.yoy_trend_pct ? `${norExp.yoy_trend_pct > 0 ? "+" : ""}${norExp.yoy_trend_pct}% YoY` : ""}
          deltaType={norExp.yoy_trend_pct > 0 ? "positive" : norExp.yoy_trend_pct < 0 ? "negative" : "neutral"}
          icon={TrendingUp}
          sparkline={sparkVols.length >= 4 ? sparkVols : undefined}
          delay={0.05}
        />
        <KPICard
          label="Norway Share of China"
          value={snapshot?.norway_share_pct ? `${snapshot.norway_share_pct}%` : "\u2014"}
          delta="of total Chinese salmon imports"
          deltaType="neutral"
          icon={Flag}
          delay={0.1}
        />
        <KPICard
          label="Demand Signal"
          value={signals?.signal_label || "\u2014"}
          delta={signals?.signal_score ? `Score: ${signals.signal_score.toFixed(2)}` : ""}
          deltaType={signals?.signal_direction?.includes("bullish") ? "positive" : signals?.signal_direction?.includes("bearish") ? "negative" : "neutral"}
          icon={Zap}
          delay={0.15}
        />
        <KPICard
          label="Price Impact"
          value={impact?.impact_label || "\u2014"}
          delta={impact?.estimated_price_impact_pct ? `${impact.estimated_price_impact_pct > 0 ? "+" : ""}${impact.estimated_price_impact_pct}% est.` : ""}
          deltaType={impact?.estimated_price_impact_pct > 0 ? "positive" : impact?.estimated_price_impact_pct < 0 ? "negative" : "neutral"}
          icon={Activity}
          delay={0.2}
        />
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

        {/* Supplier Breakdown */}
        <GlassCard delay={0.25}>
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-ocean-400" />
            Supplier Breakdown
            <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-ocean-500/10 text-ocean-400 border border-ocean-500/20 ml-auto">
              Origins supplying China
            </span>
          </h3>
          {suppliers.length === 0 ? (
            <p className="text-[var(--text-muted)] text-sm py-8 text-center">No data available</p>
          ) : (
            <div className="space-y-2">
              {suppliers.map((s: any, i: number) => (
                <div key={i}
                  className="flex items-center justify-between p-2.5 rounded-lg bg-white/[0.03] hover:bg-white/[0.06] transition">
                  <div className="flex items-center gap-2.5">
                    <span className="text-base">{FLAG_EMOJI[s.flag] || s.flag}</span>
                    <div>
                      <p className="text-sm font-medium text-[var(--text-primary)]">{s.origin}</p>
                      <p className="text-[10px] text-[var(--text-muted)]">
                        {s.is_live ? (
                          <span className="text-emerald-400">LIVE</span>
                        ) : (
                          <span className="text-amber-400">Estimate</span>
                        )}
                        {" \u2014 "}{s.share_pct}% share
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-semibold text-[var(--text-primary)]">
                      {Number(s.tonnes).toLocaleString()} t
                    </p>
                    {s.yoy_growth_pct !== undefined && s.yoy_growth_pct !== 0 && (
                      <p className={`text-[10px] ${s.yoy_growth_pct > 0 ? "text-emerald-400" : "text-rose-400"}`}>
                        {s.yoy_growth_pct > 0 ? "+" : ""}{s.yoy_growth_pct}% YoY
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
          {/* Honest provenance note (review H4): only claimed when data is
              actually on screen — hidden while loading/failed. */}
          {snapshot && suppliers.length > 0 && (
            <p className="text-[10px] text-[var(--text-muted)] mt-3 flex items-start gap-1">
              <Info className="w-3 h-3 mt-0.5 flex-shrink-0" />
              {norwayLive
                ? "Norway data is LIVE from SSB."
                : "SSB series unavailable — Norway shown from curated estimates."}{" "}
              Other origins are structured estimates from UN Comtrade/GACC.
            </p>
          )}
        </GlassCard>

        {/* Demand Momentum */}
        <GlassCard delay={0.3}>
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-ocean-400" />
            Demand Momentum
            <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-ocean-500/10 text-ocean-400 border border-ocean-500/20 ml-auto">
              Rolling 3-month trend
            </span>
          </h3>
          {momentum.length === 0 ? (
            <p className="text-[var(--text-muted)] text-sm py-8 text-center">Insufficient data for momentum chart</p>
          ) : (
            <div className="space-y-1">
              <div className="flex items-end gap-1 h-40">
                {momentum.slice(-12).map((p: any, i: number) => {
                  const maxVal = Math.max(...momentum.slice(-12).map((m: any) => m.rolling_3m_tonnes));
                  const pct = maxVal > 0 ? (p.rolling_3m_tonnes / maxVal) * 100 : 0;
                  return (
                    <div key={i} className="flex-1 flex flex-col items-center gap-1">
                      <div
                        className="w-full rounded-t bg-gradient-to-t from-ocean-600 to-ocean-400 min-h-[2px] transition-all"
                        style={{ height: `${pct}%` }}
                        title={`${p.month}: ${p.rolling_3m_tonnes}t (3m rolling)`}
                      />
                      <span className="text-[8px] text-[var(--text-muted)] rotate-[-45deg] w-6 text-center">
                        {p.month?.slice(5) || ""}
                      </span>
                    </div>
                  );
                })}
              </div>
              <p className="text-[10px] text-[var(--text-muted)] text-center mt-2">
                Rolling 3-month Norwegian export volume to China (tonnes)
              </p>
            </div>
          )}
        </GlassCard>

        {/* Price Impact Assessment */}
        <GlassCard delay={0.35}>
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <Activity className="w-4 h-4 text-ocean-400" />
            Price Impact Assessment
            <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-ocean-500/10 text-ocean-400 border border-ocean-500/20 ml-auto">
              China demand vs spot price
            </span>
          </h3>
          {!impact ? (
            <p className="text-[var(--text-muted)] text-sm py-8 text-center">Loading impact data...</p>
          ) : (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 rounded-lg bg-white/[0.03]">
                  <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider">Vol-Price Correlation</p>
                  <p className="text-lg font-bold text-[var(--text-primary)]">
                    {impact.correlation_vol_price?.toFixed(2) || "\u2014"}
                  </p>
                </div>
                <div className="p-3 rounded-lg bg-white/[0.03]">
                  <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider">Est. Price Impact</p>
                  <p className={`text-lg font-bold ${impactColor(impact.impact_label)}`}>
                    {impact.estimated_price_impact_pct > 0 ? "+" : ""}{impact.estimated_price_impact_pct}%
                  </p>
                </div>
                <div className="p-3 rounded-lg bg-white/[0.03]">
                  <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider">China Export Share</p>
                  <p className="text-lg font-bold text-[var(--text-primary)]">
                    {impact.china_share_of_norway_exports || 0}%
                  </p>
                  <p className="text-[10px] text-[var(--text-muted)]">of total Norwegian exports</p>
                </div>
                <div className="p-3 rounded-lg bg-white/[0.03]">
                  <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider">Demand Direction</p>
                  <p className={`text-lg font-bold ${signalColor(impact.demand_direction)}`}>
                    {impact.demand_direction?.replace(/_/g, " ") || "\u2014"}
                  </p>
                </div>
              </div>

              <div className="p-3 rounded-lg bg-white/[0.03] border border-white/[0.04]">
                <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                  {impact.assessment}
                </p>
              </div>

              <p className="text-[10px] text-[var(--text-muted)] leading-relaxed">
                {impact.transmission_mechanism}
              </p>
            </div>
          )}
        </GlassCard>

        {/* Demand Signals Detail */}
        <GlassCard delay={0.4}>
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <Zap className="w-4 h-4 text-ocean-400" />
            Demand Signal Components
            <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-ocean-500/10 text-ocean-400 border border-ocean-500/20 ml-auto">
              Computed dynamically
            </span>
          </h3>
          {!signals ? (
            <p className="text-[var(--text-muted)] text-sm py-8 text-center">Loading signals...</p>
          ) : (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 rounded-lg bg-white/[0.03]">
                  <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider">YoY Growth</p>
                  <p className={`text-lg font-bold ${signals.yoy_growth_pct > 0 ? "text-emerald-400" : "text-rose-400"}`}>
                    {signals.yoy_growth_pct > 0 ? "+" : ""}{signals.yoy_growth_pct}%
                  </p>
                </div>
                <div className="p-3 rounded-lg bg-white/[0.03]">
                  <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider">Acceleration</p>
                  <p className={`text-lg font-bold ${signals.acceleration_pct > 0 ? "text-emerald-400" : signals.acceleration_pct < 0 ? "text-rose-400" : "text-amber-400"}`}>
                    {signals.acceleration_pct > 0 ? "+" : ""}{signals.acceleration_pct}%
                  </p>
                </div>
                <div className="p-3 rounded-lg bg-white/[0.03]">
                  <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider">Seasonal Index</p>
                  <p className="text-lg font-bold text-[var(--text-primary)]">{signals.seasonal_index?.toFixed(2)}</p>
                  <p className="text-[10px] text-[var(--text-muted)]">{signals.seasonal_label}</p>
                </div>
                <div className="p-3 rounded-lg bg-white/[0.03]">
                  <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider">Market Growth</p>
                  <p className="text-lg font-bold text-[var(--text-primary)]">
                    +{signals.market_growth_pct}%
                  </p>
                  <p className="text-[10px] text-[var(--text-muted)]">total China imports</p>
                </div>
              </div>

              {/* Composite Signal */}
              <div className={`p-3 rounded-lg border ${
                signals.signal_direction?.includes("bullish")
                  ? "bg-emerald-500/[0.06] border-emerald-500/20"
                  : signals.signal_direction?.includes("bearish")
                    ? "bg-rose-500/[0.06] border-rose-500/20"
                    : "bg-amber-500/[0.06] border-amber-500/20"
              }`}>
                <div className="flex items-center justify-between">
                  <p className="text-xs font-medium text-[var(--text-primary)]">Composite Signal</p>
                  <span className={`text-sm font-bold ${signalColor(signals.signal_direction)}`}>
                    {signals.signal_label}
                  </span>
                </div>
                <div className="mt-1.5 h-1.5 bg-white/[0.06] rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${
                      signals.signal_direction?.includes("bullish") ? "bg-emerald-500" :
                      signals.signal_direction?.includes("bearish") ? "bg-rose-500" : "bg-amber-500"
                    }`}
                    style={{ width: `${Math.min(Math.max((signals.signal_score + 1) / 2 * 100, 5), 95)}%` }}
                  />
                </div>
              </div>

              {/* Insights */}
              {insights.length > 0 && (
                <div className="space-y-1.5">
                  {insights.map((ins: string, i: number) => (
                    <div key={i} className="flex items-start gap-2 text-xs text-[var(--text-secondary)]">
                      {ins.toLowerCase().includes("warning") || ins.toLowerCase().includes("declining") ? (
                        <TrendingDown className="w-3.5 h-3.5 text-rose-400 mt-0.5 flex-shrink-0" />
                      ) : (
                        <TrendingUp className="w-3.5 h-3.5 text-emerald-400 mt-0.5 flex-shrink-0" />
                      )}
                      <span>{ins}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </GlassCard>
      </div>

      {/* Norway Monthly Exports to China */}
      {monthlySeries.length > 0 && (
        <GlassCard delay={0.45}>
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-ocean-400" />
            Monthly Norwegian Exports to China
            <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 ml-auto">
              LIVE SSB 08799
            </span>
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-white/[0.06]">
                  <th className="text-left py-2 text-[var(--text-muted)] font-medium">Month</th>
                  <th className="text-right py-2 text-[var(--text-muted)] font-medium">Volume (t)</th>
                  <th className="text-right py-2 text-[var(--text-muted)] font-medium">Value (MNOK)</th>
                  <th className="text-right py-2 text-[var(--text-muted)] font-medium">Visualization</th>
                </tr>
              </thead>
              <tbody>
                {monthlySeries.slice(-12).map((row: any, i: number) => {
                  const maxT = Math.max(...monthlySeries.slice(-12).map((r: any) => r.tonnes));
                  const pct = maxT > 0 ? (row.tonnes / maxT) * 100 : 0;
                  return (
                    <tr key={i} className="border-b border-white/[0.03] hover:bg-white/[0.02]">
                      <td className="py-1.5 text-[var(--text-primary)]">{row.month}</td>
                      <td className="py-1.5 text-right text-[var(--text-primary)] font-medium">
                        {Number(row.tonnes).toLocaleString()}
                      </td>
                      <td className="py-1.5 text-right text-[var(--text-secondary)]">
                        {row.value_mnok}
                      </td>
                      <td className="py-1.5 text-right w-32">
                        <div className="h-2 bg-white/[0.04] rounded-full overflow-hidden">
                          <div className="h-full bg-ocean-500 rounded-full" style={{ width: `${pct}%` }} />
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </GlassCard>
      )}

      {/* Data Source Footer — honest claims only (review H4): rendered
          only when a snapshot is actually on screen. While loading or
          after a total fetch failure no provenance claim is made (the
          banner above states the failure instead). */}
      {snapshot && (
        <div className="text-[10px] text-[var(--text-muted)] p-3 rounded-lg bg-white/[0.02] border border-white/[0.04]">
          <strong>Data Sources:</strong>{" "}
          {norwayLive
            ? "Norwegian exports to China are LIVE from SSB table 08799 (Statistics Norway)."
            : "The SSB table 08799 series is currently unavailable; Norwegian export figures are shown from curated estimates."}
          Total Chinese salmon imports and non-Norwegian origin volumes are structured estimates from
          UN Comtrade / GACC, last updated {snapshot?.china_total_imports?.data_source || "Q4 2025"}.
          All growth rates, market shares, and momentum are computed dynamically from the data.
        </div>
      )}
    </div>
  );
}
