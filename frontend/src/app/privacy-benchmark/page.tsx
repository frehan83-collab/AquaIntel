/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  ShieldCheck, Search, RefreshCw, TrendingUp, TrendingDown,
  Users, Award, BarChart3, Lock, ChevronDown,
} from "lucide-react";
import GlassCard from "@/components/GlassCard";
import KPICard from "@/components/KPICard";
import { OcButton } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";

const VERDICT_COLORS: Record<string, string> = {
  "Top Performer": "text-emerald-400",
  "Above Average": "text-ocean-400",
  "Average": "text-amber-400",
  "Below Average": "text-orange-400",
  "Needs Improvement": "text-rose-400",
};

const VERDICT_BG: Record<string, string> = {
  "Top Performer": "bg-emerald-500/10 border-emerald-500/20",
  "Above Average": "bg-ocean-500/10 border-ocean-500/20",
  "Average": "bg-amber-500/10 border-amber-500/20",
  "Below Average": "bg-orange-500/10 border-orange-500/20",
  "Needs Improvement": "bg-rose-500/10 border-rose-500/20",
};

export default function PrivacyBenchmarkPage() {
  const { t } = useTranslation();
  const [companyName, setCompanyName] = useState("Mowi");
  const [report, setReport] = useState<any>(null);
  const [cohorts, setCohorts] = useState<any[]>([]);
  const [privacyInfo, setPrivacyInfo] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const load = async (name?: string) => {
    setLoading(true);
    const target = name || companyName;
    const [r1, r2, r3] = await Promise.allSettled([
      api.federatedCompany(target),
      api.federatedCohorts(),
      api.federatedPrivacyInfo(),
    ]);
    if (r1.status === "fulfilled") setReport(r1.value);
    if (r2.status === "fulfilled") setCohorts(r2.value || []);
    if (r3.status === "fulfilled") setPrivacyInfo(r3.value);
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const metrics = report?.metrics || [];
  const insights = report?.insights || [];
  const cohort = report?.cohort || {};

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] flex items-center gap-3">
            <ShieldCheck className="w-6 h-6 text-emerald-400" />
            Privacy-Preserving Benchmark
          </h1>
          <p className="text-sm text-[var(--text-secondary)] mt-1">
            Compare your performance against peers &mdash; differential privacy protects individual data
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20">
            <Lock className="w-3 h-3 text-emerald-400" />
            <span className="text-[10px] font-semibold text-emerald-400">&epsilon;={report?.epsilon || 1.0} DP</span>
          </div>
        </div>
      </motion.div>

      {/* Company Search */}
      <GlassCard delay={0.05}>
        <div className="flex items-center gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-2.5 w-4 h-4 text-[var(--text-secondary)]" />
            <input
              type="text"
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && load()}
              placeholder="Enter company name..."
              className="w-full pl-10 pr-4 py-2 text-sm rounded-lg bg-white/[0.04] border border-white/[0.08] text-[var(--text-primary)] focus:outline-none focus:border-ocean-500/40"
            />
          </div>
          <OcButton variant="primary" size="sm" onClick={() => load()} loading={loading}
            leftIcon={<RefreshCw className="w-3.5 h-3.5" />}>Analyze</OcButton>
        </div>
      </GlassCard>

      {report?.error ? (
        <GlassCard delay={0.1}>
          <p className="text-sm text-rose-400 text-center py-8">{report.error}</p>
        </GlassCard>
      ) : report && (
        <>
          {/* KPI Row */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <KPICard label="Your Cohort"
              value={cohort.size_tier?.charAt(0).toUpperCase() + (cohort.size_tier?.slice(1) || "")}
              delta={cohort.description} icon={Users} delay={0} />
            <KPICard label="Cohort Rank"
              value={`P${report.overall_percentile?.toFixed(0) || 50}`}
              delta={report.overall_verdict}
              deltaType={report.overall_percentile >= 60 ? "positive" : report.overall_percentile <= 40 ? "negative" : "neutral"}
              icon={Award} delay={0.03} />
            <KPICard label="Peer Group Size"
              value={`~${cohort.n_companies || 0}`}
              delta="Companies (noised)" icon={BarChart3} delay={0.06} />
            <KPICard label="Privacy Level"
              value={`\u03B5=${report.epsilon || 1.0}`}
              delta="Laplace mechanism" icon={Lock} delay={0.09} />
          </div>

          {/* Metric Cards */}
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
            {metrics.map((m: any, i: number) => (
              <GlassCard key={i} delay={0.1 + i * 0.03} accent={
                m.cohort_percentile >= 75 ? "emerald" :
                m.cohort_percentile <= 25 ? "rose" : "ocean"
              }>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-semibold text-[var(--text-primary)]">{m.metric}</h3>
                  <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-md border ${VERDICT_BG[m.verdict] || "bg-white/[0.04] border-white/[0.08]"}`}>
                    <span className={VERDICT_COLORS[m.verdict] || "text-[var(--text-secondary)]"}>{m.verdict}</span>
                  </span>
                </div>

                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-[var(--text-secondary)]">Your Value</span>
                    <span className="text-sm font-bold text-[var(--text-primary)]">{m.your_value?.toFixed(3)}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-[var(--text-secondary)]">Cohort Avg <Lock className="w-2.5 h-2.5 inline ml-0.5 opacity-40" /></span>
                    <span className="text-sm text-[var(--text-secondary)]">~{m.cohort_avg?.toFixed(3)}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-[var(--text-secondary)]">Industry Avg <Lock className="w-2.5 h-2.5 inline ml-0.5 opacity-40" /></span>
                    <span className="text-sm text-[var(--text-secondary)]">~{m.industry_avg?.toFixed(3)}</span>
                  </div>

                  {/* Percentile bar */}
                  <div className="pt-2">
                    <div className="flex justify-between text-[9px] text-[var(--text-secondary)] mb-1">
                      <span>Cohort Percentile</span>
                      <span className={VERDICT_COLORS[m.verdict]}>{m.cohort_percentile?.toFixed(0)}th</span>
                    </div>
                    <div className="h-2 bg-white/[0.06] rounded-full overflow-hidden">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${Math.max(2, m.cohort_percentile || 0)}%` }}
                        transition={{ duration: 0.8, delay: 0.2 + i * 0.05 }}
                        className={`h-full rounded-full ${
                          m.cohort_percentile >= 75 ? "bg-emerald-500" :
                          m.cohort_percentile >= 50 ? "bg-ocean-500" :
                          m.cohort_percentile >= 25 ? "bg-amber-500" : "bg-rose-500"
                        }`}
                      />
                    </div>
                  </div>
                </div>
              </GlassCard>
            ))}
          </div>

          {/* Insights */}
          {insights.length > 0 && (
            <GlassCard delay={0.3} accent="ocean">
              <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-ocean-400" />
                Privacy-Safe Insights
              </h3>
              <div className="space-y-2">
                {insights.map((insight: string, i: number) => (
                  <div key={i} className="flex items-start gap-2 p-2.5 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                    <span className="text-ocean-400 text-xs mt-0.5">&bull;</span>
                    <p className="text-xs text-[var(--text-secondary)] leading-relaxed">{insight}</p>
                  </div>
                ))}
              </div>
            </GlassCard>
          )}

          {/* Cohorts Overview */}
          {cohorts.length > 0 && (
            <GlassCard delay={0.35}>
              <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
                <Users className="w-4 h-4 text-violet-400" />
                Peer Cohorts
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
                {cohorts.map((c: any, i: number) => (
                  <div key={i} className={`p-3 rounded-xl border ${
                    c.cohort_id === cohort.cohort_id
                      ? "border-ocean-500/30 bg-ocean-500/[0.06]"
                      : "border-white/[0.06] bg-white/[0.02]"
                  }`}>
                    <div className="text-[11px] font-bold text-[var(--text-primary)]">{c.cohort_id?.replace("_", " \u00B7 ")}</div>
                    <div className="text-[10px] text-[var(--text-secondary)] mt-0.5">~{c.n_companies} companies</div>
                    <div className="text-[9px] text-[var(--text-secondary)] mt-0.5">{c.description}</div>
                    {c.cohort_id === cohort.cohort_id && (
                      <div className="text-[9px] text-ocean-400 font-semibold mt-1">&larr; Your cohort</div>
                    )}
                  </div>
                ))}
              </div>
            </GlassCard>
          )}
        </>
      )}

      {/* Privacy Info */}
      <GlassCard delay={0.4} accent="none" hover={false}>
        <details>
          <summary className="text-[11px] text-[var(--text-secondary)] cursor-pointer hover:text-ocean-400 transition-colors flex items-center gap-2">
            <Lock className="w-3 h-3" />
            Privacy Guarantee Details
          </summary>
          <div className="mt-3 text-xs text-[var(--text-secondary)] space-y-2 leading-relaxed">
            <p>{privacyInfo?.guarantee || "Differential privacy protects individual company data."}</p>
            <div className="grid grid-cols-3 gap-3 mt-2">
              <div className="p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                <div className="text-[10px] text-[var(--text-secondary)] uppercase">Stats &epsilon;</div>
                <div className="text-sm font-bold text-[var(--text-primary)]">{privacyInfo?.epsilon_stats || 1.0}</div>
              </div>
              <div className="p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                <div className="text-[10px] text-[var(--text-secondary)] uppercase">Percentile &epsilon;</div>
                <div className="text-sm font-bold text-[var(--text-primary)]">{privacyInfo?.epsilon_percentile || 0.5}</div>
              </div>
              <div className="p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                <div className="text-[10px] text-[var(--text-secondary)] uppercase">Min Cohort</div>
                <div className="text-sm font-bold text-[var(--text-primary)]">{privacyInfo?.min_cohort_size || 5}</div>
              </div>
            </div>
          </div>
        </details>
      </GlassCard>

      <p className="text-[10px] text-[var(--text-secondary)] text-center opacity-60">
        All peer statistics include calibrated Laplace noise (&epsilon;-differential privacy). No individual company data is revealed.
        Cohort sizes rounded to nearest 5. Percentile values approximate. Not financial advice.
      </p>
    </div>
  );
}
