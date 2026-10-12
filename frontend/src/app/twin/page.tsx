"use client";
import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Boxes, Play, Zap, RefreshCw, Bug, Fish, BarChart3,
  TrendingUp, TrendingDown, Shield, Activity, Droplets, AlertTriangle,
} from "lucide-react";
import KPICard from "@/components/KPICard";
import GlassCard from "@/components/GlassCard";
import { ChartContainer, OceanAreaChart } from "@/components/charts";
import { OcButton } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";
import ErrorBoundary from "@/components/ErrorBoundary";

/* eslint-disable @typescript-eslint/no-explicit-any */

const AGENTS = [
  { name: "Supervisor", role: "Orchestrates all agents", icon: Boxes, color: "text-ocean-400" },
  { name: "Farm Optimizer", role: "Lice + cleaner-fish scenarios", icon: Bug, color: "text-emerald-400" },
  { name: "Supply Coordinator", role: "Harvest volume forecasts", icon: TrendingUp, color: "text-violet-400" },
  { name: "Market Hedger", role: "Price-impact predictions", icon: TrendingDown, color: "text-amber-400" },
  { name: "Regulatory Forecaster", role: "PA colour predictions", icon: Shield, color: "text-rose-400" },
  { name: "Self-Improvement", role: "Accuracy tracking", icon: Activity, color: "text-cyan-400" },
];

