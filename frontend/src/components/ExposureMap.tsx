"use client";
import { useMemo, useState, useCallback, useEffect } from "react";
import MapGL, { NavigationControl, Source, Layer } from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";

/* eslint-disable @typescript-eslint/no-explicit-any */

import { api } from "@/lib/api";
import { useApiError } from "@/lib/useApiError";

interface Site {
  id: number;
  name: string;
  lat: number;
  lng: number;
  company: string;
  pa: number | null;
  lice: number;
  cleaner_fish: boolean;
  temp: number | null;
}

interface ExposureMapProps {
  onSiteClick?: (site: Site) => void;
}

export default function ExposureMap({ onSiteClick }: ExposureMapProps) {
  const handleError = useApiError();
  const [sites, setSites] = useState<Site[]>([]);
  const [diseaseGeo, setDiseaseGeo] = useState<any>(null);
  const [showDisease, setShowDisease] = useState(true);
  const [hoveredSite, setHoveredSite] = useState<any>(null);
  const [hoveredDisease, setHoveredDisease] = useState<any>(null);
  const [cursor, setCursor] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  useEffect(() => {
    api.exposureSites()
      .then(setSites)
      .catch(handleError("exposure_sites"));
    // Fetch disease outbreak locations
    fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/disease/norway/geo`)
      .then(r => r.json())
      .then(setDiseaseGeo)
      .catch(handleError("exposure_disease_geo"));
  }, []);

  // GeoJSON for site dots — each point is a REAL locality with REAL coordinates and REAL lice
  const sitesGeoJson = useMemo(() => ({
    type: "FeatureCollection" as const,
    features: sites.map(s => ({
      type: "Feature" as const,
      geometry: { type: "Point" as const, coordinates: [s.lng, s.lat] },
      properties: {
        id: s.id,
        name: s.name,
        company: s.company,
        pa: s.pa,
        lice: s.lice,
        cleaner_fish: s.cleaner_fish,
        temp: s.temp,
        // Color by lice level
        color_r: s.lice >= 0.5 ? 244 : s.lice >= 0.3 ? 245 : s.lice >= 0.15 ? 0 : 16,
        color_g: s.lice >= 0.5 ? 63 : s.lice >= 0.3 ? 158 : s.lice >= 0.15 ? 200 : 185,
        color_b: s.lice >= 0.5 ? 94 : s.lice >= 0.3 ? 11 : s.lice >= 0.15 ? 168 : 129,
        // Size: bigger dot = higher lice (draws attention to problem areas)
        radius: Math.max(3, Math.min(12, s.lice * 20 + 3)),
      },
    })),
  }), [sites]);

  // Heatmap from real lice values at real locations
  const heatmapGeoJson = useMemo(() => ({
    type: "FeatureCollection" as const,
    features: sites
      .filter(s => s.lice > 0)
      .map(s => ({
        type: "Feature" as const,
        geometry: { type: "Point" as const, coordinates: [s.lng, s.lat] },
        properties: { weight: s.lice * 5 },
      })),
  }), [sites]);

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
      const site = sites.find(s => s.id === feature.properties.id);
      if (site) onSiteClick(site);
    }
  }, [onSiteClick, sites]);

  return (
    <div className="relative rounded-2xl overflow-hidden border border-white/[0.08] shadow-[0_8px_32px_rgba(0,0,0,0.3)]" style={{ height: 520 }}>
      {/* Glass gradient overlay */}
      <div className="absolute inset-0 pointer-events-none z-10 bg-gradient-to-b from-[rgba(6,15,28,0.25)] via-transparent to-[rgba(6,15,28,0.4)]" />

      {/* Legend */}
      <div className="absolute top-4 left-4 z-20 bg-[rgba(6,15,28,0.88)] backdrop-blur-xl border border-white/[0.08] rounded-xl px-3 py-2.5 space-y-1.5">
        <p className="text-[10px] font-semibold text-[var(--text-primary)] uppercase tracking-wider">Adult Female Lice / Fish</p>
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
          <span className="text-[10px] text-[var(--text-secondary)]">Clean (&lt;0.15)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-[#00C8A8]" />
          <span className="text-[10px] text-[var(--text-secondary)]">Moderate (0.15–0.3)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-amber-500" />
          <span className="text-[10px] text-[var(--text-secondary)]">Elevated (0.3–0.5)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-rose-500" />
          <span className="text-[10px] text-[var(--text-secondary)]">Above limit (&gt;0.5)</span>
        </div>
        {showDisease && diseaseGeo?.features?.length > 0 && (
          <>
            <div className="border-t border-white/[0.06] mt-1.5 pt-1.5">
              <p className="text-[10px] font-semibold text-rose-400 uppercase tracking-wider">Disease Outbreaks</p>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-rose-500 ring-2 ring-rose-500/30" />
              <span className="text-[10px] text-[var(--text-secondary)]">ISA / IHN (critical)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-orange-400 ring-2 ring-orange-400/30" />
              <span className="text-[10px] text-[var(--text-secondary)]">PD (high)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-amber-400 ring-2 ring-amber-400/30" />
              <span className="text-[10px] text-[var(--text-secondary)]">Other (medium)</span>
            </div>
          </>
        )}
      </div>

      {/* Stats + Disease toggle */}
      <div className="absolute top-4 right-4 z-20 bg-[rgba(6,15,28,0.88)] backdrop-blur-xl border border-white/[0.08] rounded-xl px-3 py-2 space-y-1.5">
        <div className="flex items-center gap-2">
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            LIVE
          </span>
          <span className="text-[10px] text-[var(--text-secondary)]">{sites.length} farms</span>
        </div>
        {diseaseGeo?.features?.length > 0 && (
          <button
            onClick={() => setShowDisease(!showDisease)}
            className={`flex items-center gap-1.5 text-[10px] px-2 py-1 rounded-lg border transition-all w-full ${
              showDisease
                ? "bg-rose-500/10 text-rose-400 border-rose-500/20"
                : "bg-white/[0.04] text-[var(--text-secondary)] border-white/[0.06]"
            }`}
          >
            <span className={`w-2 h-2 rounded-full ${showDisease ? "bg-rose-500 animate-pulse" : "bg-white/20"}`} />
            {diseaseGeo.features.length} Disease Outbreaks
          </button>
        )}
      </div>

      <MapGL
        initialViewState={{
          longitude: 14,
          latitude: 66,
          zoom: 4.3,
          pitch: 10,
        }}
        style={{ width: "100%", height: "100%" }}
        mapStyle="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"
        interactiveLayerIds={["sites-circle"]}
        onMouseMove={onHover}
        onClick={onClick}
        cursor={hoveredSite ? "pointer" : "grab"}
      >
        <NavigationControl position="bottom-right" />

        {/* Heatmap — real lice pressure from real farm locations */}
        <Source id="heatmap" type="geojson" data={heatmapGeoJson}>
          <Layer
            id="heatmap-layer"
            type="heatmap"
            paint={{
              "heatmap-weight": ["get", "weight"],
              "heatmap-intensity": 0.5,
              "heatmap-radius": 25,
              "heatmap-opacity": 0.45,
              "heatmap-color": [
                "interpolate", ["linear"], ["heatmap-density"],
                0, "rgba(0,0,0,0)",
                0.15, "rgba(0,212,200,0.1)",
                0.3, "rgba(16,185,129,0.2)",
                0.5, "rgba(245,158,11,0.35)",
                0.7, "rgba(244,63,94,0.5)",
                1, "rgba(244,63,94,0.7)",
              ],
            }}
          />
        </Source>

        {/* Farm dots — outer glow */}
        <Source id="sites" type="geojson" data={sitesGeoJson}>
          <Layer
            id="sites-glow"
            type="circle"
            paint={{
              "circle-radius": ["*", ["get", "radius"], 1.8],
              "circle-color": ["rgb", ["get", "color_r"], ["get", "color_g"], ["get", "color_b"]],
              "circle-opacity": 0.15,
              "circle-blur": 0.8,
            }}
          />
          {/* Farm dots — main */}
          <Layer
            id="sites-circle"
            type="circle"
            paint={{
              "circle-radius": ["get", "radius"],
              "circle-color": ["rgb", ["get", "color_r"], ["get", "color_g"], ["get", "color_b"]],
              "circle-opacity": 0.85,
              "circle-stroke-width": 0.8,
              "circle-stroke-color": "rgba(255,255,255,0.15)",
            }}
          />
        </Source>

        {/* Disease outbreak markers (Mattilsynet) */}
        {showDisease && diseaseGeo?.features?.length > 0 && (
          <Source id="disease" type="geojson" data={diseaseGeo}>
            {/* Pulsing outer ring */}
            <Layer
              id="disease-pulse"
              type="circle"
              paint={{
                "circle-radius": 18,
                "circle-color": [
                  "match", ["get", "severity"],
                  "critical", "rgba(244,63,94,0.15)",
                  "high", "rgba(251,146,60,0.12)",
                  "rgba(245,158,11,0.08)",
                ],
                "circle-stroke-width": 1.5,
                "circle-stroke-color": [
                  "match", ["get", "severity"],
                  "critical", "rgba(244,63,94,0.5)",
                  "high", "rgba(251,146,60,0.4)",
                  "rgba(245,158,11,0.3)",
                ],
              }}
            />
            {/* Inner dot */}
            <Layer
              id="disease-dot"
              type="circle"
              paint={{
                "circle-radius": 6,
                "circle-color": [
                  "match", ["get", "severity"],
                  "critical", "#f43f5e",
                  "high", "#fb923c",
                  "#f59e0b",
                ],
                "circle-opacity": 0.95,
                "circle-stroke-width": 2,
                "circle-stroke-color": "rgba(255,255,255,0.5)",
              }}
            />
            {/* Disease label */}
            <Layer
              id="disease-label"
              type="symbol"
              layout={{
                "text-field": ["get", "disease"],
                "text-size": 9,
                "text-offset": [0, -2],
                "text-anchor": "bottom",
                "text-allow-overlap": true,
              }}
              paint={{
                "text-color": "#fff",
                "text-halo-color": "rgba(0,0,0,0.8)",
                "text-halo-width": 1,
              }}
            />
          </Source>
        )}
      </MapGL>

      {/* Glassmorphic tooltip */}
      {hoveredSite && (
        <div
          className="absolute z-30 pointer-events-none"
          style={{ left: Math.min(cursor.x + 14, 600), top: cursor.y - 10 }}
        >
          <div className="bg-[rgba(6,15,28,0.94)] backdrop-blur-2xl border border-white/[0.1] rounded-xl px-3 py-2.5 shadow-[0_8px_32px_rgba(0,0,0,0.5)] min-w-[190px]">
            <p className="text-xs font-semibold text-[var(--text-primary)]">{hoveredSite.name}</p>
            <p className="text-[10px] text-[var(--text-secondary)]">#{hoveredSite.id}</p>
            {hoveredSite.company && (
              <p className="text-[10px] text-ocean-400 font-medium mt-0.5">{hoveredSite.company}</p>
            )}
            <div className="mt-1.5 space-y-0.5 text-[10px]">
              <div className="flex justify-between gap-4">
                <span className="text-[var(--text-secondary)]">Adult female lice</span>
                <span className={`font-mono font-bold ${
                  Number(hoveredSite.lice) >= 0.5 ? "text-rose-400" :
                  Number(hoveredSite.lice) >= 0.3 ? "text-amber-400" :
                  Number(hoveredSite.lice) >= 0.15 ? "text-ocean-400" : "text-emerald-400"
                }`}>{Number(hoveredSite.lice).toFixed(3)}</span>
              </div>
              {hoveredSite.pa && (
                <div className="flex justify-between">
                  <span className="text-[var(--text-secondary)]">Production area</span>
                  <span className="font-mono">PA-{hoveredSite.pa}</span>
                </div>
              )}
              {hoveredSite.temp && (
                <div className="flex justify-between">
                  <span className="text-[var(--text-secondary)]">Sea temp</span>
                  <span className="font-mono">{Number(hoveredSite.temp).toFixed(1)}°C</span>
                </div>
              )}
              <div className="flex justify-between">
                <span className="text-[var(--text-secondary)]">Cleaner fish</span>
                <span>{hoveredSite.cleaner_fish === "true" || hoveredSite.cleaner_fish === true ? "Yes" : "No"}</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
