"use client";
import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  GitBranch, TrendingUp, Activity, RefreshCw, AlertCircle,
  Brain, Target, Clock, ChevronRight, BarChart3, Zap, Download,
} from "lucide-react";
import GlassCard from "@/components/GlassCard";
import KPICard from "@/components/KPICard";
import { OcButton } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { useTranslation, formatNumber } from "@/lib/i18n";
import { exportToCSV } from "@/lib/export";
import ErrorBoundary from "@/components/ErrorBoundary";
import DataQualityBadge from "@/components/DataQualityBadge";

/* eslint-disable @typescript-eslint/no-explicit-any */

function LagBarChart({ results, type, locale }: { results: any[]; type: "granger" | "te"; locale: "en" | "no" }) {
  if (!results || results.length === 0) return null;

  const values = results.map((r: any) => type === "granger" ? r.f_stat : r.z_score);
  const maxVal = Math.max(...values.map(Math.abs), 1);
  const dominantLag = results.reduce((best: any, r: any) =>
    (type === "granger" ? r.f_stat : r.z_score) > (type === "granger" ? best.f_stat : best.z_score)
    ? r : best
  );

  return (
    <div className="space-y-1">
      {results.map((r: any, i: number) => {
        const val = type === "granger" ? r.f_stat : r.z_score;
        const sig = type === "granger" ? r.significant : r.p_value < 0.05;
        const isDominant = r.lag === dominantLag.lag;
        const barW = Math.abs(val) / maxVal * 100;

        return (
          <div key={r.lag} className={`flex items-center gap-2 py-0.5 rounded px-1 ${isDominant ? "bg-ocean-500/[0.06]" : ""}`}>
            <span className="text-[9px] font-mono text-[var(--text-secondary)] w-10 flex-shrink-0">
              {isDominant && <span className="text-ocean-400">★ </span>}
              L{r.lag}
            </span>
            <div className="flex-1 h-2 bg-white/[0.04] rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full ${
                  isDominant ? "bg-ocean-500" :
                  sig ? "bg-emerald-500/60" : "bg-white/10"
                }`}
                style={{ width: `${barW}%` }}
              />
            </div>
            <span className={`text-[9px] font-mono w-12 text-right ${
              isDominant ? "text-ocean-400 font-bold" : sig ? "text-emerald-400" : "text-[var(--text-secondary)]"
            }`}>
              {formatNumber(val, locale, 2)}
            </span>
            {sig && <span className="text-[8px] text-emerald-400">*</span>}
          </div>
        );
      })}
      <p className="text-[9px] text-[var(--text-secondary)] mt-1 opacity-60">
        ★ = dominant lag · * = significant (p&lt;0.05)
      </p>
    </div>
  );
}

export default function CausalPage() {
  const { t, locale } = useTranslation();
  const [summary, setSummary] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.causalSummary(16);
      setSummary(result);
    } catch (e: any) {
      setError(e?.message || "Failed to run causal analysis");
    }
    setLoading(false);
  };

  useEffect(() => {
    // Auto-run on mount
    run();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const domLag = summary?.dominant_lag_weeks;
  const confidence = summary?.confidence;
  const method = summary?.method_used;
  const grangerResults = summary?.granger_results || [];
  const teResults = summary?.te_results || [];
  const lagRange = summary?.recommended_lag_range;
  const asymmetry = summary?.asymmetry_detected;

  return (
    <ErrorBoundary fallbackTitle="Causal Engine error">
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-3">
            <GitBranch className="w-6 h-6 text-ocean-400" />
            {t("causal.title")}
            <DataQualityBadge quality="live" source="SSB + BarentsWatch" />
          </h1>
          <p className="text-sm text-[var(--text-secondary)] mt-1">
            Granger causality · Transfer entropy · PCMCI — discovers true lice→price lag from data
          </p>
        </div>
        <div className="flex items-center gap-2">
          {grangerResults.length > 0 && (
            <OcButton variant="ghost" size="sm" leftIcon={<Download className="w-3.5 h-3.5" />}
              onClick={() => exportToCSV([
                ...grangerResults.map((r: any) => ({
                  Method: "Granger", Lag: r.lag, "F-Stat": r.f_stat,
                  "P-Value": r.p_value, Significant: r.significant ? "Yes" : "No",
                })),
                ...teResults.map((r: any) => ({
                  Method: "Transfer Entropy", Lag: r.lag, "Z-Score": r.z_score,
                  "P-Value": r.p_value, Significant: r.p_value < 0.05 ? "Yes" : "No",
                })),
              ], "causal_results")}>Export CSV</OcButton>
          )}
          <OcButton
            variant="primary"
            size="sm"
            loading={loading}
            onClick={run}
            leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
          >
            Run Analysis
          </OcButton>
        </div>
      </div>

      {error && (
        <div className="flex items-start gap-2 p-3 rounded-xl border border-rose-500/20 bg-rose-500/[0.04]">
          <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-rose-300">{error}</p>
        </div>
      )}

      {/* KPI Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KPICard
          label={t("causal.lag_weeks")}
          value={domLag ? `${domLag} weeks` : "—"}
          delta={domLag ? `Lice → Price delay` : "Run analysis to discover"}
          deltaType={domLag ? "positive" : undefined}
          icon={Clock}
          delay={0}
        />
        <KPICard
          label={t("causal.correlation")}
          value={confidence ? confidence.toUpperCase() : "—"}
          delta={method ? `via ${method}` : ""}
          deltaType={confidence === "high" ? "positive" : confidence === "medium" ? undefined : "negative"}
          icon={Target}
          delay={0.05}
        />
        <KPICard
          label="Lag Range"
          value={lagRange ? `W${lagRange[0]}–W${lagRange[1]}` : "—"}
          delta="Recommended entry window"
          icon={Activity}
          delay={0.1}
        />
        <KPICard
          label="Asymmetry"
          value={asymmetry !== undefined ? (asymmetry ? "YES" : "NO") : "—"}
          delta={asymmetry ? "Up spike > Down recovery" : "Symmetric response"}
          deltaType={asymmetry ? "negative" : "positive"}
          icon={Zap}
          delay={0.15}
        />
      </div>

      {summary && (
        <>
          {/* Interpretation */}
          <GlassCard delay={0.2} accent="ocean">
            <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
              <Brain className="w-4 h-4 text-ocean-400" />
              Causal Interpretation
            </h3>
            <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
              {summary.interpretation}
            </p>
            {lagRange && (
              <div className="mt-3 p-3 rounded-lg bg-ocean-500/[0.06] border border-ocean-500/20">
                <p className="text-[11px] text-ocean-300 font-medium">
                  Trading implication: Detect lice outbreak &rarr; wait {lagRange[0]}&ndash;{lagRange[1]} weeks &rarr; enter long position on Oslo-listed salmon equities
                </p>
              </div>
            )}
          </GlassCard>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Granger Causality Results */}
            {grangerResults.length > 0 && (
              <GlassCard delay={0.3}>
                <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
                  <BarChart3 className="w-4 h-4 text-emerald-400" />
                  {t("causal.granger_relationships")}
                  <span className="ml-auto text-[9px] text-[var(--text-secondary)]">Lice → Price</span>
                </h3>
                <LagBarChart results={grangerResults} type="granger" locale={locale} />
              </GlassCard>
            )}

            {/* Transfer Entropy Results */}
            {teResults.length > 0 && (
              <GlassCard delay={0.35}>
                <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-purple-400" />
                  Transfer Entropy (KSG estimator)
                  <span className="ml-auto text-[9px] text-[var(--text-secondary)]">Lice → Price</span>
                </h3>
                <LagBarChart results={teResults} type="te" locale={locale} />
              </GlassCard>
            )}
          </div>

          {/* PCMCI Results */}
          {summary.pcmci_available && summary.pcmci_results && (
            <GlassCard delay={0.4} accent="violet">
              <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
                <GitBranch className="w-4 h-4 text-purple-400" />
                PCMCI Causal Graph (Tigramite)
              </h3>
              <pre className="text-[10px] text-[var(--text-secondary)] font-mono overflow-x-auto whitespace-pre-wrap">
                {JSON.stringify(summary.pcmci_results, null, 2)}
              </pre>
            </GlassCard>
          )}

          {/* Literature Context */}
          <GlassCard delay={0.45}>
            <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3">
              Academic Context
            </h3>
            <div className="space-y-2 text-[11px] text-[var(--text-secondary)]">
              <div className="flex gap-2">
                <ChevronRight className="w-3 h-3 text-ocean-400 flex-shrink-0 mt-0.5" />
                <p><span className="text-[var(--text-primary)] font-medium">Abolofia et al. (2017)</span> — Norwegian salmon prices are sensitive to supply shocks from disease events. Typical transmission lag 6–10 weeks.</p>
              </div>
              <div className="flex gap-2">
                <ChevronRight className="w-3 h-3 text-ocean-400 flex-shrink-0 mt-0.5" />
                <p><span className="text-[var(--text-primary)] font-medium">Asche et al. (2009, 2015)</span> — Integration of global salmon markets. Norwegian price movements transmit to Chilean/Canadian markets within 2–4 weeks.</p>
              </div>
              <div className="flex gap-2">
                <ChevronRight className="w-3 h-3 text-ocean-400 flex-shrink-0 mt-0.5" />
                <p><span className="text-[var(--text-primary)] font-medium">Asymmetry finding</span> — Sharp lice spikes produce stronger/faster price signals than lice declines, consistent with loss-aversion pricing in commodity spot markets.</p>
              </div>
            </div>
          </GlassCard>
        </>
      )}

      {!summary && !loading && !error && (
        <GlassCard delay={0.2}>
          <div className="py-12 text-center space-y-3">
            <GitBranch className="w-12 h-12 mx-auto opacity-20" />
            <p className="text-sm text-[var(--text-secondary)]">Click &ldquo;Run Analysis&rdquo; to discover the causal lag</p>
            <p className="text-xs text-[var(--text-secondary)] opacity-60">
              Requires BarentsWatch lice data and SSB price history in the database
            </p>
          </div>
        </GlassCard>
      )}

      <p className="text-[10px] text-[var(--text-secondary)] opacity-50 text-center">
        Granger causality and Transfer Entropy are statistical associations, not structural causal proof.
        Use in conjunction with domain expertise. Not financial advice.
      </p>
    </div>
    </ErrorBoundary>
  );
}
