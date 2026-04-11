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
    bg: "bg-[var(--danger)]/10",
    text: "text-[var(--danger)]",
    dot: "bg-[var(--danger)]",
    border: "border-[var(--danger)]/20",
  },
  high: {
    bg: "bg-[var(--salmon)]/10",
    text: "text-[var(--salmon)]",
    dot: "bg-[var(--salmon)]",
    border: "border-[var(--salmon)]/20",
  },
  warning: {
    bg: "bg-[var(--warning)]/10",
    text: "text-[var(--warning)]",
    dot: "bg-[var(--warning)]",
    border: "border-[var(--warning)]/20",
  },
  normal: {
    bg: "bg-slate-500/10 dark:bg-white/[0.06]",
    text: "text-[var(--text-secondary)]",
    dot: "bg-slate-400",
    border: "border-[var(--border)]",
  },
  good: {
    bg: "bg-[var(--success)]/10",
    text: "text-[var(--success)]",
    dot: "bg-[var(--success)]",
    border: "border-[var(--success)]/20",
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
