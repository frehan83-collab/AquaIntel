"use client";
import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import {
  FileText, RefreshCw, TrendingUp, TrendingDown, Shield,
  BarChart3, Activity, AlertTriangle, DollarSign, Clock,
} from "lucide-react";
import KPICard from "@/components/KPICard";
import GlassCard from "@/components/GlassCard";
import { OcButton } from "@/components/ui/Button";
import { api } from "@/lib/api";
import ErrorBoundary from "@/components/ErrorBoundary";
import { useTranslation, formatNumber } from "@/lib/i18n";
import DataQualityBadge from "@/components/DataQualityBadge";

/* eslint-disable @typescript-eslint/no-explicit-any */

const SIGNAL_COLORS: Record<string, string> = {
  STRONG_BULLISH: "text-emerald-400",
  BULLISH: "text-emerald-300",
  NEUTRAL: "text-slate-300",
  BEARISH: "text-rose-300",
  STRONG_BEARISH: "text-rose-400",
};

const SIGNAL_BG: Record<string, string> = {
  STRONG_BULLISH: "bg-emerald-500/20 border-emerald-500/40",
  BULLISH: "bg-emerald-500/10 border-emerald-500/30",
  NEUTRAL: "bg-slate-500/10 border-slate-500/30",
  BEARISH: "bg-rose-500/10 border-rose-500/30",
  STRONG_BEARISH: "bg-rose-500/20 border-rose-500/40",
};