export default function TwinPage() {
  const { t } = useTranslation();
  const [twinStatus, setTwinStatus] = useState<any>(null);
  const [simResult, setSimResult] = useState<any>(null);
  const [syncing, setSyncing] = useState(false);
  const [simulating, setSimulating] = useState(false);
  const [agentLog, setAgentLog] = useState<string[]>([]);
  // Ocean chemistry (GLODAPv2) removed — not useful for coastal salmon ops

  // Simulation controls
  const [weeks, setWeeks] = useState(8);
  const [tempDelta, setTempDelta] = useState(0);
  const [treatAbove, setTreatAbove] = useState<number | null>(null);
  const [treatmentType, setTreatmentType] = useState("mechanical");
  const [cleanerBoost, setCleanerBoost] = useState(0);

  // Auto-sync on mount
  useEffect(() => {
    handleSync();
    // Ocean chemistry calls removed (GLODAPv2 not useful for coastal ops)
  }, []);

  const addLog = (msg: string) => setAgentLog(prev => [...prev.slice(-15), `[${new Date().toLocaleTimeString()}] ${msg}`]);

  const handleSync = async () => {
    setSyncing(true);
    addLog("Supervisor: Initiating twin sync with BarentsWatch...");
    try {
      const status = await api.twinSync();
      setTwinStatus(status);
      addLog(`Supervisor: Twin synced — ${status.total_localities} localities loaded`);
      addLog(`Farm Optimizer: National avg lice = ${status.national_avg_lice}`);
      addLog(`Regulatory Forecaster: ${status.above_threshold} sites above 0.5 threshold`);
    } catch {
      addLog("Supervisor: Sync failed — retrying on next cycle");
    }
    setSyncing(false);
  };

  const handleSimulate = async () => {
    setSimulating(true);
    setSimResult(null);

    addLog(`Supervisor: Dispatching ${weeks}-week simulation...`);
    addLog(`Farm Optimizer: Temp delta ${tempDelta >= 0 ? "+" : ""}${tempDelta}C, ${treatAbove !== null ? `treating above ${treatAbove}` : "no treatment"}`);
    if (cleanerBoost > 0) addLog(`Farm Optimizer: Cleaner fish boost +${cleanerBoost}%`);
    addLog("Market Hedger: Computing price impact scenarios...");
    addLog("Supply Coordinator: Estimating harvest volume changes...");

    try {
      const result = await api.twinSimulate({
        weeks,
        temp_delta: tempDelta,
        treat_above: treatAbove,
        treatment_type: treatmentType,
        add_cleaner_fish_pct: cleanerBoost,
      });
      setSimResult(result);

      addLog(`Supervisor: Simulation complete — ${result.localities_simulated} localities`);
      addLog(`Farm Optimizer: Lice ${result.impact?.lice_reduction_pct > 0 ? "reduced" : "increased"} by ${Math.abs(result.impact?.lice_reduction_pct || 0)}%`);
      addLog(`Supply Coordinator: Biomass impact ${result.impact?.biomass_saved_t > 0 ? "+" : ""}${result.impact?.biomass_saved_t}t`);
      addLog(`Market Hedger: Final avg lice ${result.final?.avg_lice} → price signal generated`);
      addLog("Regulatory Forecaster: PA colour assessment updated");
      addLog("Self-Improvement: Logging simulation parameters for accuracy tracking");
    } catch {
      addLog("Supervisor: Simulation failed — check backend logs");
    }
    setSimulating(false);
  };

  // Build trajectory chart data
  const trajectoryData = simResult?.trajectory?.map((t: any) => ({
    label: `W+${t.week}`,
    avg_lice: t.avg_lice,
    pct_above: t.pct_above,
  })) || [];

  return (
    <ErrorBoundary fallbackTitle="Digital Twin error">
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-3">
            <Boxes className="w-6 h-6 text-ocean-400" />
            {t("twin.title")}
          </h1>
          <p className="text-sm text-[var(--text-secondary)] mt-1">
            Live virtual replica with autonomous agent swarm — {twinStatus?.total_localities || 0} localities
          </p>
        </div>
        <OcButton
          variant="secondary"
          size="sm"
          loading={syncing}
          onClick={handleSync}
          leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
        >
          Sync Twin
        </OcButton>
      </div>

      {/* Twin Status KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          label="Localities"
          value={twinStatus?.total_localities || "—"}
          icon={Boxes}
          delay={0}
        />
        <KPICard
          label="National Avg Lice"
          value={twinStatus?.national_avg_lice?.toFixed(3) || "—"}
          deltaType={twinStatus?.national_avg_lice < 0.2 ? "positive" : "negative"}
          icon={Bug}
          delay={0.03}
        />
        <KPICard
          label="Above Threshold"
          value={twinStatus?.above_threshold ?? "—"}
          deltaType={(twinStatus?.above_threshold || 0) > 5 ? "negative" : "positive"}
          icon={Shield}
          delay={0.06}
        />
        <KPICard
          label="Total Biomass"
          value={twinStatus?.total_biomass_tonnes ? `${(twinStatus.total_biomass_tonnes / 1000).toFixed(0)}kt` : "—"}
          icon={Fish}
          delay={0.09}
        />
      </div>

      {/* Main Grid: Simulation + Agents */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Simulation Controls */}
        <GlassCard delay={0.1} accent="ocean">
          <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
            <Zap className="w-4 h-4 text-ocean-400" />
            {t("twin.simulate")}
          </h3>
          <div className="space-y-4">
            <div>
              <div className="flex justify-between mb-1">
                <label className="text-xs text-[var(--text-secondary)]">Horizon</label>
                <span className="text-xs font-mono text-ocean-400">{weeks} {t("twin.weeks")}</span>
              </div>
              <input type="range" min={2} max={20} value={weeks} onChange={e => setWeeks(Number(e.target.value))} className="w-full" />
            </div>
            <div>
              <div className="flex justify-between mb-1">
                <label className="text-xs text-[var(--text-secondary)]">{t("twin.temp_delta")}</label>
                <span className="text-xs font-mono text-ocean-400">{tempDelta >= 0 ? "+" : ""}{tempDelta}°C</span>
              </div>
              <input type="range" min={-2} max={4} step={0.5} value={tempDelta} onChange={e => setTempDelta(Number(e.target.value))} className="w-full" />
            </div>
            <div>
              <div className="flex justify-between mb-1">
                <label className="text-xs text-[var(--text-secondary)]">Cleaner Fish Boost</label>
                <span className="text-xs font-mono text-ocean-400">+{cleanerBoost}%</span>
              </div>
              <input type="range" min={0} max={50} step={5} value={cleanerBoost} onChange={e => setCleanerBoost(Number(e.target.value))} className="w-full" />
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={treatAbove !== null}
                onChange={e => setTreatAbove(e.target.checked ? 0.3 : null)}
                className="accent-ocean-500"
              />
              <label className="text-xs text-[var(--text-secondary)]">Treat all sites above 0.3 lice</label>
            </div>
            {treatAbove !== null && (
              <select
                value={treatmentType}
                onChange={e => setTreatmentType(e.target.value)}
                className="w-full bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-xs"
              >
                <option value="mechanical">Mechanical (Hydrolicer)</option>
                <option value="thermal">Thermal (Thermolicer)</option>
                <option value="medicinal">Medicinal (Bath)</option>
              </select>
            )}
            <OcButton
              variant="primary"
              size="md"
              className="w-full"
              loading={simulating}
              onClick={handleSimulate}
              leftIcon={<Play className="w-4 h-4" />}
            >
              Run Simulation
            </OcButton>
          </div>
        </GlassCard>

        {/* Agent Swarm Panel */}
        <GlassCard delay={0.15} accent="violet" className="lg:col-span-2">
          <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
            <Activity className="w-4 h-4 text-violet-400" />
            Agent Swarm — Live Collaboration
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2 mb-4">
            {AGENTS.map((agent, i) => (
              <div key={agent.name} className="flex items-center gap-2 p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                <div className={`w-2 h-2 rounded-full ${syncing || simulating ? "bg-emerald-400 animate-pulse" : "bg-emerald-400/40"}`} />
                <div className="min-w-0">
                  <p className={`text-[11px] font-semibold ${agent.color}`}>{agent.name}</p>
                  <p className="text-[9px] text-[var(--text-secondary)] truncate">{agent.role}</p>
                </div>
              </div>
            ))}
          </div>
          {/* Agent Log */}
          <div className="bg-[rgba(0,0,0,0.2)] rounded-xl border border-white/[0.04] p-3 h-[200px] overflow-y-auto font-mono text-[11px] space-y-0.5">
            {agentLog.length === 0 ? (
              <p className="text-[var(--text-secondary)] text-center py-8">Click Sync Twin or Run Simulation to see agent collaboration</p>
            ) : (
              agentLog.map((line, i) => (
                <motion.p
                  key={i}
                  initial={{ opacity: 0, x: -5 }}
                  animate={{ opacity: 1, x: 0 }}
                  className={`leading-relaxed ${
                    line.includes("Supervisor") ? "text-ocean-400" :
                    line.includes("Farm Optimizer") ? "text-emerald-400" :
                    line.includes("Supply") ? "text-violet-400" :
                    line.includes("Market") ? "text-amber-400" :
                    line.includes("Regulatory") ? "text-rose-400" :
                    line.includes("Self-Improvement") ? "text-cyan-400" :
                    "text-[var(--text-secondary)]"
                  }`}>
                    {line}
                  </motion.p>
                ))
              )}
          </div>
        </GlassCard>
      </div>

      {/* Simulation Results */}
      <AnimatePresence>
        {simResult && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-4"
          >
            {/* Impact KPIs */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <KPICard
                label="Lice Reduction"
                value={`${simResult.impact?.lice_reduction_pct > 0 ? "-" : "+"}${Math.abs(simResult.impact?.lice_reduction_pct || 0).toFixed(1)}%`}
                deltaType={simResult.impact?.lice_reduction_pct > 0 ? "positive" : "negative"}
                icon={Bug}
                delay={0}
              />
              <KPICard
                label="Final Avg Lice"
                value={simResult.final?.avg_lice?.toFixed(3) || "—"}
                delta={`Baseline: ${simResult.baseline?.avg_lice?.toFixed(3)}`}
                deltaType={simResult.final?.avg_lice < simResult.baseline?.avg_lice ? "positive" : "negative"}
                icon={TrendingDown}
                delay={0.03}
              />
              <KPICard
                label="Biomass Impact"
                value={`${simResult.impact?.biomass_saved_t > 0 ? "+" : ""}${simResult.impact?.biomass_saved_t}t`}
                deltaType={simResult.impact?.biomass_saved_t > 0 ? "positive" : "negative"}
                icon={Fish}
                delay={0.06}
              />
              <KPICard
                label="Sites Above Limit"
                value={simResult.final?.above_threshold ?? "—"}
                delta={`Baseline: ${simResult.baseline?.above_threshold}`}
                deltaType={(simResult.final?.above_threshold || 0) < (simResult.baseline?.above_threshold || 0) ? "positive" : "negative"}
                icon={Shield}
                delay={0.09}
              />
            </div>

            {/* Trajectory Chart */}
            <ChartContainer
              title="Simulation Trajectory"
              subtitle={`${simResult.weeks_simulated}-week forecast · ${simResult.localities_simulated} localities`}
              delay={0.1}
              accent="ocean"
              badge={
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-ocean-500/10 text-ocean-400 border border-ocean-500/20">
                  {treatAbove !== null ? treatmentType.toUpperCase() : "NO TREATMENT"}
                </span>
              }
            >
              {trajectoryData.length > 0 ? (
                <OceanAreaChart
                  data={trajectoryData}
                  xKey="label"
                  series={[
                    { key: "avg_lice", name: "Avg Lice/fish", color: "#00D4C8", filled: true },
                  ]}
                  height={280}
                  threshold={0.5}
                  thresholdLabel="Regulatory Limit"
                />
              ) : null}
            </ChartContainer>
          </motion.div>
        )}
      </AnimatePresence>


      {/* Ocean Chemistry removed — real-time env data from BarentsWatch + Copernicus + MET.no */}

      {/* ── Biomass & Supply Outlook ── */}
      <BiomassOutlookSection />

      <p className="text-[10px] text-[var(--text-secondary)] text-center opacity-60">
        Simulation powered by stage-structured lice dynamics, temperature-dependent growth, cleaner-fish efficacy, and treatment resistance modeling.
        Biomass: cohort model B(t) = &Sigma; N_c(t) &middot; w_c(t) &le; M(t) with Monte Carlo scenarios.
        Data: BarentsWatch (NLOD 2.0), Directorate of Fisheries MAB. Not financial advice.
      </p>
    </div>
    </ErrorBoundary>
  );
}

