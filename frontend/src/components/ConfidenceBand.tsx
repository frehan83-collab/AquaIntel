"use client";

import { useState } from "react";

interface DataPoint {
  x: number;
  y: number;
  lo80?: number;
  hi80?: number;
  lo95?: number;
  hi95?: number;
}

interface Props {
  data: DataPoint[];
  width?: number;
  height?: number;
  xLabel?: string;
  yLabel?: string;
  unit?: string;
  title?: string;
}

export default function ConfidenceBand({
  data,
  width = 400,
  height = 160,
  xLabel,
  yLabel,
  unit = "",
  title,
}: Props) {
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);

  if (!data || data.length < 2) return null;

  // Calculate scales
  const xMin = Math.min(...data.map((d) => d.x));
  const xMax = Math.max(...data.map((d) => d.x));
  const allY = data.flatMap((d) => [d.lo95 ?? d.y, d.hi95 ?? d.y, d.y]);
  const yMin = Math.min(...allY);
  const yMax = Math.max(...allY);
  const pad = 24;

  const sx = (x: number) =>
    pad + ((x - xMin) / (xMax - xMin || 1)) * (width - 2 * pad);
  const sy = (y: number) =>
    height - pad - ((y - yMin) / (yMax - yMin || 1)) * (height - 2 * pad);

  // Build center line path
  const centerPath = data
    .map((d, i) => `${i === 0 ? "M" : "L"}${sx(d.x)},${sy(d.y)}`)
    .join(" ");

  // 95% confidence band
  const band95 = data.filter((d) => d.lo95 != null && d.hi95 != null);
  const band95Path =
    band95.length > 1
      ? [
          ...band95.map(
            (d, i) => `${i === 0 ? "M" : "L"}${sx(d.x)},${sy(d.hi95!)}`
          ),
          ...[...band95]
            .reverse()
            .map(
              (d, i) => `${i === 0 ? "L" : "L"}${sx(d.x)},${sy(d.lo95!)}`
            ),
          "Z",
        ].join(" ")
      : "";

  // 80% confidence band
  const band80 = data.filter((d) => d.lo80 != null && d.hi80 != null);
  const band80Path =
    band80.length > 1
      ? [
          ...band80.map(
            (d, i) => `${i === 0 ? "M" : "L"}${sx(d.x)},${sy(d.hi80!)}`
          ),
          ...[...band80]
            .reverse()
            .map(
              (d, i) => `${i === 0 ? "L" : "L"}${sx(d.x)},${sy(d.lo80!)}`
            ),
          "Z",
        ].join(" ")
      : "";

  const hovered = hoverIdx !== null ? data[hoverIdx] : null;

  return (
    <div className="relative">
      {title && (
        <p className="text-xs text-[var(--text-secondary)] mb-1 font-medium">
          {title}
        </p>
      )}
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full"
        style={{ maxHeight: height }}
      >
        {/* 95% band — lightest fill */}
        {band95Path && (
          <path d={band95Path} fill="rgba(0,212,200,0.08)" />
        )}
        {/* 80% band — medium fill */}
        {band80Path && (
          <path d={band80Path} fill="rgba(0,212,200,0.18)" />
        )}
        {/* Central line */}
        <path
          d={centerPath}
          fill="none"
          stroke="#00D4C8"
          strokeWidth="2"
          strokeLinejoin="round"
        />
        {/* Data points with hover zones */}
        {data.map((d, i) => (
          <g key={i}>
            {/* Invisible wider hit area for hover */}
            <circle
              cx={sx(d.x)}
              cy={sy(d.y)}
              r="10"
              fill="transparent"
              onMouseEnter={() => setHoverIdx(i)}
              onMouseLeave={() => setHoverIdx(null)}
              style={{ cursor: "crosshair" }}
            />
            <circle
              cx={sx(d.x)}
              cy={sy(d.y)}
              r={hoverIdx === i ? 4 : 2.5}
              fill="#00D4C8"
              className="transition-all duration-150"
            />
          </g>
        ))}
        {/* Y-axis labels */}
        <text
          x={2}
          y={sy(yMax) + 3}
          className="fill-[var(--text-secondary)]"
          fontSize="8"
        >
          {yMax.toFixed(2)}
          {unit}
        </text>
        <text
          x={2}
          y={sy(yMin) + 3}
          className="fill-[var(--text-secondary)]"
          fontSize="8"
        >
          {yMin.toFixed(2)}
          {unit}
        </text>
        {/* X-axis labels */}
        {xLabel && (
          <text
            x={width / 2}
            y={height - 2}
            textAnchor="middle"
            className="fill-[var(--text-secondary)]"
            fontSize="8"
          >
            {xLabel}
          </text>
        )}
        {yLabel && (
          <text
            x={4}
            y={height / 2}
            textAnchor="middle"
            className="fill-[var(--text-secondary)]"
            fontSize="8"
            transform={`rotate(-90, 4, ${height / 2})`}
          >
            {yLabel}
          </text>
        )}
      </svg>

      {/* Hover tooltip */}
      {hovered && hoverIdx !== null && (
        <div
          className="absolute z-10 px-2.5 py-1.5 rounded-lg text-[10px] leading-tight pointer-events-none
            bg-[var(--glass-bg)] backdrop-blur-md border border-[var(--glass-border)]
            shadow-lg text-[var(--text-primary)]"
          style={{
            left: `${(sx(hovered.x) / width) * 100}%`,
            top: `${Math.max(0, sy(hovered.y) - 48)}px`,
            transform: "translateX(-50%)",
          }}
        >
          <div className="font-semibold text-[#00D4C8]">
            {hovered.y.toFixed(3)}
            {unit}
          </div>
          {hovered.lo80 != null && hovered.hi80 != null && (
            <div className="opacity-70">
              80%: {hovered.lo80.toFixed(3)} &ndash; {hovered.hi80.toFixed(3)}
            </div>
          )}
          {hovered.lo95 != null && hovered.hi95 != null && (
            <div className="opacity-50">
              95%: {hovered.lo95.toFixed(3)} &ndash; {hovered.hi95.toFixed(3)}
            </div>
          )}
        </div>
      )}

      {/* Legend */}
      <div className="flex justify-between text-[9px] text-[var(--text-secondary)] mt-1 px-1">
        <span className="flex items-center gap-1">
          <span
            className="inline-block w-3 h-2 rounded-sm"
            style={{ background: "rgba(0,212,200,0.08)" }}
          />
          95% confidence
        </span>
        <span className="flex items-center gap-1">
          <span
            className="inline-block w-3 h-2 rounded-sm"
            style={{ background: "rgba(0,212,200,0.18)" }}
          />
          80% confidence
        </span>
        <span className="flex items-center gap-1">
          <span
            className="inline-block w-3 h-1 rounded-sm"
            style={{ background: "#00D4C8" }}
          />
          Central estimate
        </span>
      </div>
    </div>
  );
}
