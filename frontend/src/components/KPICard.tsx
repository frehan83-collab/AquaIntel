"use client";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { LucideIcon } from "lucide-react";
import { useCountUp } from "@/lib/useCountUp";
import { useValueFlash } from "@/lib/useValueFlash";
import { colors, chartPalette } from "@/lib/design-tokens";

interface Props {
  label: string;
  value: string | number;
  delta?: string;
  deltaType?: "positive" | "negative" | "neutral";
  icon?: LucideIcon;
  pulse?: boolean;
  delay?: number;
  /** Optional sparkline data (array of 8-12 numbers) */
  sparkline?: number[];
  /** Hero variant: 2x size for primary metrics */
  hero?: boolean;
  /** Optional unit label shown after value */
  unit?: string;
}

/** Inline sparkline SVG — no extra deps */
function MiniSparkline({ data, color }: { data: number[]; color: string }) {
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;
  const w = 80;
  const h = 24;
  const points = data
    .map((v, i) => `${(i / (data.length - 1)) * w},${h - ((v - min) / range) * h}`)
    .join(" ");

  return (
    <svg width={w} height={h} className="opacity-40">
      <defs>
        <linearGradient id={`spark-${color}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity={0.4} />
          <stop offset="100%" stopColor={color} stopOpacity={0} />
        </linearGradient>
      </defs>
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <polygon
        points={`0,${h} ${points} ${w},${h}`}
        fill={`url(#spark-${color})`}
      />
    </svg>
  );
}

export default function KPICard({
  label, value, delta, deltaType = "neutral", icon: Icon, pulse, delay = 0, sparkline,
  hero = false, unit,
}: Props) {
  const deltaColor = deltaType === "positive"
    ? "text-emerald-400"
    : deltaType === "negative"
    ? "text-salmon"
    : "text-[var(--text-secondary)]";

  const sparkColor = deltaType === "positive"
    ? "#10B981"
    : deltaType === "negative"
    ? "#E8734A"
    : "#00D4C8";

  const flash = useValueFlash(value);

  // Count-up animation for numeric values
  const numericValue = typeof value === "number" ? value : parseFloat(String(value));
  const isNumeric = !isNaN(numericValue) && isFinite(numericValue);
  const decimals = isNumeric ? (String(value).includes(".") ? String(value).split(".")[1]?.length || 0 : 0) : 0;
  const animatedValue = useCountUp(isNumeric ? numericValue : 0, 800, decimals);
  const displayValue = isNumeric ? animatedValue : value;

  return (
    <motion.div
      role="status"
      aria-label={`${label}: ${value}${unit ? " " + unit : ""}${delta ? ", change: " + delta : ""}`}
      initial={{ opacity: 0, scale: 0.97 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.4, delay, ease: [0.25, 0.46, 0.45, 0.94] }}
      className={cn(
        "relative overflow-hidden card-hover",
        flash && "flash-update",
        hero ? "rounded-2xl" : "rounded-xl",
        "bg-[var(--bg-card)] dark:bg-gradient-to-br dark:from-fjord-surface/60 dark:to-fjord-midwater/40",
        "border border-slate-200 dark:border-white/[0.08]",
        hero
          ? "shadow-sm dark:shadow-[0_12px_48px_rgba(0,0,0,0.35),inset_0_1px_0_rgba(255,255,255,0.04),inset_0_-1px_2px_rgba(0,0,0,0.2)]"
          : "shadow-sm dark:shadow-[0_8px_32px_rgba(0,0,0,0.3),inset_0_1px_0_rgba(255,255,255,0.03),inset_0_-1px_2px_rgba(0,0,0,0.2)]",
        hero ? "p-6 flex flex-col gap-3" : "p-4 flex flex-col gap-1.5",
        "transition-all duration-300",
        "hover:border-salmon/30 dark:hover:border-salmon/[0.15]",
        "hover:shadow-md dark:hover:shadow-[0_12px_40px_rgba(232,115,74,0.06),inset_0_1px_0_rgba(255,255,255,0.05)]",
        "hover:-translate-y-0.5",
        pulse && "animate-pulse-slow",
      )}
    >
      {/* Left accent bar — color-coded by delta type */}
      <div className={cn(
        "absolute top-0 left-0 bottom-0 w-[2px] rounded-l-2xl",
        deltaType === "positive" ? "bg-gradient-to-b from-emerald-400/60 via-emerald-500/30 to-transparent"
        : deltaType === "negative" ? "bg-gradient-to-b from-salmon/60 via-salmon-300/30 to-transparent"
        : "bg-gradient-to-b from-ocean-500/60 via-ocean-400/30 to-transparent"
      )} />

      <div className="flex items-center justify-between relative z-10 gap-2">
        <span className={cn(
          "font-semibold text-[var(--text-secondary)] uppercase leading-tight",
          hero ? "text-[11px] tracking-[0.12em]" : "text-[9px] tracking-[0.08em]",
        )}>
          {label}
        </span>
        {Icon && (
          <div className={cn(
            "rounded-lg bg-ocean-500/[0.08] flex items-center justify-center flex-shrink-0",
            hero ? "w-8 h-8" : "w-6 h-6",
          )}>
            <Icon className={cn(hero ? "w-4 h-4" : "w-3 h-3", "text-ocean-500/70")} />
          </div>
        )}
      </div>

      <div className="flex items-end justify-between gap-3 relative z-10">
        <div className="flex items-baseline gap-2">
          <span className={cn(
            "font-bold tracking-tight text-[var(--text-primary)] leading-none text-kpi transition-number",
            hero ? "text-[36px]" : "text-[22px]",
          )}>
            {displayValue}
          </span>
          {unit && (
            <span className={cn(
              "font-medium text-[var(--text-secondary)]",
              hero ? "text-sm" : "text-[10px]",
            )}>
              {unit}
            </span>
          )}
          {delta && (
            <span className={cn(
              "font-medium",
              hero ? "text-sm" : "text-xs",
              deltaColor,
            )}>
              <span className="sr-only">{deltaType === "positive" ? "up" : deltaType === "negative" ? "down" : "unchanged"}</span>
              {delta}
            </span>
          )}
        </div>
        {sparkline && sparkline.length > 2 && (
          <MiniSparkline data={sparkline} color={sparkColor} />
        )}
      </div>
    </motion.div>
  );
}
