"use client";
import { useEffect, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Sunrise, Thermometer, TrendingUp, TrendingDown, Minus,
  ShieldCheck, ShieldAlert, AlertTriangle, CheckCircle2,
  Loader2, Search, ClipboardCheck, BarChart3, Clock, Star, X, Printer,
} from "lucide-react";
import KPICard from "@/components/KPICard";
import GlassCard from "@/components/GlassCard";
import DataQualityBadge from "@/components/DataQualityBadge";
import { OcButton } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { useApiError } from "@/lib/useApiError";
import ErrorBoundary from "@/components/ErrorBoundary";
import AnimatedGauge from "@/components/AnimatedGauge";
import { useTranslation, formatNumber, formatCurrency, formatDate } from "@/lib/i18n";
import { dataColors, colors } from "@/lib/design-tokens";

/* eslint-disable @typescript-eslint/no-explicit-any */

const ACTION_STYLES: Record<string, { bg: string; border: string; text: string; icon: any }> = {
  TREAT_NOW: {
    bg: "bg-rose-500/15",
    border: "border-rose-500/30",
    text: "text-rose-400",
    icon: ShieldAlert,
  },
  SCHEDULE_TREATMENT: {
    bg: "bg-amber-500/15",
    border: "border-amber-500/30",
    text: "text-amber-400",
    icon: AlertTriangle,
  },
  MONITOR: {
    bg: "bg-ocean-500/15",
    border: "border-ocean-500/30",
    text: "text-ocean-400",
    icon: ShieldCheck,
  },
  NO_ACTION: {
    bg: "bg-emerald-500/15",
    border: "border-emerald-500/30",
    text: "text-emerald-400",
    icon: CheckCircle2,
  },
};

const METHODS = ["mechanical", "freshwater", "medicinal", "thermal", "biological"];

