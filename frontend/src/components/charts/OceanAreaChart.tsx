"use client";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine, Legend,
} from "recharts";
import OceanTooltip from "./OceanTooltip";
import { chartPalette, colors } from "@/lib/design-tokens";

/* ─────────────────────────────────────────────────────────────────
 * Premium Multi-Series Area Chart
 * ─────────────────────────────────────────────────────────────────
 * Drop-in replacement for raw Recharts AreaChart with:
 *  - Auto-gradient fills per series
 *  - Glow filter on lines
 *  - Ocean-themed color palette
 *  - Custom glass tooltip
 *  - Optional threshold reference line
 * ───────────────────────────────────────────────────────────────── */

interface Series {
  key: string;
  name?: string;
  color: string;
  /** Show filled gradient below the line */
  filled?: boolean;
  /** Dashed line style */
  dashed?: boolean;
  strokeWidth?: number;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
interface OceanAreaChartProps {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data: any[];
  xKey: string;
  series: Series[];
  height?: number;
  threshold?: number;
  thresholdLabel?: string;
  unit?: string;
  showLegend?: boolean;
  animated?: boolean;
}

/** @deprecated Use chartPalette from design-tokens instead */
const OCEAN_PALETTE = chartPalette;

export default function OceanAreaChart({
  data,
  xKey,
  series,
  height = 280,
  threshold,
  thresholdLabel,
  unit = "",
  showLegend = true,
  animated = true,
}: OceanAreaChartProps) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
        <defs>
          {series.map((s, i) => {
            const color = s.color || OCEAN_PALETTE[i % OCEAN_PALETTE.length];
            return (
              <linearGradient key={`grad-${s.key}`} id={`grad-${s.key}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={color} stopOpacity={0.25} />
                <stop offset="50%" stopColor={color} stopOpacity={0.08} />
                <stop offset="95%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            );
          })}
          {/* Subtle line glow — reduced blur for performance */}
          <filter id="lineGlow" x="-5%" y="-5%" width="110%" height="110%">
            <feGaussianBlur stdDeviation="1" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <CartesianGrid
          strokeDasharray="3 6"
          stroke="rgba(255,255,255,0.04)"
          vertical={false}
        />

        <XAxis
          dataKey={xKey}
          stroke="rgba(136,153,170,0.6)"
          fontSize={11}
          tickLine={false}
          axisLine={{ stroke: "rgba(255,255,255,0.06)" }}
          dy={8}
        />
        <YAxis
          stroke="rgba(136,153,170,0.6)"
          fontSize={11}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v) => `${v}${unit}`}
        />

        <Tooltip
          content={<OceanTooltip unit={unit} />}
          cursor={{
            stroke: "rgba(0,212,200,0.15)",
            strokeWidth: 1,
            strokeDasharray: "4 4",
          }}
        />

        {threshold !== undefined && (
          <ReferenceLine
            y={threshold}
            stroke={colors.danger}
            strokeDasharray="6 4"
            strokeWidth={1.5}
            label={{
              value: thresholdLabel || `Limit: ${threshold}`,
              fill: "rgba(244,63,94,0.8)",
              fontSize: 10,
              position: "right",
            }}
          />
        )}

        {series.map((s, i) => {
          const color = s.color || OCEAN_PALETTE[i % OCEAN_PALETTE.length];
          return (
            <Area
              key={s.key}
              type="monotone"
              dataKey={s.key}
              name={s.name || s.key}
              stroke={color}
              fill={s.filled !== false ? `url(#grad-${s.key})` : "none"}
              strokeWidth={s.strokeWidth || 2}
              strokeDasharray={s.dashed ? "6 4" : undefined}
              dot={false}
              activeDot={{
                r: 4,
                fill: color,
                stroke: "#060F1C",
                strokeWidth: 2,
              }}
              isAnimationActive={animated}
              animationDuration={800 + i * 150}
              animationEasing="ease-out"
              filter={!s.dashed ? "url(#lineGlow)" : undefined}
            />
          );
        })}

        {showLegend && (
          <Legend
            wrapperStyle={{
              paddingTop: 16,
              fontSize: 11,
              color: "var(--text-secondary)",
            }}
            iconType="circle"
            iconSize={8}
          />
        )}
      </AreaChart>
    </ResponsiveContainer>
  );
}
