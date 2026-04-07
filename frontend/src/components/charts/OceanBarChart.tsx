"use client";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import OceanTooltip from "./OceanTooltip";

/* ─────────────────────────────────────────────────────────────────
 * Premium Bar Chart with Glass Aesthetic
 * ─────────────────────────────────────────────────────────────────
 * Features:
 *  - Rounded pill-shaped bars
 *  - Gradient fills
 *  - Ghost/baseline bars behind primary
 *  - Horizontal + vertical layouts
 *  - Animated entry with stagger
 * ───────────────────────────────────────────────────────────────── */

interface BarSeries {
  key: string;
  name?: string;
  color?: string;
  /** Ghost bar style (translucent background) */
  ghost?: boolean;
}

interface OceanBarChartProps {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data: any[];
  categoryKey: string;
  bars: BarSeries[];
  height?: number;
  layout?: "horizontal" | "vertical";
  unit?: string;
  showLegend?: boolean;
  animated?: boolean;
  /** Stacked bars */
  stacked?: boolean;
  /** Bar corner radius */
  radius?: number;
}

const OCEAN_PALETTE = [
  "rgba(0,212,200,0.55)",
  "rgba(139,92,246,0.55)",
  "rgba(245,158,11,0.55)",
  "rgba(236,72,153,0.55)",
  "rgba(16,185,129,0.55)",
];

export default function OceanBarChart({
  data,
  categoryKey,
  bars,
  height = 280,
  layout = "horizontal",
  unit = "",
  showLegend = true,
  animated = true,
  stacked = false,
  radius = 6,
}: OceanBarChartProps) {
  const isVertical = layout === "vertical";

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart
        data={data}
        layout={isVertical ? "vertical" : "horizontal"}
        margin={{
          top: 8,
          right: 8,
          left: isVertical ? 0 : -12,
          bottom: 0,
        }}
        barGap={2}
        barCategoryGap="20%"
      >
        <defs>
          {bars.map((b, i) => {
            const baseColor = b.color || OCEAN_PALETTE[i % OCEAN_PALETTE.length];
            return (
              <linearGradient
                key={`bar-grad-${b.key}`}
                id={`bar-grad-${b.key}`}
                x1="0"
                y1="0"
                x2="0"
                y2="1"
              >
                <stop offset="0%" stopColor={baseColor} stopOpacity={0.9} />
                <stop offset="100%" stopColor={baseColor} stopOpacity={0.4} />
              </linearGradient>
            );
          })}
        </defs>

        <CartesianGrid
          strokeDasharray="3 6"
          stroke="rgba(255,255,255,0.04)"
          horizontal={!isVertical}
          vertical={isVertical}
        />

        {isVertical ? (
          <>
            <XAxis
              type="number"
              stroke="rgba(136,153,170,0.6)"
              fontSize={11}
              tickLine={false}
              axisLine={{ stroke: "rgba(255,255,255,0.06)" }}
              tickFormatter={(v) => `${v}${unit}`}
            />
            <YAxis
              dataKey={categoryKey}
              type="category"
              stroke="rgba(136,153,170,0.6)"
              fontSize={11}
              tickLine={false}
              axisLine={false}
              width={80}
            />
          </>
        ) : (
          <>
            <XAxis
              dataKey={categoryKey}
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
          </>
        )}

        <Tooltip
          content={<OceanTooltip unit={unit} />}
          cursor={{
            fill: "rgba(0,212,200,0.04)",
            radius: 8,
          }}
        />

        {bars.map((b, i) => {
          const barRadius = isVertical
            ? [0, radius, radius, 0] as [number, number, number, number]
            : [radius, radius, 0, 0] as [number, number, number, number];

          return (
            <Bar
              key={b.key}
              dataKey={b.key}
              name={b.name || b.key}
              fill={
                b.ghost
                  ? "rgba(255,255,255,0.06)"
                  : `url(#bar-grad-${b.key})`
              }
              radius={barRadius}
              stackId={stacked ? "stack" : undefined}
              isAnimationActive={animated}
              animationDuration={800 + i * 100}
              animationEasing="ease-out"
              stroke={b.ghost ? "rgba(255,255,255,0.08)" : "none"}
              strokeWidth={b.ghost ? 1 : 0}
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
      </BarChart>
    </ResponsiveContainer>
  );
}
