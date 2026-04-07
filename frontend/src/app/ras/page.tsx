"use client";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Factory, RefreshCw, TrendingUp, Globe2, AlertTriangle,
  CheckCircle2, Clock, XCircle, BarChart3, Download, Gauge,
} from "lucide-react";
import KPICard from "@/components/KPICard";
import GlassCard from "@/components/GlassCard";
import { OcButton } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { exportToCSV } from "@/lib/export";
import { useTranslation } from "@/lib/i18n";

/* eslint-disable @typescript-eslint/no-explicit-any */

const STATUS_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  operational: { bg: "bg-emerald-500/20", text: "text-emerald-400", label: "Operational" },
  ramping:     { bg: "bg-amber-500/20", text: "text-amber-400", label: "Ramping Up" },
  construction:{ bg: "bg-sky-500/20", text: "text-sky-400", label: "Construction" },
  planning:    { bg: "bg-violet-500/20", text: "text-violet-400", label: "Planning" },
  delayed:     { bg: "bg-orange-500/20", text: "text-orange-400", label: "Delayed" },
  abandoned:   { bg: "bg-rose-500/20", text: "text-rose-400", label: "Abandoned" },
};

const COUNTRY_FLAGS: Record<string, string> = {
  US: "\u{1F1FA}\u{1F1F8}",
  NO: "\u{1F1F3}\u{1F1F4}",
  JP: "\u{1F1EF}\u{1F1F5}",
  IE: "\u{1F1EE}\u{1F1EA}",
  GB: "\u{1F1EC}\u{1F1E7}",
  CA: "\u{1F1E8}\u{1F1E6}",
};

function fmt(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return n.toLocaleString();
}