export default function FarmerDailyPage() {
  const { t, locale } = useTranslation();
  const handleError = useApiError();
  // Restore last-used locality from localStorage
  const [localityNo, setLocalityNo] = useState<number>(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("oc_last_locality");
      if (saved) {
        const parsed = JSON.parse(saved);
        return parsed.locality_no || 10469;
      }
    }
    return 10469;
  });
  const [localityName, setLocalityName] = useState<string>(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("oc_last_locality");
      if (saved) {
        const parsed = JSON.parse(saved);
        return parsed.name || "";
      }
    }
    return "";
  });
  const [decision, setDecision] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [formMethod, setFormMethod] = useState("mechanical");
  const [formNotes, setFormNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [efficacy, setEfficacy] = useState<any>(null);
  const [treatmentHistory, setTreatmentHistory] = useState<any[]>([]);
  const [heatwave, setHeatwave] = useState<any>(null);
  const [resistance, setResistance] = useState<any>(null);
  const [welfare, setWelfare] = useState<any>(null);
  const [advisory, setAdvisory] = useState<any>(null);

  // Saved farms ("My Farms") list
  const [savedFarms, setSavedFarms] = useState<{locality_no: number; name: string}[]>(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("oc_saved_farms");
      if (saved) {
        try { return JSON.parse(saved); } catch { return []; }
      }
    }
    return [];
  });
  const [longPressTimer, setLongPressTimer] = useState<ReturnType<typeof setTimeout> | null>(null);

  // Persist saved farms to localStorage on every change
  useEffect(() => {
    localStorage.setItem("oc_saved_farms", JSON.stringify(savedFarms));
  }, [savedFarms]);

  const isFarmSaved = useCallback(
    (locNo: number) => savedFarms.some(f => f.locality_no === locNo),
    [savedFarms]
  );

  const toggleSavedFarm = useCallback((farm: {locality_no: number; name: string}) => {
    setSavedFarms(prev => {
      if (prev.some(f => f.locality_no === farm.locality_no)) {
        return prev.filter(f => f.locality_no !== farm.locality_no);
      }
      return [...prev, farm];
    });
  }, []);

  const removeSavedFarm = useCallback((locNo: number) => {
    setSavedFarms(prev => prev.filter(f => f.locality_no !== locNo));
  }, []);

  // Farm search state
  const [farmSearch, setFarmSearch] = useState("");
  const [farmList, setFarmList] = useState<{ locality_no: number; name: string }[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [farmListLoading, setFarmListLoading] = useState(false);
  const searchTimeoutRef = useState<ReturnType<typeof setTimeout> | null>(null);
  const dropdownRef = useState<HTMLDivElement | null>(null);

  // Fetch farms when search text changes (debounced)
  useEffect(() => {
    if (searchTimeoutRef[0]) clearTimeout(searchTimeoutRef[0]);
    setFarmListLoading(true);
    const timeout = setTimeout(() => {
      api.searchLocalities(farmSearch).then((results: any) => {
        setFarmList(Array.isArray(results) ? results : []);
        setFarmListLoading(false);
      }).catch((e: unknown) => {
        handleError("farmer_daily_search_localities")(e);
        setFarmList([]);
        setFarmListLoading(false);
      });
    }, farmSearch ? 300 : 0);
    searchTimeoutRef[0] = timeout;
    return () => clearTimeout(timeout);
  }, [farmSearch]);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (dropdownRef[0] && !dropdownRef[0].contains(e.target as Node)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const selectFarm = (farm: { locality_no: number; name: string }) => {
    setLocalityNo(farm.locality_no);
    setLocalityName(farm.name);
    setShowDropdown(false);
    setFarmSearch("");
    // Save to localStorage
    localStorage.setItem("oc_last_locality", JSON.stringify(farm));
  };

  const fetchDecision = async (loc: number) => {
    setLoading(true);
    setSubmitted(false);
    try {
      const d = await api.farmDecision(loc);
      setDecision(d);
    } catch {
      setDecision(null);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchDecision(localityNo);
    api.treatmentEfficacyByMethod().then(setEfficacy).catch(handleError("farmer_daily_efficacy"));
    api.treatmentHistory(localityNo).then(setTreatmentHistory).catch(handleError("farmer_daily_treatment_history"));
    api.marineHeatwaveRisk().then(setHeatwave).catch(handleError("farmer_daily_heatwave"));
    api.resistanceMap().then(setResistance).catch(handleError("farmer_daily_resistance"));
    api.welfareScore(localityNo).then(setWelfare).catch(handleError("farmer_daily_welfare"));
    api.farmerAdvisory(localityNo).then(setAdvisory).catch(handleError("farmer_daily_advisory"));
  }, [localityNo]);

  const handleLogOutcome = async () => {
    setSubmitting(true);
    try {
      await api.logTreatmentOutcome({
        locality_no: localityNo,
        treatment_date: new Date().toISOString(),
        method: formMethod,
        pre_lice_count: decision?.lice_current || 0,
        notes: formNotes,
      });
      setSubmitted(true);
      setShowForm(false);
      setFormNotes("");
    } catch {
      /* best effort */
    }
    setSubmitting(false);
  };

  const [today, setToday] = useState("");
  useEffect(() => { setToday(formatDate(new Date(), locale)); }, [locale]);

  const action = decision?.action || "NO_ACTION";
  const style = ACTION_STYLES[action] || ACTION_STYLES.NO_ACTION;
  const ActionIcon = style.icon;

  const trendIcon =
    decision?.lice_trend === "rising" ? TrendingUp :
    decision?.lice_trend === "declining" ? TrendingDown : Minus;
  const trendColor =
    decision?.lice_trend === "rising" ? "text-rose-400" :
    decision?.lice_trend === "declining" ? "text-emerald-400" : "text-[var(--text-secondary)]";

  return (
    <ErrorBoundary fallbackTitle="Daily Check error">
    <div className="space-y-6 max-w-2xl mx-auto pb-20">
      {/* Print-friendly styles */}
      <style jsx global>{`
        @media print {
          body { background: white !important; color: black !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
          nav, header, [data-sidebar], [data-topbar], [data-demo-shell], footer,
          .print\\:hidden { display: none !important; }
          .md\\:ml-\\[240px\\] { margin-left: 0 !important; }
          main { padding: 0 !important; }
          .space-y-6 > * { break-inside: avoid; }
          [class*="bg-"] { background-color: transparent !important; }
          [class*="border-"] { border-color: #e5e7eb !important; }
          [class*="text-\\[var"] { color: #111827 !important; }
          [class*="text-rose"], [class*="text-amber"], [class*="text-emerald"],
          [class*="text-ocean"], [class*="text-sky"] { print-color-adjust: exact; -webkit-print-color-adjust: exact; }
          .rounded-2xl, .rounded-xl { border: 1px solid #d1d5db !important; padding: 12px !important; margin-bottom: 8px !important; }
          h1 { font-size: 18pt !important; }
          @page { margin: 1cm; size: A4; }
        }
      `}</style>

      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between"
      >
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] flex items-center gap-2">
            <Sunrise className="w-6 h-6 text-amber-400" />
            {t("farmer.title")}
          </h1>
          <p className="text-sm text-[var(--text-secondary)] mt-1">{today}</p>
        </div>
        <button
          onClick={() => window.print()}
          className="print:hidden flex items-center gap-1.5 px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:text-ocean-400 bg-white/[0.04] border border-white/[0.08] rounded-lg transition-colors"
          title="Download as PDF (print)"
        >
          <Printer className="w-3.5 h-3.5" />
          <span>PDF</span>
        </button>
      </motion.div>

      {/* My Farms — saved quick-access chips */}
      {savedFarms.length > 0 && (
        <div>
          <p className="text-[10px] uppercase tracking-wider text-[var(--text-secondary)] mb-1.5 font-medium">{t("farmer.my_farms")}</p>
          <div className="flex flex-wrap gap-1.5">
            {savedFarms.map(farm => (
              <div
                key={farm.locality_no}
                className="group relative"
              >
                <button
                  onClick={() => selectFarm(farm)}
                  onTouchStart={() => {
                    const timer = setTimeout(() => removeSavedFarm(farm.locality_no), 600);
                    setLongPressTimer(timer);
                  }}
                  onTouchEnd={() => { if (longPressTimer) clearTimeout(longPressTimer); }}
                  onTouchCancel={() => { if (longPressTimer) clearTimeout(longPressTimer); }}
                  className={`px-3 py-1.5 rounded-full text-[11px] border transition-colors pr-7
                    ${farm.locality_no === localityNo
                      ? "bg-ocean-500/20 border-ocean-500/30 text-ocean-400"
                      : "bg-white/[0.04] border-white/[0.06] text-[var(--text-secondary)] hover:border-ocean-500/20"}`}
                >
                  {farm.name || `Locality ${farm.locality_no}`}
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); removeSavedFarm(farm.locality_no); }}
                  className="absolute right-1.5 top-1/2 -translate-y-1/2 w-4 h-4 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity hover:bg-white/10"
                  title="Remove from My Farms"
                >
                  <X className="w-3 h-3 text-[var(--text-secondary)]" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Farm selector — searchable dropdown */}
      <div className="relative" ref={(el) => { dropdownRef[0] = el; }}>
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-secondary)] pointer-events-none" />
            <input
              type="text"
              value={showDropdown ? farmSearch : (localityName ? `${localityName} (${localityNo})` : `Locality ${localityNo}`)}
              onChange={(e) => {
                setFarmSearch(e.target.value);
                if (!showDropdown) setShowDropdown(true);
              }}
              onFocus={() => {
                setShowDropdown(true);
                setFarmSearch("");
              }}
              placeholder={t("farmer.search_farms")}
              className="w-full bg-white/[0.06] border border-white/[0.08] rounded-xl pl-9 pr-4 py-2.5 text-sm text-[var(--text-primary)] placeholder-[var(--text-secondary)] focus:outline-none focus:border-ocean-500/40"
            />
          </div>
          {/* Save / Unsave farm button */}
          <button
            onClick={() => toggleSavedFarm({ locality_no: localityNo, name: localityName })}
            className={`flex items-center justify-center w-10 h-10 rounded-xl border transition-colors ${
              isFarmSaved(localityNo)
                ? "bg-amber-500/15 border-amber-500/30 text-amber-400"
                : "bg-white/[0.06] border-white/[0.08] text-[var(--text-secondary)] hover:border-amber-500/20 hover:text-amber-400"
            }`}
            title={isFarmSaved(localityNo) ? "Remove from My Farms" : "Save to My Farms"}
          >
            <Star className={`w-4 h-4 ${isFarmSaved(localityNo) ? "fill-amber-400" : ""}`} />
          </button>
        </div>
        <AnimatePresence>
          {showDropdown && (
            <motion.div
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.15 }}
              className="absolute z-50 left-0 right-0 mt-1 max-h-64 overflow-y-auto rounded-xl bg-[var(--glass-bg,rgba(10,20,40,0.95))] border border-white/[0.1] backdrop-blur-xl shadow-2xl"
            >
              {farmListLoading ? (
                <div className="flex items-center justify-center py-4">
                  <Loader2 className="w-4 h-4 animate-spin text-ocean-400" />
                  <span className="ml-2 text-xs text-[var(--text-secondary)]">{t("common.loading")}</span>
                </div>
              ) : farmList.length === 0 ? (
                <div className="px-4 py-3 text-xs text-[var(--text-secondary)]">
                  No farms found{farmSearch ? ` for "${farmSearch}"` : ""}. Try a different search.
                </div>
              ) : (
                farmList.map((farm) => (
                  <button
                    key={farm.locality_no}
                    onClick={() => selectFarm(farm)}
                    className={`w-full text-left px-4 py-2.5 flex items-center justify-between hover:bg-white/[0.06] transition-colors border-b border-white/[0.04] last:border-b-0 ${
                      farm.locality_no === localityNo ? "bg-ocean-500/10" : ""
                    }`}
                  >
                    <div className="min-w-0">
                      <p className="text-sm text-[var(--text-primary)] truncate font-medium">{farm.name}</p>
                      <p className="text-[10px] text-[var(--text-secondary)]">Locality {farm.locality_no}</p>
                    </div>
                    {farm.locality_no === localityNo && (
                      <CheckCircle2 className="w-4 h-4 text-ocean-400 flex-shrink-0 ml-2" />
                    )}
                  </button>
                ))
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 animate-spin text-ocean-400" />
        </div>
      ) : decision?.error ? (
        <GlassCard>
          <p className="text-[var(--text-secondary)] text-center py-8">
            {t("common.no_data")}
          </p>
        </GlassCard>
      ) : decision ? (
        <>
          {/* Main Decision Card */}
          <motion.div
            initial={{ opacity: 0, scale: 0.97 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.1 }}
          >
            <GlassCard className={`${style.bg} border ${style.border}`}>
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className={`w-12 h-12 rounded-xl ${style.bg} flex items-center justify-center`}>
                    <ActionIcon className={`w-6 h-6 ${style.text}`} />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className={`text-xs font-semibold uppercase tracking-wider ${style.text}`}>
                        {action === "TREAT_NOW" ? t("farmer.action.treat_now") :
                         action === "SCHEDULE_TREATMENT" ? t("farmer.action.schedule") :
                         action === "MONITOR" ? t("farmer.action.monitor") :
                         t("farmer.action.no_action")}
                      </span>
                      <DataQualityBadge provenance={decision.data_provenance} />
                    </div>
                    <p className="text-sm text-[var(--text-secondary)] mt-0.5">
                      {localityName || `Locality ${localityNo}`} ({localityNo}) &middot; {decision.urgency?.replace(/_/g, " ")}
                    </p>
                  </div>
                </div>
              </div>

              {/* Reasoning */}
              <div className="space-y-1.5 mb-4">
                {(decision.reasoning || []).map((r: string, i: number) => (
                  <p key={i} className="text-sm text-[var(--text-primary)] leading-relaxed">
                    &bull; {r}
                  </p>
                ))}
              </div>

              {/* Lice Danger Gauge */}
              {decision.lice_current != null && (
                <div className="flex justify-center py-2">
                  <AnimatedGauge
                    value={decision.lice_current}
                    min={0}
                    max={1}
                    label={t("farmer.lice_level")}
                    unit="af/fish"
                    size={140}
                    thresholds={[
                      { value: 20, color: "var(--positive)" },
                      { value: 50, color: "var(--warning)" },
                      { value: 100, color: "var(--danger)" },
                    ]}
                  />
                </div>
              )}

              {/* Method + Success + ROI row */}
              {decision.recommended_method && decision.recommended_method !== "none" && decision.recommended_method !== "monitoring" && (
                <div className="grid grid-cols-3 gap-3 mt-4 pt-4 border-t border-white/[0.06]">
                  <div className="text-center">
                    <p className="text-xs text-[var(--text-secondary)] mb-1">{t("farmer.recommended_method")}</p>
                    <p className="text-sm font-semibold text-[var(--text-primary)] capitalize">
                      {t(`farmer.method.${decision.recommended_method}`) || decision.recommended_method}
                    </p>
                  </div>
                  <div className="text-center">
                    <p className="text-xs text-[var(--text-secondary)] mb-1">Success</p>
                    <p className="text-sm font-semibold text-emerald-400">
                      {decision.success_probability != null ? `${formatNumber(decision.success_probability * 100, locale)}%` : "\u2014"}
                    </p>
                  </div>
                  <div className="text-center">
                    <p className="text-xs text-[var(--text-secondary)] mb-1">{t("farmer.roi")}</p>
                    <p className="text-sm font-semibold text-ocean-400">
                      {decision.roi_estimate != null ? `${formatNumber(decision.roi_estimate, locale, 1)}x` : "\u2014"}
                    </p>
                  </div>
                </div>
              )}
            </GlassCard>
          </motion.div>

          {/* KPI Strip */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <KPICard
              label={t("farmer.lice_level")}
              value={decision.lice_current != null ? formatNumber(decision.lice_current, locale, 2) : "N/A"}
              delta={t("farmer.adult_female_lice")}
              icon={trendIcon}
            />
            <KPICard
              label="Trend"
              value={decision.lice_trend || "N/A"}
              delta="last 4 weeks"
              icon={trendIcon}
            />
            <KPICard
              label={t("farmer.sea_temp")}
              value={decision.sea_temp_c != null ? `${formatNumber(decision.sea_temp_c, locale, 1)}\u00B0C` : "N/A"}
              delta="latest reading"
              icon={Thermometer}
            />
            <KPICard
              label="GNN Forecast"
              value={
                decision.lice_predicted_next_week != null
                  ? formatNumber(decision.lice_predicted_next_week, locale, 2)
                  : "N/A"
              }
              delta="next week pred."
              icon={TrendingUp}
            />
          </div>

          {/* Lice Sparkline */}
          {decision.lice_history && decision.lice_history.length > 1 && (
            <GlassCard>
              <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3">Lice Trend (Recent Weeks)</h3>
              <div className="flex items-end gap-1 h-16">
                {decision.lice_history.map((h: any, i: number) => {
                  const maxLice = Math.max(...decision.lice_history.map((x: any) => x.lice || 0.01));
                  const pct = maxLice > 0 ? ((h.lice || 0) / maxLice) * 100 : 10;
                  const isLast = i === decision.lice_history.length - 1;
                  return (
                    <div key={i} className="flex-1 flex flex-col items-center gap-1">
                      <motion.div
                        initial={{ height: 0 }}
                        animate={{ height: `${Math.max(pct, 5)}%` }}
                        transition={{ delay: i * 0.08 }}
                        className={`w-full rounded-t-md ${
                          h.lice > 0.5
                            ? "bg-rose-500/70"
                            : h.lice > 0.3
                              ? "bg-amber-500/70"
                              : "bg-ocean-500/70"
                        } ${isLast ? "ring-2 ring-white/20" : ""}`}
                      />
                      <span className="text-[9px] text-[var(--text-secondary)]">W{h.week}</span>
                    </div>
                  );
                })}
              </div>
            </GlassCard>
          )}

          {/* Cost Breakdown */}
          {(decision.cost_of_treatment_nok > 0 || decision.cost_of_inaction_nok > 0) && (
            <GlassCard>
              <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3">{t("farmer.treatment_cost")}</h3>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-[var(--text-secondary)]">{t("farmer.treatment_cost")}</p>
                  <p className="text-lg font-bold text-amber-400">
                    {formatCurrency(decision.cost_of_treatment_nok / 1000, locale)}k
                  </p>
                </div>
                <div>
                  <p className="text-xs text-[var(--text-secondary)]">{t("farmer.cost_of_inaction")}</p>
                  <p className="text-lg font-bold text-rose-400">
                    {formatCurrency(decision.cost_of_inaction_nok / 1000, locale)}k
                  </p>
                </div>
              </div>
            </GlassCard>
          )}

          {/* Treatment Efficacy — Crowdsourced */}
          {efficacy?.methods?.length > 0 && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5 }}>
              <GlassCard>
                <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
                  <BarChart3 className="w-4 h-4 text-ocean-400" />
                  {t("farmer.efficacy_title")} ({efficacy.total_outcomes} {t("farmer.efficacy_subtitle")})
                </h3>
                <div className="space-y-2">
                  {efficacy.methods.map((m: any) => {
                    const pct = m.avg_reduction_pct || 0;
                    const barColor = pct >= 70 ? "bg-emerald-500" : pct >= 50 ? "bg-amber-500" : "bg-rose-500";
                    return (
                      <div key={m.method} className="flex items-center gap-3">
                        <span className="text-[11px] text-[var(--text-primary)] w-24 shrink-0 capitalize">
                          {m.method}
                        </span>
                        <div className="flex-1 h-4 bg-white/[0.06] rounded-full overflow-hidden">
                          <div className={`h-full ${barColor} rounded-full transition-all`} style={{ width: `${Math.min(pct, 100)}%` }} />
                        </div>
                        <span className="text-[11px] tabular-nums text-[var(--text-secondary)] w-16 text-right">
                          {formatNumber(pct, locale)}% ({m.sample_size})
                        </span>
                      </div>
                    );
                  })}
                </div>
                <p className="text-[9px] text-[var(--text-secondary)] mt-2 opacity-60">
                  Based on farmer-reported outcomes. Log your treatment to improve this data.
                </p>
              </GlassCard>
            </motion.div>
          )}

          {/* Treatment History */}
          {treatmentHistory.length > 0 && (
            <GlassCard>
              <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
                <Clock className="w-4 h-4 text-ocean-400" />
                Treatment History ({treatmentHistory.length})
              </h3>
              <div className="space-y-2">
                {treatmentHistory.map((t: any, i: number) => (
                  <div key={i} className="flex items-center gap-3 p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                    <div className="w-1.5 h-8 rounded-full bg-ocean-500/30" />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-[11px] font-medium text-[var(--text-primary)] capitalize">{t.method}</span>
                        <span className="text-[9px] text-[var(--text-secondary)]">{t.date}</span>
                      </div>
                      <div className="flex gap-3 mt-0.5 text-[10px] text-[var(--text-secondary)]">
                        {t.pre_lice != null && <span>Pre: {formatNumber(t.pre_lice, locale, 2)}</span>}
                        {t.post_lice != null && <span>Post: {formatNumber(t.post_lice, locale, 2)}</span>}
                        {t.pre_lice != null && t.post_lice != null && (
                          <span className="text-emerald-400">
                            -{formatNumber((1 - t.post_lice / Math.max(t.pre_lice, 0.001)) * 100, locale)}%
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </GlassCard>
          )}

          {/* Explainability — SHAP-style factor importance */}
          {decision?.explanation?.factors?.length > 0 && (
            <GlassCard>
              <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-violet-400" />
                {t("farmer.why_recommendation")}
              </h3>
              <div className="space-y-2">
                {decision.explanation.factors
                  .sort((a: any, b: any) => b.importance - a.importance)
                  .slice(0, 5)
                  .map((f: any, i: number) => (
                    <div key={i} className="flex items-center gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex justify-between text-[11px] mb-1">
                          <span className="text-[var(--text-primary)] capitalize">{f.name.replace(/_/g, " ")}</span>
                          <span className="text-[var(--text-secondary)]">{formatNumber(f.importance * 100, locale)}%</span>
                        </div>
                        <div className="h-1.5 bg-white/[0.06] rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full"
                            style={{
                              width: `${f.importance * 100}%`,
                              backgroundColor: f.name === "lice_level" || f.name === "lice_trend" ? dataColors.lice
                                : f.name === "sea_temperature" ? dataColors.temperature
                                : f.name === "regulatory_distance" ? colors.warning
                                : f.name === "season" ? dataColors.feeding
                                : colors.accent,
                              opacity: 0.7,
                            }}
                          />
                        </div>
                        <p className="text-[9px] text-[var(--text-secondary)] mt-0.5">{f.en}</p>
                      </div>
                    </div>
                  ))}
              </div>
              {decision.explanation.summary_en && (
                <p className="text-[10px] text-[var(--text-secondary)] mt-3 italic border-t border-white/[0.06] pt-2">
                  {decision.explanation.summary_en}
                </p>
              )}
            </GlassCard>
          )}

          {/* Marine Heatwave Alert */}
          {heatwave && !heatwave.error && (heatwave.warning_count > 0 || heatwave.critical_count > 0) && (
            <GlassCard>
              <h3 className="text-sm font-semibold text-amber-400 mb-2 flex items-center gap-2">
                <Thermometer className="w-4 h-4" />
                Marine Heatwave Alert
              </h3>
              <p className="text-xs text-[var(--text-secondary)]">
                {heatwave.critical_count > 0 && (
                  <span className="text-rose-400 font-medium">{heatwave.critical_count} critical </span>
                )}
                {heatwave.warning_count > 0 && (
                  <span className="text-amber-400 font-medium">{heatwave.warning_count} warning </span>
                )}
                production areas with elevated sea temperatures.
                Warm water accelerates lice reproduction and increases disease risk.
              </p>
            </GlassCard>
          )}

          {/* Treatment Resistance Warning */}
          {resistance?.production_areas?.some((p: any) =>
            p.methods?.some((m: any) => m.risk_level === "HIGH")
          ) && (
            <GlassCard>
              <h3 className="text-sm font-semibold text-amber-400 mb-2 flex items-center gap-2">
                <ShieldAlert className="w-4 h-4" />
                Treatment Resistance
              </h3>
              <p className="text-xs text-[var(--text-secondary)]">
                High resistance detected in some production areas. Consider rotating treatment
                methods to maintain efficacy. Check the Resistance Map for details.
              </p>
            </GlassCard>
          )}

          {/* Fish Welfare Score */}
          {welfare && !welfare.error && (
            <GlassCard>
              <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-ocean-400" />
                Fish Welfare Score (SWIM)
              </h3>
              <div className="flex items-center gap-4 mb-3">
                <div className={`text-3xl font-bold ${
                  welfare.total_score >= 70 ? "text-emerald-400" :
                  welfare.total_score >= 40 ? "text-amber-400" : "text-rose-400"
                }`}>
                  {formatNumber(welfare.total_score, locale, 0)}<span className="text-sm text-[var(--text-secondary)]">/100</span>
                </div>
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium border ${
                  welfare.grade === "A" ? "bg-emerald-500/15 border-emerald-500/30 text-emerald-400" :
                  welfare.grade === "B" ? "bg-ocean-500/15 border-ocean-500/30 text-ocean-400" :
                  welfare.grade === "C" ? "bg-amber-500/15 border-amber-500/30 text-amber-400" :
                  "bg-rose-500/15 border-rose-500/30 text-rose-400"
                }`}>
                  Grade {welfare.grade}
                </span>
                {welfare.predicted_mortality_7d != null && (
                  <span className="text-xs text-[var(--text-secondary)]">
                    7d mortality: {formatNumber(welfare.predicted_mortality_7d * 100, locale, 2)}%
                  </span>
                )}
              </div>
              {welfare.components && (
                <div className="space-y-1.5">
                  {Object.entries(welfare.components).map(([key, val]: [string, any]) => (
                    <div key={key} className="flex items-center gap-2">
                      <span className="text-[10px] text-[var(--text-secondary)] w-24 truncate capitalize">{key.replace(/_/g, " ")}</span>
                      <div className="flex-1 h-1.5 bg-white/[0.06] rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full ${
                            (val as number) >= 70 ? "bg-emerald-400" :
                            (val as number) >= 40 ? "bg-amber-400" : "bg-rose-400"
                          }`}
                          style={{ width: `${Math.min(100, val as number)}%` }}
                        />
                      </div>
                      <span className="text-[10px] text-[var(--text-secondary)] w-8 text-right">{formatNumber(val as number, locale, 0)}</span>
                    </div>
                  ))}
                </div>
              )}
              {welfare.alert_reason && (
                <p className="text-xs text-amber-400 mt-2">⚠ {welfare.alert_reason}</p>
              )}
            </GlassCard>
          )}

          {/* Farm Advisory Summary */}
          {advisory && !advisory.error && (
            <GlassCard>
              <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-2 flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-ocean-400" />
                Farm Advisory
                {advisory.data_provenance && <DataQualityBadge provenance={advisory.data_provenance} />}
              </h3>
              <p className="text-xs text-[var(--text-secondary)] leading-relaxed mb-2">
                {advisory.summary}
              </p>
              <div className="grid grid-cols-2 gap-2 text-xs">
                {advisory.harvest_advice && (
                  <div className="bg-white/[0.04] rounded-lg p-2">
                    <span className="text-[var(--text-secondary)]">Harvest:</span>{" "}
                    <span className="text-[var(--text-primary)]">{advisory.harvest_advice}</span>
                  </div>
                )}
                {advisory.forecast_1w != null && (
                  <div className="bg-white/[0.04] rounded-lg p-2">
                    <span className="text-[var(--text-secondary)]">1w forecast:</span>{" "}
                    <span className="text-[var(--text-primary)]">{formatNumber(advisory.forecast_1w, locale, 2)} lice</span>
                  </div>
                )}
              </div>
            </GlassCard>
          )}

          {/* I Treated Today button */}
          <div className="space-y-3">
            {submitted && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="bg-emerald-500/15 border border-emerald-500/30 rounded-xl p-3 text-center"
              >
                <p className="text-sm text-emerald-400 font-medium">
                  {t("farmer.treatment_logged")}
                </p>
              </motion.div>
            )}

            <OcButton
              onClick={() => setShowForm(!showForm)}
              variant="primary"
              className="w-full"
            >
              <ClipboardCheck className="w-4 h-4 mr-2" />
              {t("farmer.i_treated_today")}
            </OcButton>

            <AnimatePresence>
              {showForm && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                >
                  <GlassCard>
                    <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3">{t("farmer.log_treatment")}</h3>
                    <div className="space-y-3">
                      <div>
                        <label className="text-xs text-[var(--text-secondary)] block mb-1">Method</label>
                        <select
                          value={formMethod}
                          onChange={(e) => setFormMethod(e.target.value)}
                          className="w-full bg-white/[0.06] border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-[var(--text-primary)] focus:outline-none focus:border-ocean-500/40"
                        >
                          {METHODS.map((m) => (
                            <option key={m} value={m}>{t(`farmer.method.${m}`) || m.charAt(0).toUpperCase() + m.slice(1)}</option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="text-xs text-[var(--text-secondary)] block mb-1">Notes (optional)</label>
                        <textarea
                          value={formNotes}
                          onChange={(e) => setFormNotes(e.target.value)}
                          rows={2}
                          placeholder="Any observations..."
                          className="w-full bg-white/[0.06] border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-[var(--text-primary)] placeholder-[var(--text-secondary)] focus:outline-none focus:border-ocean-500/40 resize-none"
                        />
                      </div>
                      <OcButton
                        onClick={handleLogOutcome}
                        variant="primary"
                        className="w-full"
                        disabled={submitting}
                      >
                        {submitting ? (
                          <Loader2 className="w-4 h-4 animate-spin mr-2" />
                        ) : (
                          <CheckCircle2 className="w-4 h-4 mr-2" />
                        )}
                        Submit
                      </OcButton>
                    </div>
                  </GlassCard>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </>
      ) : (
        <GlassCard>
          <p className="text-[var(--text-secondary)] text-center py-8">
            {t("common.no_data")}
          </p>
        </GlassCard>
      )}
    </div>
    </ErrorBoundary>
  );
}
