"use client";
import { cn } from "@/lib/utils";

interface Props {
  /** Number of text placeholder lines */
  lines?: number;
  /** Show wider header placeholder */
  hasHeader?: boolean;
  className?: string;
}

export default function SkeletonCard({ lines = 3, hasHeader = true, className }: Props) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-2xl",
        "bg-[var(--bg-card)] dark:bg-gradient-to-br dark:from-fjord-surface/60 dark:to-fjord-midwater/40",
        "border border-slate-200 dark:border-white/[0.08]",
        "shadow-sm dark:shadow-[0_8px_32px_rgba(0,0,0,0.3)]",
        "p-6 animate-pulse",
        className,
      )}
    >
      {/* Accent bar */}
      <div className="absolute top-0 left-0 bottom-0 w-[2px] bg-gradient-to-b from-ocean-500/20 via-ocean-400/10 to-transparent" />

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
    </div>
  );
}
