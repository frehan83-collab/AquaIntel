"use client";
import { useMemo, useState, useCallback } from "react";
import MapGL, { NavigationControl, Source, Layer } from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";
import { useTranslation, formatNumber } from "@/lib/i18n";

/* eslint-disable @typescript-eslint/no-explicit-any */

interface RiskAssessment {
  locality_no: number;
  locality_name: string;
  owner_company: string | null;
  latitude: number;
  longitude: number;
  risk_level: "LOW" | "ELEVATED" | "HIGH" | "CRITICAL";
  risk_score: number;
  chl_a: number;
  sst: number | null;
  chl_a_trend: number;
  assessed_at: string;
  factors: string;
}

interface BloomMapProps {
  risks: RiskAssessment[];
  onSiteClick?: (site: RiskAssessment) => void;
}

/** RGB colour for each bloom risk level */
function riskRgb(level: string): [number, number, number] {
  switch (level) {
    case "CRITICAL": return [239, 68,  68];   // rose-500
    case "HIGH":     return [249, 115, 22];   // orange-500
    case "ELEVATED": return [245, 158, 11];   // amber-500
    default:         return [16,  185, 129];  // emerald-500
  }
}

/** Dot radius driven by chl-a intensity */
function chlRadius(chl: number): number {
  return Math.max(4, Math.min(14, chl * 2.5 + 4));
}

