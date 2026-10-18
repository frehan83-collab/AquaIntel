"use client";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Scale, RefreshCw, DollarSign, Globe2, TrendingUp,
  Activity, Award, AlertTriangle, Printer,
} from "lucide-react";
import DataTable, { Column } from "@/components/DataTable";
import KPICard from "@/components/KPICard";
import GlassCard from "@/components/GlassCard";
import { OcButton } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { useTranslation, formatNumber, formatCurrency, formatDate } from "@/lib/i18n";
import dynamic from "next/dynamic";
import ErrorBoundary from "@/components/ErrorBoundary";
import DataQualityBadge from "@/components/DataQualityBadge";
const InteractiveChart = dynamic(() => import("@/components/InteractiveChart"), { ssr: false, loading: () => <div className="h-48 bg-white/[0.04] rounded-lg animate-pulse" /> });
import type { DataPoint } from "@/components/InteractiveChart";
import type { CompetitivenessIndex, CompetitivenessOrigin, CompetitivenessScenarioResponse } from "@/types/api";

export default function CompetitivenessPage() {
  const [data, setData] = useState<CompetitivenessIndex | null>(null);
  const [loading, setLoading] = useState(true);
  const [tariffOverrides, setTariffOverrides] = useState<Record<string, number>>({});
  const [scenarioResult, setScenarioResult] = useState<CompetitivenessScenarioResponse | null>(null);
  const [scenarioLoading, setScenarioLoading] = useState(false);
  const { t, locale } = useTranslation();

  const load = async () => {
    setLoading(true);
    try {
      const [res] = await Promise.allSettled([api.competitivenessIndex()]);
      if (res.status === "fulfilled") setData(res.value);
    } catch { /* empty */ }
    setLoading(false);
  };

  const runTariffScenario = async () => {
    if (Object.keys(tariffOverrides).length === 0) return;
    setScenarioLoading(true);
    try {
      const result = await api.competitivenessTariffScenario(tariffOverrides);
      setScenarioResult(result);
    } catch { /* empty */ }
    setScenarioLoading(false);
  };

  useEffect(() => { load(); }, []);

  const origins = data?.origins ?? [];
  const cheapest = origins[0];
  const norway = origins.find((o) => o.country === "Norway");
  const bestMargin = [...origins].sort((a, b) => b.margin_pct - a.margin_pct)[0];

  return (
    <ErrorBoundary fallbackTitle="Competitiveness Index error">
    <div className="space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] flex items-center gap-3">
            <Scale className="w-6 h-6 text-ocean-400" />
            {t("competitiveness.title")}
          </h1>
          <div className="flex items-center gap-2 mt-1">
            <p className="text-sm text-[var(--text-secondary)]">
              {t("competitiveness.fx_adjusted")}
            </p>
            <DataQualityBadge
              source="FRED + Yahoo Finance"
              provenance={data?.data_provenance}
            />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => window.print()}
            className="print:hidden flex items-center gap-1.5 px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:text-ocean-400 bg-white/[0.04] border border-white/[0.08] rounded-lg transition-colors"
            title="Export as PDF"
          >
            <Printer className="w-3.5 h-3.5" /> PDF
          </button>
          <OcButton variant="secondary" size="sm" onClick={load} loading={loading}
            leftIcon={<RefreshCw className="w-3.5 h-3.5" />}>Refresh</OcButton>
        </div>
      </motion.div>

      {/* US Tariff Impact Banner */}
      <GlassCard delay={0.05} accent="rose">
        <div className="flex items-start gap-3">
          <div className="flex-shrink-0 w-9 h-9 rounded-lg bg-rose-500/10 flex items-center justify-center">
            <AlertTriangle className="w-5 h-5 text-rose-400" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-1">
              {t("competitiveness.tariff_impact_title")}
            </h3>
            <p className="text-[11px] text-[var(--text-secondary)] leading-relaxed mb-3">
              {t("competitiveness.tariff_impact_subtitle")}
            </p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {/* Rates from the payload: core/regulatory_facts.py, dated and sourced */}
              {(data?.origins ?? [])
                .filter((o) => ["Norway", "Chile", "Scotland"].includes(o.country) && o.tariff)
                .map((o) => (
                  <div key={o.country} className="p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                    <p className="text-[9px] text-[var(--text-secondary)] uppercase tracking-wider">{o.country}</p>
                    <p className={`text-sm font-bold mt-0.5 ${o.tariff!.rate_pct > 0 ? "text-rose-400" : "text-emerald-400"}`}>
                      {formatNumber(o.tariff!.rate_pct, locale, 1)}%
                    </p>
                    <a href={o.tariff!.source_url} target="_blank" rel="noopener noreferrer" className="text-[9px] text-[var(--text-secondary)] underline">
                      {locale === "no" ? "Fra" : "Since"} {formatDate(new Date(`${o.tariff!.effective_from}T12:00:00`), locale)}
                    </a>
                  </div>
                ))}
              <div className="p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                <p className="text-[9px] text-[var(--text-secondary)] uppercase tracking-wider">{locale === "no" ? "Handelsvirkning" : "Trade Impact"}</p>
                <div className="flex items-baseline gap-1.5 mt-0.5">
                  <span className="text-[10px] text-rose-400 font-semibold">{locale === "no" ? "Nor\u2192US" : "NOR\u2192US"} -29%</span>
                  <span className="text-[10px] text-emerald-400 font-semibold">{locale === "no" ? "Nor\u2192Kina" : "NOR\u2192CN"} +86%</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </GlassCard>

      {/* KPI Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KPICard
          label="Most Competitive"
          value={cheapest ? `${cheapest.flag} ${cheapest.country}` : "\u2014"}
          delta={cheapest?.total_delivered_usd != null ? `$${formatNumber(cheapest.total_delivered_usd, locale, 2)}/kg delivered` : ""}
          deltaType="positive"
          icon={Award}
          delay={0}
        />
        <KPICard
          label="Norway Delivered"
          value={norway?.total_delivered_usd != null ? `$${formatNumber(norway.total_delivered_usd, locale, 2)}/kg` : "\u2014"}
          delta={norway ? `Rank #${norway.rank}${norway.tariff ? ` (US tariff ${formatNumber(norway.tariff.rate_pct, locale, 1)}%)` : ""}` : ""}
          deltaType={norway && norway.rank > 3 ? "negative" : "neutral"}
          icon={AlertTriangle}
          delay={0.03}
        />
        <KPICard
          label="US Spot Price"
          value={data?.us_spot_usd_kg != null ? `$${formatNumber(data.us_spot_usd_kg, locale, 2)}/kg` : "\u2014"}
          delta="FRED global salmon benchmark"
          deltaType="neutral"
          icon={DollarSign}
          delay={0.06}
        />
        <KPICard
          label="Best Margin"
          value={bestMargin?.margin_pct != null ? `${formatNumber(bestMargin.margin_pct, locale, 1)}%` : "\u2014"}
          delta={bestMargin?.margin_usd != null ? `${bestMargin.flag} ${bestMargin.country} ($${formatNumber(bestMargin.margin_usd, locale, 2)}/kg)` : ""}
          deltaType="positive"
          icon={TrendingUp}
          delay={0.09}
        />
      </div>

      {/* FX-Adjusted Delivered Cost Chart */}
      {origins.length > 0 && (
        <GlassCard delay={0.11}>
          <InteractiveChart
            title="Delivered Cost by Origin (USD/kg)"
            data={origins.map((o): DataPoint => ({
              x: o.rank ?? 0,
              y: o.total_delivered_usd ?? 0,
              label: `${o.flag || ""} ${o.country || ""}`.trim(),
            }))}
            unit="$/kg"
            color="#34d399"
            fillColor="#34d399"
            height={180}
          />
        </GlassCard>
      )}

      {/* Ranking Table */}
      <GlassCard delay={0.12}>
        <DataTable
          title="Delivered Cost Ranking (US Market)"
          data={origins}
          searchKeys={["country"]}
          exportFilename="origin_competitiveness"
          compact
          emptyMessage={loading ? t("common.loading") : t("common.no_data")}
          columns={[
            {
              key: "rank", label: t("competitiveness.rank"), sortable: true, align: "center" as const, width: "40px",
              render: (val) => (
                <span className={`text-xs font-bold ${
                  val === 1 ? "text-emerald-400" : val === 2 ? "text-ocean-400" : val === 3 ? "text-amber-400" : "text-[var(--text-secondary)]"
                }`}>
                  {val}
                </span>
              ),
            },
            {
              key: "country", label: t("competitiveness.country"), sortable: true,
              render: (_v, row) => (
                <span className="font-semibold text-[var(--text-primary)]">
                  {row.flag} {row.country}
                </span>
              ),
            },
            {
              key: "local_cost_per_kg", label: t("competitiveness.cost_nok"), sortable: true, align: "right" as const,
              render: (val, row) => (
                <span className="tabular-nums text-[var(--text-secondary)]">
                  {val?.toLocaleString()} {row.currency}
                </span>
              ),
            },
            {
              key: "fx_rate_to_usd", label: "FX Rate", sortable: true, align: "right" as const,
              render: (val) => (
                <span className="tabular-nums text-[var(--text-secondary)] font-mono text-[10px]">
                  {val != null ? (val < 0.01 ? formatNumber(val, locale, 5) : formatNumber(val, locale, 4)) : "\u2014"}
                </span>
              ),
            },
            {
              key: "production_cost_usd", label: "USD Cost", sortable: true, align: "right" as const,
              render: (val) => <span className="tabular-nums">{val != null ? `$${formatNumber(val, locale, 2)}` : "\u2014"}</span>,
            },
            {
              key: "tariff_pct", label: t("competitiveness.tariff"), sortable: true, align: "right" as const,
              render: (val, row) => (
                val > 0 ? (
                  <span
                    className="text-rose-400 tabular-nums"
                    title={row.duty_base_note || undefined}
                  >
                    {formatNumber(val * 100, locale, 1)}% ({row.tariff_cost_usd != null ? `$${formatNumber(row.tariff_cost_usd, locale, 2)}` : "\u2014"})
                    {row.tariff_base === "export_price" ? (
                      <span className="text-[9px] text-[var(--text-secondary)]"> *</span>
                    ) : null}
                  </span>
                ) : (
                  <span className="text-emerald-400">
                    0% {row.tariff?.basis?.includes("USMCA") ? "(USMCA)" : row.tariff?.basis?.includes("MFN") ? "(MFN)" : ""}
                  </span>
                )
              ),
            },
            {
              key: "freight_usd", label: "Freight", sortable: true, align: "right" as const,
              render: (val) => <span className="tabular-nums text-[var(--text-secondary)]">{val != null ? `$${formatNumber(val, locale, 2)}` : "\u2014"}</span>,
            },
            {
              key: "total_delivered_usd", label: "Delivered", sortable: true, align: "right" as const,
              render: (val) => <span className="tabular-nums font-bold text-[var(--text-primary)]">{val != null ? `$${formatNumber(val, locale, 2)}` : "\u2014"}</span>,
            },
            {
              key: "margin_pct", label: "Margin", sortable: true, align: "right" as const,
              render: (val, row) => (
                <span className={`tabular-nums ${row.margin_usd > 0 ? "text-emerald-400" : "text-rose-400"}`}>
                  {val > 0 ? "+" : ""}{val}%
                </span>
              ),
            },
          ] as Column<CompetitivenessOrigin>[]}
        />
        {/* WS-37: the duty is assessed on the customs value (transaction price), not on
            the producer's cost. Say which base each row used. */}
        {data?.tariff_basis ? (
          <p className="mt-3 text-[10px] leading-relaxed text-[var(--text-secondary)]">
            <span className="font-semibold">*</span> {data.tariff_basis}
            {origins.find((o) => o.tariff_base === "export_price")?.duty_base_note ? (
              <> {origins.find((o) => o.tariff_base === "export_price")!.duty_base_note}</>
            ) : null}
          </p>
        ) : null}
      </GlassCard>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* FX Rates Panel */}
        {data?.fx_rates && (
          <GlassCard delay={0.25}>
            <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
              <DollarSign className="w-4 h-4 text-amber-400" />
              {t("competitiveness.fx_rates")}
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
              {Object.entries(data.fx_rates).map(([currency, rate]) => (
                <div key={currency} className="p-2.5 rounded-lg bg-white/[0.03] border border-white/[0.06] text-center">
                  <p className="text-[10px] text-[var(--text-secondary)] uppercase">{currency}/USD</p>
                  <p className="text-sm font-bold font-mono text-[var(--text-primary)] mt-0.5">
                    {rate != null ? (rate < 0.01 ? formatNumber(rate, locale, 5) : formatNumber(rate, locale, 4)) : "\u2014"}
                  </p>
                </div>
              ))}
            </div>
          </GlassCard>
        )}

        {/* Insights */}
        {data && data.insights && data.insights.length > 0 && (
          <GlassCard delay={0.28} accent="ocean">
            <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
              <Activity className="w-4 h-4 text-ocean-400" />
              Intelligence
            </h3>
            <div className="space-y-2">
              {data.insights.map((ins: string, i: number) => (
                <div key={i} className="flex items-start gap-2 p-2.5 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                  <Globe2 className="w-3.5 h-3.5 text-ocean-400 flex-shrink-0 mt-0.5" />
                  <p className="text-[11px] text-[var(--text-primary)] leading-relaxed">{ins}</p>
                </div>
              ))}
            </div>
          </GlassCard>
        )}
      </div>

      {/* Tariff Scenario Analysis */}
      <GlassCard delay={0.3} accent="amber">
        <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
          <Scale className="w-4 h-4 text-amber-400" />
          {t("competitiveness.tariff_scenario")}
          <span className="ml-auto text-[10px] text-[var(--text-secondary)]">What-if analysis</span>
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-4">
          {["Norway", "Chile", "Scotland", "Canada", "Faroe Islands", "Iceland"].map((origin) => (
            <div key={origin} className="space-y-1">
              <div className="flex justify-between text-[10px]">
                <span className="text-[var(--text-secondary)]">{origin}</span>
                <span className="text-ocean-400 font-semibold">{tariffOverrides[origin] ?? "—"}%</span>
              </div>
              <input
                type="range"
                min={0} max={25} step={0.5}
                value={tariffOverrides[origin] ?? 0}
                onChange={(e) => setTariffOverrides(prev => ({...prev, [origin]: Number(e.target.value)}))}
                className="w-full h-1.5 appearance-none rounded-full bg-white/10 accent-ocean-400 cursor-pointer"
              />
            </div>
          ))}
        </div>
        <OcButton variant="primary" size="sm" onClick={runTariffScenario} loading={scenarioLoading}>
          Run Scenario
        </OcButton>

        {scenarioResult?.scenario_origins && (
          <div className="mt-4 space-y-1.5">
            {scenarioResult.scenario_origins.map((o, i: number) => (
              <div key={i} className="flex items-center justify-between p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-bold text-[var(--text-primary)] w-4">#{o.scenario_rank}</span>
                  <span className="text-[11px] text-[var(--text-primary)]">{o.country}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-[10px] text-[var(--text-secondary)]">
                    {o.delivered_cost_usd != null ? `$${formatNumber(o.delivered_cost_usd, locale, 2)}/kg` : "\u2014"}
                  </span>
                  {(o.rank_change ?? 0) !== 0 && (
                    <span className={`text-[10px] font-semibold ${(o.rank_change ?? 0) > 0 ? "text-emerald-400" : "text-rose-400"}`}>
                      {(o.rank_change ?? 0) > 0 ? "\u2191" : "\u2193"}{Math.abs(o.rank_change ?? 0)}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </GlassCard>

      <p className="text-[9px] text-[var(--text-secondary)] text-center opacity-50">
        FX rates: Yahoo Finance + FRED. Norway cost: live from Fiskeridirektoratet model.
        Other origins: industry estimates. Tariffs: US Harmonized Tariff Schedule.
        Freight: approximate air/sea rates. Not financial or trade advice.
      </p>
    </div>
    </ErrorBoundary>
  );
}
