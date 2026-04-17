"use client";
import { cn } from "@/lib/utils";

interface Props {
  /** Tailwind height class, e.g. "h-64", "h-96", "h-[400px]" */
  height?: string;
  /** Show title placeholder above the chart */
  showTitle?: boolean;
  className?: string;
}

/**
 * Per-shape skeleton for a chart.
 * Renders a title bar, y-axis labels, and a faux line/area chart.
 */
export default function ChartSkeleton({
  height = "h-64",
  showTitle = true,
  className,
}: Props) {
  // Faux line path — a smooth curve using relative coordinates on a viewBox
  const linePath =
    "M0,60 C10,55 20,40 30,35 C40,30 50,48 60,45 C70,42 80,20 90,25 C95,28 100,32 100,32";

  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-2xl animate-pulse",
        "bg-white/[0.04] border border-white/[0.06]",
        "dark:bg-white/[0.04] dark:border-white/[0.06]",
        "p-5",
        className,
      )}
    >
      {/* Accent bar */}
      <div className="absolute top-0 left-0 bottom-0 w-[2px] bg-gradient-to-b from-ocean-500/20 via-ocean-400/10 to-transparent" />

      {showTitle && (
        <div className="flex items-center justify-between mb-4">
          <div className="h-5 w-1/3 rounded bg-white/[0.08]" />
          <div className="h-4 w-20 rounded bg-white/[0.04]" />
        </div>
      )}

      <div className={cn("flex gap-3", height)}>
        {/* Y-axis labels */}
        <div className="flex flex-col justify-between py-1 w-10 shrink-0">
          {Array.from({ length: 5 }, (_, i) => (
            <div key={i} className="h-2 w-full rounded bg-white/[0.04]" />
          ))}
        </div>

        {/* Plot area */}
        <div className="relative flex-1 rounded-lg bg-white/[0.02] border border-white/[0.04] overflow-hidden">
          {/* Horizontal gridlines */}
          {[20, 40, 60, 80].map((top) => (
            <div
              key={top}
              className="absolute left-0 right-0 h-[1px] bg-white/[0.04]"
              style={{ top: `${top}%` }}
            />
          ))}

          {/* Faux line + area fill */}
          <svg
            viewBox="0 0 100 100"
            preserveAspectRatio="none"
            className="absolute inset-0 h-full w-full"
          >
            <defs>
              <linearGradient id="chartSkeletonFill" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor="rgba(255,255,255,0.08)" />
                <stop offset="100%" stopColor="rgba(255,255,255,0.0)" />
              </linearGradient>
            </defs>
            <path
              d={`${linePath} L100,100 L0,100 Z`}
              fill="url(#chartSkeletonFill)"
            />
            <path
              d={linePath}
              fill="none"
              stroke="rgba(255,255,255,0.15)"
              strokeWidth="1.2"
              vectorEffect="non-scaling-stroke"
            />
          </svg>

          {/* X-axis tick labels at bottom */}
          <div className="absolute bottom-1 left-0 right-0 flex justify-between px-2">
            {Array.from({ length: 6 }, (_, i) => (
              <div
                key={i}
                className="h-2 w-6 rounded bg-white/[0.04]"
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
