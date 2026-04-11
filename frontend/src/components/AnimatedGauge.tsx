"use client";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { useCountUp } from "@/lib/useCountUp";

interface GaugeThreshold {
  value: number;
  color: string;
}

interface AnimatedGaugeProps {
  value: number;
  min?: number;
  max?: number;
  label?: string;
  /** Unit shown after the value, e.g. "%" or "score" */
  unit?: string;
  /** Color thresholds (sorted ascending). Default: red<30, amber<70, green>=70 */
  thresholds?: GaugeThreshold[];
  /** Width in px (default 120) */
  size?: number;
  /** Animate on mount (default true) */
  animated?: boolean;
}

const DEFAULT_THRESHOLDS: GaugeThreshold[] = [
  { value: 30, color: "var(--danger)" },
  { value: 70, color: "var(--warning)" },
  { value: 100, color: "var(--positive)" },
];

/**
 * Half-circle SVG gauge for single-value metrics (0-100 range by default).
 * Includes animated arc, needle indicator, and color thresholds.
 */
export function AnimatedGauge({
  value,
  min = 0,
  max = 100,
  label,
  unit,
  thresholds = DEFAULT_THRESHOLDS,
  size = 120,
  animated = true,
}: AnimatedGaugeProps) {
  const range = max - min || 1;
  const clamped = Math.max(min, Math.min(max, value));
  const pct = ((clamped - min) / range) * 100;

  const animatedPct = useCountUp(animated ? pct : 0, 900, 0);
  const displayValue = useCountUp(animated ? clamped : 0, 900, value % 1 !== 0 ? 1 : 0);

  // Determine color from thresholds
  const sortedThresholds = [...thresholds].sort((a, b) => a.value - b.value);
  let arcColor = sortedThresholds[sortedThresholds.length - 1]?.color ?? "var(--accent)";
  for (const t of sortedThresholds) {
    if (pct <= t.value) {
      arcColor = t.color;
      break;
    }
  }

  // SVG geometry: half-circle arc
  const strokeWidth = Math.max(6, size * 0.06);
  const padding = 4;
  const svgWidth = size;
  const svgHeight = size * 0.6;
  const cx = svgWidth / 2;
  const cy = svgHeight - padding;
  const radius = (svgWidth - strokeWidth * 2 - padding * 2) / 2;

  // Arc path (180 degrees, from left to right)
  const startAngle = Math.PI; // left (180 deg)
  const endAngle = 0;        // right (0 deg)

  function polarToCartesian(angle: number) {
    return {
      x: cx + radius * Math.cos(angle),
      y: cy - radius * Math.sin(angle),
    };
  }

  const arcStart = polarToCartesian(startAngle);
  const arcEnd = polarToCartesian(endAngle);
  const bgArcPath = `M ${arcStart.x} ${arcStart.y} A ${radius} ${radius} 0 0 1 ${arcEnd.x} ${arcEnd.y}`;

  // Foreground arc — partial
  const fgAngle = startAngle - (animatedPct / 100) * Math.PI;
  const fgEnd = polarToCartesian(fgAngle);
  const largeArc = animatedPct > 50 ? 1 : 0;
  const fgArcPath = `M ${arcStart.x} ${arcStart.y} A ${radius} ${radius} 0 ${largeArc} 1 ${fgEnd.x} ${fgEnd.y}`;

  // Needle angle (in degrees, for CSS transform)
  const needleAngle = 180 - (animatedPct / 100) * 180;
  const needleLength = radius - strokeWidth;

  return (
    <div
      role="meter"
      aria-valuenow={clamped}
      aria-valuemin={min}
      aria-valuemax={max}
      aria-label={label ? `${label}: ${clamped}${unit ? " " + unit : ""}` : `${clamped}${unit ? " " + unit : ""}`}
      className="inline-flex flex-col items-center"
    >
      <div className="relative" style={{ width: svgWidth, height: svgHeight }}>
        <svg width={svgWidth} height={svgHeight} viewBox={`0 0 ${svgWidth} ${svgHeight}`}>
          {/* Background arc */}
          <path
            d={bgArcPath}
            fill="none"
            stroke="var(--border)"
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            opacity={0.3}
          />
          {/* Foreground arc */}
          <motion.path
            d={fgArcPath}
            fill="none"
            stroke={arcColor}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            initial={{ pathLength: 0, opacity: 0 }}
            animate={{ pathLength: 1, opacity: 1 }}
            transition={{ duration: animated ? 0.9 : 0, ease: [0.25, 0.46, 0.45, 0.94] }}
          />
          {/* Needle line */}
          <motion.line
            x1={cx}
            y1={cy}
            x2={cx + needleLength * Math.cos((needleAngle * Math.PI) / 180)}
            y2={cy - needleLength * Math.sin((needleAngle * Math.PI) / 180)}
            stroke={arcColor}
            strokeWidth={1.5}
            strokeLinecap="round"
            opacity={0.6}
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.6 }}
            transition={{ delay: 0.4, duration: 0.3 }}
          />
          {/* Needle dot */}
          <circle cx={cx} cy={cy} r={3} fill={arcColor} opacity={0.8} />
        </svg>

        {/* Center value */}
        <div
          className="absolute flex flex-col items-center"
          style={{ left: cx, bottom: padding + 2, transform: "translateX(-50%)" }}
        >
          <span className={cn(
            "font-bold text-[var(--text-primary)] leading-none tracking-tight font-mono",
            size >= 140 ? "text-xl" : size >= 100 ? "text-base" : "text-sm",
          )}>
            {displayValue}
            {unit && (
              <span className={cn(
                "font-medium text-[var(--text-secondary)] ml-0.5",
                size >= 140 ? "text-xs" : "text-[9px]",
              )}>
                {unit}
              </span>
            )}
          </span>
        </div>
      </div>

      {label && (
        <span className="text-[10px] font-semibold text-[var(--text-secondary)] uppercase tracking-wider -mt-1">
          {label}
        </span>
      )}

      {/* Min/Max labels */}
      <div className="flex justify-between w-full px-1 -mt-0.5">
        <span className="text-[8px] text-[var(--text-secondary)] opacity-50">{min}</span>
        <span className="text-[8px] text-[var(--text-secondary)] opacity-50">{max}</span>
      </div>
    </div>
  );
}

export default AnimatedGauge;
