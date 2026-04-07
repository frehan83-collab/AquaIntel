/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";

import { useEffect, useState, useMemo } from "react";
import { motion } from "framer-motion";
import {
  Satellite, RefreshCw, Eye, AlertTriangle, Cloud, Waves,
  Activity, CheckCircle, Zap, BarChart3, Leaf, Thermometer,
  Database, Radio, Globe, MapPin, TrendingUp, Info,
} from "lucide-react";
import GlassCard from "@/components/GlassCard";
import KPICard from "@/components/KPICard";
import { OcButton } from "@/components/ui/Button";
import InteractiveChart, { DataPoint } from "@/components/InteractiveChart";
import { api } from "@/lib/api";
import { useApiError } from "@/lib/useApiError";
import { exportToCSV } from "@/lib/export";
import ErrorBoundary from "@/components/ErrorBoundary";
import { useTranslation } from "@/lib/i18n";

/* ─── Anomaly styling ───────────────────────────────────────────────── */

const ANOMALY_ICONS: Record<string, any> = {
  possible_bloom: Leaf,
  surface_disturbance: Waves,
  surface_anomaly: AlertTriangle,
};

const ANOMALY_COLORS: Record<string, string> = {
  possible_bloom: "text-emerald-400",
  surface_disturbance: "text-amber-400",
  surface_anomaly: "text-rose-400",
};

/* ─── Data source definitions ───────────────────────────────────────── */

interface DataSourceDef {
  name: string;
  provider: string;
  status: "active" | "pending" | "degraded";
  description: string;
  resolution: string;
  icon: any;
}

const DATA_SOURCES: DataSourceDef[] = [
  {
    name: "MET.no Ocean Forecast",
    provider: "Norwegian Meteorological Institute",
    status: "active",
    description: "Sea surface temperature forecasts and historical observations for all 13 production areas",
    resolution: "~800m grid, hourly updates",
    icon: Thermometer,
  },
  {
    name: "Copernicus CMEMS Chlorophyll-a",
    provider: "EU Copernicus Marine Service",
    status: "active",
    description: "Satellite-derived chlorophyll concentration for bloom risk monitoring via bloom engine",
    resolution: "~1km grid, daily composites",
    icon: Leaf,
  },
  {
    name: "BarentsWatch Farm Registry",
    provider: "Norwegian Coastal Administration",
    status: "active",
    description: "Licensed farm locations with lat/lon coordinates, production areas, and ownership data",
    resolution: "Per-farm point data",
    icon: MapPin,
  },
  {
    name: "Sentinel-2 L2A Imagery",
    provider: "Copernicus Data Space Ecosystem (CDSE)",
    status: "pending",
    description: "10m multispectral imagery for direct visual confirmation of blooms, harvest activity, and surface anomalies",
    resolution: "10m (RGB+NIR), 5-day revisit",
    icon: Satellite,
  },
  {
    name: "Climate Risk Engine",
    provider: "OpenClaw composite (MET.no + CMEMS + Regime)",
    status: "active",
    description: "Per-PA climate risk scores combining SST stress, bloom risk, and lice pressure",
    resolution: "Per production area",
    icon: Activity,
  },
];

/* ─── Helper: risk level color ──────────────────────────────────────── */

function riskColor(level: string): string {
  const l = (level || "").toUpperCase();
  if (l === "HIGH" || l === "CRITICAL") return "text-rose-400";
  if (l === "ELEVATED" || l === "MODERATE") return "text-amber-400";
  return "text-emerald-400";
}

function riskBg(level: string): string {
  const l = (level || "").toUpperCase();
  if (l === "HIGH" || l === "CRITICAL") return "bg-rose-500/10 border-rose-500/20";
  if (l === "ELEVATED" || l === "MODERATE") return "bg-amber-500/10 border-amber-500/20";
  return "bg-emerald-500/10 border-emerald-500/20";
}

/* ─── Page ──────────────────────────────────────────────────────────── */

