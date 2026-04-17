"use client";
import { cn } from "@/lib/utils";

interface Props {
  /** Number of data rows to render */
  rows?: number;
  /** Number of columns to render */
  columns?: number;
  className?: string;
}

/**
 * Per-shape skeleton for a data table.
 * Matches the shape of DataTable so users see the right shape appear, not a generic block.
 */
export default function TableSkeleton({
  rows = 10,
  columns = 5,
  className,
}: Props) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-2xl animate-pulse",
        "bg-white/[0.04] border border-white/[0.06]",
        "dark:bg-white/[0.04] dark:border-white/[0.06]",
        "p-4",
        className,
      )}
    >
      {/* Accent bar */}
      <div className="absolute top-0 left-0 bottom-0 w-[2px] bg-gradient-to-b from-ocean-500/20 via-ocean-400/10 to-transparent" />

      {/* Optional title / search bar at top */}
      <div className="flex items-center justify-between mb-4">
        <div className="h-5 w-1/4 rounded bg-white/[0.08]" />
        <div className="h-8 w-32 rounded bg-white/[0.04]" />
      </div>

      {/* Header row */}
      <div
        className="grid gap-3 mb-3 pb-2 border-b border-white/[0.06]"
        style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}
      >
        {Array.from({ length: columns }, (_, i) => (
          <div
            key={`h-${i}`}
            className="h-4 rounded bg-white/[0.08]"
            style={{ width: `${60 + ((i * 13) % 30)}%` }}
          />
        ))}
      </div>

      {/* Body rows */}
      <div className="space-y-2">
        {Array.from({ length: rows }, (_, r) => (
          <div
            key={`r-${r}`}
            className="grid gap-3 py-2"
            style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}
          >
            {Array.from({ length: columns }, (_, c) => (
              <div
                key={`r-${r}-c-${c}`}
                className="h-3 rounded bg-white/[0.04]"
                style={{ width: `${55 + ((r * 7 + c * 11) % 40)}%` }}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