export default function ContractsPage() {
  const { t, locale } = useTranslation();
  const [evaluation, setEvaluation] = useState<any>(null);
  const [marketCtx, setMarketCtx] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [ctxLoading, setCtxLoading] = useState(true);
  const [error, setError] = useState<string>("");

  // Form state
  const [contractPrice, setContractPrice] = useState("");
  const [volume, setVolume] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [counterparty, setCounterparty] = useState("");

  const loadMarketContext = useCallback(async () => {
    setCtxLoading(true);
    try {
      const ctx = await api.contractsHedgeSignals();
      setMarketCtx(ctx);
    } catch { /* empty */ }
    setCtxLoading(false);
  }, []);

  useEffect(() => { loadMarketContext(); }, [loadMarketContext]);

  const handleEvaluate = async () => {
    if (!contractPrice || !volume) {
      setError("Contract price and volume are required.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const result = await api.contractsEvaluate({
        contract_price_nok: parseFloat(contractPrice),
        volume_tonnes: parseFloat(volume),
        start_date: startDate || new Date().toISOString().slice(0, 10),
        end_date: endDate || new Date(Date.now() + 90 * 86400000).toISOString().slice(0, 10),
        counterparty: counterparty || "Unknown",
      });
      setEvaluation(result);
    } catch (e: any) {
      setError(e?.message || "Evaluation failed");
    }
    setLoading(false);
  };

  const spot = marketCtx?.live_spot_nok ?? evaluation?.live_spot_nok ?? 0;
  const fc4 = marketCtx?.forecasts?.["4w"];

  return (
    <ErrorBoundary fallbackTitle="Contract Risk error">
    <div className="space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] flex items-center gap-3">
            <div className="p-2 rounded-lg bg-violet-500/20">
              <FileText className="w-6 h-6 text-violet-400" />
            </div>
            {t("nav.contract_risk")}
            <DataQualityBadge quality="live" source="SSB + Euronext" />
          </h1>
          <p className="text-sm text-[var(--text-secondary)] mt-1">
            Evaluate fixed-price contracts against live SSB spot &amp; ML forecasts
          </p>
        </div>
        <OcButton variant="secondary" size="sm" onClick={loadMarketContext} loading={ctxLoading}
          leftIcon={<RefreshCw className="w-3.5 h-3.5" />}>Refresh Market</OcButton>
      </motion.div>

      {/* Market Context KPI Row */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}
        className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <KPICard
          label="SSB Spot"
          value={spot > 0 ? `${formatNumber(spot, locale, 1)} NOK` : "--"}
          delta={marketCtx?.spot_week || "latest week"}
          deltaType="neutral"
          icon={DollarSign}
        />
        <KPICard
          label="4w Forecast"
          value={fc4?.predicted_nok ? `${formatNumber(fc4.predicted_nok, locale, 1)} NOK` : "--"}
          delta={fc4?.direction || ""}
          deltaType={fc4?.direction === "bullish" ? "positive" : fc4?.direction === "bearish" ? "negative" : "neutral"}
          icon={TrendingUp}
        />
        <KPICard
          label="4w Range (95%)"
          value={fc4 ? `${formatNumber(fc4.lo95, locale, 0)}-${formatNumber(fc4.hi95, locale, 0)}` : "--"}
          delta="NOK/kg"
          deltaType="neutral"
          icon={BarChart3}
        />
        <KPICard
          label="Signal"
          value={fc4?.combined_signal || "--"}
          delta="combined ML"
          deltaType={fc4?.combined_signal?.includes("BULL") ? "positive" : fc4?.combined_signal?.includes("BEAR") ? "negative" : "neutral"}
          icon={Activity}
        />
        <KPICard
          label="8w Forecast"
          value={marketCtx?.forecasts?.["8w"]?.predicted_nok
            ? `${formatNumber(marketCtx.forecasts["8w"].predicted_nok, locale, 1)} NOK` : "--"}
          delta={marketCtx?.forecasts?.["8w"]?.direction || ""}
          deltaType={marketCtx?.forecasts?.["8w"]?.direction === "bullish" ? "positive" : marketCtx?.forecasts?.["8w"]?.direction === "bearish" ? "negative" : "neutral"}
          icon={TrendingUp}
        />
        <KPICard
          label="12w Forecast"
          value={marketCtx?.forecasts?.["12w"]?.predicted_nok
            ? `${formatNumber(marketCtx.forecasts["12w"].predicted_nok, locale, 1)} NOK` : "--"}
          delta={marketCtx?.forecasts?.["12w"]?.direction || ""}
          deltaType={marketCtx?.forecasts?.["12w"]?.direction === "bullish" ? "positive" : marketCtx?.forecasts?.["12w"]?.direction === "bearish" ? "negative" : "neutral"}
          icon={TrendingUp}
        />
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Contract Input Form */}
        <motion.div initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.1 }}>
          <GlassCard>
            <h2 className="text-lg font-semibold text-[var(--text-primary)] mb-4 flex items-center gap-2">
              <DollarSign className="w-5 h-5 text-violet-400" />
              Contract Details
            </h2>
            <div className="space-y-3">
              <div>
                <label className="text-xs text-[var(--text-secondary)] mb-1 block">Contract Price (NOK/kg)</label>
                <input
                  type="number"
                  step="0.1"
                  value={contractPrice}
                  onChange={(e) => setContractPrice(e.target.value)}
                  placeholder={spot > 0 ? `e.g. ${formatNumber(spot, locale, 0)}` : "e.g. 85"}
                  className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-[var(--text-primary)] text-sm focus:outline-none focus:border-violet-500/50"
                />
              </div>
              <div>
                <label className="text-xs text-[var(--text-secondary)] mb-1 block">Volume (tonnes)</label>
                <input
                  type="number"
                  step="1"
                  value={volume}
                  onChange={(e) => setVolume(e.target.value)}
                  placeholder="e.g. 500"
                  className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-[var(--text-primary)] text-sm focus:outline-none focus:border-violet-500/50"
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-xs text-[var(--text-secondary)] mb-1 block">Start Date</label>
                  <input
                    type="date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-[var(--text-primary)] text-sm focus:outline-none focus:border-violet-500/50"
                  />
                </div>
                <div>
                  <label className="text-xs text-[var(--text-secondary)] mb-1 block">End Date</label>
                  <input
                    type="date"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-[var(--text-primary)] text-sm focus:outline-none focus:border-violet-500/50"
                  />
                </div>
              </div>
              <div>
                <label className="text-xs text-[var(--text-secondary)] mb-1 block">Counterparty</label>
                <input
                  type="text"
                  value={counterparty}
                  onChange={(e) => setCounterparty(e.target.value)}
                  placeholder="e.g. Leroi Seafoods"
                  className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-[var(--text-primary)] text-sm focus:outline-none focus:border-violet-500/50"
                />
              </div>
              {error && (
                <p className="text-xs text-rose-400 flex items-center gap-1">
                  <AlertTriangle className="w-3.5 h-3.5" /> {error}
                </p>
              )}
              <OcButton variant="primary" size="md" onClick={handleEvaluate} loading={loading}
                leftIcon={<BarChart3 className="w-4 h-4" />} className="w-full mt-2">
                Evaluate Contract
              </OcButton>
            </div>
          </GlassCard>
        </motion.div>

        {/* Mark-to-Market P&L Card */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}>
          <GlassCard className="h-full">
            <h2 className="text-lg font-semibold text-[var(--text-primary)] mb-4 flex items-center gap-2">
              {evaluation?.pnl_direction === "profit" ? (
                <TrendingUp className="w-5 h-5 text-emerald-400" />
              ) : evaluation?.pnl_direction === "loss" ? (
                <TrendingDown className="w-5 h-5 text-rose-400" />
              ) : (
                <Activity className="w-5 h-5 text-slate-400" />
              )}
              Mark-to-Market P&amp;L
            </h2>
            {evaluation && !evaluation.error ? (
              <div className="space-y-4">
                {/* Main P&L */}
                <div className={`p-4 rounded-xl border ${
                  evaluation.pnl_direction === "profit"
                    ? "bg-emerald-500/10 border-emerald-500/30"
                    : evaluation.pnl_direction === "loss"
                    ? "bg-rose-500/10 border-rose-500/30"
                    : "bg-slate-500/10 border-slate-500/30"
                }`}>
                  <p className="text-xs text-[var(--text-secondary)]">Total P&amp;L</p>
                  <p className={`text-3xl font-bold ${
                    evaluation.pnl_direction === "profit" ? "text-emerald-400" :
                    evaluation.pnl_direction === "loss" ? "text-rose-400" : "text-slate-300"
                  }`}>
                    {evaluation.mtm_pnl_nok >= 0 ? "+" : ""}{formatNumber(evaluation.mtm_pnl_nok / 1e6, locale, 2)}M NOK
                  </p>
                  <p className="text-sm text-[var(--text-secondary)] mt-1">
                    {evaluation.mtm_pnl_pct >= 0 ? "+" : ""}{formatNumber(evaluation.mtm_pnl_pct, locale, 1)}% vs spot
                  </p>
                </div>

                {/* Price comparison */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="p-3 rounded-lg bg-white/5">
                    <p className="text-xs text-[var(--text-secondary)]">Contract Price</p>
                    <p className="text-xl font-semibold text-[var(--text-primary)]">
                      {evaluation.contract_price_nok} <span className="text-xs">NOK/kg</span>
                    </p>
                  </div>
                  <div className="p-3 rounded-lg bg-white/5">
                    <p className="text-xs text-[var(--text-secondary)]">Live Spot</p>
                    <p className="text-xl font-semibold text-ocean-300">
                      {evaluation.live_spot_nok} <span className="text-xs">NOK/kg</span>
                    </p>
                  </div>
                </div>

                {/* Delta */}
                <div className="flex items-center justify-between text-sm">
                  <span className="text-[var(--text-secondary)]">Price Delta</span>
                  <span className={evaluation.price_delta_nok >= 0 ? "text-emerald-400" : "text-rose-400"}>
                    {evaluation.price_delta_nok >= 0 ? "+" : ""}{formatNumber(evaluation.price_delta_nok, locale, 2)} NOK/kg
                  </span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-[var(--text-secondary)]">Volume</span>
                  <span className="text-[var(--text-primary)]">{evaluation.volume_tonnes} tonnes</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-[var(--text-secondary)]">Days Remaining</span>
                  <span className="text-[var(--text-primary)] flex items-center gap-1">
                    <Clock className="w-3.5 h-3.5 text-slate-400" />
                    {evaluation.days_remaining}
                  </span>
                </div>
              </div>
            ) : evaluation?.error ? (
              <p className="text-sm text-rose-400">{evaluation.error}</p>
            ) : (
              <div className="flex flex-col items-center justify-center py-12 text-[var(--text-secondary)] text-sm">
                <Activity className="w-10 h-10 mb-3 opacity-30" />
                Enter contract details and click Evaluate
              </div>
            )}
          </GlassCard>
        </motion.div>

        {/* VaR + Hedge Card */}
        <motion.div initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.2 }}
          className="space-y-4">
          {/* VaR Gauge */}
          <GlassCard>
            <h2 className="text-lg font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-amber-400" />
              Value at Risk (95%)
            </h2>
            {evaluation && !evaluation.error ? (
              <div className="space-y-3">
                <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30">
                  <p className="text-xs text-[var(--text-secondary)]">Max Potential Loss</p>
                  <p className="text-2xl font-bold text-amber-400">
                    {formatNumber(evaluation.var_95_nok / 1e6, locale, 2)}M NOK
                  </p>
                  <p className="text-xs text-[var(--text-secondary)]">{formatNumber(evaluation.var_95_pct, locale, 1)}% of notional</p>
                </div>
                {/* VaR gauge bar */}
                <div className="relative h-3 rounded-full bg-white/10 overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${Math.min(100, evaluation.var_95_pct * 2)}%` }}
                    transition={{ duration: 0.8 }}
                    className={`absolute left-0 top-0 h-full rounded-full ${
                      evaluation.var_95_pct > 15 ? "bg-rose-500" :
                      evaluation.var_95_pct > 8 ? "bg-amber-500" : "bg-emerald-500"
                    }`}
                  />
                </div>
                <div className="flex justify-between text-xs text-[var(--text-secondary)]">
                  <span>Low Risk</span>
                  <span>High Risk</span>
                </div>

                {/* Forecast context */}
                <div className="mt-3 p-3 rounded-lg bg-white/5 space-y-1">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-[var(--text-secondary)]">Forecast</span>
                    <span className="text-[var(--text-primary)]">{evaluation.forecast_price_nok} NOK</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-[var(--text-secondary)]">Direction</span>
                    <span className={evaluation.forecast_direction === "bullish" ? "text-emerald-400" :
                      evaluation.forecast_direction === "bearish" ? "text-rose-400" : "text-slate-300"}>
                      {evaluation.forecast_direction}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-[var(--text-secondary)]">95% Band</span>
                    <span className="text-[var(--text-primary)]">
                      {evaluation.forecast_lo95} &ndash; {evaluation.forecast_hi95}
                    </span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-8 text-[var(--text-secondary)] text-sm">
                <AlertTriangle className="w-8 h-8 mb-2 opacity-30" />
                Evaluate a contract first
              </div>
            )}
          </GlassCard>

          {/* Hedge Recommendation */}
          <GlassCard>
            <h2 className="text-lg font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
              <Shield className="w-5 h-5 text-sky-400" />
              Hedge Recommendation
            </h2>
            {evaluation && !evaluation.error ? (
              <div className="space-y-3">
                <div className={`p-3 rounded-xl border ${
                  evaluation.hedge_action === "increase_hedge"
                    ? "bg-rose-500/10 border-rose-500/30"
                    : evaluation.hedge_action === "reduce_hedge"
                    ? "bg-emerald-500/10 border-emerald-500/30"
                    : "bg-slate-500/10 border-slate-500/30"
                }`}>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs text-[var(--text-secondary)]">Action</p>
                      <p className="text-lg font-semibold text-[var(--text-primary)] capitalize">
                        {evaluation.hedge_action.replace(/_/g, " ")}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-xs text-[var(--text-secondary)]">Hedge Ratio</p>
                      <p className="text-2xl font-bold text-sky-400">
                        {formatNumber(evaluation.hedge_ratio * 100, locale, 0)}%
                      </p>
                    </div>
                  </div>
                </div>
                {/* Hedge ratio bar */}
                <div className="relative h-2 rounded-full bg-white/10 overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${evaluation.hedge_ratio * 100}%` }}
                    transition={{ duration: 0.8 }}
                    className="absolute left-0 top-0 h-full rounded-full bg-sky-500"
                  />
                </div>
                <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                  {evaluation.hedge_rationale}
                </p>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-8 text-[var(--text-secondary)] text-sm">
                <Shield className="w-8 h-8 mb-2 opacity-30" />
                Evaluate a contract first
              </div>
            )}
          </GlassCard>
        </motion.div>
      </div>

      {/* Market Context Section */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }}>
        <GlassCard>
          <h2 className="text-lg font-semibold text-[var(--text-primary)] mb-4 flex items-center gap-2">
            <Activity className="w-5 h-5 text-ocean-400" />
            Market Context
            <span className="text-xs text-[var(--text-secondary)] ml-auto">
              {marketCtx?.spot_source || "SSB Table 03024"} &bull; Updated {marketCtx?.fetched_at?.slice(0, 16) || "--"}
            </span>
          </h2>
          {marketCtx?.spot_available ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Forecast horizons */}
              <div>
                <h3 className="text-sm font-medium text-[var(--text-secondary)] mb-3">Price Forecasts (ML Ensemble)</h3>
                <div className="space-y-2">
                  {(["4w", "8w", "12w"] as const).map((h) => {
                    const fc = marketCtx.forecasts?.[h];
                    if (!fc) return null;
                    const signalColor = SIGNAL_COLORS[fc.combined_signal] || "text-slate-300";
                    const signalBg = SIGNAL_BG[fc.combined_signal] || "bg-slate-500/10 border-slate-500/30";
                    return (
                      <div key={h} className={`p-3 rounded-lg border ${signalBg} flex items-center justify-between`}>
                        <div>
                          <span className="text-xs text-[var(--text-secondary)]">{h} horizon</span>
                          <p className="text-lg font-semibold text-[var(--text-primary)]">
                            {formatNumber(fc.predicted_nok, locale, 1)} <span className="text-xs">NOK/kg</span>
                          </p>
                          <p className="text-xs text-[var(--text-secondary)]">
                            Range: {formatNumber(fc.lo95, locale, 0)} &ndash; {formatNumber(fc.hi95, locale, 0)} NOK
                          </p>
                        </div>
                        <div className="text-right">
                          <span className={`text-sm font-medium ${signalColor}`}>{fc.combined_signal}</span>
                          <p className="text-xs text-[var(--text-secondary)]">{fc.direction}</p>
                          {fc.confidence != null && (
                            <p className="text-xs text-[var(--text-secondary)]">
                              conf: {formatNumber(fc.confidence * 100, locale, 0)}%
                            </p>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Recent price history */}
              <div>
                <h3 className="text-sm font-medium text-[var(--text-secondary)] mb-3">Recent SSB Prices</h3>
                {marketCtx.recent_prices && marketCtx.recent_prices.length > 0 ? (
                  <div className="space-y-1">
                    {marketCtx.recent_prices.map((p: any, i: number) => (
                      <div key={i} className="flex items-center justify-between text-sm py-1 border-b border-white/5 last:border-0">
                        <span className="text-[var(--text-secondary)] text-xs font-mono">{p.week}</span>
                        <span className="text-[var(--text-primary)] font-medium">
                          {formatNumber(p.price_nok, locale, 1)} NOK/kg
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-[var(--text-secondary)]">No recent prices available</p>
                )}
                {fc4?.rationale && (
                  <div className="mt-4 p-3 rounded-lg bg-white/5">
                    <p className="text-xs text-[var(--text-secondary)] mb-1">ML Rationale (4w)</p>
                    <p className="text-xs text-[var(--text-primary)] leading-relaxed">{fc4.rationale}</p>
                  </div>
                )}
              </div>
            </div>
          ) : ctxLoading ? (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="w-6 h-6 text-ocean-400 animate-spin" />
            </div>
          ) : (
            <p className="text-sm text-[var(--text-secondary)] text-center py-8">
              Market data temporarily unavailable
            </p>
          )}
        </GlassCard>
      </motion.div>
    </div>
    </ErrorBoundary>
  );
}
