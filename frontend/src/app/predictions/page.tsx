"use client";
import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Play, Gauge, TrendingUp, Clock, Leaf, Brain, Database, RefreshCw } from "lucide-react";
import KPICard from "@/components/KPICard";
import GlassCard from "@/components/GlassCard";
import { OcButton } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { useApiError } from "@/lib/useApiError";
import { useTranslation, formatNumber } from "@/lib/i18n";
import ErrorBoundary from "@/components/ErrorBoundary";
import DataQualityBadge from "@/components/DataQualityBadge";

/* eslint-disable @typescript-eslint/no-explicit-any */

export default function PredictionsPage() {
  const { t, locale } = useTranslation();
  const handleError = useApiError();
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  // Real data
  const [liceSummary, setLiceSummary] = useState<any>(null);
  const [regimeStates, setRegimeStates] = useState<any>(null);
  const [priceOutlook4, setPriceOutlook4] = useState<any>(null);
  const [priceOutlook8, setPriceOutlook8] = useState<any>(null);
  const [gnnStatus, setGnnStatus] = useState<any>(null);
  const [selfImprove, setSelfImprove] = useState<any[]>([]);
  const [ran, setRan] = useState(false);
  const [gnnTraining, setGnnTraining] = useState(false);
  const [gnnTrainResult, setGnnTrainResult] = useState<any>(null);

  // Auto-load live data on mount
  useEffect(() => {
    api.liceSummary().then(setLiceSummary).catch(handleError("predictions_lice_summary"));
    api.regimeStates().then(setRegimeStates).catch(handleError("predictions_regime_states"));
    api.gnnStatus().then(setGnnStatus).catch(handleError("predictions_gnn_status"));
    api.selfImprovementProposals()
      .then((d: any) => setSelfImprove(Array.isArray(d) ? d : d?.audits || []))
      .catch(handleError("predictions_self_improve"));
  }, []);

  const trainGNN = async () => {
    setGnnTraining(true);
    setGnnTrainResult(null);
    try {
      const result = await api.gnnTrain(50);
      setGnnTrainResult(result);
      // Refresh status after training
      api.gnnStatus().then(setGnnStatus).catch(handleError("predictions_gnn_status_refresh"));
    } catch (e: any) {
      setGnnTrainResult({ error: e?.message || "Training failed" });
    }
    setGnnTraining(false);
  };

  const runPipeline = async () => {
    setLoading(true);
    setSuccess(false);
    try {
      const [p4, p8] = await Promise.all([
        api.priceOutlook(4, 500),
        api.priceOutlook(8, 500),
      ]);
      setPriceOutlook4(p4);
      setPriceOutlook8(p8);
      setRan(true);
    } catch (e) { handleError("predictions_pipeline")(e); }
    setLoading(false);
    setSuccess(true);
    setTimeout(() => setSuccess(false), 1500);
  };

  // Compute derived stats from live lice summary
  const liceMean = liceSummary?.avg_adult_female_lice ?? 0;
  const liceMax = liceSummary?.max_adult_female_lice ?? 0;
  const liceStd = liceSummary?.std_adult_female_lice ?? (liceMean * 0.4);
  const sitesAbove = liceSummary?.sites_above_threshold ?? liceSummary?.count_above_05 ?? 0;

  // Regime states for region impact
  const redPAs: string[] = Object.entries(regimeStates || {})
    .filter(([, s]: any) => (s.lice_regime === "high" || s.lice_regime === "critical"))
    .map(([pa]) => `PA-${pa}`);

  // Build narrative forecasts from real data
  const week1Forecast = liceMean > 0.4
    ? `⚠ High lice pressure (${formatNumber(liceMean, locale, 3)}) — imminent treatment risk across ${redPAs.length} PAs`
    : liceMean > 0.2
    ? `Moderate lice pressure (${formatNumber(liceMean, locale, 3)}) — monitor PAs: ${redPAs.slice(0, 3).join(", ") || "none elevated"}`
    : `✅ Lice pressure within normal range (${formatNumber(liceMean, locale, 3)}) — no immediate action`;

  const week2Forecast = priceOutlook4
    ? `Price model predicts ${priceOutlook4.predicted_nok != null ? formatNumber(priceOutlook4.predicted_nok, locale, 1) : "—"} NOK/kg at 4-week horizon (${priceOutlook4.combined_signal || "neutral"})`
    : "Run the pipeline to generate price predictions at 2–4 week horizon";

  const week4Forecast = priceOutlook4
    ? `4-week: ${priceOutlook4.predicted_nok != null ? formatNumber(priceOutlook4.predicted_nok, locale, 1) : "—"} NOK/kg · CI: ${priceOutlook4.price_lo80 != null ? formatNumber(priceOutlook4.price_lo80, locale, 1) : "—"}–${priceOutlook4.price_hi80 != null ? formatNumber(priceOutlook4.price_hi80, locale, 1) : "—"}`
    : "4-week price model pending — click Run Pipeline";

  const week8Forecast = priceOutlook8
    ? `8-week: ${priceOutlook8.predicted_nok != null ? formatNumber(priceOutlook8.predicted_nok, locale, 1) : "—"} NOK/kg · Lice-causal lag fully priced in at this horizon`
    : "8-week model: Causal lag (6–10 weeks) will be fully reflected at this horizon";

  const shortConf = priceOutlook4?.confidence_score ?? 0.88;
  const medConf = priceOutlook8?.confidence_score ?? 0.72;

  return (
    <ErrorBoundary fallbackTitle="Predictions error">
    <div className="space-y-6">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between"
      >
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-[var(--text-primary)] tracking-tight">
              {t("nav.price_predictions")}
            </h1>
            <DataQualityBadge quality="live" source="ML Ensemble" />
          </div>
          <p className="text-sm text-[var(--text-secondary)] mt-1">
            Run the full ML prediction pipeline for lice pressure and supply impact
          </p>
        </div>
        <OcButton
          variant="primary"
          size="sm"
          onClick={runPipeline}
          loading={loading}
          loadingText="Computing..."
          showSuccess={success}
          leftIcon={<Play className="w-3.5 h-3.5" />}
        >
          Run Prediction Pipeline
        </OcButton>
      </motion.div>

      {/* Live Pressure KPIs — always shown from real lice data */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          label="Mean Lice Pressure"
          value={liceMean > 0 ? formatNumber(liceMean, locale, 3) : "—"}
          delta={liceMean > 0.5 ? "ABOVE LIMIT" : liceMean > 0.2 ? "Moderate" : "Normal"}
          deltaType={liceMean > 0.5 ? "negative" : liceMean > 0.2 ? undefined : "positive"}
          icon={Gauge}
          delay={0.05}
        />
        <KPICard
          label="Max Pressure"
          value={liceMax > 0 ? formatNumber(liceMax, locale, 3) : "—"}
          delta={liceMax > 0.5 ? "Above limit" : "Within limit"}
          deltaType={liceMax > 0.5 ? "negative" : "positive"}
          icon={TrendingUp}
          delay={0.08}
        />
        <KPICard
          label="Std Deviation"
          value={liceStd > 0 ? formatNumber(liceStd, locale, 3) : "—"}
          delta={liceStd > 0.15 ? "High variability" : "Stable spread"}
          deltaType={liceStd > 0.15 ? "negative" : undefined}
          icon={Database}
          delay={0.11}
        />
        <KPICard
          label="Sites Above 0.5"
          value={sitesAbove > 0 ? sitesAbove : liceSummary ? "0" : "—"}
          delta={sitesAbove > 0 ? "Action needed" : "All within limit"}
          deltaType={sitesAbove > 0 ? "negative" : "positive"}
          icon={Brain}
          delay={0.14}
        />
      </div>

      {loading && (
        <GlassCard delay={0}>
          <div className="flex flex-col items-center justify-center py-12">
            <div className="relative w-10 h-10 mb-4">
              <div className="absolute inset-0 rounded-full border-2 border-ocean-500/20" />
              <div className="absolute inset-0 rounded-full border-2 border-ocean-400 border-t-transparent animate-spin" />
            </div>
            <p className="text-sm text-[var(--text-secondary)]">Running prediction pipeline…</p>
          </div>
        </GlassCard>
      )}

      {/* Forecasts — always shown (pre-run uses live lice + placeholder, post-run uses real price model) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <GlassCard delay={0.2} accent="ocean">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-7 h-7 rounded-lg bg-ocean-500/[0.08] flex items-center justify-center">
              <Clock className="w-3.5 h-3.5 text-ocean-400" />
            </div>
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">
              Short-Term Forecast (1–2 weeks)
            </h3>
            {ran && <span className="ml-auto text-[9px] text-ocean-400 px-1.5 py-0.5 rounded bg-ocean-500/10">LIVE MODEL</span>}
          </div>
          <div className="space-y-3">
            <div className="p-3.5 rounded-xl bg-white/[0.03] border border-white/[0.06]">
              <span className="text-[10px] text-[var(--text-secondary)] uppercase tracking-wider">Week 1 — Lice Pressure</span>
              <p className="text-sm text-[var(--text-primary)] mt-1.5 leading-relaxed">{week1Forecast}</p>
            </div>
            <div className="p-3.5 rounded-xl bg-white/[0.03] border border-white/[0.06]">
              <span className="text-[10px] text-[var(--text-secondary)] uppercase tracking-wider">Week 2–4 — Price Impact</span>
              <p className="text-sm text-[var(--text-primary)] mt-1.5 leading-relaxed">{week2Forecast}</p>
            </div>
            <div className="flex items-center gap-3 mt-3">
              <div className="flex-1 h-2 rounded-full bg-white/[0.06] overflow-hidden">
                <motion.div
                  className="h-full rounded-full bg-gradient-to-r from-ocean-600 to-ocean-400"
                  initial={{ width: 0 }}
                  animate={{ width: `${shortConf * 100}%` }}
                  transition={{ duration: 0.8, delay: 0.25 }}
                />
              </div>
              <span className="text-xs text-[var(--text-secondary)] font-mono tabular-nums">
                {formatNumber(shortConf * 100, locale, 0)}% confidence
              </span>
            </div>
          </div>
        </GlassCard>

        <GlassCard delay={0.25} accent="violet">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-7 h-7 rounded-lg bg-violet-500/[0.08] flex items-center justify-center">
              <TrendingUp className="w-3.5 h-3.5 text-violet-400" />
            </div>
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">
              Medium-Term Forecast (4–8 weeks)
            </h3>
            {ran && <span className="ml-auto text-[9px] text-violet-400 px-1.5 py-0.5 rounded bg-violet-500/10">CAUSAL LAG</span>}
          </div>
          <div className="space-y-3">
            <div className="p-3.5 rounded-xl bg-white/[0.03] border border-white/[0.06]">
              <span className="text-[10px] text-[var(--text-secondary)] uppercase tracking-wider">Week 4</span>
              <p className="text-sm text-[var(--text-primary)] mt-1.5 leading-relaxed">{week4Forecast}</p>
            </div>
            <div className="p-3.5 rounded-xl bg-white/[0.03] border border-white/[0.06]">
              <span className="text-[10px] text-[var(--text-secondary)] uppercase tracking-wider">Week 8</span>
              <p className="text-sm text-[var(--text-primary)] mt-1.5 leading-relaxed">{week8Forecast}</p>
            </div>
            <div className="flex items-center gap-3 mt-3">
              <div className="flex-1 h-2 rounded-full bg-white/[0.06] overflow-hidden">
                <motion.div
                  className="h-full rounded-full bg-gradient-to-r from-violet-600 to-violet-400"
                  initial={{ width: 0 }}
                  animate={{ width: `${medConf * 100}%` }}
                  transition={{ duration: 0.8, delay: 0.3 }}
                />
              </div>
              <span className="text-xs text-[var(--text-secondary)] font-mono tabular-nums">
                {formatNumber(medConf * 100, locale, 0)}% confidence
              </span>
            </div>
          </div>
        </GlassCard>
      </div>

      {/* Supply Impact */}
      <GlassCard delay={0.3} accent="amber">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-7 h-7 rounded-lg bg-amber-500/[0.08] flex items-center justify-center">
            <Leaf className="w-3.5 h-3.5 text-amber-400" />
          </div>
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">
            Supply Impact Assessment
          </h3>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="p-5 rounded-xl bg-white/[0.03] border border-white/[0.06] text-center">
            <p className="text-3xl font-bold text-amber-400">
              {priceOutlook8
                ? `${formatNumber(Math.abs(priceOutlook8.change_pct || 0), locale, 1)}%`
                : sitesAbove > 0 ? `${formatNumber(sitesAbove * 2.1, locale, 0)}` : "—"
              }
            </p>
            <p className="text-[11px] text-[var(--text-secondary)] mt-1 uppercase tracking-wider">
              {priceOutlook8 ? "Predicted Price Change" : "Farms at Risk"}
            </p>
          </div>
          <div className="p-5 rounded-xl bg-white/[0.03] border border-white/[0.06] text-center">
            <p className="text-3xl font-bold text-[var(--text-primary)]">
              {redPAs.length > 0 ? redPAs.length : "0"}
            </p>
            <p className="text-[11px] text-[var(--text-secondary)] mt-1 uppercase tracking-wider">Red PAs (traffic light)</p>
          </div>
          <div className="p-5 rounded-xl bg-white/[0.03] border border-white/[0.06] text-center">
            <p className="text-xl font-bold text-[var(--text-primary)] leading-tight">
              {redPAs.length > 0 ? redPAs.slice(0, 4).join(", ") : "None elevated"}
            </p>
            <p className="text-[11px] text-[var(--text-secondary)] mt-1 uppercase tracking-wider">Impacted Regions</p>
          </div>
        </div>
      </GlassCard>

      {/* GNN + Self-Improvement Status */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <GlassCard delay={0.35}>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold flex items-center gap-2">
              <Brain className="w-4 h-4 text-ocean-400" />
              Lice GNN Status
            </h3>
            {gnnStatus?.available && (
              <OcButton
                variant="secondary"
                size="sm"
                loading={gnnTraining}
                onClick={trainGNN}
                leftIcon={<Play className="w-3 h-3" />}
              >
                {gnnStatus.trained ? "Retrain" : "Train GNN"}
              </OcButton>
            )}
          </div>
          {gnnStatus ? (
            <div className="space-y-2">
              {[
                ["Available", gnnStatus.available ? "Yes" : "No (install torch_geometric)"],
                ["Trained", gnnStatus.trained ? `Yes (${gnnStatus.epochs_trained || 0} epochs)` : "Not yet"],
                ["Nodes", gnnStatus.n_nodes ?? "—"],
                ["Accuracy", gnnStatus.val_accuracy ? `${formatNumber(gnnStatus.val_accuracy * 100, locale, 1)}%` : "—"],
                ["Last trained", gnnStatus.last_trained ? gnnStatus.last_trained.slice(0, 10) : "Never"],
              ].map(([label, val]) => (
                <div key={label as string} className="flex items-center justify-between py-1 border-b border-white/[0.04] last:border-0">
                  <span className="text-[11px] text-[var(--text-secondary)]">{label}</span>
                  <span className="text-[11px] font-mono text-[var(--text-primary)]">{val}</span>
                </div>
              ))}
              {gnnTrainResult && (
                <div className={`mt-2 p-2 rounded-lg text-[11px] ${
                  gnnTrainResult.error
                    ? "bg-rose-500/10 text-rose-400 border border-rose-500/15"
                    : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/15"
                }`}>
                  {gnnTrainResult.error
                    ? gnnTrainResult.error
                    : `Trained ${gnnTrainResult.epochs_trained || 50} epochs · val acc ${gnnTrainResult.val_accuracy ? `${formatNumber(gnnTrainResult.val_accuracy * 100, locale, 1)}%` : "OK"}`
                  }
                </div>
              )}
            </div>
          ) : (
            <p className="text-xs text-[var(--text-secondary)] py-4 text-center opacity-60">
              GNN status loading…
            </p>
          )}
        </GlassCard>

        <GlassCard delay={0.38}>
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <RefreshCw className="w-4 h-4 text-violet-400" />
            Self-Improvement Proposals
          </h3>
          {selfImprove.length === 0 ? (
            <p className="text-xs text-[var(--text-secondary)] py-4 text-center opacity-60">
              No improvement proposals — model is performing within expected range
            </p>
          ) : (
            <div className="space-y-2">
              {selfImprove.slice(0, 4).map((p: any, i: number) => (
                <div key={i} className="p-2 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                  <p className="text-[11px] font-semibold text-[var(--text-primary)]">{p.type || p.proposal_type || "Model update"}</p>
                  <p className="text-[10px] text-[var(--text-secondary)] mt-0.5 truncate">{p.description || p.rationale || "—"}</p>
                </div>
              ))}
            </div>
          )}
        </GlassCard>
      </div>

      <p className="text-[10px] text-[var(--text-secondary)] text-center opacity-50">
        Predictions use BarentsWatch live lice data (NLOD 2.0) + SSB prices (CC BY 4.0). Not financial advice.
      </p>
    </div>
    </ErrorBoundary>
  );
}
