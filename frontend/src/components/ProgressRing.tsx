"use client";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { useCountUp } from "@/lib/useCountUp";

interface ProgressRingProps {
  /** Value from 0-100 */
  value: number;
  /** Diameter in px (default 80) */
  size?: number;
  /** Ring stroke width (default 6) */
  strokeWidth?: number;
  /** Center label text */
  label?: string;
  /** Small text below the value */
  sublabel?: string;
  /** Animate count-up on mount (default true) */
  animated?: boolean;
}

/**
 * Animated SVG circular progress indicator for compliance, welfare, and ESG scores.
 * Color-codes automatically: green (>=80), amber (50-79), red (<50).
 */
export function ProgressRing({
  value,
  size = 80,
  strokeWidth = 6,
  label,
  sublabel,
  animated = true,
}: ProgressRingProps) {
  const clamped = Math.max(0, Math.min(100, value));
  const animatedValue = useCountUp(animated ? clamped : 0, 900, 0);
  const displayValue = animated ? animatedValue : clamped;

  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (displayValue / 100) * circumference;

  // Color thresholds
  const color =
    clamped >= 80
      ? "var(--positive)"
      : clamped >= 50
      ? "var(--warning)"
      : "var(--danger)";

  const bgColor = "var(--border)";

  return (
    <div
      role="meter"
      aria-valuenow={clamped}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label ? `${label}: ${clamped}%` : `${clamped}%`}
      className="inline-flex flex-col items-center gap-1"
    >
      <div className="relative" style={{ width: size, height: size }}>
        <svg
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
          className="-rotate-90"
        >
          {/* Background ring */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={bgColor}
            strokeWidth={strokeWidth}
            opacity={0.3}
          />
          {/* Progress arc */}
          <motion.circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset: offset }}
            transition={{ duration: animated ? 0.9 : 0, ease: [0.25, 0.46, 0.45, 0.94] }}
          />
        </svg>

        {/* Center text */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span
            className={cn(
              "font-bold text-[var(--text-primary)] leading-none tracking-tight",
              size >= 100 ? "text-xl" : size >= 60 ? "text-sm" : "text-xs",
            )}
          >
            {displayValue}
            <span
              className={cn(
                "font-medium text-[var(--text-secondary)]",
                size >= 100 ? "text-xs" : "text-[9px]",
              )}
            >
              %
            </span>
          </span>
          {label && size >= 80 && (
            <span className="text-[8px] font-medium text-[var(--text-secondary)] uppercase tracking-wider mt-0.5 max-w-[80%] truncate">
              {label}
            </span>
          )}
        </div>
      </div>

      {sublabel && (
        <span className="text-[10px] font-medium text-[var(--text-secondary)]">
          {sublabel}
        </span>
      )}
    </div>
  );
}

export default ProgressRing;
