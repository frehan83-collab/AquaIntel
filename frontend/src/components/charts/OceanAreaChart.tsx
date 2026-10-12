"use client";
import { useMemo } from "react";
import type { EChartsCoreOption } from "echarts/core";
import EChart from "./EChart";
import { chartPalette, colors } from "@/lib/design-tokens";

/* ─────────────────────────────────────────────────────────────────
 * Premium Multi-Series Area Chart — ECharts 6 edition (Session 41)
 * ─────────────────────────────────────────────────────────────────
 * Same props contract as the previous Recharts implementation
 * (drop-in): gradient area fills, threshold mark-line, unit-aware
 * tooltip, legend, animation. Canvas rendering + built-in resize.
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
  const option = useMemo<EChartsCoreOption>(() => {
    const categories = (data || []).map((row) => String(row?.[xKey] ?? ""));

    const eSeries = series.map((s, i) => {
      const color = s.color || OCEAN_PALETTE[i % OCEAN_PALETTE.length];
      return {
        name: s.name || s.key,
        type: "line" as const,
        smooth: 0.35,
        symbol: "none",
        data: (data || []).map((row) => {
          const v = row?.[s.key];
          return typeof v === "number" ? v : null;
        }),
        lineStyle: {
          color,
          width: s.strokeWidth || 2,
          type: s.dashed ? ("dashed" as const) : ("solid" as const),
        },
        itemStyle: { color },
        areaStyle:
          s.filled !== false
            ? {
                color: {
                  type: "linear" as const,
                  x: 0, y: 0, x2: 0, y2: 1,
                  colorStops: [
                    { offset: 0.05, color: `${color}40` }, // 25% alpha
                    { offset: 0.5, color: `${color}14` },  // 8%
                    { offset: 0.95, color: `${color}00` }, // 0%
                  ],
                },
              }
            : undefined,
        emphasis: { focus: "series" as const },
      };
    });

    return {
      animation: animated,
      animationDuration: 800,
      animationEasing: "cubicOut",
      grid: { top: 8, right: 12, left: -6, bottom: showLegend ? 34 : 4, containLabel: true },
      tooltip: {
        trigger: "axis",
        backgroundColor: "rgba(6,15,28,0.92)",
        borderColor: "rgba(255,255,255,0.08)",
        textStyle: { color: "#E2E8F0", fontSize: 12 },
        valueFormatter: (v: unknown) =>
          typeof v === "number" ? `${v}${unit}` : "—",
        axisPointer: {
          lineStyle: { color: "rgba(0,212,200,0.25)", type: "dashed" as const },
        },
      },
      legend: showLegend
        ? {
            bottom: 0,
            icon: "circle",
            itemWidth: 8,
            itemHeight: 8,
            textStyle: { color: "rgba(136,153,170,0.85)", fontSize: 11 },
          }
        : undefined,
      xAxis: {
        type: "category" as const,
        boundaryGap: false,
        data: categories,
        axisLine: { lineStyle: { color: "rgba(255,255,255,0.06)" } },
        axisTick: { show: false },
        axisLabel: { color: "rgba(136,153,170,0.75)", fontSize: 11 },
      },
      yAxis: {
        type: "value" as const,
        scale: true,
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { lineStyle: { color: "rgba(255,255,255,0.04)", type: "dashed" as const } },
        axisLabel: {
          color: "rgba(136,153,170,0.75)",
          fontSize: 11,
          formatter: (v: number) => `${v}${unit}`,
        },
      },
      series: eSeries.map((s, i) =>
        i === 0 && threshold !== undefined
          ? {
              ...s,
              markLine: {
                silent: true,
                symbol: "none",
                lineStyle: { color: colors.danger, type: "dashed" as const, width: 1.5 },
                label: {
                  formatter: thresholdLabel || `Limit: ${threshold}`,
                  color: "rgba(244,63,94,0.85)",
                  fontSize: 10,
                  position: "insideEndTop" as const,
                },
                data: [{ yAxis: threshold }],
              },
            }
          : s
      ),
    };
  }, [data, xKey, series, threshold, thresholdLabel, unit, showLegend, animated]);

  return <EChart option={option} height={height} />;
}
