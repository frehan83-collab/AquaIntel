"use client";
import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import {
  Map, Building2, TrendingUp, TrendingDown, Minus, MapPin, Network,
  Zap, AlertTriangle, Bug, BarChart3, Calendar, Brain, Shield,
  RefreshCw, ChevronRight, Activity, Info,
} from "lucide-react";
import GlassCard from "@/components/GlassCard";
import KPICard from "@/components/KPICard";
import { OcButton } from "@/components/ui/Button";
import dynamic from "next/dynamic";
import { api } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";

const ExposureMap = dynamic(() => import("@/components/ExposureMap"), {
  loading: () => <div className="h-[500px] bg-slate-800/50 rounded-xl animate-pulse flex items-center justify-center"><span className="text-slate-400">Loading map...</span></div>,
  ssr: false,
});
const FarmNetworkMap = dynamic(() => import("@/components/FarmNetworkMap"), {
  loading: () => <div className="h-[500px] bg-slate-800/50 rounded-xl animate-pulse flex items-center justify-center"><span className="text-slate-400">Loading network map...</span></div>,
  ssr: false,
});

/* eslint-disable @typescript-eslint/no-explicit-any */

const TRAFFIC_LIGHT_COLORS: Record<string, string> = {
  green: "bg-emerald-400",
  yellow: "bg-amber-400",
  red: "bg-rose-500",
};
const TRAFFIC_LIGHT_TEXT: Record<string, string> = {
  green: "text-emerald-400",
  yellow: "text-amber-400",
  red: "text-rose-400",
};

const PA_NAMES: Record<number, string> = {
  1: "Svenskegrensen\u2013J\u00e6ren",
  2: "Ryfylke",
  3: "Karm\u00f8y\u2013Sunnhordland",
  4: "Nordhordland\u2013Sogn",
  5: "Fjordane",
  6: "Sunnm\u00f8re\u2013Nordm\u00f8re",
  7: "Trondheimsleia",
  8: "Helgeland\u2013Nordm\u00f8re",
  9: "Vestfjorden\u2013Vester\u00e5len",
  10: "And\u00f8ya\u2013Senja",
  11: "Kval\u00f8ya\u2013Loppa",
  12: "Vest-Finnmark",
  13: "\u00d8st-Finnmark",
};

