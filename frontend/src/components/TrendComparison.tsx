"use client";
import { useState, useMemo } from "react";
import { colors } from "@/lib/design-tokens";
import { useTranslation, formatNumber } from "@/lib/i18n";

interface DataPoint {
  week: number;
  value: number;
}

interface TrendComparisonProps {
  metric: string;
  label?: string;
  unit?: string;
  currentYear: DataPoint[];
  previousYear: DataPoint[];
  twoYearsAgo: DataPoint[];
  years?: number[];
}

function buildPath(data: DataPoint[], width: number, height: number, minVal: number, maxVal: number): string {
  if (data.length < 2) return "";
  const range = maxVal - minVal || 1;
  const xStep = width / (data.length - 1);
  return data
    .map((d, i) => {
      const x = i * xStep;
      const y = height - ((d.value - minVal) / range) * height;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

export default function TrendComparison({
  metric,
  label,
  unit = "",
  currentYear,
  previousYear,
  twoYearsAgo,
  years = [],
}: TrendComparisonProps) {
  const { locale } = useTranslation();
  const [hovered, setHovered] = useState<number | null>(null);

  const { minVal, maxVal, currentLatest, prevLatest, delta, deltaDir } = useMemo(() => {
    const all = [...currentYear, ...previousYear, ...twoYearsAgo].map((d) => d.value);
    const mn = all.length > 0 ? Math.min(...all) : 0;
    const mx = all.length > 0 ? Math.max(...all) : 1;
    const cLatest = currentYear.length > 0 ? currentYear[currentYear.length - 1].value : 0;
    const pLatest = previousYear.length > 0 ? previousYear[previousYear.length - 1].value : 0;
    const d = pLatest !== 0 ? ((cLatest - pLatest) / Math.abs(pLatest)) * 100 : 0;
    const dir = d > 0 ? "up" : d < 0 ? "down" : "flat";
    return { minVal: mn, maxVal: mx, currentLatest: cLatest, prevLatest: pLatest, delta: d, deltaDir: dir };
  }, [currentYear, previousYear, twoYearsAgo]);

  const W = 160;
  const H = 48;

  const pathCurrent = buildPath(currentYear, W, H, minVal, maxVal);
  const pathPrev = buildPath(previousYear, W, H, minVal, maxVal);
  const pathTwo = buildPath(twoYearsAgo, W, H, minVal, maxVal);

  // Graceful fallback for empty data
  if (currentYear.length === 0 && previousYear.length === 0) {
    return (
      <div className="flex items-center gap-3 p-3 rounded-xl bg-white/[0.03] border border-white/[0.06]">
        <div className="text-xs text-[var(--text-secondary)]">
          {label || metric} YoY &mdash; No data available
        </div>
      </div>
    );
  }

  const hoveredWeek = hovered !== null && currentYear[hovered] ? currentYear[hovered] : null;
  const hoveredPrev = hovered !== null && previousYear[hovered] ? previousYear[hovered] : null;

  return (
    <div
      className="relative flex items-center gap-3 p-3 rounded-xl bg-white/[0.03] border border-white/[0.06] hover:border-ocean-500/20 transition-all group"
      onMouseLeave={() => setHovered(null)}
    >
      {/* Sparkline SVG */}
      <div className="relative shrink-0">
        <svg width={W} height={H} className="overflow-visible" aria-label={`${label || metric} YoY trend`}>
          {/* 2 years ago */}
          {pathTwo && (
            <path d={pathTwo} fill="none" stroke="rgba(255,255,255,0.15)" strokeWidth="1" />
          )}
          {/* Previous year */}
          {pathPrev && (
            <path d={pathPrev} fill="none" stroke="rgba(255,255,255,0.3)" strokeWidth="1.2" />
          )}
          {/* Current year */}
          {pathCurrent && (
            <path d={pathCurrent} fill="none" stroke={colors.accent} strokeWidth="2" />
          )}
          {/* Hover indicator */}
          {hovered !== null && currentYear[hovered] && (
            <circle
              cx={((hovered / Math.max(currentYear.length - 1, 1)) * W).toFixed(1)}
              cy={(H - ((currentYear[hovered].value - minVal) / (maxVal - minVal || 1)) * H).toFixed(1)}
              r="3"
              fill={colors.accent}
              stroke="white"
              strokeWidth="1"
            />
          )}
        </svg>
        {/* Hover area */}
        <div
          className="absolute inset-0"
          role="button"
          tabIndex={0}
          aria-label={`${label || metric} trend comparison. Use arrow keys to navigate weekly data points.`}
          onMouseMove={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const idx = Math.round((x / rect.width) * (currentYear.length - 1));
            setHovered(Math.max(0, Math.min(currentYear.length - 1, idx)));
          }}
          onFocus={() => { if (currentYear.length > 0) setHovered(0); }}
          onBlur={() => setHovered(null)}
          onKeyDown={(e) => {
            if (e.key === "ArrowRight" && hovered !== null && hovered < currentYear.length - 1) {
              e.preventDefault();
              setHovered(hovered + 1);
            } else if (e.key === "ArrowLeft" && hovered !== null && hovered > 0) {
              e.preventDefault();
              setHovered(hovered - 1);
            } else if (e.key === "Escape") {
              setHovered(null);
            }
          }}
        />
      </div>

      {/* Value + Delta */}
      <div className="flex flex-col min-w-0">
        <span className="text-[10px] text-[var(--text-secondary)] uppercase tracking-wider truncate">
          {label || metric} YoY
        </span>
        <span className="text-sm font-bold text-[var(--text-primary)]">
          {formatNumber(currentLatest, locale, metric === "price" ? 1 : 2)}{unit && ` ${unit}`}
        </span>
        <span
          className={`text-[11px] font-medium flex items-center gap-0.5 ${
            deltaDir === "up" ? "text-emerald-400" : deltaDir === "down" ? "text-rose-400" : "text-[var(--text-secondary)]"
          }`}
        >
          {deltaDir === "up" ? "\u25B2" : deltaDir === "down" ? "\u25BC" : "\u2500"}
          {formatNumber(Math.abs(delta), locale, 1)}% vs {years[1] || "prev"}
        </span>
      </div>

      {/* Tooltip on hover */}
      {hoveredWeek && (
        <div className="absolute -top-16 left-1/2 -translate-x-1/2 px-3 py-2 rounded-lg bg-ocean-950/95 border border-white/10 text-[10px] z-50 whitespace-nowrap shadow-lg pointer-events-none">
          <div className="text-ocean-400 font-semibold">
            Wk {hoveredWeek.week}: {formatNumber(hoveredWeek.value, locale, 2)}{unit && ` ${unit}`}
          </div>
          {hoveredPrev && (
            <div className="text-white/50">
              {years[1] || "Prev"} Wk {hoveredPrev.week}: {formatNumber(hoveredPrev.value, locale, 2)}{unit && ` ${unit}`}
            </div>
          )}
          <div className="text-[9px] text-white/30 mt-0.5 flex gap-3">
            <span className="flex items-center gap-1">
              <span className="w-2 h-0.5 bg-[var(--accent)] inline-block rounded" /> {years[0] || "Current"}
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-0.5 bg-white/30 inline-block rounded" /> {years[1] || "Prev"}
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-0.5 bg-white/15 inline-block rounded" /> {years[2] || "2yr"}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
