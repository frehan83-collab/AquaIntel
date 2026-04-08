"use client";
import { useEffect, useState, useCallback } from "react";
import { useTranslation, formatNumber, formatCurrency } from "@/lib/i18n";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  BriefcaseBusiness, AlertTriangle, ShieldAlert, ShieldCheck, CheckCircle2,
  Loader2, Plus, Search, Thermometer, Fish, Printer,
} from "lucide-react";
import KPICard from "@/components/KPICard";
import GlassCard from "@/components/GlassCard";
import DataQualityBadge from "@/components/DataQualityBadge";
import { OcButton } from "@/components/ui/Button";
import { api } from "@/lib/api";
import ErrorBoundary from "@/components/ErrorBoundary";

/* eslint-disable @typescript-eslint/no-explicit-any */

const RISK_STYLES: Record<string, { bg: string; border: string; text: string; dot: string }> = {
  critical: {
    bg: "bg-rose-500/10 dark:bg-rose-500/15",
    border: "border-rose-500/30",
    text: "text-rose-600 dark:text-rose-400",
    dot: "bg-rose-500",
  },
  high: {
    bg: "bg-amber-500/10 dark:bg-amber-500/15",
    border: "border-amber-500/30",
    text: "text-amber-600 dark:text-amber-400",
    dot: "bg-amber-500",
  },
  moderate: {
    bg: "bg-ocean-500/10 dark:bg-ocean-500/15",
    border: "border-ocean-500/30",
    text: "text-ocean-600 dark:text-ocean-400",
    dot: "bg-ocean-500",
  },
  low: {
    bg: "bg-emerald-500/10 dark:bg-emerald-500/15",
    border: "border-emerald-500/30",
    text: "text-emerald-600 dark:text-emerald-400",
    dot: "bg-emerald-500",
  },
};

const ACTION_ICONS: Record<string, any> = {
  TREAT_NOW: ShieldAlert,
  SCHEDULE_TREATMENT: AlertTriangle,
  MONITOR: ShieldCheck,
  NO_ACTION: CheckCircle2,
};

const ACTION_LABELS: Record<string, string> = {
  TREAT_NOW: "Treat Now",
  SCHEDULE_TREATMENT: "Schedule Treatment",
  MONITOR: "Monitor",
  NO_ACTION: "No Action Needed",
  UNKNOWN: "Unknown",
};

function liceColor(lice: number): string {
  if (lice > 0.5) return "text-rose-600 dark:text-rose-400";
  if (lice > 0.3) return "text-amber-600 dark:text-amber-400";
  if (lice > 0.15) return "text-ocean-600 dark:text-ocean-400";
  return "text-emerald-600 dark:text-emerald-400";
}

function liceBarWidth(lice: number): string {
  const pct = Math.min(100, (lice / 0.7) * 100);
  return `${pct}%`;
}

function liceBarColor(lice: number): string {
  if (lice > 0.5) return "bg-rose-500";
  if (lice > 0.3) return "bg-amber-500";
  if (lice > 0.15) return "bg-ocean-500";
  return "bg-emerald-500";
}

