/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";

import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import {
  FlaskConical, Play, TrendingUp, TrendingDown,
  ArrowUpDown, Percent, BookOpen, ChevronDown, Download,
} from "lucide-react";
import GlassCard from "@/components/GlassCard";
import KPICard from "@/components/KPICard";
import { OcButton } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { useApiError } from "@/lib/useApiError";
import { exportToCSV } from "@/lib/export";
import { useTranslation } from "@/lib/i18n";

// ─── Types ───────────────────────────────────────────────────────────────────

interface OutlookResult {
  current_price: number;
  current_spot_nok?: number;
  predicted_price: number;
  predicted_nok?: number;
  change_pct: number;
  confidence_interval: [number, number];
  scenarios: number[] | Record<string, number>;
  distribution: { p10: number; p25: number; p50: number; p75: number; p90: number };
}

interface HorizonPoint {
  horizon_weeks: number;
  horizon?: number;
  predicted_price: number;
  predicted?: number;
  predicted_nok?: number;
  change_pct: number;
  confidence_interval: [number, number];
  lo80?: number;
  hi80?: number;
  lo95?: number;
  hi95?: number;
  [key: string]: any;
}

interface MultiResult {
  horizons: HorizonPoint[];
}

interface ScenarioCol {
  label: string;
  result: OutlookResult | null;
  loading: boolean;
}

// ─── Histogram SVG ───────────────────────────────────────────────────────────

function HistogramChart({ result }: { result: OutlookResult }) {
  const { current_price, distribution } = result;
  const scenarios: number[] = Array.isArray(result.scenarios)
    ? result.scenarios
    : Object.values(result.scenarios).filter((v): v is number => typeof v === "number");
  const BUCKETS = Math.min(20, Math.max(3, scenarios.length));

  if (scenarios.length < 2) return null;

  const min = Math.min(...scenarios);
  const max = Math.max(...scenarios);
  const bucketWidth = (max - min) / BUCKETS || 1;

  const counts = Array(BUCKETS).fill(0);
  for (const v of scenarios) {
    const idx = Math.min(Math.floor((v - min) / bucketWidth), BUCKETS - 1);
    counts[idx]++;
  }
  const maxCount = Math.max(...counts);

  const W = 600;
  const H = 160;
  const PAD_L = 8;
  const PAD_R = 8;
  const PAD_T = 12;
  const PAD_B = 28;
  const chartW = W - PAD_L - PAD_R;
  const chartH = H - PAD_T - PAD_B;
  const barW = chartW / BUCKETS;

  const toX = (v: number) => PAD_L + ((v - min) / (max - min)) * chartW;
  const toBarH = (c: number) => (c / maxCount) * chartH;

  const currentX = toX(current_price);
  const p10X = toX(distribution.p10);
  const p90X = toX(distribution.p90);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" className="mt-2">
      <defs>
        <linearGradient id="bar-gain" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#10B981" stopOpacity={0.9} />
          <stop offset="100%" stopColor="#10B981" stopOpacity={0.4} />
        </linearGradient>
        <linearGradient id="bar-loss" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#F43F5E" stopOpacity={0.9} />
          <stop offset="100%" stopColor="#F43F5E" stopOpacity={0.4} />
        </linearGradient>
      </defs>

      {/* Bars */}
      {counts.map((count, i) => {
        const bx = PAD_L + i * barW;
        const bh = toBarH(count);
        const by = PAD_T + chartH - bh;
        const bucketMid = min + (i + 0.5) * bucketWidth;
        const isGain = bucketMid >= current_price;
        return (
          <rect
            key={i}
            x={bx + 1}
            y={by}
            width={barW - 2}
            height={bh}
            fill={isGain ? "url(#bar-gain)" : "url(#bar-loss)"}
            rx={2}
          />
        );
      })}

      {/* p10 dashed line */}
      <line
        x1={p10X} y1={PAD_T}
        x2={p10X} y2={PAD_T + chartH}
        stroke="rgba(255,255,255,0.25)"
        strokeWidth={1}
        strokeDasharray="4 3"
      />
      <text x={p10X - 2} y={PAD_T - 3} fontSize={9} fill="rgba(255,255,255,0.4)" textAnchor="end">P10</text>

      {/* p90 dashed line */}
      <line
        x1={p90X} y1={PAD_T}
        x2={p90X} y2={PAD_T + chartH}
        stroke="rgba(255,255,255,0.25)"
        strokeWidth={1}
        strokeDasharray="4 3"
      />
      <text x={p90X + 2} y={PAD_T - 3} fontSize={9} fill="rgba(255,255,255,0.4)" textAnchor="start">P90</text>

      {/* Current price line */}
      <line
        x1={currentX} y1={PAD_T - 4}
        x2={currentX} y2={PAD_T + chartH}
        stroke="#00D4C8"
        strokeWidth={2}
      />
      <text x={currentX} y={PAD_T - 6} fontSize={9} fill="#00D4C8" textAnchor="middle">Current</text>

      {/* X-axis labels */}
      {[0, 0.25, 0.5, 0.75, 1].map((t) => {
        const v = min + t * (max - min);
        const x = PAD_L + t * chartW;
        return (
          <text key={t} x={x} y={H - 6} fontSize={9} fill="rgba(255,255,255,0.3)" textAnchor="middle">
            {v.toFixed(1)}
          </text>
        );
      })}

      {/* Baseline */}
      <line
        x1={PAD_L} y1={PAD_T + chartH}
        x2={PAD_L + chartW} y2={PAD_T + chartH}
        stroke="rgba(255,255,255,0.08)"
        strokeWidth={1}
      />
    </svg>
  );
}

