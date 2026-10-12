"use client";
import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  Wheat, TrendingUp, TrendingDown, DollarSign, BarChart3,
  RefreshCw, AlertTriangle, Minus, Fish, Globe2, Download,
} from "lucide-react";
import { exportToCSV } from "@/lib/export";
import dynamic from "next/dynamic";
import KPICard from "@/components/KPICard";
import GlassCard from "@/components/GlassCard";
const TrendComparison = dynamic(() => import("@/components/TrendComparison"), { ssr: false, loading: () => <div className="h-48 bg-white/[0.04] rounded-lg animate-pulse" /> });
import { OcButton } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { useApiError } from "@/lib/useApiError";
import { useTranslation, formatNumber, formatCurrency } from "@/lib/i18n";
import ErrorBoundary from "@/components/ErrorBoundary";
import DataQualityBadge from "@/components/DataQualityBadge";
const InteractiveChart = dynamic(() => import("@/components/InteractiveChart"), { ssr: false, loading: () => <div className="h-48 bg-white/[0.04] rounded-lg animate-pulse" /> });
import type { DataPoint } from "@/components/InteractiveChart";

/* eslint-disable @typescript-eslint/no-explicit-any */

const INGREDIENT_COLORS: Record<string, string> = {
  fishmeal: "bg-ocean-500",
  fish_oil: "bg-cyan-500",
  soy: "bg-emerald-500",
  rapeseed: "bg-amber-500",
  wheat: "bg-yellow-500",
  other: "bg-violet-500",
};

const INGREDIENT_LABEL_KEYS: Record<string, string> = {
  fishmeal: "feed_cost.fishmeal",
  fish_oil: "feed_cost.fish_oil",
  soy: "feed_cost.soy",
  rapeseed: "feed_cost.rapeseed",
  wheat: "feed_cost.wheat",
  other: "Micro-ingredients",
};

const INGREDIENT_LABELS: Record<string, string> = {
  fishmeal: "Fishmeal",
  fish_oil: "Fish Oil",
  soy: "Soy Protein",
  rapeseed: "Rapeseed Oil",
  wheat: "Wheat/Starch",
  other: "Micro-ingredients",
};

