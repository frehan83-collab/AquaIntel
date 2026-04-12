"use client";
import { useEffect, useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  GitCompare, Trophy, Search, X, Bug, Shield, Leaf,
  Factory, BarChart3, Zap, TrendingUp, TrendingDown, Minus,
  ChevronDown, AlertTriangle,
} from "lucide-react";
import KPICard from "@/components/KPICard";
import GlassCard from "@/components/GlassCard";
import { OcButton } from "@/components/ui/Button";
import DataQualityBadge from "@/components/DataQualityBadge";
import RadarChart, { RadarDataset } from "@/components/RadarChart";
import { api } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";
import ErrorBoundary from "@/components/ErrorBoundary";
import { useApiError } from "@/lib/useApiError";

/* eslint-disable @typescript-eslint/no-explicit-any */

const COMPANY_COLORS = ["#00D4C8", "#F59E0B", "#A78BFA"];
const MAX_COMPANIES = 3;

function WinnerBadge({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center gap-1 text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/20">
      <Trophy className="w-2.5 h-2.5" /> {label}
    </span>
  );
}

function MetricRow({
  label,
  icon: Icon,
  values,
  format,
  lowerIsBetter = false,
}: {
  label: string;
  icon: any;
  values: (number | null | undefined)[];
  format: (v: number) => string;
  lowerIsBetter?: boolean;
}) {
  const validValues = values.map((v) => (v != null && !isNaN(v) ? v : null));
  const numericVals = validValues.filter((v): v is number => v !== null);
  const bestVal =
    numericVals.length > 0
      ? lowerIsBetter
        ? Math.min(...numericVals)
        : Math.max(...numericVals)
      : null;

  return (
    <div className="grid items-center gap-4 py-3 border-b border-white/[0.04]" style={{ gridTemplateColumns: `180px repeat(${values.length}, 1fr)` }}>
      <div className="flex items-center gap-2">
        <Icon className="w-4 h-4 text-ocean-400/60" />
        <span className="text-xs font-medium text-[var(--text-secondary)]">{label}</span>
      </div>
      {validValues.map((v, i) => (
        <div key={i} className="flex items-center gap-2">
          <span className="text-sm font-mono font-semibold tabular-nums">
            {v !== null ? format(v) : "--"}
          </span>
          {v !== null && v === bestVal && numericVals.length > 1 && <WinnerBadge label="Best" />}
        </div>
      ))}
    </div>
  );
}