export default function SatellitePage() {
  const { t } = useTranslation();
  const handleError = useApiError();
  const [status, setStatus] = useState<any>(null);
  const [snapshot, setSnapshot] = useState<any>(null);
  const [products, setProducts] = useState<any[]>([]);
  const [scanning, setScanning] = useState(false);
  const [loading, setLoading] = useState(true);

  // New data sources
  const [climateData, setClimateData] = useState<any>(null);
  const [chlorophyllData, setChlorophyllData] = useState<any>(null);
  const [bloomRiskData, setBloomRiskData] = useState<any>(null);
  const [sstProjections, setSstProjections] = useState<any>(null);
  const [selectedPa, setSelectedPa] = useState(3);

  const load = async () => {
    setLoading(true);
    const [s, p, climate, chl, bloom] = await Promise.allSettled([
      api.satelliteStatus(),
      api.satelliteProducts(),
      api.climateRiskScores(),
      api.bloomChlorophyll(30),
      api.bloomRisk(),
    ]);
    if (s.status === "fulfilled") setStatus(s.value);
    if (p.status === "fulfilled") setProducts(p.value || []);
    if (climate.status === "fulfilled") setClimateData(climate.value);
    if (chl.status === "fulfilled") setChlorophyllData(chl.value);
    if (bloom.status === "fulfilled") setBloomRiskData(bloom.value);
    setLoading(false);
  };

  // Load SST projections when selected PA changes
  useEffect(() => {
    api.climateProjections(selectedPa, 3).then(setSstProjections).catch(handleError("satellite_sst_projections"));
  }, [selectedPa]);

  const runScan = async () => {
    setScanning(true);
    try {
      const result = await api.satelliteScan(50);
      setSnapshot(result);
    } catch (e) { handleError("satellite_scan")(e); }
    setScanning(false);
  };

  useEffect(() => { load(); }, []);

  const readings = snapshot?.readings || [];
  const anomalies = snapshot?.anomalies || [];
  const summary = snapshot?.summary || {};

  // ── Derived: SST chart data from climate PA scores ──────────────
  const sstChartData: DataPoint[] = useMemo(() => {
    if (!climateData?.pa_scores) return [];
    return climateData.pa_scores
      .filter((s: any) => s.sst_current_c != null)
      .map((s: any) => ({
        x: s.pa,
        y: s.sst_current_c,
        label: `PA ${s.pa}`,
      }));
  }, [climateData]);

  // ── Derived: SST projections chart ──────────────────────────────
  const sstProjectionChart: DataPoint[] = useMemo(() => {
    if (!sstProjections?.historical) return [];
    return sstProjections.historical
      .slice(-12)
      .map((h: any, i: number) => ({
        x: i,
        y: h.temperature_c ?? h.temp_c ?? h.sst ?? 0,
        label: h.month || h.date || `${i + 1}`,
      }));
  }, [sstProjections]);

  // ── Derived: Chlorophyll time-series chart ──────────────────────
  const chlChartData: DataPoint[] = useMemo(() => {
    if (!chlorophyllData?.items) return [];
    // Group by date, average the chl_a values
    const byDate: Record<string, number[]> = {};
    for (const r of chlorophyllData.items) {
      const d = (r.date || "").slice(0, 10);
      if (!d) continue;
      if (!byDate[d]) byDate[d] = [];
      byDate[d].push(r.chl_a_mg_m3 || 0);
    }
    const sorted = Object.entries(byDate).sort(([a], [b]) => a.localeCompare(b));
    return sorted.map(([date, vals], i) => ({
      x: i,
      y: parseFloat((vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(2)),
      label: date.slice(5), // MM-DD
    }));
  }, [chlorophyllData]);

  // ── Derived: Farm cluster analysis from bloom risk ─────────────
  const farmClusters = useMemo(() => {
    if (!bloomRiskData?.items) return { total: 0, clusters: [], riskDistribution: { HIGH: 0, ELEVATED: 0, LOW: 0 } };
    const items = bloomRiskData.items;
    // Count by risk level
    const dist: Record<string, number> = { HIGH: 0, CRITICAL: 0, ELEVATED: 0, MODERATE: 0, LOW: 0 };
    for (const item of items) {
      const level = (item.risk_level || "LOW").toUpperCase();
      if (level in dist) dist[level]++;
      else dist["LOW"]++;
    }
    // Cluster by PA (production area from latitude bands)
    // Group farms that are within ~0.5 degree of each other
    const byOwner: Record<string, { count: number; avgRisk: number; risks: number[] }> = {};
    for (const item of items) {
      const owner = item.owner_company || "Unknown";
      if (!byOwner[owner]) byOwner[owner] = { count: 0, avgRisk: 0, risks: [] };
      byOwner[owner].count++;
      byOwner[owner].risks.push(item.risk_score || 0);
    }
    const clusters = Object.entries(byOwner)
      .map(([name, data]) => ({
        name,
        count: data.count,
        avgRisk: data.risks.length
          ? parseFloat((data.risks.reduce((a, b) => a + b, 0) / data.risks.length).toFixed(1))
          : 0,
      }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 10);

    return {
      total: items.length,
      clusters,
      riskDistribution: {
        HIGH: (dist.HIGH || 0) + (dist.CRITICAL || 0),
        ELEVATED: (dist.ELEVATED || 0) + (dist.MODERATE || 0),
        LOW: dist.LOW || 0,
      },
    };
  }, [bloomRiskData]);

  // ── Derived: Climate KPIs ──────────────────────────────────────
  const climateKpis = useMemo(() => {
    if (!climateData?.summary) return null;
    const s = climateData.summary;
    return {
      avgRisk: s.average_risk_score ?? 0,
      highRiskPAs: s.high_risk_count ?? 0,
      trend: s.trend ?? "stable",
      highestPa: climateData.pa_scores?.[0]?.name || "N/A",
    };
  }, [climateData]);

  return (
    <ErrorBoundary fallbackTitle="Satellite Intelligence error">
    <div className="space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] flex items-center gap-3">
            <Satellite className="w-6 h-6 text-violet-400" />
            {t("nav.satellite_intel")}
          </h1>
          <p className="text-sm text-[var(--text-secondary)] mt-1">
            Ocean monitoring &mdash; SST, chlorophyll-a, bloom risk, farm cluster analysis
          </p>
        </div>
        <div className="flex items-center gap-2">
          {readings.length > 0 && (
            <OcButton variant="ghost" size="sm"
              onClick={() => exportToCSV(readings, "satellite_readings")}
              leftIcon={<BarChart3 className="w-3.5 h-3.5" />}>Export</OcButton>
          )}
          <OcButton variant="primary" size="sm" onClick={runScan} loading={scanning}
            leftIcon={<Eye className="w-3.5 h-3.5" />}>Scan Farms</OcButton>
          <OcButton variant="secondary" size="sm" onClick={load} loading={loading}
            leftIcon={<RefreshCw className="w-3.5 h-3.5" />}>Refresh</OcButton>
        </div>
      </motion.div>

      {/* ── Live KPIs (always visible, from climate + bloom data) ─── */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <KPICard label="Avg Climate Risk"
          value={climateKpis ? `${climateKpis.avgRisk}` : loading ? "..." : "N/A"}
          delta={climateKpis?.trend === "worsening" ? "Worsening" : climateKpis?.trend === "improving" ? "Improving" : "Stable"}
          deltaType={climateKpis?.trend === "worsening" ? "negative" : climateKpis?.trend === "improving" ? "positive" : "neutral"}
          icon={Thermometer} delay={0} />
        <KPICard label="High-Risk PAs"
          value={climateKpis?.highRiskPAs ?? (loading ? "..." : 0)}
          delta={climateKpis?.highRiskPAs && climateKpis.highRiskPAs > 3 ? "Elevated" : "Normal"}
          deltaType={climateKpis?.highRiskPAs && climateKpis.highRiskPAs > 3 ? "negative" : "positive"}
          icon={AlertTriangle} delay={0.03} />
        <KPICard label="Farms Monitored"
          value={farmClusters.total || (loading ? "..." : 0)}
          icon={MapPin} delay={0.06} />
        <KPICard label="High Bloom Risk"
          value={farmClusters.riskDistribution.HIGH}
          delta={farmClusters.riskDistribution.HIGH > 5 ? "Action needed" : "Acceptable"}
          deltaType={farmClusters.riskDistribution.HIGH > 5 ? "negative" : "positive"}
          icon={Leaf} delay={0.09} />
        <KPICard label="Chlorophyll Readings"
          value={chlorophyllData?.items?.length ?? (loading ? "..." : 0)}
          icon={Database} delay={0.12} />
      </div>

      {/* ── Sea Surface Temperature (SST) Visualization ──────────── */}
      <GlassCard delay={0.1} accent="ocean">
        <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-4 flex items-center gap-2">
          <Thermometer className="w-4 h-4 text-cyan-400" />
          Sea Surface Temperature by Production Area
          <span className="text-[10px] font-normal text-[var(--text-secondary)] ml-auto">
            Source: MET.no Ocean Forecast + Climate Risk Engine
          </span>
        </h3>
        {sstChartData.length > 0 ? (
          <div className="space-y-4">
            <InteractiveChart
              data={sstChartData}
              height={180}
              title="Current SST across Production Areas"
              unit="C"
              color="#06b6d4"
              fillColor="rgba(6, 182, 212, 0.1)"
              showArea
            />
            {/* PA SST detail grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-7 gap-2">
              {(climateData?.pa_scores || []).slice(0, 13).map((pa: any) => (
                <div key={pa.pa}
                  className={`p-2 rounded-lg border cursor-pointer transition-all ${
                    selectedPa === pa.pa
                      ? "border-cyan-400/40 bg-cyan-500/[0.08]"
                      : "border-white/[0.06] bg-white/[0.02] hover:border-white/[0.12]"
                  }`}
                  onClick={() => setSelectedPa(pa.pa)}>
                  <div className="text-[10px] text-[var(--text-secondary)]">PA {pa.pa}</div>
                  <div className="text-sm font-bold text-[var(--text-primary)]">
                    {pa.sst_current_c != null ? `${pa.sst_current_c.toFixed(1)}°C` : "N/A"}
                  </div>
                  <div className={`text-[9px] ${riskColor(pa.risk_level)}`}>
                    {pa.risk_level}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="text-center py-8 text-[var(--text-secondary)] text-sm">
            {loading ? "Loading SST data..." : "No SST data available"}
          </div>
        )}
      </GlassCard>

      {/* ── SST Projections for Selected PA ──────────────────────── */}
      {sstProjectionChart.length > 0 && (
        <GlassCard delay={0.15} accent="ocean">
          <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-cyan-400" />
            SST Trend &mdash; PA {selectedPa} ({sstProjections?.pa_name || ""})
            <span className="text-[10px] font-normal text-[var(--text-secondary)] ml-auto">
              {sstProjections?.trend_direction === "warming"
                ? `+${sstProjections.trend_c_per_year?.toFixed(2)}°C/yr`
                : sstProjections?.trend_direction === "cooling"
                ? `${sstProjections.trend_c_per_year?.toFixed(2)}°C/yr`
                : "Stable trend"}
            </span>
          </h3>
          <InteractiveChart
            data={sstProjectionChart}
            height={160}
            title={`Historical SST (last 12 months)`}
            unit="C"
            color="#22d3ee"
            fillColor="rgba(34, 211, 238, 0.08)"
            showArea
          />
          {sstProjections?.projections && sstProjections.projections.length > 0 && (
            <div className="mt-3 flex items-center gap-4 text-[10px] text-[var(--text-secondary)]">
              <span>Projected:</span>
              {sstProjections.projections.map((p: any) => (
                <span key={p.year} className="text-cyan-400 font-mono">
                  {p.year}: {p.projected_sst_c?.toFixed(1)}°C
                </span>
              ))}
              <span className="ml-auto opacity-60">Optimal: {sstProjections.optimal_sst_c}°C</span>
            </div>
          )}
        </GlassCard>
      )}

      {/* ── Chlorophyll-a Density ────────────────────────────────── */}
      <GlassCard delay={0.2} accent="emerald">
        <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-4 flex items-center gap-2">
          <Leaf className="w-4 h-4 text-emerald-400" />
          Chlorophyll-a Concentration (30-Day Trend)
          <span className="text-[10px] font-normal text-[var(--text-secondary)] ml-auto">
            Source: Copernicus CMEMS via Bloom Engine
          </span>
        </h3>
        {chlChartData.length > 0 ? (
          <div className="space-y-3">
            <InteractiveChart
              data={chlChartData}
              height={160}
              title="Average Chlorophyll-a"
              unit="mg/m3"
              color="#10b981"
              fillColor="rgba(16, 185, 129, 0.1)"
              showArea
            />
            <div className="flex items-center gap-6 text-[10px] text-[var(--text-secondary)]">
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-emerald-400" />
                &lt; 4 mg/m&sup3; = Normal
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-amber-400" />
                4-8 mg/m&sup3; = Elevated
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-rose-400" />
                &gt; 8 mg/m&sup3; = Bloom likely
              </span>
            </div>
          </div>
        ) : (
          <div className="text-center py-8 text-[var(--text-secondary)] text-sm">
            {loading ? "Loading chlorophyll data..." : "No chlorophyll readings available for the last 30 days"}
          </div>
        )}
      </GlassCard>

      {/* ── Farm Cluster Analysis ────────────────────────────────── */}
      <GlassCard delay={0.25} accent="violet">
        <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-4 flex items-center gap-2">
          <Globe className="w-4 h-4 text-violet-400" />
          Farm Cluster Analysis
          <span className="text-[10px] font-normal text-[var(--text-secondary)] ml-auto">
            {farmClusters.total} farms across {farmClusters.clusters.length} operators
          </span>
        </h3>
        {farmClusters.total > 0 ? (
          <div className="space-y-4">
            {/* Risk distribution bar */}
            <div>
              <div className="text-[10px] text-[var(--text-secondary)] mb-2 uppercase tracking-wider">
                Bloom Risk Distribution
              </div>
              <div className="flex rounded-lg overflow-hidden h-6">
                {farmClusters.riskDistribution.HIGH > 0 && (
                  <div
                    className="bg-rose-500/60 flex items-center justify-center text-[9px] text-white font-semibold"
                    style={{ width: `${(farmClusters.riskDistribution.HIGH / farmClusters.total) * 100}%` }}>
                    {farmClusters.riskDistribution.HIGH}
                  </div>
                )}
                {farmClusters.riskDistribution.ELEVATED > 0 && (
                  <div
                    className="bg-amber-500/60 flex items-center justify-center text-[9px] text-white font-semibold"
                    style={{ width: `${(farmClusters.riskDistribution.ELEVATED / farmClusters.total) * 100}%` }}>
                    {farmClusters.riskDistribution.ELEVATED}
                  </div>
                )}
                {farmClusters.riskDistribution.LOW > 0 && (
                  <div
                    className="bg-emerald-500/40 flex items-center justify-center text-[9px] text-white font-semibold"
                    style={{ width: `${(farmClusters.riskDistribution.LOW / farmClusters.total) * 100}%` }}>
                    {farmClusters.riskDistribution.LOW}
                  </div>
                )}
              </div>
              <div className="flex items-center gap-4 mt-1 text-[9px] text-[var(--text-secondary)]">
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-rose-500" /> High/Critical</span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-500" /> Elevated</span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-500" /> Low</span>
              </div>
            </div>

            {/* Top operators table */}
            <div>
              <div className="text-[10px] text-[var(--text-secondary)] mb-2 uppercase tracking-wider">
                Top Operators by Farm Count
              </div>
              <div className="space-y-1">
                {farmClusters.clusters.map((c, i) => (
                  <div key={c.name}
                    className="flex items-center gap-3 p-2 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                    <span className="text-[10px] text-[var(--text-secondary)] w-5 text-right">{i + 1}.</span>
                    <span className="text-xs text-[var(--text-primary)] flex-1 truncate">{c.name}</span>
                    <span className="text-[10px] font-mono text-violet-400">{c.count} farms</span>
                    <div className="w-20 bg-white/[0.04] rounded-full h-1.5 overflow-hidden">
                      <div
                        className={`h-full rounded-full ${c.avgRisk > 60 ? "bg-rose-400" : c.avgRisk > 30 ? "bg-amber-400" : "bg-emerald-400"}`}
                        style={{ width: `${Math.min(100, c.avgRisk)}%` }}
                      />
                    </div>
                    <span className={`text-[10px] font-mono w-8 text-right ${
                      c.avgRisk > 60 ? "text-rose-400" : c.avgRisk > 30 ? "text-amber-400" : "text-emerald-400"
                    }`}>
                      {c.avgRisk}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="text-center py-8 text-[var(--text-secondary)] text-sm">
            {loading ? "Loading farm data..." : "No farm cluster data available"}
          </div>
        )}
      </GlassCard>

      {/* ── Satellite Scan Results (existing) ────────────────────── */}

      {/* Status Banner */}
      {status && (
        <div className={`flex items-center gap-3 px-4 py-3 rounded-xl border ${
          status.configured
            ? "bg-emerald-500/[0.06] border-emerald-500/20"
            : "bg-amber-500/[0.06] border-amber-500/20"
        }`}>
          <Satellite className={`w-4 h-4 ${status.configured ? "text-emerald-400" : "text-amber-400"}`} />
          <div className="flex-1">
            <span className={`text-xs font-semibold ${status.configured ? "text-emerald-400" : "text-amber-400"}`}>
              {status.configured ? "LIVE" : "SIMULATED MODE"}
            </span>
            <span className="text-[10px] text-[var(--text-secondary)] ml-2">
              {status.note}
            </span>
          </div>
          <span className="text-[10px] text-[var(--text-secondary)]">
            {status.satellite} &middot; {status.resolution} &middot; {status.revisit_days}-day revisit
          </span>
        </div>
      )}

      {/* KPIs (after scan) */}
      {snapshot && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <KPICard label="Farms Scanned"
            value={snapshot.n_farms_queried || 0}
            icon={Satellite} delay={0} />
          <KPICard label="Readings"
            value={snapshot.n_readings || 0}
            icon={Eye} delay={0.03} />
          <KPICard label="Anomalies"
            value={snapshot.n_anomalies || 0}
            deltaType={snapshot.n_anomalies > 0 ? "negative" : "positive"}
            delta={snapshot.n_anomalies > 0 ? "Action required" : "All clear"}
            icon={AlertTriangle} delay={0.06} />
          <KPICard label="Cloud-Free"
            value={`${snapshot.cloud_free_pct || 0}%`}
            icon={Cloud} delay={0.09} />
          <KPICard label="Data Source"
            value={summary.is_live ? "Sentinel-2" : "Simulated"}
            icon={Activity} delay={0.12} />
        </div>
      )}

      {/* Intelligence Products */}
      <GlassCard delay={0.3} accent="violet">
        <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-4 flex items-center gap-2">
          <Eye className="w-4 h-4 text-violet-400" />
          Intelligence Products
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
          {products.map((p: any) => (
            <div key={p.id} className="p-4 rounded-xl border border-violet-500/20 bg-violet-500/[0.04]">
              <div className="text-sm font-semibold text-[var(--text-primary)] mb-1">{p.name}</div>
              <p className="text-[10px] text-[var(--text-secondary)] mb-3">{p.description}</p>
              <div className="space-y-1 text-[10px]">
                <div className="flex justify-between">
                  <span className="text-[var(--text-secondary)]">Index</span>
                  <span className="text-violet-400 font-mono">{p.index}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--text-secondary)]">Resolution</span>
                  <span className="text-[var(--text-primary)]">{p.resolution}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--text-secondary)]">Revisit</span>
                  <span className="text-[var(--text-primary)]">{p.revisit}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </GlassCard>

      {/* Anomalies */}
      {anomalies.length > 0 && (
        <GlassCard delay={0.35} accent="rose">
          <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-400" />
            Satellite Anomalies Detected ({anomalies.length})
          </h3>
          <div className="space-y-2">
            {anomalies.map((a: any, i: number) => {
              const Icon = ANOMALY_ICONS[a.anomaly_type] || AlertTriangle;
              const color = ANOMALY_COLORS[a.anomaly_type] || "text-amber-400";
              return (
                <motion.div key={i}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.05 + i * 0.03 }}
                  className="flex items-center gap-3 p-3 rounded-xl bg-white/[0.03] border border-white/[0.06]"
                >
                  <Icon className={`w-4 h-4 flex-shrink-0 ${color}`} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="text-[11px] font-semibold text-[var(--text-primary)]">
                        {a.name || `Locality ${a.locality_no}`}
                      </span>
                      <span className="text-[9px] px-1.5 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/20">
                        {(a.anomaly_type || "").replace(/_/g, " ")}
                      </span>
                    </div>
                    <p className="text-[10px] text-[var(--text-secondary)] truncate">{a.anomaly_detail}</p>
                  </div>
                  <div className="text-right flex-shrink-0 text-[10px]">
                    <div className="text-[var(--text-secondary)]">NDWI: {a.ndwi?.toFixed(3)}</div>
                    <div className="text-[var(--text-secondary)]">NDVI: {a.ndvi?.toFixed(3)}</div>
                  </div>
                </motion.div>
              );
            })}
          </div>
        </GlassCard>
      )}

      {/* Summary Stats (after scan) */}
      {snapshot && readings.length > 0 && (
        <GlassCard delay={0.4} accent="ocean">
          <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-ocean-400" />
            Water Quality Summary
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: "Avg NDWI", value: summary.avg_ndwi?.toFixed(4) || "\u2014", desc: "Water presence index" },
              { label: "Avg NDVI", value: summary.avg_ndvi?.toFixed(4) || "\u2014", desc: "Vegetation/chlorophyll" },
              { label: "Avg Turbidity", value: summary.avg_turbidity?.toFixed(4) || "\u2014", desc: "Surface disturbance" },
              { label: "Anomaly Rate", value: `${summary.anomaly_rate_pct || 0}%`, desc: "Farms with anomalies" },
            ].map(({ label, value, desc }) => (
              <div key={label} className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06]">
                <div className="text-[10px] text-[var(--text-secondary)] uppercase tracking-wider">{label}</div>
                <div className="text-lg font-bold text-[var(--text-primary)] mt-1">{value}</div>
                <div className="text-[9px] text-[var(--text-secondary)] mt-0.5">{desc}</div>
              </div>
            ))}
          </div>
        </GlassCard>
      )}

      {/* No scan yet */}
      {!snapshot && !scanning && (
        <GlassCard delay={0.35}>
          <div className="text-center py-12">
            <Satellite className="w-10 h-10 mx-auto text-violet-400/30 mb-3" />
            <p className="text-sm text-[var(--text-secondary)] mb-1">Run a satellite scan for detailed farm-level imagery analysis</p>
            <p className="text-[10px] text-[var(--text-secondary)] mb-4 max-w-md mx-auto">
              Queries Sentinel-2 imagery for water quality indices (NDWI, NDVI, turbidity),
              surface anomaly detection, and bloom confirmation. Currently in simulated mode
              &mdash; configure CDSE credentials for live 10m imagery.
            </p>
            <OcButton variant="primary" size="md" onClick={runScan} loading={scanning}
              leftIcon={<Eye className="w-4 h-4" />}>
              Run Satellite Scan
            </OcButton>
          </div>
        </GlassCard>
      )}

      {/* Readings table */}
      {readings.length > 0 && (
        <GlassCard delay={0.45}>
          <details>
            <summary className="text-[11px] text-[var(--text-secondary)] cursor-pointer hover:text-ocean-400 transition-colors flex items-center gap-2">
              <Eye className="w-3 h-3" />
              All Readings ({readings.length} farms)
            </summary>
            <div className="mt-3 overflow-x-auto max-h-[400px] overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-ocean-950/95 backdrop-blur">
                  <tr className="border-b border-white/[0.06]">
                    <th className="text-left py-2 px-3 text-[var(--text-secondary)] font-medium text-[10px] uppercase">Farm</th>
                    <th className="text-left py-2 px-3 text-[var(--text-secondary)] font-medium text-[10px] uppercase">NDWI</th>
                    <th className="text-left py-2 px-3 text-[var(--text-secondary)] font-medium text-[10px] uppercase">NDVI</th>
                    <th className="text-left py-2 px-3 text-[var(--text-secondary)] font-medium text-[10px] uppercase">Turbidity</th>
                    <th className="text-left py-2 px-3 text-[var(--text-secondary)] font-medium text-[10px] uppercase">Cloud</th>
                    <th className="text-left py-2 px-3 text-[var(--text-secondary)] font-medium text-[10px] uppercase">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {readings.slice(0, 50).map((r: any, i: number) => (
                    <tr key={i} className="border-b border-white/[0.04] hover:bg-white/[0.02]">
                      <td className="py-2 px-3 text-xs">
                        <span className="text-[var(--text-primary)]">{r.name}</span>
                        <span className="text-[9px] text-[var(--text-secondary)] ml-1">#{r.locality_no}</span>
                      </td>
                      <td className="py-2 px-3 font-mono text-[10px] text-[var(--text-secondary)]">{r.ndwi?.toFixed(3)}</td>
                      <td className="py-2 px-3 font-mono text-[10px] text-[var(--text-secondary)]">{r.ndvi?.toFixed(3)}</td>
                      <td className="py-2 px-3 font-mono text-[10px] text-[var(--text-secondary)]">{r.turbidity?.toFixed(3)}</td>
                      <td className="py-2 px-3 font-mono text-[10px] text-[var(--text-secondary)]">{r.cloud_pct?.toFixed(0)}%</td>
                      <td className="py-2 px-3">
                        {r.anomaly_detected ? (
                          <span className="text-[9px] px-1.5 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/20">
                            {(r.anomaly_type || "").replace(/_/g, " ")}
                          </span>
                        ) : (
                          <span className="text-[9px] text-emerald-400">Clear</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </GlassCard>
      )}

      {/* ── Data Sources Panel ───────────────────────────────────── */}
      <GlassCard delay={0.5} accent="none">
        <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-4 flex items-center gap-2">
          <Database className="w-4 h-4 text-slate-400" />
          Data Sources
          <span className="text-[10px] font-normal text-[var(--text-secondary)] ml-2">
            {DATA_SOURCES.filter(d => d.status === "active").length} active, {DATA_SOURCES.filter(d => d.status === "pending").length} pending
          </span>
        </h3>
        <div className="space-y-2">
          {DATA_SOURCES.map((ds) => {
            const Icon = ds.icon;
            return (
              <div key={ds.name}
                className={`flex items-start gap-3 p-3 rounded-xl border ${
                  ds.status === "active"
                    ? "bg-emerald-500/[0.04] border-emerald-500/15"
                    : ds.status === "pending"
                    ? "bg-amber-500/[0.04] border-amber-500/15"
                    : "bg-rose-500/[0.04] border-rose-500/15"
                }`}>
                <Icon className={`w-4 h-4 mt-0.5 flex-shrink-0 ${
                  ds.status === "active" ? "text-emerald-400" : ds.status === "pending" ? "text-amber-400" : "text-rose-400"
                }`} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-xs font-semibold text-[var(--text-primary)]">{ds.name}</span>
                    <span className={`text-[9px] px-1.5 py-0.5 rounded border font-semibold uppercase tracking-wider ${
                      ds.status === "active"
                        ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                        : ds.status === "pending"
                        ? "bg-amber-500/10 text-amber-400 border-amber-500/20"
                        : "bg-rose-500/10 text-rose-400 border-rose-500/20"
                    }`}>
                      {ds.status}
                    </span>
                  </div>
                  <p className="text-[10px] text-[var(--text-secondary)]">{ds.description}</p>
                  <div className="flex items-center gap-4 mt-1 text-[9px] text-[var(--text-secondary)]">
                    <span>Provider: {ds.provider}</span>
                    <span>Resolution: {ds.resolution}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </GlassCard>

      <p className="text-[10px] text-[var(--text-secondary)] text-center opacity-60">
        Live data: MET.no OceanForecast 2.0 (SST), Copernicus CMEMS (chlorophyll-a), BarentsWatch (farm registry), Climate Risk Engine (composite scoring).
        Sentinel-2 10m imagery pending CDSE credentials (SENTINEL_HUB_CLIENT_ID / SENTINEL_HUB_CLIENT_SECRET).
      </p>
    </div>
    </ErrorBoundary>
  );
}
