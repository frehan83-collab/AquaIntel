"use client";
import { useEffect, useState, useMemo, Suspense } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Trophy, TrendingUp, TrendingDown, Minus, Shield, AlertTriangle,
  Building2, MapPin, BarChart3, ChevronDown, ChevronUp,
  X, Star, Zap, Target, ArrowUpRight, Lock, Download,
} from "lucide-react";
import { useTranslation, formatNumber, formatCurrency } from "@/lib/i18n";
import { exportToCSV } from "@/lib/export";
import { useQueryParams } from "@/lib/useQueryParams";
import KPICard from "@/components/KPICard";
import GlassCard from "@/components/GlassCard";
import { OcButton } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { useApiError } from "@/lib/useApiError";
import DataQualityBadge from "@/components/DataQualityBadge";
import type { DiseaseCompanyCounts } from "@/types/api";

type SortKey = "rank" | "performance_score" | "outlook_index" | "production_volume_tonnes" | "avg_lice" | "risk_level";
type FilterType = "all" | "public" | "private";
type RiskFilter = "all" | "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

const riskColors: Record<string, string> = {
  LOW: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  MEDIUM: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  HIGH: "bg-orange-500/10 text-orange-400 border-orange-500/20",
  CRITICAL: "bg-rose-500/10 text-rose-400 border-rose-500/20",
};

const outlookColors = (dir: string) => {
  if (dir === "positive") return "text-emerald-400";
  if (dir === "negative") return "text-rose-400";
  return "text-amber-400";
};

const OutlookIcon = ({ dir }: { dir: string }) => {
  if (dir === "positive") return <TrendingUp className="w-3.5 h-3.5 text-emerald-400" />;
  if (dir === "negative") return <TrendingDown className="w-3.5 h-3.5 text-rose-400" />;
  return <Minus className="w-3.5 h-3.5 text-amber-400" />;
};

function DualSparkline({
  historical,
  predicted,
  histColor = "#00D4C8",
  predColor = "#F59E0B",
}: {
  historical: number[];
  predicted: number[];
  histColor?: string;
  predColor?: string;
}) {
  if ((!historical || historical.length < 2) && (!predicted || predicted.length === 0)) return null;

  const allData = [...(historical || []), ...(predicted || [])];
  const max = Math.max(...allData, 0.01);
  const min = Math.min(...allData, 0);
  const range = max - min || 0.01;
  const totalLen = allData.length;
  const w = 100;
  const h = 24;

  const toPoint = (v: number, i: number) =>
    `${(i / Math.max(totalLen - 1, 1)) * w},${h - ((v - min) / range) * h}`;

  // Historical line
  const histPoints = (historical || []).map((v, i) => toPoint(v, i)).join(" ");

  // Prediction line (starts from last historical point)
  const predStartIdx = (historical || []).length - 1;
  const bridgePoint = historical?.length ? toPoint(historical[historical.length - 1], predStartIdx) : "";
  const predPoints = (predicted || []).map((v, i) => toPoint(v, predStartIdx + 1 + i)).join(" ");

  // Divider position
  const dividerX = historical?.length ? (predStartIdx / Math.max(totalLen - 1, 1)) * w : 0;

  return (
    <svg width={w} height={h} className="opacity-70">
      {/* Threshold line at 0.5 */}
      {max >= 0.4 && (
        <line
          x1={0} y1={h - ((0.5 - min) / range) * h}
          x2={w} y2={h - ((0.5 - min) / range) * h}
          stroke="#F43F5E" strokeWidth={0.5} strokeDasharray="2 2" opacity={0.3}
        />
      )}
      {/* Historical */}
      {histPoints && (
        <polyline points={histPoints} fill="none" stroke={histColor} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
      )}
      {/* Prediction (dashed) */}
      {predPoints && (
        <polyline
          points={`${bridgePoint} ${predPoints}`}
          fill="none" stroke={predColor} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round"
          strokeDasharray="3 2"
        />
      )}
      {/* Divider dot */}
      {historical?.length && predicted?.length ? (
        <circle
          cx={dividerX}
          cy={h - ((historical[historical.length - 1] - min) / range) * h}
          r={2} fill={histColor}
        />
      ) : null}
    </svg>
  );
}

