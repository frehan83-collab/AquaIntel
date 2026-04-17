"use client";
import { cn } from "@/lib/utils";

interface Props {
  /** Tailwind height class or arbitrary value, e.g. "h-[500px]", "h-96" */
  height?: string;
  /** Override the loading label */
  label?: string;
  className?: string;
}

/**
 * Per-shape skeleton for a map container.
 * Renders a large pulsing rectangle with a centered "loading map" message.
 */
export default function MapSkeleton({
  height = "h-[500px]",
  label = "Loading map…",
  className,
}: Props) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-2xl animate-pulse",
        "bg-white/[0.04] border border-white/[0.06]",
        "dark:bg-white/[0.04] dark:border-white/[0.06]",
        height,
        className,
      )}
      role="status"
      aria-label={label}
    >
      {/* Accent bar */}
      <div className="absolute top-0 left-0 bottom-0 w-[2px] bg-gradient-to-b from-ocean-500/20 via-ocean-400/10 to-transparent" />

      {/* Faux grid lines suggestive of a tiled map */}
      <div className="absolute inset-0">
        {[20, 40, 60, 80].map((p) => (
          <div
            key={`h-${p}`}
            className="absolute left-0 right-0 h-[1px] bg-white/[0.03]"
            style={{ top: `${p}%` }}
          />
        ))}
        {[20, 40, 60, 80].map((p) => (
          <div
            key={`v-${p}`}
            className="absolute top-0 bottom-0 w-[1px] bg-white/[0.03]"
            style={{ left: `${p}%` }}
          />
        ))}
      </div>

      {/* A few faux "map pins" to hint at data density */}
      <div className="absolute inset-0">
        {[
          { top: "28%", left: "32%" },
          { top: "45%", left: "58%" },
          { top: "62%", left: "40%" },
          { top: "38%", left: "70%" },
          { top: "72%", left: "22%" },
        ].map((pos, i) => (
          <div
            key={i}
            className="absolute h-2 w-2 rounded-full bg-white/[0.12]"
            style={pos}
          />
        ))}
      </div>

      {/* Centered loading label */}
      <div className="absolute inset-0 flex items-center justify-center">
        <div className="flex items-center gap-3 rounded-full bg-white/[0.06] border border-white/[0.08] px-4 py-2">
          <span className="inline-block h-2 w-2 rounded-full bg-ocean-400/80" />
          <span className="text-xs text-white/60 font-medium tracking-wide">
            {label}
          </span>
        </div>
      </div>

      {/* Top-left zoom-control placeholder */}
      <div className="absolute top-3 left-3 flex flex-col gap-1">
        <div className="h-6 w-6 rounded bg-white/[0.06]" />
        <div className="h-6 w-6 rounded bg-white/[0.06]" />
      </div>
    </div>
  );
}
