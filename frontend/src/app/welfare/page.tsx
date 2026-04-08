"use client";
import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import {
  Heart, Search, AlertTriangle, TrendingDown,
  Loader2, Activity, Thermometer, Droplets, Syringe, Bug,
} from "lucide-react";
import GlassCard from "@/components/GlassCard";
import KPICard from "@/components/KPICard";
import ErrorBoundary from "@/components/ErrorBoundary";
import { api } from "@/lib/api";
import { useApiError } from "@/lib/useApiError";
import { useTranslation, formatNumber } from "@/lib/i18n";

/* eslint-disable @typescript-eslint/no-explicit-any */

const GRADE_COLORS: Record<string, string> = {
  "A+": "text-emerald-400",
  "A":  "text-emerald-400",
  "B+": "text-green-400",
  "B":  "text-lime-400",
  "C":  "text-amber-400",
  "D":  "text-orange-400",
  "F":  "text-rose-400",
};

const GRADE_BG: Record<string, string> = {
  "A+": "bg-emerald-500/20 border-emerald-500/30",
  "A":  "bg-emerald-500/20 border-emerald-500/30",
  "B+": "bg-green-500/20 border-green-500/30",
  "B":  "bg-lime-500/20 border-lime-500/30",
  "C":  "bg-amber-500/20 border-amber-500/30",
  "D":  "bg-orange-500/20 border-orange-500/30",
  "F":  "bg-rose-500/20 border-rose-500/30",
};

const COMPONENT_META: Record<string, { icon: any; key: string; weight: string }> = {
  lice:             { icon: Bug,          key: "welfare.component.lice",        weight: "35%" },
  thermal:          { icon: Thermometer,  key: "welfare.component.thermal",     weight: "15%" },
  mortality:        { icon: TrendingDown, key: "welfare.component.mortality",   weight: "20%" },
  environment:      { icon: Droplets,     key: "welfare.component.environment", weight: "15%" },
  treatment_stress: { icon: Syringe,      key: "welfare.component.treatment",   weight: "15%" },
};

/** Map 0-1 score to bar color */
function barColor(val: number): string {
  if (val >= 0.7) return "bg-emerald-500";
  if (val >= 0.4) return "bg-amber-500";
  return "bg-rose-500";
}

/** Map 0-100 score to circular gauge color */
function scoreColor(score: number): string {
  if (score >= 80) return "#10b981"; // emerald
  if (score >= 60) return "#84cc16"; // lime
  if (score >= 40) return "#f59e0b"; // amber
  return "#ef4444"; // rose
}

