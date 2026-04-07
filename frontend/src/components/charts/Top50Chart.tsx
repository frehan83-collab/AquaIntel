"use client";
import { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";

/* eslint-disable @typescript-eslint/no-explicit-any */

interface Company {
  name: string;
  avg_lice: number;
  performance_score: number;
  production_volume_tonnes: number;
  outlook_direction: string;
  parent_group: string;
  ticker: string | null;
  is_public: boolean;
  risk_level: string;
  n_localities: number;
  production_areas: number[];
}

type SortMode = "lice" | "score" | "volume";

interface Top50ChartProps {
  companies: Company[];
  onCompanyClick?: (company: Company) => void;
}

export default function Top50Chart({ companies, onCompanyClick }: Top50ChartProps) {
  const [sortMode, setSortMode] = useState<SortMode>("volume");
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

  const sorted = useMemo(() => {
    const filtered = companies.filter(c => c.avg_lice > 0).slice(0, 50);
    switch (sortMode) {
      case "lice": return [...filtered].sort((a, b) => b.avg_lice - a.avg_lice);
      case "score": return [...filtered].sort((a, b) => b.performance_score - a.performance_score);
      case "volume": return [...filtered].sort((a, b) => b.production_volume_tonnes - a.production_volume_tonnes);
    }
  }, [companies, sortMode]);

  const maxLice = useMemo(() => Math.max(...sorted.map(c => c.avg_lice), 0.01), [sorted]);

  const getBarColor = (lice: number) => {
    if (lice >= 0.5) return { from: "#F43F5E", to: "#FB7185" };   // red — above limit
    if (lice >= 0.3) return { from: "#F59E0B", to: "#FBBF24" };   // amber — elevated
    if (lice >= 0.15) return { from: "#00C8A0", to: "#00D4C8" };  // teal — moderate
    return { from: "#10B981", to: "#34D399" };                     // emerald — clean
  };

  if (sorted.length === 0) {
    return (
      <div className="h-[400px] flex items-center justify-center text-sm text-[var(--text-secondary)]">
        Loading company data...
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Sort Controls */}
      <div className="flex items-center gap-1.5">
        {([
          { key: "volume", label: "By Volume" },
          { key: "lice", label: "By Lice Level" },
          { key: "score", label: "By Score" },
        ] as { key: SortMode; label: string }[]).map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setSortMode(key)}
            className={cn(
              "px-2.5 py-1 rounded-lg text-[10px] font-medium transition-all",
              sortMode === key
                ? "bg-ocean-500/15 text-ocean-400 border border-ocean-500/20"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] border border-transparent"
            )}
          >
            {label}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-2 text-[10px] text-[var(--text-secondary)]">
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-emerald-500" />&lt;0.15</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-[#00D4C8]" />0.15-0.3</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-amber-500" />0.3-0.5</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-rose-500" />&gt;0.5</span>
        </div>
      </div>

      {/* Chart Area */}
      <div className="relative overflow-x-auto overflow-y-hidden pb-2" style={{ scrollSnapType: "x mandatory" }}>
        <div className="flex gap-[3px] items-end min-w-[900px]" style={{ height: 320 }}>
          {/* Threshold line at 0.5 */}
          <div
            className="absolute left-0 right-0 border-t border-dashed border-rose-500/30 pointer-events-none z-10"
            style={{ bottom: `${(0.5 / maxLice) * 280 + 36}px` }}
          >
            <span className="absolute -top-3 right-0 text-[9px] text-rose-400/60 font-mono">0.5 limit</span>
          </div>

          <AnimatePresence mode="popLayout">
            {sorted.map((co, idx) => {
              const pct = Math.max(2, (co.avg_lice / maxLice) * 280);
              const colors = getBarColor(co.avg_lice);
              const isHovered = hoveredIdx === idx;
              const isTop5 = idx < 5 && sortMode === "score";
              const shortName = co.name
                .replace(/ AS$| ASA$/i, "")
                .replace(/OPPDRETT|HAVBRUK|SEAFOOD|FISKEOPPDRETT|SJØFARM|FARMING/gi, "")
                .trim()
                .slice(0, 12);

              return (
                <motion.div
                  key={co.name}
                  layout
                  className="flex flex-col items-center flex-1 min-w-[16px] cursor-pointer group"
                  style={{ scrollSnapAlign: "start" }}
                  onMouseEnter={() => setHoveredIdx(idx)}
                  onMouseLeave={() => setHoveredIdx(null)}
                  onClick={() => onCompanyClick?.(co)}
                >
                  {/* Tooltip */}
                  <AnimatePresence>
                    {isHovered && (
                      <motion.div
                        initial={{ opacity: 0, y: 5, scale: 0.95 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: 5, scale: 0.95 }}
                        className="absolute z-30 -translate-y-2 pointer-events-none"
                        style={{ bottom: pct + 50 }}
                      >
                        <div className="bg-[rgba(6,15,28,0.95)] backdrop-blur-xl border border-white/[0.1] rounded-xl px-3 py-2 shadow-[0_8px_32px_rgba(0,0,0,0.5)] min-w-[160px]">
                          <p className="text-xs font-semibold text-[var(--text-primary)] truncate">{co.name}</p>
                          {co.parent_group && (
                            <p className="text-[9px] text-violet-400">{co.parent_group}</p>
                          )}
                          <div className="mt-1.5 space-y-0.5">
                            <div className="flex justify-between text-[10px]">
                              <span className="text-[var(--text-secondary)]">Avg Lice</span>
                              <span className={cn("font-mono font-bold",
                                co.avg_lice >= 0.5 ? "text-rose-400" :
                                co.avg_lice >= 0.3 ? "text-amber-400" : "text-emerald-400"
                              )}>{co.avg_lice.toFixed(3)}</span>
                            </div>
                            <div className="flex justify-between text-[10px]">
                              <span className="text-[var(--text-secondary)]">Score</span>
                              <span className="font-mono font-semibold text-ocean-400">{co.performance_score.toFixed(0)}</span>
                            </div>
                            <div className="flex justify-between text-[10px]">
                              <span className="text-[var(--text-secondary)]">Sites</span>
                              <span className="font-mono">{co.n_localities}</span>
                            </div>
                            <div className="flex justify-between text-[10px]">
                              <span className="text-[var(--text-secondary)]">Outlook</span>
                              <span className={cn("font-semibold",
                                co.outlook_direction === "positive" ? "text-emerald-400" :
                                co.outlook_direction === "negative" ? "text-rose-400" : "text-amber-400"
                              )}>
                                {co.outlook_direction === "positive" ? "+" : co.outlook_direction === "negative" ? "-" : "="} {co.outlook_direction}
                              </span>
                            </div>
                          </div>
                          {co.ticker && (
                            <div className="mt-1 pt-1 border-t border-white/[0.06]">
                              <span className="text-[9px] text-ocean-400">Oslo Bors: {co.ticker}</span>
                            </div>
                          )}
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>

                  {/* Bar */}
                  <motion.div
                    className="w-full rounded-t-sm relative overflow-hidden"
                    initial={{ height: 0 }}
                    animate={{
                      height: pct,
                      scale: isHovered ? 1.08 : 1,
                      y: isHovered ? -3 : 0,
                    }}
                    transition={{
                      height: { duration: 0.6, delay: idx * 0.012, ease: "easeOut" },
                      scale: { duration: 0.15 },
                      y: { duration: 0.15 },
                    }}
                    style={{
                      background: `linear-gradient(to top, ${colors.from}, ${colors.to})`,
                      boxShadow: isHovered
                        ? `0 0 12px ${colors.from}40, inset 0 1px 0 rgba(255,255,255,0.15)`
                        : `inset 0 1px 0 rgba(255,255,255,0.06)`,
                    }}
                  >
                    {/* Shine effect */}
                    <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/[0.06] to-transparent" />
                    {/* Top 5 sparkle */}
                    {isTop5 && (
                      <motion.div
                        className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-transparent via-amber-400/40 to-transparent"
                        animate={{ opacity: [0.3, 0.8, 0.3] }}
                        transition={{ duration: 2, repeat: Infinity }}
                      />
                    )}
                  </motion.div>

                  {/* Label */}
                  <div className="mt-1 w-full text-center">
                    <span className={cn(
                      "text-[8px] leading-tight block truncate transition-colors",
                      isHovered ? "text-[var(--text-primary)]" : "text-[var(--text-secondary)]"
                    )} style={{ writingMode: sorted.length > 30 ? "vertical-rl" : undefined, height: sorted.length > 30 ? 50 : undefined }}>
                      {shortName}
                    </span>
                  </div>
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
