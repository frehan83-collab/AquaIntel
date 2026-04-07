"use client";
import { motion, AnimatePresence } from "framer-motion";

/* ─────────────────────────────────────────────────────────────────
 * Premium Glassmorphic Chart Tooltip
 * ─────────────────────────────────────────────────────────────────
 * Recharts custom tooltip with:
 *  - Frosted glass background
 *  - Animated entry
 *  - Color-coded data labels
 *  - Smart value formatting
 * ───────────────────────────────────────────────────────────────── */

interface TooltipProps {
  active?: boolean;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload?: any[];
  label?: string;
  /** Optional unit suffix */
  unit?: string;
  /** Custom label formatter */
  labelFormatter?: (label: string) => string;
  /** Precision for numeric values */
  precision?: number;
}

export default function OceanTooltip({
  active,
  payload,
  label,
  unit = "",
  labelFormatter,
  precision = 2,
}: TooltipProps) {
  if (!active || !payload?.length) return null;

  const displayLabel = labelFormatter ? labelFormatter(String(label)) : label;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: 4, scale: 0.96 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 4, scale: 0.96 }}
        transition={{ duration: 0.15 }}
        className="
          relative rounded-xl px-4 py-3 min-w-[160px]
          bg-[rgba(6,15,28,0.92)] backdrop-blur-2xl
          border border-white/[0.08]
          shadow-[0_8px_32px_rgba(0,0,0,0.5),0_0_0_1px_rgba(255,255,255,0.04)]
        "
      >
        {/* Top accent */}
        <div className="absolute top-0 left-3 right-3 h-px bg-gradient-to-r from-transparent via-ocean-500/40 to-transparent" />

        {/* Label */}
        <p className="text-[11px] font-medium text-[var(--text-secondary)] mb-2 tracking-wide uppercase">
          {displayLabel}
        </p>

        {/* Values */}
        <div className="space-y-1.5">
          {payload.map((entry, i) => {
            const value = typeof entry.value === "number"
              ? entry.value.toFixed(precision)
              : entry.value;
            return (
              <div key={i} className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-2">
                  <div
                    className="w-2 h-2 rounded-full shadow-[0_0_6px_currentColor]"
                    style={{ backgroundColor: entry.color, color: entry.color }}
                  />
                  <span className="text-[12px] text-[var(--text-secondary)]">
                    {entry.name || entry.dataKey}
                  </span>
                </div>
                <span className="text-[12px] font-semibold text-[var(--text-primary)] font-mono tabular-nums">
                  {value}{unit}
                </span>
              </div>
            );
          })}
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
