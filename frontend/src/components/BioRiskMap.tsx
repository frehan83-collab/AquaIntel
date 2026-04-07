"use client";
import { useMemo, useState, useCallback, useEffect, useRef } from "react";
import MapGL, { NavigationControl, Source, Layer } from "react-map-gl/maplibre";
import type { MapRef } from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";
import { api } from "@/lib/api";
import { useApiError } from "@/lib/useApiError";

/* eslint-disable @typescript-eslint/no-explicit-any */

/**
 * Unified Biological Risk Map
 * 3 toggleable layers: Lice · Bloom · Disease
 * All on one map with smart filter chips.
 */

interface BioRiskMapProps {
  onSiteClick?: (site: any) => void;
}

type LayerToggle = "lice" | "bloom" | "disease" | "global_farms";
type CountryView = "all" | "norway" | "iceland" | "scotland" | "faroes" | "chile" | "canada";

const LAYER_CONFIG: Record<LayerToggle, { label: string; color: string; activeColor: string; dotColor: string }> = {
  lice:    { label: "Sea Lice",  color: "bg-ocean-500/10 border-ocean-500/20 text-ocean-400",    activeColor: "bg-ocean-500/20 border-ocean-500/40 text-ocean-300",    dotColor: "bg-ocean-400" },
  bloom:   { label: "Algal Bloom", color: "bg-emerald-500/10 border-emerald-500/20 text-emerald-400", activeColor: "bg-emerald-500/20 border-emerald-500/40 text-emerald-300", dotColor: "bg-emerald-400" },
  disease: { label: "Disease",   color: "bg-rose-500/10 border-rose-500/20 text-rose-400",       activeColor: "bg-rose-500/20 border-rose-500/40 text-rose-300",       dotColor: "bg-rose-400" },
  global_farms: { label: "Global Farms", color: "bg-violet-500/10 border-violet-500/20 text-violet-400", activeColor: "bg-violet-500/20 border-violet-500/40 text-violet-300", dotColor: "bg-violet-400" },
};

const VIEW_POSITIONS: Record<CountryView, { longitude: number; latitude: number; zoom: number }> = {
  all:       { longitude: -15, latitude: 55, zoom: 2.8 },
  norway:    { longitude: 14, latitude: 66, zoom: 4.3 },
  iceland:   { longitude: -19, latitude: 65.3, zoom: 5.5 },
  scotland:  { longitude: -5.5, latitude: 57.5, zoom: 5.5 },
  faroes:    { longitude: -6.9, latitude: 62.0, zoom: 7.0 },
  chile:     { longitude: -74, latitude: -46, zoom: 4.5 },
  canada:    { longitude: -127, latitude: 50.5, zoom: 5.5 },
};

