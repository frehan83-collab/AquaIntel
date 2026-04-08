"use client";
import { cn } from "@/lib/utils";
import { useTranslation } from "@/lib/i18n";

interface Props {
  color: "green" | "yellow" | "red" | "unknown";
  /** Production area number (1-13) */
  pa?: number;
  /** Show the MAB impact text */
  showImpact?: boolean;
  /** Size */
  size?: "sm" | "md" | "lg";
  className?: string;
}

const LIGHT_STYLES = {
  green:   { active: "bg-traffic-green shadow-[0_0_8px_rgba(34,197,94,0.5)]",   inactive: "bg-white/[0.06]", label: "Gr\u00f8nt", impact: "+6% MTB" },
  yellow:  { active: "bg-traffic-yellow shadow-[0_0_8px_rgba(234,179,8,0.5)]",  inactive: "bg-white/[0.06]", label: "Gult",  impact: "0% MTB" },
  red:     { active: "bg-traffic-red shadow-[0_0_8px_rgba(239,68,68,0.5)]",     inactive: "bg-white/[0.06]", label: "R\u00f8dt",  impact: "-6% MTB" },
  unknown: { active: "bg-slate-400 shadow-none",                                 inactive: "bg-white/[0.06]", label: "Ukjent", impact: "\u2014" },
};

const SIZES = {
  sm: { light: "w-3 h-3", gap: "gap-1", text: "text-[10px]", container: "gap-2" },
  md: { light: "w-4 h-4", gap: "gap-1.5", text: "text-xs", container: "gap-3" },
  lg: { light: "w-5 h-5", gap: "gap-2", text: "text-sm", container: "gap-3" },
};

export default function TrafikklysIndicator({ color, pa, showImpact, size = "md", className }: Props) {
  const { t } = useTranslation();
  const sz = SIZES[size];
  const style = LIGHT_STYLES[color] || LIGHT_STYLES.unknown;

  return (
    <div className={cn("inline-flex items-center", sz.container, className)}>
      {/* Traffic light stack */}
      <div className={cn("flex flex-col items-center bg-slate-800/50 dark:bg-white/[0.04] rounded-full p-1", sz.gap)}>
        {(["green", "yellow", "red"] as const).map((c) => (
          <div
            key={c}
            className={cn(
              "rounded-full transition-all duration-300",
              sz.light,
              c === color ? LIGHT_STYLES[c].active : LIGHT_STYLES[c].inactive,
            )}
          />
        ))}
      </div>
      {/* Label */}
      <div className="flex flex-col">
        <span className={cn("font-semibold text-[var(--text-primary)]", sz.text)}>
          {pa != null ? `PA ${pa}` : ""} {style.label}
        </span>
        {showImpact && (
          <span className={cn("text-[var(--text-secondary)]", size === "lg" ? "text-xs" : "text-[9px]")}>
            {style.impact}
          </span>
        )}
      </div>
    </div>
  );
}
