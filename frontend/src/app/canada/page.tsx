"use client";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Globe2, RefreshCw, Fish, AlertTriangle, Activity,
  Thermometer, Shield, Clock, TrendingUp, BarChart3, Download,
} from "lucide-react";
import KPICard from "@/components/KPICard";
import GlassCard from "@/components/GlassCard";
import TrendComparison from "@/components/TrendComparison";
import { OcButton } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { useApiError } from "@/lib/useApiError";
import { useTranslation } from "@/lib/i18n";
import { exportToCSV } from "@/lib/export";

/* eslint-disable @typescript-eslint/no-explicit-any */

const REGION_COLORS: Record<string, string> = {
  "Discovery Islands": "text-ocean-400",
  "Broughton Archipelago": "text-emerald-400",
  "Clayoquot Sound": "text-amber-400",
  "Quatsino Sound": "text-violet-400",
  "Nootka Sound": "text-rose-400",
  "Klemtu / Bella Bella": "text-sky-400",
  "Campbell River": "text-orange-400",
  "Tofino": "text-pink-400",
};

export default function CanadaPage() {
  const { t } = useTranslation();
  const handleError = useApiError();
  const [snapshot, setSnapshot] = useState<any>(null);
  const [liceByRegion, setLiceByRegion] = useState<any>(null);
  const [norwayLice, setNorwayLice] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [yoyLice, setYoyLice] = useState<any>(null);

  const load = async () => {
    setLoading(true);
    try {
      const [snap, regions, norLice] = await Promise.allSettled([
        api.canadaSnapshot(),
        api.canadaLiceByRegion(),
        api.liceSummary(),
      ]);
      if (snap.status === "fulfilled") setSnapshot(snap.value);
      if (regions.status === "fulfilled") setLiceByRegion(regions.value);
      if (norLice.status === "fulfilled") setNorwayLice(norLice.value?.avg_adult_female_lice || 0);
    } catch (e) { handleError("canada_snapshot")(e); }
    setLoading(false);
  };

  useEffect(() => {
    load();
    api.yoyComparison("lice").then(setYoyLice).catch(handleError("canada_yoy_lice"));
  }, []);

  // June 2029 countdown
  const deadline = new Date("2029-06-30T00:00:00Z");
  const now = new Date();
  const daysRemaining = Math.max(0, Math.floor((deadline.getTime() - now.getTime()) / (1000 * 60 * 60 * 24)));

  const lice = snapshot?.lice || {};
  const sea = snapshot?.sea_conditions || {};

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] flex items-center gap-3">
            <span className="text-lg">🇨🇦</span>
            {t("canada.title")}
          </h1>
          <p className="text-sm text-[var(--text-secondary)] mt-1">
            DFO open data &mdash; richest public aquaculture dataset globally
          </p>
        </div>
        <OcButton variant="secondary" size="sm" onClick={load} loading={loading}
          leftIcon={<RefreshCw className="w-3.5 h-3.5" />}>Refresh</OcButton>
      </motion.div>

      {/* KPI Row */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <KPICard
          label="Avg Lice / Fish"
          value={lice.avg_per_fish != null ? lice.avg_per_fish.toFixed(1) : "—"}
          delta={lice.avg_per_fish > 3 ? "ABOVE BC THRESHOLD (3.0)" : "Below threshold"}
          deltaType={lice.avg_per_fish > 3 ? "negative" : "positive"}
          icon={Fish}
          delay={0}
        />
        <KPICard
          label="Farms Reporting"
          value={lice.total_farms_reporting || "—"}
          delta={`${lice.farms_above_threshold || 0} above threshold`}
          deltaType={lice.farms_above_threshold > 5 ? "negative" : "neutral"}
          icon={BarChart3}
          delay={0.03}
        />
        <KPICard
          label="Mortality Events"
          value={snapshot?.mortality_events_6m || "—"}
          delta="Last 6 months (DFO)"
          deltaType={snapshot?.mortality_events_6m > 10 ? "negative" : "neutral"}
          icon={AlertTriangle}
          delay={0.06}
        />
        <KPICard
          label="Disease Events"
          value={snapshot?.disease_events_12m || "—"}
          delta="Last 12 months (DFO)"
          deltaType={snapshot?.disease_events_12m > 10 ? "negative" : "neutral"}
          icon={Shield}
          delay={0.09}
        />
        <KPICard
          label="BC Waters SST"
          value={sea.sst_c != null ? `${sea.sst_c}°C` : "—"}
          delta={`Bloom: ${sea.bloom_risk || "unknown"}`}
          deltaType={sea.bloom_risk === "HIGH" || sea.bloom_risk === "CRITICAL" ? "negative" : "positive"}
          icon={Thermometer}
          delay={0.12}
        />
      </div>

      {/* Lice Year-over-Year (Norway baseline for BC comparison) */}
      {yoyLice && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <TrendComparison
            metric="lice"
            label="Norway Lice YoY (BC comparison)"
            unit="lice/fish"
            currentYear={yoyLice.current_year || []}
            previousYear={yoyLice.previous_year || []}
            twoYearsAgo={yoyLice.two_years_ago || []}
            years={yoyLice.years}
          />
        </div>
      )}

      {/* June 2029 Transition Banner */}
      <GlassCard delay={0.15} accent="amber">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-2xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center flex-shrink-0">
            <Clock className="w-7 h-7 text-amber-400" />
          </div>
          <div className="flex-1">
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">
              {t("canada.ban_countdown")}
            </h3>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">
              All BC open net-pen salmon farming must cease by June 30, 2029 (federal policy).
              Estimated supply impact: ~8,000-10,000 tonnes removed from global market.
            </p>
          </div>
          <div className="text-right flex-shrink-0">
            <p className="text-2xl font-bold text-amber-400 tabular-nums">{daysRemaining}</p>
            <p className="text-[10px] text-[var(--text-secondary)]">{t("canada.days_remaining")}</p>
          </div>
        </div>
      </GlassCard>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Regional Lice Table */}
        <GlassCard delay={0.18}>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold flex items-center gap-2">
              <Fish className="w-4 h-4 text-ocean-400" />
              {t("canada.bc_regions")}
              <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-ocean-500/10 text-ocean-400 border border-ocean-500/20">
                BC threshold: 3.0 motile/fish
              </span>
            </h3>
            {liceByRegion && (
              <OcButton variant="ghost" size="sm" leftIcon={<Download className="w-3.5 h-3.5" />}
                onClick={() => exportToCSV(Object.entries(liceByRegion).map(([region, data]: [string, any]) => {
                  const latest = Array.isArray(data) && data.length > 0 ? data[data.length - 1] : null;
                  return { Region: region, "Months of Data": Array.isArray(data) ? data.length : 0,
                    "Latest Avg Lice": latest?.avg_lice?.toFixed(2) || "",
                    "Above Threshold": (latest?.avg_lice || 0) > 3 ? "Yes" : "No" };
                }), "canada_lice_by_region")}>Export CSV</OcButton>
            )}
          </div>
          <div className="space-y-1.5">
            {liceByRegion && Object.entries(liceByRegion).map(([region, data]: [string, any]) => {
              const latest = Array.isArray(data) && data.length > 0 ? data[data.length - 1] : null;
              const avg = latest?.avg_lice || 0;
              return (
                <div key={region} className="flex items-center justify-between p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                  <span className={`text-[11px] font-medium ${REGION_COLORS[region] || "text-[var(--text-primary)]"}`}>
                    {region}
                  </span>
                  <div className="flex items-center gap-3">
                    <span className="text-[10px] text-[var(--text-secondary)]">
                      {Array.isArray(data) ? data.length : 0} months
                    </span>
                    <span className={`text-[11px] font-mono font-bold ${
                      avg > 3 ? "text-rose-400" : avg > 1 ? "text-amber-400" : "text-emerald-400"
                    }`}>
                      {avg > 0 ? avg.toFixed(1) : "—"}
                    </span>
                  </div>
                </div>
              );
            })}
            {!liceByRegion && (
              <p className="text-xs text-[var(--text-secondary)] py-4 text-center opacity-60">
                Loading DFO lice data...
              </p>
            )}
          </div>
        </GlassCard>

        {/* BC vs Norway Comparison */}
        <GlassCard delay={0.21}>
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-violet-400" />
            BC vs Norway Comparison
          </h3>
          <div className="space-y-3">
            {/* Lice comparison */}
            <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06]">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] text-[var(--text-secondary)] uppercase tracking-wider">Avg Lice / Fish</span>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="text-center">
                  <p className="text-[10px] text-[var(--text-secondary)]">🇨🇦 BC (DFO)</p>
                  <p className={`text-xl font-bold ${
                    (lice.avg_per_fish || 0) > 3 ? "text-rose-400" : "text-emerald-400"
                  }`}>
                    {lice.avg_per_fish?.toFixed(1) || "—"}
                  </p>
                  <p className="text-[9px] text-[var(--text-secondary)]">threshold: 3.0</p>
                </div>
                <div className="text-center">
                  <p className="text-[10px] text-[var(--text-secondary)]">🇳🇴 Norway (BW)</p>
                  <p className={`text-xl font-bold ${
                    norwayLice > 0.5 ? "text-rose-400" : "text-emerald-400"
                  }`}>
                    {norwayLice > 0 ? norwayLice.toFixed(3) : "—"}
                  </p>
                  <p className="text-[9px] text-[var(--text-secondary)]">threshold: 0.5</p>
                </div>
              </div>
            </div>

            {/* Data availability */}
            <div className="p-3 rounded-xl bg-ocean-500/[0.04] border border-ocean-500/[0.1]">
              <p className="text-[10px] font-semibold text-ocean-400 mb-1">Data Sources</p>
              <div className="space-y-1 text-[10px] text-[var(--text-secondary)]">
                <p>DFO Industry Sea Lice Counts (2011-2025, monthly, per-farm)</p>
                <p>DFO Sea Lice Audits (independent government verification)</p>
                <p>DFO Mortality Events (daily, per-facility, with cause)</p>
                <p>DFO Fish Health Events (disease requiring vet involvement)</p>
                <p>CMEMS Global SST + Chlorophyll for BC waters</p>
              </div>
              <p className="text-[9px] text-ocean-400 mt-2">
                Open Government Licence — Canada. No auth required.
              </p>
            </div>
          </div>
        </GlassCard>
      </div>

      {/* Insights */}
      {snapshot?.insights?.length > 0 && (
        <GlassCard delay={0.24} accent="ocean">
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <Activity className="w-4 h-4 text-ocean-400" />
            Intelligence
          </h3>
          <div className="space-y-2">
            {snapshot.insights.map((ins: string, i: number) => (
              <div key={i} className="flex items-start gap-2 p-2.5 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                <Globe2 className="w-3.5 h-3.5 text-ocean-400 flex-shrink-0 mt-0.5" />
                <p className="text-[11px] text-[var(--text-primary)] leading-relaxed">{ins}</p>
              </div>
            ))}
          </div>
        </GlassCard>
      )}

      <p className="text-[9px] text-[var(--text-secondary)] text-center opacity-50">
        Data: DFO Open Data (open.canada.ca) — Open Government Licence Canada.
        CMEMS (Copernicus) for ocean conditions. BarentsWatch for Norway comparison.
        Not financial or regulatory advice.
      </p>
    </div>
  );
}
