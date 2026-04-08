"use client";
import { useState, useEffect, useMemo } from "react";
import { motion } from "framer-motion";
import {
  Wheat, AlertTriangle, Leaf, Factory, TrendingUp, TrendingDown,
  ShieldCheck, ShieldAlert, ShieldX, ArrowRight, Minus,
} from "lucide-react";
import KPICard from "@/components/KPICard";
import GlassCard from "@/components/GlassCard";
import { api } from "@/lib/api";
import { useApiError } from "@/lib/useApiError";
import { useTranslation, formatNumber, formatCurrency } from "@/lib/i18n";
import ErrorBoundary from "@/components/ErrorBoundary";

/* eslint-disable @typescript-eslint/no-explicit-any */

/* ── Colour palette for ingredients ────────────────────────────────────── */
const ING_COLORS: Record<string, string> = {
  "Soy Protein Concentrate": "#10b981",
  "Fishmeal": "#0ea5e9",
  "Fish Oil": "#06b6d4",
  "Wheat": "#eab308",
  "Rapeseed Oil": "#f59e0b",
  "Micro-nutrients": "#8b5cf6",
  "Astaxanthin": "#ec4899",
  "Insect Meal (BSF)": "#84cc16",
  "Algae Oil (DHA/EPA)": "#14b8a6",
};

const ING_FILL: Record<string, string> = {
  "Soy Protein Concentrate": "bg-emerald-500",
  "Fishmeal": "bg-sky-500",
  "Fish Oil": "bg-cyan-500",
  "Wheat": "bg-yellow-500",
  "Rapeseed Oil": "bg-amber-500",
  "Micro-nutrients": "bg-violet-500",
  "Astaxanthin": "bg-pink-500",
};

/* ── EUDR status icon ───────────────────────────────────────────────── */
function EudrStatusIcon({ status }: { status: string }) {
  if (status === "compliant")
    return <ShieldCheck className="h-6 w-6 text-emerald-400" />;
  if (status === "partial")
    return <ShieldAlert className="h-6 w-6 text-amber-400" />;
  return <ShieldX className="h-6 w-6 text-rose-400" />;
}

function eudrColor(status: string): string {
  if (status === "compliant") return "text-emerald-400";
  if (status === "partial") return "text-amber-400";
  return "text-rose-400";
}

function riskBadge(level: string): string {
  const map: Record<string, string> = {
    low: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
    medium: "bg-amber-500/20 text-amber-300 border-amber-500/30",
    high: "bg-rose-500/20 text-rose-300 border-rose-500/30",
    critical: "bg-red-600/20 text-red-300 border-red-600/30",
  };
  return map[level] || map.medium;
}