export default function ExposurePage() {
  const { t } = useTranslation();
  // Exposure data
  const [companies, setCompanies] = useState<any[]>([]);
  const [selectedCompany, setSelectedCompany] = useState<any>(null);
  const [graphSummary, setGraphSummary] = useState<any>(null);
  const [clusters, setClusters] = useState<any[]>([]);
  const [cascades, setCascades] = useState<any[]>([]);

  // Lice data
  const [summary, setSummary] = useState<any>(null);
  const [regimeStates, setRegimeStates] = useState<any[]>([]);
  const [regimeAlerts, setRegimeAlerts] = useState<any[]>([]);
  const [companyRisk, setCompanyRisk] = useState<any[]>([]);
  const [gnnPredictions, setGnnPredictions] = useState<any>(null);

  const [loading, setLoading] = useState(true);
  const [viewTab, setViewTab] = useState<"exposure" | "network">("exposure");
  const [selectedPA, setSelectedPA] = useState<number | null>(null);
  const [paDetail, setPaDetail] = useState<any>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    const results = await Promise.allSettled([
      api.leadersTop30(),
      api.farmGraphSummary(),
      api.farmGraphClusters("high"),
      api.farmGraphCascades(),
      api.farmGraphCompanyExposure(),
      api.liceSummary(),
      api.regimeStates(),
      api.regimeAlerts(),
      api.regimeCompanyRisk(),
      api.gnnPredictAll(),
    ]);

    const [r_cos, r_graph, r_clus, r_casc, r_expo, r_lice, r_regime, r_alerts, r_corisk, r_gnn] = results;

    if (r_cos.status === "fulfilled") setCompanies(r_cos.value || []);
    if (r_graph.status === "fulfilled") setGraphSummary(r_graph.value);
    if (r_clus.status === "fulfilled") {
      const v = r_clus.value;
      setClusters(Array.isArray(v) ? v : v?.clusters || []);
    }
    if (r_casc.status === "fulfilled") {
      const v = r_casc.value;
      setCascades(Array.isArray(v) ? v : v?.cascades || []);
    }
    if (r_lice.status === "fulfilled") setSummary(r_lice.value);
    if (r_regime.status === "fulfilled") setRegimeStates(r_regime.value || []);
    if (r_alerts.status === "fulfilled") setRegimeAlerts(r_alerts.value || []);
    if (r_corisk.status === "fulfilled") setCompanyRisk(r_corisk.value || []);
    if (r_gnn.status === "fulfilled") setGnnPredictions(r_gnn.value);

    setLoading(false);
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const loadPaDetail = async (pa: number) => {
    if (selectedPA === pa) { setSelectedPA(null); setPaDetail(null); return; }
    setSelectedPA(pa);
    try { setPaDetail(await api.regimePaDetail(pa)); } catch { setPaDetail(null); }
  };

  // Derived values
  const avgLice = summary?.avg_adult_female_lice ?? 0;
  const maxLice = summary?.max_adult_female_lice ?? 0;
  const nAbove = summary?.sites_above_threshold ?? 0;
  const nTotal = summary?.records ?? 1;
  const pctAbove = ((nAbove / nTotal) * 100).toFixed(1);

  const redPAs = regimeStates.filter(s => s.current_color === "red").length;
  const yellowPAs = regimeStates.filter(s => s.current_color === "yellow").length;
  const greenPAs = regimeStates.filter(s => s.current_color === "green").length;

  // PA stats from company data
  const paStats: Record<number, { companies: number; totalLocs: number; avgLice: number; names: string[] }> = {};
  companies.forEach(co => {
    (co.production_areas || []).forEach((pa: number) => {
      if (!paStats[pa]) paStats[pa] = { companies: 0, totalLocs: 0, avgLice: 0, names: [] };
      paStats[pa].companies++;
      paStats[pa].totalLocs += co.n_localities || 0;
      paStats[pa].avgLice += co.avg_lice || 0;
      paStats[pa].names.push(co.name);
    });
  });
  Object.values(paStats).forEach(s => { s.avgLice = s.companies > 0 ? s.avgLice / s.companies : 0; });

  return (
    <div className="space-y-6">

      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] flex items-center gap-3">
            <Map className="w-6 h-6 text-ocean-400" />
            Lice Exposure Map
          </h1>
          <p className="text-sm text-[var(--text-secondary)] mt-1">
            BarentsWatch real-time data &middot; Traffic light regime &middot; Farm network &middot; GNN forecasts
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex rounded-lg border border-white/[0.08] overflow-hidden">
            <button
              onClick={() => setViewTab("exposure")}
              className={`px-3 py-1.5 text-xs font-medium transition-colors ${viewTab === "exposure" ? "bg-ocean-500/20 text-ocean-400" : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"}`}
            >
              Company Exposure
            </button>
            <button
              onClick={() => setViewTab("network")}
              className={`px-3 py-1.5 text-xs font-medium transition-colors ${viewTab === "network" ? "bg-ocean-500/20 text-ocean-400" : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"}`}
            >
              Farm Network
            </button>
          </div>
          <OcButton variant="secondary" size="sm" onClick={loadData} loading={loading}
            leftIcon={<RefreshCw className="w-3.5 h-3.5" />}>
            Refresh
          </OcButton>
        </div>
      </motion.div>

      {/* KPI Row */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <KPICard
          label="Week / Year"
          value={summary ? `W${summary.week} ${summary.year}` : "\u2014"}
          icon={Calendar} delay={0}
        />
        <KPICard
          label="Avg Lice"
          value={avgLice?.toFixed(3) ?? "\u2014"}
          delta={avgLice < 0.2 ? "Below limit" : avgLice < 0.5 ? "Elevated" : "ABOVE LIMIT"}
          deltaType={avgLice < 0.2 ? "positive" : "negative"}
          icon={Bug} delay={0.04}
        />
        <KPICard
          label="Max Observed"
          value={maxLice?.toFixed(2) ?? "\u2014"}
          delta={maxLice > 0.5 ? "Exceeds 0.5 threshold" : "Within limit"}
          deltaType={maxLice > 0.5 ? "negative" : "positive"}
          icon={AlertTriangle} delay={0.08}
        />
        <KPICard
          label="% Above 0.5"
          value={`${pctAbove}%`}
          delta={`${nAbove} of ${nTotal} farms`}
          deltaType={parseFloat(pctAbove) > 20 ? "negative" : "positive"}
          icon={BarChart3} delay={0.12}
        />
        <KPICard
          label="Regime Alerts"
          value={regimeAlerts.length}
          delta={regimeAlerts.length > 0 ? "Color changes predicted" : "No changes expected"}
          deltaType={regimeAlerts.length > 0 ? "negative" : "positive"}
          icon={Shield} delay={0.16}
        />
        <KPICard
          label="High-Risk Clusters"
          value={clusters.length}
          delta="Cascade risk"
          deltaType={clusters.length > 2 ? "negative" : "positive"}
          icon={Network} delay={0.2}
        />
      </div>

      {/* Map Section — tab controlled */}
      {viewTab === "exposure" ? (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
        >
          <ExposureMap
            onSiteClick={(site) => {
              const co = companies.find((c: any) => c.name === site.company);
              if (co) setSelectedCompany(co);
            }}
          />
        </motion.div>
      ) : (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
        >
          <FarmNetworkMap />
        </motion.div>
      )}

      {/* Traffic Light Grid */}
      <GlassCard delay={0.2}>
        <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-4 flex items-center gap-2">
          <Shield className="w-4 h-4 text-amber-400" />
          Production Area Traffic Light System (PA 1&ndash;13)
          <div className="flex items-center gap-2 ml-auto text-[10px]">
            <span className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-emerald-400" /> Green ({greenPAs})</span>
            <span className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-amber-400" /> Yellow ({yellowPAs})</span>
            <span className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-rose-500" /> Red ({redPAs})</span>
          </div>
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-2">
          {regimeStates.map((state: any) => {
            const isSelected = selectedPA === state.production_area;
            const willChange = state.color_change;
            const colorClass = TRAFFIC_LIGHT_COLORS[state.current_color] || "bg-white/20";
            const textClass = TRAFFIC_LIGHT_TEXT[state.current_color] || "text-white";

            return (
              <motion.button
                key={state.production_area}
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                whileHover={{ scale: 1.02 }}
                onClick={() => loadPaDetail(state.production_area)}
                className={`text-left p-3 rounded-xl border transition-all ${
                  isSelected
                    ? "border-ocean-500/50 bg-ocean-500/[0.08]"
                    : "border-white/[0.06] bg-white/[0.02] hover:bg-white/[0.04]"
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-2">
                    <div className={`w-3 h-3 rounded-full ${colorClass} ${willChange ? "animate-pulse" : ""}`} />
                    <span className="text-[11px] font-bold text-[var(--text-primary)]">PA {state.production_area}</span>
                  </div>
                  {willChange && (
                    <span className={`text-[9px] px-1.5 py-0.5 rounded-full border ${
                      state.predicted_color === "red" ? "bg-rose-500/10 text-rose-400 border-rose-500/20" :
                      state.predicted_color === "green" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" :
                      "bg-amber-500/10 text-amber-400 border-amber-500/20"
                    }`}>
                      &rarr; {state.predicted_color}
                    </span>
                  )}
                </div>
                <p className="text-[9px] text-[var(--text-secondary)] mb-1.5 truncate">
                  {PA_NAMES[state.production_area] || ""}
                </p>
                <div className="flex items-center justify-between">
                  <span className={`text-[11px] font-semibold ${textClass}`}>
                    {state.current_color?.toUpperCase()}
                  </span>
                  <div className="flex items-center gap-1 text-[9px] text-[var(--text-secondary)]">
                    <span>P: {(state.lice_pressure_score * 100).toFixed(0)}%</span>
                    {isSelected && <ChevronRight className="w-3 h-3 text-ocean-400" />}
                  </div>
                </div>
              </motion.button>
            );
          })}
          {regimeStates.length === 0 && !loading && (
            <div className="col-span-full text-center py-8 text-[var(--text-secondary)] text-sm">
              Traffic light data loading...
            </div>
          )}
        </div>

        {/* PA Detail Drawer */}
        {selectedPA && paDetail && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            className="mt-4 pt-4 border-t border-white/[0.06]"
          >
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <div className="text-[10px] text-[var(--text-secondary)] mb-1">Current Color</div>
                <div className={`text-sm font-bold ${TRAFFIC_LIGHT_TEXT[paDetail.current_color]}`}>
                  {paDetail.current_color?.toUpperCase()}
                </div>
              </div>
              <div>
                <div className="text-[10px] text-[var(--text-secondary)] mb-1">Predicted</div>
                <div className={`text-sm font-bold ${TRAFFIC_LIGHT_TEXT[paDetail.predicted_color]}`}>
                  {paDetail.predicted_color?.toUpperCase()}
                </div>
              </div>
              <div>
                <div className="text-[10px] text-[var(--text-secondary)] mb-1">Lice Pressure</div>
                <div className="text-sm font-bold text-[var(--text-primary)]">
                  {(paDetail.lice_pressure_score * 100).toFixed(0)}%
                </div>
              </div>
              <div>
                <div className="text-[10px] text-[var(--text-secondary)] mb-1">Trend</div>
                <div className={`text-sm font-semibold ${
                  paDetail.trend === "deteriorating" ? "text-rose-400" :
                  paDetail.trend === "improving" ? "text-emerald-400" : "text-amber-400"
                }`}>
                  {paDetail.trend}
                </div>
              </div>
              {paDetail.avg_recent_8w !== null && (
                <div>
                  <div className="text-[10px] text-[var(--text-secondary)] mb-1">8-Week Avg Lice</div>
                  <div className="text-sm font-bold text-[var(--text-primary)]">{paDetail.avg_recent_8w}</div>
                </div>
              )}
              {paDetail.peak_52w !== null && (
                <div>
                  <div className="text-[10px] text-[var(--text-secondary)] mb-1">52-Week Peak</div>
                  <div className="text-sm font-bold text-rose-400">{paDetail.peak_52w}</div>
                </div>
              )}
              <div className="col-span-2">
                <div className="text-[10px] text-[var(--text-secondary)] mb-1">Key Drivers</div>
                <div className="text-[11px] text-[var(--text-primary)]">{paDetail.key_drivers}</div>
              </div>
            </div>
            {paDetail.companies_exposed?.length > 0 && (
              <div className="mt-3">
                <div className="text-[10px] text-[var(--text-secondary)] mb-2">Exposed Companies</div>
                <div className="flex flex-wrap gap-2">
                  {paDetail.companies_exposed.map((co: any) => (
                    <span key={co.ticker} className="text-[10px] px-2 py-0.5 rounded-full bg-white/[0.05] border border-white/[0.1]">
                      {co.ticker} <span className="text-ocean-400">{co.exposure_pct}%</span>
                    </span>
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        )}
      </GlassCard>

      {/* PA Exposure Grid */}
      <GlassCard delay={0.25}>
        <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
          <MapPin className="w-4 h-4 text-ocean-400" />
          Production Area Exposure
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 ml-auto">REAL DATA</span>
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-2">
          {Array.from({ length: 13 }, (_, i) => i + 1).map(pa => {
            const s = paStats[pa];
            if (!s) return (
              <div key={pa} className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.04] text-center opacity-40">
                <p className="text-xs font-bold text-[var(--text-secondary)]">PA-{pa}</p>
                <p className="text-[10px] text-[var(--text-secondary)] mt-1">No data</p>
              </div>
            );
            const color = s.avgLice >= 0.3 ? "border-rose-500/20 bg-rose-500/[0.04]" :
                          s.avgLice >= 0.15 ? "border-amber-500/20 bg-amber-500/[0.04]" :
                          "border-emerald-500/20 bg-emerald-500/[0.04]";
            return (
              <motion.div
                key={pa}
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.1 + pa * 0.03 }}
                className={`p-3 rounded-xl border ${color}`}
              >
                <p className="text-xs font-bold text-[var(--text-primary)]">PA-{pa}</p>
                <p className={`text-lg font-bold mt-1 ${
                  s.avgLice >= 0.3 ? "text-rose-400" : s.avgLice >= 0.15 ? "text-amber-400" : "text-emerald-400"
                }`}>{s.avgLice.toFixed(3)}</p>
                <p className="text-[10px] text-[var(--text-secondary)]">{s.companies} cos &middot; {s.totalLocs} sites</p>
              </motion.div>
            );
          })}
        </div>
      </GlassCard>

      {/* Intelligence Row: Alerts + Company Risk + GNN */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

        {/* Regime Alerts */}
        <GlassCard delay={0.3} accent="amber">
          <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            Color Change Alerts
          </h3>
          <div className="space-y-2 max-h-[300px] overflow-y-auto">
            {regimeAlerts.slice(0, 8).map((alert: any, i: number) => (
              <div key={i} className={`p-2.5 rounded-lg border ${
                alert.predicted === "red" ? "border-rose-500/20 bg-rose-500/[0.04]" :
                alert.predicted === "green" ? "border-emerald-500/20 bg-emerald-500/[0.04]" :
                "border-amber-500/20 bg-amber-500/[0.04]"
              }`}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[11px] font-semibold">PA {alert.production_area}</span>
                  <div className="flex items-center gap-1.5 text-[9px]">
                    <span className={TRAFFIC_LIGHT_TEXT[alert.current]}>{alert.current}</span>
                    <span className="text-[var(--text-secondary)]">&rarr;</span>
                    <span className={TRAFFIC_LIGHT_TEXT[alert.predicted]}>{alert.predicted}</span>
                    <span className="text-[var(--text-secondary)] ml-1">({(alert.probability * 100).toFixed(0)}%)</span>
                  </div>
                </div>
                <div className="flex items-center justify-between text-[9px] text-[var(--text-secondary)]">
                  <span>{alert.timing}</span>
                  <span>Impact: {alert.stock_impact}</span>
                </div>
                {alert.tickers?.length > 0 && (
                  <div className="flex gap-1 mt-1">
                    {alert.tickers.map((t: string) => (
                      <span key={t} className="text-[9px] px-1 py-0.5 rounded bg-white/[0.05] text-ocean-400">{t}</span>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {regimeAlerts.length === 0 && (
              <p className="text-[11px] text-emerald-400 text-center py-6">
                No color changes predicted
              </p>
            )}
          </div>
        </GlassCard>

        {/* Company Regulatory Risk */}
        <GlassCard delay={0.35} accent="ocean">
          <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
            <TrendingDown className="w-4 h-4 text-ocean-400" />
            Company Regulatory Risk
          </h3>
          <div className="space-y-2 max-h-[300px] overflow-y-auto">
            {companyRisk.slice(0, 6).map((co: any) => (
              <div key={co.ticker} className="p-2.5 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-[11px] font-bold font-mono">{co.ticker}</span>
                  <span className={`text-[10px] font-semibold ${
                    co.risk_level === "high" ? "text-rose-400" :
                    co.risk_level === "medium" ? "text-amber-400" : "text-emerald-400"
                  }`}>
                    {co.risk_level?.toUpperCase()}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex-1 h-1.5 bg-white/10 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${
                        co.risk_level === "high" ? "bg-rose-500" :
                        co.risk_level === "medium" ? "bg-amber-400" : "bg-emerald-500"
                      }`}
                      style={{ width: `${Math.min(100, co.regulatory_risk_score)}%` }}
                    />
                  </div>
                  <span className="text-[10px] font-mono w-8 text-right text-[var(--text-secondary)]">
                    {co.regulatory_risk_score}
                  </span>
                </div>
                <div className="flex justify-between text-[9px] text-[var(--text-secondary)] mt-1">
                  <span>Risk: {co.regulatory_risk_score}</span>
                  <span className="text-emerald-400">Upside: +{co.regulatory_upside_score}</span>
                  <span>{co.n_pas_exposed} PAs</span>
                </div>
              </div>
            ))}
            {companyRisk.length === 0 && (
              <p className="text-[11px] text-[var(--text-secondary)] text-center py-6">
                Loading company risk...
              </p>
            )}
          </div>
        </GlassCard>

        {/* GNN Predictions */}
        <GlassCard delay={0.4} accent="rose">
          <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
            <Brain className="w-4 h-4 text-rose-400" />
            GNN Week-Ahead Forecast
            <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20 ml-auto">AI</span>
          </h3>
          {gnnPredictions ? (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-[10px] mb-2">
                <span className="text-[var(--text-secondary)]">{gnnPredictions.n_farms} farms modelled</span>
                <span className="text-rose-400 font-semibold">{gnnPredictions.n_high_risk} predicted above 0.5</span>
              </div>
              {(gnnPredictions.high_risk_farms || []).slice(0, 8).map((farm: any) => (
                <div key={farm.farm_id} className="flex items-center gap-2 p-1.5 rounded bg-white/[0.03]">
                  <span className="text-[9px] text-[var(--text-secondary)] w-12 font-mono">#{farm.farm_id}</span>
                  <div className="flex-1 h-1.5 bg-white/10 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${farm.exceed_probability > 0.7 ? "bg-rose-500" : "bg-amber-400"}`}
                      style={{ width: `${farm.exceed_probability * 100}%` }}
                    />
                  </div>
                  <span className="text-[9px] font-semibold text-rose-400 w-8 text-right">
                    {(farm.exceed_probability * 100).toFixed(0)}%
                  </span>
                  <span className="text-[9px] text-[var(--text-secondary)] w-12 text-right">
                    {farm.predicted_lice?.toFixed(2)} lice
                  </span>
                </div>
              ))}
              {gnnPredictions.n_high_risk === 0 && (
                <p className="text-[11px] text-emerald-400 text-center py-4">
                  No farms predicted above threshold next week
                </p>
              )}
            </div>
          ) : (
            <div className="py-6 text-center space-y-2">
              <Brain className="w-8 h-8 mx-auto opacity-20" />
              <p className="text-[11px] text-[var(--text-secondary)]">GNN model not trained yet</p>
              <p className="text-[9px] text-[var(--text-secondary)] opacity-60">
                Requires torch_geometric + training data
              </p>
            </div>
          )}
        </GlassCard>
      </div>

      {/* Farm Network Row */}
      {(graphSummary || clusters.length > 0 || cascades.length > 0) && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

          {/* Network Summary */}
          <GlassCard delay={0.45} accent="ocean">
            <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
              <Network className="w-4 h-4 text-ocean-400" />
              Farm Network Graph
            </h3>
            {graphSummary ? (
              <div className="space-y-2">
                {[
                  ["Farms tracked", graphSummary.n_farms ?? "\u2014"],
                  ["Connections", graphSummary.n_connections ?? "\u2014"],
                  ["Clusters", graphSummary.n_clusters ?? "\u2014"],
                  ["Above threshold", graphSummary.n_above_threshold ?? "\u2014"],
                  ["Avg lice (network)", (graphSummary.avg_lice ?? 0).toFixed(3)],
                ].map(([label, val]) => (
                  <div key={label as string} className="flex items-center justify-between py-1 border-b border-white/[0.04] last:border-0">
                    <span className="text-[11px] text-[var(--text-secondary)]">{label}</span>
                    <span className="text-[11px] font-mono font-semibold text-[var(--text-primary)]">{val}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-[var(--text-secondary)] py-4 text-center opacity-60">
                Farm graph building...
              </p>
            )}
          </GlassCard>

          {/* High-Risk Clusters */}
          <GlassCard delay={0.48} accent="rose">
            <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
              <Zap className="w-4 h-4 text-rose-400" />
              High-Risk Clusters
            </h3>
            {clusters.length === 0 ? (
              <p className="text-xs text-[var(--text-secondary)] py-4 text-center opacity-60">
                No high-risk clusters detected
              </p>
            ) : (
              <div className="space-y-2">
                {clusters.slice(0, 5).map((cl: any, i: number) => (
                  <div key={i} className="p-2 rounded-lg bg-rose-500/[0.04] border border-rose-500/[0.1]">
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] font-semibold text-[var(--text-primary)]">
                        Cluster {cl.cluster_id ?? i + 1}
                      </span>
                      <span className="text-[10px] text-rose-400">{cl.farm_count ?? cl.size ?? "?"} farms</span>
                    </div>
                    <p className="text-[10px] text-[var(--text-secondary)] mt-0.5">
                      Avg lice: {(cl.avg_lice ?? cl.mean_lice ?? 0).toFixed(3)} &middot; PA {cl.pa ?? cl.production_area ?? "?"}
                    </p>
                    {cl.dominant_company && (
                      <p className="text-[9px] text-rose-400 mt-0.5">{cl.dominant_company}</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </GlassCard>

          {/* Cascade Predictions */}
          <GlassCard delay={0.51} accent="amber">
            <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
              <Activity className="w-4 h-4 text-amber-400" />
              Cascade Predictions
            </h3>
            {cascades.length === 0 ? (
              <p className="text-xs text-[var(--text-secondary)] py-4 text-center opacity-60">
                No cascade events predicted &mdash; network stable
              </p>
            ) : (
              <div className="space-y-2">
                {cascades.slice(0, 5).map((cas: any, i: number) => (
                  <div key={i} className="p-2 rounded-lg bg-amber-500/[0.04] border border-amber-500/[0.1]">
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] font-semibold text-[var(--text-primary)]">
                        {cas.source_farm ?? `Farm ${cas.source_locality_no ?? i + 1}`}
                      </span>
                      <span className="text-[10px] text-amber-400">&rarr; {cas.affected_farms ?? cas.n_affected ?? "?"} farms</span>
                    </div>
                    <p className="text-[10px] text-[var(--text-secondary)] mt-0.5 truncate">
                      Risk: {cas.cascade_risk?.toFixed(2) ?? "?"} &middot; {cas.direction ?? "downflow"}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </GlassCard>
        </div>
      )}

      {/* Company Table */}
      <GlassCard delay={0.55}>
        <div className="flex items-center gap-2 mb-4">
          <Building2 className="w-4 h-4 text-ocean-400" />
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">Company Exposure Summary</h3>
        </div>
        <div className="overflow-x-auto max-h-[500px] overflow-y-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-ocean-950/95 backdrop-blur z-10">
              <tr className="border-b border-white/[0.06]">
                <th className="text-left py-2 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Company</th>
                <th className="text-left py-2 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">PAs</th>
                <th className="text-left py-2 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Sites</th>
                <th className="text-left py-2 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Avg Lice</th>
                <th className="text-left py-2 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Score</th>
                <th className="text-left py-2 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Risk</th>
                <th className="text-left py-2 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Outlook</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={7} className="py-12 text-center text-[var(--text-secondary)]">Loading...</td></tr>
              ) : companies.slice(0, 50).map((co, i) => (
                <motion.tr
                  key={co.name}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: Math.min(i * 0.015, 0.3) }}
                  onClick={() => setSelectedCompany(selectedCompany?.name === co.name ? null : co)}
                  className={`border-b border-white/[0.04] hover:bg-white/[0.03] cursor-pointer transition-colors ${
                    selectedCompany?.name === co.name ? "bg-white/[0.04]" : ""
                  }`}
                >
                  <td className="py-2.5 px-3">
                    <span className="font-semibold text-[var(--text-primary)]">{co.name}</span>
                    {co.parent_group && (
                      <span className="text-[9px] text-violet-400 ml-1.5">{co.parent_group}</span>
                    )}
                  </td>
                  <td className="py-2.5 px-3 text-xs text-[var(--text-secondary)]">
                    {co.production_areas?.map((pa: number) => `PA-${pa}`).join(", ") || "\u2014"}
                  </td>
                  <td className="py-2.5 px-3">{co.n_localities}</td>
                  <td className="py-2.5 px-3">
                    <span className={`font-mono text-xs ${
                      co.avg_lice > 0.3 ? "text-rose-400" : co.avg_lice > 0.15 ? "text-amber-400" : "text-emerald-400"
                    }`}>{co.avg_lice?.toFixed(3) || "\u2014"}</span>
                  </td>
                  <td className="py-2.5 px-3">
                    <span className={`text-xs font-bold ${
                      co.performance_score >= 70 ? "text-emerald-400" : co.performance_score >= 40 ? "text-amber-400" : "text-rose-400"
                    }`}>{co.performance_score?.toFixed(0)}</span>
                  </td>
                  <td className="py-2.5 px-3">
                    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-md border ${
                      co.risk_level === "LOW" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" :
                      co.risk_level === "MEDIUM" ? "bg-amber-500/10 text-amber-400 border-amber-500/20" :
                      co.risk_level === "HIGH" ? "bg-orange-500/10 text-orange-400 border-orange-500/20" :
                      "bg-rose-500/10 text-rose-400 border-rose-500/20"
                    }`}>{co.risk_level}</span>
                  </td>
                  <td className="py-2.5 px-3">
                    <span className={`inline-flex items-center gap-1 text-xs ${
                      co.outlook_direction === "positive" ? "text-emerald-400" :
                      co.outlook_direction === "negative" ? "text-rose-400" : "text-amber-400"
                    }`}>
                      {co.outlook_direction === "positive" ? <TrendingUp className="w-3 h-3" /> :
                       co.outlook_direction === "negative" ? <TrendingDown className="w-3 h-3" /> :
                       <Minus className="w-3 h-3" />}
                      {co.outlook_direction}
                    </span>
                  </td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
      </GlassCard>

      {/* Detail Panel */}
      {selectedCompany && (
        <GlassCard delay={0}>
          <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3">
            {selectedCompany.name} &mdash; Exposure Detail
          </h3>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {[
              { label: "Company", value: selectedCompany.name },
              { label: "Sites", value: selectedCompany.n_localities },
              { label: "Avg Lice", value: selectedCompany.avg_lice?.toFixed(4) },
              { label: "Max Lice", value: selectedCompany.max_lice?.toFixed(4) },
              { label: "Score", value: selectedCompany.performance_score?.toFixed(1) },
              { label: "Production Areas", value: selectedCompany.production_areas?.map((p: number) => `PA-${p}`).join(", ") },
              { label: "Risk Level", value: selectedCompany.risk_level },
              { label: "Lice Records", value: selectedCompany.n_lice_records?.toLocaleString() },
            ].map((item) => (
              <div key={item.label} className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06]">
                <span className="text-[10px] text-[var(--text-secondary)] uppercase tracking-wider">{item.label}</span>
                <p className="text-sm font-medium text-[var(--text-primary)] mt-1">{item.value}</p>
              </div>
            ))}
          </div>
        </GlassCard>
      )}

      {/* Attribution */}
      <div className="flex items-start gap-2 px-1">
        <Info className="w-3.5 h-3.5 text-[var(--text-secondary)] flex-shrink-0 mt-0.5" />
        <p className="text-[10px] text-[var(--text-secondary)] opacity-60">
          Lice data: BarentsWatch public API (NLOD 2.0). Current traffic-light colours are the official decision of 19 June 2026;
          the regime predictions blend lice pressure with fixed transition priors that are not estimated from the official decisions. GNN predictions require model training.
          Farm dispersal network uses haversine distance + NorKyst800 current proxies. Not financial or regulatory advice.
        </p>
      </div>
    </div>
  );
}
