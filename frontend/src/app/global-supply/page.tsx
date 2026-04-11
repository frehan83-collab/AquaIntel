"use client";
import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  Globe2, RefreshCw, TrendingUp, TrendingDown, AlertTriangle,
  BarChart3, Zap, Fish, Download, ArrowRightLeft, Anchor,
} from "lucide-react";
import dynamic from "next/dynamic";
import KPICard from "@/components/KPICard";
import GlassCard from "@/components/GlassCard";
const SupplyChainSankey = dynamic(() => import("@/components/SupplyChainSankey"), { ssr: false, loading: () => <div className="h-80 bg-white/[0.04] rounded-lg animate-pulse" /> });
import type { SankeyData } from "@/components/SupplyChainSankey";
import { OcButton } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { useTranslation, formatNumber, formatCurrency } from "@/lib/i18n";
import { useApiError } from "@/lib/useApiError";
import { exportToCSV } from "@/lib/export";
import DataQualityBadge from "@/components/DataQualityBadge";

/* eslint-disable @typescript-eslint/no-explicit-any */

const STATUS_STYLE: Record<string, { bg: string; text: string }> = {
  normal:    { bg: "bg-emerald-500/10 border-emerald-500/20", text: "text-emerald-400" },
  disrupted: { bg: "bg-rose-500/10 border-rose-500/20", text: "text-rose-400" },
  elevated:  { bg: "bg-amber-500/10 border-amber-500/20", text: "text-amber-400" },
  unknown:   { bg: "bg-white/[0.04] border-white/[0.08]", text: "text-[var(--text-secondary)]" },
};

const FLAG: Record<string, string> = {
  Norway: "\ud83c\uddf3\ud83c\uddf4", Chile: "\ud83c\udde8\ud83c\uddf1",
  Scotland: "\ud83c\udff4\udb40\udc67\udb40\udc62\udb40\udc73\udb40\udc63\udb40\udc74\udb40\udc7f",
  Canada: "\ud83c\udde8\ud83c\udde6", "Faroe Islands": "\ud83c\uddeb\ud83c\uddf4",
  Iceland: "\ud83c\uddee\ud83c\uddf8", Others: "\ud83c\udf0d",
};