function CompanySelector({
  index,
  selected,
  companies,
  onSelect,
  onClear,
  color,
}: {
  index: number;
  selected: any | null;
  companies: any[];
  onSelect: (co: any) => void;
  onClear: () => void;
  color: string;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");

  const filtered = useMemo(
    () =>
      companies.filter(
        (c) =>
          c.name.toLowerCase().includes(search.toLowerCase()) ||
          (c.ticker && c.ticker.toLowerCase().includes(search.toLowerCase()))
      ),
    [companies, search]
  );

  return (
    <div className="relative">
      {selected ? (
        <div
          className="flex items-center gap-3 px-4 py-3 rounded-xl border border-white/[0.08] bg-white/[0.03] cursor-pointer hover:bg-white/[0.05] transition-colors"
          style={{ borderLeftColor: color, borderLeftWidth: 3 }}
        >
          <div className="flex-1 min-w-0">
            <div className="font-semibold text-sm truncate">{selected.name}</div>
            <div className="text-[10px] text-[var(--text-secondary)]">
              {selected.ticker ? selected.ticker + " · " : ""}
              {selected.n_localities} sites · PA {selected.production_areas?.join(", ") || "N/A"}
            </div>
          </div>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onClear();
            }}
            className="p-1 rounded hover:bg-white/[0.08] transition-colors"
            aria-label="Remove company"
          >
            <X className="w-3.5 h-3.5 text-[var(--text-secondary)]" />
          </button>
        </div>
      ) : (
        <button
          onClick={() => setOpen(!open)}
          className="w-full flex items-center gap-3 px-4 py-3 rounded-xl border border-dashed border-white/[0.12] bg-white/[0.02] hover:bg-white/[0.04] hover:border-white/[0.2] transition-colors text-left"
          aria-label={`Select company ${index + 1}`}
        >
          <div
            className="w-3 h-3 rounded-full opacity-50"
            style={{ backgroundColor: color }}
          />
          <span className="text-sm text-[var(--text-secondary)]">
            Select company {index + 1}...
          </span>
          <ChevronDown className="w-4 h-4 text-[var(--text-secondary)] ml-auto" />
        </button>
      )}

      <AnimatePresence>
        {open && !selected && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.15 }}
            className="absolute top-full mt-1 left-0 right-0 z-50 bg-fjord-surface/98 border border-white/[0.1] rounded-xl shadow-2xl overflow-hidden"
          >
            <div className="p-2 border-b border-white/[0.06]">
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--text-secondary)]" />
                <input
                  type="text"
                  placeholder="Search companies..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  autoFocus
                  className="w-full pl-8 pr-3 py-1.5 bg-white/[0.04] border border-white/[0.06] rounded-lg text-xs focus:outline-none focus:border-ocean-500/30"
                />
              </div>
            </div>
            <div className="max-h-48 overflow-y-auto">
              {filtered.length === 0 ? (
                <div className="px-3 py-4 text-xs text-[var(--text-secondary)] text-center">
                  No companies found
                </div>
              ) : (
                filtered.slice(0, 20).map((co) => (
                  <button
                    key={co.name}
                    onClick={() => {
                      onSelect(co);
                      setOpen(false);
                      setSearch("");
                    }}
                    className="w-full flex items-center gap-3 px-3 py-2 text-left hover:bg-white/[0.05] transition-colors"
                    aria-label={`Select ${co.name}`}
                  >
                    <span className="text-[10px] font-mono text-[var(--text-secondary)] w-6 text-right">
                      #{co.rank}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-medium truncate">{co.name}</div>
                      <div className="text-[10px] text-[var(--text-secondary)]">
                        Lice: {co.avg_lice?.toFixed(3)} · Score: {co.performance_score?.toFixed(0)}
                      </div>
                    </div>
                    {co.ticker && (
                      <span className="text-[9px] px-1 py-0.5 rounded bg-ocean-500/10 text-ocean-400">
                        {co.ticker}
                      </span>
                    )}
                  </button>
                ))
              )}
            </div>
            <button
              onClick={() => {
                setOpen(false);
                setSearch("");
              }}
              className="w-full px-3 py-2 text-[10px] text-[var(--text-secondary)] hover:bg-white/[0.04] border-t border-white/[0.06]"
              aria-label="Cancel company selection"
            >
              Cancel
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/** Normalize a metric to 0-1 scale for radar chart */
function normalize(val: number, min: number, max: number, invert = false): number {
  if (max === min) return 0.5;
  const norm = (val - min) / (max - min);
  return invert ? 1 - Math.max(0, Math.min(1, norm)) : Math.max(0, Math.min(1, norm));
}

