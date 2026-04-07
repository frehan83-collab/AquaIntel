"use client";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { type ReactNode } from "react";

/* ─────────────────────────────────────────────────────────────────
 * Glassmorphic Chart Container
 * ─────────────────────────────────────────────────────────────────
 * Wraps every chart in a premium glass card with:
 *  - Frosted glass backdrop
 *  - Gradient top accent line
 *  - Subtle noise texture
 *  - Header + optional subtitle + optional badge
 *  - Footer annotation slot
 * ───────────────────────────────────────────────────────────────── */

interface ChartContainerProps {
  title: string;
  subtitle?: string;
  badge?: ReactNode;
  footer?: ReactNode;
  children: ReactNode;
  className?: string;
  delay?: number;
  /** Accent color for the top gradient line */
  accent?: "ocean" | "emerald" | "amber" | "rose" | "violet";
}

const accentGradients = {
  ocean:   "from-ocean-500/60 via-ocean-400/30 to-transparent",
  emerald: "from-emerald-500/60 via-emerald-400/30 to-transparent",
  amber:   "from-amber-500/60 via-amber-400/30 to-transparent",
  rose:    "from-rose-500/60 via-rose-400/30 to-transparent",
  violet:  "from-violet-500/60 via-violet-400/30 to-transparent",
};

export default function ChartContainer({
  title,
  subtitle,
  badge,
  footer,
  children,
  className,
  delay = 0,
  accent = "ocean",
}: ChartContainerProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay, ease: "easeOut" }}
      className={cn(
        "relative overflow-hidden rounded-2xl",
        "bg-white/[0.03] backdrop-blur-md",
        "border border-white/[0.06]",
        "shadow-[0_8px_32px_rgba(0,0,0,0.25),inset_0_1px_0_rgba(255,255,255,0.04)]",
        "transition-all duration-300",
        "hover:border-white/[0.1]",
        "hover:shadow-[0_12px_40px_rgba(0,0,0,0.3),inset_0_1px_0_rgba(255,255,255,0.06)]",
        className
      )}
    >
      {/* Top accent gradient line */}
      <div className={cn(
        "absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r",
        accentGradients[accent]
      )} />

      {/* Header */}
      <div className="relative px-6 pt-5 pb-3 flex items-start justify-between">
        <div>
          <h3 className="text-sm font-semibold text-[var(--text-primary)] tracking-tight">
            {title}
          </h3>
          {subtitle && (
            <p className="text-[11px] text-[var(--text-secondary)] mt-0.5">
              {subtitle}
            </p>
          )}
        </div>
        {badge && (
          <div className="flex items-center">{badge}</div>
        )}
      </div>

      {/* Chart area */}
      <div className="relative px-4 pb-2">
        {children}
      </div>

      {/* Footer annotation */}
      {footer && (
        <div className="relative px-6 pb-4 pt-1">
          {footer}
        </div>
      )}
    </motion.div>
  );
}
