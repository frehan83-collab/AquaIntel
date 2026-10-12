"use client";
import { useState, useMemo } from "react";
import { colors } from "@/lib/design-tokens";

/* ────────────────────────────────────────────────────────────────────────────
 * RegionalHeatmap — SVG-based heatmap of Norway's 13 Production Areas
 *
 * Shows a stylised vertical strip of the Norwegian coast (PA 1 south to
 * PA 13 north) where each zone is coloured by intensity:
 *   green (low) → yellow (moderate) → orange (elevated) → red (high)
 *
 * Pure SVG + React, no external map library needed.
 * ──────────────────────────────────────────────────────────────────────── */

export interface PADataPoint {
  /** Production area number (1-13) */
  pa: number;
  /** Numeric intensity value */
  value: number;
  /** Human-readable label for the tooltip */
  label: string;
}

interface RegionalHeatmapProps {
  data: PADataPoint[];
  title: string;
  metric: string;
  maxValue?: number;
}

/* PA metadata — approximate latitude bands for positioning + region names */
const PA_META: { pa: number; name: string }[] = [
  { pa: 1,  name: "Svenskegrensa to Jæren" },
  { pa: 2,  name: "Ryfylke" },
  { pa: 3,  name: "Karmøy to Sotra" },
  { pa: 4,  name: "Nordhordland to Stadt" },
  { pa: 5,  name: "Stadt to Hustadvika" },
  { pa: 6,  name: "Nordmøre to Sør-Trøndelag" },
  { pa: 7,  name: "Nord-Trøndelag" },
  { pa: 8,  name: "Helgeland to Bodø" },
  { pa: 9,  name: "Vestfjorden to Vesterålen" },
  { pa: 10, name: "Andøya to Senja" },
  { pa: 11, name: "Kvaløya to Loppa" },
  { pa: 12, name: "Vest-Finnmark" },
  { pa: 13, name: "Øst-Finnmark" },
];

/** Interpolate between two RGB colours */
function lerpColor(a: [number, number, number], b: [number, number, number], t: number): string {
  const r = Math.round(a[0] + (b[0] - a[0]) * t);
  const g = Math.round(a[1] + (b[1] - a[1]) * t);
  const bl = Math.round(a[2] + (b[2] - a[2]) * t);
  return `rgb(${r},${g},${bl})`;
}

/** 4-stop colour ramp: green → yellow → orange → red (using traffic-light tokens) */
function intensityColor(ratio: number): string {
  const clamped = Math.max(0, Math.min(1, ratio));
  const GREEN:  [number, number, number] = [34, 197, 94];   // traffic green
  const YELLOW: [number, number, number] = [234, 179, 8];   // traffic yellow
  const ORANGE: [number, number, number] = [249, 115, 22];  // orange-500
  const RED:    [number, number, number] = [239, 68, 68];    // traffic red

  if (clamped < 0.33) return lerpColor(GREEN, YELLOW, clamped / 0.33);
  if (clamped < 0.66) return lerpColor(YELLOW, ORANGE, (clamped - 0.33) / 0.33);
  return lerpColor(ORANGE, RED, (clamped - 0.66) / 0.34);
}

function intensityLabel(ratio: number): string {
  if (ratio < 0.25) return "Low";
  if (ratio < 0.50) return "Moderate";
  if (ratio < 0.75) return "Elevated";
  return "High";
}

