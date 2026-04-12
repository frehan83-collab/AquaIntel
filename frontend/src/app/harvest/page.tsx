"use client";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Timer,
  Search,
  Loader2,
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  Syringe,
  Clock,
  Fish,
  DollarSign,
  Building2,
  BarChart3,
  Thermometer,
} from "lucide-react";
import KPICard from "@/components/KPICard";
import GlassCard from "@/components/GlassCard";
import DataQualityBadge from "@/components/DataQualityBadge";
import ErrorBoundary from "@/components/ErrorBoundary";
import { OcButton } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { useApiError } from "@/lib/useApiError";
import { useTranslation } from "@/lib/i18n";

/* eslint-disable @typescript-eslint/no-explicit-any */

const ACTION_CONFIG: Record<string, { color: string; bg: string; Icon: any; label: string }> = {
  HARVEST_NOW: {
    color: "text-emerald-400",
    bg: "bg-emerald-500/10 border-emerald-500/20",
    Icon: CheckCircle2,
    label: "Harvest Now",
  },
  WAIT_1_WEEK: {
    color: "text-ocean-400",
    bg: "bg-ocean-500/10 border-ocean-500/20",
    Icon: Clock,
    label: "Wait",
  },
  TREAT_THEN_WAIT: {
    color: "text-amber-400",
    bg: "bg-amber-500/10 border-amber-500/20",
    Icon: Syringe,
    label: "Treat Then Wait",
  },
  ERROR: {
    color: "text-rose-400",
    bg: "bg-rose-500/10 border-rose-500/20",
    Icon: AlertTriangle,
    label: "Error",
  },
};

