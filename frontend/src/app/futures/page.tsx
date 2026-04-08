/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";

import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import {
  TrendingUp, TrendingDown, Minus, RefreshCw, DollarSign, Download,
  BarChart2, Activity, ArrowUpRight, ArrowDownRight, LineChart,
} from "lucide-react";
import GlassCard from "@/components/GlassCard";
import KPICard from "@/components/KPICard";
import DataQualityBadge from "@/components/DataQualityBadge";
import { OcButton } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { useTranslation, formatNumber, formatCurrency } from "@/lib/i18n";
import ErrorBoundary from "@/components/ErrorBoundary";

// ── Types ────────────────────────────────────────────────────────────────────

interface CurvePoint {
  month: string;
  price_eur_kg: number;
  price_nok_kg: number;
  months_ahead: number;
  source: string;
}

interface BasisPoint {
  month: string;
  forward_nok: number;
  basis_nok: number;
  basis_pct: number;
  months_ahead: number;
}

// ── Skeleton ─────────────────────────────────────────────────────────────────

function Skeleton({ className }: { className?: string }) {
  return (
    <div className={`animate-pulse bg-white/[0.06] dark:bg-white/[0.06] rounded-lg ${className ?? ""}`} />
  );
}

// ── Forward Curve Chart (SVG) ────────────────────────────────────────────────

function ForwardCurveChart({ data, spotNok }: { data: CurvePoint[]; spotNok: number | null }) {
  if (!data.length) return <Skeleton className="h-48 w-full" />;

  const W = 800;
  const H = 200;
  const PAD = { top: 24, right: 64, bottom: 40, left: 64 };

  const prices = data.map((d) => d.price_nok_kg);
  const allPrices = spotNok ? [spotNok, ...prices] : prices;
  const minP = Math.min(...allPrices) * 0.95;
  const maxP = Math.max(...allPrices) * 1.05;
  const range = maxP - minP || 1;

  const x = (i: number) => PAD.left + (i / Math.max(data.length - 1, 1)) * (W - PAD.left - PAD.right);
  const y = (p: number) => PAD.top + (1 - (p - minP) / range) * (H - PAD.top - PAD.bottom);

  const linePts = data.map((d, i) => `${x(i)},${y(d.price_nok_kg)}`).join(" ");
  const areaPath =
    `M${x(0)},${y(data[0].price_nok_kg)} ` +
    data.map((d, i) => `L${x(i)},${y(d.price_nok_kg)}`).join(" ") +
    ` L${x(data.length - 1)},${H - PAD.bottom} L${x(0)},${H - PAD.bottom} Z`;

  const yTicks = Array.from({ length: 5 }, (_, i) => minP + (range / 4) * i);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" preserveAspectRatio="none" style={{ overflow: "visible" }}>
      <defs>
        <linearGradient id="fwdArea" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.25} />
          <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0} />
        </linearGradient>
        <linearGradient id="fwdLine" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#7c3aed" />
          <stop offset="100%" stopColor="#a78bfa" />
        </linearGradient>
      </defs>

      {/* Grid lines */}
      {yTicks.map((val, i) => (
        <g key={i}>
          <line x1={PAD.left} y1={y(val)} x2={W - PAD.right} y2={y(val)}
            stroke="rgba(255,255,255,0.05)" strokeWidth={1} />
          <text x={PAD.left - 8} y={y(val) + 4} textAnchor="end"
            fill="rgba(255,255,255,0.35)" fontSize={10}>
            {val.toFixed(0)}
          </text>
        </g>
      ))}

      {/* Spot line */}
      {spotNok && spotNok > 0 && (
        <g>
          <line x1={PAD.left} y1={y(spotNok)} x2={W - PAD.right} y2={y(spotNok)}
            stroke="#22d3ee" strokeWidth={1} strokeDasharray="6 4" opacity={0.6} />
          <text x={W - PAD.right + 4} y={y(spotNok) + 4}
            fill="#22d3ee" fontSize={10} fontWeight="bold">
            Spot {spotNok.toFixed(0)}
          </text>
        </g>
      )}

      {/* Area + line */}
      <path d={areaPath} fill="url(#fwdArea)" />
      <polyline points={linePts} fill="none" stroke="url(#fwdLine)" strokeWidth={2.5} />

      {/* Dots + labels */}
      {data.map((d, i) => (
        <g key={i}>
          <circle cx={x(i)} cy={y(d.price_nok_kg)} r={3.5}
            fill="#a78bfa" stroke="#1e1b4b" strokeWidth={1.5} />
          {i % 2 === 0 && (
            <text x={x(i)} y={H - PAD.bottom + 14} textAnchor="middle"
              fill="rgba(255,255,255,0.4)" fontSize={9}>
              {d.month.slice(5)}
            </text>
          )}
        </g>
      ))}

      {/* Y-axis label */}
      <text x={12} y={H / 2} textAnchor="middle" fill="rgba(255,255,255,0.3)"
        fontSize={9} transform={`rotate(-90, 12, ${H / 2})`}>
        NOK/kg
      </text>
    </svg>
  );
}

