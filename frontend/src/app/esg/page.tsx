"use client";
import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  Leaf, Shield, Users, Award, TrendingUp, TrendingDown,
  RefreshCw, ChevronRight, BarChart3, Download,
} from "lucide-react";
import KPICard from "@/components/KPICard";
import GlassCard from "@/components/GlassCard";
import TrendComparison from "@/components/TrendComparison";
import { OcButton } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { useApiError } from "@/lib/useApiError";
import { exportToCSV } from "@/lib/export";
import { useTranslation } from "@/lib/i18n";

/* eslint-disable @typescript-eslint/no-explicit-any */

const GRADE_COLORS: Record<string, string> = {
  "A+": "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  "A":  "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  "B+": "text-ocean-400 bg-ocean-500/10 border-ocean-500/20",
  "B":  "text-ocean-400 bg-ocean-500/10 border-ocean-500/20",
  "C":  "text-amber-400 bg-amber-500/10 border-amber-500/20",
  "D":  "text-orange-400 bg-orange-500/10 border-orange-500/20",
  "F":  "text-rose-400 bg-rose-500/10 border-rose-500/20",
};

export default function ESGPage() {
  const { t } = useTranslation();
  const handleError = useApiError();
  const [scores, setScores] = useState<any[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [selected, setSelected] = useState<any>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [yoyLice, setYoyLice] = useState<any>(null);

  const load = async () => {
    setLoading(true);
    const [s, sum] = await Promise.allSettled([api.esgScores(), api.esgSummary()]);
    if (s.status === "fulfilled") setScores(s.value || []);
    if (sum.status === "fulfilled") setSummary(sum.value);
    setLoading(false);
  };

  useEffect(() => {
    load();
    api.yoyComparison("lice").then(setYoyLice).catch(handleError("esg_yoy_lice"));
  }, []);

  const handleRowClick = async (co: any) => {
    if (selected?.company_name === co.company_name) {
      setSelected(null);
      return;
    }
    setDetailLoading(true);
    try {
      const detail = await api.esgCompany(co.company_name);
      setSelected(detail);
    } catch {
      setSelected(co); // fallback to index data
    }
    setDetailLoading(false);
  };

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] flex items-center gap-3">
            <Leaf className="w-6 h-6 text-emerald-400" />
            {t("nav.leaders_esg")}
          </h1>
          <p className="text-sm text-[var(--text-secondary)] mt-1">
            Environmental, Social &amp; Governance scoring for
            {loading ? " \u2026" : ` ${scores.length}`} salmon producers
          </p>
        </div>
        <OcButton variant="secondary" size="sm" onClick={load} loading={loading}
          leftIcon={<RefreshCw className="w-3.5 h-3.5" />}>Refresh</OcButton>
      </motion.div>

      {/* KPIs */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <KPICard label="Industry Average" value={summary.avg_score} delta="out of 100"
            icon={BarChart3} delay={0} />
          <KPICard label="Top Company" value={summary.top_company}
            delta={`Score: ${summary.top_score} (${summary.top_grade})`}
            deltaType="positive" icon={Award} delay={0.04} />
          <KPICard label="A+ / A Grades" value={(summary.grade_distribution?.["A+"] || 0) + (summary.grade_distribution?.["A"] || 0)}
            delta={`of ${summary.n_companies} companies`}
            deltaType="positive" icon={Leaf} delay={0.08} />
          <KPICard label="D / F Grades" value={(summary.grade_distribution?.D || 0) + (summary.grade_distribution?.F || 0)}
            delta="Improvement needed"
            deltaType={(summary.grade_distribution?.D || 0) + (summary.grade_distribution?.F || 0) > 5 ? "negative" : "positive"}
            icon={Shield} delay={0.12} />
        </div>
      )}

      {/* Industry Lice YoY — Environmental Context */}
      {yoyLice && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <TrendComparison
            metric="lice"
            label="Industry Lice Trend (E-score driver)"
            unit="lice/fish"
            currentYear={yoyLice.current_year || []}
            previousYear={yoyLice.previous_year || []}
            twoYearsAgo={yoyLice.two_years_ago || []}
            years={yoyLice.years}
          />
        </div>
      )}

      {/* Company Ranking Table */}
      <GlassCard delay={0.15}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold flex items-center gap-2">
            <Award className="w-4 h-4 text-emerald-400" />
            ESG Rankings
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              {scores.length} companies
            </span>
          </h3>
          {scores.length > 0 && (
            <OcButton variant="ghost" size="sm" leftIcon={<Download className="w-3.5 h-3.5" />}
              onClick={() => exportToCSV(scores.map((co: any) => ({
                Rank: co.rank, Company: co.company_name, Ticker: co.ticker || "",
                Grade: co.grade, Total: co.total, Environmental: co.environmental,
                Social: co.social, Governance: co.governance, Sites: co.n_localities,
              })), "esg_rankings")}>Export CSV</OcButton>
          )}
        </div>
        <div className="overflow-x-auto max-h-[500px] overflow-y-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-ocean-950/95 backdrop-blur z-10">
              <tr className="border-b border-white/[0.06]">
                <th className="text-left py-2 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">#</th>
                <th className="text-left py-2 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Company</th>
                <th className="text-center py-2 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Grade</th>
                <th className="text-center py-2 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Total</th>
                <th className="text-center py-2 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Env</th>
                <th className="text-center py-2 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Social</th>
                <th className="text-center py-2 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Gov</th>
                <th className="text-center py-2 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Sites</th>
              </tr>
            </thead>
            <tbody>
              {scores.map((co, i) => (
                <motion.tr
                  key={co.company_name}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: Math.min(i * 0.01, 0.3) }}
                  onClick={() => handleRowClick(co)}
                  className={`border-b border-white/[0.04] hover:bg-white/[0.03] cursor-pointer transition-colors ${
                    selected?.company_name === co.company_name ? "bg-ocean-500/[0.04]" : ""
                  }`}
                >
                  <td className="py-2.5 px-3 text-[var(--text-secondary)] text-xs">{co.rank}</td>
                  <td className="py-2.5 px-3">
                    <div>
                      <span className="font-semibold text-[var(--text-primary)]">{co.company_name}</span>
                      {co.ticker && <span className="text-[9px] text-ocean-400 ml-1.5 font-mono">{co.ticker}</span>}
                    </div>
                  </td>
                  <td className="py-2.5 px-3 text-center">
                    <span className={`text-[11px] font-bold px-2 py-0.5 rounded-md border ${GRADE_COLORS[co.grade] || GRADE_COLORS.C}`}>
                      {co.grade}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-center font-mono font-semibold">{co.total}</td>
                  <td className="py-2.5 px-3 text-center">
                    <span className="text-xs text-emerald-400">{co.environmental}/40</span>
                  </td>
                  <td className="py-2.5 px-3 text-center">
                    <span className="text-xs text-ocean-400">{co.social}/30</span>
                  </td>
                  <td className="py-2.5 px-3 text-center">
                    <span className="text-xs text-violet-400">{co.governance}/30</span>
                  </td>
                  <td className="py-2.5 px-3 text-center text-[var(--text-secondary)] text-xs">{co.n_localities}</td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
      </GlassCard>

      {/* Detail Panel */}
      {(selected || detailLoading) && (
        <GlassCard delay={0}>
          <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
            {detailLoading ? "Loading\u2026" : <>{selected.company_name} &mdash; ESG Breakdown</>}
            <span className={`ml-auto text-sm font-bold px-3 py-1 rounded-lg border ${GRADE_COLORS[selected.grade] || GRADE_COLORS.C}`}>
              {selected.grade} ({selected.total}/100)
            </span>
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Environmental */}
            <div className="space-y-2">
              <h4 className="text-[11px] font-semibold text-emerald-400 uppercase tracking-wider flex items-center gap-1.5">
                <Leaf className="w-3.5 h-3.5" /> Environmental ({selected.environmental}/40)
              </h4>
              {[
                { label: "Lice Performance", value: selected.breakdown?.e_lice, max: 15 },
                { label: "Treatment Impact", value: selected.breakdown?.e_treatment, max: 10 },
                { label: "Bloom Exposure", value: selected.breakdown?.e_bloom, max: 10 },
                { label: "Cleaner Fish Use", value: selected.breakdown?.e_cleaner_fish, max: 5 },
              ].map(item => (
                <div key={item.label} className="flex items-center justify-between p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                  <span className="text-[10px] text-[var(--text-secondary)]">{item.label}</span>
                  <div className="flex items-center gap-2">
                    <div className="w-12 h-1.5 bg-white/[0.06] rounded-full overflow-hidden">
                      <div className="h-full rounded-full bg-emerald-500" style={{ width: `${(item.value / item.max) * 100}%` }} />
                    </div>
                    <span className="text-[10px] font-mono text-emerald-400">{item.value}/{item.max}</span>
                  </div>
                </div>
              ))}
            </div>
            {/* Social */}
            <div className="space-y-2">
              <h4 className="text-[11px] font-semibold text-ocean-400 uppercase tracking-wider flex items-center gap-1.5">
                <Users className="w-3.5 h-3.5" /> Social ({selected.social}/30)
              </h4>
              {[
                { label: "Fish Welfare", value: selected.breakdown?.s_welfare, max: 15 },
                { label: "Treatment Method", value: selected.breakdown?.s_treatment_method, max: 10 },
                { label: "Regulatory", value: selected.breakdown?.s_regulatory, max: 5 },
              ].map(item => (
                <div key={item.label} className="flex items-center justify-between p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                  <span className="text-[10px] text-[var(--text-secondary)]">{item.label}</span>
                  <div className="flex items-center gap-2">
                    <div className="w-12 h-1.5 bg-white/[0.06] rounded-full overflow-hidden">
                      <div className="h-full rounded-full bg-ocean-500" style={{ width: `${(item.value / item.max) * 100}%` }} />
                    </div>
                    <span className="text-[10px] font-mono text-ocean-400">{item.value}/{item.max}</span>
                  </div>
                </div>
              ))}
            </div>
            {/* Governance */}
            <div className="space-y-2">
              <h4 className="text-[11px] font-semibold text-violet-400 uppercase tracking-wider flex items-center gap-1.5">
                <Shield className="w-3.5 h-3.5" /> Governance ({selected.governance}/30)
              </h4>
              {[
                { label: "Reporting Quality", value: selected.breakdown?.g_reporting, max: 15 },
                { label: "Peer Performance", value: selected.breakdown?.g_peer, max: 10 },
                { label: "Geographic Diversity", value: selected.breakdown?.g_diversity, max: 5 },
              ].map(item => (
                <div key={item.label} className="flex items-center justify-between p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                  <span className="text-[10px] text-[var(--text-secondary)]">{item.label}</span>
                  <div className="flex items-center gap-2">
                    <div className="w-12 h-1.5 bg-white/[0.06] rounded-full overflow-hidden">
                      <div className="h-full rounded-full bg-violet-500" style={{ width: `${(item.value / item.max) * 100}%` }} />
                    </div>
                    <span className="text-[10px] font-mono text-violet-400">{item.value}/{item.max}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </GlassCard>
      )}

      <p className="text-[10px] text-[var(--text-secondary)] text-center opacity-60">
        ESG scores computed from BarentsWatch lice data (NLOD 2.0), treatment records, regulatory regime states,
        and reporting completeness. Scoring framework: Environmental (40pts) + Social (30pts) + Governance (30pts).
        Updated hourly. Not investment advice.
      </p>
    </div>
  );
}