// ─── Fan Chart SVG ───────────────────────────────────────────────────────────

function FanChart({ multi }: { multi: MultiResult }) {
  const { horizons } = multi;
  if (!horizons || horizons.length === 0) return null;

  const W = 600;
  const H = 160;
  const PAD_L = 40;
  const PAD_R = 16;
  const PAD_T = 12;
  const PAD_B = 28;
  const chartW = W - PAD_L - PAD_R;
  const chartH = H - PAD_T - PAD_B;

  const allPrices = horizons.flatMap((h) => [((h as any).predicted_price || (h as any).predicted || (h as any).predicted_nok || 0) || h.predicted || h.predicted_nok || 0, ...(h.confidence_interval || [h.lo80 || 0, h.hi80 || 0])]);
  const minP = Math.min(...allPrices) * 0.98;
  const maxP = Math.max(...allPrices) * 1.02;

  const toX = (i: number) => PAD_L + (i / (horizons.length - 1)) * chartW;
  const toY = (p: number) => PAD_T + chartH - ((p - minP) / (maxP - minP)) * chartH;

  const upperPoints = horizons.map((h, i) => `${toX(i)},${toY(((h as any).confidence_interval?.[1] || (h as any).hi80 || 0))}`).join(" ");
  const lowerPoints = horizons.map((h, i) => `${toX(i)},${toY(((h as any).confidence_interval?.[0] || (h as any).lo80 || 0))}`).join(" ");
  const medianPoints = horizons.map((h, i) => `${toX(i)},${toY(((h as any).predicted_price || (h as any).predicted || (h as any).predicted_nok || 0))}`).join(" ");

  const upperArr = horizons.map((h, i) => `${toX(i)},${toY(((h as any).confidence_interval?.[1] || (h as any).hi80 || 0))}`);
  const lowerArr = [...horizons].reverse().map((h, i) => `${toX(horizons.length - 1 - i)},${toY(((h as any).confidence_interval?.[0] || (h as any).lo80 || 0))}`);
  const fanPolygon = [...upperArr, ...lowerArr].join(" ");

  const yTicks = 4;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%">
      {/* Y-axis grid */}
      {Array.from({ length: yTicks + 1 }, (_, i) => {
        const frac = i / yTicks;
        const price = minP + frac * (maxP - minP);
        const y = PAD_T + chartH - frac * chartH;
        return (
          <g key={i}>
            <line x1={PAD_L} y1={y} x2={PAD_L + chartW} y2={y} stroke="rgba(255,255,255,0.05)" strokeWidth={1} />
            <text x={PAD_L - 4} y={y + 4} fontSize={9} fill="rgba(255,255,255,0.3)" textAnchor="end">{price.toFixed(1)}</text>
          </g>
        );
      })}

      {/* Fan fill */}
      <polygon
        points={fanPolygon}
        fill="rgba(0,212,200,0.07)"
        stroke="none"
      />

      {/* Upper band */}
      <polyline
        points={upperPoints}
        fill="none"
        stroke="rgba(255,255,255,0.12)"
        strokeWidth={1}
        strokeDasharray="3 3"
      />

      {/* Lower band */}
      <polyline
        points={lowerPoints}
        fill="none"
        stroke="rgba(255,255,255,0.12)"
        strokeWidth={1}
        strokeDasharray="3 3"
      />

      {/* Median line */}
      <polyline
        points={medianPoints}
        fill="none"
        stroke="#00D4C8"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Dots at horizon points */}
      {horizons.map((h, i) => (
        <circle key={i} cx={toX(i)} cy={toY(((h as any).predicted_price || (h as any).predicted || (h as any).predicted_nok || 0))} r={3} fill="#00D4C8" />
      ))}

      {/* X-axis labels */}
      {horizons.map((h, i) => (
        <text key={i} x={toX(i)} y={H - 6} fontSize={9} fill="rgba(255,255,255,0.4)" textAnchor="middle">
          {h.horizon_weeks}W
        </text>
      ))}

      {/* Baseline */}
      <line
        x1={PAD_L} y1={PAD_T + chartH}
        x2={PAD_L + chartW} y2={PAD_T + chartH}
        stroke="rgba(255,255,255,0.08)"
        strokeWidth={1}
      />
    </svg>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function ScenariosPage() {
  const { t } = useTranslation();
  const handleError = useApiError();

  // Parameter state
  const [liceShock, setLiceShock] = useState(100);
  const [tempShock, setTempShock] = useState(0);
  const [regulatory, setRegulatory] = useState(false);
  const [horizon, setHorizon] = useState(4);
  const [numScenarios, setNumScenarios] = useState(1000);

  // Data state
  const [result, setResult] = useState<OutlookResult | null>(null);
  const [multi, setMulti] = useState<MultiResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [multiLoading, setMultiLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Scenario comparison
  const [scenarioCols, setScenarioCols] = useState<ScenarioCol[]>([
    { label: "Base Case", result: null, loading: false },
    { label: "Bear Case", result: null, loading: false },
    { label: "Bull Case", result: null, loading: false },
  ]);
  const [bioScenarios, setBioScenarios] = useState<any>(null);

  const runSimulation = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const raw = await api.priceOutlook(horizon, numScenarios);
      // Normalize API field names to match component expectations
      const data = {
        ...raw,
        current_price: raw.current_price || raw.current_spot_nok || 0,
        predicted_price: raw.predicted_price || raw.predicted_nok || 0,
        change_pct: raw.change_pct || ((raw.predicted_nok || 0) - (raw.current_spot_nok || 0)) / Math.max(raw.current_spot_nok || 1, 1) * 100,
        confidence_interval: raw.confidence_interval || [raw.bands?.p80?.[0] || 0, raw.bands?.p80?.[1] || 0],
        distribution: raw.distribution || (raw.scenarios && !Array.isArray(raw.scenarios) ? raw.scenarios : { p10: 0, p25: 0, p50: 0, p75: 0, p90: 0 }),
      };
      setResult(data);
    } catch (e: any) {
      setError(e?.message || "Simulation failed");
    } finally {
      setLoading(false);
    }
  }, [horizon, numScenarios]);

  const fetchMulti = useCallback(async () => {
    setMultiLoading(true);
    try {
      const data = await api.priceOutlookMulti();
      setMulti(data);
    } catch (e) {
      handleError("scenarios_multi_horizon")(e);
    } finally {
      setMultiLoading(false);
    }
  }, []);

  const runComparisons = useCallback(async () => {
    const configs = [
      { label: "Base Case" },
      { label: "Bear Case" },
      { label: "Bull Case" },
    ];

    setScenarioCols(configs.map((c) => ({ ...c, result: null, loading: true })));

    const results = await Promise.allSettled([
      api.priceOutlook(4, 1000),
      api.priceOutlook(8, 1000),
      api.priceOutlook(4, 500),
    ]);

    setScenarioCols(
      configs.map((c, i) => {
        const raw = results[i].status === "fulfilled"
          ? (results[i] as PromiseFulfilledResult<any>).value
          : null;
        return {
          label: c.label,
          loading: false,
          result: raw ? {
            ...raw,
            current_price: raw.current_price || raw.current_spot_nok || 0,
            predicted_price: raw.predicted_price || raw.predicted_nok || 0,
            change_pct: raw.change_pct || ((raw.predicted_nok || 0) - (raw.current_spot_nok || 0)) / Math.max(raw.current_spot_nok || 1, 1) * 100,
            confidence_interval: raw.confidence_interval || [raw.bands?.p80?.[0] || 0, raw.bands?.p80?.[1] || 0],
            distribution: raw.distribution || (raw.scenarios && !Array.isArray(raw.scenarios) ? raw.scenarios : { p10: 0, p25: 0, p50: 0, p75: 0, p90: 0 }),
          } : null,
        };
      })
    );
  }, []);

  useEffect(() => {
    runSimulation();
    fetchMulti();
    runComparisons();
    api.biomassScenarios().then(setBioScenarios).catch(handleError("scenarios_biomass"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Derived KPIs — map API fields to expected names
  const dist = result?.distribution || (result?.scenarios && !Array.isArray(result.scenarios) ? result.scenarios as any : null);
  const probGain = result?.scenarios
    ? (() => {
        const vals = Array.isArray(result.scenarios)
          ? result.scenarios
          : Object.values(result.scenarios).filter((v): v is number => typeof v === "number");
        if (vals.length === 0) return null;
        const above = vals.filter((v) => v > (result.current_price || result.current_spot_nok || 0)).length;
        return ((above / vals.length) * 100).toFixed(1);
      })()
    : null;

  const fmtNOK = (v?: number) => (v != null ? `NOK ${v.toFixed(2)}` : "—");
  const fmtPct = (v?: number) => (v != null ? `${v >= 0 ? "+" : ""}${v.toFixed(1)}%` : "—");

  return (
    <div className="min-h-screen p-6 space-y-6">
      {/* ── Header ── */}
      <motion.div
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45 }}
        className="flex items-center justify-between"
      >
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-ocean-500/10 border border-ocean-500/20 flex items-center justify-center">
            <FlaskConical className="w-5 h-5 text-ocean-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-[var(--text-primary)] tracking-tight">
              {t("nav.scenarios")}
            </h1>
            <p className="text-xs text-[var(--text-secondary)]">
              Monte Carlo price simulation — parametric stress testing
            </p>
          </div>
        </div>
        <OcButton
          variant="primary"
          size="md"
          loading={loading}
          loadingText="Running…"
          leftIcon={<Play className="w-4 h-4" />}
          onClick={runSimulation}
        >
          Run Simulation
        </OcButton>
      </motion.div>

      {/* ── Parameters ── */}
      <GlassCard accent="ocean" delay={0.05}>
        <div className="mb-4">
          <h2 className="text-sm font-semibold text-[var(--text-primary)] tracking-wide">
            Scenario Parameters
          </h2>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
            Adjust stress factors and rerun the simulation
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-8 gap-y-5">
          {/* Lice shock */}
          <div className="space-y-2">
            <div className="flex justify-between items-center">
              <label className="text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wide">
                Sea Lice Shock
              </label>
              <span className="text-xs font-bold text-ocean-400">{liceShock}% increase</span>
            </div>
            <input
              type="range"
              min={0}
              max={300}
              step={10}
              value={liceShock}
              onChange={(e) => setLiceShock(Number(e.target.value))}
              className="w-full h-1.5 appearance-none rounded-full bg-white/10 accent-ocean-400 cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-[var(--text-secondary)]">
              <span>0%</span><span>150%</span><span>300%</span>
            </div>
          </div>

          {/* Temperature shock */}
          <div className="space-y-2">
            <div className="flex justify-between items-center">
              <label className="text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wide">
                Temperature Shock
              </label>
              <span className={`text-xs font-bold ${tempShock > 0 ? "text-rose-400" : tempShock < 0 ? "text-emerald-400" : "text-[var(--text-secondary)]"}`}>
                {tempShock >= 0 ? "+" : ""}{tempShock}°C
              </span>
            </div>
            <input
              type="range"
              min={-3}
              max={3}
              step={0.5}
              value={tempShock}
              onChange={(e) => setTempShock(Number(e.target.value))}
              className="w-full h-1.5 appearance-none rounded-full bg-white/10 accent-ocean-400 cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-[var(--text-secondary)]">
              <span>−3°C</span><span>0°C</span><span>+3°C</span>
            </div>
          </div>

          {/* Regulatory tightening */}
          <div className="space-y-2">
            <label className="text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wide block">
              Regulatory Tightening
            </label>
            <div className="flex items-center gap-3 mt-1">
              <button
                onClick={() => setRegulatory(!regulatory)}
                className={`relative w-10 h-5 rounded-full transition-colors duration-200 ${
                  regulatory ? "bg-ocean-500" : "bg-white/10"
                }`}
              >
                <span
                  className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform duration-200 ${
                    regulatory ? "translate-x-5" : "translate-x-0.5"
                  }`}
                />
              </button>
              <span className="text-xs text-[var(--text-secondary)]">
                {regulatory ? (
                  <span className="text-amber-400">−10% supply shock applied</span>
                ) : (
                  "Off"
                )}
              </span>
            </div>
          </div>

          {/* Horizon select */}
          <div className="space-y-2">
            <label className="text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wide block">
              Forecast Horizon
            </label>
            <div className="relative">
              <select
                value={horizon}
                onChange={(e) => setHorizon(Number(e.target.value))}
                className="w-full h-9 px-3 pr-8 text-sm rounded-lg bg-white/[0.04] border border-white/[0.08] text-[var(--text-primary)] appearance-none cursor-pointer focus:outline-none focus:border-ocean-500/40"
              >
                {[4, 8, 12, 16].map((w) => (
                  <option key={w} value={w}>{w} Weeks</option>
                ))}
              </select>
              <ChevronDown className="absolute right-2.5 top-2.5 w-3.5 h-3.5 text-[var(--text-secondary)] pointer-events-none" />
            </div>
          </div>

          {/* Scenarios select */}
          <div className="space-y-2">
            <label className="text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wide block">
              Monte Carlo Paths
            </label>
            <div className="relative">
              <select
                value={numScenarios}
                onChange={(e) => setNumScenarios(Number(e.target.value))}
                className="w-full h-9 px-3 pr-8 text-sm rounded-lg bg-white/[0.04] border border-white/[0.08] text-[var(--text-primary)] appearance-none cursor-pointer focus:outline-none focus:border-ocean-500/40"
              >
                {[500, 1000, 2000, 5000].map((n) => (
                  <option key={n} value={n}>{n.toLocaleString()} scenarios</option>
                ))}
              </select>
              <ChevronDown className="absolute right-2.5 top-2.5 w-3.5 h-3.5 text-[var(--text-secondary)] pointer-events-none" />
            </div>
          </div>
        </div>
      </GlassCard>

      {/* ── Error ── */}
      {error && (
        <div className="rounded-xl border border-rose-500/20 bg-rose-500/[0.06] px-4 py-3 text-sm text-rose-400">
          {error}
        </div>
      )}

      {/* ── KPI Cards ── */}
      {result && dist && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <KPICard
            label="Median Outcome (P50)"
            value={fmtNOK(dist.p50)}
            delta={fmtPct(result.change_pct)}
            deltaType={result.change_pct >= 0 ? "positive" : "negative"}
            icon={ArrowUpDown}
            delay={0.05}
          />
          <KPICard
            label="Upside (P90)"
            value={fmtNOK(dist.p90)}
            delta={`+${((dist.p90 - result.current_price) / result.current_price * 100).toFixed(1)}%`}
            deltaType="positive"
            icon={TrendingUp}
            delay={0.1}
          />
          <KPICard
            label="Downside (P10)"
            value={fmtNOK(dist.p10)}
            delta={`${((dist.p10 - result.current_price) / result.current_price * 100).toFixed(1)}%`}
            deltaType="negative"
            icon={TrendingDown}
            delay={0.15}
          />
          <KPICard
            label="Probability of Gain"
            value={probGain != null ? `${probGain}%` : "—"}
            delta={Number(probGain) > 50 ? "Bullish tilt" : "Bearish tilt"}
            deltaType={Number(probGain) > 50 ? "positive" : "negative"}
            icon={Percent}
            delay={0.2}
          />
        </div>
      )}

      {/* ── Distribution Chart ── */}
      {(result || loading) && (
        <GlassCard accent="ocean" delay={0.1}>
          <div className="mb-3 flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-[var(--text-primary)]">
                Outcome Distribution
              </h2>
              <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                Histogram of {numScenarios.toLocaleString()} Monte Carlo paths ·{" "}
                <span className="text-emerald-400">green = above current</span> ·{" "}
                <span className="text-rose-400">red = below current</span>
              </p>
            </div>
            {result && (
              <span className="text-xs text-[var(--text-secondary)]">
                Current:{" "}
                <span className="text-ocean-400 font-semibold">{fmtNOK(result.current_price)}</span>
              </span>
            )}
          </div>
          {loading ? (
            <div className="h-40 flex items-center justify-center text-sm text-[var(--text-secondary)] animate-pulse">
              Running simulation…
            </div>
          ) : result ? (
            <HistogramChart result={result} />
          ) : null}
        </GlassCard>
      )}

      {/* ── Horizon Fan Chart ── */}
      <GlassCard accent="ocean" delay={0.15}>
        <div className="mb-3">
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">
            Horizon Fan Chart
          </h2>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
            Predicted price across 4 / 8 / 12 / 16-week horizons with 80% confidence band
          </p>
        </div>
        {multiLoading ? (
          <div className="h-40 flex items-center justify-center text-sm text-[var(--text-secondary)] animate-pulse">
            Loading fan chart…
          </div>
        ) : multi ? (
          <FanChart multi={multi} />
        ) : (
          <div className="h-40 flex items-center justify-center text-xs text-[var(--text-secondary)]">
            No horizon data available
          </div>
        )}
      </GlassCard>

      {/* ── Scenario Comparison Table ── */}
      <GlassCard accent="ocean" delay={0.2}>
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-[var(--text-primary)]">
              Scenario Comparison
            </h2>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">
              Named stress scenarios side-by-side
            </p>
          </div>
          {scenarioCols.some(c => c.result) && (
            <OcButton variant="ghost" size="sm" leftIcon={<Download className="w-3.5 h-3.5" />}
              onClick={() => exportToCSV(scenarioCols.filter(c => c.result).map(c => ({
                Scenario: c.label, "Predicted (NOK)": c.result!.predicted_price,
                "Change %": c.result!.change_pct, "P10 (NOK)": c.result!.distribution.p10,
                "P50 (NOK)": c.result!.distribution.p50, "P90 (NOK)": c.result!.distribution.p90,
                "P10-P90 Range": c.result!.distribution.p90 - c.result!.distribution.p10,
              })), "scenario_comparison")}>Export CSV</OcButton>
          )}
        </div>

        <div className="grid grid-cols-3 gap-4">
          {scenarioCols.map((col, idx) => {
            const accentClasses = [
              "border-ocean-500/20 bg-ocean-500/[0.04]",
              "border-rose-500/20 bg-rose-500/[0.04]",
              "border-emerald-500/20 bg-emerald-500/[0.04]",
            ];
            const labelColors = ["text-ocean-400", "text-rose-400", "text-emerald-400"];
            const descriptions = [
              "Current parameters",
              "Lice +200%, Temp +2°C, Regulatory on",
              "Lice −50%, Temp −1°C, Regulatory off",
            ];

            return (
              <div
                key={idx}
                className={`rounded-xl border p-4 space-y-3 ${accentClasses[idx]}`}
              >
                <div>
                  <div className={`text-xs font-bold uppercase tracking-widest ${labelColors[idx]}`}>
                    {col.label}
                  </div>
                  <div className="text-[10px] text-[var(--text-secondary)] mt-0.5">
                    {descriptions[idx]}
                  </div>
                </div>

                {col.loading ? (
                  <div className="space-y-2 animate-pulse">
                    {[...Array(4)].map((_, i) => (
                      <div key={i} className="h-3 bg-white/5 rounded" />
                    ))}
                  </div>
                ) : col.result ? (
                  <div className="space-y-2 text-xs">
                    <div className="flex justify-between">
                      <span className="text-[var(--text-secondary)]">Predicted</span>
                      <span className="font-semibold text-[var(--text-primary)]">
                        {fmtNOK(col.result.predicted_price)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[var(--text-secondary)]">Change</span>
                      <span className={col.result.change_pct >= 0 ? "text-emerald-400" : "text-rose-400"}>
                        {fmtPct(col.result.change_pct)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[var(--text-secondary)]">P10</span>
                      <span className="text-rose-400">{fmtNOK(col.result.distribution.p10)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[var(--text-secondary)]">P50</span>
                      <span className="text-[var(--text-primary)]">{fmtNOK(col.result.distribution.p50)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[var(--text-secondary)]">P90</span>
                      <span className="text-emerald-400">{fmtNOK(col.result.distribution.p90)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[var(--text-secondary)]">P10–P90 Range</span>
                      <span className="text-[var(--text-secondary)] text-[10px]">
                        {(col.result.distribution.p90 - col.result.distribution.p10).toFixed(2)}
                      </span>
                    </div>
                  </div>
                ) : (
                  <div className="text-[10px] text-[var(--text-secondary)]">No data</div>
                )}
              </div>
            );
          })}
        </div>

        <div className="mt-4 flex justify-end">
          <OcButton variant="secondary" size="sm" onClick={runComparisons}>
            Refresh Comparisons
          </OcButton>
        </div>
      </GlassCard>

      {/* ── Biomass Regulatory Scenarios ── */}
      {bioScenarios && (
        <GlassCard accent="emerald" delay={0.22}>
          <div className="mb-4">
            <h2 className="text-sm font-semibold text-[var(--text-primary)]">
              Biomass Regulatory Scenarios
            </h2>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">
              Traffic Light System impact on national biomass capacity
            </p>
          </div>
          <div className="grid grid-cols-3 gap-4">
            {[
              { key: "all_red", label: "All Red", color: "rose", desc: "Maximum regulatory restriction" },
              { key: "current", label: "Current Mix", color: "ocean", desc: "Actual traffic light status" },
              { key: "all_green", label: "All Green", color: "emerald", desc: "Maximum growth allowance" },
            ].map(({ key, label, color, desc }) => {
              const sc = bioScenarios[key] || bioScenarios;
              if (!sc || typeof sc !== "object") return null;
              const mab = sc.national_mab || sc.mab || 0;
              const util = sc.utilization || sc.utilization_pct || 0;
              const delta = sc.harvest_delta || sc.delta_pct || 0;
              return (
                <div key={key} className={`rounded-xl border p-4 space-y-3 border-${color}-500/20 bg-${color}-500/[0.04]`}>
                  <div>
                    <div className={`text-xs font-bold uppercase tracking-widest text-${color}-400`}>{label}</div>
                    <div className="text-[10px] text-[var(--text-secondary)] mt-0.5">{desc}</div>
                  </div>
                  <div className="space-y-2 text-xs">
                    <div className="flex justify-between">
                      <span className="text-[var(--text-secondary)]">National MAB</span>
                      <span className="font-semibold text-[var(--text-primary)]">{typeof mab === "number" ? `${(mab / 1000).toFixed(0)}k t` : String(mab)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[var(--text-secondary)]">Utilization</span>
                      <span className="font-semibold text-[var(--text-primary)]">{typeof util === "number" ? `${(util * 100).toFixed(1)}%` : String(util)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[var(--text-secondary)]">Harvest Impact</span>
                      <span className={typeof delta === "number" && delta >= 0 ? "text-emerald-400" : "text-rose-400"}>
                        {typeof delta === "number" ? `${delta >= 0 ? "+" : ""}${(delta * 100).toFixed(1)}%` : String(delta)}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </GlassCard>
      )}

      {/* ── Interpretation ── */}
      <GlassCard accent="none" hover={false} delay={0.25}>
        <div className="flex items-start gap-3">
          <div className="w-8 h-8 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
            <BookOpen className="w-4 h-4 text-amber-400" />
          </div>
          <div className="space-y-2">
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">
              How the Simulation Works
            </h3>
            <div className="text-xs text-[var(--text-secondary)] space-y-1.5 leading-relaxed">
              <p>
                <span className="text-[var(--text-primary)] font-medium">Sea lice shock</span> — elevated lice
                counts trigger mandatory treatment cycles, temporarily reducing harvest throughput.
                A 100% lice increase is modelled as roughly a 5–8% supply reduction over the horizon,
                which historically correlates with proportional spot price increases.
              </p>
              <p>
                <span className="text-[var(--text-primary)] font-medium">Temperature shock</span> — water
                temperatures above 14°C accelerate lice reproduction and reduce fish appetite,
                compressing growth rates. Temperatures below 6°C slow processing yields.
                Each ±1°C deviation is calibrated against Norwegian Meteorological Institute seasonal norms.
              </p>
              <p>
                <span className="text-[var(--text-primary)] font-medium">Regulatory tightening</span> — enabling
                this toggle applies a fixed −10% supply shock across all simulation paths, representing
                a tightening of the Norwegian Traffic Light System from green to yellow zones.
              </p>
              <p>
                <span className="text-[var(--text-primary)] font-medium">Monte Carlo paths</span> — the model
                samples {numScenarios.toLocaleString()} stochastic price trajectories using a geometric
                Brownian motion base plus the above parametric shocks. The distribution percentiles
                (P10/P50/P90) bound 80% of simulated outcomes.
              </p>
            </div>
          </div>
        </div>
      </GlassCard>
    </div>
  );
}
