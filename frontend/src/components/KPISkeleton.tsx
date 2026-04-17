"use client";
import { cn } from "@/lib/utils";

interface Props {
  /** Number of KPI cards to render */
  count?: number;
  className?: string;
}

/**
 * Per-shape skeleton for a grid of KPI cards.
 * Matches the shape of KPICard so users see the right shape appear, not a generic block.
 */
export default function KPISkeleton({ count = 4, className }: Props) {
  const gridCols =
    count <= 2
      ? "grid-cols-1 md:grid-cols-2"
      : count === 3
      ? "grid-cols-2 md:grid-cols-3"
      : count === 4
      ? "grid-cols-2 md:grid-cols-4"
      : count === 5
      ? "grid-cols-2 md:grid-cols-5"
      : "grid-cols-2 md:grid-cols-6";

  return (
    <div className={cn("grid gap-4 animate-pulse", gridCols, className)}>
      {Array.from({ length: count }, (_, i) => (
        <div
          key={i}
          className={cn(
            "relative overflow-hidden rounded-2xl p-5",
            "bg-white/[0.04] border border-white/[0.06]",
            "dark:bg-white/[0.04] dark:border-white/[0.06]",
          )}
        >
          {/* Accent bar */}
          <div className="absolute top-0 left-0 bottom-0 w-[2px] bg-gradient-to-b from-ocean-500/20 via-ocean-400/10 to-transparent" />
          <div className="flex items-center gap-4">
            {/* Icon circle */}
            <div className="h-10 w-10 shrink-0 rounded-full bg-white/[0.06]" />
            <div className="flex-1 space-y-2">
              {/* Value line */}
              <div className="h-6 w-3/5 rounded bg-white/[0.06]" />
              {/* Label line */}
              <div className="h-3 w-2/5 rounded bg-white/[0.04]" />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