// ── Basis Chart (bar chart) ──────────────────────────────────────────────────

function BasisChart({ data }: { data: BasisPoint[] }) {
  if (!data.length) return <Skeleton className="h-40 w-full" />;

  const W = 800;
  const H = 160;
  const PAD = { top: 16, right: 32, bottom: 32, left: 56 };
  const barW = Math.min(30, (W - PAD.left - PAD.right) / data.length - 4);

  const values = data.map((d) => d.basis_nok);
  const maxAbs = Math.max(Math.abs(Math.min(...values)), Math.abs(Math.max(...values))) || 1;
  const zeroY = PAD.top + (H - PAD.top - PAD.bottom) / 2;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" preserveAspectRatio="none" style={{ overflow: "visible" }}>
      {/* Zero line */}
      <line x1={PAD.left} y1={zeroY} x2={W - PAD.right} y2={zeroY}
        stroke="rgba(255,255,255,0.15)" strokeWidth={1} />
      <text x={PAD.left - 8} y={zeroY + 4} textAnchor="end"
        fill="rgba(255,255,255,0.4)" fontSize={10}>0</text>

      {data.map((d, i) => {
        const cx = PAD.left + (i + 0.5) * ((W - PAD.left - PAD.right) / data.length);
        const halfRange = (H - PAD.top - PAD.bottom) / 2;
        const barH = Math.abs(d.basis_nok) / maxAbs * halfRange;
        const isPositive = d.basis_nok >= 0;
        const barY = isPositive ? zeroY - barH : zeroY;
        const color = isPositive ? "#a78bfa" : "#f87171";

        return (
          <g key={i}>
            <rect
              x={cx - barW / 2}
              y={barY}
              width={barW}
              height={Math.max(barH, 1)}
              fill={color}
              opacity={0.7}
              rx={2}
            />
            <text x={cx} y={H - PAD.bottom + 14} textAnchor="middle"
              fill="rgba(255,255,255,0.35)" fontSize={9}>
              {d.month.slice(5)}
            </text>
          </g>
        );
      })}

      {/* Labels */}
      <text x={W - PAD.right + 4} y={PAD.top + 10}
        fill="#a78bfa" fontSize={9}>Contango</text>
      <text x={W - PAD.right + 4} y={H - PAD.bottom - 4}
        fill="#f87171" fontSize={9}>Backw.</text>
    </svg>
  );
}

// ── Term Structure Indicator ─────────────────────────────────────────────────

