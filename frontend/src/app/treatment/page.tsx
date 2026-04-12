"use client";
import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import {
  Syringe,
  Search,
  Loader2,
  DollarSign,
  Shield,
  Clock,
  Network,
  TrendingDown,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  BarChart3,
  Calculator,
  Star,
} from "lucide-react";
import KPICard from "@/components/KPICard";
import GlassCard from "@/components/GlassCard";
import { OcButton } from "@/components/ui/Button";
import InteractiveChart, { DataPoint } from "@/components/InteractiveChart";
import { api } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";
import ErrorBoundary from "@/components/ErrorBoundary";
import DataQualityBadge from "@/components/DataQualityBadge";

/* eslint-disable @typescript-eslint/no-explicit-any */

const TREATMENT_KEYS = ["mechanical", "thermal", "medicinal_bath", "medicinal_feed", "cleaner_fish"];
const REGULATORY_LIMIT = 0.5;

export default function TreatmentPage() {
  const { t } = useTranslation();
  const [localityNo, setLocalityNo] = useState(10469);
  const [budgetInput, setBudgetInput] = useState("");
  const [selectedPa, setSelectedPa] = useState(3);
  const [loading, setLoading] = useState(false);

  const [optimizeData, setOptimizeData] = useState<any>(null);
  const [compareData, setCompareData] = useState<any>(null);
  const [networkData, setNetworkData] = useState<any>(null);
  const [costBenefitData, setCostBenefitData] = useState<any>(null);
  const [selectedTreatment, setSelectedTreatment] = useState("mechanical");

  // Cost comparison calculator state
  const [ccBiomass, setCcBiomass] = useState(500);
  const [ccLiceLevel, setCcLiceLevel] = useState(0.5);
  const [ccData, setCcData] = useState<any>(null);
  const [ccLoading, setCcLoading] = useState(false);

  const fetchAll = async () => {
    setLoading(true);
    const budget = budgetInput ? parseFloat(budgetInput) : undefined;
    try {
      const [opt, cmp, net] = await Promise.allSettled([
        api.treatmentOptimize(localityNo, budget),
        api.treatmentCompare(localityNo),
        api.treatmentNetworkSchedule(selectedPa),
      ]);
      setOptimizeData(opt.status === "fulfilled" ? opt.value : null);
      setCompareData(cmp.status === "fulfilled" ? cmp.value : null);
      setNetworkData(net.status === "fulfilled" ? net.value : null);
    } catch {
      /* swallow */
    }
    setLoading(false);
  };

  const fetchCostBenefit = async (treatmentType: string) => {
    setSelectedTreatment(treatmentType);
    try {
      const data = await api.treatmentCostBenefit(localityNo, treatmentType);
      setCostBenefitData(data);
    } catch {
      setCostBenefitData(null);
    }
  };

  const fetchCostComparison = useCallback(async () => {
    setCcLoading(true);
    try {
      const data = await api.treatmentCostComparison(ccBiomass, ccLiceLevel, localityNo);
      setCcData(data);
    } catch {
      setCcData(null);
    }
    setCcLoading(false);
  }, [ccBiomass, ccLiceLevel, localityNo]);

  useEffect(() => {
    fetchAll();
    fetchCostComparison();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const rec = optimizeData?.recommendation;
  const treatments = compareData?.treatments || [];

  const urgencyColor: Record<string, string> = {
    immediate: "text-rose-400",
    high: "text-orange-400",
    medium: "text-amber-400",
    low: "text-emerald-400",
  };

  const priorityBadge = (p: number) => {
    const styles: Record<number, string> = {
      1: "bg-rose-500/20 text-rose-300",
      2: "bg-orange-500/20 text-orange-300",
      3: "bg-amber-500/20 text-amber-300",
      4: "bg-emerald-500/20 text-emerald-300",
    };
    const labels: Record<number, string> = {
      1: "Critical",
      2: "High",
      3: "Monitor",
      4: "Low",
    };
    return (
      <span className={`px-2 py-0.5 rounded text-xs font-medium ${styles[p] || "bg-slate-500/20 text-slate-300"}`}>
        {labels[p] || `P${p}`}
      </span>
    );
  };

  return (
    <ErrorBoundary fallbackTitle="Treatment error">
    <div className="space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Syringe className="w-7 h-7 text-cyan-400" />
          {t("nav.treatment_optimizer")}
          <DataQualityBadge quality="live" source="BarentsWatch + Treatment DB" />
        </h1>
        <p className="text-slate-400 mt-1">
          Optimize treatment timing, compare methods, and coordinate PA-wide schedules using live lice and temperature data.
        </p>
      </motion.div>

      {/* Controls */}
      <GlassCard>
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <label className="block text-xs text-slate-400 mb-1">Locality Number</label>
            <input
              type="number"
              value={localityNo}
              onChange={(e) => setLocalityNo(Number(e.target.value))}
              className="bg-slate-800 border border-slate-600 rounded px-3 py-2 text-white w-32 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Budget (NOK, optional)</label>
            <input
              type="number"
              value={budgetInput}
              onChange={(e) => setBudgetInput(e.target.value)}
              placeholder="No limit"
              className="bg-slate-800 border border-slate-600 rounded px-3 py-2 text-white w-36 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Production Area (PA)</label>
            <select
              value={selectedPa}
              onChange={(e) => setSelectedPa(Number(e.target.value))}
              className="bg-slate-800 border border-slate-600 rounded px-3 py-2 text-white w-28 text-sm"
            >
              {Array.from({ length: 13 }, (_, i) => i + 1).map((pa) => (
                <option key={pa} value={pa}>PA {pa}</option>
              ))}
            </select>
          </div>
          <OcButton onClick={fetchAll} disabled={loading}>
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
            {loading ? "Analyzing..." : "Optimize"}
          </OcButton>
        </div>
      </GlassCard>

      {/* Loading skeleton */}
      {loading && (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 text-cyan-400 animate-spin" />
          <span className="ml-3 text-slate-400">Fetching live data and computing optimal strategy...</span>
        </div>
      )}

      {!loading && optimizeData && !optimizeData.error && (
        <>
          {/* KPI Cards */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <KPICard
              label="Current Lice"
              value={optimizeData.current_lice?.toFixed(3)}
              delta="adult female/fish"
              deltaType={optimizeData.current_lice >= 0.5 ? "negative" : optimizeData.current_lice >= 0.2 ? "neutral" : "positive"}
              icon={TrendingDown}
            />
            <KPICard
              label="SST"
              value={`${optimizeData.current_sst_c?.toFixed(1)}\u00B0C`}
              delta="sea surface temp"
              icon={BarChart3}
            />
            <KPICard
              label="Urgency"
              value={rec?.urgency?.toUpperCase() || "N/A"}
              delta={`W${rec?.optimal_week || "?"} target`}
              deltaType={rec?.urgency === "immediate" || rec?.urgency === "high" ? "negative" : "neutral"}
              icon={AlertTriangle}
            />
            <KPICard
              label="Weeks to Limit"
              value={rec?.weeks_until_limit ?? "N/A"}
              delta="regulatory 0.5 lice"
              deltaType={rec?.weeks_until_limit <= 2 ? "negative" : rec?.weeks_until_limit <= 4 ? "neutral" : "positive"}
              icon={Clock}
            />
            <KPICard
              label="Est. Cost"
              value={`${((rec?.projected_cost_nok || 0) / 1000).toFixed(0)}k NOK`}
              delta="treatment cost"
              icon={DollarSign}
            />
            <KPICard
              label="Cleaner Fish"
              value={optimizeData.has_cleaner_fish ? "Yes" : "No"}
              delta="deployed"
              deltaType={optimizeData.has_cleaner_fish ? "positive" : "neutral"}
              icon={Shield}
            />
          </div>

          {/* Timing Recommendation */}
          <GlassCard>
            <h2 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
              <Clock className="w-5 h-5 text-cyan-400" />
              Timing Recommendation
            </h2>
            {rec && (
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <span className="text-slate-400 text-sm">Optimal week:</span>
                  <span className="text-white font-bold text-lg">W{rec.optimal_week} {rec.optimal_year}</span>
                  <span className={`text-sm font-medium ${urgencyColor[rec.urgency] || "text-slate-300"}`}>
                    ({rec.urgency})
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-slate-400 text-sm">Recommended:</span>
                  <span className="text-cyan-300 font-medium">{rec.treatment}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-slate-400 text-sm">Projected lice at treatment:</span>
                  <span className="text-white">{rec.projected_lice_at_treatment?.toFixed(4)}</span>
                </div>
                {optimizeData.budget_nok && (
                  <div className="flex items-center gap-3">
                    <span className="text-slate-400 text-sm">Within budget:</span>
                    {optimizeData.within_budget ? (
                      <span className="text-emerald-400 flex items-center gap-1"><CheckCircle2 className="w-4 h-4" /> Yes</span>
                    ) : (
                      <span className="text-rose-400 flex items-center gap-1"><XCircle className="w-4 h-4" /> Over budget</span>
                    )}
                  </div>
                )}
                <p className="text-slate-300 text-sm mt-2 bg-slate-800/50 rounded p-3">{rec.reasoning}</p>
              </div>
            )}
          </GlassCard>

          {/* Lice Trajectory Chart (SVG) */}
          {optimizeData.lice_trajectory && (
            <GlassCard>
              <h2 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
                <TrendingDown className="w-5 h-5 text-cyan-400" />
                Projected Lice Trajectory (No Treatment)
              </h2>
              <div className="overflow-x-auto">
                <svg viewBox="0 0 600 200" className="w-full h-48">
                  {/* Regulatory limit line */}
                  {(() => {
                    const traj = optimizeData.lice_trajectory as number[];
                    const maxVal = Math.max(...traj, REGULATORY_LIMIT) * 1.1;
                    const yScale = (v: number) => 180 - (v / maxVal) * 160;
                    const xStep = 560 / Math.max(traj.length - 1, 1);
                    const limitY = yScale(REGULATORY_LIMIT);

                    return (
                      <>
                        <line x1={30} y1={limitY} x2={590} y2={limitY} stroke="#f43f5e" strokeWidth={1} strokeDasharray="6,3" />
                        <text x={592} y={limitY + 4} fill="#f43f5e" fontSize={9}>0.5 limit</text>
                        {/* Trajectory line */}
                        <polyline
                          fill="none"
                          stroke="#22d3ee"
                          strokeWidth={2}
                          points={traj.map((v, i) => `${30 + i * xStep},${yScale(v)}`).join(" ")}
                        />
                        {/* Dots */}
                        {traj.map((v, i) => (
                          <circle key={i} cx={30 + i * xStep} cy={yScale(v)} r={3} fill={v >= REGULATORY_LIMIT ? "#f43f5e" : "#22d3ee"} />
                        ))}
                        {/* Week labels */}
                        {traj.map((_, i) => (
                          i % 2 === 0 && <text key={`l${i}`} x={30 + i * xStep} y={196} fill="#94a3b8" fontSize={9} textAnchor="middle">+{i}w</text>
                        ))}
                      </>
                    );
                  })()}
                </svg>
              </div>
            </GlassCard>
          )}
        </>
      )}

      {/* Error state */}
      {!loading && optimizeData?.error && (
        <GlassCard>
          <p className="text-rose-400">{optimizeData.error}</p>
        </GlassCard>
      )}

      {/* Treatment Comparison Table */}
      {!loading && treatments.length > 0 && (
        <GlassCard>
          <h2 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-cyan-400" />
            Treatment Comparison (5 Methods)
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-slate-400 border-b border-slate-700">
                  <th className="text-left py-2 px-2">Method</th>
                  <th className="text-right py-2 px-2">Efficacy</th>
                  <th className="text-right py-2 px-2">Mortality</th>
                  <th className="text-right py-2 px-2">Cost/fish</th>
                  <th className="text-right py-2 px-2">Total Cost</th>
                  <th className="text-right py-2 px-2">Recovery</th>
                  <th className="text-right py-2 px-2">Post-Lice</th>
                  <th className="text-right py-2 px-2">ROI Score</th>
                  <th className="text-center py-2 px-2">Suitable</th>
                  <th className="text-center py-2 px-2">Action</th>
                </tr>
              </thead>
              <tbody>
                {treatments.map((t: any) => (
                  <tr
                    key={t.key}
                    className={`border-b border-slate-800 hover:bg-slate-800/40 ${!t.suitable ? "opacity-50" : ""}`}
                  >
                    <td className="py-2 px-2 text-white font-medium">{t.name}</td>
                    <td className="py-2 px-2 text-right text-cyan-300">{t.efficacy_pct}%</td>
                    <td className="py-2 px-2 text-right text-orange-300">{t.mortality_pct}%</td>
                    <td className="py-2 px-2 text-right text-slate-300">{t.cost_per_fish_nok} NOK</td>
                    <td className="py-2 px-2 text-right text-slate-300">{(t.total_cost_nok / 1000).toFixed(0)}k</td>
                    <td className="py-2 px-2 text-right text-slate-300">{t.recovery_weeks}w</td>
                    <td className="py-2 px-2 text-right text-emerald-300">{t.post_treatment_lice?.toFixed(4)}</td>
                    <td className="py-2 px-2 text-right font-bold text-amber-300">{t.roi_score?.toFixed(3)}</td>
                    <td className="py-2 px-2 text-center">
                      {t.suitable ? (
                        <CheckCircle2 className="w-4 h-4 text-emerald-400 mx-auto" />
                      ) : (
                        <span className="text-xs text-rose-400" title={t.unsuitable_reason}>
                          <XCircle className="w-4 h-4 mx-auto" />
                        </span>
                      )}
                    </td>
                    <td className="py-2 px-2 text-center">
                      <button
                        onClick={() => fetchCostBenefit(t.key)}
                        className="text-xs text-cyan-400 hover:text-cyan-300 underline"
                      >
                        Analyze
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {treatments.some((t: any) => !t.suitable) && (
            <p className="text-xs text-slate-500 mt-2">
              Greyed-out methods are unsuitable at current SST or conditions.
              {treatments.filter((t: any) => !t.suitable).map((t: any) => (
                <span key={t.key} className="block text-rose-400/70 mt-0.5">{t.name}: {t.unsuitable_reason}</span>
              ))}
            </p>
          )}
        </GlassCard>
      )}

      {/* Cost-Benefit Analysis */}
      {costBenefitData && !costBenefitData.error && (
        <GlassCard>
          <h2 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
            <DollarSign className="w-5 h-5 text-cyan-400" />
            Cost-Benefit: {costBenefitData.treatment_name}
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <div className="bg-slate-800/50 rounded p-3">
              <div className="text-xs text-slate-400">Treatment Cost</div>
              <div className="text-lg font-bold text-white">{(costBenefitData.treatment_cost_nok / 1000).toFixed(0)}k NOK</div>
            </div>
            <div className="bg-slate-800/50 rounded p-3">
              <div className="text-xs text-slate-400">Mortality</div>
              <div className="text-lg font-bold text-orange-300">{costBenefitData.expected_mortality_pct}% ({costBenefitData.expected_mortality_fish} fish)</div>
            </div>
            <div className="bg-slate-800/50 rounded p-3">
              <div className="text-xs text-slate-400">Regulatory Risk Avoided</div>
              <div className="text-lg font-bold text-emerald-300">{(costBenefitData.regulatory_risk_cost_nok / 1000).toFixed(0)}k NOK</div>
            </div>
            <div className="bg-slate-800/50 rounded p-3">
              <div className="text-xs text-slate-400">Net Benefit (ROI)</div>
              <div className={`text-lg font-bold ${costBenefitData.net_benefit_nok >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                {costBenefitData.net_benefit_nok >= 0 ? "+" : ""}{(costBenefitData.net_benefit_nok / 1000).toFixed(0)}k NOK ({costBenefitData.roi_ratio}x)
              </div>
            </div>
          </div>

          {/* Baseline vs Treated trajectory chart */}
          {costBenefitData.baseline_trajectory && costBenefitData.treated_trajectory && (
            <div className="overflow-x-auto">
              <div className="flex items-center gap-4 mb-2 text-xs text-slate-400">
                <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-rose-400 inline-block" /> No treatment</span>
                <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-emerald-400 inline-block" /> With {costBenefitData.treatment_name?.split("(")[0]?.trim()}</span>
                <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-rose-400/50 inline-block border-dashed" /> 0.5 limit</span>
              </div>
              <svg viewBox="0 0 600 200" className="w-full h-48">
                {(() => {
                  const base = costBenefitData.baseline_trajectory as number[];
                  const treated = costBenefitData.treated_trajectory as number[];
                  const labels = costBenefitData.weeks_labels as string[];
                  const all = [...base, ...treated, REGULATORY_LIMIT];
                  const maxVal = Math.max(...all) * 1.1;
                  const yScale = (v: number) => 180 - (v / maxVal) * 160;
                  const n = Math.max(base.length, treated.length);
                  const xStep = 560 / Math.max(n - 1, 1);
                  const limitY = yScale(REGULATORY_LIMIT);

                  return (
                    <>
                      <line x1={30} y1={limitY} x2={590} y2={limitY} stroke="#f43f5e" strokeWidth={1} strokeDasharray="6,3" opacity={0.5} />
                      {/* Baseline */}
                      <polyline
                        fill="none"
                        stroke="#f43f5e"
                        strokeWidth={2}
                        points={base.map((v, i) => `${30 + i * xStep},${yScale(v)}`).join(" ")}
                      />
                      {/* Treated */}
                      <polyline
                        fill="none"
                        stroke="#34d399"
                        strokeWidth={2}
                        points={treated.map((v, i) => `${30 + i * xStep},${yScale(v)}`).join(" ")}
                      />
                      {/* Labels */}
                      {labels?.map((lbl, i) => (
                        i % 2 === 0 && <text key={`l${i}`} x={30 + i * xStep} y={196} fill="#94a3b8" fontSize={9} textAnchor="middle">{lbl}</text>
                      ))}
                    </>
                  );
                })()}
              </svg>
            </div>
          )}
        </GlassCard>
      )}

      {/* ═══════════════════════════════════════════════════════════════ */}
      {/* Cost Comparison Calculator                                     */}
      {/* ═══════════════════════════════════════════════════════════════ */}
      <GlassCard>
        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Calculator className="w-5 h-5 text-cyan-400" />
          Cost Comparison Calculator
        </h2>

        {/* Sliders */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-4">
          <div>
            <label className="block text-xs text-slate-400 mb-1">
              Biomass: <span className="text-white font-medium">{ccBiomass} tonnes</span>
            </label>
            <input
              type="range"
              min={100}
              max={2000}
              step={50}
              value={ccBiomass}
              onChange={(e) => setCcBiomass(Number(e.target.value))}
              className="w-full accent-cyan-400"
            />
            <div className="flex justify-between text-[10px] text-slate-500 mt-0.5">
              <span>100t</span><span>500t</span><span>1000t</span><span>1500t</span><span>2000t</span>
            </div>
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">
              Current Lice Level: <span className="text-white font-medium">{ccLiceLevel.toFixed(1)} adult female/fish</span>
            </label>
            <input
              type="range"
              min={0.1}
              max={5.0}
              step={0.1}
              value={ccLiceLevel}
              onChange={(e) => setCcLiceLevel(Number(e.target.value))}
              className="w-full accent-cyan-400"
            />
            <div className="flex justify-between text-[10px] text-slate-500 mt-0.5">
              <span>0.1</span>
              <span className="text-amber-400">0.5 (limit)</span>
              <span>2.5</span>
              <span>5.0</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3 mb-6">
          <OcButton onClick={fetchCostComparison} disabled={ccLoading}>
            {ccLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Calculator className="w-4 h-4" />}
            {ccLoading ? "Calculating..." : "Calculate"}
          </OcButton>
          {ccData && (
            <span className="text-xs text-slate-500">
              SST: {ccData.inputs?.sea_temp_c}&deg;C | Fish: {(ccData.inputs?.fish_count || 0).toLocaleString()} |
              Avoided loss (4w): {((ccData.avoided_loss_4w_nok || 0) / 1000).toFixed(0)}k NOK
            </span>
          )}
        </div>

        {ccLoading && (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 text-cyan-400 animate-spin" />
            <span className="ml-2 text-slate-400 text-sm">Computing cost comparison...</span>
          </div>
        )}

        {!ccLoading && ccData && ccData.methods && (
          <>
            {/* Results Table */}
            <div className="overflow-x-auto mb-6">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-slate-400 border-b border-slate-700">
                    <th className="text-left py-2 px-2">#</th>
                    <th className="text-left py-2 px-2">Method</th>
                    <th className="text-right py-2 px-2">Total Cost</th>
                    <th className="text-right py-2 px-2">Efficacy</th>
                    <th className="text-right py-2 px-2">Post-Lice</th>
                    <th className="text-right py-2 px-2">ROI</th>
                    <th className="text-right py-2 px-2">Mortality</th>
                    <th className="text-center py-2 px-2">Resistance</th>
                    <th className="text-center py-2 px-2">Temp OK</th>
                    <th className="text-right py-2 px-2">Score</th>
                  </tr>
                </thead>
                <tbody>
                  {ccData.methods.map((m: any) => (
                    <tr
                      key={m.key}
                      className={`border-b border-slate-800 hover:bg-slate-800/40 ${
                        m.recommended ? "bg-cyan-500/5 border-l-2 border-l-cyan-400" : ""
                      } ${!m.temp_suitable ? "opacity-60" : ""}`}
                    >
                      <td className="py-2 px-2 text-slate-400 text-xs">
                        {m.recommended ? (
                          <Star className="w-4 h-4 text-amber-400 fill-amber-400" />
                        ) : (
                          m.rank
                        )}
                      </td>
                      <td className="py-2 px-2 text-white font-medium text-xs">
                        {m.name}
                        {m.efficacy_source !== "literature" && (
                          <span className="block text-[10px] text-purple-400 mt-0.5">{m.efficacy_source}</span>
                        )}
                      </td>
                      <td className="py-2 px-2 text-right text-slate-300">
                        {(m.total_with_mortality_nok / 1000).toFixed(0)}k
                        <span className="block text-[10px] text-slate-500">
                          +{(m.mortality_cost_nok / 1000).toFixed(0)}k mort
                        </span>
                      </td>
                      <td className="py-2 px-2 text-right text-cyan-300">{m.efficacy_pct}%</td>
                      <td className="py-2 px-2 text-right text-emerald-300">{m.post_treatment_lice.toFixed(3)}</td>
                      <td className={`py-2 px-2 text-right font-medium ${
                        m.roi >= 1 ? "text-emerald-400" : m.roi >= 0 ? "text-amber-400" : "text-rose-400"
                      }`}>
                        {m.roi >= 0 ? "+" : ""}{m.roi.toFixed(1)}x
                      </td>
                      <td className="py-2 px-2 text-right text-orange-300">{m.mortality_risk_pct}%</td>
                      <td className="py-2 px-2 text-center">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                          m.resistance_risk === "none"
                            ? "bg-emerald-500/20 text-emerald-300"
                            : m.resistance_risk === "emerging"
                              ? "bg-amber-500/20 text-amber-300"
                              : "bg-rose-500/20 text-rose-300"
                        }`}>
                          {m.resistance_risk}
                        </span>
                      </td>
                      <td className="py-2 px-2 text-center">
                        {m.temp_suitable ? (
                          <CheckCircle2 className="w-4 h-4 text-emerald-400 mx-auto" />
                        ) : (
                          <XCircle className="w-4 h-4 text-rose-400 mx-auto" />
                        )}
                      </td>
                      <td className="py-2 px-2 text-right font-bold text-amber-300">
                        {m.recommendation_score.toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Cost Comparison Bar Chart */}
            {(() => {
              const chartData: DataPoint[] = ccData.methods.map((m: any, i: number) => ({
                x: i,
                y: m.total_with_mortality_nok / 1000,
                label: m.key.replace(/_/g, " ").replace(/\b\w/g, (c: string) => c.toUpperCase()),
              }));
              return (
                <InteractiveChart
                  data={chartData}
                  title="Total Cost Comparison (kNOK)"
                  unit="kNOK"
                  color="#22d3ee"
                  showArea
                  fillColor="rgba(34,211,238,0.15)"
                  height={180}
                />
              );
            })()}

            {/* Recommended Method Highlight */}
            {ccData.recommended_method && (() => {
              const rec = ccData.methods.find((m: any) => m.recommended);
              if (!rec) return null;
              return (
                <div className="mt-4 bg-cyan-500/10 border border-cyan-500/30 rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Star className="w-5 h-5 text-amber-400 fill-amber-400" />
                    <span className="text-white font-semibold">Recommended: {rec.name}</span>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                    <div>
                      <span className="text-slate-400 text-xs">Total Cost</span>
                      <div className="text-white font-medium">{(rec.total_with_mortality_nok / 1000).toFixed(0)}k NOK</div>
                    </div>
                    <div>
                      <span className="text-slate-400 text-xs">Efficacy</span>
                      <div className="text-cyan-300 font-medium">{rec.efficacy_pct}%</div>
                    </div>
                    <div>
                      <span className="text-slate-400 text-xs">ROI</span>
                      <div className={`font-medium ${rec.roi >= 1 ? "text-emerald-400" : "text-amber-400"}`}>
                        {rec.roi >= 0 ? "+" : ""}{rec.roi.toFixed(1)}x
                      </div>
                    </div>
                    <div>
                      <span className="text-slate-400 text-xs">Recovery</span>
                      <div className="text-slate-300 font-medium">{rec.recovery_weeks} weeks</div>
                    </div>
                  </div>
                </div>
              );
            })()}
          </>
        )}
      </GlassCard>

      {/* Network Coordination Schedule */}
      {!loading && networkData && !networkData.error && (
        <GlassCard>
          <h2 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
            <Network className="w-5 h-5 text-cyan-400" />
            PA {networkData.production_area} Network Treatment Schedule
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            <div className="bg-slate-800/50 rounded p-3">
              <div className="text-xs text-slate-400">Total Farms</div>
              <div className="text-lg font-bold text-white">{networkData.total_farms}</div>
            </div>
            <div className="bg-slate-800/50 rounded p-3">
              <div className="text-xs text-slate-400">Need Treatment</div>
              <div className="text-lg font-bold text-orange-300">{networkData.farms_needing_treatment}</div>
            </div>
            <div className="bg-slate-800/50 rounded p-3">
              <div className="text-xs text-slate-400">Total Est. Cost</div>
              <div className="text-lg font-bold text-cyan-300">{(networkData.total_estimated_cost_nok / 1_000_000).toFixed(1)}M NOK</div>
            </div>
            <div className="bg-slate-800/50 rounded p-3">
              <div className="text-xs text-slate-400">Network Risk</div>
              <div className={`text-lg font-bold ${networkData.network_risk === "high" ? "text-rose-400" : networkData.network_risk === "medium" ? "text-amber-400" : "text-emerald-400"}`}>
                {networkData.network_risk?.toUpperCase() || "N/A"}
              </div>
            </div>
          </div>

          {networkData.schedule?.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-slate-400 border-b border-slate-700">
                    <th className="text-left py-2 px-2">Farm</th>
                    <th className="text-right py-2 px-2">Locality</th>
                    <th className="text-right py-2 px-2">Current Lice</th>
                    <th className="text-right py-2 px-2">SST</th>
                    <th className="text-center py-2 px-2">Priority</th>
                    <th className="text-center py-2 px-2">Week</th>
                    <th className="text-left py-2 px-2">Treatment</th>
                    <th className="text-right py-2 px-2">Est. Cost</th>
                    <th className="text-left py-2 px-2">Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {networkData.schedule.slice(0, 30).map((entry: any, idx: number) => (
                    <tr key={idx} className="border-b border-slate-800 hover:bg-slate-800/40">
                      <td className="py-2 px-2 text-white text-xs">{entry.farm_name?.slice(0, 25)}</td>
                      <td className="py-2 px-2 text-right text-slate-300">{entry.locality_no}</td>
                      <td className={`py-2 px-2 text-right font-medium ${entry.current_lice >= 0.5 ? "text-rose-400" : entry.current_lice >= 0.2 ? "text-amber-400" : "text-emerald-400"}`}>
                        {entry.current_lice?.toFixed(3)}
                      </td>
                      <td className="py-2 px-2 text-right text-slate-300">{entry.sst_c?.toFixed(1)}&deg;C</td>
                      <td className="py-2 px-2 text-center">{priorityBadge(entry.priority)}</td>
                      <td className="py-2 px-2 text-center text-white font-medium">
                        {entry.recommended_week > 0 ? `W${entry.recommended_week}` : "-"}
                      </td>
                      <td className="py-2 px-2 text-cyan-300 text-xs">{entry.recommended_treatment}</td>
                      <td className="py-2 px-2 text-right text-slate-300">
                        {entry.estimated_cost_nok > 0 ? `${(entry.estimated_cost_nok / 1000).toFixed(0)}k` : "-"}
                      </td>
                      <td className="py-2 px-2 text-slate-400 text-xs max-w-[200px] truncate" title={entry.reason}>{entry.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {networkData.schedule.length > 30 && (
                <p className="text-xs text-slate-500 mt-2">Showing 30 of {networkData.schedule.length} farms.</p>
              )}
            </div>
          )}
        </GlassCard>
      )}

      {/* Empty state */}
      {!loading && !optimizeData && !compareData && (
        <GlassCard>
          <div className="text-center py-12 text-slate-400">
            <Syringe className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p>Enter a locality number and click Optimize to analyze treatment options.</p>
          </div>
        </GlassCard>
      )}
    </div>
    </ErrorBoundary>
  );
}