function fmtPct(n: number | null | undefined): string {
  if (n == null) return "N/A";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(1)}%`;
}

export default function RASPage() {
  const { t } = useTranslation();
  const [summary, setSummary] = useState<any>(null);
  const [companies, setCompanies] = useState<any[]>([]);
  const [timeline, setTimeline] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const [s, c, t] = await Promise.allSettled([
        api.rasSummary(),
        api.rasCompanies(),
        api.rasTimeline(),
      ]);
      if (s.status === "fulfilled") setSummary(s.value);
      if (c.status === "fulfilled") setCompanies(c.value);
      if (t.status === "fulfilled") setTimeline(t.value);
    } catch { /* empty */ }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const counts = summary?.project_counts || {};
  const timelineData = timeline?.timeline || [];

  // Find max for bar chart scaling
  const maxTimeline = Math.max(...timelineData.map((y: any) => y.total || 0), 1);

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] flex items-center gap-3">
            <Factory className="w-7 h-7 text-ocean-400" />
            {t("nav.ras_tracker")}
          </h1>
          <p className="text-sm text-[var(--text-secondary)] mt-1">
            Land-based salmon farming &mdash; projects, capacity, and reality vs hype
          </p>
        </div>
        <div className="flex gap-2">
          <OcButton variant="ghost" size="sm"
            leftIcon={<Download className="w-3.5 h-3.5" />}
            onClick={() => companies.length > 0 && exportToCSV(companies.map(c => ({
              Company: c.name, Country: c.country, Status: c.status,
              Technology: c.technology,
              "Planned Capacity (t)": c.planned_capacity,
              "Actual 2024 (t)": c.actual_2024,
              "Actual 2025 (t)": c.actual_2025,
              "Target 2026 (t)": c.target_2026,
              "Target 2030 (t)": c.target_2030,
              "Utilization %": c.utilization_pct,
              "% of Global": c.pct_of_global_supply,
              "Funding USD": c.funding_usd,
            })), "ras-companies")}>
            Export CSV
          </OcButton>
          <OcButton variant="secondary" size="sm" onClick={load} loading={loading}
            leftIcon={<RefreshCw className="w-3.5 h-3.5" />}>Refresh</OcButton>
        </div>
      </motion.div>

      {/* KPI Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KPICard
          label="RAS Production 2025"
          value={summary ? `${fmt(summary.total_ras_actual_2025)}t` : "\u2014"}
          delta={summary?.growth_2024_to_2025_pct != null ? fmtPct(summary.growth_2024_to_2025_pct) + " YoY" : undefined}
          deltaType={summary?.growth_2024_to_2025_pct > 0 ? "positive" : "neutral"}
          icon={TrendingUp}
          delay={0}
        />
        <KPICard
          label="% of Global Supply"
          value={summary ? `${summary.ras_share_of_global_2025_pct}%` : "\u2014"}
          delta={`of ${fmt(summary?.global_production_tonnes || 0)}t total`}
          deltaType="neutral"
          icon={Globe2}
          delay={0.05}
        />
        <KPICard
          label="Active Projects"
          value={counts.active != null ? String(counts.active) : "\u2014"}
          delta={`${counts.operational || 0} operational, ${counts.ramping || 0} ramping`}
          deltaType="neutral"
          icon={Factory}
          delay={0.1}
        />
        <KPICard
          label="Avg Utilization"
          value={summary ? `${summary.avg_utilization_pct}%` : "\u2014"}
          delta={summary ? `Reality ratio: ${summary.reality_ratio_pct}%` : undefined}
          deltaType={summary?.avg_utilization_pct > 50 ? "positive" : "negative"}
          icon={Gauge}
          delay={0.15}
        />
      </div>

      {/* Company Cards Grid */}
      <GlassCard>
        <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
          <Factory className="w-4 h-4 text-ocean-400" />
          RAS Companies
        </h3>
        {loading && companies.length === 0 ? (
          <div className="animate-pulse space-y-3">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-24 bg-white/5 rounded-lg" />
            ))}
          </div>
        ) : companies.length === 0 ? (
          <p className="text-[var(--text-tertiary)]">No data available</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {companies.map((c: any, i: number) => {
              const st = STATUS_STYLES[c.status] || STATUS_STYLES.planning;
              const flag = COUNTRY_FLAGS[c.country_flag] || "";
              return (
                <motion.div
                  key={c.name}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.03 }}
                  className="p-4 rounded-xl bg-white/[0.03] border border-white/[0.06] hover:bg-white/[0.06] transition-all"
                >
                  {/* Header */}
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <span className="text-lg">{flag}</span>
                      <div>
                        <h3 className="text-sm font-semibold text-[var(--text-primary)]">{c.name}</h3>
                        <p className="text-xs text-[var(--text-tertiary)]">{c.country} &middot; {c.technology}</p>
                      </div>
                    </div>
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${st.bg} ${st.text}`}>
                      {st.label}
                    </span>
                  </div>

                  {/* Capacity bar */}
                  <div className="mb-3">
                    <div className="flex justify-between text-xs text-[var(--text-secondary)] mb-1">
                      <span>Actual 2025: {fmt(c.actual_2025)}t</span>
                      <span>Planned: {fmt(c.planned_capacity)}t</span>
                    </div>
                    <div className="h-2 bg-white/[0.06] rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-ocean-500 to-ocean-400 transition-all duration-500"
                        style={{ width: `${Math.min(c.utilization_pct, 100)}%` }}
                      />
                    </div>
                    <p className="text-[10px] text-[var(--text-tertiary)] mt-0.5">
                      {c.utilization_pct}% utilization
                    </p>
                  </div>

                  {/* Stats row */}
                  <div className="grid grid-cols-3 gap-2 text-center">
                    <div>
                      <p className="text-[10px] text-[var(--text-tertiary)]">2024</p>
                      <p className="text-xs font-medium text-[var(--text-secondary)]">{fmt(c.actual_2024)}t</p>
                    </div>
                    <div>
                      <p className="text-[10px] text-[var(--text-tertiary)]">Target 2026</p>
                      <p className="text-xs font-medium text-[var(--text-secondary)]">{fmt(c.target_2026)}t</p>
                    </div>
                    <div>
                      <p className="text-[10px] text-[var(--text-tertiary)]">Target 2030</p>
                      <p className="text-xs font-medium text-[var(--text-secondary)]">{fmt(c.target_2030)}t</p>
                    </div>
                  </div>

                  {/* Growth */}
                  {c.growth_24_25_pct != null && (
                    <div className="mt-2 flex items-center gap-1 text-xs">
                      <TrendingUp className={`w-3 h-3 ${c.growth_24_25_pct > 0 ? "text-emerald-400" : "text-rose-400"}`} />
                      <span className={c.growth_24_25_pct > 0 ? "text-emerald-400" : "text-rose-400"}>
                        {fmtPct(c.growth_24_25_pct)} YoY
                      </span>
                      {c.funding_usd > 0 && (
                        <span className="text-[var(--text-tertiary)] ml-auto">
                          ${fmt(c.funding_usd)} raised
                        </span>
                      )}
                    </div>
                  )}

                  {/* Notes */}
                  <p className="text-[10px] text-[var(--text-tertiary)] mt-2 line-clamp-2">{c.notes}</p>
                </motion.div>
              );
            })}
          </div>
        )}
      </GlassCard>

      {/* Timeline Chart */}
      <GlassCard>
        <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
          <BarChart3 className="w-4 h-4 text-ocean-400" />
          RAS Capacity Timeline (2024&#8211;2030)
        </h3>
        {timelineData.length === 0 ? (
          <div className="animate-pulse h-48 bg-white/5 rounded-lg" />
        ) : (
          <div>
            <div className="flex items-end gap-3 h-56 px-2">
              {timelineData.map((y: any, i: number) => {
                const pct = (y.total / maxTimeline) * 100;
                const isActual = y.year <= 2025;
                return (
                  <div key={y.year} className="flex-1 flex flex-col items-center gap-1">
                    <span className="text-xs font-medium text-[var(--text-primary)]">
                      {fmt(y.total)}t
                    </span>
                    <span className="text-[10px] text-[var(--text-tertiary)]">
                      {y.pct_of_global}%
                    </span>
                    <motion.div
                      initial={{ height: 0 }}
                      animate={{ height: `${pct}%` }}
                      transition={{ delay: i * 0.08, duration: 0.5 }}
                      className={`w-full rounded-t-lg ${
                        isActual
                          ? "bg-gradient-to-t from-ocean-600 to-ocean-400"
                          : "bg-gradient-to-t from-ocean-800 to-ocean-600 border border-dashed border-ocean-500/30"
                      }`}
                      style={{ minHeight: 4 }}
                    />
                    <span className={`text-xs font-medium ${isActual ? "text-ocean-400" : "text-[var(--text-tertiary)]"}`}>
                      {y.year}
                    </span>
                    {isActual && (
                      <span className="text-[9px] text-emerald-400">Actual</span>
                    )}
                    {!isActual && (
                      <span className="text-[9px] text-[var(--text-tertiary)]">Target</span>
                    )}
                  </div>
                );
              })}
            </div>
            <div className="mt-3 flex items-center gap-4 text-xs text-[var(--text-tertiary)]">
              <div className="flex items-center gap-1.5">
                <div className="w-3 h-3 rounded bg-gradient-to-t from-ocean-600 to-ocean-400" />
                <span>Actual production</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-3 h-3 rounded bg-ocean-800 border border-dashed border-ocean-500/30" />
                <span>Company targets (projected)</span>
              </div>
            </div>
          </div>
        )}
      </GlassCard>

      {/* Reality Check */}
      <GlassCard accent="rose">
        <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-rose-400" />
          Reality Check: Actual vs Hype
        </h3>
        {!summary ? (
          <div className="animate-pulse h-32 bg-white/5 rounded-lg" />
        ) : (
          <div className="space-y-4">
            {/* Big metrics */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-4 rounded-xl bg-rose-500/5 border border-rose-500/10">
                <div className="flex items-center gap-2 mb-2">
                  <AlertTriangle className="w-4 h-4 text-rose-400" />
                  <span className="text-xs font-medium text-rose-400">Reality Ratio</span>
                </div>
                <p className="text-2xl font-bold text-rose-400">{summary.reality_ratio_pct}%</p>
                <p className="text-xs text-[var(--text-tertiary)] mt-1">
                  Actual output vs total announced capacity
                </p>
              </div>
              <div className="p-4 rounded-xl bg-amber-500/5 border border-amber-500/10">
                <div className="flex items-center gap-2 mb-2">
                  <Globe2 className="w-4 h-4 text-amber-400" />
                  <span className="text-xs font-medium text-amber-400">Global Share</span>
                </div>
                <p className="text-2xl font-bold text-amber-400">{summary.ras_share_of_global_2025_pct}%</p>
                <p className="text-xs text-[var(--text-tertiary)] mt-1">
                  of {fmt(summary.global_production_tonnes)}t global production
                </p>
              </div>
              <div className="p-4 rounded-xl bg-sky-500/5 border border-sky-500/10">
                <div className="flex items-center gap-2 mb-2">
                  <Clock className="w-4 h-4 text-sky-400" />
                  <span className="text-xs font-medium text-sky-400">Abandoned/Delayed</span>
                </div>
                <p className="text-2xl font-bold text-sky-400">{counts.abandoned_or_delayed || 0}</p>
                <p className="text-xs text-[var(--text-tertiary)] mt-1">
                  projects failed or significantly delayed
                </p>
              </div>
            </div>

            {/* Total funding */}
            <div className="p-3 rounded-lg bg-white/[0.03] border border-white/[0.06]">
              <div className="flex items-center justify-between">
                <span className="text-sm text-[var(--text-secondary)]">Total Industry Funding</span>
                <span className="text-lg font-bold text-[var(--text-primary)]">
                  ${fmt(summary.total_funding_usd)}
                </span>
              </div>
              <div className="flex items-center justify-between mt-1">
                <span className="text-sm text-[var(--text-secondary)]">Cost per Tonne Produced (2025)</span>
                <span className="text-sm font-medium text-[var(--text-primary)]">
                  {summary.total_ras_actual_2025 > 0
                    ? `$${Math.round(summary.total_funding_usd / summary.total_ras_actual_2025).toLocaleString()}/t`
                    : "\u2014"}
                </span>
              </div>
              <p className="text-[10px] text-[var(--text-tertiary)] mt-2">
                Note: This measures cumulative capital investment per tonne of current production.
                Traditional sea-cage salmon costs ~$5-8/kg to produce. RAS capital intensity is dramatically higher.
              </p>
            </div>

            {/* Insights */}
            {summary.insights && summary.insights.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider">
                  Key Insights
                </h4>
                {summary.insights.map((insight: string, i: number) => (
                  <div key={i} className="flex gap-2 text-xs text-[var(--text-secondary)]">
                    <span className="text-ocean-400 mt-0.5 flex-shrink-0">&bull;</span>
                    <span>{insight}</span>
                  </div>
                ))}
              </div>
            )}

            {/* 2030 projection comparison */}
            <div className="p-3 rounded-lg bg-white/[0.03] border border-white/[0.06]">
              <h4 className="text-xs font-medium text-[var(--text-secondary)] mb-2">
                Projection: 2025 Actual vs 2030 Targets
              </h4>
              <div className="grid grid-cols-3 gap-4 text-center">
                <div>
                  <p className="text-xs text-[var(--text-tertiary)]">2025 Actual</p>
                  <p className="text-lg font-bold text-emerald-400">{fmt(summary.total_ras_actual_2025)}t</p>
                  <p className="text-[10px] text-[var(--text-tertiary)]">{summary.ras_share_of_global_2025_pct}% of global</p>
                </div>
                <div>
                  <p className="text-xs text-[var(--text-tertiary)]">2026 Target</p>
                  <p className="text-lg font-bold text-amber-400">{fmt(summary.total_ras_target_2026)}t</p>
                  <p className="text-[10px] text-[var(--text-tertiary)]">{summary.ras_share_of_global_2026_pct}% of global</p>
                </div>
                <div>
                  <p className="text-xs text-[var(--text-tertiary)]">2030 Target</p>
                  <p className="text-lg font-bold text-sky-400">{fmt(summary.total_ras_target_2030)}t</p>
                  <p className="text-[10px] text-[var(--text-tertiary)]">{summary.ras_share_of_global_2030_pct}% of global</p>
                </div>
              </div>
            </div>
          </div>
        )}
      </GlassCard>
    </div>
  );
}
