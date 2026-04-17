"use client";
import { useMemo, useState, useEffect } from "react";
import MapGL, { NavigationControl, Source, Layer, Popup } from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";

/* eslint-disable @typescript-eslint/no-explicit-any */

import { api } from "@/lib/api";
import { useApiError } from "@/lib/useApiError";
import { chartPalette, colors } from "@/lib/design-tokens";
import { useTranslation, formatNumber } from "@/lib/i18n";

const CLUSTER_COLORS = [
  ...chartPalette,
  colors.data.biomass,  // amber
  colors.chart["7"],    // indigo
];

const getCoord = (n: any): [number, number] => [
  n.lon || n.lng || n.longitude || 0,
  n.lat || n.latitude || 0,
];

export default function FarmNetworkMap() {
  const { locale } = useTranslation();
  const handleError = useApiError();
  const [mapData, setMapData] = useState<any>(null);
  const [popup, setPopup] = useState<any>(null);
  const [farmDetail, setFarmDetail] = useState<any>(null);

  useEffect(() => {
    api.farmGraphMapData()
      .then(setMapData)
      .catch(handleError("farm_network_map_data"));
  }, []);

  // Build GeoJSON for nodes
  const nodesGeoJson = useMemo(() => {
    if (!mapData?.nodes) return null;
    const nodes = Array.isArray(mapData.nodes) ? mapData.nodes : [];
    return {
      type: "FeatureCollection" as const,
      features: nodes.map((n: any) => ({
        type: "Feature" as const,
        geometry: { type: "Point" as const, coordinates: getCoord(n) },
        properties: {
          id: n.locality_no || n.id,
          name: n.name || `Farm ${n.locality_no || n.id}`,
          company: n.company || n.owner || "",
          cluster_id: n.cluster_id ?? 0,
          lice: n.lice || n.avg_lice || 0,
          pa: n.pa || n.production_area || 0,
          color: CLUSTER_COLORS[(n.cluster_id ?? 0) % CLUSTER_COLORS.length],
        },
      })),
    };
  }, [mapData]);

  // Build GeoJSON for edges
  const edgesGeoJson = useMemo(() => {
    if (!mapData?.edges || !mapData?.nodes) return null;
    const nodes = Array.isArray(mapData.nodes) ? mapData.nodes : [];
    const nodeMap: Map<any, any> = new Map(nodes.map((n: any) => [n.locality_no || n.id, n]));
    const edges = Array.isArray(mapData.edges) ? mapData.edges : [];

    return {
      type: "FeatureCollection" as const,
      features: edges.filter((e: any) => {
        const src = nodeMap.get(e.source || e.from);
        const tgt = nodeMap.get(e.target || e.to);
        return src && tgt;
      }).map((e: any) => {
        const src = nodeMap.get(e.source || e.from)!;
        const tgt = nodeMap.get(e.target || e.to)!;
        const srcLice = src.lice || src.avg_lice || 0;
        const tgtLice = tgt.lice || tgt.avg_lice || 0;
        const bothHigh = srcLice >= 0.5 && tgtLice >= 0.5;
        const oneHigh = srcLice >= 0.5 || tgtLice >= 0.5;

        return {
          type: "Feature" as const,
          geometry: {
            type: "LineString" as const,
            coordinates: [getCoord(src), getCoord(tgt)],
          },
          properties: {
            weight: e.dispersal_weight || e.weight || 0.5,
            opacity: Math.max(0.1, Math.min(0.8, (e.dispersal_weight || e.weight || 0.5))),
            color: bothHigh ? colors.danger : oneHigh ? colors.warning : colors.success,
          },
        };
      }),
    };
  }, [mapData]);

  const handleNodeClick = async (e: any) => {
    const feature = e.features?.[0];
    if (!feature) return;
    const { id, name, company, lice, pa } = feature.properties;
    setPopup({
      lng: feature.geometry.coordinates[0],
      lat: feature.geometry.coordinates[1],
      name,
      company,
      lice,
      pa,
      id,
    });
    try {
      const detail = await api.farmGraphFarm(id);
      setFarmDetail(detail);
    } catch {
      setFarmDetail(null);
    }
  };

  return (
    <div className="relative w-full h-[500px] rounded-xl overflow-hidden border border-white/[0.06]">
      <MapGL
        initialViewState={{
          longitude: 14.0,
          latitude: 66.5,
          zoom: 5,
        }}
        style={{ width: "100%", height: "100%" }}
        mapStyle="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"
        interactiveLayerIds={["farm-nodes"]}
        onClick={handleNodeClick}
      >
        <NavigationControl position="top-right" />

        {/* Edge lines */}
        {edgesGeoJson && (
          <Source id="farm-edges" type="geojson" data={edgesGeoJson}>
            <Layer
              id="farm-edge-lines"
              type="line"
              paint={{
                "line-color": ["get", "color"],
                "line-opacity": ["get", "opacity"],
                "line-width": 1.5,
              }}
            />
          </Source>
        )}

        {/* Farm nodes */}
        {nodesGeoJson && (
          <Source id="farm-nodes-src" type="geojson" data={nodesGeoJson}>
            <Layer
              id="farm-nodes"
              type="circle"
              paint={{
                "circle-radius": [
                  "interpolate", ["linear"], ["get", "lice"],
                  0, 4, 0.5, 8, 1.0, 12,
                ],
                "circle-color": ["get", "color"],
                "circle-opacity": 0.85,
                "circle-stroke-width": 1,
                "circle-stroke-color": "rgba(255,255,255,0.2)",
              }}
            />
          </Source>
        )}

        {/* Popup */}
        {popup && (
          <Popup
            longitude={popup.lng}
            latitude={popup.lat}
            onClose={() => { setPopup(null); setFarmDetail(null); }}
            closeButton={true}
            closeOnClick={false}
            className="farm-popup"
          >
            <div className="p-2 text-xs space-y-1" style={{ color: colors.text.primary, background: colors.surface["1"], borderRadius: 8, minWidth: 180 }}>
              <div className="font-bold text-sm">{popup.name}</div>
              <div className="text-gray-400">{popup.company} &middot; PA-{popup.pa}</div>
              <div>Lice: <span className={popup.lice >= 0.5 ? "text-red-400" : popup.lice >= 0.2 ? "text-yellow-400" : "text-green-400"}>{formatNumber(Number(popup.lice), locale, 3)}</span></div>
              {farmDetail && (
                <div className="border-t border-white/10 pt-1 mt-1">
                  <div className="text-gray-400 mb-0.5">Neighbors ({farmDetail.neighbors?.length || farmDetail.n_neighbors || 0})</div>
                  {(farmDetail.neighbors || []).slice(0, 4).map((nb: any, i: number) => (
                    <div key={i} className="flex justify-between text-[10px]">
                      <span>{nb.name || `Farm ${nb.locality_no}`}</span>
                      <span className="text-gray-400">{formatNumber(nb.distance_km, locale, 1)}km</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </Popup>
        )}
      </MapGL>

      {/* Legend */}
      <div className="absolute bottom-3 left-3 bg-ocean-950/80 backdrop-blur-lg rounded-lg border border-white/[0.08] p-3 space-y-1.5">
        <div className="text-[10px] font-semibold text-[var(--text-primary)] mb-1">Network Legend</div>
        <div className="flex items-center gap-2 text-[9px] text-[var(--text-secondary)]">
          <div className="w-6 h-0.5 bg-emerald-500 rounded" /> Safe (both &lt;0.5)
        </div>
        <div className="flex items-center gap-2 text-[9px] text-[var(--text-secondary)]">
          <div className="w-6 h-0.5 bg-amber-400 rounded" /> One farm &gt;0.5
        </div>
        <div className="flex items-center gap-2 text-[9px] text-[var(--text-secondary)]">
          <div className="w-6 h-0.5 bg-rose-500 rounded" /> Both farms &gt;0.5
        </div>
        <div className="text-[9px] text-[var(--text-secondary)] mt-1">
          Node size = lice level &middot; Color = cluster
        </div>
      </div>

      {/* Stats badge */}
      {mapData && (
        <div className="absolute top-3 left-3 bg-ocean-950/80 backdrop-blur-lg rounded-lg border border-white/[0.08] px-3 py-2">
          <div className="text-[10px] text-[var(--text-secondary)]">
            {(mapData.nodes || []).length} farms &middot; {(mapData.edges || []).length} connections
          </div>
        </div>
      )}
    </div>
  );
}