export default function RegionalHeatmap({ data, title, metric, maxValue }: RegionalHeatmapProps) {
  const [hoveredPA, setHoveredPA] = useState<number | null>(null);

  /* Build a lookup from pa number → data point */
  const dataMap = useMemo(() => {
    const m = new Map<number, PADataPoint>();
    for (const d of data) m.set(d.pa, d);
    return m;
  }, [data]);

  /* Derive the effective max for colour scaling */
  const effectiveMax = useMemo(() => {
    if (maxValue && maxValue > 0) return maxValue;
    const vals = data.map((d) => d.value);
    return vals.length > 0 ? Math.max(...vals, 1) : 1;
  }, [data, maxValue]);

  /* SVG layout constants */
  const SVG_W = 280;
  const CELL_H = 34;
  const CELL_W = 44;
  const LABEL_X = 54;
  const CELL_X = 4;
  const GAP = 2;
  const TOP_PAD = 8;
  const SVG_H = TOP_PAD + 13 * (CELL_H + GAP) + 52; // +52 for legend

  /* Reversed so PA 13 (north) is at top, PA 1 (south) at bottom */
  const orderedPAs = [...PA_META].reverse();

  const hoveredData = hoveredPA !== null ? dataMap.get(hoveredPA) : null;
  const hoveredMeta = hoveredPA !== null ? PA_META.find((p) => p.pa === hoveredPA) : null;

  return (
    <div className="relative">
      {/* Title */}
      <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-2 flex items-center gap-2">
        {title}
        <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-ocean-500/10 text-ocean-400 border border-ocean-500/20 ml-auto">
          PA 1&ndash;13
        </span>
      </h3>

      <div className="flex gap-4">
        {/* SVG strip */}
        <svg
          viewBox={`0 0 ${SVG_W} ${SVG_H}`}
          className="w-full max-w-[280px] h-auto"
          style={{ minHeight: 440 }}
          role="img"
          aria-label={`${title} heatmap showing ${metric} across Norway production areas 1 to 13`}
          suppressHydrationWarning
        >
          <title suppressHydrationWarning>{title} - {metric} by Production Area</title>
          {/* Background */}
          <rect x="0" y="0" width={SVG_W} height={SVG_H} rx="8" fill="rgba(15,23,42,0.6)" />

          {orderedPAs.map((pa, idx) => {
            const d = dataMap.get(pa.pa);
            const value = d?.value ?? 0;
            const ratio = value / effectiveMax;
            const color = intensityColor(ratio);
            const y = TOP_PAD + idx * (CELL_H + GAP);
            const isHovered = hoveredPA === pa.pa;

            return (
              <g
                key={pa.pa}
                role="button"
                tabIndex={0}
                aria-label={`PA ${pa.pa} ${pa.name}: ${d ? `${value} ${metric || ""} - ${intensityLabel(ratio)}` : "No data"}`}
                onMouseEnter={() => setHoveredPA(pa.pa)}
                onMouseLeave={() => setHoveredPA(null)}
                onFocus={() => setHoveredPA(pa.pa)}
                onBlur={() => setHoveredPA(null)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    setHoveredPA(hoveredPA === pa.pa ? null : pa.pa);
                  }
                }}
                style={{ cursor: "pointer" }}
              >
                {/* Cell background */}
                <rect
                  x={CELL_X}
                  y={y}
                  width={CELL_W}
                  height={CELL_H}
                  rx="6"
                  fill={color}
                  opacity={isHovered ? 1 : 0.85}
                  stroke={isHovered ? "rgba(255,255,255,0.5)" : "rgba(255,255,255,0.08)"}
                  strokeWidth={isHovered ? 1.5 : 0.5}
                />
                {/* PA number */}
                <text
                  x={CELL_X + CELL_W / 2}
                  y={y + CELL_H / 2 + 1}
                  textAnchor="middle"
                  dominantBaseline="central"
                  fill="white"
                  fontSize="12"
                  fontWeight="700"
                  style={{ textShadow: "0 1px 3px rgba(0,0,0,0.6)" }}
                >
                  {pa.pa}
                </text>

                {/* Region name */}
                <text
                  x={LABEL_X}
                  y={y + 13}
                  fill={isHovered ? "rgba(255,255,255,0.95)" : "rgba(255,255,255,0.55)"}
                  fontSize="10"
                  fontWeight={isHovered ? "600" : "400"}
                >
                  {pa.name.length > 24 ? pa.name.slice(0, 22) + "\u2026" : pa.name}
                </text>

                {/* Value + intensity label */}
                <text
                  x={LABEL_X}
                  y={y + 27}
                  fill={isHovered ? "rgba(255,255,255,0.85)" : "rgba(255,255,255,0.35)"}
                  fontSize="9"
                  fontFamily="monospace"
                >
                  {d
                    ? `${value}${metric ? " " + metric : ""} — ${intensityLabel(ratio)}`
                    : "No data"}
                </text>
              </g>
            );
          })}

          {/* ── Legend bar ──────────────────────────────────────────── */}
          {(() => {
            const legendY = TOP_PAD + 13 * (CELL_H + GAP) + 8;
            const legendX = CELL_X;
            const legendW = SVG_W - CELL_X * 2 - 4;
            const legendH = 10;
            const gradId = "heatmap-grad";

            return (
              <g>
                <defs>
                  <linearGradient id={gradId} x1="0" y1="0" x2="1" y2="0">
                    <stop offset="0%" stopColor={colors.traffic.green} />
                    <stop offset="33%" stopColor={colors.traffic.yellow} />
                    <stop offset="66%" stopColor="rgb(249,115,22)" />
                    <stop offset="100%" stopColor={colors.traffic.red} />
                  </linearGradient>
                </defs>
                <rect
                  x={legendX}
                  y={legendY}
                  width={legendW}
                  height={legendH}
                  rx="4"
                  fill={`url(#${gradId})`}
                  opacity="0.85"
                />
                {/* Legend labels */}
                <text x={legendX} y={legendY + legendH + 12} fill="rgba(255,255,255,0.45)" fontSize="8">
                  Low
                </text>
                <text
                  x={legendX + legendW * 0.33}
                  y={legendY + legendH + 12}
                  fill="rgba(255,255,255,0.45)"
                  fontSize="8"
                  textAnchor="middle"
                >
                  Moderate
                </text>
                <text
                  x={legendX + legendW * 0.66}
                  y={legendY + legendH + 12}
                  fill="rgba(255,255,255,0.45)"
                  fontSize="8"
                  textAnchor="middle"
                >
                  Elevated
                </text>
                <text
                  x={legendX + legendW}
                  y={legendY + legendH + 12}
                  fill="rgba(255,255,255,0.45)"
                  fontSize="8"
                  textAnchor="end"
                >
                  High
                </text>

                {/* Scale endpoints */}
                <text x={legendX} y={legendY + legendH + 24} fill="rgba(255,255,255,0.3)" fontSize="7" fontFamily="monospace">
                  0
                </text>
                <text
                  x={legendX + legendW}
                  y={legendY + legendH + 24}
                  fill="rgba(255,255,255,0.3)"
                  fontSize="7"
                  fontFamily="monospace"
                  textAnchor="end"
                >
                  {effectiveMax}{metric ? ` ${metric}` : ""}
                </text>
              </g>
            );
          })()}
        </svg>
      </div>

      {/* ── Hover tooltip ───────────────────────────────────────────── */}
      {hoveredData && hoveredMeta && (
        <div className="absolute top-2 right-2 z-30 bg-[rgba(6,15,28,0.94)] backdrop-blur-2xl border border-white/[0.1] rounded-xl px-3 py-2.5 shadow-[0_8px_32px_rgba(0,0,0,0.5)] min-w-[180px] pointer-events-none">
          <p className="text-xs font-semibold text-[var(--text-primary)]">
            PA {hoveredData.pa} &mdash; {hoveredMeta.name}
          </p>
          <div className="mt-1.5 space-y-0.5 text-[10px]">
            <div className="flex justify-between gap-4">
              <span className="text-[var(--text-secondary)]">Value</span>
              <span className="font-mono font-bold" style={{ color: intensityColor(hoveredData.value / effectiveMax) }}>
                {hoveredData.value} {metric}
              </span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-[var(--text-secondary)]">Intensity</span>
              <span className="font-semibold" style={{ color: intensityColor(hoveredData.value / effectiveMax) }}>
                {intensityLabel(hoveredData.value / effectiveMax)}
              </span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-[var(--text-secondary)]">Detail</span>
              <span className="text-[var(--text-secondary)]">{hoveredData.label}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