export default function FeedCostPage() {
  const { t, locale } = useTranslation();
  const handleError = useApiError();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [compositeIndex, setCompositeIndex] = useState<any>(null);
  const [anchovy, setAnchovy] = useState<any>(null);
  const [yoyPrice, setYoyPrice] = useState<any>(null);

  const load = async () => {
    setLoading(true);
    try {
      const d = await api.feedCostLatest();
      setData(d);
    } catch (e) { handleError("feed_cost_latest")(e); }
    setLoading(false);
  };

  useEffect(() => {
    load();
    api.feedCostCompositeIndex(5).then(setCompositeIndex).catch(handleError("feed_cost_composite_index"));
    api.feedCostPeruAnchovy().then(setAnchovy).catch(handleError("feed_cost_peru_anchovy"));
    api.yoyComparison("price").then(setYoyPrice).catch(handleError("feed_cost_yoy_price"));
  }, []);

  const margin = data?.margin_nok_per_kg ?? 0;
  const marginTrend = data?.margin_trend ?? "stable";

  return (
    <ErrorBoundary fallbackTitle="Feed Cost error">
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] flex items-center gap-3">
            <Wheat className="w-6 h-6 text-amber-400" />
            {t("feed_cost.title")}
          </h1>
          <div className="flex items-center gap-2 mt-1">
            <p className="text-sm text-[var(--text-secondary)]">
              Official Fiskeridirektoratet cost data + live FRED feed prices &middot; Full cost stack
            </p>
            <DataQualityBadge source="FRED + Fiskeridirektoratet" quality="live" />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <OcButton variant="ghost" size="sm"
            onClick={() => {
              const exportData = data?.ingredients ? Object.entries(data.ingredients).map(([name, ing]: [string, any]) => ({
                ingredient: name,
                price_usd_per_kg: ing.price_usd_per_kg,
                cost_contribution_pct: ing.cost_contribution_pct,
                source: ing.source,
              })) : [];
              exportToCSV(exportData, "feed_cost_breakdown");
            }}
            leftIcon={<Download className="w-3.5 h-3.5" />}>Export CSV</OcButton>
          <OcButton variant="secondary" size="sm" onClick={load} loading={loading}
            leftIcon={<RefreshCw className="w-3.5 h-3.5" />}>Refresh</OcButton>
        </div>
      </motion.div>

      {/* KPI Row */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <KPICard label={t("feed_cost.total_cost")} value={data?.production_cost_nok_per_kg_salmon != null ? `${formatCurrency(data.production_cost_nok_per_kg_salmon, locale)}/kg` : "\u2014"}
          delta="Fiskeridirektoratet + FRED"
          icon={BarChart3} delay={0} />
        <KPICard label={t("feed_cost.feed_cost")}
          value={data ? `${formatNumber(data.feed_cost_nok_per_kg_salmon || (data.feed_cost_nok_per_kg * data.fcr), locale, 1)} NOK` : "\u2014"}
          delta={data ? `FCR: ${formatNumber(data.fcr, locale, 2)} \u00b7 Ingredients: ${formatCurrency(data.feed_cost_nok_per_kg, locale)}/kg` : undefined}
          icon={Wheat} delay={0.04} />
        <KPICard label="Salmon Spot"
          value={data?.salmon_spot_nok != null ? `${formatCurrency(data.salmon_spot_nok, locale)}/kg` : "\u2014"}
          delta="SSB export price" icon={Fish} delay={0.08} />
        <KPICard label={t("feed_cost.margin")}
          value={margin ? `${formatCurrency(margin, locale)}/kg` : "\u2014"}
          delta={data?.margin_pct != null ? `${formatNumber(data.margin_pct, locale, 1)}% of spot` : undefined}
          deltaType={margin > 15 ? "positive" : margin > 5 ? undefined : "negative"}
          icon={DollarSign} delay={0.12} />
        <KPICard label={t("feed_cost.fcr")}
          value={marginTrend.charAt(0).toUpperCase() + marginTrend.slice(1)}
          deltaType={marginTrend === "improving" ? "positive" : marginTrend === "squeezing" ? "negative" : undefined}
          icon={marginTrend === "improving" ? TrendingUp : marginTrend === "squeezing" ? TrendingDown : Minus}
          delay={0.16} />
        <KPICard label="FX Rates" value={data?.usd_nok != null ? `${formatNumber(data.usd_nok, locale, 2)} NOK/$` : "\u2014"}
          delta="Live exchange rates"
          icon={DollarSign} delay={0.2} />
      </div>

      {/* Price Year-over-Year */}
      {yoyPrice && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <TrendComparison
            metric="price"
            label="Salmon Price YoY (SSB)"
            unit="NOK/kg"
            currentYear={yoyPrice.current_year || []}
            previousYear={yoyPrice.previous_year || []}
            twoYearsAgo={yoyPrice.two_years_ago || []}
            years={yoyPrice.years}
          />
        </div>
      )}

      {/* Ingredient Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <GlassCard delay={0.15} accent="amber">
          <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
            <Wheat className="w-4 h-4 text-amber-400" />
            Ingredient Cost Breakdown
          </h3>
          {data?.ingredients ? (
            <div className="space-y-3">
              {Object.entries(data.ingredients).map(([name, ing]: [string, any]) => (
                <div key={name} className="space-y-1">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-[var(--text-primary)] font-medium">
                      {INGREDIENT_LABEL_KEYS[name] ? t(INGREDIENT_LABEL_KEYS[name]) : name}
                    </span>
                    <div className="flex items-center gap-3">
                      <span className="text-[var(--text-secondary)]">
                        {ing.price_usd_per_kg != null ? `$${formatNumber(ing.price_usd_per_kg, locale, 2)}/kg` : "\u2014"}
                      </span>
                      <span className="font-mono text-[var(--text-primary)]">
                        {ing.cost_contribution_pct}%
                      </span>
                      <span className={`text-[9px] px-1.5 py-0.5 rounded ${
                        ing.source === "yahoo_finance" ? "bg-emerald-500/10 text-emerald-400" :
                        ing.source === "world_bank" ? "bg-ocean-500/10 text-ocean-400" :
                        "bg-white/[0.05] text-[var(--text-secondary)]"
                      }`}>
                        {ing.source === "yahoo_finance" ? "LIVE" :
                         ing.source === "world_bank" ? "WB" : "EST"}
                      </span>
                    </div>
                  </div>
                  <div className="h-2 w-full bg-white/[0.06] rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${INGREDIENT_COLORS[name] || "bg-white/20"}`}
                      style={{ width: `${Math.min(100, ing.cost_contribution_pct)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="space-y-2 animate-pulse">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="h-8 rounded bg-white/[0.04]" />
              ))}
            </div>
          )}
        </GlassCard>

        {/* Margin Analysis */}
        <GlassCard delay={0.2} accent="ocean">
          <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
            <DollarSign className="w-4 h-4 text-ocean-400" />
            Margin Analysis
          </h3>
          {data ? (
            <div className="space-y-4">
              {/* Visual margin bar */}
              <div className="p-4 rounded-xl bg-white/[0.03] border border-white/[0.06]">
                <div className="flex items-center justify-between mb-2 text-[11px]">
                  <span className="text-[var(--text-secondary)]">Production Cost</span>
                  <span className="text-[var(--text-secondary)]">Salmon Spot Price</span>
                </div>
                <div className="relative h-6 bg-white/[0.06] rounded-full overflow-hidden">
                  {/* Cost portion */}
                  <div
                    className="absolute left-0 h-full rounded-l-full bg-rose-500/40"
                    style={{ width: `${Math.min(95, (data.production_cost_nok_per_kg_salmon / Math.max(data.salmon_spot_nok, 1)) * 100)}%` }}
                  />
                  {/* Margin portion */}
                  <div
                    className="absolute right-0 h-full rounded-r-full bg-emerald-500/40"
                    style={{ width: `${Math.max(5, data.margin_pct)}%` }}
                  />
                </div>
                <div className="flex items-center justify-between mt-2 text-[10px]">
                  <span className="text-rose-400">{formatCurrency(data.production_cost_nok_per_kg_salmon, locale)}/kg cost</span>
                  <span className={`font-bold ${margin > 15 ? "text-emerald-400" : margin > 5 ? "text-amber-400" : "text-rose-400"}`}>
                    {formatNumber(data.margin_pct, locale, 1)}% margin
                  </span>
                  <span className="text-emerald-400">{formatCurrency(data.salmon_spot_nok, locale)}/kg spot</span>
                </div>
              </div>

              {/* Margin alert */}
              {data.margin_pct < 15 && (
                <div className="flex items-center gap-2 p-3 rounded-xl bg-amber-500/[0.06] border border-amber-500/20">
                  <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0" />
                  <p className="text-[11px] text-amber-300">
                    Margin below 15% &mdash; feed cost pressure elevated.
                    Consider hedging or reviewing feed contracts.
                  </p>
                </div>
              )}

              {/* Cost stack */}
              <div className="space-y-2">
                {[
                  { label: "Feed ingredient cost", value: data.feed_cost_nok_per_kg, pct: formatNumber((data.feed_cost_nok_per_kg / data.salmon_spot_nok) * 100, locale, 0) },
                  { label: "Feed conversion (FCR " + formatNumber(data.fcr, locale, 2) + ")", value: data.production_cost_nok_per_kg_salmon, pct: formatNumber((data.production_cost_nok_per_kg_salmon / data.salmon_spot_nok) * 100, locale, 0) },
                  { label: "Farmer margin", value: data.margin_nok_per_kg, pct: formatNumber(data.margin_pct, locale, 0) },
                ].map(item => (
                  <div key={item.label} className="flex items-center justify-between p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                    <span className="text-[11px] text-[var(--text-secondary)]">{item.label}</span>
                    <span className="text-[11px] font-mono font-semibold text-[var(--text-primary)]">
                      {item.value != null ? formatCurrency(item.value, locale) : "\u2014"}/kg ({item.pct}%)
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="space-y-2 animate-pulse">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="h-12 rounded bg-white/[0.04]" />
              ))}
            </div>
          )}
        </GlassCard>
      </div>

      {/* Official Cost Waterfall + 17-Year Trend */}
      <OfficialCostSection data={data} />

      {/* Historical Price Comparison */}
      <HistoricalPriceChart />

      {/* Composite Feed Cost Index */}
      {compositeIndex && (
        <GlassCard delay={0.3} accent="amber">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold flex items-center gap-2">
              <Wheat className="w-4 h-4 text-amber-400" />
              {t("feed_cost.composite_index")}
            </h3>
            <span className="text-[8px] px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 font-medium tracking-wide uppercase">
              Proprietary &mdash; No public equivalent
            </span>
          </div>

          <div className="flex items-center gap-6 mb-4">
            <div>
              <p className={`text-3xl font-bold font-mono ${
                compositeIndex.current_index < 105 ? "text-emerald-400" :
                compositeIndex.current_index <= 120 ? "text-amber-400" : "text-rose-400"
              }`}>
                {compositeIndex.current_index != null ? formatNumber(compositeIndex.current_index, locale, 1) : "\u2014"}
              </p>
              <p className="text-[10px] text-[var(--text-secondary)] mt-0.5">Current Index (base 100)</p>
            </div>
            {compositeIndex.ytd_change_pct != null && (
              <div className="p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                <p className={`text-sm font-bold font-mono ${
                  compositeIndex.ytd_change_pct > 0 ? "text-rose-400" : "text-emerald-400"
                }`}>
                  {compositeIndex.ytd_change_pct > 0 ? "+" : ""}{compositeIndex.ytd_change_pct != null ? formatNumber(compositeIndex.ytd_change_pct, locale, 1) : "\u2014"}%
                </p>
                <p className="text-[9px] text-[var(--text-secondary)]">YTD Change</p>
              </div>
            )}
          </div>

          {compositeIndex.volatility_alert && (
            <div className="flex items-center gap-2 p-3 rounded-xl bg-amber-500/[0.06] border border-amber-500/20 mb-4">
              <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0" />
              <p className="text-[11px] text-amber-300">
                Feed cost volatility exceeds 1.5&times; baseline &mdash; margin risk elevated
              </p>
            </div>
          )}

          {/* Interactive composite index chart */}
          {compositeIndex.series?.length > 1 && (
            <div className="mb-4">
              <InteractiveChart
                data={(compositeIndex.series as any[]).map((s: any, i: number): DataPoint => ({
                  x: i,
                  y: s.index ?? 0,
                  label: s.date || s.period || `Point ${i + 1}`,
                }))}
                unit=""
                color="#f59e0b"
                fillColor="#f59e0b"
                height={140}
                title="Composite Feed Cost Index"
              />
            </div>
          )}

          {/* Weight breakdown */}
          {compositeIndex.weights && (
            <div>
              <p className="text-[10px] text-[var(--text-secondary)] mb-2 font-medium">Index Weight Breakdown</p>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                {Object.entries(compositeIndex.weights).map(([name, weight]: [string, any]) => (
                  <div key={name} className="flex items-center justify-between p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                    <span className="text-[10px] text-[var(--text-secondary)]">
                      {INGREDIENT_LABEL_KEYS[name] ? t(INGREDIENT_LABEL_KEYS[name]) : name}
                    </span>
                    <span className="text-[10px] font-mono font-semibold text-[var(--text-primary)]">
                      {typeof weight === "number" ? `${(weight * 100).toFixed(0)}%` : String(weight)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </GlassCard>
      )}

      {/* Peru Anchovy Watch */}
      {anchovy && (
        <GlassCard delay={0.35} accent="ocean">
          <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
            <Globe2 className="w-4 h-4 text-ocean-400" />
            {t("feed_cost.anchovy_watch")}
          </h3>

          <div className="flex flex-wrap items-center gap-4 mb-4">
            {anchovy.risk_level && (
              <span className={`text-xs font-bold px-3 py-1 rounded-full border ${
                anchovy.risk_level === "CRITICAL" ? "bg-rose-500/10 text-rose-400 border-rose-500/20" :
                anchovy.risk_level === "ELEVATED" ? "bg-amber-500/10 text-amber-400 border-amber-500/20" :
                anchovy.risk_level === "NORMAL" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" :
                "bg-ocean-500/10 text-ocean-400 border-ocean-500/20"
              }`}>
                {anchovy.risk_level}
              </span>
            )}
            {anchovy.oni_value != null && (
              <div className="p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                <p className="text-lg font-bold font-mono text-[var(--text-primary)]">
                  {anchovy.oni_value > 0 ? "+" : ""}{anchovy.oni_value}&deg;C
                </p>
                <p className="text-[9px] text-[var(--text-secondary)]">
                  ONI {anchovy.season || ""}
                </p>
              </div>
            )}
            {anchovy.fishmeal_price_usd_tonne != null && (
              <div className="p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                <p className="text-lg font-bold font-mono text-[var(--text-primary)]">
                  ${anchovy.fishmeal_price_usd_tonne != null ? formatNumber(anchovy.fishmeal_price_usd_tonne, locale, 0) : "\u2014"}
                </p>
                <p className="text-[9px] text-[var(--text-secondary)]">Fishmeal USD/t</p>
              </div>
            )}
          </div>

          {anchovy.risk_description && (
            <p className="text-[11px] text-[var(--text-secondary)] mb-3">
              {anchovy.risk_description}
            </p>
          )}

          <div className="p-3 rounded-xl bg-ocean-500/[0.04] border border-ocean-500/15">
            <p className="text-[10px] text-ocean-300 leading-relaxed">
              Peru produces ~20% of global fishmeal. El Ni&ntilde;o events cause
              season cancellation &rarr; fishmeal price spikes &rarr; salmon feed
              cost increases.
            </p>
          </div>
        </GlassCard>
      )}

      <p className="text-[10px] text-[var(--text-secondary)] text-center opacity-60">
        Non-feed costs: Fiskeridirektoratet l&oslash;nnsomhetsunders&oslash;kelse 2024 (official government survey).
        Feed ingredients: FRED (St. Louis Fed) live commodity prices. FCR: 1.30 (Norwegian economic average).
        Total production cost = live feed &times; FCR + official non-feed costs. Not financial advice.
      </p>
    </div>
    </ErrorBoundary>
  );
}

// ── Official Cost Waterfall + 17-Year Trend ──────────────────────────────────

function OfficialCostSection({ data }: { data: any }) {
  const { locale } = useTranslation();
  const handleError = useApiError();
  const [history, setHistory] = useState<any>(null);

  useEffect(() => {
    api.feedCostOfficialHistory().then(setHistory).catch(handleError("feed_cost_official_history"));
  }, []);

  const breakdown = data?.cost_breakdown;
  const items = breakdown ? [
    { label: "Feed (live)", value: breakdown.feed_per_kg_salmon, color: "bg-amber-500" },
    { label: "Smolt", value: breakdown.smolt, color: "bg-cyan-500" },
    { label: "Other operating", value: breakdown.other_operating, color: "bg-violet-500" },
    { label: "Slaughter", value: breakdown.slaughter, color: "bg-rose-500" },
    { label: "Labour", value: breakdown.labour, color: "bg-ocean-500" },
    { label: "Insurance", value: breakdown.insurance, color: "bg-emerald-500" },
    { label: "Depreciation", value: breakdown.depreciation, color: "bg-blue-500" },
    { label: "Net finance", value: breakdown.net_finance, color: "bg-white/20" },
  ] : [];

  const total = items.reduce((s, i) => s + (i.value || 0), 0);
  const histData = history?.data || [];

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {/* Waterfall: cost stack */}
      <GlassCard delay={0.22} accent="violet">
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <BarChart3 className="w-4 h-4 text-violet-400" />
          Cost Stack (NOK/kg salmon)
          <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-violet-500/10 text-violet-400 border border-violet-500/20 ml-auto">
            Official + Live
          </span>
        </h3>
        {items.length > 0 ? (
          <div className="space-y-1.5">
            {items.filter(i => i.value > 0).map((item) => (
              <div key={item.label} className="flex items-center gap-2">
                <span className="text-[10px] text-[var(--text-secondary)] w-28 flex-shrink-0 text-right">
                  {item.label}
                </span>
                <div className="flex-1 h-5 bg-white/[0.04] rounded overflow-hidden relative">
                  <div
                    className={`h-full rounded ${item.color}`}
                    style={{ width: `${(item.value / Math.max(total, 1)) * 100}%`, opacity: 0.6 }}
                  />
                  <span className="absolute right-2 top-0 h-full flex items-center text-[10px] font-mono font-semibold text-[var(--text-primary)]">
                    {formatNumber(item.value, locale, 1)}
                  </span>
                </div>
              </div>
            ))}
            {/* Total bar */}
            <div className="flex items-center gap-2 pt-1 border-t border-white/[0.06]">
              <span className="text-[10px] text-[var(--text-primary)] font-semibold w-28 flex-shrink-0 text-right">
                TOTAL
              </span>
              <div className="flex-1 h-6 bg-white/[0.04] rounded overflow-hidden relative">
                <div className="h-full rounded bg-gradient-to-r from-violet-500/50 to-ocean-500/50" style={{ width: "100%" }} />
                <span className="absolute right-2 top-0 h-full flex items-center text-[11px] font-mono font-bold text-[var(--text-primary)]">
                  {formatCurrency(total, locale)}/kg
                </span>
              </div>
            </div>
            <p className="text-[9px] text-[var(--text-secondary)] mt-1 opacity-60">
              Feed = live FRED prices &times; FCR {data?.fcr}. Other costs = Fiskeridirektoratet 2024.
            </p>
          </div>
        ) : (
          <div className="h-40 flex items-center justify-center text-sm text-[var(--text-secondary)]">
            Loading cost data...
          </div>
        )}
      </GlassCard>

      {/* 17-Year Trend */}
      <GlassCard delay={0.24} accent="ocean">
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-ocean-400" />
          Production Cost Trend (2008&ndash;2024)
          <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 ml-auto">
            Fiskeridirektoratet
          </span>
        </h3>
        {histData.length > 0 ? (
          <>
            <CostTrendSVG data={histData} />
            <div className="grid grid-cols-3 gap-2 mt-3">
              <div className="p-2 rounded-lg bg-white/[0.03] border border-white/[0.06] text-center">
                <p className="text-xs font-bold text-[var(--text-primary)]">
                  NOK {histData[0]?.total_cost}/kg
                </p>
                <p className="text-[8px] text-[var(--text-secondary)]">{histData[0]?.year}</p>
              </div>
              <div className="p-2 rounded-lg bg-white/[0.03] border border-white/[0.06] text-center">
                <p className="text-xs font-bold text-rose-400">
                  +{(((histData[histData.length-1]?.total_cost / histData[0]?.total_cost) - 1) * 100).toFixed(0)}%
                </p>
                <p className="text-[8px] text-[var(--text-secondary)]">{histData.length}yr change</p>
              </div>
              <div className="p-2 rounded-lg bg-white/[0.03] border border-white/[0.06] text-center">
                <p className="text-xs font-bold text-[var(--text-primary)]">
                  NOK {histData[histData.length-1]?.total_cost}/kg
                </p>
                <p className="text-[8px] text-[var(--text-secondary)]">{histData[histData.length-1]?.year}</p>
              </div>
            </div>
          </>
        ) : (
          <div className="h-40 flex items-center justify-center text-sm text-[var(--text-secondary)]">
            Loading historical data...
          </div>
        )}
      </GlassCard>
    </div>
  );
}

function CostTrendSVG({ data }: { data: any[] }) {
  const W = 400, H = 160, PAD_L = 40, PAD_R = 10, PAD_T = 10, PAD_B = 25;
  const plotW = W - PAD_L - PAD_R;
  const plotH = H - PAD_T - PAD_B;

  const totals = data.map((d: any) => d.total_cost);
  const feeds = data.map((d: any) => d.feed_cost);
  const min = 0;
  const max = Math.max(...totals) * 1.1;
  const range = max - min || 1;

  const x = (i: number) => PAD_L + (i / Math.max(data.length - 1, 1)) * plotW;
  const y = (v: number) => PAD_T + plotH - ((v - min) / range) * plotH;

  const totalPath = data.map((d: any, i: number) => `${i === 0 ? "M" : "L"}${x(i)},${y(d.total_cost)}`).join(" ");
  const feedPath = data.map((d: any, i: number) => `${i === 0 ? "M" : "L"}${x(i)},${y(d.feed_cost)}`).join(" ");

  const yTicks = [0, 20, 40, 60, 80].filter(v => v <= max);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height: H }}>
      {yTicks.map(v => (
        <g key={v}>
          <line x1={PAD_L} y1={y(v)} x2={W - PAD_R} y2={y(v)} stroke="rgba(255,255,255,0.05)" strokeDasharray="3,3" />
          <text x={PAD_L - 4} y={y(v) + 3} textAnchor="end" fill="rgba(255,255,255,0.3)" fontSize="8" fontFamily="monospace">{v}</text>
        </g>
      ))}
      {data.filter((_: any, i: number) => i % 2 === 0).map((d: any, i: number) => (
        <text key={d.year} x={x(data.indexOf(d))} y={H - 5} textAnchor="middle" fill="rgba(255,255,255,0.3)" fontSize="7" fontFamily="monospace">
          {String(d.year).slice(-2)}
        </text>
      ))}
      {/* Feed area */}
      <path d={`${feedPath} L${x(data.length-1)},${y(0)} L${x(0)},${y(0)} Z`} fill="rgba(245,158,11,0.1)" />
      {/* Total line */}
      <path d={totalPath} fill="none" stroke="#a78bfa" strokeWidth="2" strokeLinecap="round" />
      {/* Feed line */}
      <path d={feedPath} fill="none" stroke="#f59e0b" strokeWidth="1.5" strokeLinecap="round" strokeDasharray="4,2" />
      {/* Legend */}
      <line x1={PAD_L + 5} y1={8} x2={PAD_L + 20} y2={8} stroke="#a78bfa" strokeWidth="2" />
      <text x={PAD_L + 23} y={11} fill="rgba(255,255,255,0.5)" fontSize="8">Total</text>
      <line x1={PAD_L + 65} y1={8} x2={PAD_L + 80} y2={8} stroke="#f59e0b" strokeWidth="1.5" strokeDasharray="4,2" />
      <text x={PAD_L + 83} y={11} fill="rgba(255,255,255,0.5)" fontSize="8">Feed</text>
    </svg>
  );
}

// ── Historical Price Comparison Chart ────────────────────────────────────────

const HIST_COLORS: Record<string, { line: string; bg: string; label: string }> = {
  soy:       { line: "#10b981", bg: "bg-emerald-500", label: "Soybean" },
  wheat:     { line: "#eab308", bg: "bg-yellow-500", label: "Wheat" },
  fishmeal:  { line: "#06b6d4", bg: "bg-cyan-500", label: "Fishmeal" },
  fish_oil:  { line: "#3b82f6", bg: "bg-blue-500", label: "Fish Oil" },
  rapeseed:  { line: "#f59e0b", bg: "bg-amber-500", label: "Rapeseed" },
};

function HistoricalPriceChart() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [years, setYears] = useState(5);
  const [selected, setSelected] = useState<Set<string>>(new Set(["soy", "wheat", "fishmeal", "fish_oil"]));

  const load = async () => {
    setLoading(true);
    try {
      const d = await api.feedCostHistorical(years);
      setData(d);
    } catch { /* empty */ }
    setLoading(false);
  };

  useEffect(() => { load(); }, [years]);

  const toggle = (name: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  // Build unified date axis and SVG paths
  const ingredients = data?.ingredients || {};
  const allDates: string[] = [];
  for (const [name] of Object.entries(ingredients)) {
    if (!selected.has(name)) continue;
    for (const pt of ingredients[name].data || []) {
      if (!allDates.includes(pt.date)) allDates.push(pt.date);
    }
  }
  allDates.sort();

  // Find global min/max for Y axis
  let globalMin = Infinity, globalMax = -Infinity;
  for (const [name] of Object.entries(ingredients)) {
    if (!selected.has(name)) continue;
    for (const pt of ingredients[name].data || []) {
      globalMin = Math.min(globalMin, pt.price_usd_tonne);
      globalMax = Math.max(globalMax, pt.price_usd_tonne);
    }
  }
  if (!isFinite(globalMin)) { globalMin = 0; globalMax = 1000; }
  const yRange = globalMax - globalMin || 1;

  const W = 800, H = 220, PAD_L = 50, PAD_R = 10, PAD_T = 10, PAD_B = 30;
  const plotW = W - PAD_L - PAD_R;
  const plotH = H - PAD_T - PAD_B;

  const xScale = (i: number) => PAD_L + (i / Math.max(allDates.length - 1, 1)) * plotW;
  const yScale = (v: number) => PAD_T + plotH - ((v - globalMin) / yRange) * plotH;

  // Build SVG paths per ingredient
  const paths: { name: string; d: string; color: string }[] = [];
  for (const [name] of Object.entries(ingredients)) {
    if (!selected.has(name)) continue;
    const series = ingredients[name].data || [];
    const dateMap = new Map<string, number>(series.map((p: any) => [p.date, p.price_usd_tonne]));

    let d = "";
    let started = false;
    for (let i = 0; i < allDates.length; i++) {
      const val = dateMap.get(allDates[i]);
      if (val == null) continue;
      const x = xScale(i);
      const y = yScale(val);
      d += started ? ` L${x},${y}` : `M${x},${y}`;
      started = true;
    }
    if (d) paths.push({ name, d, color: HIST_COLORS[name]?.line || "#888" });
  }

  // Y axis labels (5 ticks)
  const yTicks = Array.from({ length: 5 }, (_, i) => globalMin + (yRange * i) / 4);

  // X axis labels (show ~8 dates)
  const xLabels: { date: string; x: number }[] = [];
  const step = Math.max(1, Math.floor(allDates.length / 8));
  for (let i = 0; i < allDates.length; i += step) {
    xLabels.push({ date: allDates[i], x: xScale(i) });
  }

  return (
    <GlassCard delay={0.25} accent="ocean">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-ocean-400" />
          Historical Ingredient Prices ({years}-Year)
        </h3>
        <div className="flex items-center gap-2">
          <select
            value={years}
            onChange={(e) => setYears(Number(e.target.value))}
            className="bg-white/[0.04] border border-white/[0.08] rounded-lg px-2 py-1 text-[11px] focus:outline-hidden focus:border-ocean-500/30"
          >
            {[1, 2, 3, 5, 10].map(y => (
              <option key={y} value={y}>{y} year{y > 1 ? "s" : ""}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Ingredient toggles */}
      <div className="flex flex-wrap gap-2 mb-4">
        {Object.entries(HIST_COLORS).map(([name, cfg]) => {
          const ing = ingredients[name];
          const active = selected.has(name);
          return (
            <button
              key={name}
              onClick={() => toggle(name)}
              className={`flex items-center gap-1.5 text-[10px] px-2.5 py-1 rounded-full border transition-all ${
                active
                  ? "border-white/20 bg-white/[0.06] text-[var(--text-primary)]"
                  : "border-white/[0.06] bg-transparent text-[var(--text-secondary)] opacity-50"
              }`}
            >
              <div className={`w-2 h-2 rounded-full ${cfg.bg}`} />
              {cfg.label}
              {ing?.change_pct != null && (
                <span className={`ml-1 font-mono ${ing.change_pct > 0 ? "text-rose-400" : "text-emerald-400"}`}>
                  {ing.change_pct > 0 ? "+" : ""}{ing.change_pct}%
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* SVG Chart */}
      {loading ? (
        <div className="h-[220px] flex items-center justify-center">
          <RefreshCw className="w-5 h-5 text-ocean-400 animate-spin" />
        </div>
      ) : allDates.length < 2 ? (
        <div className="h-[220px] flex items-center justify-center text-[var(--text-secondary)] text-sm">
          No historical data available
        </div>
      ) : (
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height: H }}>
          {/* Grid lines */}
          {yTicks.map((v, i) => (
            <g key={i}>
              <line x1={PAD_L} y1={yScale(v)} x2={W - PAD_R} y2={yScale(v)}
                stroke="rgba(255,255,255,0.05)" strokeDasharray="4,4" />
              <text x={PAD_L - 5} y={yScale(v) + 3} textAnchor="end"
                fill="rgba(255,255,255,0.3)" fontSize="9" fontFamily="monospace">
                ${Math.round(v)}
              </text>
            </g>
          ))}

          {/* X axis labels */}
          {xLabels.map((l, i) => (
            <text key={i} x={l.x} y={H - 5} textAnchor="middle"
              fill="rgba(255,255,255,0.3)" fontSize="8" fontFamily="monospace">
              {l.date}
            </text>
          ))}

          {/* Data lines */}
          {paths.map(p => (
            <path key={p.name} d={p.d} fill="none" stroke={p.color}
              strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          ))}
        </svg>
      )}

      {/* Summary stats */}
      {data && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-3">
          {Object.entries(ingredients).map(([name, ing]: [string, any]) => {
            if (!selected.has(name)) return null;
            const cfg = HIST_COLORS[name] || { label: name, bg: "bg-white/20" };
            return (
              <div key={name} className="p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                <div className="flex items-center gap-1.5 mb-1">
                  <div className={`w-2 h-2 rounded-full ${cfg.bg}`} />
                  <span className="text-[10px] font-medium text-[var(--text-primary)]">{cfg.label}</span>
                </div>
                <div className="text-[9px] text-[var(--text-secondary)] space-y-0.5">
                  <div className="flex justify-between">
                    <span>Current</span>
                    <span className="font-mono">${ing.current_usd_tonne}/t</span>
                  </div>
                  <div className="flex justify-between">
                    <span>{years}y range</span>
                    <span className="font-mono">${ing.min_usd_tonne} &ndash; ${ing.max_usd_tonne}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>{years}y avg</span>
                    <span className="font-mono">${ing.avg_usd_tonne}/t</span>
                  </div>
                  <div className="flex justify-between">
                    <span>{years}y change</span>
                    <span className={`font-mono font-semibold ${
                      ing.change_pct > 0 ? "text-rose-400" : "text-emerald-400"
                    }`}>
                      {ing.change_pct > 0 ? "+" : ""}{ing.change_pct}%
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <p className="text-[9px] text-[var(--text-secondary)] opacity-50 mt-2">
        USD/tonne. Soy &amp; Wheat: CBOT futures via Yahoo Finance. Fishmeal: World Bank Commodity Prices.
        Fish Oil: derived (2.2&times; fishmeal). Monthly data.
      </p>
    </GlassCard>
  );
}