export default function BloomMap({ risks, onSiteClick }: BloomMapProps) {
  const { locale } = useTranslation();
  const [hoveredSite, setHoveredSite] = useState<any>(null);
  const [cursor, setCursor]           = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  // ── GeoJSON: one point per locality ──────────────────────────────────────
  const sitesGeoJson = useMemo(() => ({
    type: "FeatureCollection" as const,
    features: risks
      .filter((r) => r.latitude && r.longitude)
      .map((r) => {
        const [cr, cg, cb] = riskRgb(r.risk_level);
        return {
          type: "Feature" as const,
          geometry: { type: "Point" as const, coordinates: [r.longitude, r.latitude] },
          properties: {
            id:           r.locality_no,
            name:         r.locality_name || `Locality ${r.locality_no}`,
            company:      r.owner_company || "",
            risk_level:   r.risk_level,
            risk_score:   r.risk_score,
            chl_a:        r.chl_a,
            sst:          r.sst,
            chl_a_trend:  r.chl_a_trend,
            assessed_at:  r.assessed_at,
            radius:       chlRadius(r.chl_a),
            color_r:      cr,
            color_g:      cg,
            color_b:      cb,
          },
        };
      }),
  }), [risks]);

  // ── Heatmap weighted by chl-a value ───────────────────────────────────────
  const heatmapGeoJson = useMemo(() => ({
    type: "FeatureCollection" as const,
    features: risks
      .filter((r) => r.latitude && r.longitude && r.chl_a > 0)
      .map((r) => ({
        type: "Feature" as const,
        geometry: { type: "Point" as const, coordinates: [r.longitude, r.latitude] },
        properties: { weight: Math.min(r.chl_a / 5, 2) },   // normalise: 5 mg/m³ → full weight
      })),
  }), [risks]);

  // ── Interaction handlers ──────────────────────────────────────────────────
  const onHover = useCallback((e: any) => {
    const feature = e.features?.[0];
    if (feature) {
      setHoveredSite(feature.properties);
      setCursor({ x: e.point.x, y: e.point.y });
    } else {
      setHoveredSite(null);
    }
  }, []);

  const onClick = useCallback((e: any) => {
    const feature = e.features?.[0];
    if (feature && onSiteClick) {
      const site = risks.find((r) => r.locality_no === feature.properties.id);
      if (site) onSiteClick(site);
    }
  }, [onSiteClick, risks]);

  // Stats for the badge
  const critical = risks.filter((r) => r.risk_level === "CRITICAL").length;
  const high      = risks.filter((r) => r.risk_level === "HIGH").length;

  return (
    <div
      className="relative rounded-2xl overflow-hidden border border-white/[0.08] shadow-[0_8px_32px_rgba(0,0,0,0.3)]"
      style={{ height: 520 }}
    >
      {/* Vignette overlay */}
      <div className="absolute inset-0 pointer-events-none z-10 bg-gradient-to-b from-[rgba(6,15,28,0.25)] via-transparent to-[rgba(6,15,28,0.4)]" />

      {/* ── Legend ── */}
      <div className="absolute top-4 left-4 z-20 bg-[rgba(6,15,28,0.88)] backdrop-blur-xl border border-white/[0.08] rounded-xl px-3 py-2.5 space-y-1.5">
        <p className="text-[10px] font-semibold text-[var(--text-primary)] uppercase tracking-wider">
          Chlorophyll-a Bloom Risk
        </p>
        {[
          { color: "#10B981", label: "LOW  (< 2 mg/m³)" },
          { color: "#F59E0B", label: "ELEVATED  (2–5 mg/m³)" },
          { color: "#F97316", label: "HIGH  (5–10 mg/m³)" },
          { color: "#EF4444", label: "CRITICAL  (> 10 mg/m³)" },
        ].map(({ color, label }) => (
          <div key={label} className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: color }} />
            <span className="text-[10px] text-[var(--text-secondary)]">{label}</span>
          </div>
        ))}
      </div>

      {/* ── Stats badge ── */}
      <div className="absolute top-4 right-4 z-20 bg-[rgba(6,15,28,0.88)] backdrop-blur-xl border border-white/[0.08] rounded-xl px-3 py-1.5 flex items-center gap-2">
        {(critical + high) > 0 ? (
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20 animate-pulse">
            {critical + high} HIGH/CRITICAL
          </span>
        ) : (
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            All Clear
          </span>
        )}
        <span className="text-[10px] text-[var(--text-secondary)]">{risks.filter(r => r.latitude && r.longitude).length} sites</span>
      </div>

      {/* ── MapLibre GL ── */}
      <MapGL
        initialViewState={{
          longitude: 14,
          latitude:  66,
          zoom:      4.3,
          pitch:     10,
        }}
        style={{ width: "100%", height: "100%" }}
        mapStyle="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"
        interactiveLayerIds={["bloom-sites-circle"]}
        onMouseMove={onHover}
        onClick={onClick}
        cursor={hoveredSite ? "pointer" : "grab"}
      >
        <NavigationControl position="bottom-right" />

        {/* Heatmap — chl-a intensity at real farm positions */}
        <Source id="bloom-heatmap" type="geojson" data={heatmapGeoJson}>
          <Layer
            id="bloom-heatmap-layer"
            type="heatmap"
            paint={{
              "heatmap-weight":     ["get", "weight"],
              "heatmap-intensity":  0.6,
              "heatmap-radius":     28,
              "heatmap-opacity":    0.5,
              "heatmap-color": [
                "interpolate", ["linear"], ["heatmap-density"],
                0,    "rgba(0,0,0,0)",
                0.1,  "rgba(16,185,129,0.1)",
                0.3,  "rgba(245,158,11,0.2)",
                0.6,  "rgba(249,115,22,0.4)",
                0.85, "rgba(239,68,68,0.55)",
                1,    "rgba(220,38,38,0.75)",
              ],
            }}
          />
        </Source>

        {/* Farm dots — glow ring */}
        <Source id="bloom-sites" type="geojson" data={sitesGeoJson}>
          <Layer
            id="bloom-sites-glow"
            type="circle"
            paint={{
              "circle-radius":  ["*", ["get", "radius"], 1.9],
              "circle-color":   ["rgb", ["get", "color_r"], ["get", "color_g"], ["get", "color_b"]],
              "circle-opacity": 0.18,
              "circle-blur":    0.9,
            }}
          />
          {/* Farm dots — main */}
          <Layer
            id="bloom-sites-circle"
            type="circle"
            paint={{
              "circle-radius":        ["get", "radius"],
              "circle-color":         ["rgb", ["get", "color_r"], ["get", "color_g"], ["get", "color_b"]],
              "circle-opacity":       0.88,
              "circle-stroke-width":  0.8,
              "circle-stroke-color":  "rgba(255,255,255,0.15)",
            }}
          />
        </Source>
      </MapGL>

      {/* ── Glassmorphic tooltip ── */}
      {hoveredSite && (
        <div
          className="absolute z-30 pointer-events-none"
          style={{ left: Math.min(cursor.x + 14, 580), top: cursor.y - 10 }}
        >
          <div className="bg-[rgba(6,15,28,0.94)] backdrop-blur-2xl border border-white/[0.1] rounded-xl px-3 py-2.5 shadow-[0_8px_32px_rgba(0,0,0,0.5)] min-w-[200px]">
            <p className="text-xs font-semibold text-[var(--text-primary)]">{hoveredSite.name}</p>
            <p className="text-[10px] text-[var(--text-secondary)]">#{hoveredSite.id}</p>
            {hoveredSite.company && (
              <p className="text-[10px] text-ocean-400 font-medium mt-0.5">{hoveredSite.company}</p>
            )}
            <div className="mt-1.5 space-y-0.5 text-[10px]">
              <div className="flex justify-between gap-4">
                <span className="text-[var(--text-secondary)]">Bloom risk</span>
                <span className={`font-semibold ${
                  hoveredSite.risk_level === "CRITICAL" ? "text-rose-400" :
                  hoveredSite.risk_level === "HIGH"     ? "text-orange-400" :
                  hoveredSite.risk_level === "ELEVATED" ? "text-amber-400" : "text-emerald-400"
                }`}>{hoveredSite.risk_level}</span>
              </div>
              <div className="flex justify-between gap-4">
                <span className="text-[var(--text-secondary)]">Chlorophyll-a</span>
                <span className="font-mono font-bold" style={{
                  color: Number(hoveredSite.chl_a) >= 10 ? "#EF4444" :
                         Number(hoveredSite.chl_a) >= 5  ? "#F97316" :
                         Number(hoveredSite.chl_a) >= 2  ? "#F59E0B" : "#10B981",
                }}>
                  {formatNumber(Number(hoveredSite.chl_a), locale, 2)} mg/m³
                </span>
              </div>
              <div className="flex justify-between gap-4">
                <span className="text-[var(--text-secondary)]">Risk score</span>
                <span className="font-mono">{formatNumber(Number(hoveredSite.risk_score), locale, 0)}</span>
              </div>
              {hoveredSite.sst != null && (
                <div className="flex justify-between gap-4">
                  <span className="text-[var(--text-secondary)]">Sea temp (SST)</span>
                  <span className="font-mono">{formatNumber(Number(hoveredSite.sst), locale, 1)} °C</span>
                </div>
              )}
              {hoveredSite.chl_a_trend != null && (
                <div className="flex justify-between gap-4">
                  <span className="text-[var(--text-secondary)]">Chl-a trend</span>
                  <span className={`font-mono ${
                    Number(hoveredSite.chl_a_trend) > 0.3 ? "text-rose-400" :
                    Number(hoveredSite.chl_a_trend) < -0.3 ? "text-emerald-400" : "text-[var(--text-secondary)]"
                  }`}>
                    {Number(hoveredSite.chl_a_trend) > 0.3 ? "Rising" :
                     Number(hoveredSite.chl_a_trend) < -0.3 ? "Falling" : "Stable"}
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