function ScoreBar({ score, label, max = 100 }: { score: number; label: string; max?: number }) {
  const pct = Math.min(100, (score / max) * 100);
  const color = pct >= 70 ? "from-emerald-600 to-emerald-400" : pct >= 40 ? "from-amber-600 to-amber-400" : "from-rose-600 to-rose-400";
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className="text-[11px] text-[var(--text-secondary)]">{label}</span>
        <span className="text-[11px] font-mono font-semibold">{score.toFixed(0)}</span>
      </div>
      <div className="w-full h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
        <motion.div
          className={`h-full rounded-full bg-gradient-to-r ${color}`}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.6, ease: "easeOut" }}
        />
      </div>
    </div>
  );
}

function LeadersPageInner() {
  const { t, locale } = useTranslation();
  const handleError = useApiError();
  const [filters, setFilters] = useQueryParams({
    sort: "rank" as string,
    asc: true as boolean,
    type: "all" as string,
    risk: "all" as string,
    pa: 0,
  });

  const sortKey = filters.sort as SortKey;
  const sortAsc = filters.asc;
  const filterType = filters.type as FilterType;
  const riskFilter = filters.risk as RiskFilter;
  const paFilter = filters.pa;

  const [companies, setCompanies] = useState<any[]>([]);
  const [paLeaderboard, setPaLeaderboard] = useState<any[]>([]);
  const [diseaseMap, setDiseaseMap] = useState<Record<string, DiseaseCompanyCounts>>({});
  const [loading, setLoading] = useState(true);
  const [selectedCompany, setSelectedCompany] = useState<any>(null);
  const [showOptIn, setShowOptIn] = useState(false);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.leadersTop30().catch(() => []),
      api.paLeaderboard().catch(() => []),
      api.diseaseByCompany().catch(handleError("leaders_disease_by_company")),
    ]).then(([c, pa, disease]) => {
      setCompanies(c);
      setPaLeaderboard(pa);
      setDiseaseMap(disease?.companies ?? {});
    }).finally(() => setLoading(false));
  }, []);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setFilters({ asc: !sortAsc });
    } else {
      setFilters({ sort: key, asc: key === "rank" || key === "avg_lice" });
    }
  };

  const filtered = useMemo(() => {
    let result = [...companies];
    if (filterType === "public") result = result.filter(c => c.is_public);
    if (filterType === "private") result = result.filter(c => !c.is_public);
    if (riskFilter !== "all") result = result.filter(c => c.risk_level === riskFilter);
    if (paFilter > 0) result = result.filter(c => c.production_areas?.includes(paFilter));

    result.sort((a, b) => {
      const riskOrder: Record<string, number> = { LOW: 0, MEDIUM: 1, HIGH: 2, CRITICAL: 3 };
      let va = sortKey === "risk_level" ? (riskOrder[a[sortKey]] ?? 0) : a[sortKey];
      let vb = sortKey === "risk_level" ? (riskOrder[b[sortKey]] ?? 0) : b[sortKey];
      if (typeof va === "string") va = va.toLowerCase();
      if (typeof vb === "string") vb = vb.toLowerCase();
      if (va < vb) return sortAsc ? -1 : 1;
      if (va > vb) return sortAsc ? 1 : -1;
      return 0;
    });
    return result;
  }, [companies, sortKey, sortAsc, filterType, riskFilter]);

  const avgScore = companies.length > 0 ? companies.reduce((s, c) => s + c.performance_score, 0) / companies.length : 0;
  const publicCount = companies.filter(c => c.is_public).length;

  const SortHeader = ({ label, k, className = "" }: { label: string; k: SortKey; className?: string }) => (
    <th
      className={`text-left py-2.5 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider cursor-pointer hover:text-ocean-400 transition-colors select-none ${className}`}
      onClick={() => handleSort(k)}
    >
      <div className="flex items-center gap-1">
        {label}
        {sortKey === k && (sortAsc ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />)}
      </div>
    </th>
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-3">
            <Trophy className="w-6 h-6 text-amber-400" />
            {t("leaders.title")}
          </h1>
          <div className="flex items-center gap-2 mt-1">
            <p className="text-sm text-[var(--text-secondary)]">
              Performance benchmarking powered by biological simulations
            </p>
            <DataQualityBadge source="BarentsWatch + ESG" quality="live" />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => window.print()}
            className="print:hidden flex items-center gap-1.5 px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:text-ocean-400 bg-white/[0.04] border border-white/[0.08] rounded-lg transition-colors"
            title="Export as PDF"
          >
            <Download className="w-3.5 h-3.5" /> PDF
          </button>
          <OcButton
            variant="primary"
            size="md"
            onClick={() => setShowOptIn(true)}
            leftIcon={<Star className="w-4 h-4" />}
          >
            Get Your Benchmark Report
          </OcButton>
        </div>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard label="Companies Ranked" value={companies.length} icon={Building2} delay={0} />
        <KPICard label="Avg Performance" value={formatNumber(avgScore, locale, 1)} icon={Target} delay={0.03} />
        <KPICard
          label="Public / Private"
          value={`${publicCount} / ${companies.length - publicCount}`}
          icon={BarChart3}
          delay={0.06}
        />
        <KPICard
          label="High Risk"
          value={companies.filter(c => c.risk_level === "HIGH" || c.risk_level === "CRITICAL").length}
          icon={AlertTriangle}
          deltaType={companies.filter(c => c.risk_level === "CRITICAL").length > 0 ? "negative" : "neutral"}
          delay={0.09}
        />
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <OcButton
          variant="ghost"
          size="sm"
          onClick={() => exportToCSV(companies, "leaders_lice_ranking")}
          leftIcon={<Download className="w-3.5 h-3.5" />}
        >
          Export CSV
        </OcButton>
        <div className="w-px h-6 bg-white/[0.08]" />
        {(["all", "public", "private"] as FilterType[]).map(f => (
          <OcButton
            key={f}
            variant={filterType === f ? "accent" : "ghost"}
            size="sm"
            onClick={() => setFilters({ type: f })}
          >
            {f === "all" ? "All" : f === "public" ? "Public" : "Private"}
          </OcButton>
        ))}
        <div className="w-px h-6 bg-white/[0.08]" />
        {(["all", "LOW", "MEDIUM", "HIGH", "CRITICAL"] as RiskFilter[]).map(r => (
          <OcButton
            key={r}
            variant={riskFilter === r ? "accent" : "ghost"}
            size="xs"
            onClick={() => setFilters({ risk: r })}
          >
            {r === "all" ? "All Risk" : r}
          </OcButton>
        ))}
        <div className="w-px h-6 bg-white/[0.08]" />
        <select
          value={paFilter}
          onChange={(e) => setFilters({ pa: Number(e.target.value) })}
          className="bg-white/[0.04] border border-white/[0.08] rounded-lg px-2 py-1 text-xs focus:outline-hidden focus:border-ocean-500/30"
        >
          <option value={0}>All PAs</option>
          {Array.from({ length: 13 }, (_, i) => i + 1).map(pa => (
            <option key={pa} value={pa}>PA-{pa}</option>
          ))}
        </select>
      </div>

      {/* Table */}
      <GlassCard delay={0.1} className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/[0.06]">
                <SortHeader label={t("leaders.rank")} k="rank" className="w-12" />
                <th className="text-left py-2.5 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">{t("leaders.company_name")}</th>
                <SortHeader label={t("leaders.production")} k="production_volume_tonnes" />
                <SortHeader label={t("leaders.lice_score")} k="performance_score" />
                <SortHeader label="12w Outlook" k="outlook_index" />
                <th className="text-left py-2.5 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Price Impact</th>
                <SortHeader label={t("leaders.esg_score")} k="avg_lice" />
                <th className="text-left py-2.5 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">{t("leaders.disease")}</th>
                <th className="text-left py-2.5 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">
                  <div>Trend</div>
                  <div className="flex items-center gap-2 mt-0.5 font-normal normal-case tracking-normal">
                    <span className="flex items-center gap-1"><span className="w-3 h-[2px] bg-[#00D4C8] rounded-full inline-block" />Actual</span>
                    <span className="flex items-center gap-1"><span className="w-3 h-[2px] bg-[#F59E0B] rounded-full inline-block opacity-70" style={{ borderBottom: "1px dashed #F59E0B" }} />Predicted</span>
                  </div>
                </th>
                <SortHeader label={t("leaders.verdict")} k="risk_level" />
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={10} className="py-12 text-center text-[var(--text-secondary)]">{t("common.loading")}</td></tr>
              ) : filtered.length === 0 ? (
                <tr><td colSpan={10} className="py-12 text-center text-[var(--text-secondary)]">{t("common.no_data")}</td></tr>
              ) : (
                filtered.map((co, i) => (
                  <motion.tr
                    key={co.name}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: Math.min(i * 0.02, 0.4) }}
                    className="border-b border-white/[0.04] hover:bg-white/[0.03] cursor-pointer transition-colors"
                    onClick={() => setSelectedCompany(co)}
                  >
                    {/* Rank */}
                    <td className="py-3 px-3">
                      <span className={`text-xs font-bold tabular-nums ${
                        co.rank <= 3 ? "text-amber-400" : co.rank <= 10 ? "text-ocean-400" : "text-[var(--text-secondary)]"
                      }`}>
                        {co.rank <= 3 ? "🥇🥈🥉"[co.rank - 1] : co.rank}
                      </span>
                    </td>
                    {/* Company */}
                    <td className="py-3 px-3">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-semibold text-[var(--text-primary)]">{co.name}</span>
                        {co.is_public && co.ticker && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-ocean-500/10 text-ocean-400 border border-ocean-500/20">
                            {co.ticker}
                          </span>
                        )}
                        {co.parent_group && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-violet-500/10 text-violet-400 border border-violet-500/20">
                            {co.parent_group}
                          </span>
                        )}
                        {!co.is_public && !co.parent_group && (
                          <Lock className="w-3 h-3 text-[var(--text-secondary)] opacity-40" />
                        )}
                      </div>
                      <div className="flex items-center gap-1.5 mt-0.5">
                        <MapPin className="w-3 h-3 text-[var(--text-secondary)]" />
                        <span className="text-[10px] text-[var(--text-secondary)]">
                          {co.production_areas?.length > 0 ? `PA ${co.production_areas.join(", ")}` : "Norway"}
                        </span>
                        <span className="text-[10px] text-[var(--text-secondary)]">· {co.n_localities} sites</span>
                        <span className="text-[10px] text-[var(--text-secondary)]">· {(co.n_lice_records || 0).toLocaleString()} records</span>
                      </div>
                    </td>
                    {/* Volume */}
                    <td className="py-3 px-3 font-mono text-xs tabular-nums">
                      {co.production_volume_tonnes != null
                        ? co.production_volume_tonnes > 1000
                          ? `${formatNumber(co.production_volume_tonnes / 1000, locale, 1)}k`
                          : formatNumber(co.production_volume_tonnes, locale)
                        : "\u2014"}
                    </td>
                    {/* Score */}
                    <td className="py-3 px-3">
                      <div className="flex items-center gap-2">
                        <div className="w-12 h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
                          <div
                            className={`h-full rounded-full ${
                              co.performance_score >= 70 ? "bg-emerald-400" :
                              co.performance_score >= 40 ? "bg-amber-400" : "bg-rose-400"
                            }`}
                            style={{ width: `${co.performance_score}%` }}
                          />
                        </div>
                        <span className={`text-xs font-bold tabular-nums ${
                          co.performance_score >= 70 ? "text-emerald-400" :
                          co.performance_score >= 40 ? "text-amber-400" : "text-rose-400"
                        }`}>
                          {formatNumber(co.performance_score, locale)}
                        </span>
                      </div>
                    </td>
                    {/* Outlook */}
                    <td className="py-3 px-3">
                      <div className="flex items-center gap-1.5">
                        <OutlookIcon dir={co.outlook_direction} />
                        <span className={`text-xs font-semibold tabular-nums ${outlookColors(co.outlook_direction)}`}>
                          {formatNumber(co.outlook_index, locale)}
                        </span>
                      </div>
                    </td>
                    {/* Price Impact */}
                    <td className="py-3 px-3">
                      <span className={`text-xs font-mono ${
                        co.price_impact_direction === "bullish" ? "text-emerald-400" :
                        co.price_impact_direction === "bearish" ? "text-rose-400" :
                        "text-[var(--text-secondary)]"
                      }`}>
                        {co.price_impact_pct != null ? `${co.price_impact_pct > 0 ? "+" : ""}${formatNumber(co.price_impact_pct, locale, 1)}%` : "\u2014"}
                      </span>
                    </td>
                    {/* Avg Lice */}
                    <td className="py-3 px-3">
                      <span className={`text-xs font-mono tabular-nums ${
                        co.avg_lice > 0.3 ? "text-rose-400" : co.avg_lice > 0.15 ? "text-amber-400" : "text-emerald-400"
                      }`}>
                        {co.avg_lice != null ? formatNumber(co.avg_lice, locale, 3) : "\u2014"}
                      </span>
                    </td>
                    {/* Disease */}
                    <td className="py-3 px-3">
                      {(() => {
                        const d = diseaseMap[co.name];
                        if (!d || d.total === 0) return (
                          <span className="text-[10px] text-emerald-400 font-medium">{t("leaders.clear")}</span>
                        );
                        return (
                          <div className="space-y-0.5">
                            {d.isa > 0 && (
                              <span className="text-[10px] font-bold text-rose-400 block">{d.isa} ISA</span>
                            )}
                            {d.pd > 0 && (
                              <span className="text-[10px] font-bold text-orange-400 block">{d.pd} PD</span>
                            )}
                            {d.other > 0 && (
                              <span className="text-[10px] font-bold text-amber-400 block">{d.other} Other</span>
                            )}
                          </div>
                        );
                      })()}
                    </td>
                    {/* Dual Trend Chart */}
                    <td className="py-3 px-3">
                      <DualSparkline
                        historical={co.lice_sparkline}
                        predicted={co.lice_prediction || []}
                      />
                    </td>
                    {/* Risk */}
                    <td className="py-3 px-3">
                      <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-md border ${riskColors[co.risk_level] || riskColors.LOW}`}>
                        {co.risk_level}
                      </span>
                    </td>
                  </motion.tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </GlassCard>

      {/* Detail Card Modal */}
      <AnimatePresence>
        {selectedCompany && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-black/60 backdrop-blur-xs"
            onClick={() => setSelectedCompany(null)}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              transition={{ type: "spring", stiffness: 300, damping: 25 }}
              className="relative w-full max-w-2xl max-h-[85vh] overflow-y-auto rounded-2xl bg-[rgba(6,15,28,0.95)] backdrop-blur-2xl border border-white/[0.08] shadow-[0_24px_80px_rgba(0,0,0,0.5)]"
              onClick={e => e.stopPropagation()}
            >
              {/* Top accent */}
              <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-ocean-500/60 via-ocean-400/30 to-transparent" />

              {/* Close */}
              <button
                onClick={() => setSelectedCompany(null)}
                className="absolute top-4 right-4 p-2 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] transition-colors z-10"
              >
                <X className="w-4 h-4 text-[var(--text-secondary)]" />
              </button>

              <div className="p-6 space-y-6">
                {/* Header */}
                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-ocean-500/20 to-ocean-600/20 border border-ocean-500/20 flex items-center justify-center">
                    <Trophy className={`w-6 h-6 ${selectedCompany.rank <= 3 ? "text-amber-400" : "text-ocean-400"}`} />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-3">
                      <h2 className="text-xl font-bold">{selectedCompany.name}</h2>
                      {selectedCompany.ticker && (
                        <span className="text-xs px-2 py-0.5 rounded bg-ocean-500/10 text-ocean-400 border border-ocean-500/20">
                          {selectedCompany.ticker}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-4 mt-1 text-xs text-[var(--text-secondary)]">
                      <span className="flex items-center gap-1"><MapPin className="w-3 h-3" /> {selectedCompany.hq_region}</span>
                      <span>{selectedCompany.n_localities} sites</span>
                      <span>{selectedCompany.is_public ? "Public" : "Private"}</span>
                      <span>Rank #{selectedCompany.rank}</span>
                    </div>
                  </div>
                </div>

                {/* Score + Outlook KPIs */}
                <div className="grid grid-cols-3 gap-3">
                  <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06] text-center">
                    <p className="text-[10px] text-[var(--text-secondary)] uppercase tracking-wider">Performance</p>
                    <p className={`text-2xl font-bold mt-1 ${
                      selectedCompany.performance_score >= 70 ? "text-emerald-400" :
                      selectedCompany.performance_score >= 40 ? "text-amber-400" : "text-rose-400"
                    }`}>
                      {formatNumber(selectedCompany.performance_score, locale)}
                    </p>
                  </div>
                  <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06] text-center">
                    <p className="text-[10px] text-[var(--text-secondary)] uppercase tracking-wider">12w Outlook</p>
                    <div className="flex items-center justify-center gap-1 mt-1">
                      <OutlookIcon dir={selectedCompany.outlook_direction} />
                      <span className={`text-2xl font-bold ${outlookColors(selectedCompany.outlook_direction)}`}>
                        {formatNumber(selectedCompany.outlook_index, locale)}
                      </span>
                    </div>
                  </div>
                  <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06] text-center">
                    <p className="text-[10px] text-[var(--text-secondary)] uppercase tracking-wider">Peer Rank</p>
                    <p className="text-2xl font-bold mt-1 text-ocean-400">
                      Top {formatNumber(100 - selectedCompany.peer_percentile, locale)}%
                    </p>
                  </div>
                </div>

                {/* Score Breakdown */}
                <div className="space-y-2">
                  <h3 className="text-sm font-semibold">Score Breakdown</h3>
                  {selectedCompany.score_components && Object.entries(selectedCompany.score_components).map(([key, val]: [string, any]) => (
                    <ScoreBar
                      key={key}
                      label={key.replace(/_/g, " ").replace(/\b\w/g, (l: string) => l.toUpperCase())}
                      score={val}
                    />
                  ))}
                </div>

                {/* Disease Status */}
                {(() => {
                  const d = diseaseMap[selectedCompany?.name];
                  if (!d || d.total === 0) return (
                    <div className="p-3 rounded-xl bg-emerald-500/[0.06] border border-emerald-500/20">
                      <span className="text-xs text-emerald-400 font-medium flex items-center gap-2">
                        <Shield className="w-3.5 h-3.5" /> No active disease outbreaks
                      </span>
                    </div>
                  );
                  return (
                    <div className="p-3 rounded-xl bg-rose-500/[0.06] border border-rose-500/20 space-y-1">
                      <span className="text-xs text-rose-400 font-semibold flex items-center gap-2">
                        <AlertTriangle className="w-3.5 h-3.5" /> {d.total} Active Disease Outbreak{d.total > 1 ? "s" : ""}
                      </span>
                      <div className="flex gap-3 text-[10px]">
                        {d.isa > 0 && <span className="text-rose-400 font-bold">{d.isa} ISA</span>}
                        {d.pd > 0 && <span className="text-orange-400 font-bold">{d.pd} PD</span>}
                        {d.other > 0 && <span className="text-amber-400 font-bold">{d.other} Other</span>}
                      </div>
                      {d.localities?.length > 0 && (
                        <p className="text-[10px] text-[var(--text-secondary)]">
                          Affected: {d.localities.slice(0, 5).join(", ")}{d.localities.length > 5 ? ` +${d.localities.length - 5} more` : ""}
                        </p>
                      )}
                    </div>
                  );
                })()}

                {/* Lice Sparkline */}
                {(selectedCompany.lice_sparkline?.length > 0 || selectedCompany.lice_prediction?.length > 0) && (
                  <div>
                    <h3 className="text-sm font-semibold mb-2">
                      Lice Trend — Historical + 4-Week Prediction
                    </h3>
                    <div className="p-4 rounded-xl bg-white/[0.03] border border-white/[0.06]">
                      <div className="flex items-center justify-between mb-3">
                        <div className="space-y-1">
                          <span className="text-xs text-[var(--text-secondary)]">Avg: {selectedCompany.avg_lice != null ? formatNumber(selectedCompany.avg_lice, locale, 3) : "\u2014"}</span>
                          <span className="text-xs text-[var(--text-secondary)] block">Max: {selectedCompany.max_lice != null ? formatNumber(selectedCompany.max_lice, locale, 3) : "\u2014"}</span>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="flex items-center gap-1 text-[10px] text-[var(--text-secondary)]">
                            <span className="w-4 h-[2px] bg-[#00D4C8] rounded-full inline-block" /> Actual
                          </span>
                          <span className="flex items-center gap-1 text-[10px] text-[var(--text-secondary)]">
                            <span className="w-4 h-[2px] bg-[#F59E0B] rounded-full inline-block opacity-70" /> Predicted
                          </span>
                          <span className={`text-xs font-semibold px-2 py-0.5 rounded-md border ${riskColors[selectedCompany.risk_level]}`}>
                            {selectedCompany.risk_level}
                          </span>
                        </div>
                      </div>
                      <DualSparkline
                        historical={selectedCompany.lice_sparkline}
                        predicted={selectedCompany.lice_prediction || []}
                      />
                    </div>
                  </div>
                )}



              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Opt-In Modal */}
      <AnimatePresence>
        {showOptIn && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-black/60 backdrop-blur-xs"
            onClick={() => setShowOptIn(false)}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="relative w-full max-w-md rounded-2xl bg-[rgba(6,15,28,0.95)] backdrop-blur-2xl border border-white/[0.08] shadow-[0_24px_80px_rgba(0,0,0,0.5)] p-6"
              onClick={e => e.stopPropagation()}
            >
              <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-ocean-500/60 via-violet-400/30 to-transparent" />
              <button onClick={() => setShowOptIn(false)} className="absolute top-4 right-4 p-2 rounded-xl bg-white/[0.04] hover:bg-white/[0.08]">
                <X className="w-4 h-4 text-[var(--text-secondary)]" />
              </button>

              <div className="text-center mb-6">
                <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-ocean-500/20 to-violet-500/20 border border-ocean-500/20 flex items-center justify-center mx-auto mb-3">
                  <Star className="w-7 h-7 text-amber-400" />
                </div>
                <h3 className="text-lg font-bold">Personalised Benchmark Report</h3>
                <p className="text-xs text-[var(--text-secondary)] mt-1">
                  See how your company ranks against peers with detailed simulations
                </p>
              </div>

              <div className="space-y-3">
                <input
                  type="text"
                  placeholder="Company Name"
                  className="w-full px-4 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.08] text-sm focus:outline-hidden focus:border-ocean-500/30 transition-colors placeholder:text-[var(--text-secondary)]"
                />
                <input
                  type="email"
                  placeholder="Email Address"
                  className="w-full px-4 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.08] text-sm focus:outline-hidden focus:border-ocean-500/30 transition-colors placeholder:text-[var(--text-secondary)]"
                />
                <input
                  type="text"
                  placeholder="Your Role (CEO, Production Manager, etc.)"
                  className="w-full px-4 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.08] text-sm focus:outline-hidden focus:border-ocean-500/30 transition-colors placeholder:text-[var(--text-secondary)]"
                />
                <OcButton
                  variant="primary"
                  size="lg"
                  className="w-full"
                  onClick={() => setShowOptIn(false)}
                  rightIcon={<ArrowUpRight className="w-4 h-4" />}
                >
                  Request Free Report
                </OcButton>
                <p className="text-[10px] text-[var(--text-secondary)] text-center">
                  We will send a personalised benchmark report within 48 hours.
                  Your data remains confidential and is never shared.
                </p>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Disclaimer */}
      <p className="text-[10px] text-[var(--text-secondary)] text-center opacity-60">
        Rankings based on publicly available data from BarentsWatch (NLOD 2.0), Directorate of Fisheries, and Mattilsynet.
        Production volumes estimated from locality data. Disease data from Norwegian Food Safety Authority. Not financial advice.
      </p>
    </div>
  );
}

export default function LeadersPage() {
  return (
    <Suspense>
      <LeadersPageInner />
    </Suspense>
  );
}
