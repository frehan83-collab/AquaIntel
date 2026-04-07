"use client";
import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import {
  Zap, CheckCircle, XCircle, Clock, TrendingDown, TrendingUp, Loader2,
  GitBranch, MessageSquare, Globe, RefreshCw, Shield, Download,
} from "lucide-react";
import { useTranslation, formatNumber, formatCurrency } from "@/lib/i18n";
import { useApiError } from "@/lib/useApiError";
import { exportToCSV } from "@/lib/export";
import GlassCard from "@/components/GlassCard";
import DataQualityBadge from "@/components/DataQualityBadge";
import { OcButton } from "@/components/ui/Button";
import { api } from "@/lib/api";
import ErrorBoundary from "@/components/ErrorBoundary";
import FreshnessIndicator from "@/components/FreshnessIndicator";

/* eslint-disable @typescript-eslint/no-explicit-any */

export default function SignalsPage() {
  const { t, locale } = useTranslation();
  const handleError = useApiError();
  const [signals, setSignals] = useState<any[]>([]);
  const [fetchedAt, setFetchedAt] = useState<Date | null>(null);
  const [orders, setOrders] = useState<any[]>([]);
  const [pairsSignals, setPairsSignals] = useState<any[]>([]);
  const [sentimentSignals, setSentimentSignals] = useState<any[]>([]);
  const [chileSignals, setChileSignals] = useState<any[]>([]);
  const [anomalyData, setAnomalyData] = useState<any>(null);
  const [causalData, setCausalData] = useState<any>(null);
  const [aisVessels, setAisVessels] = useState<any>(null);
  const [pairsDetail, setPairsDetail] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<number | null>(null);
  const [actionSuccess, setActionSuccess] = useState<number | null>(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [sigs, ords, pairs, sent, chile] = await Promise.all([
        api.signals(),
        api.orders(),
        api.pairsSignals(7).catch(handleError("signals_pairs")),
        api.sentimentSignals().catch(handleError("signals_sentiment")),
        api.chileSignals(14).catch(handleError("signals_chile")),
      ]);
      setSignals(sigs || []);
      setOrders(ords || []);
      setPairsSignals(Array.isArray(pairs) ? pairs : pairs?.signals || []);
      setSentimentSignals(Array.isArray(sent) ? sent : sent?.signals || []);
      setChileSignals(Array.isArray(chile) ? chile : chile?.signals || []);
      api.anomalyScores().then(setAnomalyData).catch(handleError("signals_anomaly_scores"));
      api.causalSummary().then(setCausalData).catch(handleError("signals_causal_summary"));
      api.aisTreatmentSignals().then(setAisVessels).catch(handleError("signals_ais_treatment"));
    } catch {
      /* empty */
    }
    setLoading(false);
    setFetchedAt(new Date());
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const handleConfirm = async (id: number) => {
    setActionLoading(id);
    try {
      await api.confirmSignal(id);
      setActionSuccess(id);
      setTimeout(() => setActionSuccess(null), 1500);
      await fetchAll();
    } catch { /* empty */ }
    setActionLoading(null);
  };

  const handleReject = async (id: number) => {
    setActionLoading(id);
    try {
      await api.rejectSignal(id);
      await fetchAll();
    } catch { /* empty */ }
    setActionLoading(null);
  };

  const pendingSignals = signals.filter((s) => s.status === "pending");
  const processedSignals = signals.filter((s) => s.status !== "pending");

  return (
    <ErrorBoundary fallbackTitle="Signals Intelligence error">
    <div className="space-y-6">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between"
      >
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] tracking-tight">
            {t("signals.title")}
          </h1>
          <div className="flex items-center gap-2 mt-1">
            <p className="text-sm text-[var(--text-secondary)]">
              Review pending trade signals and manage order execution
            </p>
            <DataQualityBadge provenance={{
              source: "BarentsWatch + SSB + Pairs + Sentiment",
              is_live: signals.length > 0,
              freshness: new Date().toISOString(),
              confidence: signals.length > 0 ? 0.85 : 0.3,
              fallback_reason: signals.length === 0 ? "No active signals" : null,
            }} />
            <FreshnessIndicator lastUpdated={fetchedAt} />
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/[0.03] backdrop-blur border border-white/[0.06]">
            <Zap className="w-4 h-4 text-ocean-400" />
            <span className="text-xs text-ocean-400 font-semibold">
              {pendingSignals.length} pending
            </span>
          </div>
          <button
            onClick={fetchAll}
            className="p-1.5 rounded-lg bg-white/[0.03] border border-white/[0.06] text-[var(--text-secondary)] hover:text-ocean-400 transition-colors"
            aria-label="Refresh signals"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </motion.div>

      {loading ? (
        <GlassCard delay={0}>
          <div className="flex flex-col items-center justify-center py-16">
            <Loader2 className="w-8 h-8 text-ocean-500/60 animate-spin mb-3" />
            <p className="text-sm text-[var(--text-secondary)]">{t("common.loading")}</p>
          </div>
        </GlassCard>
      ) : (
        <>
          {/* Early Warning System */}
          {anomalyData && (
            <GlassCard delay={0.02} accent={
              anomalyData.composite_risk_score >= 80 ? "rose" :
              anomalyData.composite_risk_score >= 40 ? "amber" : "emerald"
            }>
              <div className="flex items-center gap-2 mb-4">
                <Shield className="w-4 h-4 text-ocean-400" />
                <h3 className="text-sm font-semibold text-[var(--text-primary)]">
                  {t("signals.early_warning")}
                </h3>
              </div>
              <div className="flex items-center gap-6 mb-4">
                <div className="flex items-center gap-3">
                  <span className={`text-4xl font-black tabular-nums ${
                    anomalyData.composite_risk_score >= 80 ? "text-rose-400" :
                    anomalyData.composite_risk_score >= 60 ? "text-orange-400" :
                    anomalyData.composite_risk_score >= 40 ? "text-amber-400" : "text-emerald-400"
                  }`}>
                    {anomalyData.composite_risk_score != null ? formatNumber(anomalyData.composite_risk_score, locale) : "\u2014"}
                  </span>
                  <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-md ${
                    anomalyData.composite_risk_score >= 80 ? "bg-rose-500/10 text-rose-400 border border-rose-500/15" :
                    anomalyData.composite_risk_score >= 60 ? "bg-orange-500/10 text-orange-400 border border-orange-500/15" :
                    anomalyData.composite_risk_score >= 40 ? "bg-amber-500/10 text-amber-400 border border-amber-500/15" :
                    "bg-emerald-500/10 text-emerald-400 border border-emerald-500/15"
                  }`}>
                    {anomalyData.composite_risk_score >= 80 ? "CRITICAL" :
                     anomalyData.composite_risk_score >= 60 ? "HIGH" :
                     anomalyData.composite_risk_score >= 40 ? "MEDIUM" : "LOW"}
                  </span>
                </div>
                {anomalyData.summary && (
                  <p className="text-xs text-[var(--text-secondary)] flex-1">{anomalyData.summary}</p>
                )}
              </div>
              {Array.isArray(anomalyData.anomalies) && anomalyData.anomalies.length > 0 && (
                <div className="space-y-2">
                  {anomalyData.anomalies.map((a: any, i: number) => {
                    const sevColor =
                      a.severity === "critical" ? "rose" :
                      a.severity === "high" ? "orange" :
                      a.severity === "medium" ? "amber" : "emerald";
                    const categoryIcon =
                      a.category === "price" ? <TrendingDown className="w-3.5 h-3.5" /> :
                      a.category === "biological" ? <Globe className="w-3.5 h-3.5" /> :
                      a.category === "sentiment" ? <MessageSquare className="w-3.5 h-3.5" /> :
                      <Zap className="w-3.5 h-3.5" />;
                    return (
                      <motion.div
                        key={i}
                        initial={{ opacity: 0, x: -8 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: 0.05 + i * 0.03 }}
                        className="flex items-center gap-3 p-3 rounded-xl bg-white/[0.03] border border-white/[0.06]"
                      >
                        <span className={`text-${sevColor}-400`}>{categoryIcon}</span>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-0.5">
                            <span className="text-[11px] font-semibold text-[var(--text-primary)]">{a.source || a.category || "Unknown"}</span>
                            <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded bg-${sevColor}-500/10 text-${sevColor}-400 border border-${sevColor}-500/15`}>
                              {a.severity?.toUpperCase() || "—"}
                            </span>
                            <span className="text-[10px] font-mono text-[var(--text-secondary)]">
                              z={typeof a.z_score === "number" ? formatNumber(a.z_score, locale, 2) : "\u2014"}
                            </span>
                          </div>
                          <p className="text-[10px] text-[var(--text-secondary)] truncate">{a.message || "No details"}</p>
                        </div>
                      </motion.div>
                    );
                  })}
                </div>
              )}
            </GlassCard>
          )}

          {/* Pending Signals */}
          <GlassCard delay={0.05} accent="amber">
            <div className="flex items-center gap-2 mb-4">
              <Clock className="w-4 h-4 text-amber-400" />
              <h3 className="text-sm font-semibold text-[var(--text-primary)]">
                {t("signals.trading_signals")} ({pendingSignals.length})
              </h3>
            </div>
            {pendingSignals.length > 0 ? (
              <div className="space-y-3">
                {pendingSignals.map((sig, i) => (
                  <motion.div
                    key={sig.id || i}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.1 + i * 0.04 }}
                    className="flex items-center justify-between p-4 rounded-xl bg-white/[0.03] border border-white/[0.06] hover:bg-white/[0.05] transition-all"
                  >
                    <div className="flex items-center gap-4">
                      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-semibold ${
                        sig.direction === "SHORT"
                          ? "bg-rose-500/10 text-rose-400 border border-rose-500/15"
                          : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/15"
                      }`}>
                        {sig.direction === "SHORT" ? <TrendingDown className="w-3 h-3" /> : <TrendingUp className="w-3 h-3" />}
                        {sig.direction === "SHORT" ? t("signals.short") : t("signals.long")}
                      </span>
                      <div>
                        <p className="text-sm font-semibold text-[var(--text-primary)]">{sig.ticker}</p>
                        <p className="text-xs text-[var(--text-secondary)] max-w-md truncate">
                          Strength: {formatNumber((sig.strength || 0) * 100, locale)}% | {sig.rationale || "ML model signal"}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <OcButton
                        variant="success"
                        size="sm"
                        onClick={() => handleConfirm(sig.id)}
                        loading={actionLoading === sig.id}
                        showSuccess={actionSuccess === sig.id}
                        leftIcon={<CheckCircle className="w-3.5 h-3.5" />}
                      >
                        Confirm
                      </OcButton>
                      <OcButton
                        variant="danger"
                        size="sm"
                        onClick={() => handleReject(sig.id)}
                        loading={actionLoading === sig.id}
                        leftIcon={<XCircle className="w-3.5 h-3.5" />}
                      >
                        Reject
                      </OcButton>
                    </div>
                  </motion.div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-[var(--text-secondary)] text-center py-8">
                {t("common.no_data")}
              </p>
            )}
          </GlassCard>

          {/* Processed Signals */}
          {processedSignals.length > 0 && (
            <GlassCard delay={0.15}>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-[var(--text-primary)]">
                  Processed Signals
                </h3>
                <OcButton
                  variant="ghost"
                  size="xs"
                  onClick={() => exportToCSV(processedSignals, "signal_history")}
                  leftIcon={<Download className="w-3.5 h-3.5" />}
                >
                  Export CSV
                </OcButton>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-white/[0.06]">
                      <th className="text-left py-2.5 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Time</th>
                      <th className="text-left py-2.5 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Ticker</th>
                      <th className="text-left py-2.5 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Direction</th>
                      <th className="text-left py-2.5 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Strength</th>
                      <th className="text-left py-2.5 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {processedSignals.slice(0, 20).map((sig, i) => (
                      <tr key={sig.id || i} className="border-b border-white/[0.04] hover:bg-white/[0.02] transition-colors">
                        <td className="py-3 px-3 text-[var(--text-secondary)] text-xs font-mono">{sig.created_at?.slice(0, 16)?.replace("T", " ") || "—"}</td>
                        <td className="py-3 px-3 font-semibold">{sig.ticker}</td>
                        <td className="py-3 px-3">
                          <span className={sig.direction === "SHORT" ? "text-rose-400" : "text-emerald-400"}>
                            {sig.direction}
                          </span>
                        </td>
                        <td className="py-3 px-3 text-[var(--text-secondary)] font-mono tabular-nums">{formatNumber((sig.strength || 0) * 100, locale)}%</td>
                        <td className="py-3 px-3">
                          <span className={`text-[11px] font-medium px-2 py-0.5 rounded-md ${
                            sig.status === "confirmed" ? "bg-emerald-500/10 text-emerald-400" : "bg-rose-500/10 text-rose-400"
                          }`}>
                            {sig.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </GlassCard>
          )}

          {/* Intelligence Signals Row */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

            {/* Pairs Trading Signals */}
            <GlassCard delay={0.2}>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold flex items-center gap-2">
                  <GitBranch className="w-4 h-4 text-purple-400" />
                  {t("signals.pairs_trading")}
                </h3>
                <span className="text-[10px] text-[var(--text-secondary)]">7d window</span>
              </div>
              {pairsSignals.length === 0 ? (
                <p className="text-xs text-[var(--text-secondary)] py-6 text-center opacity-60">
                  No pairs signals — spreads at normal z-score
                </p>
              ) : (
                <div className="space-y-2">
                  {pairsSignals.slice(0, 5).map((ps: any, i: number) => (
                    <div key={i} className="p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[11px] font-bold text-[var(--text-primary)]">{ps.pair}</span>
                        <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${
                          ps.signal?.includes("LONG") ? "bg-emerald-500/10 text-emerald-400" :
                          ps.signal?.includes("SHORT") ? "bg-rose-500/10 text-rose-400" :
                          "bg-white/5 text-[var(--text-secondary)]"
                        }`}>
                          {ps.signal?.replace(/_/g, " ")}
                        </span>
                      </div>
                      <p className="text-[10px] text-[var(--text-secondary)] truncate">
                        z={ps.z_score != null ? formatNumber(ps.z_score, locale, 2) : "\u2014"} · conf={formatNumber((ps.confidence || 0) * 100, locale)}% · {ps.reversion_days}d horizon
                      </p>
                      {ps.causal_lag_weeks && (
                        <p className="text-[9px] text-ocean-400 mt-0.5">⚡ Causal lag: {ps.causal_lag_weeks}w ({ps.causal_confidence})</p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </GlassCard>

            {/* Sentiment Signals */}
            <GlassCard delay={0.22}>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold flex items-center gap-2">
                  <MessageSquare className="w-4 h-4 text-amber-400" />
                  {t("signals.sentiment")}
                </h3>
                <span className="text-[10px] text-[var(--text-secondary)]">NLP · News</span>
              </div>
              {sentimentSignals.length === 0 ? (
                <p className="text-xs text-[var(--text-secondary)] py-6 text-center opacity-60">
                  No strong sentiment signals detected
                </p>
              ) : (
                <div className="space-y-2">
                  {sentimentSignals.slice(0, 5).map((ss: any, i: number) => (
                    <div key={i} className="p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[11px] font-bold text-[var(--text-primary)]">{ss.ticker || ss.entity || "Market"}</span>
                        <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${
                          (ss.direction || ss.signal || "").toLowerCase().includes("bull") ? "bg-emerald-500/10 text-emerald-400" :
                          (ss.direction || ss.signal || "").toLowerCase().includes("bear") ? "bg-rose-500/10 text-rose-400" :
                          "bg-amber-500/10 text-amber-400"
                        }`}>
                          {ss.direction || ss.signal || "NEUTRAL"}
                        </span>
                      </div>
                      <p className="text-[10px] text-[var(--text-secondary)] truncate">
                        {ss.rationale || ss.summary || "News sentiment signal"}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </GlassCard>

            {/* Chile / Cross-Market Signals */}
            <GlassCard delay={0.24}>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold flex items-center gap-2">
                  <Globe className="w-4 h-4 text-ocean-400" />
                  Cross-Market (Chile)
                </h3>
                <span className="text-[10px] text-[var(--text-secondary)]">14d window</span>
              </div>
              {chileSignals.length === 0 ? (
                <p className="text-xs text-[var(--text-secondary)] py-6 text-center opacity-60">
                  No Chile arbitrage signals — markets in equilibrium
                </p>
              ) : (
                <div className="space-y-2">
                  {chileSignals.slice(0, 5).map((cs: any, i: number) => (
                    <div key={i} className="p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                      <div className="flex items-center justify-between mb-1">
                        <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${
                          cs.signal_type?.includes("BUY") ? "bg-emerald-500/10 text-emerald-400" :
                          cs.signal_type?.includes("SELL") ? "bg-rose-500/10 text-rose-400" :
                          "bg-ocean-500/10 text-ocean-400"
                        }`}>
                          {cs.signal_type || "MONITOR"}
                        </span>
                        <span className="text-[10px] text-[var(--text-secondary)]">
                          conf={formatNumber((cs.confidence || 0) * 100, locale)}%
                        </span>
                      </div>
                      <p className="text-[10px] text-[var(--text-secondary)] truncate">
                        {cs.rationale || cs.description || "Chile market signal"}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </GlassCard>
          </div>

          {/* Vessel Intelligence */}
          {aisVessels && (
            <GlassCard delay={0.26}>
              <div className="flex items-center gap-2 mb-3">
                <Globe className="w-4 h-4 text-cyan-400" />
                <h3 className="text-sm font-semibold text-[var(--text-primary)]">
                  Vessel Intelligence
                </h3>
                <span className="ml-auto text-[9px] px-1.5 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                  AIS Treatment Signals
                </span>
              </div>
              <div className="space-y-1.5">
                {(Array.isArray(aisVessels) ? aisVessels : aisVessels?.signals || []).slice(0, 6).map((v: any, i: number) => (
                  <div key={i} className="flex items-center justify-between p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                      <span className="text-[11px] text-ocean-400 font-medium">{v.vessel_name || v.vessel || "Unknown vessel"}</span>
                      <span className="text-[10px] text-[var(--text-secondary)]">&rarr;</span>
                      <span className="text-[11px] text-amber-400 font-medium truncate">{v.farm_name || v.locality || v.location || "Near farm"}</span>
                    </div>
                    <div className="flex items-center gap-3 flex-shrink-0">
                      <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${
                        (v.confidence || 0) > 0.7 ? "bg-emerald-500/10 text-emerald-400" : "bg-amber-500/10 text-amber-400"
                      }`}>
                        {formatNumber((v.confidence || 0) * 100, locale)}% conf
                      </span>
                      <span className="text-[10px] text-[var(--text-secondary)]">{v.duration_hours ? `${v.duration_hours}h` : ""}</span>
                    </div>
                  </div>
                ))}
                {(Array.isArray(aisVessels) ? aisVessels : aisVessels?.signals || []).length === 0 && (
                  <p className="text-xs text-[var(--text-secondary)] py-4 text-center opacity-60">No treatment vessel activity detected</p>
                )}
              </div>
            </GlassCard>
          )}

          {/* Causal Drivers */}
          {causalData && (
            <GlassCard delay={0.28}>
              <div className="flex items-center gap-2 mb-3">
                <GitBranch className="w-4 h-4 text-violet-400" />
                <h3 className="text-sm font-semibold text-[var(--text-primary)]">
                  {t("signals.causal_drivers")}
                </h3>
                <span className="ml-auto text-[9px] px-1.5 py-0.5 rounded-full bg-violet-500/10 text-violet-400 border border-violet-500/20">
                  Granger + Transfer Entropy
                </span>
              </div>
              <div className="space-y-1.5">
                {(causalData.relationships || causalData.granger_results || []).slice(0, 8).map((r: any, i: number) => (
                  <div key={i} className="flex items-center justify-between p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                      <span className="text-[11px] text-ocean-400 font-medium">{r.cause || r.driver || r.x || "Factor"}</span>
                      <span className="text-[10px] text-[var(--text-secondary)]">&rarr;</span>
                      <span className="text-[11px] text-amber-400 font-medium">{r.effect || r.target || r.y || "Price"}</span>
                    </div>
                    <div className="flex items-center gap-3 flex-shrink-0">
                      {r.lag != null && (
                        <span className="text-[10px] text-[var(--text-secondary)] tabular-nums">{r.lag}w lag</span>
                      )}
                      {r.p_value != null && (
                        <span className={`text-[10px] tabular-nums ${r.p_value < 0.05 ? "text-emerald-400" : "text-[var(--text-secondary)]"}`}>
                          p={formatNumber(r.p_value, locale, 3)}
                        </span>
                      )}
                      {r.significance && (
                        <span className={`text-[9px] px-1.5 py-0.5 rounded-full ${
                          r.significance === "strong" ? "bg-emerald-500/10 text-emerald-400"
                          : r.significance === "moderate" ? "bg-amber-500/10 text-amber-400"
                          : "bg-gray-500/10 text-gray-400"
                        }`}>
                          {r.significance}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
                {causalData.summary && (
                  <p className="text-[10px] text-[var(--text-secondary)] mt-2 opacity-60">{causalData.summary}</p>
                )}
              </div>
            </GlassCard>
          )}

          {/* Order History */}
          <GlassCard delay={0.3}>
            <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-4">
              Order History
            </h3>
            {orders.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-white/[0.06]">
                      <th className="text-left py-2.5 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Date</th>
                      <th className="text-left py-2.5 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Ticker</th>
                      <th className="text-left py-2.5 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Side</th>
                      <th className="text-left py-2.5 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Qty</th>
                      <th className="text-left py-2.5 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Price</th>
                      <th className="text-left py-2.5 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {orders.map((ord: any, i: number) => (
                      <tr key={ord.id || i} className="border-b border-white/[0.04] hover:bg-white/[0.02] transition-colors">
                        <td className="py-3 px-3 text-[var(--text-secondary)] text-xs font-mono">{ord.created_at?.slice(0, 10) || "—"}</td>
                        <td className="py-3 px-3 font-semibold">{ord.ticker || "—"}</td>
                        <td className="py-3 px-3">
                          <span className={ord.side === "SELL" ? "text-rose-400" : "text-emerald-400"}>
                            {ord.side || "—"}
                          </span>
                        </td>
                        <td className="py-3 px-3 font-mono">{ord.quantity || "—"}</td>
                        <td className="py-3 px-3 font-mono">{ord.price || "—"}</td>
                        <td className="py-3 px-3 text-xs text-[var(--text-secondary)]">{ord.status || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm text-[var(--text-secondary)] text-center py-8">
                {t("common.no_data")}
              </p>
            )}
          </GlassCard>
        </>
      )}
    </div>
    </ErrorBoundary>
  );
}
