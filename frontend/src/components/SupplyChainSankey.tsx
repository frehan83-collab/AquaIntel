"use client";
import { useState, useMemo, useRef, useCallback } from "react";
import { chartPalette } from "@/lib/design-tokens";

/* ────────────────────────────────────────────────────────────────────────────
 * SupplyChainSankey — Pure SVG Sankey diagram for salmon production flow
 *
 * Visualises: Smolt Production → Sea Growth → Harvest → Processing → Markets
 * No external library — cubic bezier links, proportional widths, glassmorphic
 * tooltip matching existing OpenClaw design language.
 * ──────────────────────────────────────────────────────────────────────── */

/* ─── Types ──────────────────────────────────────────────────────────────── */

export interface SankeyNode {
  id: string;
  label: string;
  /** Which column (stage) this node belongs to (0-based) */
  column: number;
  /** Volume in kt */
  value: number;
  /** Optional override colour */
  color?: string;
}

export interface SankeyLink {
  source: string;
  target: string;
  /** Flow volume in kt */
  value: number;
  /** Optional label for tooltip */
  label?: string;
}

export interface SankeyData {
  nodes: SankeyNode[];
  links: SankeyLink[];
  /** Column stage labels */
  stages?: string[];
}

interface SupplyChainSankeyProps {
  data: SankeyData;
  title?: string;
  height?: number;
}

/* ─── Stage colour palette ───────────────────────────────────────────────── */

const STAGE_COLORS: Record<number, string> = {
  0: chartPalette[5],     // emerald — smolt / production origins
  1: "rgb(56,189,248)",   // sky     — sea growth
  2: chartPalette[3],     // amber   — harvest
  3: chartPalette[2],     // violet  — processing
  4: chartPalette[4],     // pink    — export markets
};

function nodeColor(node: SankeyNode): string {
  if (node.color) return node.color;
  return STAGE_COLORS[node.column] ?? "rgb(148,163,184)";
}

function linkColor(sourceCol: number): string {
  const base = STAGE_COLORS[sourceCol] ?? "rgb(148,163,184)";
  return base;
}

/* ─── Layout engine ──────────────────────────────────────────────────────── */

interface LayoutNode {
  id: string;
  label: string;
  column: number;
  value: number;
  color: string;
  x: number;
  y: number;
  w: number;
  h: number;
}

interface LayoutLink {
  source: string;
  target: string;
  value: number;
  label: string;
  sourceCol: number;
  sy: number; // source y start
  ty: number; // target y start
  thickness: number;
}

function computeLayout(
  data: SankeyData,
  width: number,
  height: number,
): { nodes: LayoutNode[]; links: LayoutLink[] } {
  const PAD_TOP = 40;
  const PAD_BOTTOM = 16;
  const PAD_LEFT = 12;
  const PAD_RIGHT = 12;
  const NODE_W = 18;
  const NODE_GAP = 14;

  const plotW = width - PAD_LEFT - PAD_RIGHT;
  const plotH = height - PAD_TOP - PAD_BOTTOM;

  /* Group nodes by column */
  const columns = new Map<number, SankeyNode[]>();
  for (const n of data.nodes) {
    const arr = columns.get(n.column) || [];
    arr.push(n);
    columns.set(n.column, arr);
  }
  const numCols = Math.max(...Array.from(columns.keys())) + 1;
  const colSpacing = numCols > 1 ? (plotW - NODE_W) / (numCols - 1) : 0;

  /* For each column, compute total value to scale heights */
  const colTotals = new Map<number, number>();
  Array.from(columns.entries()).forEach(([col, colNodes]) => {
    colTotals.set(col, colNodes.reduce((s: number, n: SankeyNode) => s + n.value, 0));
  });
  const maxTotal = Math.max(...Array.from(colTotals.values()), 1);

  /* Position nodes */
  const layoutNodes = new Map<string, LayoutNode>();
  Array.from(columns.entries()).forEach(([col, colNodes]) => {
    const x = PAD_LEFT + col * colSpacing;
    const totalVal = colTotals.get(col) || 1;
    const availableH = plotH - (colNodes.length - 1) * NODE_GAP;
    const scale = availableH / totalVal;

    let yOff = PAD_TOP;
    for (const n of colNodes) {
      const h = Math.max(n.value * scale, 4);
      layoutNodes.set(n.id, {
        id: n.id,
        label: n.label,
        column: n.column,
        value: n.value,
        color: nodeColor(n),
        x,
        y: yOff,
        w: NODE_W,
        h,
      });
      yOff += h + NODE_GAP;
    }
  });

  /* Position links — track consumed vertical space on source and target */
  const sourceOffsets = new Map<string, number>();
  const targetOffsets = new Map<string, number>();
  for (const n of Array.from(layoutNodes.values())) {
    sourceOffsets.set(n.id, 0);
    targetOffsets.set(n.id, 0);
  }

  const layoutLinks: LayoutLink[] = [];
  /* Sort links by value descending for nicer stacking */
  const sortedLinks = [...data.links].sort((a, b) => b.value - a.value);

  for (const link of sortedLinks) {
    const sn = layoutNodes.get(link.source);
    const tn = layoutNodes.get(link.target);
    if (!sn || !tn) continue;

    const thickness = (link.value / sn.value) * sn.h;
    const sy = sn.y + (sourceOffsets.get(link.source) || 0);
    const tThickness = (link.value / tn.value) * tn.h;
    const ty = tn.y + (targetOffsets.get(link.target) || 0);

    sourceOffsets.set(link.source, (sourceOffsets.get(link.source) || 0) + thickness);
    targetOffsets.set(link.target, (targetOffsets.get(link.target) || 0) + tThickness);

    layoutLinks.push({
      source: link.source,
      target: link.target,
      value: link.value,
      label: link.label || `${sn.label} \u2192 ${tn.label}: ${link.value}kt`,
      sourceCol: sn.column,
      sy,
      ty,
      thickness: Math.max(thickness, 1.5),
    });
  }

  return { nodes: Array.from(layoutNodes.values()), links: layoutLinks };
}

