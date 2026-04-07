"use client";
import { useMemo } from "react";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts";
import OceanTooltip from "./OceanTooltip";

/* ─────────────────────────────────────────────────────────────────
 * Animated Forecast Cone
 * ─────────────────────────────────────────────────────────────────
 * Time-series with dynamically widening uncertainty bands.
 *
 * Features:
 *  - 95% and 80% confidence bands (layered translucent fills)
 *  - Central forecast line with glow
 *  - Animated SVG gradient that shifts with data
 *  - Optional reference/threshold line
 *  - Responsive with proper aspect ratio
 * ───────────────────────────────────────────────────────────────── */

interface DataPoint {
  label: string;
  forecast: number;
  upper95?: number;
  lower95?: number;
  upper80?: number;
  lower80?: number;
  [key: string]: string | number | undefined;
}

interface ForecastConeProps {
  data: DataPoint[];
  height?: number;
  /** Reference line value (e.g., regulatory threshold) */
  threshold?: number;
  thresholdLabel?: string;
  /** Y-axis unit */
  unit?: string;
  /** Accent color scheme */
  color?: "ocean" | "emerald" | "amber" | "rose";
  /** Show animated gradient */
  animated?: boolean;
}

const COLOR_MAP = {
  ocean:   { line: "#00D4C8", fill: "0,212,200",   glow: "rgba(0,212,200,0.3)" },
  emerald: { line: "#10B981", fill: "16,185,129",  glow: "rgba(16,185,129,0.3)" },
  amber:   { line: "#F59E0B", fill: "245,158,11",  glow: "rgba(245,158,11,0.3)" },
  rose:    { line: "#F43F5E", fill: "244,63,94",   glow: "rgba(244,63,94,0.3)" },
};

export default function ForecastCone({
  data,
  height = 300,
  threshold,
  thresholdLabel,
  unit = "",
  color = "ocean",
  animated = true,
}: ForecastConeProps) {
  const c = COLOR_MAP[color];
  const gradientId95 = `cone95-${color}`;
  const gradientId80 = `cone80-${color}`;
  const glowId = `glow-${color}`;

  // Compute Y domain with padding
  const yDomain = useMemo(() => {
    const allVals = data.flatMap((d) => [
      d.forecast,
      d.upper95 ?? d.forecast,
      d.lower95 ?? d.forecast,
    ].filter(Boolean));
    const min = Math.min(...allVals);
    const max = Math.max(...allVals);
    const pad = (max - min) * 0.15 || 1;
    return [Math.max(0, min - pad), max + pad];
  }, [data]);

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
        <defs>
          {/* 95% band gradient */}
          <linearGradient id={gradientId95} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={`rgba(${c.fill},0.12)`} />
            <stop offset="100%" stopColor={`rgba(${c.fill},0.02)`} />
          </linearGradient>
          {/* 80% band gradient */}
          <linearGradient id={gradientId80} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={`rgba(${c.fill},0.22)`} />
            <stop offset="100%" stopColor={`rgba(${c.fill},0.05)`} />
          </linearGradient>
          {/* Line glow filter — reduced for performance */}
          <filter id={glowId} x="-5%" y="-5%" width="110%" height="110%">
            <feGaussianBlur stdDeviation="1.5" result="blur" />
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
          dataKey="label"
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
          domain={yDomain}
          tickFormatter={(v) => `${v}${unit}`}
        />

        <Tooltip
          content={<OceanTooltip unit={unit} precision={3} />}
          cursor={{
            stroke: "rgba(0,212,200,0.15)",
            strokeWidth: 1,
            strokeDasharray: "4 4",
          }}
        />

        {/* Threshold reference line */}
        {threshold !== undefined && (
          <ReferenceLine
            y={threshold}
            stroke="#F43F5E"
            strokeDasharray="6 4"
            strokeWidth={1.5}
            label={{
              value: thresholdLabel || `${threshold}`,
              fill: "#F43F5E",
              fontSize: 10,
              position: "right",
            }}
          />
        )}

        {/* 95% confidence band */}
        {data[0]?.upper95 !== undefined && (
          <>
            <Area
              type="monotone"
              dataKey="upper95"
              stroke="none"
              fill={`url(#${gradientId95})`}
              fillOpacity={1}
              name="95% Upper"
              isAnimationActive={animated}
              animationDuration={1200}
              animationEasing="ease-out"
            />
            <Area
              type="monotone"
              dataKey="lower95"
              stroke="none"
              fill="var(--bg-primary)"
              fillOpacity={0.6}
              name="95% Lower"
              isAnimationActive={animated}
              animationDuration={1200}
            />
          </>
        )}

        {/* 80% confidence band */}
        {data[0]?.upper80 !== undefined && (
          <>
            <Area
              type="monotone"
              dataKey="upper80"
              stroke="none"
              fill={`url(#${gradientId80})`}
              fillOpacity={1}
              name="80% Upper"
              isAnimationActive={animated}
              animationDuration={1000}
              animationEasing="ease-out"
            />
            <Area
              type="monotone"
              dataKey="lower80"
              stroke="none"
              fill="var(--bg-primary)"
              fillOpacity={0.7}
              name="80% Lower"
              isAnimationActive={animated}
              animationDuration={1000}
            />
          </>
        )}

        {/* Forecast line with glow */}
        <Area
          type="monotone"
          dataKey="forecast"
          stroke={c.line}
          fill="none"
          strokeWidth={2.5}
          name="Forecast"
          dot={false}
          activeDot={{
            r: 5,
            fill: c.line,
            stroke: "#060F1C",
            strokeWidth: 2,
            filter: `url(#${glowId})`,
          }}
          isAnimationActive={animated}
          animationDuration={800}
          animationEasing="ease-out"
          filter={`url(#${glowId})`}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
