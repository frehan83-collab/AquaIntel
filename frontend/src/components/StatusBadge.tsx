"use client";
import { cn } from "@/lib/utils";

type Status = "critical" | "high" | "warning" | "normal" | "good" | "info";

interface Props {
  status: Status;
  label: string;
  /** Show a pulsing dot for live/active states */
  pulse?: boolean;
  /** Size variant */
  size?: "sm" | "md";
  className?: string;
}

const STATUS_STYLES: Record<Status, { bg: string; text: string; dot: string; border: string }> = {
  critical: {
    bg: "bg-rose-500/10 dark:bg-rose-500/15",
    text: "text-rose-600 dark:text-rose-400",
    dot: "bg-rose-500",
    border: "border-rose-500/20",
  },
  high: {
    bg: "bg-orange-500/10 dark:bg-orange-500/15",
    text: "text-orange-600 dark:text-orange-400",
    dot: "bg-orange-500",
    border: "border-orange-500/20",
  },
  warning: {
    bg: "bg-amber-500/10 dark:bg-amber-500/15",
    text: "text-amber-600 dark:text-amber-400",
    dot: "bg-amber-500",
    border: "border-amber-500/20",
  },
  normal: {
    bg: "bg-slate-500/10 dark:bg-white/[0.06]",
    text: "text-slate-600 dark:text-slate-400",
    dot: "bg-slate-400",
    border: "border-slate-500/20 dark:border-white/10",
  },
  good: {
    bg: "bg-emerald-500/10 dark:bg-emerald-500/15",
    text: "text-emerald-600 dark:text-emerald-400",
    dot: "bg-emerald-500",
    border: "border-emerald-500/20",
  },
  info: {
    bg: "bg-blue-500/10 dark:bg-blue-500/15",
    text: "text-blue-600 dark:text-blue-400",
    dot: "bg-blue-500",
    border: "border-blue-500/20",
  },
};

export default function StatusBadge({ status, label, pulse, size = "sm", className }: Props) {
  const s = STATUS_STYLES[status] || STATUS_STYLES.normal;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border font-medium",
        s.bg, s.text, s.border,
        size === "sm" ? "px-2 py-0.5 text-[10px]" : "px-3 py-1 text-xs",
        className,
      )}
    >
      <span className={cn("rounded-full", s.dot, size === "sm" ? "w-1.5 h-1.5" : "w-2 h-2", pulse && "animate-pulse")} />
      {label}
    </span>
  );
}
