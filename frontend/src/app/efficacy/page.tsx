"use client";
import { useEffect, useState } from "react";
import { useTranslation } from "@/lib/i18n";
import { motion } from "framer-motion";
import {
  FlaskConical, BarChart3, MapPin, CalendarDays,
  Loader2, Users, TrendingUp, Shield, AlertTriangle,
  ArrowRight, ChevronDown,
} from "lucide-react";
import KPICard from "@/components/KPICard";
import GlassCard from "@/components/GlassCard";
import DataQualityBadge from "@/components/DataQualityBadge";
import { OcButton } from "@/components/ui/Button";
import { api } from "@/lib/api";
import Link from "next/link";
import ErrorBoundary from "@/components/ErrorBoundary";

/* eslint-disable @typescript-eslint/no-explicit-any */

const METHODS_COLORS: Record<string, string> = {
  mechanical: "bg-ocean-500",
  freshwater: "bg-sky-500",
  medicinal: "bg-amber-500",
  thermal: "bg-rose-500",
  biological: "bg-emerald-500",
};

const METHODS_TEXT: Record<string, string> = {
  mechanical: "text-ocean-400",
  freshwater: "text-sky-400",
  medicinal: "text-amber-400",
  thermal: "text-rose-400",
  biological: "text-emerald-400",
};

function efficacyColor(pct: number): string {
  if (pct >= 80) return "bg-emerald-500";
  if (pct >= 60) return "bg-emerald-400";
  if (pct >= 40) return "bg-amber-400";
  if (pct >= 20) return "bg-orange-400";
  return "bg-rose-400";
}

function efficacyTextColor(pct: number): string {
  if (pct >= 80) return "text-emerald-400";
  if (pct >= 60) return "text-emerald-300";
  if (pct >= 40) return "text-amber-400";
  if (pct >= 20) return "text-orange-400";
  return "text-rose-400";
}