/* ─── SVG path for a link (cubic bezier) ─────────────────────────────────── */

function linkPath(
  sx: number,
  sy: number,
  sThick: number,
  tx: number,
  ty: number,
  tThick: number,
): string {
  const midX = (sx + tx) / 2;
  return [
    `M${sx},${sy}`,
    `C${midX},${sy} ${midX},${ty} ${tx},${ty}`,
    `L${tx},${ty + tThick}`,
    `C${midX},${ty + tThick} ${midX},${sy + sThick} ${sx},${sy + sThick}`,
    "Z",
  ].join(" ");
}

/* ─── Component ──────────────────────────────────────────────────────────── */

export default function SupplyChainSankey({
  data,
  title,
  height: H = 360,
}: SupplyChainSankeyProps) {
  const W = 760;
  const svgRef = useRef<SVGSVGElement>(null);
  const [hoveredLink, setHoveredLink] = useState<LayoutLink | null>(null);
  const [mousePos, setMousePos] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  const { nodes, links } = useMemo(() => computeLayout(data, W, H), [data, W, H]);

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      if (!svgRef.current) return;
      const rect = svgRef.current.getBoundingClientRect();
      setMousePos({
        x: ((e.clientX - rect.left) / rect.width) * W,
        y: ((e.clientY - rect.top) / rect.height) * H,
      });
    },
    [W, H],
  );

  const NODE_W = 18;
  const stages = data.stages || ["Production", "Growth", "Harvest", "Processing", "Markets"];

  /* Empty state */
  if (!data.nodes.length) {
    return (
      <div
        className="flex items-center justify-center rounded-xl border border-white/[0.06] bg-white/[0.02]"
        style={{ width: "100%", height: H }}
      >
        <span className="text-sm text-[var(--text-secondary)] opacity-50">No supply chain data</span>
      </div>
    );
  }

  return (
    <div className="relative w-full select-none">
      {title && (
        <div className="text-xs font-medium text-[var(--text-secondary)] mb-2 ml-1">{title}</div>
      )}

      {/* Stage column headers */}
      <div className="flex justify-between mb-1 px-3">
        {stages.map((s, i) => (
          <span
            key={i}
            className="text-[10px] font-semibold uppercase tracking-wider"
            style={{ color: STAGE_COLORS[i] ?? "rgba(255,255,255,0.4)", opacity: 0.8 }}
          >
            {s}
          </span>
        ))}
      </div>

      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        width="100%"
        preserveAspectRatio="xMidYMid meet"
        style={{ overflow: "visible" }}
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHoveredLink(null)}
        className="cursor-default"
        role="img"
        aria-label={`${title ? title + ": " : ""}Supply chain Sankey diagram with ${nodes.length} nodes and ${links.length} flow links`}
      >
        {/* Links */}
        {links.map((lk, i) => {
          const sn = nodes.find((n) => n.id === lk.source)!;
          const tn = nodes.find((n) => n.id === lk.target)!;
          const sx = sn.x + NODE_W;
          const tx = tn.x;
          const tThick = (lk.value / tn.value) * tn.h;
          const isHovered = hoveredLink === lk;

          return (
            <path
              key={`link-${i}`}
              d={linkPath(sx, lk.sy, lk.thickness, tx, lk.ty, tThick)}
              fill={linkColor(lk.sourceCol)}
              opacity={hoveredLink ? (isHovered ? 0.45 : 0.08) : 0.2}
              stroke={isHovered ? "rgba(255,255,255,0.3)" : "none"}
              strokeWidth={isHovered ? 0.5 : 0}
              role="button"
              tabIndex={0}
              aria-label={`Flow: ${lk.label} (${lk.value}kt)`}
              onMouseEnter={() => setHoveredLink(lk)}
              onMouseLeave={() => setHoveredLink(null)}
              onFocus={() => setHoveredLink(lk)}
              onBlur={() => setHoveredLink(null)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  setHoveredLink(hoveredLink === lk ? null : lk);
                }
              }}
              style={{ cursor: "pointer", transition: "opacity 0.2s" }}
            />
          );
        })}

        {/* Nodes */}
        {nodes.map((n) => (
          <g key={n.id}>
            <rect
              x={n.x}
              y={n.y}
              width={n.w}
              height={n.h}
              rx={4}
              fill={n.color}
              opacity={0.9}
              stroke="rgba(255,255,255,0.15)"
              strokeWidth={0.5}
            />
            {/* Label — right side for left columns, left side for right columns */}
            {n.column < 3 ? (
              <text
                x={n.x + n.w + 6}
                y={n.y + n.h / 2 + 1}
                dominantBaseline="central"
                fill="rgba(255,255,255,0.75)"
                fontSize={10}
                fontWeight="600"
              >
                {n.label}
              </text>
            ) : (
              <text
                x={n.x - 6}
                y={n.y + n.h / 2 + 1}
                textAnchor="end"
                dominantBaseline="central"
                fill="rgba(255,255,255,0.75)"
                fontSize={10}
                fontWeight="600"
              >
                {n.label}
              </text>
            )}
            {/* Value */}
            {n.h > 16 && (
              n.column < 3 ? (
                <text
                  x={n.x + n.w + 6}
                  y={n.y + n.h / 2 + 13}
                  dominantBaseline="central"
                  fill="rgba(255,255,255,0.35)"
                  fontSize={8}
                  fontFamily="monospace"
                >
                  {n.value}kt
                </text>
              ) : (
                <text
                  x={n.x - 6}
                  y={n.y + n.h / 2 + 13}
                  textAnchor="end"
                  dominantBaseline="central"
                  fill="rgba(255,255,255,0.35)"
                  fontSize={8}
                  fontFamily="monospace"
                >
                  {n.value}kt
                </text>
              )
            )}
          </g>
        ))}
      </svg>

      {/* Glassmorphic tooltip */}
      {hoveredLink && (
        <div
          className="absolute pointer-events-none z-30"
          style={{
            left: `${(mousePos.x / W) * 100}%`,
            top: `${(mousePos.y / H) * 100}%`,
            transform: mousePos.x > W * 0.65 ? "translate(-110%, -50%)" : "translate(10%, -50%)",
          }}
        >
          <div className="bg-[rgba(6,15,28,0.94)] backdrop-blur-2xl border border-white/[0.1] rounded-xl px-3 py-2.5 shadow-[0_8px_32px_rgba(0,0,0,0.5)] min-w-[160px]">
            <p className="text-xs font-semibold text-[var(--text-primary)]">
              {hoveredLink.label}
            </p>
            <div className="mt-1.5 space-y-0.5 text-[10px]">
              <div className="flex justify-between gap-4">
                <span className="text-[var(--text-secondary)]">Volume</span>
                <span className="font-mono font-bold text-ocean-400">
                  {hoveredLink.value}kt
                </span>
              </div>
              <div className="flex justify-between gap-4">
                <span className="text-[var(--text-secondary)]">Share</span>
                <span className="font-mono text-[var(--text-secondary)]">
                  {((hoveredLink.value / Math.max(nodes.filter(n => n.column === 0).reduce((s, n) => s + n.value, 0), 1)) * 100).toFixed(1)}%
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
