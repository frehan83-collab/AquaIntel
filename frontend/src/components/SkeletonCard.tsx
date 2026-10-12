"use client";
import { cn } from "@/lib/utils";

type Variant = "text" | "kpi" | "chart" | "table";

interface Props {
  /** Number of text placeholder lines (used by "text" variant) */
  lines?: number;
  /** Show wider header placeholder (used by "text" variant) */
  hasHeader?: boolean;
  /** Skeleton layout variant */
  variant?: Variant;
  className?: string;
}

function TextSkeleton({ lines, hasHeader }: { lines: number; hasHeader: boolean }) {
  return (
    <div className="space-y-3">
      {hasHeader && (
        <div className="h-5 w-2/5 rounded bg-slate-200 dark:bg-white/[0.06]" />
      )}
      {Array.from({ length: lines }, (_, i) => (
        <div
          key={i}
          className={cn(
            "h-3 rounded bg-slate-200 dark:bg-white/[0.04]",
            i === lines - 1 ? "w-3/5" : "w-full",
          )}
        />
      ))}
    </div>
  );
}

function KpiSkeleton() {
  return (
    <div className="flex items-center gap-4">
      {/* Icon circle */}
      <div className="h-10 w-10 shrink-0 rounded-full bg-slate-200 dark:bg-white/[0.06]" />
      <div className="flex-1 space-y-2">
        {/* Number line */}
        <div className="h-6 w-3/5 rounded bg-slate-200 dark:bg-white/[0.06]" />
        {/* Label line */}
        <div className="h-3 w-2/5 rounded bg-slate-200 dark:bg-white/[0.04]" />
      </div>
    </div>
  );
}

function ChartSkeleton() {
  return (
    <div className="flex h-full min-h-[140px] flex-col">
      <div className="flex flex-1 items-end gap-[6px] pb-2 pl-6 pr-2">
        {/* Left Y-axis line */}
        <div className="absolute left-6 top-6 bottom-10 w-[2px] rounded bg-slate-200 dark:bg-white/[0.06]" />
        {/* Bar / wave shapes */}
        <div className="h-[45%] flex-1 rounded-t bg-slate-200 dark:bg-white/[0.04]" />
        <div className="h-[70%] flex-1 rounded-t bg-slate-200 dark:bg-white/[0.05]" />
        <div className="h-[55%] flex-1 rounded-t bg-slate-200 dark:bg-white/[0.04]" />
        <div className="h-[85%] flex-1 rounded-t bg-slate-200 dark:bg-white/[0.06]" />
        <div className="h-[40%] flex-1 rounded-t bg-slate-200 dark:bg-white/[0.04]" />
        <div className="h-[65%] flex-1 rounded-t bg-slate-200 dark:bg-white/[0.05]" />
        <div className="h-[50%] flex-1 rounded-t bg-slate-200 dark:bg-white/[0.04]" />
      </div>
      {/* X-axis line */}
      <div className="mx-6 h-[2px] rounded bg-slate-200 dark:bg-white/[0.06]" />
    </div>
  );
}

function TableSkeleton() {
  return (
    <div className="space-y-0">
      {/* Header row */}
      <div className="h-8 w-full rounded-t bg-slate-300 dark:bg-white/[0.08]" />
      {/* Data rows */}
      {Array.from({ length: 5 }, (_, i) => (
        <div
          key={i}
          className={cn(
            "h-7 w-full border-b border-slate-100 dark:border-white/[0.03]",
            "bg-slate-200 dark:bg-white/[0.03]",
            i === 4 && "rounded-b",
          )}
        />
      ))}
    </div>
  );
}

export default function SkeletonCard({
  lines = 3,
  hasHeader = true,
  variant = "text",
  className,
}: Props) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-2xl",
        "bg-[var(--bg-card)] dark:bg-gradient-to-br dark:from-fjord-surface/60 dark:to-fjord-midwater/40",
        "border border-slate-200 dark:border-white/[0.08]",
        "shadow-xs dark:shadow-[0_8px_32px_rgba(0,0,0,0.3)]",
        "p-6 skeleton-shimmer",
        className,
      )}
    >
      {/* Accent bar */}
      <div className="absolute top-0 left-0 bottom-0 w-[2px] bg-gradient-to-b from-ocean-500/20 via-ocean-400/10 to-transparent" />

      {variant === "text" && <TextSkeleton lines={lines} hasHeader={hasHeader} />}
      {variant === "kpi" && <KpiSkeleton />}
      {variant === "chart" && <ChartSkeleton />}
      {variant === "table" && <TableSkeleton />}
    </div>
  );
}
