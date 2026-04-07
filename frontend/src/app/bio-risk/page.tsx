"use client";
import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  Shield, RefreshCw, Bug, Leaf, AlertTriangle, Activity,
} from "lucide-react";
import KPICard from "@/components/KPICard";
import GlassCard from "@/components/GlassCard";
import { OcButton } from "@/components/ui/Button";
import dynamic from "next/dynamic";
import { api } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";
import { useApiError } from "@/lib/useApiError";
import ErrorBoundary from "@/components/ErrorBoundary";
import FreshnessIndicator from "@/components/FreshnessIndicator";
import type { PADataPoint } from "@/components/RegionalHeatmap";

const BioRiskMap = dynamic(() => import("@/components/BioRiskMap"), {
  loading: () => <div className="h-[500px] bg-slate-800/50 rounded-xl animate-pulse flex items-center justify-center"><span className="text-slate-400">Loading...</span></div>,
  ssr: false,
});

const RegionalHeatmap = dynamic(() => import("@/components/RegionalHeatmap"), {
  loading: () => <div className="h-[300px] bg-slate-800/50 rounded-xl animate-pulse flex items-center justify-center"><span className="text-slate-400">Loading...</span></div>,
});

/* eslint-disable @typescript-eslint/no-explicit-any */

const WEEK_LABELS = (() => {
  const labels: string[] = [];
  const now = new Date();
  for (let i = 7; i >= 0; i--) {
    const d = new Date(now.getTime() - i * 7 * 24 * 60 * 60 * 1000);
    const weekNum = Math.ceil(((d.getTime() - new Date(d.getFullYear(), 0, 1).getTime()) / 86400000 + 1) / 7);
    labels.push(`W${weekNum}`);
  }
  return labels;
})();