export default function BioRiskMap({ onSiteClick }: BioRiskMapProps) {
  const mapRef = useRef<MapRef>(null);
  const handleError = useApiError();
  const [layers, setLayers] = useState<Set<LayerToggle>>(() => new Set<LayerToggle>(["lice", "bloom", "disease", "global_farms"]));
  const [countryView, setCountryView] = useState<CountryView>("all");
  const [sites, setSites] = useState<any[]>([]);
  const [bloomData, setBloomData] = useState<any[]>([]);
  const [diseaseGeo, setDiseaseGeo] = useState<any>(null);
  const [globalFarms, setGlobalFarms] = useState<any>(null);
  const [hovered, setHovered] = useState<any>(null);
  const [cursor, setCursor] = useState({ x: 0, y: 0 });

  // Fly to selected region
  useEffect(() => {
    const pos = VIEW_POSITIONS[countryView];
    mapRef.current?.flyTo({ center: [pos.longitude, pos.latitude], zoom: pos.zoom, duration: 1200 });
  }, [countryView]);

  // Fetch all data sources — GLOBAL layers (all countries)
  useEffect(() => {
    // Norway per-farm lice (BarentsWatch) + Canada DFO lice merged
    Promise.all([
      api.exposureSites().catch(handleError("biorisk_exposure_sites")),
      api.globalLice().catch(handleError("biorisk_global_lice")),
    ]).then(([norwaySites, globalLiceGeo]) => {
      // Merge Norway sites + Canada DFO lice into one array
      const canadaAsLice = (globalLiceGeo?.features || []).map((f: any) => ({
        id: f.properties?.name,
        name: f.properties?.name,
        company: f.properties?.company,
        lat: f.geometry?.coordinates?.[1],
        lng: f.geometry?.coordinates?.[0],
        lice: f.properties?.lice || 0,
        temp: 0,
        country: f.properties?.country,
      }));
      setSites([...(Array.isArray(norwaySites) ? norwaySites : []), ...canadaAsLice]);
    });

    // Global bloom risk (Norway Copernicus + all countries CMEMS)
    api.globalBloomRisk().then((d: any) => {
      const features = d?.features || [];
      // Convert GeoJSON features to bloom data format
      const bloomArr = features.map((f: any) => ({
        locality_name: f.properties?.name,
        latitude: f.geometry?.coordinates?.[1],
        longitude: f.geometry?.coordinates?.[0],
        risk_level: f.properties?.risk_level,
        chl_a: f.properties?.chl_a,
        sst: f.properties?.sst,
        country: f.properties?.country,
      }));
      setBloomData(bloomArr);
    }).catch(handleError("biorisk_bloom"));

    // Global disease outbreaks (Norway Mattilsynet + Chile ISA/SRS + Scotland PD + Canada DFO)
    api.globalDiseaseGeo().then(setDiseaseGeo).catch(handleError("biorisk_disease_geo"));

    // Global farm locations (all 5 countries)
    api.globalFarms().then(setGlobalFarms).catch(handleError("biorisk_global_farms"));
  }, []);

  const toggle = (layer: LayerToggle) => {
    setLayers(prev => {
      const next = new Set(prev);
      if (next.has(layer)) next.delete(layer);
      else next.add(layer);
      return next;
    });
  };

  // ── Lice GeoJSON ───────────────────────────────────────────────────
  const liceGeoJson = useMemo(() => ({
    type: "FeatureCollection" as const,
    features: sites.map(s => ({
      type: "Feature" as const,
      geometry: { type: "Point" as const, coordinates: [s.lng, s.lat] },
      properties: {
        id: s.id, name: s.name, company: s.company, lice: s.lice, temp: s.temp,
        color_r: s.lice >= 0.5 ? 244 : s.lice >= 0.3 ? 245 : s.lice >= 0.15 ? 0 : 16,
        color_g: s.lice >= 0.5 ? 63 : s.lice >= 0.3 ? 158 : s.lice >= 0.15 ? 200 : 185,
        color_b: s.lice >= 0.5 ? 94 : s.lice >= 0.3 ? 11 : s.lice >= 0.15 ? 168 : 129,
        radius: Math.max(3, Math.min(12, s.lice * 20 + 3)),
        weight: Math.min(s.lice / 0.8, 1.5),
        layer: "lice",
      },
    })),
  }), [sites]);

  // ── Bloom GeoJSON ──────────────────────────────────────────────────
  const bloomGeoJson = useMemo(() => ({
    type: "FeatureCollection" as const,
    features: bloomData
      .filter((b: any) => b.latitude && b.longitude)
      .map((b: any) => ({
        type: "Feature" as const,
        geometry: { type: "Point" as const, coordinates: [b.longitude, b.latitude] },
        properties: {
          name: b.locality_name || b.name || `#${b.locality_no || ""}`,
          country: b.country || "Norway",
          risk_level: b.risk_level,
          chl_a: b.chl_a || 0,
          sst: b.sst || 0,
          color_r: b.risk_level === "CRITICAL" ? 239 : b.risk_level === "HIGH" ? 249 : b.risk_level === "ELEVATED" ? 245 : b.risk_level === "monitoring" ? 139 : 16,
          color_g: b.risk_level === "CRITICAL" ? 68 : b.risk_level === "HIGH" ? 115 : b.risk_level === "ELEVATED" ? 158 : b.risk_level === "monitoring" ? 92 : 185,
          color_b: b.risk_level === "CRITICAL" ? 68 : b.risk_level === "HIGH" ? 22 : b.risk_level === "ELEVATED" ? 11 : b.risk_level === "monitoring" ? 246 : 129,
          radius: Math.max(6, Math.min(14, (b.chl_a || 0) * 2.5 + 6)),
          layer: "bloom",
        },
      })),
  }), [bloomData]);

  // ── Hover handler ──────────────────────────────────────────────────
  const onHover = useCallback((e: any) => {
    const feature = e.features?.[0];
    if (feature) {
      setHovered(feature.properties);
      setCursor({ x: e.point.x, y: e.point.y });
    } else {
      setHovered(null);
    }
  }, []);

  // Stats
  const liceAbove = sites.filter(s => s.lice > 0.5).length;
  const bloomHigh = bloomData.filter((b: any) => b.risk_level === "HIGH" || b.risk_level === "CRITICAL").length;
  const diseaseCount = diseaseGeo?.features?.length || 0;
  const globalFarmsCount = globalFarms?.features?.length || 0;

  return (
    <div className="relative rounded-2xl overflow-hidden border border-white/[0.08] shadow-[0_8px_32px_rgba(0,0,0,0.3)]" style={{ height: 580 }}>
      {/* Gradient overlay */}
      <div className="absolute inset-0 pointer-events-none z-10 bg-gradient-to-b from-[rgba(6,15,28,0.25)] via-transparent to-[rgba(6,15,28,0.4)]" />

      {/* Country + Layer toggles */}
      <div className="absolute top-4 left-4 z-20 bg-[rgba(6,15,28,0.9)] backdrop-blur-xl border border-white/[0.08] rounded-xl p-2 space-y-1.5">
        {/* Country view */}
        <p className="text-[9px] font-semibold text-[var(--text-secondary)] uppercase tracking-wider px-1">Region</p>
        <div className="flex flex-wrap gap-1">
          {(["all", "norway", "iceland", "scotland", "faroes", "chile", "canada"] as CountryView[]).map(cv => {
            const labels: Record<string, string> = { all: "All", norway: "\ud83c\uddf3\ud83c\uddf4", iceland: "\ud83c\uddee\ud83c\uddf8", scotland: "\ud83c\udff4\udb40\udc67\udb40\udc62\udb40\udc73\udb40\udc63\udb40\udc74\udb40\udc7f", faroes: "\ud83c\uddeb\ud83c\uddf4", chile: "\ud83c\udde8\ud83c\uddf1", canada: "\ud83c\udde8\ud83c\udde6" };
            return (
              <button key={cv} onClick={() => setCountryView(cv)}
                className={`px-2 py-1 rounded-md text-[9px] font-medium border transition-all ${
                  countryView === cv
                    ? "bg-ocean-500/20 border-ocean-500/40 text-ocean-300"
                    : "bg-white/[0.02] border-white/[0.04] text-[var(--text-secondary)] hover:bg-white/[0.05]"
                }`}>
                {labels[cv] || cv}
              </button>
            );
          })}
        </div>
        <div className="w-full h-px bg-white/[0.06]" />
        <p className="text-[9px] font-semibold text-[var(--text-secondary)] uppercase tracking-wider px-1">Layers</p>
        {(Object.entries(LAYER_CONFIG) as [LayerToggle, typeof LAYER_CONFIG[LayerToggle]][]).map(([key, cfg]) => {
          const active = layers.has(key);
          const count = key === "lice" ? liceAbove : key === "bloom" ? bloomHigh : key === "global_farms" ? globalFarmsCount : diseaseCount;
          return (
            <button
              key={key}
              onClick={() => toggle(key)}
              className={`flex items-center gap-2 w-full text-left px-2 py-1.5 rounded-lg border text-[10px] font-medium transition-all ${
                active ? cfg.activeColor : "bg-white/[0.02] border-white/[0.04] text-[var(--text-secondary)] opacity-50"
              }`}
            >
              <span className={`w-2 h-2 rounded-full ${active ? cfg.dotColor : "bg-white/20"} ${active && key === "disease" ? "animate-pulse" : ""}`} />
              {cfg.label}
              {count > 0 && active && (
                <span className="ml-auto text-[9px] font-mono">{count}</span>
              )}
            </button>
          );
        })}
      </div>

      {/* Stats badge */}
      <div className="absolute top-4 right-4 z-20 bg-[rgba(6,15,28,0.9)] backdrop-blur-xl border border-white/[0.08] rounded-xl px-3 py-2 space-y-1">
        <div className="flex items-center gap-2">
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">LIVE</span>
          <span className="text-[10px] text-[var(--text-secondary)]">{sites.length} lice sites</span>
        </div>
        {layers.has("lice") && liceAbove > 0 && (
          <p className="text-[9px] text-rose-400">{liceAbove} above 0.5 lice limit</p>
        )}
        {layers.has("bloom") && bloomHigh > 0 && (
          <p className="text-[9px] text-amber-400">{bloomHigh} HIGH/CRITICAL bloom</p>
        )}
        {layers.has("disease") && diseaseCount > 0 && (
          <p className="text-[9px] text-rose-400 animate-pulse">{diseaseCount} disease outbreaks</p>
        )}
        {layers.has("global_farms") && globalFarmsCount > 0 && (
          <p className="text-[9px] text-violet-400">{globalFarmsCount} global farm regions</p>
        )}
      </div>

      {/* Legend */}
      <div className="absolute bottom-4 left-4 z-20 bg-[rgba(6,15,28,0.9)] backdrop-blur-xl border border-white/[0.08] rounded-xl px-3 py-2 space-y-1">
        {layers.has("lice") && (
          <>
            <p className="text-[9px] font-semibold text-ocean-400 uppercase">Lice</p>
            <div className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-emerald-500" /><span className="text-[9px] text-[var(--text-secondary)]">&lt;0.15</span></div>
            <div className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-amber-500" /><span className="text-[9px] text-[var(--text-secondary)]">0.3-0.5</span></div>
            <div className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-rose-500" /><span className="text-[9px] text-[var(--text-secondary)]">&gt;0.5</span></div>
          </>
        )}
        {layers.has("bloom") && (
          <>
            <p className="text-[9px] font-semibold text-emerald-400 uppercase mt-1">Bloom</p>
            <div className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-emerald-500" /><span className="text-[9px] text-[var(--text-secondary)]">LOW</span></div>
            <div className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-amber-500" /><span className="text-[9px] text-[var(--text-secondary)]">ELEVATED</span></div>
            <div className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-orange-500" /><span className="text-[9px] text-[var(--text-secondary)]">HIGH/CRIT</span></div>
            <div className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-violet-500" /><span className="text-[9px] text-[var(--text-secondary)]">Monitoring</span></div>
          </>
        )}
        {layers.has("disease") && (
          <>
            <p className="text-[9px] font-semibold text-rose-400 uppercase mt-1">Disease</p>
            <div className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-rose-500" /><span className="text-[9px] text-[var(--text-secondary)]">ISA/IHN</span></div>
            <div className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-orange-400" /><span className="text-[9px] text-[var(--text-secondary)]">PD/SRS</span></div>
            <div className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-emerald-500" /><span className="text-[9px] text-[var(--text-secondary)]">Clear/Vacc.</span></div>
          </>
        )}
        {layers.has("global_farms") && (
          <>
            <p className="text-[9px] font-semibold text-violet-400 uppercase mt-1">Global Farms</p>
            <div className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-violet-500 ring-1 ring-violet-400/30" /><span className="text-[9px] text-[var(--text-secondary)]">Farm region</span></div>
            <div className="text-[8px] text-[var(--text-secondary)] italic mt-0.5">IS + SCO + FO + CL</div>
          </>
        )}
      </div>

      <MapGL
        ref={mapRef}
        initialViewState={{ ...VIEW_POSITIONS[countryView], pitch: 10 }}
        style={{ width: "100%", height: "100%" }}
        mapStyle="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"
        interactiveLayerIds={[
          ...(layers.has("lice") ? ["lice-circle"] : []),
          ...(layers.has("bloom") ? ["bloom-circle"] : []),
          ...(layers.has("disease") ? ["disease-dot"] : []),
          ...(layers.has("global_farms") ? ["gfarms-circle"] : []),
        ]}
        onMouseMove={onHover}
        cursor={hovered ? "pointer" : "grab"}
      >
        <NavigationControl position="bottom-right" />

        {/* ── Lice Layer ── */}
        {layers.has("lice") && (
          <Source id="lice-src" type="geojson" data={liceGeoJson}>
            <Layer id="lice-heat" type="heatmap" paint={{
              "heatmap-weight": ["get", "weight"],
              "heatmap-intensity": 0.4,
              "heatmap-radius": 20,
              "heatmap-opacity": 0.35,
              "heatmap-color": [
                "interpolate", ["linear"], ["heatmap-density"],
                0, "rgba(0,0,0,0)", 0.2, "rgba(0,212,200,0.1)",
                0.5, "rgba(245,158,11,0.3)", 1, "rgba(244,63,94,0.5)",
              ],
            }} />
            <Layer id="lice-circle" type="circle" paint={{
              "circle-radius": ["get", "radius"],
              "circle-color": ["rgb", ["get", "color_r"], ["get", "color_g"], ["get", "color_b"]],
              "circle-opacity": 0.8,
              "circle-stroke-width": 0.5,
              "circle-stroke-color": "rgba(255,255,255,0.1)",
            }} />
          </Source>
        )}

        {/* ── Bloom Layer ── */}
        {layers.has("bloom") && bloomGeoJson.features.length > 0 && (
          <Source id="bloom-src" type="geojson" data={bloomGeoJson}>
            <Layer id="bloom-circle" type="circle" paint={{
              "circle-radius": ["get", "radius"],
              "circle-color": ["rgb", ["get", "color_r"], ["get", "color_g"], ["get", "color_b"]],
              "circle-opacity": 0.6,
              "circle-stroke-width": 1,
              "circle-stroke-color": "rgba(255,255,255,0.15)",
            }} />
          </Source>
        )}

        {/* ── Disease Layer ── */}
        {layers.has("disease") && diseaseGeo?.features?.length > 0 && (
          <Source id="disease-src" type="geojson" data={diseaseGeo}>
            <Layer id="disease-pulse" type="circle" paint={{
              "circle-radius": ["interpolate", ["linear"], ["zoom"], 2, 10, 5, 18, 8, 24],
              "circle-color": ["match", ["get", "severity"],
                "critical", "rgba(244,63,94,0.15)",
                "high", "rgba(251,146,60,0.12)",
                "medium", "rgba(245,158,11,0.10)",
                "low", "rgba(16,185,129,0.08)",
                "rgba(139,92,246,0.06)"],
              "circle-stroke-width": 1.5,
              "circle-stroke-color": ["match", ["get", "severity"],
                "critical", "rgba(244,63,94,0.5)",
                "high", "rgba(251,146,60,0.4)",
                "medium", "rgba(245,158,11,0.3)",
                "low", "rgba(16,185,129,0.25)",
                "rgba(139,92,246,0.2)"],
            }} />
            <Layer id="disease-dot" type="circle" paint={{
              "circle-radius": ["interpolate", ["linear"], ["zoom"], 2, 3, 5, 6, 8, 8],
              "circle-color": ["match", ["get", "severity"],
                "critical", "#f43f5e",
                "high", "#fb923c",
                "medium", "#f59e0b",
                "low", "#10b981",
                "#8b5cf6"],
              "circle-opacity": 0.9,
              "circle-stroke-width": 1.5,
              "circle-stroke-color": "rgba(255,255,255,0.4)",
            }} />
            <Layer id="disease-label" type="symbol" layout={{
              "text-field": ["get", "disease"],
              "text-size": 9,
              "text-offset": [0, -2],
              "text-anchor": "bottom",
              "text-allow-overlap": true,
            }} paint={{
              "text-color": "#fff",
              "text-halo-color": "rgba(0,0,0,0.8)",
              "text-halo-width": 1,
            }} />
          </Source>
        )}

        {/* ── Global Farms Layer (Iceland + Scotland + Faroes + Chile) ── */}
        {layers.has("global_farms") && globalFarms?.features?.length > 0 && (
          <Source id="gfarms-src" type="geojson" data={globalFarms}>
            <Layer id="gfarms-ring" type="circle" paint={{
              "circle-radius": ["interpolate", ["linear"], ["zoom"], 2, 8, 5, 16, 8, 24],
              "circle-color": "rgba(139,92,246,0.12)",
              "circle-stroke-width": 1.5,
              "circle-stroke-color": "rgba(139,92,246,0.5)",
            }} />
            <Layer id="gfarms-circle" type="circle" paint={{
              "circle-radius": ["interpolate", ["linear"], ["zoom"], 2, 3, 5, 7, 8, 10],
              "circle-color": "#8b5cf6",
              "circle-opacity": 0.9,
              "circle-stroke-width": 2,
              "circle-stroke-color": "rgba(255,255,255,0.5)",
            }} />
            <Layer id="gfarms-label" type="symbol" layout={{
              "text-field": ["concat", ["get", "name"], " (", ["get", "country"], ")"],
              "text-size": ["interpolate", ["linear"], ["zoom"], 3, 0, 5, 9, 8, 11],
              "text-offset": [0, -2],
              "text-anchor": "bottom",
              "text-allow-overlap": false,
            }} paint={{
              "text-color": "#c4b5fd",
              "text-halo-color": "rgba(0,0,0,0.8)",
              "text-halo-width": 1,
            }} />
          </Source>
        )}
      </MapGL>

      {/* Tooltip */}
      {hovered && (
        <div className="absolute z-30 pointer-events-none"
          style={{ left: Math.min(cursor.x + 14, 600), top: cursor.y - 10 }}>
          <div className="bg-[rgba(6,15,28,0.94)] backdrop-blur-2xl border border-white/[0.1] rounded-xl px-3 py-2.5 shadow-[0_8px_32px_rgba(0,0,0,0.5)] min-w-[180px]">
            <p className="text-xs font-semibold text-[var(--text-primary)]">{hovered.name}</p>
            {hovered.layer === "lice" && (
              <>
                {hovered.company && <p className="text-[10px] text-ocean-400">{hovered.company}</p>}
                <p className="text-[10px] text-[var(--text-secondary)]">
                  Lice: <span className={hovered.lice >= 0.5 ? "text-rose-400 font-bold" : "text-emerald-400"}>{Number(hovered.lice).toFixed(3)}</span>
                  {hovered.temp ? ` · ${Number(hovered.temp).toFixed(1)}°C` : ""}
                </p>
              </>
            )}
            {hovered.layer === "bloom" && (
              <>
                {hovered.country && <p className="text-[10px] text-violet-400">{hovered.country}</p>}
                <p className="text-[10px] text-[var(--text-secondary)]">
                  Bloom: <span className={
                    hovered.risk_level === "CRITICAL" ? "text-rose-400 font-bold" :
                    hovered.risk_level === "HIGH" ? "text-orange-400 font-bold" :
                    hovered.risk_level === "ELEVATED" ? "text-amber-400 font-bold" : "text-emerald-400"
                  }>{hovered.risk_level}</span>
                  {hovered.chl_a ? ` · Chl-a ${Number(hovered.chl_a).toFixed(1)} mg/m³` : ""}
                  {hovered.sst ? ` · SST ${Number(hovered.sst).toFixed(1)}°C` : ""}
                </p>
              </>
            )}
            {hovered.disease && !hovered.layer && (
              <>
                {hovered.country && <p className="text-[10px] text-violet-400">{hovered.country}</p>}
                <p className="text-[10px] text-rose-400 font-semibold">
                  {hovered.disease}{hovered.subtype ? ` (${hovered.subtype})` : ""}
                </p>
                {hovered.status && <p className="text-[9px] text-[var(--text-secondary)]">Status: {hovered.status}</p>}
              </>
            )}
            {hovered.country && !hovered.layer && (
              <>
                <p className="text-[10px] text-violet-400">
                  {hovered.company || hovered.country}
                  {hovered.region ? ` · ${hovered.region}` : ""}
                  {hovered.n_sites ? ` · ${hovered.n_sites} sites` : ""}
                </p>
                {hovered.species && <p className="text-[10px] text-[var(--text-secondary)]">{hovered.species}</p>}
                {hovered.sst && (
                  <p className="text-[10px] text-[var(--text-secondary)]">
                    SST: {Number(hovered.sst).toFixed(1)}°C
                    {hovered.air_temp ? ` · Air: ${Number(hovered.air_temp).toFixed(1)}°C` : ""}
                    {hovered.wind_ms ? ` · Wind: ${Number(hovered.wind_ms).toFixed(1)} m/s` : ""}
                  </p>
                )}
                {hovered.bloom_risk && hovered.bloom_risk !== "unknown" && (
                  <p className={`text-[10px] font-medium ${
                    hovered.bloom_risk === "CRITICAL" ? "text-rose-400" :
                    hovered.bloom_risk === "HIGH" ? "text-orange-400" :
                    hovered.bloom_risk === "ELEVATED" ? "text-amber-400" : "text-emerald-400"
                  }`}>Bloom: {hovered.bloom_risk}</p>
                )}
                {hovered.pd_status === "endemic" && (
                  <p className="text-[9px] text-orange-400">PD endemic</p>
                )}
                {hovered.isa_vaccinated && (
                  <p className="text-[9px] text-emerald-400">ISA vaccinated</p>
                )}
                {hovered.disruption_level && hovered.disruption_level !== "normal" && hovered.disruption_level !== "unknown" && (
                  <p className="text-[9px] text-amber-400">Disruption: {hovered.disruption_level}</p>
                )}
                {hovered.lice_data_available === false && (
                  <p className="text-[9px] text-[var(--text-secondary)] italic">No public lice data</p>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