export default function EfficacyMarketplacePage() {
  const { t } = useTranslation();
  const [benchmarks, setBenchmarks] = useState<any>(null);
  const [regional, setRegional] = useState<any>(null);
  const [seasonal, setSeasonal] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"benchmarks" | "regional" | "seasonal">("benchmarks");

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    const [bRes, rRes, sRes] = await Promise.allSettled([
      api.efficacyBenchmarks(),
      api.efficacyByRegion(),
      api.efficacyBySeason(),
    ]);
    if (bRes.status === "fulfilled") setBenchmarks(bRes.value);
    if (rRes.status === "fulfilled") setRegional(rRes.value);
    if (sRes.status === "fulfilled") setSeasonal(sRes.value);
    setLoading(false);
  };

  const totalOutcomes = benchmarks?.total_outcomes || 0;
  const methodCount = benchmarks?.contributing_methods || 0;
  const regionCount = regional?.regions?.length || 0;
  const topMethod = benchmarks?.methods?.[0];

  return (
    <ErrorBoundary fallbackTitle="Efficacy Marketplace error">
    <div className="min-h-screen p-6 space-y-6">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between"
      >
        <div>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-fuchsia-600 flex items-center justify-center shadow-lg shadow-violet-500/20">
              <FlaskConical className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-[var(--text-primary)]">
                {t("efficacy.title")}
              </h1>
              <p className="text-sm text-[var(--text-secondary)]">
                Crowdsourced treatment efficacy database &mdash; anonymized to PA level
              </p>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {benchmarks?.data_provenance && (
            <DataQualityBadge provenance={benchmarks.data_provenance} />
          )}
          <Link href="/farmer-daily">
            <OcButton variant="primary" size="sm">
              <TrendingUp className="w-4 h-4 mr-1" />
              {t("efficacy.contribute")}
            </OcButton>
          </Link>
        </div>
      </motion.div>

      {/* KPI Strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KPICard
          label="Total Outcomes"
          value={loading ? "..." : totalOutcomes.toLocaleString()}
          delta="farmer-reported"
          deltaType="neutral"
          icon={Users}
        />
        <KPICard
          label="Methods Tracked"
          value={loading ? "..." : String(methodCount)}
          delta="treatment types"
          deltaType="neutral"
          icon={FlaskConical}
        />
        <KPICard
          label="Regions Active"
          value={loading ? "..." : String(regionCount)}
          delta="production areas"
          deltaType="neutral"
          icon={MapPin}
        />
        <KPICard
          label="Top Method"
          value={loading ? "..." : topMethod?.method?.replace(/_/g, " ") || "N/A"}
          delta={topMethod ? `${topMethod.avg_reduction_pct}% avg reduction` : "awaiting data"}
          deltaType="positive"
          icon={BarChart3}
        />
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-2 border-b border-white/[0.06] pb-1">
        {([
          { key: "benchmarks", label: t("efficacy.benchmarks"), icon: BarChart3 },
          { key: "regional", label: t("efficacy.by_region"), icon: MapPin },
          { key: "seasonal", label: t("efficacy.by_season"), icon: CalendarDays },
        ] as const).map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`flex items-center gap-2 px-4 py-2 text-sm rounded-t-lg transition-all ${
              activeTab === tab.key
                ? "bg-white/[0.08] text-[var(--text-primary)] border-b-2 border-violet-500"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-white/[0.04]"
            }`}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Loading State */}
      {loading && (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 animate-spin text-violet-400" />
          <span className="ml-3 text-[var(--text-secondary)]">{t("common.loading")}</span>
        </div>
      )}

      {/* Empty State */}
      {!loading && totalOutcomes === 0 && (
        <GlassCard>
          <div className="text-center py-12">
            <FlaskConical className="w-16 h-16 mx-auto mb-4 text-violet-400/40" />
            <h2 className="text-xl font-semibold text-[var(--text-primary)] mb-2">
              {t("common.no_data")}
            </h2>
            <p className="text-[var(--text-secondary)] max-w-md mx-auto mb-6">
              No treatment outcomes have been logged yet. When farmers log treatments on the
              Daily Check page, anonymized efficacy data appears here &mdash; building the
              industry&apos;s first crowdsourced treatment database.
            </p>
            <Link href="/farmer-daily">
              <OcButton variant="primary">
                Log Your First Treatment <ArrowRight className="w-4 h-4 ml-1" />
              </OcButton>
            </Link>
          </div>
        </GlassCard>
      )}

      {/* Tab Content: Method Benchmarks */}
      {!loading && activeTab === "benchmarks" && totalOutcomes > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {benchmarks?.methods?.map((m: any) => (
            <motion.div
              key={m.method}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
            >
              <GlassCard>
                <div className="space-y-4">
                  {/* Method Header */}
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className={`w-3 h-3 rounded-full ${METHODS_COLORS[m.method] || "bg-gray-500"}`} />
                      <span className="font-semibold text-[var(--text-primary)]">
                        {m.label || m.method}
                      </span>
                    </div>
                    <span className="text-xs text-[var(--text-secondary)] bg-white/[0.06] px-2 py-0.5 rounded-full">
                      {t("efficacy.sample_size")}: {m.sample_size}
                    </span>
                  </div>

                  {/* Reduction Bar */}
                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-[var(--text-secondary)]">{t("efficacy.reduction_pct")}</span>
                      <span className={efficacyTextColor(m.avg_reduction_pct)}>
                        {m.avg_reduction_pct}%
                      </span>
                    </div>
                    <div className="h-3 bg-white/[0.06] rounded-full overflow-hidden">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${Math.min(100, m.avg_reduction_pct)}%` }}
                        transition={{ duration: 0.8, ease: "easeOut" }}
                        className={`h-full rounded-full ${efficacyColor(m.avg_reduction_pct)}`}
                      />
                    </div>
                  </div>

                  {/* Baseline Comparison */}
                  {m.baseline_success_pct > 0 && (
                    <div className="flex items-center gap-2 text-xs">
                      <span className="text-[var(--text-secondary)]">vs Baseline:</span>
                      <span className={m.vs_baseline_delta >= 0 ? "text-emerald-400" : "text-rose-400"}>
                        {m.vs_baseline_delta >= 0 ? "+" : ""}{m.vs_baseline_delta}%
                      </span>
                      <span className="text-[var(--text-secondary)]">
                        (baseline: {m.baseline_success_pct}%)
                      </span>
                    </div>
                  )}

                  {/* Stats Grid */}
                  <div className="grid grid-cols-3 gap-2 pt-2 border-t border-white/[0.06]">
                    <div className="text-center">
                      <div className="text-xs text-[var(--text-secondary)]">Avg Cost</div>
                      <div className="text-sm font-medium text-[var(--text-primary)]">
                        {m.avg_cost_nok ? `${m.avg_cost_nok.toLocaleString()} NOK` : "N/A"}
                      </div>
                    </div>
                    <div className="text-center">
                      <div className="text-xs text-[var(--text-secondary)]">Mortality</div>
                      <div className="text-sm font-medium text-[var(--text-primary)]">
                        {m.avg_mortality}
                      </div>
                    </div>
                    <div className="text-center">
                      <div className="text-xs text-[var(--text-secondary)]">Resistance</div>
                      <div className={`text-sm font-medium ${
                        m.resistance_risk === "high" ? "text-rose-400" :
                        m.resistance_risk === "medium" ? "text-amber-400" :
                        "text-emerald-400"
                      }`}>
                        {m.resistance_risk || "unknown"}
                      </div>
                    </div>
                  </div>
                </div>
              </GlassCard>
            </motion.div>
          ))}
        </div>
      )}

      {/* Tab Content: Regional Heatmap */}
      {!loading && activeTab === "regional" && totalOutcomes > 0 && (
        <GlassCard>
          <h3 className="text-lg font-semibold text-[var(--text-primary)] mb-4 flex items-center gap-2">
            <MapPin className="w-5 h-5 text-violet-400" />
            Production Area x Method Efficacy
          </h3>
          {regional?.matrix?.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/[0.08]">
                    <th className="text-left py-2 px-3 text-[var(--text-secondary)]">PA</th>
                    <th className="text-left py-2 px-3 text-[var(--text-secondary)]">Method</th>
                    <th className="text-center py-2 px-3 text-[var(--text-secondary)]">n</th>
                    <th className="text-center py-2 px-3 text-[var(--text-secondary)]">Reduction %</th>
                    <th className="text-center py-2 px-3 text-[var(--text-secondary)]">Avg Cost</th>
                    <th className="text-center py-2 px-3 text-[var(--text-secondary)]">Mortality</th>
                  </tr>
                </thead>
                <tbody>
                  {regional.matrix.map((cell: any, idx: number) => (
                    <tr
                      key={idx}
                      className="border-b border-white/[0.04] hover:bg-white/[0.03] transition-colors"
                    >
                      <td className="py-2 px-3 font-medium text-[var(--text-primary)]">
                        PA {cell.production_area}
                      </td>
                      <td className="py-2 px-3">
                        <div className="flex items-center gap-2">
                          <span className={`w-2 h-2 rounded-full ${METHODS_COLORS[cell.method] || "bg-gray-500"}`} />
                          <span className="text-[var(--text-primary)] capitalize">{cell.method}</span>
                        </div>
                      </td>
                      <td className="py-2 px-3 text-center text-[var(--text-secondary)]">{cell.n}</td>
                      <td className="py-2 px-3 text-center">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                          cell.avg_reduction_pct >= 70 ? "bg-emerald-500/15 text-emerald-400" :
                          cell.avg_reduction_pct >= 40 ? "bg-amber-500/15 text-amber-400" :
                          "bg-rose-500/15 text-rose-400"
                        }`}>
                          {cell.avg_reduction_pct}%
                        </span>
                      </td>
                      <td className="py-2 px-3 text-center text-[var(--text-secondary)]">
                        {cell.avg_cost_nok ? `${cell.avg_cost_nok.toLocaleString()}` : "N/A"}
                      </td>
                      <td className="py-2 px-3 text-center text-[var(--text-secondary)]">
                        {cell.avg_mortality}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-[var(--text-secondary)] text-center py-8">
              Not enough regional data yet. Need at least 3 outcomes per PA/method combination.
            </p>
          )}
          {regional?.cells_suppressed > 0 && (
            <p className="text-xs text-[var(--text-secondary)] mt-3 flex items-center gap-1">
              <Shield className="w-3 h-3" />
              {regional.cells_suppressed} cell(s) suppressed for privacy (fewer than 3 outcomes).
            </p>
          )}
        </GlassCard>
      )}

      {/* Tab Content: Seasonal Patterns */}
      {!loading && activeTab === "seasonal" && totalOutcomes > 0 && (
        <GlassCard>
          <h3 className="text-lg font-semibold text-[var(--text-primary)] mb-4 flex items-center gap-2">
            <CalendarDays className="w-5 h-5 text-violet-400" />
            Monthly Efficacy Patterns
          </h3>
          {seasonal?.matrix?.length > 0 ? (
            <div className="space-y-3">
              {seasonal.monthly.map((month: any) => (
                <div key={month.month} className="border-b border-white/[0.04] pb-3 last:border-0">
                  <div className="flex items-center gap-3 mb-2">
                    <span className="text-sm font-medium text-[var(--text-primary)] w-12">
                      {month.month_name}
                    </span>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-violet-500/15 text-violet-300 capitalize">
                      {month.season}
                    </span>
                    <span className="text-xs text-[var(--text-secondary)]">
                      {month.total_n} outcome{month.total_n !== 1 ? "s" : ""}
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-3 ml-16">
                    {month.methods.map((mc: any) => (
                      <div
                        key={`${month.month}-${mc.method}`}
                        className="flex items-center gap-2 bg-white/[0.04] rounded-lg px-3 py-1.5"
                      >
                        <span className={`w-2 h-2 rounded-full ${METHODS_COLORS[mc.method] || "bg-gray-500"}`} />
                        <span className="text-xs text-[var(--text-secondary)] capitalize">{mc.method}</span>
                        <span className={`text-xs font-medium ${efficacyTextColor(mc.avg_reduction_pct)}`}>
                          {mc.avg_reduction_pct}%
                        </span>
                        <span className="text-[10px] text-[var(--text-secondary)]">n={mc.n}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-[var(--text-secondary)] text-center py-8">
              Not enough seasonal data yet. Need at least 3 outcomes per month/method combination.
            </p>
          )}
          {seasonal?.cells_suppressed > 0 && (
            <p className="text-xs text-[var(--text-secondary)] mt-3 flex items-center gap-1">
              <Shield className="w-3 h-3" />
              {seasonal.cells_suppressed} cell(s) suppressed for privacy (fewer than 3 outcomes).
            </p>
          )}
        </GlassCard>
      )}

      {/* Privacy Notice + Contribute CTA */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <GlassCard>
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/15 flex items-center justify-center flex-shrink-0">
              <Shield className="w-4 h-4 text-emerald-400" />
            </div>
            <div>
              <h4 className="text-sm font-semibold text-[var(--text-primary)] mb-1">
                Privacy &amp; Anonymization
              </h4>
              <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                All data is anonymized to Production Area level. Individual locality outcomes
                are never exposed. Aggregation cells with fewer than 3 data points are
                suppressed to prevent re-identification. Only PA-level granularity is shown.
              </p>
            </div>
          </div>
        </GlassCard>

        <GlassCard>
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-lg bg-violet-500/15 flex items-center justify-center flex-shrink-0">
              <Users className="w-4 h-4 text-violet-400" />
            </div>
            <div>
              <h4 className="text-sm font-semibold text-[var(--text-primary)] mb-1">
                Contribute to the Database
              </h4>
              <p className="text-xs text-[var(--text-secondary)] leading-relaxed mb-2">
                Every treatment outcome you log improves the intelligence for everyone.
                The more data, the better the benchmarks become.
              </p>
              <Link href="/farmer-daily">
                <OcButton variant="ghost" size="sm">
                  Go to Daily Check <ArrowRight className="w-3 h-3 ml-1" />
                </OcButton>
              </Link>
            </div>
          </div>
        </GlassCard>
      </div>
    </div>
    </ErrorBoundary>
  );
}
