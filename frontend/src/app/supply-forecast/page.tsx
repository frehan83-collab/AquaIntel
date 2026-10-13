/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  TrendingUp, Fish, BarChart3, Activity, Target,
  RefreshCw, Zap, ArrowUpDown,
} from "lucide-react";
import dynamic from "next/dynamic";
import GlassCard from "@/components/GlassCard";
import KPICard from "@/components/KPICard";
const ConfidenceBand = dynamic(() => import("@/components/ConfidenceBand"), { ssr: false, loading: () => <div className="h-48 bg-white/[0.04] rounded-lg animate-pulse" /> });
const InteractiveChart = dynamic(() => import("@/components/InteractiveChart"), { ssr: false, loading: () => <div className="h-48 bg-white/[0.04] rounded-lg animate-pulse" /> });
import type { DataPoint } from "@/components/InteractiveChart";
import { OcButton } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { useTranslation, formatNumber, formatCurrency } from "@/lib/i18n";
import DataQualityBadge from "@/components/DataQualityBadge";

function PricePathChart({ weekly }: { weekly: Array<{ mid_nok_kg: number; p10?: number; p90?: number }> }) {
  if (!weekly?.length) return null;
  const W = 320;
  const H = 96;
  const PAD = 6;
  const lo = (p: { mid_nok_kg: number; p10?: number }) => p.p10 ?? p.mid_nok_kg;
  const hi = (p: { mid_nok_kg: number; p90?: number }) => p.p90 ?? p.mid_nok_kg;
  const min = Math.min(...weekly.map(lo));
  const max = Math.max(...weekly.map(hi));
  const span = Math.max(max - min, 1e-9);
  const x = (i: number) => PAD + (i / Math.max(weekly.length - 1, 1)) * (W - 2 * PAD);
  const y = (v: number) => H - PAD - ((v - min) / span) * (H - 2 * PAD);
  const band = [
    ...weekly.map((p, i) => `${x(i)},${y(hi(p))}`),
    ...[...weekly].reverse().map((p, j) => `${x(weekly.length - 1 - j)},${y(lo(p))}`),
  ].join(" ");
  const mid = weekly
    .map((p, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(p.mid_nok_kg).toFixed(1)}`)
    .join(" ");
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="w-full h-24"
      preserveAspectRatio="none"
      role="img"
      aria-label="2-20 week price path with p10-p90 band"
    >
      <polygon points={band} fill="rgba(56,189,248,0.14)" />
      <path d={mid} fill="none" stroke="#38bdf8" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}


export default function SupplyForecastPage() {
  const [summary, setSummary] = useState<any>(null);
  const [smoltData, setSmoltData] = useState<any>(null);
  const [cohortData, setCohortData] = useState<any>(null);
  const [intel, setIntel] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const { t, locale } = useTranslation();

  const load = async () => {
    setLoading(true);
    try {
      const [sum, smolt, cohort, intelRes] = await Promise.allSettled([
        api.supplySummary(),
        api.smoltForecast(18),
        api.cohortTimeline(),
        api.supplyDemandBalance(),
      ]);
      if (sum.status === "fulfilled") setSummary(sum.value);
      if (smolt.status === "fulfilled") setSmoltData(smolt.value);
      if (cohort.status === "fulfilled") setCohortData(cohort.value);
      if (intelRes.status === "fulfilled") setIntel(intelRes.value);
    } catch { /* empty */ }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const pipeline = summary?.pipeline || [];
  const cohorts = summary?.cohorts || [];
  const balance = summary?.demand_balance || {};
  const pf = intel?.price_forecast;

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] flex items-center gap-3">
            <TrendingUp className="w-6 h-6 text-ocean-400" />
            {t("supply.title")}
          </h1>
          <div className="flex items-center gap-2 mt-1">
            <p className="text-sm text-[var(--text-secondary)]">
              {t("supply.smolt_to_harvest")}
            </p>
            <DataQualityBadge source="Smolt Model" quality="live" />
          </div>
        </div>
        <OcButton variant="secondary" size="sm" onClick={load} loading={loading}
          leftIcon={<RefreshCw className="w-3.5 h-3.5" />}>Refresh</OcButton>
      </motion.div>

      {/* KPIs */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <KPICard label="Next Quarter Harvest"
            value={`${formatNumber((summary.next_quarter_harvest_tonnes || 0) / 1000, locale)}k t`}
            icon={Fish} delay={0} />
          <KPICard label="Smolt Releases YTD"
            value={`${summary.smolt_releases_ytd_millions != null ? formatNumber(summary.smolt_releases_ytd_millions, locale) : "\u2014"}M`}
            icon={Activity} delay={0.03} />
          <KPICard label="Supply Growth YoY"
            value={`+${formatNumber(summary.supply_growth_yoy_pct || 0, locale, 1)}%`}
            deltaType="positive" icon={TrendingUp} delay={0.06} />
          <KPICard label="MAB Utilization"
            value={`${formatNumber(summary.mab_utilization_pct || 0, locale, 1)}%`}
            delta="National capacity" icon={Target} delay={0.09} />
          <KPICard label="Price Pressure"
            value={summary.price_pressure || "neutral"}
            deltaType={summary.price_pressure === "bullish" ? "positive" : summary.price_pressure === "bearish" ? "negative" : "neutral"}
            icon={Zap} delay={0.12} />
        </div>
      )}

      {/* Supply Pipeline */}
      {pipeline.length > 0 && (
        <GlassCard delay={0.1} accent="ocean">
          <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-ocean-400" />
            {t("supply.monthly_supply")}
            <span className="ml-auto text-[10px] px-2 py-0.5 rounded-full bg-ocean-500/10 text-ocean-400 border border-ocean-500/20">
              Cohort-based model
            </span>
          </h3>

          <div className="space-y-1">
            {pipeline.map((p: any, i: number) => {
              const maxH = Math.max(...pipeline.map((pp: any) => pp.projected_harvest_tonnes || 0));
              const pct = maxH > 0 ? ((p.projected_harvest_tonnes || 0) / maxH) * 100 : 0;
              const isDeficit = (p.balance || 0) < 0;
              return (
                <div key={i} className="flex items-center gap-3">
                  <span className="text-[10px] font-mono text-[var(--text-secondary)] w-16 flex-shrink-0">{p.month_label}</span>
                  <div className="flex-1 h-4 bg-white/[0.04] rounded overflow-hidden relative">
                    <div
                      className={`h-full rounded ${isDeficit ? "bg-rose-500/60" : "bg-ocean-500/60"}`}
                      style={{ width: `${pct}%` }}
                    />
                    {/* Demand marker */}
                    {maxH > 0 && (
                      <div
                        className="absolute top-0 h-full w-0.5 bg-amber-400/60"
                        style={{ left: `${((p.demand_tonnes || 0) / maxH) * 100}%` }}
                      />
                    )}
                  </div>
                  <span className="text-[10px] font-mono text-[var(--text-secondary)] w-14 text-right flex-shrink-0">
                    {formatNumber((p.projected_harvest_tonnes || 0) / 1000, locale)}k t
                  </span>
                  <span className={`text-[9px] font-semibold w-8 text-right flex-shrink-0 ${isDeficit ? "text-rose-400" : "text-emerald-400"}`}>
                    {(p.balance || 0) > 0 ? "+" : ""}{formatNumber((p.balance || 0) / 1000, locale)}k
                  </span>
                </div>
              );
            })}
          </div>
          <div className="flex items-center gap-4 mt-3 text-[9px] text-[var(--text-secondary)]">
            <span className="flex items-center gap-1"><div className="w-3 h-2 bg-ocean-500/60 rounded" /> Supply</span>
            <span className="flex items-center gap-1"><div className="w-3 h-2 bg-rose-500/60 rounded" /> Deficit month</span>
            <span className="flex items-center gap-1"><div className="w-0.5 h-2 bg-amber-400/60" /> Demand line</span>
          </div>
        </GlassCard>
      )}

      {/* Interactive Supply Pipeline Chart */}
      {pipeline.length > 0 && (
        <GlassCard delay={0.12} accent="ocean">
          <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-ocean-400" />
            Supply Pipeline (Interactive)
            <span className="ml-auto text-[10px] px-2 py-0.5 rounded-full bg-ocean-500/10 text-ocean-400 border border-ocean-500/20">
              Crosshair hover
            </span>
          </h3>
          <InteractiveChart
            data={pipeline.map((p: any, i: number) => ({
              x: i,
              y: (p.projected_harvest_tonnes || 0) / 1000,
              label: p.month_label || `M+${i + 1}`,
            } as DataPoint))}
            title=""
            unit=" kt"
            height={220}
            color="#00D4C8"
            bands={pipeline.map((p: any) => ({
              lo: Math.max(0, ((p.projected_harvest_tonnes || 0) - (p.projected_harvest_tonnes || 0) * 0.1) / 1000),
              hi: ((p.projected_harvest_tonnes || 0) + (p.projected_harvest_tonnes || 0) * 0.1) / 1000,
            }))}
          />
        </GlassCard>
      )}

      {/* Supply Confidence Bands */}
      {pipeline.length >= 2 ? (
        <GlassCard delay={0.13} accent="violet">
          <ConfidenceBand
            title="Supply Forecast with Uncertainty Bands"
            unit=" kt"
            xLabel="Month"
            yLabel="Harvest"
            data={pipeline.map((p: any, i: number) => {
              const harvest = (p.projected_harvest_tonnes || 0) / 1000;
              // Use confidence intervals from smolt model if available, else derive from pipeline
              const hasCI = p.lo80 != null && p.hi80 != null;
              return {
                x: i + 1,
                y: harvest,
                lo80: hasCI ? (p.lo80 / 1000) : harvest * 0.9,
                hi80: hasCI ? (p.hi80 / 1000) : harvest * 1.1,
                lo95: p.lo95 != null ? (p.lo95 / 1000) : harvest * 0.82,
                hi95: p.hi95 != null ? (p.hi95 / 1000) : harvest * 1.18,
              };
            })}
          />
          {!pipeline.some((p: any) => p.lo80 != null) && (
            <p className="text-[9px] text-[var(--text-secondary)] mt-2 italic">
              Bands derived from +/-10% (80%) and +/-18% (95%) estimates.
              Full confidence intervals will be available when the smolt model produces interval estimates.
            </p>
          )}
        </GlassCard>
      ) : (
        <GlassCard delay={0.13}>
          <p className="text-xs text-[var(--text-secondary)] italic">
            {loading ? t("common.loading") : t("common.no_data")}
          </p>
        </GlassCard>
      )}

      {/* Cohort Pipeline + Demand Balance */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

        {/* Active Cohorts */}
        {cohorts.length > 0 && (
          <GlassCard delay={0.15} accent="violet">
            <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
              <Fish className="w-4 h-4 text-violet-400" />
              {t("supply.cohorts")} ({cohorts.length})
            </h3>
            <div className="overflow-y-auto max-h-[350px] space-y-1.5">
              {cohorts.map((c: any, i: number) => {
                const stageColor =
                  c.stage === "harvestable" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" :
                  c.stage === "pre-harvest" ? "bg-amber-500/10 text-amber-400 border-amber-500/20" :
                  c.stage === "grower" ? "bg-ocean-500/10 text-ocean-400 border-ocean-500/20" :
                  "bg-white/[0.04] text-[var(--text-secondary)] border-white/[0.08]";
                return (
                  <div key={i} className="flex items-center justify-between p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-mono text-[var(--text-secondary)]">{c.intake}</span>
                      <span className={`text-[9px] font-semibold px-1.5 py-0.5 rounded border ${stageColor}`}>
                        {c.stage}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 text-[10px]">
                      <span className="text-[var(--text-secondary)]">{c.n_smolt_millions != null ? formatNumber(c.n_smolt_millions, locale, 1) : "\u2014"}M smolt ({t("supply.survival_rate")})</span>
                      <span className="text-[var(--text-primary)] font-semibold">{c.current_weight_kg != null ? formatNumber(c.current_weight_kg, locale, 2) : "\u2014"}kg {t("supply.harvest_weight")}</span>
                      <span className="text-[var(--text-secondary)]">&rarr; {c.harvest_month}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </GlassCard>
        )}

        {/* Supply-Demand Balance */}
        <GlassCard delay={0.2} accent={balance.signal === "oversupply" ? "rose" : balance.signal === "undersupply" ? "emerald" : "amber"}>
          <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
            <ArrowUpDown className="w-4 h-4 text-amber-400" />
            {t("supply.demand_balance")}
          </h3>
          <div className="space-y-4">
            <div className="grid grid-cols-3 gap-3">
              <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06] text-center">
                <div className="text-[10px] text-[var(--text-secondary)] uppercase tracking-wider mb-1">Supply</div>
                <div className="text-lg font-bold text-[var(--text-primary)]">
                  {formatNumber((balance.total_supply_tonnes || 0) / 1000, locale)}k t
                </div>
              </div>
              <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06] text-center">
                <div className="text-[10px] text-[var(--text-secondary)] uppercase tracking-wider mb-1">Demand</div>
                <div className="text-lg font-bold text-[var(--text-primary)]">
                  {formatNumber((balance.total_demand_tonnes || 0) / 1000, locale)}k t
                </div>
              </div>
              <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06] text-center">
                <div className="text-[10px] text-[var(--text-secondary)] uppercase tracking-wider mb-1">Balance</div>
                <div className={`text-lg font-bold ${(balance.balance_tonnes || 0) > 0 ? "text-rose-400" : "text-emerald-400"}`}>
                  {(balance.balance_tonnes || 0) > 0 ? "+" : ""}{formatNumber((balance.balance_tonnes || 0) / 1000, locale)}k t
                </div>
              </div>
            </div>
            <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06]">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-[var(--text-secondary)]">Price Pressure Signal</span>
                <span className="text-[9px] text-[var(--text-secondary)] italic">{t("supply.smolt_model_tag")}</span>
                <span className={`text-sm font-bold ${
                  balance.price_pressure === "bullish" ? "text-emerald-400" :
                  balance.price_pressure === "bearish" ? "text-rose-400" : "text-amber-400"
                }`}>
                  {(balance.price_pressure || "neutral").toUpperCase()}
                </span>
              </div>
              <p className="text-[10px] text-[var(--text-secondary)]">
                {balance.signal === "oversupply"
                  ? t("supply.surplus")
                  : balance.signal === "undersupply"
                  ? t("supply.deficit")
                  : t("supply.balanced")}
              </p>
            </div>
            {pf && pf.weekly?.length > 0 && (
              <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06] space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-[var(--text-secondary)]">{t("supply.price_path")}</span>
                  <DataQualityBadge provenance={intel?.data_provenance} />
                </div>
                <PricePathChart weekly={pf.weekly} />
                <div className="flex items-center justify-between text-[9px] text-[var(--text-secondary)] font-mono">
                  <span>
                    {pf.weekly[0].year}W{String(pf.weekly[0].iso_week).padStart(2, "0")}
                  </span>
                  <span>
                    {pf.weekly[pf.weekly.length - 1].year}W
                    {String(pf.weekly[pf.weekly.length - 1].iso_week).padStart(2, "0")}
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div className="p-2 rounded-lg bg-white/[0.02]">
                    <div className="text-[9px] uppercase tracking-wider text-[var(--text-secondary)] mb-0.5">Spot</div>
                    <div className="text-sm font-bold text-[var(--text-primary)]">
                      {formatNumber(pf.spot_nok_kg, locale, 1)}
                    </div>
                    <div className="text-[9px] text-[var(--text-secondary)] font-mono">
                      {pf.spot_week}
                      {pf.spot_lag_weeks != null ? ` · lag ${pf.spot_lag_weeks}w` : ""}
                    </div>
                  </div>
                  <div className="p-2 rounded-lg bg-white/[0.02]">
                    <div className="text-[9px] uppercase tracking-wider text-[var(--text-secondary)] mb-0.5">
                      {t("supply.spot_vs_seasonal")}
                    </div>
                    <div className={`text-sm font-bold ${(pf.gap_vs_seasonal_pct || 0) >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                      {(pf.gap_vs_seasonal_pct || 0) >= 0 ? "+" : ""}
                      {formatNumber(pf.gap_vs_seasonal_pct, locale, 1)}%
                    </div>
                  </div>
                  <div className="p-2 rounded-lg bg-white/[0.02]">
                    <div className="text-[9px] uppercase tracking-wider text-[var(--text-secondary)] mb-0.5">
                      {t("supply.forecast_band")}
                    </div>
                    <div className="text-sm font-bold text-ocean-400">p10–p90</div>
                  </div>
                </div>
                {pf.backtest?.mape ? (
                  <div className="flex items-center justify-between text-[10px]">
                    <span className="text-[var(--text-secondary)]">
                      {t("supply.backtest")}
                      {pf.backtest.n_origins != null ? ` · ${pf.backtest.n_origins} origins` : ""}
                    </span>
                    <span className="font-mono text-[var(--text-primary)]">
                      MAPE 2w {pf.backtest.mape["2"] ?? "–"}% → 20w {pf.backtest.mape["20"] ?? "–"}%
                    </span>
                  </div>
                ) : (
                  <p className="text-[10px] text-amber-400/80">{t("supply.backtest_missing")}</p>
                )}
                {pf.bands_source !== "walk_forward_residuals" && (
                  <p className="text-[10px] text-amber-400/80">{t("supply.bands_fallback")}</p>
                )}
                <p className="text-[9px] leading-relaxed text-[var(--text-secondary)]">{pf.method}</p>
              </div>
            )}
          </div>
        </GlassCard>
      </div>

      {/* Smolt Forecast — Monthly Releases & Harvest Projections */}
      {smoltData && (
        <GlassCard delay={0.22} accent="ocean">
          <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
            <Fish className="w-4 h-4 text-ocean-400" />
            Smolt Forecast — Monthly Harvest Projections
            <span className="ml-auto text-[10px] px-2 py-0.5 rounded-full bg-ocean-500/10 text-ocean-400 border border-ocean-500/20">
              {smoltData.horizon_months || 18} months
            </span>
          </h3>
          {smoltData.monthly_projections?.length > 0 ? (
            <div className="space-y-1">
              {smoltData.monthly_projections.map((m: any, i: number) => {
                const maxH = Math.max(...(smoltData.monthly_projections || []).map((p: any) => p.harvest_tonnes || p.projected_harvest_tonnes || 0));
                const val = m.harvest_tonnes || m.projected_harvest_tonnes || 0;
                const pct = maxH > 0 ? (val / maxH) * 100 : 0;
                return (
                  <div key={i} className="flex items-center gap-3">
                    <span className="text-[10px] font-mono text-[var(--text-secondary)] w-16 flex-shrink-0">
                      {m.month || m.month_label || `M+${i + 1}`}
                    </span>
                    <div className="flex-1 h-3.5 bg-white/[0.04] rounded overflow-hidden">
                      <div className="h-full rounded bg-ocean-500/50" style={{ width: `${pct}%` }} />
                    </div>
                    <span className="text-[10px] font-mono text-[var(--text-secondary)] w-16 text-right flex-shrink-0">
                      {formatNumber(val / 1000, locale, 1)}k t
                    </span>
                    {m.smolt_releases != null && (
                      <span className="text-[9px] text-violet-400 w-16 text-right flex-shrink-0">
                        {formatNumber(m.smolt_releases / 1_000_000, locale, 1)}M smolt
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="text-xs text-[var(--text-secondary)]">{t("common.no_data")}</p>
          )}
          {smoltData.total_harvest_tonnes != null && (
            <div className="mt-3 pt-3 border-t border-white/[0.06] flex items-center justify-between text-xs">
              <span className="text-[var(--text-secondary)]">Total projected harvest</span>
              <span className="font-bold text-[var(--text-primary)]">
                {formatNumber(smoltData.total_harvest_tonnes / 1000, locale)}k tonnes
              </span>
            </div>
          )}
        </GlassCard>
      )}

      {/* Cohort Timeline */}
      {cohortData && (
        <GlassCard delay={0.25} accent="violet">
          <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
            <Activity className="w-4 h-4 text-violet-400" />
            Cohort Timeline
            <span className="ml-auto text-[10px] px-2 py-0.5 rounded-full bg-violet-500/10 text-violet-400 border border-violet-500/20">
              {(Array.isArray(cohortData) ? cohortData : cohortData?.cohorts || []).length} cohorts
            </span>
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-[11px]">
              <thead>
                <tr className="border-b border-white/[0.06]">
                  <th className="text-left py-2 px-2 text-[var(--text-secondary)] font-medium uppercase tracking-wider">Intake</th>
                  <th className="text-left py-2 px-2 text-[var(--text-secondary)] font-medium uppercase tracking-wider">Stage</th>
                  <th className="text-right py-2 px-2 text-[var(--text-secondary)] font-medium uppercase tracking-wider">Smolt (M)</th>
                  <th className="text-right py-2 px-2 text-[var(--text-secondary)] font-medium uppercase tracking-wider">Weight (kg)</th>
                  <th className="text-right py-2 px-2 text-[var(--text-secondary)] font-medium uppercase tracking-wider">Harvest</th>
                  <th className="text-right py-2 px-2 text-[var(--text-secondary)] font-medium uppercase tracking-wider">Volume (t)</th>
                </tr>
              </thead>
              <tbody>
                {(Array.isArray(cohortData) ? cohortData : cohortData?.cohorts || []).map((c: any, i: number) => {
                  const stageColor =
                    c.stage === "harvestable" ? "text-emerald-400" :
                    c.stage === "pre-harvest" ? "text-amber-400" :
                    c.stage === "grower" ? "text-ocean-400" : "text-[var(--text-secondary)]";
                  return (
                    <tr key={i} className="border-b border-white/[0.04] hover:bg-white/[0.02]">
                      <td className="py-2 px-2 font-mono text-[var(--text-secondary)]">{c.intake || c.intake_month || "\u2014"}</td>
                      <td className={`py-2 px-2 font-semibold ${stageColor}`}>{c.stage || "\u2014"}</td>
                      <td className="py-2 px-2 text-right font-mono">{c.n_smolt_millions != null ? formatNumber(c.n_smolt_millions, locale, 1) : "\u2014"}</td>
                      <td className="py-2 px-2 text-right font-mono">{c.current_weight_kg != null ? formatNumber(c.current_weight_kg, locale, 2) : "\u2014"}</td>
                      <td className="py-2 px-2 text-right text-[var(--text-secondary)]">{c.harvest_month || c.expected_harvest || "\u2014"}</td>
                      <td className="py-2 px-2 text-right font-mono font-semibold">
                        {c.projected_harvest_tonnes != null ? formatNumber(c.projected_harvest_tonnes / 1000, locale, 1) + "k" : "\u2014"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </GlassCard>
      )}

      {/* Attribution */}
      <p className="text-[10px] text-[var(--text-secondary)] text-center opacity-60">
        Cohort growth model: temperature-dependent SGR (Austreng 1987). Constants: Mowi Industry Handbook 2025.
        Demand proxy: SSB export seasonality. Not financial or regulatory advice.
      </p>
    </div>
  );
}
