"use client";
import { useState, useRef, useCallback } from "react";

export interface RadarDataset {
  name: string;
  values: number[];
  color: string;
}

interface Props {
  labels: string[];
  datasets: RadarDataset[];
  /** Size of the chart in pixels (default 320) */
  size?: number;
  /** Number of concentric rings (default 4) */
  rings?: number;
  className?: string;
}

/**
 * Pure SVG radar/spider chart -- no external dependencies.
 * Supports 5-6 axes and multiple overlapping datasets.
 */
export default function RadarChart({
  labels,
  datasets,
  size = 320,
  rings = 4,
  className = "",
}: Props) {
  const [tooltip, setTooltip] = useState<{
    x: number;
    y: number;
    label: string;
    values: { name: string; value: number; color: string }[];
  } | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const cx = size / 2;
  const cy = size / 2;
  const radius = size * 0.38;
  const n = labels.length;
  const angleStep = (2 * Math.PI) / n;
  // Start from top (12 o'clock)
  const startAngle = -Math.PI / 2;

  const pointAt = useCallback(
    (i: number, r: number) => {
      const angle = startAngle + i * angleStep;
      return {
        x: cx + r * Math.cos(angle),
        y: cy + r * Math.sin(angle),
      };
    },
    [cx, cy, angleStep, startAngle]
  );

  // Build ring polygons
  const ringPolygons = Array.from({ length: rings }, (_, ri) => {
    const r = ((ri + 1) / rings) * radius;
    const pts = Array.from({ length: n }, (_, i) => {
      const p = pointAt(i, r);
      return `${p.x},${p.y}`;
    }).join(" ");
    return pts;
  });

  // Axis lines
  const axes = Array.from({ length: n }, (_, i) => {
    const outer = pointAt(i, radius);
    return { x1: cx, y1: cy, x2: outer.x, y2: outer.y };
  });

  // Label positions (slightly beyond radius)
  const labelPositions = Array.from({ length: n }, (_, i) => {
    const p = pointAt(i, radius + 18);
    return { x: p.x, y: p.y, label: labels[i] };
  });

  // Dataset polygons
  const dataPolygons = datasets.map((ds) => {
    const pts = ds.values.map((v, i) => {
      const clamped = Math.max(0, Math.min(1, v));
      const p = pointAt(i, clamped * radius);
      return `${p.x},${p.y}`;
    });
    return { name: ds.name, color: ds.color, points: pts.join(" "), values: ds.values };
  });

  // Data point dots for hover
  const dataPoints = datasets.flatMap((ds) =>
    ds.values.map((v, i) => {
      const clamped = Math.max(0, Math.min(1, v));
      const p = pointAt(i, clamped * radius);
      return { x: p.x, y: p.y, dsName: ds.name, color: ds.color, value: v, axisIndex: i };
    })
  );

  const handleAxisHover = (axisIndex: number, event: React.MouseEvent) => {
    if (!svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    setTooltip({
      x,
      y,
      label: labels[axisIndex],
      values: datasets.map((ds) => ({
        name: ds.name,
        value: ds.values[axisIndex],
        color: ds.color,
      })),
    });
  };

  return (
    <div className={`relative inline-block ${className}`}>
      <svg
        ref={svgRef}
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        className="overflow-visible"
        role="img"
        aria-label={`Radar chart comparing ${datasets.map(ds => ds.name).join(" and ")} across ${labels.join(", ")}`}
        onMouseLeave={() => setTooltip(null)}
      >
        {/* Background rings */}
        {ringPolygons.map((pts, i) => (
          <polygon
            key={`ring-${i}`}
            points={pts}
            fill="none"
            stroke="rgba(255,255,255,0.06)"
            strokeWidth={1}
          />
        ))}

        {/* Axis lines */}
        {axes.map((a, i) => (
          <line
            key={`axis-${i}`}
            x1={a.x1}
            y1={a.y1}
            x2={a.x2}
            y2={a.y2}
            stroke="rgba(255,255,255,0.08)"
            strokeWidth={1}
          />
        ))}

        {/* Dataset filled polygons */}
        {dataPolygons.map((dp, i) => (
          <polygon
            key={`ds-fill-${i}`}
            points={dp.points}
            fill={dp.color}
            fillOpacity={0.12}
            stroke={dp.color}
            strokeWidth={2}
            strokeOpacity={0.8}
            strokeLinejoin="round"
          />
        ))}

        {/* Data points */}
        {dataPoints.map((pt, i) => (
          <circle
            key={`pt-${i}`}
            cx={pt.x}
            cy={pt.y}
            r={3.5}
            fill={pt.color}
            fillOpacity={0.9}
            stroke="rgba(0,0,0,0.4)"
            strokeWidth={1}
          />
        ))}

        {/* Invisible hover zones per axis (larger hit area) */}
        {Array.from({ length: n }, (_, i) => {
          const p = pointAt(i, radius * 0.5);
          return (
            <circle
              key={`hover-${i}`}
              cx={p.x}
              cy={p.y}
              r={radius * 0.25}
              fill="transparent"
              role="button"
              tabIndex={0}
              aria-label={`${labels[i]} axis: ${datasets.map(ds => `${ds.name} ${(ds.values[i] * 100).toFixed(0)}%`).join(", ")}`}
              onMouseEnter={(e) => handleAxisHover(i, e)}
              onMouseMove={(e) => handleAxisHover(i, e)}
              onFocus={(e) => handleAxisHover(i, e as unknown as React.MouseEvent)}
              onBlur={() => setTooltip(null)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  if (tooltip?.label === labels[i]) {
                    setTooltip(null);
                  } else {
                    setTooltip({
                      x: p.x,
                      y: p.y,
                      label: labels[i],
                      values: datasets.map((ds) => ({
                        name: ds.name,
                        value: ds.values[i],
                        color: ds.color,
                      })),
                    });
                  }
                }
              }}
              className="cursor-crosshair"
            />
          );
        })}

        {/* Axis labels */}
        {labelPositions.map((lp, i) => (
          <text
            key={`label-${i}`}
            x={lp.x}
            y={lp.y}
            textAnchor="middle"
            dominantBaseline="central"
            className="fill-[var(--text-secondary)] text-[10px] font-medium select-none pointer-events-none"
          >
            {lp.label}
          </text>
        ))}

        {/* Ring value labels */}
        {Array.from({ length: rings }, (_, ri) => {
          const val = ((ri + 1) / rings) * 100;
          const p = pointAt(0, ((ri + 1) / rings) * radius);
          return (
            <text
              key={`rv-${ri}`}
              x={p.x + 4}
              y={p.y - 4}
              className="fill-[var(--text-secondary)] text-[8px] font-mono opacity-40 select-none pointer-events-none"
            >
              {val.toFixed(0)}
            </text>
          );
        })}
      </svg>

      {/* Tooltip */}
      {tooltip && (
        <div
          className="absolute z-50 px-3 py-2 rounded-lg bg-fjord-surface/95 border border-white/[0.1] shadow-xl text-xs pointer-events-none"
          style={{
            left: tooltip.x + 12,
            top: tooltip.y - 8,
            transform: tooltip.x > size * 0.6 ? "translateX(-110%)" : "none",
          }}
        >
          <div className="font-semibold text-[var(--text-primary)] mb-1">{tooltip.label}</div>
          {tooltip.values.map((v, i) => (
            <div key={i} className="flex items-center gap-2">
              <span
                className="w-2 h-2 rounded-full flex-shrink-0"
                style={{ backgroundColor: v.color }}
              />
              <span className="text-[var(--text-secondary)]">{v.name}:</span>
              <span className="font-mono font-semibold">{(v.value * 100).toFixed(0)}%</span>
            </div>
          ))}
        </div>
      )}

      {/* Legend */}
      <div className="flex items-center justify-center gap-4 mt-3">
        {datasets.map((ds, i) => (
          <div key={i} className="flex items-center gap-1.5 text-[11px]">
            <span
              className="w-3 h-3 rounded-xs"
              style={{ backgroundColor: ds.color, opacity: 0.7 }}
            />
            <span className="text-[var(--text-secondary)]">{ds.name}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
