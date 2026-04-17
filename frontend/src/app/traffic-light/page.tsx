"use client";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Thermometer, RefreshCw, AlertTriangle, ChevronRight,
  ArrowUp, ArrowDown, Minus, Activity,
} from "lucide-react";
import KPICard from "@/components/KPICard";
import GlassCard from "@/components/GlassCard";
import { OcButton } from "@/components/ui/Button";
import TrafikklysIndicator from "@/components/TrafikklysIndicator";
import { api } from "@/lib/api";
import { useTranslation, formatNumber } from "@/lib/i18n";
import { useApiError } from "@/lib/useApiError";
import DataTable, { Column } from "@/components/DataTable";
import { trafficLight, colors } from "@/lib/design-tokens";
import DataQualityBadge from "@/components/DataQualityBadge";
import ErrorBoundary from "@/components/ErrorBoundary";

/* eslint-disable @typescript-eslint/no-explicit-any */

/** Traffic light color styles — hex values reference design tokens (trafficLight) */
const COLOR_STYLES: Record<string, { dot: string; bg: string; text: string; border: string; hex: string }> = {
  green: {
    dot: "bg-emerald-400",
    bg: "bg-emerald-500/20",
    text: "text-emerald-400",
    border: "border-emerald-500/30",
    hex: trafficLight.green,
  },
  yellow: {
    dot: "bg-amber-400",
    bg: "bg-amber-500/20",
    text: "text-amber-400",
    border: "border-amber-500/30",
    hex: trafficLight.yellow,
  },
  red: {
    dot: "bg-rose-400",
    bg: "bg-rose-500/20",
    text: "text-rose-400",
    border: "border-rose-500/30",
    hex: trafficLight.red,
  },
};

function colorDot(color: string) {
  const s = COLOR_STYLES[color] || COLOR_STYLES.yellow;
  return <span className={`inline-block w-3 h-3 rounded-full ${s.dot}`} />;
}