export default function ComparePage() {
  const { t } = useTranslation();
  const handleError = useApiError();
  const [allCompanies, setAllCompanies] = useState<any[]>([]);
  const [diseaseMap, setDiseaseMap] = useState<Record<string, any>>({});
  const [esgCache, setEsgCache] = useState<Record<string, any>>({});
  const [selected, setSelected] = useState<(any | null)[]>([null, null, null]);
  const [loading, setLoading] = useState(true);

  // Load companies + disease data
  useEffect(() => {
    setLoading(true);
    Promise.allSettled([
      api.leadersTop30(),
      api.diseaseByCompany(),
    ]).then(([cRes, dRes]) => {
      if (cRes.status === "fulfilled") setAllCompanies(cRes.value || []);
      if (dRes.status === "fulfilled" && dRes.value && typeof dRes.value === "object")
        setDiseaseMap(dRes.value);
      setLoading(false);
    });
  }, []);

  // Load ESG data for selected companies
  useEffect(() => {
    const names = selected.filter(Boolean).map((c: any) => c.name);
    const missing = names.filter((n: string) => !esgCache[n]);
    if (missing.length === 0) return;
    missing.forEach((name: string) => {
      api.esgCompany(name).then((data: any) => {
        setEsgCache((prev) => ({ ...prev, [name]: data }));
      }).catch(handleError("compare_esg_company"));
    });
  }, [selected]);

  const activeCompanies = selected.filter(Boolean);
  const companyCount = activeCompanies.length;

  // Available companies (exclude already selected)
  const selectedNames = new Set(selected.filter(Boolean).map((c: any) => c.name));
  const availableCompanies = allCompanies.filter((c) => !selectedNames.has(c.name));

  // Compute ranges for normalization
  const ranges = useMemo(() => {
    if (allCompanies.length === 0) return null;
    return {
      lice: {
        min: Math.min(...allCompanies.map((c) => c.avg_lice || 0)),
        max: Math.max(...allCompanies.map((c) => c.avg_lice || 0)),
      },
      score: {
        min: Math.min(...allCompanies.map((c) => c.performance_score || 0)),
        max: Math.max(...allCompanies.map((c) => c.performance_score || 0)),
      },
      production: {
        min: Math.min(...allCompanies.map((c) => c.production_volume_tonnes || 0)),
        max: Math.max(...allCompanies.map((c) => c.production_volume_tonnes || 0)),
      },
    };
  }, [allCompanies]);

  // Build radar chart data
  const radarLabels = ["Lice Control", "ESG Score", "Production", "Disease Resilience", "Treatment Eff."];
  const radarDatasets: RadarDataset[] = useMemo(() => {
    if (!ranges || companyCount < 2) return [];
    return activeCompanies.map((co: any, i: number) => {
      const esg = esgCache[co.name];
      const disease = diseaseMap[co.name];
      const diseaseTotal = disease?.total || 0;

      // Lice: lower is better, invert
      const liceScore = normalize(co.avg_lice || 0, ranges.lice.min, ranges.lice.max, true);
      // ESG: higher is better
      const esgScore = esg?.total_score ? normalize(esg.total_score, 0, 100) : 0.5;
      // Production: higher is better
      const prodScore = normalize(co.production_volume_tonnes || 0, ranges.production.min, ranges.production.max);
      // Disease resilience: fewer disease events is better, invert
      const diseaseScore = normalize(diseaseTotal, 0, 10, true);
      // Treatment efficiency: based on outlook index (proxy)
      const treatScore = normalize(co.outlook_index || 50, 0, 100);

      return {
        name: co.name,
        values: [liceScore, esgScore, prodScore, diseaseScore, treatScore],
        color: COMPANY_COLORS[i],
      };
    });
  }, [activeCompanies, ranges, esgCache, diseaseMap, companyCount]);

  const setCompanyAt = (index: number, co: any | null) => {
    setSelected((prev) => {
      const next = [...prev];
      next[index] = co;
      return next;
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-ocean-500" />
      </div>
    );
  }

  return (
    <ErrorBoundary fallbackTitle="Company Comparison error">
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight flex items-center gap-3">
          <GitCompare className="w-6 h-6 text-ocean-400" />
          {t("compare.title")}
        </h1>
        <p className="text-sm text-[var(--text-secondary)] mt-1">
          Compare 2-3 salmon producers side by side across biological, ESG, and operational metrics
        </p>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard label="Companies Available" value={allCompanies.length} icon={Factory} delay={0} />
        <KPICard label="Comparing" value={companyCount} icon={GitCompare} delay={0.03} />
        <KPICard
          label="Best Lice Score"
          value={
            companyCount > 0
              ? Math.min(...activeCompanies.map((c: any) => c.avg_lice || 99)).toFixed(3)
              : "--"
          }
          icon={Bug}
          delay={0.06}
        />
        <KPICard
          label="Best Overall"
          value={
            companyCount > 0
              ? Math.max(...activeCompanies.map((c: any) => c.performance_score || 0)).toFixed(0)
              : "--"
          }
          icon={Trophy}
          delay={0.09}
        />
      </div>

      {/* Company Selectors */}
      <GlassCard delay={0.1} aria-label="Company selectors">
        <div className="flex items-center gap-2 mb-4">
          <Search className="w-4 h-4 text-ocean-400" />
          <h2 className="text-sm font-semibold">{t("compare.select_companies")}</h2>
          <span className="text-[10px] text-[var(--text-secondary)] ml-auto">
            {companyCount}/{MAX_COMPANIES} selected
          </span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {[0, 1, 2].map((i) => (
            <CompanySelector
              key={i}
              index={i}
              selected={selected[i]}
              companies={availableCompanies}
              onSelect={(co) => setCompanyAt(i, co)}
              onClear={() => setCompanyAt(i, null)}
              color={COMPANY_COLORS[i]}
            />
          ))}
        </div>
      </GlassCard>

      {/* Comparison Content */}
      {companyCount >= 2 && (
        <>
          {/* Radar Chart */}
          <GlassCard delay={0.15} aria-label="Radar comparison chart">
            <h2 className="text-sm font-semibold mb-4 flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-ocean-400" />
              {t("compare.radar_chart")}
            </h2>
            <div className="flex justify-center">
              <RadarChart
                labels={radarLabels}
                datasets={radarDatasets}
                size={340}
              />
            </div>
            <p className="text-[10px] text-[var(--text-secondary)] text-center mt-2">
              Values normalized against all {allCompanies.length} companies in the leaders dataset. Higher is better.
            </p>
          </GlassCard>

          {/* Side-by-side Metrics */}
          <GlassCard delay={0.2} aria-label="Detailed metric comparison">
            <h2 className="text-sm font-semibold mb-4 flex items-center gap-2">
              <Zap className="w-4 h-4 text-amber-400" />
              Metric-by-Metric Comparison
            </h2>

            {/* Column headers */}
            <div
              className="grid items-center gap-4 pb-2 border-b border-white/[0.08]"
              style={{ gridTemplateColumns: `180px repeat(${companyCount}, 1fr)` }}
            >
              <div className="text-[10px] text-[var(--text-secondary)] uppercase tracking-wider font-semibold">
                Metric
              </div>
              {activeCompanies.map((co: any, i: number) => (
                <div key={co.name} className="flex items-center gap-2">
                  <span
                    className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                    style={{ backgroundColor: COMPANY_COLORS[i] }}
                  />
                  <span className="text-xs font-semibold truncate">{co.name}</span>
                </div>
              ))}
            </div>

            {/* Biological Metrics */}
            <div className="mt-2">
              <div className="text-[10px] text-ocean-400 uppercase tracking-wider font-semibold mb-1 mt-3">
                Biological Performance
              </div>
              <MetricRow
                label="Avg Lice (adult female)"
                icon={Bug}
                values={activeCompanies.map((c: any) => c.avg_lice)}
                format={(v) => v.toFixed(3)}
                lowerIsBetter
              />
              <MetricRow
                label="Performance Score"
                icon={Trophy}
                values={activeCompanies.map((c: any) => c.performance_score)}
                format={(v) => v.toFixed(1)}
              />
              <MetricRow
                label="12-Week Outlook"
                icon={TrendingUp}
                values={activeCompanies.map((c: any) => c.outlook_index)}
                format={(v) => v.toFixed(0)}
              />
              <MetricRow
                label="Risk Level Score"
                icon={AlertTriangle}
                values={activeCompanies.map((c: any) => {
                  const riskMap: Record<string, number> = { LOW: 25, MEDIUM: 50, HIGH: 75, CRITICAL: 100 };
                  return riskMap[c.risk_level] || 50;
                })}
                format={(v) => {
                  if (v <= 25) return "LOW";
                  if (v <= 50) return "MEDIUM";
                  if (v <= 75) return "HIGH";
                  return "CRITICAL";
                }}
                lowerIsBetter
              />
            </div>

            {/* ESG Metrics */}
            <div className="mt-2">
              <div className="text-[10px] text-emerald-400 uppercase tracking-wider font-semibold mb-1 mt-3">
                ESG Sustainability
              </div>
              <MetricRow
                label="Environmental (E)"
                icon={Leaf}
                values={activeCompanies.map((c: any) => esgCache[c.name]?.environmental)}
                format={(v) => v.toFixed(1)}
              />
              <MetricRow
                label="Social (S)"
                icon={Shield}
                values={activeCompanies.map((c: any) => esgCache[c.name]?.social)}
                format={(v) => v.toFixed(1)}
              />
              <MetricRow
                label="Governance (G)"
                icon={Shield}
                values={activeCompanies.map((c: any) => esgCache[c.name]?.governance)}
                format={(v) => v.toFixed(1)}
              />
              <MetricRow
                label="Total ESG Score"
                icon={BarChart3}
                values={activeCompanies.map((c: any) => esgCache[c.name]?.total_score)}
                format={(v) => v.toFixed(1)}
              />
            </div>

            {/* Operational Metrics */}
            <div className="mt-2">
              <div className="text-[10px] text-amber-400 uppercase tracking-wider font-semibold mb-1 mt-3">
                Operational Scale
              </div>
              <MetricRow
                label="Production Volume"
                icon={Factory}
                values={activeCompanies.map((c: any) => c.production_volume_tonnes)}
                format={(v) =>
                  v >= 1000 ? `${(v / 1000).toFixed(1)}k t` : `${v.toFixed(0)} t`
                }
              />
              <MetricRow
                label="Farm Count"
                icon={Factory}
                values={activeCompanies.map((c: any) => c.n_localities)}
                format={(v) => v.toFixed(0)}
              />
              <MetricRow
                label="Lice Records"
                icon={BarChart3}
                values={activeCompanies.map((c: any) => c.n_lice_records)}
                format={(v) => v.toLocaleString()}
              />
              <MetricRow
                label="Production Areas"
                icon={BarChart3}
                values={activeCompanies.map((c: any) => c.production_areas?.length || 0)}
                format={(v) => v.toFixed(0)}
              />
            </div>

            {/* Disease Status */}
            <div className="mt-2">
              <div className="text-[10px] text-rose-400 uppercase tracking-wider font-semibold mb-1 mt-3">
                Disease Status
              </div>
              <MetricRow
                label="Total Disease Events"
                icon={Shield}
                values={activeCompanies.map((c: any) => diseaseMap[c.name]?.total || 0)}
                format={(v) => v.toFixed(0)}
                lowerIsBetter
              />
              <MetricRow
                label="ISA Cases"
                icon={AlertTriangle}
                values={activeCompanies.map((c: any) => diseaseMap[c.name]?.isa || 0)}
                format={(v) => v.toFixed(0)}
                lowerIsBetter
              />
              <MetricRow
                label="PD Cases"
                icon={AlertTriangle}
                values={activeCompanies.map((c: any) => diseaseMap[c.name]?.pd || 0)}
                format={(v) => v.toFixed(0)}
                lowerIsBetter
              />
            </div>
          </GlassCard>

          {/* Company Detail Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {activeCompanies.map((co: any, i: number) => {
              const esg = esgCache[co.name];
              const disease = diseaseMap[co.name];
              return (
                <GlassCard key={co.name} delay={0.25 + i * 0.05} accent={i === 0 ? "ocean" : i === 1 ? "amber" : "violet"}>
                  <div className="flex items-center gap-2 mb-3">
                    <span
                      className="w-3 h-3 rounded-full flex-shrink-0"
                      style={{ backgroundColor: COMPANY_COLORS[i] }}
                    />
                    <h3 className="text-sm font-bold truncate">{co.name}</h3>
                    {co.ticker && (
                      <span className="text-[9px] px-1.5 py-0.5 rounded bg-ocean-500/10 text-ocean-400 border border-ocean-500/20">
                        {co.ticker}
                      </span>
                    )}
                  </div>

                  {/* Quick stats */}
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <span className="text-[var(--text-secondary)]">Rank</span>
                      <div className="font-mono font-bold">#{co.rank}</div>
                    </div>
                    <div>
                      <span className="text-[var(--text-secondary)]">Avg Lice</span>
                      <div className={`font-mono font-bold ${co.avg_lice > 0.3 ? "text-rose-400" : co.avg_lice > 0.15 ? "text-amber-400" : "text-emerald-400"}`}>
                        {co.avg_lice?.toFixed(3)}
                      </div>
                    </div>
                    <div>
                      <span className="text-[var(--text-secondary)]">Score</span>
                      <div className="font-mono font-bold">{co.performance_score?.toFixed(0)}</div>
                    </div>
                    <div>
                      <span className="text-[var(--text-secondary)]">Risk</span>
                      <div className={`font-mono font-bold ${
                        co.risk_level === "LOW" ? "text-emerald-400" :
                        co.risk_level === "MEDIUM" ? "text-amber-400" :
                        co.risk_level === "HIGH" ? "text-orange-400" : "text-rose-400"
                      }`}>
                        {co.risk_level}
                      </div>
                    </div>
                    <div>
                      <span className="text-[var(--text-secondary)]">Sites</span>
                      <div className="font-mono font-bold">{co.n_localities}</div>
                    </div>
                    <div>
                      <span className="text-[var(--text-secondary)]">Volume</span>
                      <div className="font-mono font-bold">
                        {co.production_volume_tonnes >= 1000
                          ? `${(co.production_volume_tonnes / 1000).toFixed(1)}k t`
                          : `${co.production_volume_tonnes} t`}
                      </div>
                    </div>
                  </div>

                  {/* ESG Breakdown */}
                  {esg && (
                    <div className="mt-3 pt-3 border-t border-white/[0.06]">
                      <div className="text-[10px] text-[var(--text-secondary)] uppercase tracking-wider font-semibold mb-2">
                        ESG Breakdown
                      </div>
                      <div className="space-y-1.5">
                        {[
                          { label: "Environmental", val: esg.environmental, max: 40 },
                          { label: "Social", val: esg.social, max: 30 },
                          { label: "Governance", val: esg.governance, max: 30 },
                        ].map((bar) => (
                          <div key={bar.label} className="flex items-center gap-2">
                            <span className="text-[10px] text-[var(--text-secondary)] w-20">{bar.label}</span>
                            <div className="flex-1 h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
                              <motion.div
                                className={`h-full rounded-full ${
                                  (bar.val / bar.max) >= 0.7 ? "bg-emerald-400" :
                                  (bar.val / bar.max) >= 0.4 ? "bg-amber-400" : "bg-rose-400"
                                }`}
                                initial={{ width: 0 }}
                                animate={{ width: `${(bar.val / bar.max) * 100}%` }}
                                transition={{ duration: 0.5 }}
                              />
                            </div>
                            <span className="text-[10px] font-mono w-8 text-right">{bar.val?.toFixed(1)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Disease */}
                  <div className="mt-3 pt-3 border-t border-white/[0.06]">
                    <div className="text-[10px] text-[var(--text-secondary)] uppercase tracking-wider font-semibold mb-1">
                      Disease Status
                    </div>
                    {(!disease || disease.total === 0) ? (
                      <span className="text-[10px] text-emerald-400 font-medium">Clear</span>
                    ) : (
                      <div className="flex items-center gap-2 flex-wrap">
                        {disease.isa > 0 && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-rose-500/15 text-rose-400 border border-rose-500/20">
                            ISA: {disease.isa}
                          </span>
                        )}
                        {disease.pd > 0 && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-400 border border-amber-500/20">
                            PD: {disease.pd}
                          </span>
                        )}
                        {disease.other > 0 && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-violet-500/15 text-violet-400 border border-violet-500/20">
                            Other: {disease.other}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </GlassCard>
              );
            })}
          </div>

          {/* Data Source */}
          <div className="flex justify-end">
            <DataQualityBadge
              quality="live"
              source="BarentsWatch + ESG Scorer + Mattilsynet"
            />
          </div>
        </>
      )}

      {/* Empty state when < 2 companies selected */}
      {companyCount < 2 && (
        <GlassCard delay={0.15} accent="none">
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <GitCompare className="w-12 h-12 text-ocean-400/30 mb-4" />
            <h3 className="text-lg font-semibold mb-2">Select at Least 2 Companies</h3>
            <p className="text-sm text-[var(--text-secondary)] max-w-md">
              Use the dropdowns above to pick 2 or 3 salmon producers.
              You will see a radar chart, side-by-side metrics, ESG breakdowns, and disease status.
            </p>
          </div>
        </GlassCard>
      )}
    </div>
    </ErrorBoundary>
  );
}
