"use client";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Thermometer, RefreshCw, TrendingUp, TrendingDown, AlertTriangle,
  Globe2, Activity, BarChart3, ArrowUp, ArrowDown, Minus,
} from "lucide-react";
import dynamic from "next/dynamic";
import KPICard from "@/components/KPICard";
import GlassCard from "@/components/GlassCard";
const TrendComparison = dynamic(() => import("@/components/TrendComparison"), { ssr: false, loading: () => <div className="h-48 bg-white/[0.04] rounded-lg animate-pulse" /> });
import { OcButton } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { useApiError } from "@/lib/useApiError";
import { useTranslation, formatNumber, formatCurrency } from "@/lib/i18n";
import ErrorBoundary from "@/components/ErrorBoundary";
const InteractiveChart = dynamic(() => import("@/components/InteractiveChart"), { ssr: false, loading: () => <div className="h-48 bg-white/[0.04] rounded-lg animate-pulse" /> });
import type { DataPoint } from "@/components/InteractiveChart";

/* eslint-disable @typescript-eslint/no-explicit-any */

const FLAG_MAP: Record<string, string> = {
  NO: "\uD83C\uDDF3\uD83C\uDDF4",
  IS: "\uD83C\uDDEE\uD83C\uDDF8",
  "GB-SCT": "\uD83C\uDFF4\uDB40\uDC67\uDB40\uDC62\uDB40\uDC73\uDB40\uDC63\uDB40\uDC74\uDB40\uDC7F",
  FO: "\uD83C\uDDEB\uD83C\uDDF4",
  CL: "\uD83C\uDDE8\uD83C\uDDF1",
  CA: "\uD83C\uDDE8\uD83C\uDDE6",
  IE: "\uD83C\uDDEE\uD83C\uDDEA",
};

function riskColor(score: number): string {
  if (score >= 60) return "text-rose-400";
  if (score >= 30) return "text-amber-400";
  return "text-emerald-400";
}

function riskBg(score: number): string {
  if (score >= 60) return "from-rose-500/20 to-rose-500/5 border-rose-500/30";
  if (score >= 30) return "from-amber-500/20 to-amber-500/5 border-amber-500/30";
  return "from-emerald-500/20 to-emerald-500/5 border-emerald-500/30";
}

function riskBadge(level: string): string {
  if (level === "HIGH") return "bg-rose-500/20 text-rose-400 border-rose-500/30";
  if (level === "MODERATE") return "bg-amber-500/20 text-amber-400 border-amber-500/30";
  return "bg-emerald-500/20 text-emerald-400 border-emerald-500/30";
}