function colorBadge(color: string) {
  const s = COLOR_STYLES[color] || COLOR_STYLES.yellow;
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-semibold uppercase ${s.bg} ${s.text} border ${s.border}`}>
      {color}
    </span>
  );
}

function impactArrow(val: number) {
  if (val > 0) return <ArrowUp className="w-4 h-4 text-emerald-400 inline" />;
  if (val < 0) return <ArrowDown className="w-4 h-4 text-rose-400 inline" />;
  return <Minus className="w-4 h-4 text-slate-400 inline" />;
}

export default function TrafficLightPage() {
  const { t, locale } = useTranslation();
  const handleError = useApiError();
  const [current, setCurrent] = useState<any>(null);
  const [simulation, setSimulation] = useState<any>(null);
  const [selectedPa, setSelectedPa] = useState(3);
  const [selectedColor, setSelectedColor] = useState("red");
  const [loading, setLoading] = useState(true);
  const [simLoading, setSimLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const data = await api.trafficLightCurrent();
      setCurrent(data);
    } catch (e) {
      handleError("traffic_light_load")(e);
    }
    setLoading(false);
  };

  const runSimulation = async () => {
    setSimLoading(true);
    try {
      const data = await api.trafficLightSimulate(selectedPa, selectedColor);
      setSimulation(data);
    } catch (e) {
      handleError("traffic_light_simulate")(e);
    }
    setSimLoading(false);
  };

  useEffect(() => { load(); }, []);

  if (loading) {
    return (
      <div className="p-6 space-y-6">
        <div className="h-8 w-64 bg-white/5 rounded animate-pulse" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-24 bg-white/5 rounded-xl animate-pulse" />
          ))}
        </div>
        <div className="h-96 bg-white/5 rounded-xl animate-pulse" />
      </div>
    );
  }

  const pas = current?.production_areas || [];

  return (
    <ErrorBoundary fallbackTitle="Traffic Light error">
    <div className="p-6 space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2">
              <Thermometer className="w-7 h-7 text-cyan-400" />
              {t("traffic_light.title")}
            </h1>
            <div className="flex items-center gap-2 mt-1">
              <p className="text-slate-400 text-sm">
                Norway Production Area Capacity Planning (2027-2029)
              </p>
              <DataQualityBadge source="BarentsWatch" quality="live" />
            </div>
          </div>
          <OcButton variant="ghost" onClick={load}>
            <RefreshCw className="w-4 h-4 mr-1" /> Refresh
          </OcButton>
        </div>
      </motion.div>

      {/* KPI Strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KPICard label="Total PAs" value={current?.total_pas || 13} icon={Activity} />
        <KPICard label={t("traffic_light.green")} value={current?.green || 0} icon={ArrowUp} />
        <KPICard label={t("traffic_light.yellow")} value={current?.yellow || 0} icon={Minus} />
        <KPICard label={t("traffic_light.red")} value={current?.red || 0} icon={ArrowDown} />
      </div>

      {/* Current Status Table */}
      <GlassCard>
        <DataTable
          title={t("traffic_light.current_status")}
          data={pas}
          searchKeys={["name", "region"]}
          exportFilename="traffic_light_status"
          compact
          columns={[
            {
              key: "production_area", label: "PA", sortable: true, width: "50px",
              render: (val: any) => <span className="text-white font-mono">{val}</span>,
            },
            {
              key: "name", label: "Name", sortable: true,
              render: (val: any) => <span className="text-slate-300">{val}</span>,
            },
            {
              key: "region", label: "Region", sortable: true,
              render: (val: any) => <span className="text-slate-400">{val}</span>,
            },
            {
              key: "current_color", label: "Status", sortable: true, align: "center" as const,
              render: (val: any, row: any) => (
                <TrafikklysIndicator
                  color={val || "unknown"}
                  pa={row?.production_area}
                  size="sm"
                  showImpact
                />
              ),
            },
            {
              key: "base_mab_tonnes", label: "MAB (t)", sortable: true, align: "right" as const,
              render: (val: any) => <span className="text-slate-300 font-mono">{(val || 0).toLocaleString()}</span>,
            },
            {
              key: "effective_mab_tonnes", label: "Effective MAB (t)", sortable: true, align: "right" as const,
              render: (val: any) => <span className="text-white font-mono">{(val || 0).toLocaleString()}</span>,
            },
            {
              key: "farms", label: "Farms", sortable: true, align: "right" as const,
              render: (val: any) => <span className="text-slate-300">{val}</span>,
            },
          ] as Column[]}
        />
      </GlassCard>

      {/* Simulate Change */}
      <GlassCard>
        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 text-amber-400" />
          {t("traffic_light.simulator")}
        </h2>
        <div className="flex flex-wrap items-end gap-4 mb-6">
          {/* PA Selector */}
          <div>
            <label className="block text-xs text-slate-400 mb-1">Production Area</label>
            <select
              value={selectedPa}
              onChange={(e) => setSelectedPa(Number(e.target.value))}
              className="bg-white/10 border border-white/20 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
            >
              {Array.from({ length: 13 }, (_, i) => i + 1).map((pa) => {
                const info = pas.find((p: any) => p.production_area === pa);
                return (
                  <option key={pa} value={pa} className="bg-slate-800">
                    PA {pa} - {info?.name || `Area ${pa}`}
                  </option>
                );
              })}
            </select>
          </div>

          {/* Color Selector */}
          <div>
            <label className="block text-xs text-slate-400 mb-1">Simulated Color</label>
            <div className="flex gap-2">
              {(["green", "yellow", "red"] as const).map((c) => {
                const s = COLOR_STYLES[c];
                const active = selectedColor === c;
                return (
                  <button
                    key={c}
                    onClick={() => setSelectedColor(c)}
                    className={`px-4 py-2 rounded-lg text-sm font-semibold transition-all border ${
                      active
                        ? `${s.bg} ${s.text} ${s.border} ring-2 ring-offset-1 ring-offset-slate-900 ring-${c === "green" ? "emerald" : c === "yellow" ? "amber" : "rose"}-500/50`
                        : "bg-white/5 text-slate-400 border-white/10 hover:bg-white/10"
                    }`}
                  >
                    <span className={`inline-block w-2 h-2 rounded-full ${s.dot} mr-2`} />
                    {c.charAt(0).toUpperCase() + c.slice(1)}
                  </button>
                );
              })}
            </div>
          </div>

          <OcButton onClick={runSimulation} disabled={simLoading}>
            {simLoading ? (
              <RefreshCw className="w-4 h-4 mr-1 animate-spin" />
            ) : (
              <ChevronRight className="w-4 h-4 mr-1" />
            )}
            Run Simulation
          </OcButton>
        </div>

        {/* Simulation Results */}
        {simulation && !simulation.error && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-4"
          >
            {/* Impact Summary */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-white/5 rounded-lg p-4">
                <p className="text-xs text-slate-400">Color Change</p>
                <div className="flex items-center gap-2 mt-1">
                  {colorBadge(simulation.current_color)}
                  <ChevronRight className="w-4 h-4 text-slate-500" />
                  {colorBadge(simulation.simulated_color)}
                </div>
              </div>
              <div className="bg-white/5 rounded-lg p-4">
                <p className="text-xs text-slate-400">MAB Change</p>
                <p className={`text-lg font-bold ${simulation.mab_change_pct > 0 ? "text-emerald-400" : simulation.mab_change_pct < 0 ? "text-rose-400" : "text-slate-300"}`}>
                  {impactArrow(simulation.mab_change_pct)} {simulation.mab_change_pct > 0 ? "+" : ""}{simulation.mab_change_pct}%
                </p>
                <p className="text-xs text-slate-500">
                  {(simulation.current_mab_tonnes || 0).toLocaleString()} &rarr; {(simulation.new_mab_tonnes || 0).toLocaleString()} t
                </p>
              </div>
              <div className="bg-white/5 rounded-lg p-4">
                <p className="text-xs text-slate-400">Production Impact</p>
                <p className={`text-lg font-bold ${simulation.production_impact_tonnes > 0 ? "text-emerald-400" : simulation.production_impact_tonnes < 0 ? "text-rose-400" : "text-slate-300"}`}>
                  {impactArrow(simulation.production_impact_tonnes)} {Math.abs(simulation.production_impact_tonnes || 0).toLocaleString()} t
                </p>
              </div>
              <div className="bg-white/5 rounded-lg p-4">
                <p className="text-xs text-slate-400">Revenue Impact</p>
                <p className={`text-lg font-bold ${simulation.revenue_impact_mnok > 0 ? "text-emerald-400" : simulation.revenue_impact_mnok < 0 ? "text-rose-400" : "text-slate-300"}`}>
                  {impactArrow(simulation.revenue_impact_mnok)} {formatNumber(Math.abs(simulation.revenue_impact_mnok || 0), locale, 1)} MNOK
                </p>
                <p className="text-xs text-slate-500">@ {simulation.spot_price_nok_kg} NOK/kg</p>
              </div>
            </div>

            {/* Reasoning */}
            <div className="bg-cyan-500/10 border border-cyan-500/20 rounded-lg p-4">
              <p className="text-sm text-cyan-300">{simulation.reasoning}</p>
              <p className="text-xs text-slate-500 mt-2">
                Effective date: {simulation.effective_date} | Farms affected: {simulation.farms_affected}
              </p>
            </div>

            {/* Affected Companies */}
            {simulation.affected_companies && simulation.affected_companies.length > 0 && (
              <DataTable
                title={t("traffic_light.companies_affected")}
                data={simulation.affected_companies}
                searchKeys={["company"]}
                exportFilename="affected_companies"
                compact
                columns={[
                  {
                    key: "company", label: "Company", sortable: true,
                    render: (val: any) => <span className="text-white font-medium">{val}</span>,
                  },
                  {
                    key: "farms", label: "Farms", sortable: true, align: "right" as const,
                    render: (val: any) => <span className="text-slate-300">{val}</span>,
                  },
                  {
                    key: "share_pct", label: "Share", sortable: true, align: "right" as const,
                    render: (val: any) => <span className="text-slate-300">{val}%</span>,
                  },
                  {
                    key: "impact_tonnes", label: "Impact (t)", sortable: true, align: "right" as const,
                    render: (val: any) => (
                      <span className={`font-mono ${val > 0 ? "text-emerald-400" : val < 0 ? "text-rose-400" : "text-slate-300"}`}>
                        {val > 0 ? "+" : ""}{val?.toLocaleString()}
                      </span>
                    ),
                  },
                  {
                    key: "revenue_impact_mnok", label: "Revenue (MNOK)", sortable: true, align: "right" as const,
                    render: (val: any) => (
                      <span className={`font-mono ${val > 0 ? "text-emerald-400" : val < 0 ? "text-rose-400" : "text-slate-300"}`}>
                        {val > 0 ? "+" : ""}{formatNumber(val, locale, 1)}
                      </span>
                    ),
                  },
                ] as Column[]}
              />
            )}
          </motion.div>
        )}

        {simulation?.error && (
          <div className="bg-rose-500/10 border border-rose-500/20 rounded-lg p-4 text-rose-300 text-sm">
            {simulation.error}
          </div>
        )}
      </GlassCard>

      {/* Color Legend */}
      <GlassCard>
        <h2 className="text-lg font-semibold text-white mb-4">Traffic Light System Explained</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <span className="w-4 h-4 rounded-full bg-emerald-400" />
              <span className="text-emerald-400 font-semibold">Green (+6% MAB)</span>
            </div>
            <p className="text-sm text-slate-300">
              Low lice impact on wild salmon. Production area may grow MAB capacity by 6%.
              Favorable for expansion and new stocking.
            </p>
          </div>
          <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <span className="w-4 h-4 rounded-full bg-amber-400" />
              <span className="text-amber-400 font-semibold">Yellow (0% change)</span>
            </div>
            <p className="text-sm text-slate-300">
              Moderate lice impact. MAB capacity frozen at current levels.
              Companies must maintain but cannot grow production.
            </p>
          </div>
          <div className="bg-rose-500/10 border border-rose-500/20 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <span className="w-4 h-4 rounded-full bg-rose-400" />
              <span className="text-rose-400 font-semibold">Red (-6% MAB)</span>
            </div>
            <p className="text-sm text-slate-300">
              High lice impact on wild salmon. Mandatory 6% MAB reduction.
              Producers must reduce stocking or accelerate harvest.
            </p>
          </div>
        </div>
        <div className="mt-4 text-xs text-slate-500">
          Assessments announced Q4, effective Q2 next year. System transitioning 2027-2029 to potentially include growth-based sustainability indicators.
        </div>
      </GlassCard>
    </div>
    </ErrorBoundary>
  );
}
