"use client";
import { useState, useRef, useCallback, useMemo } from "react";
import { colors } from "@/lib/design-tokens";

/* ─── Types ──────────────────────────────────────────────────────────────── */

export interface DataPoint {
  x: number;
  y: number;
  label?: string;
}

interface Band {
  lo: number;
  hi: number;
}

interface InteractiveChartProps {
  data: DataPoint[];
  width?: number;
  height?: number;
  title?: string;
  unit?: string;
  color?: string;
  fillColor?: string;
  showArea?: boolean;
  yMin?: number;
  yMax?: number;
  bands?: Band[];
  bandColor?: string;
}

/* ─── Helpers ────────────────────────────────────────────────────────────── */

function clamp(v: number, lo: number, hi: number) {
  return Math.max(lo, Math.min(hi, v));
}

function formatValue(v: number): string {
  if (Math.abs(v) >= 1000) return v.toLocaleString(undefined, { maximumFractionDigits: 1 });
  if (Math.abs(v) < 0.01) return v.toFixed(4);
  if (Math.abs(v) < 10) return v.toFixed(2);
  return v.toFixed(1);
}

/* ─── Component ──────────────────────────────────────────────────────────── */

export default function InteractiveChart({
  data,
  width: W = 800,
  height: H = 200,
  title,
  unit = "",
  color = colors.accent,
  fillColor,
  showArea = true,
  yMin: forcedYMin,
  yMax: forcedYMax,
  bands,
  bandColor = "rgba(0, 212, 200, 0.12)",
}: InteractiveChartProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [activeIdx, setActiveIdx] = useState<number | null>(null);

  const PAD = useMemo(() => ({ top: 20, right: 56, bottom: 34, left: 56 }), []);

  /* ── Scales ─────────────────────────────────────────────────────────── */
  const { yMinVal, yMaxVal, yRange, plotW, plotH } = useMemo(() => {
    if (!data.length) return { yMinVal: 0, yMaxVal: 1, yRange: 1, plotW: W - 112, plotH: H - 54 };
    const vals = data.map((d) => d.y);
    const bandLos = bands ? bands.map((b) => b.lo) : [];
    const bandHis = bands ? bands.map((b) => b.hi) : [];
    const allVals = [...vals, ...bandLos, ...bandHis];
    const rawMin = Math.min(...allVals);
    const rawMax = Math.max(...allVals);
    const pad = (rawMax - rawMin) * 0.08 || 1;
    const mn = forcedYMin ?? rawMin - pad;
    const mx = forcedYMax ?? rawMax + pad;
    return {
      yMinVal: mn,
      yMaxVal: mx,
      yRange: mx - mn || 1,
      plotW: W - PAD.left - PAD.right,
      plotH: H - PAD.top - PAD.bottom,
    };
  }, [data, bands, forcedYMin, forcedYMax, W, H, PAD]);

  const xScale = useCallback(
    (i: number) => PAD.left + (data.length > 1 ? (i / (data.length - 1)) * plotW : plotW / 2),
    [data.length, plotW, PAD.left],
  );
  const yScale = useCallback(
    (v: number) => PAD.top + (1 - (v - yMinVal) / yRange) * plotH,
    [yMinVal, yRange, plotH, PAD.top],
  );

  /* ── Paths ──────────────────────────────────────────────────────────── */
  const { linePath, areaPath, bandPath } = useMemo(() => {
    if (!data.length) return { linePath: "", areaPath: "", bandPath: "" };
    const pts = data.map((d, i) => `${xScale(i)},${yScale(d.y)}`);
    const line = `M${pts.join(" L")}`;
    const area =
      `M${xScale(0)},${yScale(data[0].y)} ` +
      pts.map((p) => `L${p}`).join(" ") +
      ` L${xScale(data.length - 1)},${PAD.top + plotH} L${xScale(0)},${PAD.top + plotH} Z`;

    let band = "";
    if (bands && bands.length === data.length) {
      const upper = data.map((_, i) => `${xScale(i)},${yScale(bands[i].hi)}`);
      const lower = data
        .map((_, i) => `${xScale(i)},${yScale(bands[i].lo)}`)
        .reverse();
      band = `M${upper.join(" L")} L${lower.join(" L")} Z`;
    }
    return { linePath: line, areaPath: area, bandPath: band };
  }, [data, bands, xScale, yScale, plotH, PAD.top]);

  /* ── Y-axis ticks ───────────────────────────────────────────────────── */
  const yTicks = useMemo(() => {
    const count = 5;
    return Array.from({ length: count }, (_, i) => yMinVal + (yRange / (count - 1)) * i);
  }, [yMinVal, yRange]);

  /* ── X-axis labels (max 8) ──────────────────────────────────────────── */
  const xLabels = useMemo(() => {
    if (!data.length) return [];
    const step = Math.max(1, Math.floor(data.length / 8));
    return data
      .map((d, i) => ({ ...d, idx: i }))
      .filter((_, i) => i % step === 0 || i === data.length - 1);
  }, [data]);

  /* ── Mouse handling ─────────────────────────────────────────────────── */
  const handleMouseMove = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      if (!svgRef.current || !data.length) return;
      const rect = svgRef.current.getBoundingClientRect();
      const mouseX = ((e.clientX - rect.left) / rect.width) * W;
      let closest = 0;
      let closestDist = Infinity;
      for (let i = 0; i < data.length; i++) {
        const dist = Math.abs(xScale(i) - mouseX);
        if (dist < closestDist) {
          closestDist = dist;
          closest = i;
        }
      }
      setActiveIdx(closest);
    },
    [data, W, xScale],
  );

  const handleMouseLeave = useCallback(() => setActiveIdx(null), []);

  /* ── Gradient IDs (unique per instance, must be before early return) ── */
  const gradId = useMemo(() => `ic-grad-${Math.random().toString(36).slice(2, 8)}`, []);

  /* ── Empty state ────────────────────────────────────────────────────── */
  if (!data.length) {
    return (
      <div
        className="flex items-center justify-center rounded-xl border border-white/[0.06] bg-white/[0.02]"
        style={{ width: "100%", height: H }}
      >
        <span className="text-sm text-[var(--text-secondary)] opacity-50">No data available</span>
      </div>
    );
  }

  /* ── Active data point ──────────────────────────────────────────────── */
  const active = activeIdx !== null ? data[activeIdx] : null;
  const activeBand = activeIdx !== null && bands ? bands[activeIdx] : null;
  const activeX = activeIdx !== null ? xScale(activeIdx) : 0;
  const activeY = active ? yScale(active.y) : 0;
  const lineGradId = `${gradId}-line`;
  const areaGradId = `${gradId}-area`;

  /* ── High / Low markers ─────────────────────────────────────────────── */
  const hiIdx = data.reduce((hi, d, i) => (d.y > data[hi].y ? i : hi), 0);
  const loIdx = data.reduce((lo, d, i) => (d.y < data[lo].y ? i : lo), 0);

  return (
    <div className="relative w-full select-none">
      {title && (
        <div className="text-xs font-medium text-[var(--text-secondary)] mb-2 ml-1">{title}</div>
      )}
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        width="100%"
        preserveAspectRatio="xMidYMid meet"
        style={{ overflow: "visible" }}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        onFocus={() => { if (data.length > 0) setActiveIdx(0); }}
        onBlur={() => setActiveIdx(null)}
        onKeyDown={(e) => {
          if (e.key === "ArrowRight" && activeIdx !== null && activeIdx < data.length - 1) {
            e.preventDefault();
            setActiveIdx(activeIdx + 1);
          } else if (e.key === "ArrowLeft" && activeIdx !== null && activeIdx > 0) {
            e.preventDefault();
            setActiveIdx(activeIdx - 1);
          } else if (e.key === "Escape") {
            setActiveIdx(null);
          }
        }}
        className="cursor-crosshair"
        role="img"
        aria-label={`${title ? title + ": " : ""}Interactive chart with ${data.length} data points${unit ? " in " + unit : ""}. Use arrow keys to navigate data points.`}
        tabIndex={0}
      >
        {/* ── Defs ── */}
        <defs>
          <linearGradient id={lineGradId} x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor={color} stopOpacity={0.7} />
            <stop offset="100%" stopColor={color} />
          </linearGradient>
          <linearGradient id={areaGradId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={fillColor ?? color} stopOpacity={0.25} />
            <stop offset="100%" stopColor={fillColor ?? color} stopOpacity={0} />
          </linearGradient>
        </defs>

        {/* ── Grid lines ── */}
        {yTicks.map((val, i) => (
          <g key={`yt-${i}`}>
            <line
              x1={PAD.left}
              y1={yScale(val)}
              x2={W - PAD.right}
              y2={yScale(val)}
              stroke="rgba(255,255,255,0.05)"
              strokeWidth={1}
            />
            <text
              x={PAD.left - 8}
              y={yScale(val) + 3.5}
              textAnchor="end"
              fill="rgba(255,255,255,0.3)"
              fontSize={10}
              fontFamily="monospace"
            >
              {formatValue(val)}
            </text>
          </g>
        ))}

        {/* ── X-axis labels ── */}
        {xLabels.map((d) => (
          <text
            key={`xl-${d.idx}`}
            x={xScale(d.idx)}
            y={H - PAD.bottom + 16}
            textAnchor="middle"
            fill="rgba(255,255,255,0.3)"
            fontSize={9}
          >
            {d.label ?? String(d.x)}
          </text>
        ))}

        {/* ── Confidence band ── */}
        {bandPath && <path d={bandPath} fill={bandColor} />}

        {/* ── Area fill ── */}
        {showArea && <path d={areaPath} fill={`url(#${areaGradId})`} />}

        {/* ── Line ── */}
        <path
          d={linePath}
          fill="none"
          stroke={`url(#${lineGradId})`}
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* ── High / Low markers ── */}
        <circle cx={xScale(hiIdx)} cy={yScale(data[hiIdx].y)} r={3} fill={colors.positive} />
        <text
          x={xScale(hiIdx)}
          y={yScale(data[hiIdx].y) - 8}
          textAnchor="middle"
          fontSize={9}
          fill={colors.positive}
        >
          H {formatValue(data[hiIdx].y)}
        </text>
        <circle cx={xScale(loIdx)} cy={yScale(data[loIdx].y)} r={3} fill={colors.negative} />
        <text
          x={xScale(loIdx)}
          y={yScale(data[loIdx].y) + 14}
          textAnchor="middle"
          fontSize={9}
          fill={colors.negative}
        >
          L {formatValue(data[loIdx].y)}
        </text>

        {/* ── Crosshair ── */}
        {activeIdx !== null && (
          <>
            <line
              x1={activeX}
              y1={PAD.top}
              x2={activeX}
              y2={PAD.top + plotH}
              stroke="rgba(255,255,255,0.2)"
              strokeWidth={1}
              strokeDasharray="3,3"
            />
            <line
              x1={PAD.left}
              y1={activeY}
              x2={W - PAD.right}
              y2={activeY}
              stroke="rgba(255,255,255,0.08)"
              strokeWidth={1}
              strokeDasharray="3,3"
            />
            {/* Active dot */}
            <circle cx={activeX} cy={activeY} r={5} fill={color} opacity={0.3} />
            <circle cx={activeX} cy={activeY} r={3} fill={color} />
          </>
        )}

        {/* ── Unit label ── */}
        {unit && (
          <text x={W - PAD.right + 6} y={PAD.top + 4} fill="rgba(255,255,255,0.25)" fontSize={9}>
            {unit}
          </text>
        )}
      </svg>

      {/* ── Tooltip (HTML overlay for better rendering) ── */}
      {active && activeIdx !== null && (
        <div
          className="absolute pointer-events-none z-10"
          style={{
            left: `${(activeX / W) * 100}%`,
            top: `${(clamp(activeY - 60, 0, H - 70) / H) * 100}%`,
            transform: activeX > W * 0.7 ? "translateX(-110%)" : "translateX(10%)",
          }}
        >
          <div className="bg-[var(--card-bg)] border border-white/[0.1] rounded-lg px-3 py-2 shadow-xl backdrop-blur-md">
            <div className="text-xs font-bold text-[var(--text-primary)]">
              {formatValue(active.y)}
              {unit && <span className="text-[var(--text-secondary)] font-normal ml-1">{unit}</span>}
            </div>
            {active.label && (
              <div className="text-[10px] text-[var(--text-secondary)] mt-0.5">{active.label}</div>
            )}
            {activeBand && (
              <div className="text-[10px] text-[var(--text-secondary)] mt-0.5 opacity-70">
                Range: {formatValue(activeBand.lo)} &ndash; {formatValue(activeBand.hi)}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