export default function BioRiskPage() {
  const { t } = useTranslation();
  const handleError = useApiError();
  const [lice, setLice] = useState<any>(null);
  const [bloom, setBloom] = useState<any[]>([]);
  const [disease, setDisease] = useState<any>(null);
  const [regime, setRegime] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchedAt, setFetchedAt] = useState<Date | null>(null);

  const [globalDisease, setGlobalDisease] = useState<any>(null);
  const [countryFarms, setCountryFarms] = useState<Record<string, any>>({});

  // Time slider state (0 = 8 weeks ago, 7 = this week)
  const [selectedWeek, setSelectedWeek] = useState(7);
  // Snapshot data from the bio-risk/snapshot endpoint
  const [snapshot, setSnapshot] = useState<any>(null);
  const [snapshotLoading, setSnapshotLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    const [r1, r2, r3, r4, r5] = await Promise.allSettled([
      api.liceSummary(),
      api.bloomRisk(),
      api.diseaseNorway(),
      api.regimeStates(),
      api.globalDiseaseGeo(),
    ]);
    if (r1.status === "fulfilled") setLice(r1.value);
    if (r2.status === "fulfilled") setBloom(Array.isArray(r2.value) ? r2.value : r2.value?.assessments || []);
    if (r3.status === "fulfilled") setDisease(r3.value);
    if (r4.status === "fulfilled") setRegime(r4.value || []);
    if (r5.status === "fulfilled") setGlobalDisease(r5.value);
    setLoading(false);
    setFetchedAt(new Date());

    // Country-specific enrichment
    api.exposureSites().then(d => setCountryFarms(prev => ({...prev, norway: d}))).catch(handleError("bio_risk_exposure_sites"));
    api.canadaFarms().then(d => setCountryFarms(prev => ({...prev, canada: d}))).catch(handleError("bio_risk_canada_farms"));
    api.icelandFarms().then(d => setCountryFarms(prev => ({...prev, iceland: d}))).catch(handleError("bio_risk_iceland_farms"));
  };

  // Fetch snapshot when slider changes
  const loadSnapshot = async (weekValue: number) => {
    const weekOffset = 7 - weekValue;
    setSnapshotLoading(true);
    try {
      const data = await api.bioRiskSnapshot(weekOffset);
      setSnapshot(data);
    } catch {
      setSnapshot(null);
    }
    setSnapshotLoading(false);
  };

  useEffect(() => { load(); }, []);

  // Load snapshot whenever selectedWeek changes
  useEffect(() => { loadSnapshot(selectedWeek); }, [selectedWeek]);

  // Derive KPI values: use snapshot when available, fall back to live data
  const useSnapshot = snapshot && !snapshotLoading;
  const kpiLiceAvg = useSnapshot ? Number(snapshot.lice?.avg || 0).toFixed(3) : (lice ? Number(lice.avg_adult_female_lice).toFixed(3) : "\u2014");
  const kpiLiceHigh = useSnapshot ? `${snapshot.lice?.high_count || 0} sites > 0.5` : (lice ? `${lice.sites_above_threshold} sites > 0.5` : undefined);
  const kpiLiceNeg = useSnapshot ? (snapshot.lice?.avg || 0) > 0.3 : (lice?.avg_adult_female_lice || 0) > 0.3;

  const bloomCritical = bloom.filter((b: any) => b.risk_level === "CRITICAL" || b.risk_level === "HIGH").length;
  const kpiBloomValue = useSnapshot
    ? (snapshot.bloom?.affected_areas > 0 ? `${snapshot.bloom.affected_areas} HIGH/CRIT` : "All Clear")
    : (bloomCritical > 0 ? `${bloomCritical} HIGH/CRIT` : "All Clear");
  const kpiBloomDelta = useSnapshot
    ? `Risk: ${snapshot.bloom?.risk_level || "LOW"}`
    : `${bloom.length} sites assessed`;
  const kpiBloomNeg = useSnapshot ? (snapshot.bloom?.affected_areas || 0) > 0 : bloomCritical > 0;

  const kpiDiseaseValue = useSnapshot ? (snapshot.disease?.outbreak_count ?? "\u2014") : (disease?.active_cases ?? "\u2014");
  const kpiDiseaseDelta = useSnapshot
    ? (snapshot.disease?.types?.length > 0 ? snapshot.disease.types.slice(0, 2).join(", ") : undefined)
    : (disease?.by_disease ? Object.entries(disease.by_disease).slice(0, 2).map(([k, v]) => `${v} ${String(k).split("(")[0].trim()}`).join(", ") : undefined);
  const kpiDiseaseNeg = useSnapshot ? (snapshot.disease?.outbreak_count || 0) > 5 : (disease?.active_cases || 0) > 5;

  const redPAs = regime.filter((s: any) => s.current_color === "red").length;
  const kpiRegimeValue = useSnapshot
    ? ((snapshot.regime?.pa_summary?.red || 0) > 0 ? `${snapshot.regime.pa_summary.red} Red PAs` : "All Green/Yellow")
    : (redPAs > 0 ? `${redPAs} Red PAs` : "All Green/Yellow");
  const kpiRegimeDelta = useSnapshot
    ? `Status: ${snapshot.regime?.status || "normal"}`
    : `${regime.length} production areas`;
  const kpiRegimeNeg = useSnapshot ? (snapshot.regime?.pa_summary?.red || 0) > 0 : redPAs > 0;

  return (
    <ErrorBoundary fallbackTitle="Bio Risk Map error">
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] flex items-center gap-3">
            <Shield className="w-6 h-6 text-ocean-400" />
            {t("bio_risk.title")}
          </h1>
          <div className="flex items-center gap-2 mt-1">
            <p className="text-sm text-[var(--text-secondary)]">
              Sea lice &middot; Algal bloom &middot; Disease outbreaks &mdash; unified view across 1,815 farms
            </p>
            <FreshnessIndicator lastUpdated={fetchedAt} />
          </div>
        </div>
        <OcButton variant="secondary" size="sm" onClick={load} loading={loading}
          leftIcon={<RefreshCw className="w-3.5 h-3.5" />}>Refresh</OcButton>
      </motion.div>

      {/* KPI Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KPICard
          label={t("bio_risk.lice_layer")}
          value={snapshotLoading ? "\u2014" : kpiLiceAvg}
          delta={snapshotLoading ? undefined : kpiLiceHigh}
          deltaType={kpiLiceNeg ? "negative" : "positive"}
          icon={Bug} delay={0}
        />
        <KPICard
          label={t("bio_risk.bloom_layer")}
          value={snapshotLoading ? "\u2014" : kpiBloomValue}
          delta={snapshotLoading ? undefined : kpiBloomDelta}
          deltaType={kpiBloomNeg ? "negative" : "positive"}
          icon={Leaf} delay={0.04}
        />
        <KPICard
          label={t("bio_risk.disease_layer")}
          value={snapshotLoading ? "\u2014" : kpiDiseaseValue}
          delta={snapshotLoading ? undefined : kpiDiseaseDelta}
          deltaType={kpiDiseaseNeg ? "negative" : "positive"}
          icon={AlertTriangle} delay={0.08}
        />
        <KPICard
          label={t("bio_risk.farm_layer")}
          value={snapshotLoading ? "\u2014" : kpiRegimeValue}
          delta={snapshotLoading ? undefined : kpiRegimeDelta}
          deltaType={kpiRegimeNeg ? "negative" : "positive"}
          icon={Activity} delay={0.12}
        />
      </div>

      {/* Unified Map + Lice Heatmap side-by-side */}
      <div className="grid grid-cols-1 xl:grid-cols-4 gap-4">
        <div className="xl:col-span-3">
          <BioRiskMap />
        </div>
        <GlassCard delay={0.14}>
          <RegionalHeatmap
            title="Lice Pressure by PA"
            metric="score"
            maxValue={1}
            data={regime.map((s: any) => ({
              pa: s.production_area ?? s.pa ?? 0,
              value: Math.round((s.lice_pressure_score ?? 0) * 100) / 100,
              label: `${s.current_color?.toUpperCase() || "Unknown"} zone — ${s.trend || "stable"} trend`,
            } as PADataPoint)).filter((d: PADataPoint) => d.pa >= 1 && d.pa <= 13)}
          />
        </GlassCard>
      </div>

      {/* Time Slider */}
      <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] backdrop-blur-sm px-5 py-4">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-xs font-semibold text-[var(--text-primary)] flex items-center gap-2">
            <Activity className="w-3.5 h-3.5 text-ocean-400" />
            {t("bio_risk.week_offset")}
          </h3>
          <span className="text-[9px] px-2 py-0.5 rounded-full bg-ocean-500/10 text-ocean-400 border border-ocean-500/20">
            {WEEK_LABELS[selectedWeek]} {selectedWeek === 7 ? "(current)" : ""}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-[var(--text-secondary)] whitespace-nowrap">8 weeks ago</span>
          <input
            type="range"
            min={0}
            max={7}
            value={selectedWeek}
            onChange={(e) => setSelectedWeek(Number(e.target.value))}
            className="flex-1 h-1.5 rounded-full appearance-none bg-white/[0.08] cursor-pointer
              [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4
              [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-ocean-400
              [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-ocean-300
              [&::-webkit-slider-thumb]:shadow-[0_0_8px_rgba(0,212,200,0.4)]
              [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:h-4
              [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-ocean-400
              [&::-moz-range-thumb]:border-2 [&::-moz-range-thumb]:border-ocean-300"
          />
          <span className="text-xs text-[var(--text-secondary)] whitespace-nowrap">This week</span>
        </div>
        {/* Week tick marks */}
        <div className="flex justify-between mt-1 px-[2px]" style={{ marginLeft: "82px", marginRight: "72px" }}>
          {WEEK_LABELS.map((lbl, i) => (
            <span
              key={i}
              className={`text-[8px] ${i === selectedWeek ? "text-ocean-400 font-bold" : "text-white/20"}`}
            >
              {lbl}
            </span>
          ))}
        </div>
        {selectedWeek < 7 && (
          <div className="mt-2 flex items-center gap-2">
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-ocean-500/10 text-ocean-400 border border-ocean-500/20 flex items-center gap-1">
              <Activity className="w-2.5 h-2.5" />
              Viewing {snapshot?.week_label || WEEK_LABELS[selectedWeek]} data
            </span>
            <span className="text-[9px] text-[var(--text-secondary)] opacity-60">
              KPI cards reflect historical week &mdash; map shows current data
            </span>
            {snapshotLoading && (
              <RefreshCw className="w-3 h-3 text-ocean-400 animate-spin" />
            )}
          </div>
        )}
      </div>

      {/* Disease outbreak details */}
      {disease?.active_outbreaks?.length > 0 && (
        <GlassCard delay={0.15} accent="rose">
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-400" />
            Active Disease Outbreaks
            <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20 ml-auto animate-pulse">
              {disease.active_cases} active
            </span>
          </h3>
          <div className="space-y-1.5 max-h-[300px] overflow-y-auto">
            {disease.active_outbreaks.map((o: any) => (
              <div key={o.id} className={`flex items-center justify-between p-2.5 rounded-lg border ${
                o.disease?.includes("ISA") ? "bg-rose-500/[0.06] border-rose-500/20" :
                o.disease?.includes("PD") ? "bg-orange-500/[0.06] border-orange-500/20" :
                "bg-amber-500/[0.06] border-amber-500/20"
              }`}>
                <div>
                  <span className="text-[11px] font-semibold text-[var(--text-primary)]">{o.locality_name}</span>
                  <span className="text-[10px] text-[var(--text-secondary)] ml-2">#{o.locality_no}</span>
                  {o.company && (
                    <span className="text-[10px] text-ocean-400 ml-2 font-medium">{o.company}</span>
                  )}
                  <p className="text-[10px] text-[var(--text-secondary)]">
                    {o.disease} {o.subtype ? `(${o.subtype})` : ""} &middot; {o.species}
                  </p>
                </div>
                <div className="text-right">
                  <span className={`text-[10px] font-bold ${
                    o.disease?.includes("ISA") ? "text-rose-400" : "text-orange-400"
                  }`}>
                    {o.days_active}d active
                  </span>
                  {o.diagnosis_date && (
                    <p className="text-[9px] text-[var(--text-secondary)]">
                      Diagnosed: {o.diagnosis_date.split("T")[0]}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
          <p className="text-[9px] text-[var(--text-secondary)] opacity-50 mt-2">
            Source: Mattilsynet (Norwegian Food Safety Authority) &middot; NLOD 2.0
          </p>
        </GlassCard>
      )}

      {/* Global Disease Overview */}
      {globalDisease?.features?.length > 0 && (
        <GlassCard delay={0.2} accent="violet">
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <Shield className="w-4 h-4 text-violet-400" />
            {t("bio_risk.all_countries")}
            <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-violet-500/10 text-violet-400 border border-violet-500/20 ml-auto">
              {globalDisease.features.length} markers across {new Set(globalDisease.features.map((f: any) => f.properties?.country)).size} countries
            </span>
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2">
            {Array.from(new Set(globalDisease.features.map((f: any) => f.properties?.country))).map((country: any) => {
              const countryFeatures = globalDisease.features.filter((f: any) => f.properties?.country === country);
              const critical = countryFeatures.filter((f: any) => f.properties?.severity === "critical").length;
              const high = countryFeatures.filter((f: any) => f.properties?.severity === "high").length;
              const low = countryFeatures.filter((f: any) => f.properties?.severity === "low").length;
              return (
                <div key={country} className="p-2 rounded-lg bg-white/[0.03] border border-white/[0.06] text-center">
                  <p className="text-[10px] font-semibold text-[var(--text-primary)]">{country}</p>
                  <div className="flex justify-center gap-1.5 mt-1">
                    {critical > 0 && <span className="text-[9px] text-rose-400 font-bold">{critical} crit</span>}
                    {high > 0 && <span className="text-[9px] text-orange-400 font-bold">{high} high</span>}
                    {low > 0 && <span className="text-[9px] text-emerald-400">{low} clear</span>}
                    {critical === 0 && high === 0 && low === 0 && <span className="text-[9px] text-[var(--text-secondary)]">{countryFeatures.length}</span>}
                  </div>
                </div>
              );
            })}
          </div>
        </GlassCard>
      )}

      <p className="text-[9px] text-[var(--text-secondary)] text-center opacity-50">
        Lice: BarentsWatch (NLOD 2.0) &middot; Bloom: CMEMS satellite &middot;
        Disease: Mattilsynet + WOAH + DFO + Sernapesca &middot; 7 countries live. Not medical or regulatory advice.
      </p>
    </div>
    </ErrorBoundary>
  );
}
