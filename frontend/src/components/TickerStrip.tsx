"use client";
import { cn } from "@/lib/utils";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { useTranslation, formatNumber } from "@/lib/i18n";

interface TickerItem {
  label: string;
  value: string;
  /** Percent change (positive or negative) */
  change?: number;
  trend?: "up" | "down" | "flat";
}

interface TickerStripProps {
  items: TickerItem[];
  /** Seconds for one full scroll cycle (default 30) */
  speed?: number;
  className?: string;
}

/**
 * Horizontal scrolling price/metric ticker bar with glassmorphic styling.
 * Duplicates items internally for seamless infinite scroll. Pauses on hover.
 */
export function TickerStrip({ items, speed = 30, className }: TickerStripProps) {
  if (!items.length) return null;

  // Duplicate for seamless loop
  const doubled = [...items, ...items];

  return (
    <div
      role="marquee"
      aria-label="Live metrics ticker"
      className={cn(
        "relative overflow-hidden",
        "bg-[var(--bg-card)]/80 dark:bg-fjord-surface/40",
        "backdrop-blur-sm",
        "border-y border-slate-200 dark:border-white/[0.06]",
        "py-2",
        className,
      )}
    >
      <div
        className="flex items-center gap-8 whitespace-nowrap animate-ticker hover:[animation-play-state:paused]"
        style={{
          animationDuration: `${speed}s`,
        }}
      >
        {doubled.map((item, i) => (
          <TickerEntry key={`${item.label}-${i}`} item={item} />
        ))}
      </div>

      {/* Edge fades */}
      <div className="absolute inset-y-0 left-0 w-12 bg-gradient-to-r from-[var(--bg-card)] dark:from-fjord-surface/80 to-transparent pointer-events-none z-10" />
      <div className="absolute inset-y-0 right-0 w-12 bg-gradient-to-l from-[var(--bg-card)] dark:from-fjord-surface/80 to-transparent pointer-events-none z-10" />

      <style jsx>{`
        @keyframes ticker-scroll {
          0% { transform: translateX(0); }
          100% { transform: translateX(-50%); }
        }
        .animate-ticker {
          animation: ticker-scroll linear infinite;
        }
      `}</style>
    </div>
  );
}

function TickerEntry({ item }: { item: TickerItem }) {
  const { locale } = useTranslation();
  const trend = item.trend ?? (item.change != null ? (item.change > 0 ? "up" : item.change < 0 ? "down" : "flat") : undefined);

  const TrendIcon = trend === "up" ? TrendingUp : trend === "down" ? TrendingDown : Minus;
  const trendColor =
    trend === "up"
      ? "text-[var(--positive)]"
      : trend === "down"
      ? "text-[var(--negative)]"
      : "text-[var(--text-secondary)]";

  return (
    <div className="flex items-center gap-2 flex-shrink-0 px-1">
      <span className="text-[10px] font-semibold text-[var(--text-secondary)] uppercase tracking-wider">
        {item.label}
      </span>
      <span className="text-sm font-bold text-[var(--text-primary)] font-mono tracking-tight">
        {item.value}
      </span>
      {trend && (
        <span className={cn("flex items-center gap-0.5", trendColor)}>
          <TrendIcon className="w-3 h-3" />
          {item.change != null && (
            <span className="text-[10px] font-semibold font-mono">
              {item.change > 0 ? "+" : ""}
              {formatNumber(item.change, locale, 1)}%
            </span>
          )}
        </span>
      )}
      {/* Separator dot */}
      <span className="w-1 h-1 rounded-full bg-[var(--border)] opacity-40 ml-2" />
    </div>
  );
}

export default TickerStrip;