export default function GlobalSupplyPage() {
  const { t, locale } = useTranslation();
  const handleError = useApiError();
  const [data, setData] = useState<any>(null);
  const [monthly, setMonthly] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [annualProd, setAnnualProd] = useState<any[]>([]);
  const [costHistory, setCostHistory] = useState<any[]>([]);
  const [biomass, setBiomass] = useState<any>(null);

  const load = async () => {
    setLoading(true);
    try {
      const [gs, mo] = await Promise.allSettled([
        api.globalSupply(),
        api.productionMonthly(),
      ]);
      if (gs.status === "fulfilled") setData(gs.value);
      if (mo.status === "fulfilled") {
        const raw = (mo.value as any)?.data || (Array.isArray(mo.value) ? mo.value : []);
        setMonthly(raw.slice(-24));
      }
    } catch { /* empty */ }
    api.productionAnnual().then((d: any) => setAnnualProd(Array.isArray(d) ? d : d?.data || [])).catch(handleError("global_supply_production_annual"));
    api.feedCostOfficialHistory().then((d: any) => setCostHistory(Array.isArray(d) ? d : d?.data || d?.history || [])).catch(handleError("global_supply_feed_cost_history"));
    api.biomassNational().then(setBiomass).catch(handleError("global_supply_biomass_national"));
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const balance = data?.balance || "balanced";
  const pressure = data?.price_pressure || "neutral";

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] flex items-center gap-3">
            <Globe2 className="w-6 h-6 text-ocean-400" />
            {t("global_supply.title")}
          </h1>
          <div className="flex items-center gap-2 mt-1">
            <p className="text-sm text-[var(--text-secondary)]">
              7-country live supply model &mdash; Norway, Chile, Iceland, Scotland, Canada, Faroes + Others
            </p>
            <DataQualityBadge source="Multi-country (7 sources)" quality="live" />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => window.print()}
            className="print:hidden flex items-center gap-1.5 px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:text-ocean-400 bg-white/[0.04] border border-white/[0.08] rounded-lg transition-colors"
            title="Export as PDF"
          >
            <Download className="w-3.5 h-3.5" /> PDF
          </button>
          {data?.countries?.length > 0 && (
            <OcButton variant="ghost" size="sm" leftIcon={<Download className="w-3.5 h-3.5" />}
              onClick={() => exportToCSV(data.countries.map((c: any) => ({
                Country: c.country, "2026E Production (t)": c.annual_tonnes_2026e,
                "2025 Actual (t)": c.annual_tonnes_2025, "YoY Growth %": c.yoy_growth_pct,
                "Share %": c.share_pct, Currency: c.currency, Status: c.status,
                "Disruption Reason": c.disruption_reason || "", "Lice Pressure": c.lice_pressure || "",
              })), "global_supply")}>Export CSV</OcButton>
          )}
          <OcButton variant="secondary" size="sm" onClick={load} loading={loading}
            leftIcon={<RefreshCw className="w-3.5 h-3.5" />}>Refresh</OcButton>
        </div>
      </motion.div>

      {data && (
        <>
          {/* KPIs */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <KPICard label={t("global_supply.total_global")}
              value={`${formatNumber(data.total_production_tonnes / 1_000_000, locale, 2)}M t`}
              delta="Annual (FAO est.)" icon={Globe2} delay={0} />
            <KPICard label="Effective Supply"
              value={`${formatNumber(data.effective_production_tonnes / 1_000_000, locale, 2)}M t`}
              delta={`Deficit: ${formatNumber(data.supply_deficit_pct, locale, 1)}%`}
              deltaType={data.supply_deficit_pct > 2 ? "negative" : "positive"}
              icon={BarChart3} delay={0.04} />
            <KPICard label="Price Pressure"
              value={pressure.charAt(0).toUpperCase() + pressure.slice(1)}
              deltaType={pressure === "bullish" ? "positive" : pressure === "bearish" ? "negative" : undefined}
              icon={pressure === "bullish" ? TrendingUp : TrendingDown} delay={0.08} />
            <KPICard label="Norway Premium"
              value={`${data.norway_premium_pct > 0 ? "+" : ""}${formatNumber(data.norway_premium_pct, locale, 1)}%`}
              delta={`Global: $${formatNumber(data.global_salmon_usd_kg, locale, 2)}/kg`}
              deltaType={data.norway_premium_pct > 5 ? "positive" : data.norway_premium_pct < -5 ? "negative" : undefined}
              icon={Fish} delay={0.12} />
          </div>

          {/* National Biomass (Fiskeridirektoratet) */}
          {biomass && (
            <GlassCard delay={0.06} accent="ocean">
              <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                <Anchor className="w-4 h-4 text-ocean-400" />
                Norway Standing Biomass
                <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-ocean-500/10 text-ocean-400 border border-ocean-500/20 ml-auto">
                  Fiskeridirektoratet
                </span>
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06] text-center">
                  <div className="text-[10px] text-[var(--text-secondary)] uppercase tracking-wider mb-1">Total Biomass</div>
                  <div className="text-lg font-bold text-[var(--text-primary)]">
                    {biomass.total_biomass_tonnes != null
                      ? `${formatNumber(biomass.total_biomass_tonnes / 1000, locale)}k t`
                      : "\u2014"}
                  </div>
                </div>
                <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06] text-center">
                  <div className="text-[10px] text-[var(--text-secondary)] uppercase tracking-wider mb-1">MAB Utilization</div>
                  <div className={`text-lg font-bold ${
                    (biomass.mab_utilization_pct || 0) > 95 ? "text-rose-400" :
                    (biomass.mab_utilization_pct || 0) > 85 ? "text-amber-400" : "text-emerald-400"
                  }`}>
                    {biomass.mab_utilization_pct != null
                      ? `${formatNumber(biomass.mab_utilization_pct, locale, 1)}%`
                      : "\u2014"}
                  </div>
                </div>
                <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06] text-center">
                  <div className="text-[10px] text-[var(--text-secondary)] uppercase tracking-wider mb-1">Localities</div>
                  <div className="text-lg font-bold text-[var(--text-primary)]">
                    {biomass.locality_count != null ? formatNumber(biomass.locality_count, locale) : "\u2014"}
                  </div>
                </div>
                <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06] text-center">
                  <div className="text-[10px] text-[var(--text-secondary)] uppercase tracking-wider mb-1">National MTB</div>
                  <div className="text-lg font-bold text-[var(--text-primary)]">
                    {biomass.national_mtb_tonnes != null
                      ? `${formatNumber(biomass.national_mtb_tonnes / 1000, locale)}k t`
                      : "948k t"}
                  </div>
                </div>
              </div>
            </GlassCard>
          )}

          {/* Supply Chain Sankey — Production Flow */}
          <GlassCard delay={0.08}>
            <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
              <Globe2 className="w-4 h-4 text-ocean-400" />
              Production Flow &mdash; Origin to Market
              <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-ocean-500/10 text-ocean-400 border border-ocean-500/20 ml-auto">
                2026E volumes &middot; kt HOG
              </span>
            </h3>
            <SupplyChainSankey
              data={(() => {
                /* Build Sankey from live country data when available, fallback to reference */
                const countryMap = Object.fromEntries(
                  (data.countries || []).map((c: any) => [c.country, (c.annual_tonnes_2026e || c.annual_tonnes || 0) / 1000])
                );
                const nor = countryMap["Norway"] || 1400;
                const chl = countryMap["Chile"] || 900;
                const sct = countryMap["Scotland"] || 180;
                const can = countryMap["Canada"] || 130;
                const far = countryMap["Faroe Islands"] || 90;
                const ice = countryMap["Iceland"] || 45;
                const total = nor + chl + sct + can + far + ice;

                /* Market split ratios (FAO/EUMOFA reference) */
                const eu = Math.round(total * 0.437);
                const us = Math.round(total * 0.219);
                const asia = Math.round(total * 0.182);
                const domestic = total - eu - us - asia;

                const sankeyData: SankeyData = {
                  stages: ["Origins", "Smolt", "Harvest", "Processing", "Markets"],
                  nodes: [
                    /* Col 0: Origins */
                    { id: "nor", label: "Norway", column: 0, value: Math.round(nor) },
                    { id: "chl", label: "Chile", column: 0, value: Math.round(chl) },
                    { id: "sct", label: "Scotland", column: 0, value: Math.round(sct) },
                    { id: "can", label: "Canada", column: 0, value: Math.round(can) },
                    { id: "far", label: "Faroes", column: 0, value: Math.round(far) },
                    { id: "ice", label: "Iceland", column: 0, value: Math.round(ice) },
                    /* Col 1: Smolt production */
                    { id: "smolt", label: "Smolt Production", column: 1, value: Math.round(total) },
                    /* Col 2: Harvest */
                    { id: "harvest", label: "Harvest (HOG)", column: 2, value: Math.round(total * 0.95) },
                    /* Col 3: Processing */
                    { id: "proc", label: "Processing", column: 3, value: Math.round(total * 0.93) },
                    /* Col 4: Markets */
                    { id: "eu", label: "EU", column: 4, value: eu, color: "rgb(59,130,246)" },
                    { id: "us", label: "US", column: 4, value: us, color: "rgb(168,85,247)" },
                    { id: "asia", label: "Asia", column: 4, value: asia, color: "rgb(244,63,94)" },
                    { id: "dom", label: "Domestic", column: 4, value: domestic, color: "rgb(245,158,11)" },
                  ],
                  links: [
                    /* Origins → Smolt */
                    { source: "nor", target: "smolt", value: Math.round(nor), label: `Norway \u2192 Smolt: ${Math.round(nor)}kt` },
                    { source: "chl", target: "smolt", value: Math.round(chl), label: `Chile \u2192 Smolt: ${Math.round(chl)}kt` },
                    { source: "sct", target: "smolt", value: Math.round(sct), label: `Scotland \u2192 Smolt: ${Math.round(sct)}kt` },
                    { source: "can", target: "smolt", value: Math.round(can), label: `Canada \u2192 Smolt: ${Math.round(can)}kt` },
                    { source: "far", target: "smolt", value: Math.round(far), label: `Faroes \u2192 Smolt: ${Math.round(far)}kt` },
                    { source: "ice", target: "smolt", value: Math.round(ice), label: `Iceland \u2192 Smolt: ${Math.round(ice)}kt` },
                    /* Smolt → Harvest (5% mortality) */
                    { source: "smolt", target: "harvest", value: Math.round(total * 0.95), label: `Sea Growth \u2192 Harvest: ${Math.round(total * 0.95)}kt (5% mortality)` },
                    /* Harvest → Processing (2% loss) */
                    { source: "harvest", target: "proc", value: Math.round(total * 0.93), label: `Harvest \u2192 Processing: ${Math.round(total * 0.93)}kt (2% processing loss)` },
                    /* Processing → Markets */
                    { source: "proc", target: "eu", value: eu, label: `Processing \u2192 EU: ${eu}kt` },
                    { source: "proc", target: "us", value: us, label: `Processing \u2192 US: ${us}kt` },
                    { source: "proc", target: "asia", value: asia, label: `Processing \u2192 Asia: ${asia}kt` },
                    { source: "proc", target: "dom", value: domestic, label: `Processing \u2192 Domestic: ${domestic}kt` },
                  ],
                };
                return sankeyData;
              })()}
              height={340}
            />
          </GlassCard>

          {/* Country Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {(data.countries || []).map((c: any, i: number) => {
              const style = STATUS_STYLE[c.status] || STATUS_STYLE.unknown;
              return (
                <motion.div
                  key={c.country}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.06 }}
                >
                  <GlassCard delay={0}>
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <span className="text-lg">{FLAG[c.country] || "\ud83c\udf0d"}</span>
                        <div>
                          <p className="text-sm font-semibold text-[var(--text-primary)]">{c.country}</p>
                          <p className="text-[10px] text-[var(--text-secondary)]">{formatNumber(c.share_pct, locale, 1)}% of global supply</p>
                        </div>
                      </div>
                      <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-md border ${style.bg} ${style.text}`}>
                        {c.status.toUpperCase()}
                      </span>
                    </div>

                    {/* Production — 2026E vs 2025 actual */}
                    <div className="mb-2">
                      <div className="flex justify-between text-[10px] mb-1">
                        <span className="text-[var(--text-secondary)]">2026E Production</span>
                        <span className="font-mono text-[var(--text-primary)]">
                          {formatNumber(c.annual_tonnes_2026e / 1000, locale)}k t
                          {c.yoy_growth_pct ? (
                            <span className={`ml-1 ${c.yoy_growth_pct > 0 ? "text-emerald-400" : c.yoy_growth_pct < 0 ? "text-rose-400" : "text-[var(--text-secondary)]"}`}>
                              {c.yoy_growth_pct > 0 ? "+" : ""}{formatNumber(c.yoy_growth_pct, locale, 1)}%
                            </span>
                          ) : null}
                        </span>
                      </div>
                      <div className="h-2 bg-white/[0.06] rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full ${c.status === "disrupted" ? "bg-rose-500" : "bg-ocean-500"}`}
                          style={{ width: `${Math.min(100, ((c.annual_tonnes_2026e || c.annual_tonnes) / 1_730_000) * 100)}%` }}
                        />
                      </div>
                      {c.annual_tonnes_2025 > 0 && (
                        <p className="text-[9px] text-[var(--text-secondary)] mt-0.5">
                          2025 actual: {formatNumber(c.annual_tonnes_2025 / 1000, locale)}k t
                          <span className="opacity-50 ml-1">({c.source_2025})</span>
                        </p>
                      )}
                    </div>

                    {/* Details */}
                    <div className="space-y-1 text-[10px]">
                      {/* Currency */}
                      {c.currency && (
                        <div className="flex justify-between text-[var(--text-secondary)]">
                          <span>Currency</span>
                          <span className="font-mono text-ocean-400">{c.currency}</span>
                        </div>
                      )}
                      {c.disruption_pct > 0 && (
                        <div className="flex items-center gap-1.5 text-rose-400">
                          <AlertTriangle className="w-3 h-3" />
                          <span>{c.disruption_reason}</span>
                        </div>
                      )}
                      {c.lice_pressure && c.lice_pressure !== "normal" && (
                        <div className="flex justify-between text-[var(--text-secondary)]">
                          <span>Lice pressure</span>
                          <span className={c.lice_pressure === "critical" ? "text-rose-400" :
                            c.lice_pressure === "elevated" ? "text-amber-400" : ""}>
                            {c.lice_pressure}
                          </span>
                        </div>
                      )}
                      {c.disease_events > 0 && (
                        <div className="flex justify-between text-[var(--text-secondary)]">
                          <span>Disease events</span>
                          <span className="text-rose-400">{c.disease_events}</span>
                        </div>
                      )}
                      {c.price_impact_pct > 0 && (
                        <div className="flex justify-between text-[var(--text-secondary)]">
                          <span>Price impact</span>
                          <span className="text-amber-400">+{c.price_impact_pct}%</span>
                        </div>
                      )}
                    </div>
                  </GlassCard>
                </motion.div>
              );
            })}
          </div>

          {/* Supply Pipeline — 12-Month Forward Stacked Bar Chart */}
          {data.countries?.length > 0 && (() => {
            const PIPELINE_COUNTRIES = [
              { key: "Norway", color: "#00D4C8" },
              { key: "Chile", color: "#F59E0B" },
              { key: "Scotland", color: "#8B5CF6" },
              { key: "Canada", color: "#EF4444" },
              { key: "Iceland", color: "#3B82F6" },
              { key: "Faroe Islands", color: "#10B981" },
            ];
            const MONTHS = Array.from({ length: 12 }, (_, i) => {
              const d = new Date();
              d.setMonth(d.getMonth() + i + 1);
              return d.toLocaleString("en", { month: "short", year: "2-digit" });
            });
            // Seasonal production weights (index 0 = Jan). Salmon harvest peaks Q3-Q4.
            const SEASONAL = [0.06, 0.06, 0.07, 0.08, 0.08, 0.09, 0.10, 0.11, 0.11, 0.10, 0.08, 0.06];
            // Build monthly data from country annual figures
            const countryMap = Object.fromEntries(
              (data.countries || []).map((c: any) => [c.country, c.annual_tonnes_2026e || c.annual_tonnes || 0])
            );
            const monthlyData = MONTHS.map((label, mi) => {
              const calMonth = (new Date().getMonth() + mi + 1) % 12;
              const weight = SEASONAL[calMonth];
              const segments = PIPELINE_COUNTRIES.map(pc => ({
                country: pc.key,
                color: pc.color,
                value: Math.round((countryMap[pc.key] || 0) * weight),
              }));
              return { label, segments, total: segments.reduce((s, seg) => s + seg.value, 0) };
            });
            const maxTotal = Math.max(...monthlyData.map(m => m.total), 1);
            const chartW = 760;
            const chartH = 200;
            const barW = (chartW - 40) / 12;
            const gap = 4;

            return (
              <GlassCard delay={0.14}>
                <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                  <BarChart3 className="w-4 h-4 text-ocean-400" />
                  Supply Pipeline — 12-Month Forward
                  <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-ocean-500/10 text-ocean-400 border border-ocean-500/20 ml-auto">
                    Stacked by country &middot; seasonal weights
                  </span>
                </h3>
                {/* Legend */}
                <div className="flex flex-wrap gap-3 mb-3">
                  {PIPELINE_COUNTRIES.map(pc => (
                    <div key={pc.key} className="flex items-center gap-1.5">
                      <span className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: pc.color }} />
                      <span className="text-[10px] text-[var(--text-secondary)]">{pc.key}</span>
                    </div>
                  ))}
                </div>
                {/* Chart */}
                <div className="overflow-x-auto">
                  <svg viewBox={`0 0 ${chartW} ${chartH + 28}`} width="100%" className="min-w-[600px]">
                    {monthlyData.map((m, mi) => {
                      const x = 30 + mi * barW;
                      let yOffset = 0;
                      return (
                        <g key={mi}>
                          {m.segments.map((seg, si) => {
                            const segH = (seg.value / maxTotal) * chartH;
                            const y = chartH - yOffset - segH;
                            yOffset += segH;
                            return (
                              <rect
                                key={si}
                                x={x + gap / 2}
                                y={y}
                                width={barW - gap}
                                height={Math.max(segH, 0)}
                                rx={2}
                                fill={seg.color}
                                opacity={0.85}
                              >
                                <title>{`${seg.country}: ${(seg.value / 1000).toFixed(0)}k t`}</title>
                              </rect>
                            );
                          })}
                          {/* Month label */}
                          <text
                            x={x + barW / 2}
                            y={chartH + 14}
                            textAnchor="middle"
                            className="fill-[var(--text-secondary)]"
                            fontSize={9}
                          >
                            {m.label}
                          </text>
                          {/* Total label */}
                          <text
                            x={x + barW / 2}
                            y={chartH - yOffset - 4}
                            textAnchor="middle"
                            className="fill-[var(--text-secondary)]"
                            fontSize={8}
                          >
                            {(m.total / 1000).toFixed(0)}k
                          </text>
                        </g>
                      );
                    })}
                    {/* Y-axis labels */}
                    {[0, 0.25, 0.5, 0.75, 1].map((pct, i) => (
                      <g key={i}>
                        <line
                          x1={28} y1={chartH * (1 - pct)} x2={chartW} y2={chartH * (1 - pct)}
                          stroke="rgba(255,255,255,0.06)" strokeDasharray="2,4"
                        />
                        <text x={26} y={chartH * (1 - pct) + 3} textAnchor="end"
                          className="fill-[var(--text-secondary)]" fontSize={8}>
                          {((maxTotal * pct) / 1000).toFixed(0)}k
                        </text>
                      </g>
                    ))}
                  </svg>
                </div>
              </GlassCard>
            );
          })()}

          {/* Insights */}
          {data.insights?.length > 0 && (
            <GlassCard delay={0.2} accent="ocean">
              <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                <Zap className="w-4 h-4 text-ocean-400" />
                Supply Intelligence
              </h3>
              <div className="space-y-2">
                {data.insights.map((ins: string, i: number) => (
                  <div key={i} className="flex items-start gap-2 p-2.5 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                    <TrendingUp className="w-3.5 h-3.5 text-ocean-400 flex-shrink-0 mt-0.5" />
                    <p className="text-[11px] text-[var(--text-primary)] leading-relaxed">{ins}</p>
                  </div>
                ))}
              </div>
            </GlassCard>
          )}
          {/* 2026 Trade Flow Shifts */}
          <GlassCard delay={0.25} accent="amber">
            <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
              <ArrowRightLeft className="w-4 h-4 text-amber-400" />
              {t("global_supply.trade_flow_title")}
              <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 ml-auto">
                {locale === "no" ? "US-toll 15 % p\u00e5 norsk laks" : "US 15% tariff on Norwegian salmon"}
              </span>
            </h3>
            <p className="text-[11px] text-[var(--text-secondary)] mb-4 leading-relaxed">
              {locale === "no"
                ? "US-tollsatser p\u00e5 15 % (fra april 2025) har omdirigert norske eksportstr\u00f8mmer. Chile og Canada \u00f8ker markedsandelen i USA, mens Kina absorberer norsk volum."
                : "US tariffs at 15% (effective April 2025) have redirected Norwegian export flows. Chile and Canada gaining US market share while China absorbs Norwegian volume."}
            </p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="text-center p-3 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                <p className="text-[9px] text-[var(--text-secondary)] uppercase tracking-wider">
                  {locale === "no" ? "US import fra Norge" : "US imports from Norway"}
                </p>
                <p className="text-xl font-bold text-rose-400 mt-1">-29%</p>
                <p className="text-[9px] text-[var(--text-secondary)] mt-0.5">YoY 2025\u21922026</p>
              </div>
              <div className="text-center p-3 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                <p className="text-[9px] text-[var(--text-secondary)] uppercase tracking-wider">
                  {locale === "no" ? "Kina import fra Norge" : "China imports from Norway"}
                </p>
                <p className="text-xl font-bold text-emerald-400 mt-1">+86%</p>
                <p className="text-[9px] text-[var(--text-secondary)] mt-0.5">YoY 2025\u21922026</p>
              </div>
              <div className="text-center p-3 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                <p className="text-[9px] text-[var(--text-secondary)] uppercase tracking-wider">
                  {locale === "no" ? "Chile\u2192US-andel" : "Chile\u2192US share"}
                </p>
                <p className="text-xl font-bold text-emerald-400 mt-1">{locale === "no" ? "Voksende" : "Growing"}</p>
                <p className="text-[9px] text-[var(--text-secondary)] mt-0.5">FTA 0% {locale === "no" ? "toll" : "tariff"}</p>
              </div>
              <div className="text-center p-3 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                <p className="text-[9px] text-[var(--text-secondary)] uppercase tracking-wider">
                  {locale === "no" ? "Canada\u2192US-andel" : "Canada\u2192US share"}
                </p>
                <p className="text-xl font-bold text-ocean-400 mt-1">{locale === "no" ? "Stabil" : "Stable"}</p>
                <p className="text-[9px] text-[var(--text-secondary)] mt-0.5">USMCA 0% {locale === "no" ? "toll" : "tariff"}</p>
              </div>
            </div>
          </GlassCard>
        </>
      )}

      {/* Norway Monthly Production */}
      {monthly.length > 0 && (
        <GlassCard delay={0.35}>
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-ocean-400" />
            Norway Monthly Production
            <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-ocean-500/10 text-ocean-400 border border-ocean-500/20 ml-auto">
              Last {monthly.length} months &mdash; Fiskeridirektoratet
            </span>
          </h3>
          <div className="space-y-1 max-h-64 overflow-y-auto">
            {monthly.map((m: any, i: number) => {
              const harvest = m.harvest_tonnes || 0;
              const maxH = Math.max(...monthly.map((x: any) => x.harvest_tonnes || 0), 1);
              const pct = (harvest / maxH) * 100;
              const label = m.month ? `${m.year}-${String(m.month).padStart(2, "0")}` : `${m.year}`;
              return (
                <div key={i} className="flex items-center gap-3 py-1">
                  <span className="text-[10px] text-[var(--text-secondary)] w-16 flex-shrink-0 tabular-nums">{label}</span>
                  <div className="flex-1 h-4 bg-white/[0.04] rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-ocean-600 to-ocean-400 rounded-full transition-all"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <span className="text-[10px] text-[var(--text-primary)] tabular-nums w-16 text-right flex-shrink-0">
                    {harvest > 0 ? `${formatNumber(harvest / 1000, locale, 1)}K t` : "—"}
                  </span>
                </div>
              );
            })}
          </div>
        </GlassCard>
      )}

      {/* Norway Production History */}
      {annualProd.length > 0 && (
        <GlassCard delay={0.3}>
          <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-ocean-400" />
            Norway Production History
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.06]">
                  <th className="text-left py-2 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Year</th>
                  <th className="text-left py-2 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Production (t)</th>
                  <th className="text-left py-2 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">YoY Growth</th>
                </tr>
              </thead>
              <tbody>
                {annualProd.slice(-10).map((r: any, i: number) => (
                  <tr key={i} className="border-b border-white/[0.04] hover:bg-white/[0.02]">
                    <td className="py-2 px-3 font-mono text-xs text-[var(--text-secondary)]">{r.year}</td>
                    <td className="py-2 px-3 font-semibold text-[var(--text-primary)]">
                      {typeof r.volume === "number" ? `${formatNumber(r.volume / 1000, locale)}k` : typeof r.tonnes === "number" ? `${formatNumber(r.tonnes / 1000, locale)}k` : String(r.production || r.value || "\u2014")}
                    </td>
                    <td className="py-2 px-3">
                      <span className={`text-xs ${(r.growth_pct || r.yoy || 0) >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                        {(r.growth_pct || r.yoy || 0) >= 0 ? "+" : ""}{formatNumber(r.growth_pct || r.yoy || 0, locale, 1)}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </GlassCard>
      )}

      {/* Feed Cost History */}
      {costHistory.length > 0 && (
        <GlassCard delay={0.35}>
          <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
            <Zap className="w-4 h-4 text-amber-400" />
            Official Production Cost History (Fiskeridirektoratet)
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.06]">
                  <th className="text-left py-2 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Year</th>
                  <th className="text-left py-2 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Cost NOK/kg</th>
                  <th className="text-left py-2 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Feed Share</th>
                </tr>
              </thead>
              <tbody>
                {costHistory.slice(-10).map((r: any, i: number) => (
                  <tr key={i} className="border-b border-white/[0.04] hover:bg-white/[0.02]">
                    <td className="py-2 px-3 font-mono text-xs text-[var(--text-secondary)]">{r.year}</td>
                    <td className="py-2 px-3 font-semibold text-[var(--text-primary)]">
                      {formatNumber(r.total_cost || r.cost_nok || r.total || 0, locale, 1)} NOK
                    </td>
                    <td className="py-2 px-3 text-xs text-[var(--text-secondary)]">
                      {r.feed_share ? `${formatNumber(r.feed_share * 100, locale)}%` : r.feed_pct ? `${formatNumber(r.feed_pct, locale)}%` : "\u2014"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </GlassCard>
      )}

      <p className="text-[9px] text-[var(--text-secondary)] text-center opacity-50">
        Data: BarentsWatch (Norway lice), SSB (prices), Sernapesca (Chile), FRED (global benchmark),
        Fiskeridirektoratet (monthly production). Updated every 2 hours. Not financial advice.
      </p>
    </div>
  );
}
