"use client";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { ReactNode } from "react";
import { colors } from "@/lib/design-tokens";

interface Props {
  children: ReactNode;
  className?: string;
  hover?: boolean;
  glow?: boolean;
  delay?: number;
  /** Accent color for the left gradient bar */
  accent?: "ocean" | "emerald" | "amber" | "rose" | "violet" | "salmon" | "none";
  /** Visual hierarchy: primary (prominent), secondary (recedes), flush (no padding/border) */
  tier?: "primary" | "secondary" | "flush";
  /** Accessible label for the card region */
  "aria-label"?: string;
}

const accentGradients = {
  ocean:   "from-ocean-500/50 via-ocean-400/20 to-transparent",
  emerald: "from-emerald-500/50 via-emerald-400/20 to-transparent",
  amber:   "from-amber-500/50 via-amber-400/20 to-transparent",
  rose:    "from-rose-500/50 via-rose-400/20 to-transparent",
  violet:  "from-violet-500/50 via-violet-400/20 to-transparent",
  salmon:  "from-salmon/50 via-salmon-300/20 to-transparent",
  none:    "",
};

export default function GlassCard({
  children, className, hover = true, glow = false, delay = 0, accent = "ocean", tier = "primary",
  "aria-label": ariaLabel,
}: Props) {
  return (
    <motion.div
      role={ariaLabel ? "region" : undefined}
      aria-label={ariaLabel}
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, delay, ease: [0.25, 0.46, 0.45, 0.94] }}
      className={cn(
        "relative overflow-hidden",
        // Tier-based visual hierarchy
        tier === "flush"
          ? "rounded-xl bg-transparent border-0 shadow-none p-0"
          : tier === "secondary"
          ? [
              "rounded-xl",
              "bg-white/60 dark:bg-fjord-midwater/30",
              "border border-slate-200 dark:border-white/[0.05]",
              "shadow-xs dark:shadow-[0_4px_16px_rgba(0,0,0,0.2)]",
              "p-4",
            ]
          : [
              "rounded-2xl",
              "bg-[var(--bg-card)] dark:bg-gradient-to-br dark:from-fjord-surface/60 dark:to-fjord-midwater/40",
              "border border-slate-200 dark:border-white/[0.08]",
              "shadow-xs dark:shadow-[0_8px_32px_rgba(0,0,0,0.3),inset_0_1px_0_rgba(255,255,255,0.03),inset_0_-1px_2px_rgba(0,0,0,0.2)]",
              "p-6",
            ],
        hover && tier !== "flush" && [
          "transition-all duration-300",
          "hover:border-salmon/30 dark:hover:border-salmon/[0.15]",
          "hover:shadow-md dark:hover:shadow-[0_12px_40px_rgba(232,115,74,0.06),inset_0_1px_0_rgba(255,255,255,0.05)]",
          "hover:-translate-y-0.5",
        ],
        glow && "shadow-glow-salmon",
        className,
      )}
    >
      {/* Left accent bar — Nordic Deep instrument panel style */}
      {accent !== "none" && (
        <div className={cn(
          "absolute top-0 left-0 bottom-0 w-[2px] bg-gradient-to-b",
          accentGradients[accent]
        )} />
      )}

      {/* Bathymetric contour overlay */}
      <div className="absolute inset-0 contour-bg pointer-events-none opacity-40 rounded-[inherit]" />

      {/* Content */}
      <div className="relative z-10">{children}</div>
    </motion.div>
  );
}