export default function WelfarePage() {
  const { t, locale } = useTranslation();
  const handleError = useApiError();

  const [localityInput, setLocalityInput] = useState("");
  const [selectedLocality, setSelectedLocality] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [welfare, setWelfare] = useState<any>(null);
  const [farms, setFarms] = useState<any[]>([]);
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);

  // Load farm list for search
  useEffect(() => {
    api.exposureSites()
      .then((data: any) => {
        if (Array.isArray(data)) {
          setFarms(data);
        }
      })
      .catch(handleError("welfare_farms"));
  }, [handleError]);

  // Search farms
  useEffect(() => {
    if (!localityInput.trim()) {
      setSearchResults([]);
      setShowDropdown(false);
      return;
    }
    const q = localityInput.toLowerCase();
    const matches = farms
      .filter(
        (f: any) =>
          String(f.id).includes(q) ||
          (f.name && f.name.toLowerCase().includes(q))
      )
      .slice(0, 10);
    setSearchResults(matches);
    setShowDropdown(matches.length > 0);
  }, [localityInput, farms]);

  const selectFarm = useCallback((farm: any) => {
    setSelectedLocality(farm.id);
    setLocalityInput(`${farm.name} (${farm.id})`);
    setShowDropdown(false);
  }, []);

  // Fetch welfare score
  useEffect(() => {
    if (!selectedLocality) return;
    setLoading(true);
    setWelfare(null);
    api.welfareScore(selectedLocality)
      .then(setWelfare)
      .catch(handleError("welfare_score", { critical: true }))
      .finally(() => setLoading(false));
  }, [selectedLocality, handleError]);

  const score = welfare?.total_score ?? 0;
  const grade = welfare?.grade ?? "N/A";
  const components = welfare?.components ?? {};
  const circumference = 2 * Math.PI * 54;
  const dashOffset = circumference - (circumference * (score / 100));

  return (
    <ErrorBoundary>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-display text-[var(--text-primary)] flex items-center gap-3">
              <Heart className="w-7 h-7 text-rose-400" />
              {t("welfare.title")}
            </h1>
            <p className="text-sm text-[var(--text-secondary)] mt-1">
              {t("welfare.subtitle")}
            </p>
          </div>
        </div>

        {/* Farm Selector */}
        <GlassCard>
          <div className="relative max-w-lg">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
            <input
              type="text"
              value={localityInput}
              onChange={(e) => {
                setLocalityInput(e.target.value);
                setSelectedLocality(null);
              }}
              onFocus={() => {
                if (searchResults.length > 0) setShowDropdown(true);
              }}
              placeholder={t("welfare.search_placeholder")}
              className="w-full h-10 pl-10 pr-4 text-sm rounded-lg bg-slate-100 dark:bg-slate-800/60 border border-slate-300 dark:border-slate-700/50 text-[var(--text-primary)] placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:border-salmon/40 focus:ring-1 focus:ring-salmon/20 outline-none transition-all"
            />
            {showDropdown && (
              <div className="absolute z-20 top-full left-0 right-0 mt-1 max-h-60 overflow-y-auto rounded-lg bg-white dark:bg-fjord-midwater border border-slate-200 dark:border-slate-700 shadow-xl">
                {searchResults.map((farm: any) => (
                  <button
                    key={farm.id}
                    onClick={() => selectFarm(farm)}
                    className="w-full text-left px-4 py-2.5 text-sm hover:bg-slate-100 dark:hover:bg-white/[0.06] border-b border-slate-100 dark:border-slate-800 last:border-0 transition-colors"
                  >
                    <span className="font-medium text-[var(--text-primary)]">{farm.name}</span>
                    <span className="ml-2 text-xs text-[var(--text-secondary)]">#{farm.id}</span>
                    {farm.company && (
                      <span className="ml-2 text-xs text-slate-400">{farm.company}</span>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>
        </GlassCard>

        {/* No selection state */}
        {!selectedLocality && !loading && (
          <div className="text-center py-16 text-[var(--text-secondary)]">
            <Heart className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p>{t("welfare.select_farm")}</p>
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-8 h-8 animate-spin text-salmon" />
          </div>
        )}

        {/* Results */}
        {welfare && !loading && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            className="space-y-6"
          >
            {/* Top row: Score + Grade + Mortality */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">

              {/* Circular Welfare Score */}
              <GlassCard className="flex flex-col items-center justify-center py-8">
                <p className="text-xs text-[var(--text-secondary)] uppercase tracking-wider mb-4">
                  {t("welfare.score")}
                </p>
                <div className="relative w-36 h-36">
                  <svg className="w-full h-full -rotate-90" viewBox="0 0 120 120">
                    {/* Background circle */}
                    <circle
                      cx="60" cy="60" r="54"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="8"
                      className="text-slate-200 dark:text-slate-700/50"
                    />
                    {/* Score arc */}
                    <circle
                      cx="60" cy="60" r="54"
                      fill="none"
                      stroke={scoreColor(score)}
                      strokeWidth="8"
                      strokeLinecap="round"
                      strokeDasharray={circumference}
                      strokeDashoffset={dashOffset}
                      style={{ transition: "stroke-dashoffset 0.8s ease-out" }}
                    />
                  </svg>
                  <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <span
                      className="text-4xl font-bold"
                      style={{ color: scoreColor(score) }}
                    >
                      {formatNumber(score, locale, 0)}
                    </span>
                    <span className="text-xs text-[var(--text-secondary)]">/100</span>
                  </div>
                </div>
              </GlassCard>

              {/* Grade Badge */}
              <GlassCard className="flex flex-col items-center justify-center py-8">
                <p className="text-xs text-[var(--text-secondary)] uppercase tracking-wider mb-4">
                  {t("welfare.grade")}
                </p>
                <div className={`w-24 h-24 rounded-2xl border-2 flex items-center justify-center ${GRADE_BG[grade] || "bg-slate-500/20 border-slate-500/30"}`}>
                  <span className={`text-5xl font-bold ${GRADE_COLORS[grade] || "text-slate-400"}`}>
                    {grade}
                  </span>
                </div>
                <p className="mt-3 text-xs text-[var(--text-secondary)]">
                  Stien et al. (2013) SWIM
                </p>
              </GlassCard>

              {/* Predicted Mortality */}
              <GlassCard className="flex flex-col items-center justify-center py-8">
                <p className="text-xs text-[var(--text-secondary)] uppercase tracking-wider mb-4">
                  {t("welfare.predicted_mortality")}
                </p>
                <div className="flex items-baseline gap-1">
                  <span className={`text-4xl font-bold ${
                    welfare.predicted_mortality_7d > 1.0 ? "text-rose-400" :
                    welfare.predicted_mortality_7d > 0.3 ? "text-amber-400" : "text-emerald-400"
                  }`}>
                    {formatNumber(welfare.predicted_mortality_7d, locale, 2)}
                  </span>
                  <span className="text-lg text-[var(--text-secondary)]">%</span>
                </div>
                <p className="mt-2 text-xs text-[var(--text-secondary)] flex items-center gap-1">
                  <Activity className="w-3 h-3" />
                  next 7 days
                </p>
              </GlassCard>
            </div>

            {/* Alert Reason */}
            {welfare.alert_reason && (
              <GlassCard>
                <div className="flex items-start gap-3">
                  <AlertTriangle className={`w-5 h-5 mt-0.5 flex-shrink-0 ${
                    welfare.alert_reason.startsWith("Critical") ? "text-rose-400" :
                    welfare.alert_reason.startsWith("Warning") ? "text-amber-400" : "text-emerald-400"
                  }`} />
                  <div>
                    <p className="text-xs text-[var(--text-secondary)] uppercase tracking-wider mb-1">
                      {t("welfare.alert_reason")}
                    </p>
                    <p className="text-sm text-[var(--text-primary)] font-medium">
                      {welfare.alert_reason}
                    </p>
                  </div>
                </div>
              </GlassCard>
            )}

            {/* Component Breakdown */}
            <GlassCard>
              <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-4">
                {t("welfare.components")}
              </h3>
              <div className="space-y-4">
                {Object.entries(COMPONENT_META).map(([key, meta]) => {
                  const val = components[key] ?? 0;
                  const Icon = meta.icon;
                  return (
                    <div key={key} className="flex items-center gap-3">
                      <Icon className="w-4 h-4 text-[var(--text-secondary)] flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs text-[var(--text-primary)] font-medium">
                            {t(meta.key)}
                          </span>
                          <div className="flex items-center gap-2">
                            <span className="text-[10px] text-[var(--text-secondary)]">
                              {meta.weight}
                            </span>
                            <span className="text-xs font-mono text-[var(--text-primary)]">
                              {formatNumber(val * 100, locale, 0)}%
                            </span>
                          </div>
                        </div>
                        <div className="h-2 rounded-full bg-slate-200 dark:bg-slate-700/50 overflow-hidden">
                          <motion.div
                            initial={{ width: 0 }}
                            animate={{ width: `${val * 100}%` }}
                            transition={{ duration: 0.6, delay: 0.1 }}
                            className={`h-full rounded-full ${barColor(val)}`}
                          />
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </GlassCard>

            {/* Contributing Factors */}
            {welfare.factors && welfare.factors.length > 0 && (
              <GlassCard>
                <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3">
                  {t("welfare.factors")}
                </h3>
                <ul className="space-y-1.5">
                  {welfare.factors.map((factor: string, i: number) => (
                    <li key={i} className="text-xs text-[var(--text-secondary)] flex items-start gap-2">
                      <span className="w-1 h-1 rounded-full bg-salmon mt-1.5 flex-shrink-0" />
                      {factor}
                    </li>
                  ))}
                </ul>
              </GlassCard>
            )}
          </motion.div>
        )}
      </div>
    </ErrorBoundary>
  );
}