export default function ClimatePage() {
  const { t, locale } = useTranslation();
  const handleError = useApiError();
  const [dashboard, setDashboard] = useState<any>(null);
  const [projections, setProjections] = useState<any>(null);
  const [selectedPa, setSelectedPa] = useState(3);
  const [loading, setLoading] = useState(true);
  const [projLoading, setProjLoading] = useState(false);
  const [yoyData, setYoyData] = useState<any>(null);

  const load = async () => {
    setLoading(true);
    try {
      const [dash] = await Promise.allSettled([
        api.climateRiskScores(),
      ]);
      if (dash.status === "fulfilled") setDashboard(dash.value);
    } catch (e) { handleError("climate_risk_scores")(e); }
    setLoading(false);
  };

  const loadProjections = async (pa: number) => {
    setProjLoading(true);
    try {
      const data = await api.climateProjections(pa, 5);
      setProjections(data);
    } catch (e) { handleError("climate_projections")(e); }
    setProjLoading(false);
  };

  useEffect(() => { load(); }, []);
  useEffect(() => {
    loadProjections(selectedPa);
    api.yoyComparison("sst", selectedPa).then(setYoyData).catch(handleError("climate_yoy_sst"));
  }, [selectedPa]);

  const summary = dashboard?.summary || {};
  const paScores: any[] = dashboard?.pa_scores || [];
  const countryScores: any[] = dashboard?.country_scores || [];
  const highest = summary.highest_risk_pa;
  const lowest = summary.lowest_risk_pa;

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-8 bg-white/5 rounded animate-pulse w-64" />
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-24 bg-white/5 rounded-xl animate-pulse" />
          ))}
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {[...Array(13)].map((_, i) => (
            <div key={i} className="h-32 bg-white/5 rounded-xl animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <ErrorBoundary fallbackTitle="Climate Risk error">
    <div className="space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] flex items-center gap-3">
            <Thermometer className="w-6 h-6 text-ocean-400" />
            {t("climate.title")}
          </h1>
          <p className="text-sm text-[var(--text-secondary)] mt-1">
            Live SST stress, bloom risk &amp; lice pressure per production area
          </p>
        </div>
        <OcButton variant="secondary" size="sm" onClick={load} loading={loading}
          leftIcon={<RefreshCw className="w-3.5 h-3.5" />}>Refresh</OcButton>
      </motion.div>

      {/* KPI Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KPICard
          label={t("climate.heatwave_risk")}
          value={highest ? `PA-${highest.pa}` : "\u2014"}
          delta={highest ? `${formatNumber(highest.climate_risk_score, locale)}/100 \u2014 ${highest.name}` : ""}
          deltaType={highest?.risk_level === "HIGH" ? "negative" : "neutral"}
          icon={AlertTriangle}
          delay={0}
        />
        <KPICard
          label={t("climate.sst_anomaly")}
          value={lowest ? `PA-${lowest.pa}` : "\u2014"}
          delta={lowest ? `${formatNumber(lowest.climate_risk_score, locale)}/100 \u2014 ${lowest.name}` : ""}
          deltaType={lowest?.risk_level === "LOW" ? "positive" : "neutral"}
          icon={Activity}
          delay={0.03}
        />
        <KPICard
          label={t("climate.composite_risk")}
          value={summary.avg_climate_risk != null ? formatNumber(summary.avg_climate_risk, locale, 1) : "\u2014"}
          delta={`${formatNumber(summary.high_risk_count || 0, locale)} of 13 PAs at HIGH risk`}
          deltaType={summary.high_risk_count > 3 ? "negative" : "neutral"}
          icon={BarChart3}
          delay={0.06}
        />
        <KPICard
          label="Trend Direction"
          value={summary.trend_direction ? summary.trend_direction.charAt(0).toUpperCase() + summary.trend_direction.slice(1) : "\u2014"}
          delta="Based on lice + SST signals"
          deltaType={summary.trend_direction === "improving" ? "positive" : summary.trend_direction === "worsening" ? "negative" : "neutral"}
          icon={summary.trend_direction === "improving" ? TrendingDown : TrendingUp}
          delay={0.09}
        />
      </div>

      {/* SST Year-over-Year Trend */}
      {yoyData && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <TrendComparison
            metric="sst"
            label={`PA-${selectedPa} Sea Surface Temp`}
            unit="\u00B0C"
            currentYear={yoyData.current_year || []}
            previousYear={yoyData.previous_year || []}
            twoYearsAgo={yoyData.two_years_ago || []}
            years={yoyData.years}
          />
          {yoyData.current_year?.length > 1 && (
            <GlassCard>
              <InteractiveChart
                title={`PA-${selectedPa} SST Trend`}
                data={(yoyData.current_year as any[]).map((v: any, i: number): DataPoint => ({
                  x: i + 1,
                  y: typeof v === "number" ? v : v?.value ?? 0,
                  label: `Month ${i + 1}`,
                }))}
                unit="\u00B0C"
                color="#38bdf8"
                fillColor="#38bdf8"
                height={180}
              />
            </GlassCard>
          )}
        </div>
      )}

      {/* PA Climate Risk Score Chart */}
      {paScores.length > 0 && (
        <GlassCard>
          <InteractiveChart
            title="Climate Risk by Production Area"
            data={paScores.map((pa: any): DataPoint => ({
              x: pa.pa,
              y: pa.climate_risk_score ?? 0,
              label: `PA-${pa.pa}`,
            }))}
            unit="/100"
            color="#f97316"
            fillColor="#f97316"
            height={180}
            yMin={0}
            yMax={100}
          />
        </GlassCard>
      )}

      {/* PA Risk Grid */}
      <GlassCard>
        <h2 className="text-lg font-semibold text-[var(--text-primary)] mb-4 flex items-center gap-2">
          <Thermometer className="w-5 h-5 text-ocean-400" />
          {t("climate.bloom_risk")}
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
          {(paScores.length > 0 ? paScores : [...Array(13)].map((_, i) => ({ pa: i + 1, name: `PA-${i + 1}`, climate_risk_score: 0, risk_level: "LOW", sst_current_c: null, sst_stress: 0, bloom_risk: 0, lice_pressure: 0, primary_driver: "" }))).map((pa: any) => (
            <motion.button
              key={pa.pa}
              onClick={() => setSelectedPa(pa.pa)}
              whileHover={{ scale: 1.02 }}
              className={`relative p-3 rounded-xl border bg-gradient-to-br transition-all cursor-pointer text-left ${riskBg(pa.climate_risk_score)} ${selectedPa === pa.pa ? "ring-2 ring-ocean-400/50" : ""}`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-medium text-[var(--text-secondary)]">PA-{pa.pa}</span>
                <span className={`text-xs font-bold px-1.5 py-0.5 rounded border ${riskBadge(pa.risk_level)}`}>
                  {pa.risk_level}
                </span>
              </div>
              <div className={`text-2xl font-bold ${riskColor(pa.climate_risk_score)}`}>
                {formatNumber(pa.climate_risk_score, locale)}
              </div>
              <div className="text-[10px] text-[var(--text-secondary)] mt-1 truncate">{pa.name}</div>
              {pa.sst_current_c != null && (
                <div className="text-[10px] text-[var(--text-secondary)] mt-0.5">
                  SST: {formatNumber(pa.sst_current_c, locale, 1)}&deg;C
                </div>
              )}
              {/* Component bars */}
              <div className="mt-2 space-y-1">
                <div className="flex items-center gap-1">
                  <span className="text-[9px] text-[var(--text-secondary)] w-8">SST</span>
                  <div className="flex-1 h-1 bg-white/10 rounded-full overflow-hidden">
                    <div className="h-full bg-sky-400 rounded-full" style={{ width: `${Math.min(100, pa.sst_stress)}%` }} />
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  <span className="text-[9px] text-[var(--text-secondary)] w-8">HAB</span>
                  <div className="flex-1 h-1 bg-white/10 rounded-full overflow-hidden">
                    <div className="h-full bg-lime-400 rounded-full" style={{ width: `${Math.min(100, pa.bloom_risk)}%` }} />
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  <span className="text-[9px] text-[var(--text-secondary)] w-8">Lice</span>
                  <div className="flex-1 h-1 bg-white/10 rounded-full overflow-hidden">
                    <div className="h-full bg-orange-400 rounded-full" style={{ width: `${Math.min(100, pa.lice_pressure)}%` }} />
                  </div>
                </div>
              </div>
            </motion.button>
          ))}
        </div>
      </GlassCard>

      {/* Country Comparison */}
      <GlassCard>
        <h2 className="text-lg font-semibold text-[var(--text-primary)] mb-4 flex items-center gap-2">
          <Globe2 className="w-5 h-5 text-ocean-400" />
          {t("climate.lice_climate_risk")}
        </h2>
        {countryScores.length === 0 ? (
          <p className="text-sm text-[var(--text-secondary)]">{t("common.loading")}</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
            {countryScores.map((c: any) => (
              <div key={c.country}
                className={`p-4 rounded-xl border bg-gradient-to-br ${riskBg(c.climate_risk_score)}`}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-lg">{FLAG_MAP[c.flag] || ""}</span>
                    <span className="font-semibold text-[var(--text-primary)]">{c.country}</span>
                  </div>
                  <span className={`text-xs font-bold px-1.5 py-0.5 rounded border ${riskBadge(c.risk_level)}`}>
                    {c.risk_level}
                  </span>
                </div>
                <div className={`text-3xl font-bold ${riskColor(c.climate_risk_score)}`}>
                  {formatNumber(c.climate_risk_score, locale)}
                  <span className="text-xs text-[var(--text-secondary)] font-normal ml-1">/100</span>
                </div>
                {c.avg_sst_c != null && (
                  <div className="text-xs text-[var(--text-secondary)] mt-2">
                    SST: {formatNumber(c.avg_sst_c, locale, 1)}&deg;C
                  </div>
                )}
                {c.bloom_risk && (
                  <div className="text-xs text-[var(--text-secondary)]">
                    Bloom: {c.bloom_risk}
                  </div>
                )}
                {c.disease_note && (
                  <div className="text-[10px] text-amber-400/80 mt-1">{c.disease_note}</div>
                )}
                {c.highest_risk_pa && (
                  <div className="text-[10px] text-[var(--text-secondary)] mt-1">
                    Peak: {c.highest_risk_pa} ({c.highest_risk_score})
                  </div>
                )}
                <div className="text-[10px] text-[var(--text-secondary)] mt-1 opacity-60">
                  {c.source}
                </div>
              </div>
            ))}
          </div>
        )}
      </GlassCard>

      {/* SST Projections */}
      <GlassCard>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-[var(--text-primary)] flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-ocean-400" />
            {t("climate.projections")}
          </h2>
          <div className="flex items-center gap-2">
            <span className="text-xs text-[var(--text-secondary)]">PA:</span>
            <select
              value={selectedPa}
              onChange={(e) => setSelectedPa(Number(e.target.value))}
              className="bg-white/5 border border-white/10 rounded px-2 py-1 text-xs text-[var(--text-primary)] focus:outline-none focus:ring-1 focus:ring-ocean-400"
            >
              {Array.from({ length: 13 }, (_, i) => i + 1).map((pa) => (
                <option key={pa} value={pa} className="bg-gray-900">PA-{pa}</option>
              ))}
            </select>
          </div>
        </div>

        {projLoading ? (
          <div className="h-40 bg-white/5 rounded-xl animate-pulse" />
        ) : projections ? (
          <div className="space-y-4">
            {/* Trend summary */}
            <div className="flex items-center gap-4 text-sm">
              <div className="flex items-center gap-1.5">
                {projections.trend_direction === "warming" ? (
                  <ArrowUp className="w-4 h-4 text-rose-400" />
                ) : projections.trend_direction === "cooling" ? (
                  <ArrowDown className="w-4 h-4 text-sky-400" />
                ) : (
                  <Minus className="w-4 h-4 text-[var(--text-secondary)]" />
                )}
                <span className={
                  projections.trend_direction === "warming" ? "text-rose-400 font-medium" :
                  projections.trend_direction === "cooling" ? "text-sky-400 font-medium" :
                  "text-[var(--text-secondary)]"
                }>
                  {projections.trend_direction?.charAt(0).toUpperCase() + projections.trend_direction?.slice(1)}
                </span>
              </div>
              {projections.trend_c_per_year != null && (
                <span className="text-[var(--text-secondary)]">
                  {projections.trend_c_per_year > 0 ? "+" : ""}{formatNumber(projections.trend_c_per_year, locale, 2)}&deg;C/year
                </span>
              )}
              <span className="text-[var(--text-secondary)]">
                {formatNumber(projections.data_points || 0, locale)} data points
              </span>
              <span className="text-[var(--text-secondary)]">
                Optimal: {formatNumber(projections.optimal_sst_c, locale, 1)}&deg;C
              </span>
            </div>

            {/* Historical data table */}
            {projections.historical && projections.historical.length > 0 && (
              <div>
                <h3 className="text-xs font-medium text-[var(--text-secondary)] mb-2 uppercase tracking-wider">
                  Historical SST ({projections.pa_name})
                </h3>
                <div className="flex gap-1 flex-wrap">
                  {projections.historical.slice(-12).map((h: any) => (
                    <div key={h.period}
                      className="flex flex-col items-center p-1.5 rounded bg-white/5 text-[10px] min-w-[48px]"
                    >
                      <span className="text-[var(--text-secondary)]">{h.period?.slice(5)}</span>
                      <span className={`font-bold ${
                        h.avg_temp_c > 14 ? "text-rose-400" :
                        h.avg_temp_c > 10 ? "text-amber-400" :
                        h.avg_temp_c > 6 ? "text-emerald-400" : "text-sky-400"
                      }`}>
                        {h.avg_temp_c != null ? formatNumber(h.avg_temp_c, locale, 1) : "\u2014"}&deg;
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Projection bars */}
            {projections.projections && projections.projections.length > 0 && (
              <div>
                <h3 className="text-xs font-medium text-[var(--text-secondary)] mb-2 uppercase tracking-wider">
                  5-Year Projection
                </h3>
                <div className="space-y-2">
                  {projections.projections.map((p: any) => (
                    <div key={p.year} className="flex items-center gap-3">
                      <span className="text-xs text-[var(--text-secondary)] w-10">{p.year}</span>
                      <div className="flex-1 h-6 bg-white/5 rounded-full overflow-hidden relative">
                        <div
                          className={`h-full rounded-full ${
                            p.projected_stress > 60 ? "bg-rose-500/60" :
                            p.projected_stress > 30 ? "bg-amber-500/60" :
                            "bg-emerald-500/60"
                          }`}
                          style={{ width: `${Math.min(100, p.projected_stress)}%` }}
                        />
                        <span className="absolute inset-0 flex items-center justify-center text-[10px] font-medium text-[var(--text-primary)]">
                          {formatNumber(p.projected_sst_c, locale, 1)}&deg;C (stress: {formatNumber(p.projected_stress, locale)})
                        </span>
                      </div>
                      <span className={`text-xs w-16 text-right ${
                        p.delta_from_optimal > 2 ? "text-rose-400" :
                        p.delta_from_optimal > 0 ? "text-amber-400" :
                        "text-emerald-400"
                      }`}>
                        {p.delta_from_optimal > 0 ? "+" : ""}{formatNumber(p.delta_from_optimal, locale, 1)}&deg;C
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {(!projections.historical || projections.historical.length === 0) &&
             (!projections.projections || projections.projections.length === 0) && (
              <p className="text-sm text-[var(--text-secondary)]">
                Insufficient historical data for PA-{selectedPa}. SST observations from MET.no Frost required.
              </p>
            )}
          </div>
        ) : (
          <p className="text-sm text-[var(--text-secondary)]">{t("common.no_data")}</p>
        )}
      </GlassCard>
    </div>
    </ErrorBoundary>
  );
}