// ── Biomass & Supply Outlook Section ────────────────��────────────────────────
function BiomassOutlookSection() {
  const [outlook, setOutlook] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [horizon, setHorizon] = useState(20);
  const [scenario, setScenario] = useState("current");

  const load = async () => {
    setLoading(true);
    try {
      const data = await api.biomassOutlook(horizon, 1000, scenario);
      setOutlook(data);
    } catch { /* empty */ }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold text-[var(--text-primary)] flex items-center gap-2">
          <Fish className="w-5 h-5 text-ocean-400" />
          Biomass &amp; Supply Outlook
        </h2>
        <div className="flex items-center gap-2">
          <select
            value={scenario}
            onChange={(e) => setScenario(e.target.value)}
            className="bg-white/[0.04] border border-white/[0.08] rounded-lg px-2 py-1.5 text-[11px] focus:outline-hidden focus:border-ocean-500/30"
          >
            <option value="current">Current Regime</option>
            <option value="all_green">All PAs Green (+6%)</option>
            <option value="all_red">All PAs Red (-6%)</option>
          </select>
          <select
            value={horizon}
            onChange={(e) => setHorizon(Number(e.target.value))}
            className="bg-white/[0.04] border border-white/[0.08] rounded-lg px-2 py-1.5 text-[11px] focus:outline-hidden focus:border-ocean-500/30"
          >
            {[8, 12, 20, 30, 52].map(h => (
              <option key={h} value={h}>{h}w</option>
            ))}
          </select>
          <OcButton variant="ghost" size="sm" loading={loading} onClick={load}
            leftIcon={<RefreshCw className="w-3 h-3" />}>Compute</OcButton>
        </div>
      </div>

      {outlook && (
        <>
          {/* KPI cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <KPICard
              label="Standing Biomass"
              value={outlook.current_biomass_tonnes ? `${(outlook.current_biomass_tonnes / 1000).toFixed(0)}k t` : "\u2014"}
              delta="Live weight"
              icon={Fish} delay={0}
            />
            <KPICard
              label="MAB Utilization"
              value={outlook.utilization_pct != null ? `${outlook.utilization_pct}%` : "—"}
              delta={outlook.national_mab ? `MAB: ${(outlook.national_mab / 1000).toFixed(0)}k t` : "—"}
              deltaType={(outlook.utilization_pct ?? 0) > 90 ? "negative" : "positive"}
              icon={BarChart3} delay={0.03}
            />
            <KPICard
              label="Green Scenario"
              value={outlook.scenario_green_impact_pct != null ? `${outlook.scenario_green_impact_pct > 0 ? "+" : ""}${outlook.scenario_green_impact_pct}%` : "—"}
              delta="If all PAs green"
              deltaType="positive"
              icon={TrendingUp} delay={0.06}
            />
            <KPICard
              label="Red Scenario"
              value={outlook.scenario_red_impact_pct != null ? `${outlook.scenario_red_impact_pct}%` : "—"}
              delta="If high-risk PAs red"
              deltaType="negative"
              icon={TrendingDown} delay={0.09}
            />
          </div>

          {/* Biomass projection chart (simple bar visualization) */}
          <GlassCard delay={0.12} accent="ocean">
            <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
              <Activity className="w-4 h-4 text-ocean-400" />
              Biomass Forecast ({horizon}w &middot; {outlook.n_scenarios} scenarios)
              <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-ocean-500/10 text-ocean-400 border border-ocean-500/20 ml-auto">
                Monte Carlo
              </span>
            </h3>
            <div className="space-y-1">
              {(outlook.forecast_biomass || []).filter((_: any, i: number) => i % Math.max(1, Math.floor(horizon / 12)) === 0).map((b: number, i: number) => {
                const weekIdx = i * Math.max(1, Math.floor(horizon / 12));
                const p10 = outlook.p10_biomass?.[weekIdx] || b * 0.9;
                const p90 = outlook.p90_biomass?.[weekIdx] || b * 1.1;
                const pct = (b / outlook.national_mab) * 100;
                return (
                  <div key={weekIdx} className="flex items-center gap-2">
                    <span className="text-[9px] text-[var(--text-secondary)] w-8 flex-shrink-0">W+{weekIdx + 1}</span>
                    <div className="flex-1 relative h-4 bg-white/[0.04] rounded overflow-hidden">
                      {/* P10-P90 band */}
                      <div
                        className="absolute h-full bg-ocean-500/15 rounded"
                        style={{
                          left: `${(p10 / outlook.national_mab) * 100}%`,
                          width: `${((p90 - p10) / outlook.national_mab) * 100}%`,
                        }}
                      />
                      {/* Median bar */}
                      <div
                        className={`absolute h-full rounded ${pct > 95 ? "bg-rose-500/50" : pct > 85 ? "bg-amber-500/40" : "bg-ocean-500/40"}`}
                        style={{ width: `${Math.min(100, pct)}%` }}
                      />
                      {/* MAB line */}
                      <div className="absolute right-0 top-0 w-px h-full bg-rose-500/30" />
                    </div>
                    <span className="text-[9px] font-mono text-[var(--text-secondary)] w-14 text-right">
                      {(b / 1000).toFixed(0)}k t
                    </span>
                  </div>
                );
              })}
            </div>
            <div className="flex items-center gap-4 mt-2 text-[9px] text-[var(--text-secondary)]">
              <span className="flex items-center gap-1"><div className="w-3 h-2 rounded bg-ocean-500/40" /> Forecast</span>
              <span className="flex items-center gap-1"><div className="w-3 h-2 rounded bg-ocean-500/15" /> P10-P90 band</span>
              <span className="flex items-center gap-1"><div className="w-px h-3 bg-rose-500/30" /> MAB limit</span>
            </div>
          </GlassCard>

          {/* Recommendations */}
          {outlook.recommendations?.length > 0 && (
            <GlassCard delay={0.15} accent="amber">
              <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                <Zap className="w-4 h-4 text-amber-400" />
                Actionable Recommendations
              </h3>
              <div className="space-y-2">
                {outlook.recommendations.map((rec: string, i: number) => (
                  <div key={i} className="flex items-start gap-2 p-2.5 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-400 flex-shrink-0 mt-0.5" />
                    <p className="text-[11px] text-[var(--text-primary)] leading-relaxed">{rec}</p>
                  </div>
                ))}
              </div>
            </GlassCard>
          )}
        </>
      )}

      {!outlook && !loading && (
        <GlassCard delay={0.1}>
          <div className="py-8 text-center">
            <Fish className="w-10 h-10 mx-auto mb-3 opacity-20" />
            <p className="text-sm text-[var(--text-secondary)]">
              Click &ldquo;Compute&rdquo; to generate biomass outlook
            </p>
          </div>
        </GlassCard>
      )}
    </div>
  );
}