export default function HarvestPage() {
  const { t } = useTranslation();
  const handleError = useApiError();
  const [localityNo, setLocalityNo] = useState(10469);
  const [companyName, setCompanyName] = useState("");
  const [weeks, setWeeks] = useState(12);
  const [loading, setLoading] = useState(false);
  const [simLoading, setSimLoading] = useState(false);
  const [portLoading, setPortLoading] = useState(false);

  const [optimizeData, setOptimizeData] = useState<any>(null);
  const [simulateData, setSimulateData] = useState<any>(null);
  const [portfolioData, setPortfolioData] = useState<any>(null);
  const [activeTab, setActiveTab] = useState<"farm" | "portfolio">("farm");

  const fetchOptimize = async () => {
    setLoading(true);
    try {
      const data = await api.harvestOptimize(localityNo);
      setOptimizeData(data);
    } catch (e) {
      handleError("harvest_optimize")(e);
      setOptimizeData(null);
    }
    setLoading(false);
  };

  const fetchSimulate = async () => {
    setSimLoading(true);
    try {
      const data = await api.harvestSimulate(localityNo, weeks);
      setSimulateData(data);
    } catch (e) {
      handleError("harvest_simulate")(e);
      setSimulateData(null);
    }
    setSimLoading(false);
  };

  const fetchPortfolio = async () => {
    if (!companyName.trim()) return;
    setPortLoading(true);
    try {
      const data = await api.harvestPortfolio(companyName.trim());
      setPortfolioData(data);
    } catch (e) {
      handleError("harvest_portfolio")(e);
      setPortfolioData(null);
    }
    setPortLoading(false);
  };

  useEffect(() => {
    fetchOptimize();
    fetchSimulate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const rec = optimizeData?.recommendation;
  const state = optimizeData?.current_state;
  const rev = optimizeData?.revenue_projection;
  const actionCfg = rec ? ACTION_CONFIG[rec.action] || ACTION_CONFIG.ERROR : null;

  const trajectory = simulateData?.trajectory || [];
  const maxWeight = Math.max(...trajectory.map((t: any) => t.fish_weight_kg || 0), 1);
  const maxLice = Math.max(...trajectory.map((t: any) => t.lice_count || 0), 0.1);

  return (
    <ErrorBoundary fallbackTitle="Harvest Optimizer error">
    <div className="space-y-6 p-6">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between"
      >
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] flex items-center gap-3">
            <div className="p-2 rounded-xl bg-ocean-500/10">
              <Timer className="w-6 h-6 text-ocean-400" />
            </div>
            {t("harvest.title")}
          </h1>
          <p className="text-sm text-[var(--text-secondary)] mt-1">
            RL-based harvest timing using live growth, lice, and market data
          </p>
        </div>
        {optimizeData?.data_provenance && <DataQualityBadge provenance={optimizeData.data_provenance} />}
      </motion.div>

      {/* Tab Switcher */}
      <div className="flex gap-2">
        <OcButton
          variant={activeTab === "farm" ? "primary" : "ghost"}
          onClick={() => setActiveTab("farm")}
        >
          <Fish className="w-4 h-4 mr-2" /> Farm Analysis
        </OcButton>
        <OcButton
          variant={activeTab === "portfolio" ? "primary" : "ghost"}
          onClick={() => setActiveTab("portfolio")}
        >
          <Building2 className="w-4 h-4 mr-2" /> Portfolio View
        </OcButton>
      </div>

      {activeTab === "farm" && (
        <>
          {/* Farm Selector */}
          <GlassCard>
            <div className="flex items-center gap-2 mb-4">
              <Search className="w-5 h-5 text-ocean-400" />
              <h3 className="text-sm font-semibold text-[var(--text-primary)]">Farm Selector</h3>
            </div>
            <div className="flex flex-wrap items-end gap-4">
              <div>
                <label className="block text-xs text-[var(--text-secondary)] mb-1">
                  Locality Number
                </label>
                <input
                  type="number"
                  value={localityNo}
                  onChange={(e) => setLocalityNo(Number(e.target.value))}
                  className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-[var(--text-primary)] w-32"
                />
              </div>
              <div>
                <label className="block text-xs text-[var(--text-secondary)] mb-1">
                  Simulation Weeks
                </label>
                <input
                  type="number"
                  value={weeks}
                  onChange={(e) => setWeeks(Number(e.target.value))}
                  min={1}
                  max={52}
                  className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-[var(--text-primary)] w-24"
                />
              </div>
              <OcButton
                onClick={() => {
                  fetchOptimize();
                  fetchSimulate();
                }}
                disabled={loading}
              >
                {loading ? (
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                ) : (
                  <Search className="w-4 h-4 mr-2" />
                )}
                Analyze
              </OcButton>
            </div>
          </GlassCard>

          {/* KPI Cards */}
          {state && (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
              <KPICard
                label={t("harvest.expected_weight")}
                value={`${state.fish_weight_kg?.toFixed(2)} kg`}
                icon={Fish}
              />
              <KPICard
                label="Lice Count"
                value={state.lice_count?.toFixed(2)}
                icon={AlertTriangle}
                delta={state.lice_count > 0.4 ? "above threshold" : "normal range"}
                deltaType={state.lice_count > 0.4 ? "negative" : "positive"}
              />
              <KPICard
                label="Sea Temp"
                value={`${state.sea_temp_c?.toFixed(1)}\u00B0C`}
                icon={Thermometer}
              />
              <KPICard
                label="SSB Price"
                value={`NOK ${state.market_price_nok?.toFixed(1)}`}
                icon={DollarSign}
              />
              <KPICard
                label="Biomass"
                value={`${state.cage_biomass_tonnes?.toFixed(0)} t`}
                icon={BarChart3}
              />
              <KPICard
                label="MAB Headroom"
                value={`${state.days_to_mab_limit} days`}
                icon={Clock}
                delta={state.days_to_mab_limit < 30 ? "tight!" : "OK"}
                deltaType={state.days_to_mab_limit < 30 ? "negative" : "positive"}
              />
            </div>
          )}

          {/* Recommendation Card */}
          {rec && actionCfg && (
            <GlassCard>
              <div className="flex items-center gap-2 mb-4">
                <actionCfg.Icon className={`w-5 h-5 ${actionCfg.color}`} />
                <h3 className="text-sm font-semibold text-[var(--text-primary)]">Harvest Recommendation</h3>
              </div>
              <div className={`border rounded-xl p-4 ${actionCfg.bg}`}>
                <div className="flex items-center gap-3 mb-3">
                  <actionCfg.Icon className={`w-8 h-8 ${actionCfg.color}`} />
                  <div>
                    <h3 className={`text-xl font-bold ${actionCfg.color}`}>
                      {actionCfg.label}
                    </h3>
                    <p className="text-xs text-[var(--text-secondary)]">
                      Farm: {optimizeData?.locality_name || localityNo}
                    </p>
                  </div>
                </div>
                <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
                  {rec.reasoning}
                </p>
              </div>
            </GlassCard>
          )}

          {/* Revenue Projection */}
          {rev && (
            <GlassCard>
              <div className="flex items-center gap-2 mb-4">
                <DollarSign className="w-5 h-5 text-emerald-400" />
                <h3 className="text-sm font-semibold text-[var(--text-primary)]">{t("harvest.revenue_estimate")}</h3>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-white/5 rounded-xl p-4 border border-white/10">
                  <p className="text-xs text-[var(--text-secondary)]">Harvest Now</p>
                  <p className="text-lg font-bold text-[var(--text-primary)]">
                    NOK {rev.harvest_now_nok_per_fish?.toFixed(1)}/fish
                  </p>
                  <p className="text-sm text-[var(--text-secondary)]">
                    Total: {rev.harvest_now_total_mnok?.toFixed(1)} MNOK
                  </p>
                </div>
                <div className="bg-white/5 rounded-xl p-4 border border-white/10">
                  <p className="text-xs text-[var(--text-secondary)]">Harvest +4 Weeks</p>
                  <p className="text-lg font-bold text-[var(--text-primary)]">
                    NOK {rev.harvest_4w_nok_per_fish?.toFixed(1)}/fish
                  </p>
                  <p className="text-sm text-[var(--text-secondary)]">
                    Total: {rev.harvest_4w_total_mnok?.toFixed(1)} MNOK
                  </p>
                </div>
                <div className="bg-white/5 rounded-xl p-4 border border-white/10">
                  <p className="text-xs text-[var(--text-secondary)]">Waiting Uplift</p>
                  <p
                    className={`text-lg font-bold ${
                      (rev.difference_pct || 0) > 0
                        ? "text-emerald-400"
                        : "text-rose-400"
                    }`}
                  >
                    {(rev.difference_pct || 0) > 0 ? "+" : ""}
                    {rev.difference_pct?.toFixed(1)}%
                  </p>
                  <p className="text-sm text-[var(--text-secondary)]">
                    vs harvesting today
                  </p>
                </div>
              </div>
            </GlassCard>
          )}

          {/* Simulation Chart */}
          <GlassCard>
            <div className="flex items-center gap-2 mb-4">
              <BarChart3 className="w-5 h-5 text-ocean-400" />
              <h3 className="text-sm font-semibold text-[var(--text-primary)]">{weeks}-{t("harvest.optimal_week")}</h3>
            </div>
            {simLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-6 h-6 animate-spin text-ocean-400" />
                <span className="ml-2 text-sm text-[var(--text-secondary)]">Simulating...</span>
              </div>
            ) : trajectory.length > 1 ? (
              <div className="space-y-4">
                {/* SVG Chart: Weight + Lice */}
                <div className="relative">
                  <svg
                    viewBox={`0 0 ${Math.max(trajectory.length * 40, 200)} 180`}
                    className="w-full h-48"
                    preserveAspectRatio="none"
                  >
                    {/* Weight line (emerald) */}
                    <polyline
                      fill="none"
                      stroke="rgb(52, 211, 153)"
                      strokeWidth="2"
                      points={trajectory
                        .map(
                          (t: any, i: number) =>
                            `${i * 40 + 20},${160 - (t.fish_weight_kg / maxWeight) * 140}`
                        )
                        .join(" ")}
                    />
                    {/* Lice line (rose) */}
                    <polyline
                      fill="none"
                      stroke="rgb(251, 113, 133)"
                      strokeWidth="2"
                      strokeDasharray="4,4"
                      points={trajectory
                        .map(
                          (t: any, i: number) =>
                            `${i * 40 + 20},${160 - (t.lice_count / maxLice) * 140}`
                        )
                        .join(" ")}
                    />
                    {/* Harvest threshold line */}
                    <line
                      x1="0"
                      y1={160 - (5.0 / maxWeight) * 140}
                      x2={trajectory.length * 40}
                      y2={160 - (5.0 / maxWeight) * 140}
                      stroke="rgb(96, 165, 250)"
                      strokeWidth="1"
                      strokeDasharray="8,4"
                      opacity="0.5"
                    />
                    {/* Action markers */}
                    {trajectory.map((t: any, i: number) => {
                      if (t.action === "HARVEST_NOW")
                        return (
                          <circle
                            key={i}
                            cx={i * 40 + 20}
                            cy={160 - (t.fish_weight_kg / maxWeight) * 140}
                            r="5"
                            fill="rgb(52, 211, 153)"
                          />
                        );
                      if (t.action === "TREAT_THEN_WAIT")
                        return (
                          <circle
                            key={i}
                            cx={i * 40 + 20}
                            cy={160 - (t.fish_weight_kg / maxWeight) * 140}
                            r="4"
                            fill="rgb(251, 191, 36)"
                          />
                        );
                      return null;
                    })}
                    {/* X-axis labels */}
                    {trajectory.map((t: any, i: number) =>
                      i % 2 === 0 ? (
                        <text
                          key={`lbl-${i}`}
                          x={i * 40 + 20}
                          y="178"
                          textAnchor="middle"
                          className="text-[10px] fill-gray-400"
                        >
                          W{t.week}
                        </text>
                      ) : null
                    )}
                  </svg>
                  <div className="flex gap-4 mt-2 text-xs text-[var(--text-secondary)]">
                    <span className="flex items-center gap-1">
                      <span className="w-3 h-0.5 bg-emerald-400 inline-block" /> Weight (kg)
                    </span>
                    <span className="flex items-center gap-1">
                      <span className="w-3 h-0.5 bg-rose-400 inline-block" /> Lice
                    </span>
                    <span className="flex items-center gap-1">
                      <span className="w-3 h-0.5 bg-blue-400 inline-block opacity-50" /> Harvest Target (5kg)
                    </span>
                  </div>
                </div>

                {/* Trajectory Table */}
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-[var(--text-secondary)] border-b border-white/10">
                        <th className="px-2 py-1 text-left">Week</th>
                        <th className="px-2 py-1 text-right">Weight (kg)</th>
                        <th className="px-2 py-1 text-right">Lice</th>
                        <th className="px-2 py-1 text-right">Temp</th>
                        <th className="px-2 py-1 text-right">Biomass (t)</th>
                        <th className="px-2 py-1 text-left">Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {trajectory.map((t: any, i: number) => {
                        const aCfg = ACTION_CONFIG[t.action] || ACTION_CONFIG.ERROR;
                        return (
                          <tr
                            key={i}
                            className="border-b border-white/5 hover:bg-white/5"
                          >
                            <td className="px-2 py-1 text-[var(--text-primary)]">{t.week}</td>
                            <td className="px-2 py-1 text-right text-[var(--text-primary)]">
                              {t.fish_weight_kg?.toFixed(2)}
                            </td>
                            <td
                              className={`px-2 py-1 text-right ${
                                t.lice_count > 0.4
                                  ? "text-rose-400"
                                  : t.lice_count > 0.3
                                  ? "text-amber-400"
                                  : "text-[var(--text-primary)]"
                              }`}
                            >
                              {t.lice_count?.toFixed(3)}
                            </td>
                            <td className="px-2 py-1 text-right text-[var(--text-secondary)]">
                              {t.sea_temp_c?.toFixed(1)}
                            </td>
                            <td className="px-2 py-1 text-right text-[var(--text-secondary)]">
                              {t.cage_biomass_tonnes?.toFixed(0)}
                            </td>
                            <td className="px-2 py-1">
                              <span className={`text-xs font-medium ${aCfg.color}`}>
                                {t.action === "START" ? "---" : aCfg.label}
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              <p className="text-sm text-[var(--text-secondary)] py-8 text-center">
                No simulation data available. Enter a locality number and click Analyze.
              </p>
            )}
          </GlassCard>
        </>
      )}

      {/* Portfolio View */}
      {activeTab === "portfolio" && (
        <>
          <GlassCard>
            <div className="flex items-center gap-2 mb-4">
              <Building2 className="w-5 h-5 text-ocean-400" />
              <h3 className="text-sm font-semibold text-[var(--text-primary)]">Company Portfolio</h3>
            </div>
            <div className="flex flex-wrap items-end gap-4">
              <div>
                <label className="block text-xs text-[var(--text-secondary)] mb-1">
                  Company Name
                </label>
                <input
                  type="text"
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                  placeholder="e.g. Mowi, SalMar, Cermaq"
                  className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-[var(--text-primary)] w-56"
                />
              </div>
              <OcButton onClick={fetchPortfolio} disabled={portLoading || !companyName.trim()}>
                {portLoading ? (
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                ) : (
                  <Search className="w-4 h-4 mr-2" />
                )}
                Analyze Portfolio
              </OcButton>
            </div>
          </GlassCard>

          {portfolioData?.error && (
            <GlassCard>
              <p className="text-sm text-rose-400 py-4 text-center">
                {portfolioData.error}
              </p>
            </GlassCard>
          )}

          {portfolioData?.summary && !portfolioData.error && (
            <>
              {/* Portfolio KPIs */}
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
                <KPICard
                  label="Total Farms"
                  value={portfolioData.n_farms}
                  icon={Building2}
                />
                <KPICard
                  label="Harvest Now"
                  value={portfolioData.summary.harvest_now}
                  icon={CheckCircle2}
                  delta="farms ready"
                />
                <KPICard
                  label="Treat First"
                  value={portfolioData.summary.treat_then_wait}
                  icon={Syringe}
                />
                <KPICard
                  label="Wait"
                  value={portfolioData.summary.wait}
                  icon={Clock}
                />
                <KPICard
                  label="Current Rev"
                  value={`${portfolioData.summary.total_current_revenue_mnok?.toFixed(0)} MNOK`}
                  icon={DollarSign}
                />
                <KPICard
                  label="Revenue Uplift"
                  value={`${(portfolioData.summary.revenue_uplift_pct || 0) > 0 ? "+" : ""}${portfolioData.summary.revenue_uplift_pct?.toFixed(1)}%`}
                  icon={TrendingUp}
                  delta="if optimal timing"
                />
              </div>

              {/* Farm List */}
              <GlassCard>
                <div className="flex items-center gap-2 mb-4">
                  <Fish className="w-5 h-5 text-ocean-400" />
                  <h3 className="text-sm font-semibold text-[var(--text-primary)]">{portfolioData.company} Farms</h3>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-[var(--text-secondary)] border-b border-white/10">
                        <th className="px-2 py-2 text-left">Farm</th>
                        <th className="px-2 py-2 text-left">Action</th>
                        <th className="px-2 py-2 text-right">Weight (kg)</th>
                        <th className="px-2 py-2 text-right">Lice</th>
                        <th className="px-2 py-2 text-right">Price (NOK)</th>
                        <th className="px-2 py-2 text-right">Now (MNOK)</th>
                        <th className="px-2 py-2 text-right">+4w (MNOK)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(portfolioData.farms || []).map((f: any, i: number) => {
                        const aCfg = ACTION_CONFIG[f.action] || ACTION_CONFIG.ERROR;
                        return (
                          <tr
                            key={i}
                            className="border-b border-white/5 hover:bg-white/5"
                          >
                            <td className="px-2 py-2">
                              <div className="text-[var(--text-primary)] font-medium">
                                {f.name}
                              </div>
                              <div className="text-xs text-[var(--text-secondary)]">
                                #{f.locality_no}
                              </div>
                            </td>
                            <td className="px-2 py-2">
                              <span
                                className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${aCfg.bg} ${aCfg.color}`}
                              >
                                <aCfg.Icon className="w-3 h-3" />
                                {aCfg.label}
                              </span>
                            </td>
                            <td className="px-2 py-2 text-right text-[var(--text-primary)]">
                              {f.fish_weight_kg?.toFixed(2)}
                            </td>
                            <td
                              className={`px-2 py-2 text-right ${
                                f.lice_count > 0.4
                                  ? "text-rose-400"
                                  : f.lice_count > 0.3
                                  ? "text-amber-400"
                                  : "text-[var(--text-primary)]"
                              }`}
                            >
                              {f.lice_count?.toFixed(2)}
                            </td>
                            <td className="px-2 py-2 text-right text-[var(--text-secondary)]">
                              {f.price_nok?.toFixed(1)}
                            </td>
                            <td className="px-2 py-2 text-right text-[var(--text-primary)]">
                              {f.current_revenue_mnok?.toFixed(1)}
                            </td>
                            <td className="px-2 py-2 text-right text-emerald-400">
                              {f.projected_revenue_mnok?.toFixed(1)}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </GlassCard>
            </>
          )}

          {!portfolioData && !portLoading && (
            <GlassCard>
              <p className="text-sm text-[var(--text-secondary)] py-8 text-center">
                Enter a company name (e.g. Mowi, SalMar, Cermaq) and click Analyze Portfolio
                to see harvest recommendations across all farms.
              </p>
            </GlassCard>
          )}
        </>
      )}
    </div>
    </ErrorBoundary>
  );
}