export default function PortfolioPage() {
  const { t, locale } = useTranslation();
  const router = useRouter();
  const [portfolio, setPortfolio] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Read saved farms from localStorage (same key as farmer-daily)
  const [savedFarms, setSavedFarms] = useState<{ locality_no: number; name: string }[]>(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("oc_saved_farms");
      if (saved) {
        try { return JSON.parse(saved); } catch { return []; }
      }
    }
    return [];
  });

  const fetchPortfolio = useCallback(async () => {
    if (savedFarms.length === 0) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const locNos = savedFarms.map(f => f.locality_no);
      const data = await api.farmPortfolio(locNos);
      setPortfolio(data);
    } catch (e: any) {
      setError(e.message || "Failed to load portfolio");
    } finally {
      setLoading(false);
    }
  }, [savedFarms]);

  useEffect(() => {
    fetchPortfolio();
  }, [fetchPortfolio]);

  const navigateToFarm = (localityNo: number) => {
    // Save as last-used locality so farmer-daily picks it up
    const farm = savedFarms.find(f => f.locality_no === localityNo);
    if (farm) {
      localStorage.setItem("oc_last_locality", JSON.stringify(farm));
    }
    router.push("/farmer-daily");
  };

  // Empty state: no saved farms
  if (!loading && savedFarms.length === 0) {
    return (
      <ErrorBoundary>
        <div className="space-y-6">
          <div className="flex items-center gap-3">
            <BriefcaseBusiness className="w-7 h-7 text-salmon" />
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">{t("portfolio.title")}</h1>
          </div>

          <GlassCard>
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <div className="w-16 h-16 rounded-full bg-ocean-500/10 dark:bg-ocean-500/20 flex items-center justify-center mb-4">
                <Search className="w-8 h-8 text-ocean-500" />
              </div>
              <h2 className="text-xl font-semibold text-[var(--text-primary)] mb-2">
                {t("common.no_data")}
              </h2>
              <p className="text-[var(--text-secondary)] max-w-md mb-6">
                Search and save farms to build your portfolio. Get a multi-farm overview
                with lice levels, decision recommendations, and risk assessments at a glance.
              </p>
              <OcButton onClick={() => router.push("/farmer-daily")}>
                <Plus className="w-4 h-4 mr-2" />
                Search &amp; Save Farms
              </OcButton>
            </div>
          </GlassCard>
        </div>
      </ErrorBoundary>
    );
  }

  const summary = portfolio?.summary;
  const farms = portfolio?.farms || [];
  const provenance = portfolio?.data_provenance;

  return (
    <ErrorBoundary>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <BriefcaseBusiness className="w-7 h-7 text-salmon" />
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">{t("portfolio.title")}</h1>
            {summary && (
              <span className="px-2.5 py-0.5 text-sm font-medium rounded-full bg-ocean-500/15 text-ocean-600 dark:text-ocean-400">
                {summary.total_farms} {summary.total_farms === 1 ? "farm" : "farms"}
              </span>
            )}
            {provenance && <DataQualityBadge provenance={provenance} />}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => window.print()}
              className="print:hidden flex items-center gap-1.5 px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:text-ocean-400 bg-white/[0.04] border border-white/[0.08] rounded-lg transition-colors"
              title="Export as PDF"
            >
              <Printer className="w-3.5 h-3.5" /> PDF
            </button>
            <OcButton variant="ghost" onClick={() => router.push("/farmer-daily")}>
              <Plus className="w-4 h-4 mr-1" />
              Add Farm
            </OcButton>
          </div>
        </div>

        {/* Loading state */}
        {loading && (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-8 h-8 text-ocean-500 animate-spin" />
            <span className="ml-3 text-[var(--text-secondary)]">{t("common.loading")}</span>
          </div>
        )}

        {/* Error state */}
        {error && !loading && (
          <GlassCard>
            <div className="text-center py-8">
              <p className="text-rose-500 mb-3">{error}</p>
              <OcButton onClick={fetchPortfolio}>Retry</OcButton>
            </div>
          </GlassCard>
        )}

        {/* Portfolio data */}
        {!loading && !error && summary && (
          <>
            {/* KPI Row */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <KPICard
                label={t("portfolio.risk_overview")}
                value={summary.total_farms}
                icon={BriefcaseBusiness}
              />
              <KPICard
                label={t("portfolio.avg_lice")}
                value={summary.avg_lice_level != null ? formatNumber(summary.avg_lice_level, locale, 3) : "\u2014"}
                icon={Fish}
                delta={summary.avg_lice_level > 0.3 ? "Above trigger" : "Within safe range"}
                deltaType={summary.avg_lice_level > 0.3 ? "negative" : "positive"}
              />
              <KPICard
                label={t("portfolio.farms_needing_treatment")}
                value={summary.farms_needing_treatment}
                icon={AlertTriangle}
                delta={`${formatNumber(summary.risk_breakdown.critical, locale)} critical, ${formatNumber(summary.risk_breakdown.high, locale)} high`}
                deltaType={summary.farms_needing_treatment > 0 ? "negative" : "positive"}
              />
              <KPICard
                label="Actions Needed"
                value={summary.farms_needing_treatment}
                icon={ShieldAlert}
                delta={`${summary.total_farms - summary.farms_needing_treatment} farms OK`}
                deltaType={summary.farms_needing_treatment === 0 ? "positive" : "neutral"}
              />
            </div>

            {/* Risk Breakdown Bar */}
            {summary.total_farms > 0 && (
              <GlassCard>
                <h3 className="text-sm font-medium text-[var(--text-secondary)] mb-3">{t("portfolio.risk_breakdown")}</h3>
                <div className="flex h-3 rounded-full overflow-hidden bg-white/5">
                  {summary.risk_breakdown.critical > 0 && (
                    <div
                      className="bg-rose-500 transition-all"
                      style={{ width: `${(summary.risk_breakdown.critical / summary.total_farms) * 100}%` }}
                      title={`${summary.risk_breakdown.critical} critical`}
                    />
                  )}
                  {summary.risk_breakdown.high > 0 && (
                    <div
                      className="bg-amber-500 transition-all"
                      style={{ width: `${(summary.risk_breakdown.high / summary.total_farms) * 100}%` }}
                      title={`${summary.risk_breakdown.high} high`}
                    />
                  )}
                  {summary.risk_breakdown.moderate > 0 && (
                    <div
                      className="bg-ocean-500 transition-all"
                      style={{ width: `${(summary.risk_breakdown.moderate / summary.total_farms) * 100}%` }}
                      title={`${summary.risk_breakdown.moderate} moderate`}
                    />
                  )}
                  {summary.risk_breakdown.low > 0 && (
                    <div
                      className="bg-emerald-500 transition-all"
                      style={{ width: `${(summary.risk_breakdown.low / summary.total_farms) * 100}%` }}
                      title={`${summary.risk_breakdown.low} low`}
                    />
                  )}
                </div>
                <div className="flex gap-4 mt-2 text-xs text-[var(--text-secondary)]">
                  {summary.risk_breakdown.critical > 0 && (
                    <span className="flex items-center gap-1">
                      <span className="w-2 h-2 rounded-full bg-rose-500" /> Critical ({formatNumber(summary.risk_breakdown.critical, locale)})
                    </span>
                  )}
                  {summary.risk_breakdown.high > 0 && (
                    <span className="flex items-center gap-1">
                      <span className="w-2 h-2 rounded-full bg-amber-500" /> High ({formatNumber(summary.risk_breakdown.high, locale)})
                    </span>
                  )}
                  {summary.risk_breakdown.moderate > 0 && (
                    <span className="flex items-center gap-1">
                      <span className="w-2 h-2 rounded-full bg-ocean-500" /> Moderate ({formatNumber(summary.risk_breakdown.moderate, locale)})
                    </span>
                  )}
                  {summary.risk_breakdown.low > 0 && (
                    <span className="flex items-center gap-1">
                      <span className="w-2 h-2 rounded-full bg-emerald-500" /> Low ({formatNumber(summary.risk_breakdown.low, locale)})
                    </span>
                  )}
                </div>
              </GlassCard>
            )}

            {/* Farm Cards Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {farms.map((farm: any) => {
                const style = RISK_STYLES[farm.risk_level] || RISK_STYLES.low;
                const ActionIcon = ACTION_ICONS[farm.decision?.action] || CheckCircle2;
                const actionLabel = ACTION_LABELS[farm.decision?.action] || "Unknown";

                return (
                  <motion.div
                    key={farm.locality_no}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    whileHover={{ scale: 1.01 }}
                    onClick={() => navigateToFarm(farm.locality_no)}
                    className={`cursor-pointer rounded-xl border ${style.border} ${style.bg} p-4 transition-all hover:shadow-lg`}
                    role="button"
                    tabIndex={0}
                    aria-label={`View details for ${farm.name}`}
                    onKeyDown={(e) => e.key === "Enter" && navigateToFarm(farm.locality_no)}
                  >
                    {/* Farm header */}
                    <div className="flex items-start justify-between mb-3">
                      <div className="min-w-0 flex-1">
                        <h3 className="font-semibold text-[var(--text-primary)] truncate">
                          {farm.name}
                        </h3>
                        <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                          PA {farm.production_area} &middot; #{farm.locality_no}
                          {farm.company && ` &middot; ${farm.company}`}
                        </p>
                      </div>
                      <span className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${style.text} ${style.bg}`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${style.dot}`} />
                        {farm.risk_level}
                      </span>
                    </div>

                    {/* Lice level bar */}
                    <div className="mb-3">
                      <div className="flex items-baseline justify-between mb-1">
                        <span className="text-xs text-[var(--text-secondary)]">Lice Level</span>
                        <span className={`text-sm font-mono font-semibold ${liceColor(farm.lice_level)}`}>
                          {farm.lice_level != null ? formatNumber(farm.lice_level, locale, 3) : "\u2014"}
                        </span>
                      </div>
                      <div className="h-1.5 rounded-full bg-white/10 dark:bg-white/5 overflow-hidden">
                        <div
                          className={`h-full rounded-full ${liceBarColor(farm.lice_level)} transition-all`}
                          style={{ width: liceBarWidth(farm.lice_level) }}
                        />
                      </div>
                      <div className="flex justify-between mt-0.5 text-[10px] text-[var(--text-secondary)]">
                        <span>0</span>
                        <span className="text-amber-500">0.3</span>
                        <span className="text-rose-500">0.5</span>
                        <span>0.7</span>
                      </div>
                    </div>

                    {/* Decision recommendation */}
                    <div className="flex items-center gap-2 mb-2">
                      <ActionIcon className={`w-4 h-4 ${style.text}`} />
                      <span className={`text-sm font-medium ${style.text}`}>
                        {actionLabel}
                      </span>
                    </div>

                    {/* Details row */}
                    <div className="flex items-center gap-3 text-xs text-[var(--text-secondary)]">
                      {farm.decision?.recommended_method && farm.decision.recommended_method !== "none" && farm.decision.recommended_method !== "monitoring" && (
                        <span className="capitalize">{farm.decision.recommended_method}</span>
                      )}
                      {farm.sea_temp_c && (
                        <span className="flex items-center gap-0.5">
                          <Thermometer className="w-3 h-3" />
                          {formatNumber(farm.sea_temp_c, locale, 1)}C
                        </span>
                      )}
                      {farm.decision?.roi_estimate > 0 && (
                        <span>ROI {formatNumber(farm.decision.roi_estimate, locale, 1)}x</span>
                      )}
                      {farm.data_week && (
                        <span className="ml-auto opacity-60">{farm.data_week}</span>
                      )}
                    </div>
                  </motion.div>
                );
              })}
            </div>
          </>
        )}
      </div>
    </ErrorBoundary>
  );
}