/* ── Page ─────────────────────────────────────────────────────────────── */
export default function FeedSupplyChainPage() {
  const { t, locale } = useTranslation();
  const handleError = useApiError();

  const [summary, setSummary] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const data = await api.feedSupplyChainSummary();
        setSummary(data);
      } catch (e) {
        handleError("feed-supply-chain")(e);
      } finally {
        setLoading(false);
      }
    })();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const composition: any[] = summary?.composition || [];
  const eudr = summary?.eudr_risk || {};
  const scenarios: any[] = summary?.scenarios || [];

  /* KPI derived values */
  const totalCost = summary?.total_cost_nok_per_tonne || 0;
  const totalCarbon = summary?.total_carbon_kg_co2_per_tonne || 0;
  const soyPct = composition.find((c: any) => c.name?.includes("Soy"))?.weight_pct || 0;
  const marinePct = composition
    .filter((c: any) => c.name?.includes("Fish"))
    .reduce((s: number, c: any) => s + (c.weight_pct || 0), 0);

  /* ── Stacked bar width calc ──────────────────────────────────────── */
  const totalWeight = useMemo(
    () => composition.reduce((s: number, c: any) => s + (c.weight_pct || 0), 0),
    [composition],
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin h-8 w-8 border-2 border-ocean-400 border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <ErrorBoundary>
      <div className="space-y-6">
        {/* Header */}
        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Wheat className="h-7 w-7 text-amber-400" />
            {t("feed_chain.title")}
          </h1>
          <p className="text-sm text-gray-400 mt-1">
            {t("feed_chain.subtitle")}
          </p>
        </motion.div>

        {/* KPI row */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <KPICard
            label={t("feed_chain.total_cost")}
            value={formatCurrency(totalCost, locale)}
            unit="/tonne"
            icon={Wheat}
          />
          <KPICard
            label={t("feed_chain.carbon")}
            value={formatNumber(totalCarbon, locale, 0)}
            unit="kg CO2/t"
            icon={Leaf}
          />
          <KPICard
            label={t("feed_chain.soy_share")}
            value={`${formatNumber(soyPct, locale, 1)}%`}
            delta={t("feed_chain.of_feed")}
            deltaType="neutral"
            icon={AlertTriangle}
          />
          <KPICard
            label={t("feed_chain.marine_share")}
            value={`${formatNumber(marinePct, locale, 1)}%`}
            delta={t("feed_chain.of_feed")}
            deltaType="neutral"
            icon={Factory}
          />
        </div>

        {/* Main grid: composition + EUDR */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Feed composition breakdown */}
          <GlassCard>
            <h2 className="text-lg font-semibold text-white mb-4">
              {t("feed_chain.composition")}
            </h2>

            {/* Stacked horizontal bar */}
            <div className="relative h-10 rounded-lg overflow-hidden flex mb-4">
              {composition.map((ing: any) => {
                const widthPct = totalWeight > 0
                  ? (ing.weight_pct / totalWeight) * 100
                  : 0;
                return (
                  <div
                    key={ing.name}
                    className="h-full relative group transition-all"
                    style={{
                      width: `${widthPct}%`,
                      backgroundColor: ING_COLORS[ing.name] || "#64748b",
                    }}
                    title={`${ing.name}: ${ing.weight_pct}%`}
                  >
                    {widthPct > 8 && (
                      <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-white/90">
                        {ing.weight_pct}%
                      </span>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Legend + detail table */}
            <div className="space-y-2">
              {composition.map((ing: any) => (
                <div
                  key={ing.name}
                  className="flex items-center justify-between text-sm"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span
                      className="h-3 w-3 rounded-full shrink-0"
                      style={{ backgroundColor: ING_COLORS[ing.name] || "#64748b" }}
                    />
                    <span className="text-gray-300 truncate">{ing.name}</span>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded border ${riskBadge(ing.eudr_risk)}`}>
                      {ing.eudr_risk.toUpperCase()}
                    </span>
                  </div>
                  <div className="flex gap-4 text-gray-400 shrink-0">
                    <span>{ing.weight_pct}%</span>
                    <span className="w-24 text-right">
                      {formatCurrency(ing.cost_nok_per_kg, locale)}
                      <span className="text-[10px]">/kg</span>
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </GlassCard>

          {/* EUDR Compliance Gauge */}
          <GlassCard>
            <h2 className="text-lg font-semibold text-white mb-4">
              {t("feed_chain.eudr_status")}
            </h2>

            {/* Big status indicator */}
            <div className="flex items-center gap-4 mb-6">
              <div className={`p-4 rounded-xl ${
                eudr.status === "compliant"
                  ? "bg-emerald-500/10 ring-1 ring-emerald-500/30"
                  : eudr.status === "partial"
                    ? "bg-amber-500/10 ring-1 ring-amber-500/30"
                    : "bg-rose-500/10 ring-1 ring-rose-500/30"
              }`}>
                <EudrStatusIcon status={eudr.status || "non_compliant"} />
              </div>
              <div>
                <p className={`text-xl font-bold ${eudrColor(eudr.status || "non_compliant")}`}>
                  {eudr.status === "compliant"
                    ? t("feed_chain.compliant")
                    : eudr.status === "partial"
                      ? t("feed_chain.partial")
                      : t("feed_chain.non_compliant")}
                </p>
                <p className="text-sm text-gray-400">
                  {t("feed_chain.deforestation_exposure")}: {eudr.deforestation_pct || 0}%
                </p>
              </div>
            </div>

            {/* Risk factors */}
            {(eudr.risk_factors || []).length > 0 && (
              <div className="mb-4">
                <h3 className="text-sm font-medium text-gray-300 mb-2">
                  {t("feed_chain.risk_factors")}
                </h3>
                <ul className="space-y-1">
                  {(eudr.risk_factors || []).map((f: string, i: number) => (
                    <li key={i} className="text-xs text-gray-400 flex items-start gap-1.5">
                      <AlertTriangle className="h-3 w-3 text-amber-400 mt-0.5 shrink-0" />
                      {f}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Recommendation */}
            {eudr.recommendation && (
              <div className="p-3 rounded-lg bg-white/5 border border-white/10">
                <p className="text-xs text-gray-300">
                  <span className="font-semibold text-ocean-300">
                    {t("feed_chain.recommendation")}:
                  </span>{" "}
                  {eudr.recommendation}
                </p>
              </div>
            )}
          </GlassCard>
        </div>

        {/* Cost breakdown bar chart */}
        <GlassCard>
          <h2 className="text-lg font-semibold text-white mb-4">
            {t("feed_chain.cost_breakdown")}
          </h2>
          <div className="space-y-3">
            {composition
              .sort((a: any, b: any) => {
                const aCost = a.cost_nok_per_kg * (a.weight_pct / 100) * 1000;
                const bCost = b.cost_nok_per_kg * (b.weight_pct / 100) * 1000;
                return bCost - aCost;
              })
              .map((ing: any) => {
                const ingCost = ing.cost_nok_per_kg * (ing.weight_pct / 100) * 1000;
                const pct = totalCost > 0 ? (ingCost / totalCost) * 100 : 0;
                return (
                  <div key={ing.name}>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="text-gray-300">{ing.name}</span>
                      <span className="text-gray-400">
                        {formatCurrency(ingCost, locale)} ({formatNumber(pct, locale, 1)}%)
                      </span>
                    </div>
                    <div className="h-3 bg-white/5 rounded-full overflow-hidden">
                      <motion.div
                        className="h-full rounded-full"
                        style={{ backgroundColor: ING_COLORS[ing.name] || "#64748b" }}
                        initial={{ width: 0 }}
                        animate={{ width: `${pct}%` }}
                        transition={{ duration: 0.6, delay: 0.1 }}
                      />
                    </div>
                  </div>
                );
              })}
          </div>
          <p className="text-xs text-gray-500 mt-4">
            Total: {formatCurrency(totalCost, locale)} NOK/tonne
          </p>
        </GlassCard>

        {/* Scenario Comparison */}
        <div>
          <h2 className="text-lg font-semibold text-white mb-4">
            {t("feed_chain.scenarios")}
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
            {scenarios.map((s: any) => {
              const isBaseline = s.scenario === "current";
              const costUp = (s.cost_delta_pct || 0) > 0;
              const carbonDown = (s.carbon_delta_pct || 0) < 0;
              return (
                <motion.div
                  key={s.scenario}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={`rounded-xl p-4 border transition-all ${
                    isBaseline
                      ? "bg-ocean-900/40 border-ocean-500/30"
                      : "bg-white/5 border-white/10 hover:border-white/20"
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-sm font-semibold text-white">{s.label}</h3>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded border ${riskBadge(s.eudr_risk_level)}`}>
                      EUDR: {s.eudr_status?.toUpperCase()}
                    </span>
                  </div>

                  <p className="text-2xl font-bold text-white mb-1">
                    {formatCurrency(s.cost_nok_per_tonne, locale)}
                  </p>
                  <p className="text-[10px] text-gray-500 mb-3">NOK / tonne</p>

                  {!isBaseline && (
                    <div className="flex gap-3 mb-3">
                      <div className="flex items-center gap-1 text-xs">
                        {costUp ? (
                          <TrendingUp className="h-3 w-3 text-rose-400" />
                        ) : (s.cost_delta_pct || 0) < 0 ? (
                          <TrendingDown className="h-3 w-3 text-emerald-400" />
                        ) : (
                          <Minus className="h-3 w-3 text-gray-400" />
                        )}
                        <span className={costUp ? "text-rose-400" : "text-emerald-400"}>
                          {s.cost_delta_pct > 0 ? "+" : ""}{formatNumber(s.cost_delta_pct, locale, 1)}% cost
                        </span>
                      </div>
                      <div className="flex items-center gap-1 text-xs">
                        {carbonDown ? (
                          <TrendingDown className="h-3 w-3 text-emerald-400" />
                        ) : (
                          <TrendingUp className="h-3 w-3 text-rose-400" />
                        )}
                        <span className={carbonDown ? "text-emerald-400" : "text-rose-400"}>
                          {s.carbon_delta_pct > 0 ? "+" : ""}{formatNumber(s.carbon_delta_pct, locale, 1)}% CO2
                        </span>
                      </div>
                    </div>
                  )}

                  <p className="text-xs text-gray-400">{s.description}</p>
                </motion.div>
              );
            })}
          </div>
        </div>

        {/* Supply Chain Sankey */}
        {summary?.sankey && (
          <GlassCard>
            <h2 className="text-lg font-semibold text-white mb-4">
              {t("feed_chain.supply_flow")}
            </h2>
            <FeedSankey data={summary.sankey} />
          </GlassCard>
        )}

        {/* Data provenance footer */}
        <p className="text-[10px] text-gray-600 text-center">
          Source: {summary?.data_provenance?.source || "BioMar/Skretting sustainability reports"} |
          Confidence: {Math.round((summary?.data_provenance?.confidence || 0.75) * 100)}%
        </p>
      </div>
    </ErrorBoundary>
  );
}

/* ── Simplified Sankey for feed flow ─────────────────────────────────── */
function FeedSankey({ data }: { data: any }) {
  const stages: string[] = data.stages || [];
  const nodes: any[] = data.nodes || [];
  const links: any[] = data.links || [];

  if (!nodes.length) return null;

  const W = 800;
  const H = 360;
  const PAD = 40;
  const NODE_W = 18;
  const colCount = stages.length || 4;
  const colSpacing = (W - 2 * PAD - NODE_W) / Math.max(colCount - 1, 1);

  /* Group nodes by column */
  const columns: Record<number, any[]> = {};
  for (const n of nodes) {
    const col = n.column ?? 0;
    if (!columns[col]) columns[col] = [];
    columns[col].push(n);
  }

  /* Position nodes */
  const nodePos: Record<string, { x: number; y: number; h: number }> = {};
  for (const [colStr, colNodes] of Object.entries(columns)) {
    const col = Number(colStr);
    const x = PAD + col * colSpacing;
    const totalVal = colNodes.reduce(
      (s: number, n: any) => s + (n.value || links.filter((l: any) =>
        l.source === n.id || l.target === n.id
      ).reduce((a: number, l: any) => Math.max(a, l.value || 0), 10)),
      0,
    );
    const usableH = H - 2 * PAD;
    let yOff = PAD;
    for (const n of colNodes) {
      const val = n.value || links.filter((l: any) =>
        l.source === n.id || l.target === n.id
      ).reduce((a: number, l: any) => Math.max(a, l.value || 0), 10);
      const h = Math.max((val / Math.max(totalVal, 1)) * usableH, 16);
      nodePos[n.id] = { x, y: yOff, h };
      yOff += h + 4;
    }
  }

  /* Colors per column */
  const colColors = ["#0ea5e9", "#10b981", "#f59e0b", "#06b6d4"];

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ maxHeight: 360 }}>
      {/* Stage labels */}
      {stages.map((label, i) => (
        <text
          key={label}
          x={PAD + i * colSpacing + NODE_W / 2}
          y={14}
          textAnchor="middle"
          className="fill-gray-500 text-[10px]"
          fontSize={10}
        >
          {label}
        </text>
      ))}

      {/* Links */}
      {links.map((link: any, i: number) => {
        const src = nodePos[link.source];
        const tgt = nodePos[link.target];
        if (!src || !tgt) return null;
        const sy = src.y + src.h / 2;
        const ty = tgt.y + tgt.h / 2;
        const sx = src.x + NODE_W;
        const tx = tgt.x;
        const cx1 = sx + (tx - sx) * 0.4;
        const cx2 = sx + (tx - sx) * 0.6;
        const thickness = Math.max(link.value * 0.6, 2);
        return (
          <path
            key={i}
            d={`M${sx},${sy} C${cx1},${sy} ${cx2},${ty} ${tx},${ty}`}
            fill="none"
            stroke="rgba(255,255,255,0.08)"
            strokeWidth={thickness}
          />
        );
      })}

      {/* Nodes */}
      {nodes.map((n: any) => {
        const pos = nodePos[n.id];
        if (!pos) return null;
        const col = n.column ?? 0;
        return (
          <g key={n.id}>
            <rect
              x={pos.x}
              y={pos.y}
              width={NODE_W}
              height={pos.h}
              rx={4}
              fill={colColors[col] || "#64748b"}
              opacity={0.7}
            />
            <text
              x={col < colCount - 1 ? pos.x + NODE_W + 6 : pos.x - 6}
              y={pos.y + pos.h / 2 + 3}
              textAnchor={col < colCount - 1 ? "start" : "end"}
              className="fill-gray-400"
              fontSize={9}
            >
              {n.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