function TermStructureIndicator({ data }: { data: any }) {
  const { locale } = useTranslation();
  if (!data || data.error) return null;

  const structure = data.structure || "flat";
  const slope = data.slope_pct || 0;

  const config: Record<string, { color: string; bg: string; icon: any; label: string }> = {
    contango: {
      color: "text-violet-400",
      bg: "bg-violet-500/10 border-violet-500/20",
      icon: ArrowUpRight,
      label: "Contango", // i18n: futures.contango
    },
    backwardation: {
      color: "text-amber-400",
      bg: "bg-amber-500/10 border-amber-500/20",
      icon: ArrowDownRight,
      label: "Backwardation", // i18n: futures.backwardation
    },
    flat: {
      color: "text-[var(--text-secondary)]",
      bg: "bg-white/[0.04] border-white/[0.08]",
      icon: Minus,
      label: "Flat",
    },
  };

  const c = config[structure] || config.flat;
  const Icon = c.icon;

  return (
    <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border ${c.bg}`}>
      <Icon className={`w-4 h-4 ${c.color}`} />
      <span className={`text-sm font-semibold ${c.color}`}>{c.label}</span>
      <span className="text-xs text-[var(--text-muted)]">
        ({slope > 0 ? "+" : ""}{formatNumber(slope, locale, 1)}%)
      </span>
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function FuturesPage() {
  const { t, locale } = useTranslation();
  const [curveData, setCurveData] = useState<any>(null);
  const [basisData, setBasisData] = useState<any>(null);
  const [settlement, setSettlement] = useState<any>(null);
  const [termStructure, setTermStructure] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [months, setMonths] = useState(12);

  const load = useCallback(async () => {
    setLoading(true);
    const [r1, r2, r3, r4] = await Promise.allSettled([
      api.futuresForwardCurve(months),
      api.futuresBasis(),
      api.futuresSettlement(),
      api.futuresTermStructure(),
    ]);
    if (r1.status === "fulfilled") setCurveData(r1.value);
    if (r2.status === "fulfilled") setBasisData(r2.value);
    if (r3.status === "fulfilled") setSettlement(r3.value);
    if (r4.status === "fulfilled") setTermStructure(r4.value);
    setLoading(false);
  }, [months]);

  useEffect(() => { load(); }, [load]);

  const spotNok = curveData?.spot_nok_kg;
  const spotEur = curveData?.spot_eur_kg;
  const eurNok = curveData?.eur_nok_rate;
  const curve: CurvePoint[] = curveData?.curve || [];
  const basisPoints: BasisPoint[] = basisData?.monthly_basis || [];
  const structure = termStructure?.structure || basisData?.structure;

  const structureColor = structure === "contango"
    ? "text-violet-400" : structure === "backwardation"
    ? "text-amber-400" : "text-[var(--text-secondary)]";

  return (
    <ErrorBoundary>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">
              {t("futures.title")}
            </h1>
            <p className="text-sm text-[var(--text-muted)] mt-1">
              Euronext ESF forward curve, basis analysis, and term structure.
              Settlement against SISALMONI spot index.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => window.print()}
              className="print:hidden flex items-center gap-1.5 px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:text-ocean-400 bg-white/[0.04] border border-white/[0.08] rounded-lg transition-colors"
              title="Export as PDF"
            >
              <Download className="w-3.5 h-3.5" /> PDF
            </button>
            {curveData?.data_provenance && (
              <DataQualityBadge provenance={curveData.data_provenance} />
            )}
            <OcButton variant="ghost" onClick={load} disabled={loading}>
              <RefreshCw className={`w-4 h-4 mr-1 ${loading ? "animate-spin" : ""}`} />
              Refresh
            </OcButton>
          </div>
        </div>

        {/* Synthetic data notice */}
        {curveData?.is_synthetic && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            className="px-4 py-3 rounded-lg border border-amber-500/20 bg-amber-500/5 text-sm"
          >
            <span className="font-semibold text-amber-400">{t("futures.synthetic_note")}</span>
            <span className="text-[var(--text-muted)] ml-2">
              Fish Pool forward prices currently unavailable. Showing SSB seasonal synthesis.
              Actual Euronext ESF prices may differ significantly.
            </span>
          </motion.div>
        )}

        {/* KPI Cards */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          <KPICard
            label={t("futures.spot_vs_future")}
            value={spotNok != null ? formatCurrency(spotNok, locale) : "--"}
            icon={DollarSign}
          />
          <KPICard
            label="Spot (EUR/kg)"
            value={spotEur != null ? `EUR ${formatNumber(spotEur, locale, 2)}` : "--"}
            icon={DollarSign}
          />
          <KPICard
            label="EUR/NOK"
            value={eurNok != null ? formatNumber(eurNok, locale, 2) : "--"}
            icon={Activity}
          />
          <KPICard
            label="FPI Settlement"
            value={settlement?.fpi_eur_kg != null ? `EUR ${formatNumber(settlement.fpi_eur_kg, locale, 2)}` : "--"}
            icon={BarChart2}
          />
          <KPICard
            label="Basis"
            value={basisData?.basis_nok != null ? `${basisData.basis_nok > 0 ? "+" : ""}${formatNumber(basisData.basis_nok, locale, 1)}` : "--"}
            delta={basisData?.basis_pct != null ? `${basisData.basis_pct > 0 ? "+" : ""}${formatNumber(basisData.basis_pct, locale, 1)}%` : undefined}
            icon={basisData?.basis_nok > 0 ? TrendingUp : basisData?.basis_nok < 0 ? TrendingDown : Minus}
          />
          <KPICard
            label="Term Structure"
            value={structure ? structure.charAt(0).toUpperCase() + structure.slice(1) : "--"}
            icon={LineChart}
          />
        </div>

        {/* Forward Curve Chart */}
        <GlassCard>
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-lg font-semibold text-[var(--text-primary)]">{t("futures.forward_curve")}</h2>
              <p className="text-xs text-[var(--text-muted)]">
                Monthly forward prices (NOK/kg) &mdash; dashed line = current spot
              </p>
            </div>
            <div className="flex items-center gap-2">
              {[6, 9, 12, 18].map((m) => (
                <button
                  key={m}
                  onClick={() => setMonths(m)}
                  className={`px-2.5 py-1 text-xs rounded-md transition-colors ${
                    months === m
                      ? "bg-violet-500/20 text-violet-300 border border-violet-500/30"
                      : "text-[var(--text-muted)] hover:text-[var(--text-secondary)] hover:bg-white/[0.04]"
                  }`}
                >
                  {m}M
                </button>
              ))}
            </div>
          </div>
          {loading ? (
            <Skeleton className="h-48 w-full" />
          ) : (
            <ForwardCurveChart data={curve} spotNok={spotNok} />
          )}
          {curveData?.methodology && (
            <p className="text-xs text-[var(--text-muted)] mt-3 opacity-60">
              {curveData.methodology}
            </p>
          )}
        </GlassCard>

        {/* Two-column: Basis + Term Structure */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Basis Analysis */}
          <GlassCard>
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-lg font-semibold text-[var(--text-primary)]">{t("futures.basis_analysis")}</h2>
                <p className="text-xs text-[var(--text-muted)]">
                  Forward - Spot spread (NOK/kg) per month
                </p>
              </div>
              {basisData?.data_provenance && (
                <DataQualityBadge provenance={basisData.data_provenance} />
              )}
            </div>
            {loading ? (
              <Skeleton className="h-40 w-full" />
            ) : basisData?.error ? (
              <p className="text-sm text-[var(--text-muted)]">{basisData.error}</p>
            ) : (
              <>
                <BasisChart data={basisPoints} />
                <div className="mt-4 flex items-center gap-4 text-sm">
                  <div>
                    <span className="text-[var(--text-muted)]">Avg Forward: </span>
                    <span className="text-[var(--text-primary)] font-semibold">
                      {basisData?.forward_avg_nok_kg != null ? formatNumber(basisData.forward_avg_nok_kg, locale, 1) : "--"} NOK
                    </span>
                  </div>
                  <div>
                    <span className="text-[var(--text-muted)]">Basis: </span>
                    <span className={`font-semibold ${structureColor}`}>
                      {basisData?.basis_nok != null ? `${basisData.basis_nok > 0 ? "+" : ""}${formatNumber(basisData.basis_nok, locale, 1)}` : "--"} NOK
                      ({basisData?.basis_pct != null ? `${basisData.basis_pct > 0 ? "+" : ""}${formatNumber(basisData.basis_pct, locale, 1)}` : "--"}%)
                    </span>
                  </div>
                </div>
                {basisData?.structure_description && (
                  <p className="text-xs text-[var(--text-muted)] mt-2 opacity-70">
                    {basisData.structure_description}
                  </p>
                )}
              </>
            )}
          </GlassCard>

          {/* Term Structure */}
          <GlassCard>
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-lg font-semibold text-[var(--text-primary)]">{t("futures.term_structure")}</h2>
                <p className="text-xs text-[var(--text-muted)]">
                  {t("futures.contango")}/{t("futures.backwardation")}
                </p>
              </div>
              {termStructure && !termStructure.error && (
                <TermStructureIndicator data={termStructure} />
              )}
            </div>
            {loading ? (
              <Skeleton className="h-40 w-full" />
            ) : termStructure?.error ? (
              <p className="text-sm text-[var(--text-muted)]">{termStructure.error}</p>
            ) : (
              <div className="space-y-4">
                {/* Near vs Far */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-3 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                    <p className="text-xs text-[var(--text-muted)]">Near-term (1-3M)</p>
                    <p className="text-lg font-bold text-[var(--text-primary)]">
                      {termStructure?.near_term_avg_nok != null ? formatNumber(termStructure.near_term_avg_nok, locale, 1) : "--"}
                      <span className="text-xs text-[var(--text-muted)] ml-1">NOK/kg</span>
                    </p>
                  </div>
                  <div className="p-3 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                    <p className="text-xs text-[var(--text-muted)]">Far-term (9-12M)</p>
                    <p className="text-lg font-bold text-[var(--text-primary)]">
                      {termStructure?.far_term_avg_nok != null ? formatNumber(termStructure.far_term_avg_nok, locale, 1) : "--"}
                      <span className="text-xs text-[var(--text-muted)] ml-1">NOK/kg</span>
                    </p>
                  </div>
                </div>

                {/* Slope + Curvature */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-3 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                    <p className="text-xs text-[var(--text-muted)]">Slope</p>
                    <p className={`text-lg font-bold ${structureColor}`}>
                      {termStructure?.slope_pct != null ? `${termStructure.slope_pct > 0 ? "+" : ""}${formatNumber(termStructure.slope_pct, locale, 1)}%` : "\u2014"}
                    </p>
                  </div>
                  <div className="p-3 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                    <p className="text-xs text-[var(--text-muted)]">Curvature</p>
                    <p className="text-lg font-bold text-[var(--text-primary)]">
                      {termStructure?.curvature_pct != null ? `${formatNumber(termStructure.curvature_pct, locale, 1)}%` : "\u2014"}
                    </p>
                  </div>
                </div>

                {/* Signal */}
                {termStructure?.signal && (
                  <div className="p-3 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                    <p className="text-xs text-[var(--text-muted)] mb-1">Market Signal</p>
                    <p className={`text-sm font-medium ${structureColor}`}>
                      {termStructure.signal.replace(/_/g, " ").replace(/\b\w/g, (c: string) => c.toUpperCase())}
                    </p>
                  </div>
                )}

                {/* Interpretation */}
                {termStructure?.interpretation && (
                  <p className="text-xs text-[var(--text-muted)] opacity-70">
                    {termStructure.interpretation}
                  </p>
                )}
              </div>
            )}
          </GlassCard>
        </div>

        {/* Settlement Data Table */}
        <GlassCard>
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-lg font-semibold text-[var(--text-primary)]">{t("futures.spot_vs_future")}</h2>
              <p className="text-xs text-[var(--text-muted)]">
                Fish Pool Index &mdash; used for Euronext ESF cash settlement
              </p>
            </div>
            {settlement?.data_provenance && (
              <DataQualityBadge provenance={settlement.data_provenance} />
            )}
          </div>
          {loading ? (
            <Skeleton className="h-24 w-full" />
          ) : settlement ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm" aria-label="FPI Settlement Data">
                <thead>
                  <tr className="border-b border-white/[0.06]">
                    <th className="text-left py-2 px-3 text-[var(--text-muted)] font-medium">Field</th>
                    <th className="text-right py-2 px-3 text-[var(--text-muted)] font-medium">Value</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-b border-white/[0.04] hover:bg-white/[0.02]">
                    <td className="py-2 px-3 text-[var(--text-secondary)]">FPI (EUR/kg)</td>
                    <td className="py-2 px-3 text-right font-mono text-[var(--text-primary)]">
                      {settlement.fpi_eur_kg != null ? `EUR ${formatNumber(settlement.fpi_eur_kg, locale, 2)}` : "--"}
                    </td>
                  </tr>
                  <tr className="border-b border-white/[0.04] hover:bg-white/[0.02]">
                    <td className="py-2 px-3 text-[var(--text-secondary)]">FPI (NOK/kg)</td>
                    <td className="py-2 px-3 text-right font-mono text-[var(--text-primary)]">
                      {settlement.fpi_nok_kg != null ? formatCurrency(settlement.fpi_nok_kg, locale) : "--"}
                    </td>
                  </tr>
                  <tr className="border-b border-white/[0.04] hover:bg-white/[0.02]">
                    <td className="py-2 px-3 text-[var(--text-secondary)]">EUR/NOK Rate</td>
                    <td className="py-2 px-3 text-right font-mono text-[var(--text-primary)]">
                      {settlement.eur_nok_rate != null ? formatNumber(settlement.eur_nok_rate, locale, 4) : eurNok != null ? formatNumber(eurNok, locale, 4) : "--"}
                    </td>
                  </tr>
                  <tr className="border-b border-white/[0.04] hover:bg-white/[0.02]">
                    <td className="py-2 px-3 text-[var(--text-secondary)]">Period</td>
                    <td className="py-2 px-3 text-right font-mono text-[var(--text-primary)]">
                      {settlement.period ?? "--"}
                    </td>
                  </tr>
                  <tr className="border-b border-white/[0.04] hover:bg-white/[0.02]">
                    <td className="py-2 px-3 text-[var(--text-secondary)]">Source</td>
                    <td className="py-2 px-3 text-right text-[var(--text-muted)]">
                      {settlement.source ?? "--"}
                    </td>
                  </tr>
                  {settlement.note && (
                    <tr className="hover:bg-white/[0.02]">
                      <td colSpan={2} className="py-2 px-3 text-xs text-amber-400/80 italic">
                        {settlement.note}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-sm text-[var(--text-muted)]">{t("common.no_data")}</p>
          )}
        </GlassCard>

        {/* Forward Curve Data Table */}
        {curve.length > 0 && (
          <GlassCard>
            <h2 className="text-lg font-semibold text-[var(--text-primary)] mb-4">Forward Prices</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm" aria-label="Forward Curve Data">
                <thead>
                  <tr className="border-b border-white/[0.06]">
                    <th className="text-left py-2 px-3 text-[var(--text-muted)] font-medium">Month</th>
                    <th className="text-right py-2 px-3 text-[var(--text-muted)] font-medium">EUR/kg</th>
                    <th className="text-right py-2 px-3 text-[var(--text-muted)] font-medium">NOK/kg</th>
                    <th className="text-right py-2 px-3 text-[var(--text-muted)] font-medium">vs Spot</th>
                    <th className="text-left py-2 px-3 text-[var(--text-muted)] font-medium">Source</th>
                  </tr>
                </thead>
                <tbody>
                  {curve.map((pt, i) => {
                    const diff = spotNok ? pt.price_nok_kg - spotNok : 0;
                    const diffPct = spotNok ? (diff / spotNok) * 100 : 0;
                    return (
                      <tr key={i} className="border-b border-white/[0.04] hover:bg-white/[0.02]">
                        <td className="py-2 px-3 font-mono text-[var(--text-primary)]">{pt.month}</td>
                        <td className="py-2 px-3 text-right font-mono text-[var(--text-secondary)]">
                          {formatNumber(pt.price_eur_kg, locale, 2)}
                        </td>
                        <td className="py-2 px-3 text-right font-mono text-[var(--text-primary)] font-semibold">
                          {formatNumber(pt.price_nok_kg, locale, 1)}
                        </td>
                        <td className={`py-2 px-3 text-right font-mono ${
                          diff > 0 ? "text-violet-400" : diff < 0 ? "text-rose-400" : "text-[var(--text-muted)]"
                        }`}>
                          {diff > 0 ? "+" : ""}{formatNumber(diff, locale, 1)} ({diffPct > 0 ? "+" : ""}{formatNumber(diffPct, locale, 1)}%)
                        </td>
                        <td className="py-2 px-3 text-xs text-[var(--text-muted)]">
                          {pt.source === "fishpool_forward" ? "Fish Pool" : "SSB Synthetic"}
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
        <p className="text-xs text-[var(--text-muted)] text-center opacity-50">
          Forward prices: fishpool.eu | Spot: SSB Table 03024 | FX: Yahoo Finance
          | Euronext ESF settlement against SISALMONI weekly index
        </p>
      </div>
    </ErrorBoundary>
  );
}
