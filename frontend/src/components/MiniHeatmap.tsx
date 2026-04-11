"use client";
import { useState, useCallback } from "react";
import { cn } from "@/lib/utils";
import { colors, dataColors } from "@/lib/design-tokens";

interface MiniHeatmapProps {
  /** 2D array of values (rows x cols) */
  data: number[][];
  rowLabels?: string[];
  colLabels?: string[];
  /** Color scale mapped to aquaculture data domains */
  colorScale?: "lice" | "temperature" | "mortality" | "default";
  /** Size of each cell in px (default 14) */
  cellSize?: number;
  /** Show numeric values inside cells (default false) */
  showValues?: boolean;
  className?: string;
}

const SCALE_COLORS: Record<string, string> = {
  lice: dataColors.lice,           // #F43F5E
  temperature: dataColors.temperature, // #3B82F6
  mortality: dataColors.mortality,     // #9F1239
  default: colors.accent,             // #00D4C8
};

/**
 * Interpolate between white and a target color based on a 0-1 ratio.
 * Returns an rgb() string.
 */
function interpolateColor(ratio: number, hexTarget: string): string {
  const t = Math.max(0, Math.min(1, ratio));
  const r = parseInt(hexTarget.slice(1, 3), 16);
  const g = parseInt(hexTarget.slice(3, 5), 16);
  const b = parseInt(hexTarget.slice(5, 7), 16);
  const fr = Math.round(255 + (r - 255) * t);
  const fg = Math.round(255 + (g - 255) * t);
  const fb = Math.round(255 + (b - 255) * t);
  return `rgb(${fr}, ${fg}, ${fb})`;
}

interface TooltipState {
  row: number;
  col: number;
  x: number;
  y: number;
}

/**
 * Compact inline heatmap for embedding in DataTable cells or small widgets.
 * Color-interpolates values from white (low) to a domain-specific high color.
 * Shows tooltip on hover with row/col labels and value.
 */
export function MiniHeatmap({
  data,
  rowLabels,
  colLabels,
  colorScale = "default",
  cellSize = 14,
  showValues = false,
  className,
}: MiniHeatmapProps) {
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);

  // Compute global min/max for normalization
  const flat = data.flat();
  const minVal = Math.min(...flat);
  const maxVal = Math.max(...flat);
  const range = maxVal - minVal || 1;

  const targetColor = SCALE_COLORS[colorScale] ?? SCALE_COLORS.default;
  const cols = data[0]?.length ?? 0;

  const handleMouseEnter = useCallback((row: number, col: number, e: React.MouseEvent) => {
    const rect = (e.target as HTMLElement).getBoundingClientRect();
    const parent = (e.target as HTMLElement).closest("[data-heatmap]")?.getBoundingClientRect();
    if (parent) {
      setTooltip({
        row,
        col,
        x: rect.left - parent.left + cellSize / 2,
        y: rect.top - parent.top - 4,
      });
    }
  }, [cellSize]);

  const handleMouseLeave = useCallback(() => setTooltip(null), []);

  return (
    <div
      data-heatmap
      role="grid"
      aria-label="Heatmap"
      className={cn("relative inline-block", className)}
    >
      {/* Column labels */}
      {colLabels && colLabels.length > 0 && (
        <div
          className="flex"
          style={{ marginLeft: rowLabels ? cellSize * 2.5 : 0, gap: 1 }}
        >
          {colLabels.map((label, i) => (
            <div
              key={i}
              className="text-[7px] font-medium text-[var(--text-secondary)] text-center truncate"
              style={{ width: cellSize, minWidth: cellSize }}
              title={label}
            >
              {label}
            </div>
          ))}
        </div>
      )}

      {/* Grid rows */}
      {data.map((row, ri) => (
        <div key={ri} className="flex items-center" style={{ gap: 1 }}>
          {/* Row label */}
          {rowLabels && rowLabels[ri] != null && (
            <span
              className="text-[7px] font-medium text-[var(--text-secondary)] truncate text-right pr-1"
              style={{ width: cellSize * 2.5, minWidth: cellSize * 2.5 }}
              title={rowLabels[ri]}
            >
              {rowLabels[ri]}
            </span>
          )}
          {row.map((val, ci) => {
            const ratio = (val - minVal) / range;
            const bg = interpolateColor(ratio, targetColor);
            // Use dark text on light cells, light text on dark cells
            const textBright = ratio > 0.55;

            return (
              <div
                key={ci}
                role="gridcell"
                className={cn(
                  "rounded-[2px] cursor-default transition-transform duration-100",
                  "hover:scale-125 hover:z-10",
                )}
                style={{
                  width: cellSize,
                  height: cellSize,
                  minWidth: cellSize,
                  backgroundColor: bg,
                  fontSize: showValues ? Math.max(7, cellSize * 0.5) : 0,
                  lineHeight: `${cellSize}px`,
                  textAlign: "center",
                  color: textBright ? "white" : "var(--text-secondary)",
                  fontWeight: 600,
                }}
                onMouseEnter={(e) => handleMouseEnter(ri, ci, e)}
                onMouseLeave={handleMouseLeave}
              >
                {showValues ? (val % 1 !== 0 ? val.toFixed(1) : val) : null}
              </div>
            );
          })}
        </div>
      ))}

      {/* Tooltip */}
      {tooltip && (
        <div
          className={cn(
            "absolute z-50 pointer-events-none",
            "px-2 py-1 rounded-md",
            "bg-[var(--bg-card)] dark:bg-fjord-surface/95",
            "border border-slate-200 dark:border-white/[0.1]",
            "shadow-lg",
            "text-[10px] text-[var(--text-primary)] font-mono whitespace-nowrap",
          )}
          style={{
            left: tooltip.x,
            top: tooltip.y,
            transform: "translate(-50%, -100%)",
          }}
        >
          {rowLabels?.[tooltip.row] && (
            <span className="text-[var(--text-secondary)]">{rowLabels[tooltip.row]} </span>
          )}
          {colLabels?.[tooltip.col] && (
            <span className="text-[var(--text-secondary)]">{colLabels[tooltip.col]}: </span>
          )}
          <span className="font-bold">
            {data[tooltip.row][tooltip.col] % 1 !== 0
              ? data[tooltip.row][tooltip.col].toFixed(2)
              : data[tooltip.row][tooltip.col]}
          </span>
        </div>
      )}
    </div>
  );
}

export default MiniHeatmap;
