"use client";
import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  Trophy, RefreshCw, TrendingUp, TrendingDown, BarChart3,
  Search, MapPin, Award, Shield, Leaf, Bug, ChevronRight,
} from "lucide-react";
import KPICard from "@/components/KPICard";
import GlassCard from "@/components/GlassCard";
import { OcButton } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { useTranslation, formatNumber, formatCurrency } from "@/lib/i18n";
import DataTable, { Column } from "@/components/DataTable";

/* eslint-disable @typescript-eslint/no-explicit-any */

const VERDICT_STYLE: Record<string, { bg: string; text: string }> = {
  "Excellent":         { bg: "bg-emerald-500/10 border-emerald-500/20", text: "text-emerald-400" },
  "Good":              { bg: "bg-ocean-500/10 border-ocean-500/20", text: "text-ocean-400" },
  "Average":           { bg: "bg-amber-500/10 border-amber-500/20", text: "text-amber-400" },
  "Below Average":     { bg: "bg-orange-500/10 border-orange-500/20", text: "text-orange-400" },
  "Needs Improvement": { bg: "bg-rose-500/10 border-rose-500/20", text: "text-rose-400" },
};

const PA_NAMES: Record<number, string> = {
  1: "Svenskegrensen\u2013J\u00e6ren", 2: "Ryfylke", 3: "Karm\u00f8y\u2013Sotra",
  4: "Nordhordland\u2013Stadt", 5: "Stadt\u2013Hustadvika", 6: "Nordm\u00f8re\u2013S\u00f8r-Tr\u00f8ndelag",
  7: "Nord-Tr\u00f8ndelag\u2013Bindal", 8: "Helgeland\u2013Bod\u00f8", 9: "Vestfjorden\u2013Vester\u00e5len",
  10: "And\u00f8ya\u2013Kval\u00f8ya", 11: "Kval\u00f8ya\u2013Senja", 12: "Vest-Finnmark", 13: "\u00d8st-Finnmark",
};

export default function BenchmarkPage() {
  const { t, locale } = useTranslation();
  const [leaderboard, setLeaderboard] = useState<any[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [selected, setSelected] = useState<any>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedPA, setSelectedPA] = useState<number | null>(null);
  const [paData, setPaData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    const [lb, sum] = await Promise.allSettled([
      api.benchmarkLeaderboard(50),
      api.benchmarkSummary(),
    ]);
    if (lb.status === "fulfilled") setLeaderboard(lb.value || []);
    if (sum.status === "fulfilled") setSummary(sum.value);
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const loadCompany = async (name: string) => {
    try {
      const data = await api.benchmarkCompany(name);
      setSelected(data);
    } catch { setSelected(null); }
  };

  const loadPA = async (pa: number) => {
    if (selectedPA === pa) { setSelectedPA(null); setPaData([]); return; }
    setSelectedPA(pa);
    try {
      const data = await api.benchmarkPa(pa);
      setPaData(data || []);
    } catch { setPaData([]); }
  };

  const filtered = searchTerm
    ? leaderboard.filter(c =>
        c.company_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (c.ticker && c.ticker.toLowerCase().includes(searchTerm.toLowerCase()))
      )
    : leaderboard;

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] flex items-center gap-3">
            <Trophy className="w-6 h-6 text-amber-400" />
            {t("benchmark.title")}
          </h1>
          <p className="text-sm text-[var(--text-secondary)] mt-1">
            Anonymous performance comparison across {summary?.n_companies || "..."} Norwegian salmon producers
          </p>
        </div>
        <OcButton variant="secondary" size="sm" onClick={load} loading={loading}
          leftIcon={<RefreshCw className="w-3.5 h-3.5" />}>Refresh</OcButton>
      </motion.div>

      {/* KPIs */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <KPICard label="Companies Benchmarked" value={summary.n_companies}
            icon={BarChart3} delay={0} />
          <KPICard label="Top Performer" value={summary.top_performer || "\u2014"}
            delta={`${summary.top_percentile}th percentile`}
            deltaType="positive" icon={Trophy} delay={0.04} />
          <KPICard label="Excellent Ratings"
            value={summary.verdict_distribution?.Excellent || 0}
            delta="80th+ percentile"
            icon={Award} delay={0.08} />
          <KPICard label="Needs Improvement"
            value={summary.verdict_distribution?.["Needs Improvement"] || 0}
            delta="Below 20th percentile"
            deltaType={(summary.verdict_distribution?.["Needs Improvement"] || 0) > 10 ? "negative" : "positive"}
            icon={Shield} delay={0.12} />
        </div>
      )}

      {/* Search + PA Filter */}
      <div className="flex gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-secondary)]" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search company or ticker..."
            className="w-full pl-10 pr-4 py-2.5 bg-white/[0.04] border border-white/[0.08] rounded-xl text-sm text-[var(--text-primary)] placeholder:text-white/20 focus:outline-hidden focus:border-ocean-500/30"
          />
        </div>
        <select
          value={selectedPA || ""}
          onChange={(e) => {
            const pa = e.target.value ? Number(e.target.value) : null;
            if (pa) loadPA(pa);
            else { setSelectedPA(null); setPaData([]); }
          }}
          className="bg-white/[0.04] border border-white/[0.08] rounded-xl px-3 py-2.5 text-sm text-[var(--text-primary)] focus:outline-hidden focus:border-ocean-500/30"
        >
          <option value="">All Production Areas</option>
          {Array.from({ length: 13 }, (_, i) => i + 1).map(pa => (
            <option key={pa} value={pa}>PA-{pa} {PA_NAMES[pa] || ""}</option>
          ))}
        </select>
      </div>

      {/* Leaderboard Table */}
      <GlassCard delay={0.15}>
        <DataTable
          title={selectedPA ? `PA-${selectedPA} Rankings` : t("benchmark.industry_avg")}
          data={(selectedPA ? paData : filtered).map((co: any, i: number) => {
            const liceB = co.benchmarks?.find((b: any) => b.metric === "Lice Performance");
            return { ...co, _rank: i + 1, _lice_value: liceB?.your_value ?? null, _pa_count: co.production_areas?.length || 0 };
          })}
          searchKeys={["company_name", "ticker"]}
          exportFilename="benchmark_leaderboard"
          compact
          columns={[
            {
              key: "_rank", label: "#", sortable: false, width: "40px",
              render: (_val: any, _row: any, idx: number) => (
                <span className="text-[var(--text-secondary)]">{idx + 1}</span>
              ),
            },
            {
              key: "company_name", label: t("benchmark.metric"), sortable: true,
              render: (val: any, row: any) => (
                <span className="cursor-pointer" onClick={() => loadCompany(row.company_name)}>
                  <span className="font-semibold text-[var(--text-primary)]">{val}</span>
                  {row.ticker && <span className="text-[9px] text-ocean-400 ml-1.5 font-mono">{row.ticker}</span>}
                </span>
              ),
            },
            {
              key: "overall_percentile", label: t("benchmark.percentile"), sortable: true, align: "center" as const,
              render: (val: any) => (
                <div className="flex items-center justify-center gap-2">
                  <div className="w-16 h-1.5 bg-white/[0.06] rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${
                        val >= 80 ? "bg-emerald-500" : val >= 60 ? "bg-ocean-500" : val >= 40 ? "bg-amber-500" : "bg-rose-500"
                      }`}
                      style={{ width: `${val}%` }}
                    />
                  </div>
                  <span className="text-xs font-mono">{val != null ? formatNumber(val, locale) : "\u2014"}</span>
                </div>
              ),
            },
            {
              key: "overall_verdict", label: "Verdict", sortable: true, align: "center" as const,
              render: (val: any) => {
                const style = VERDICT_STYLE[val] || VERDICT_STYLE.Average;
                return (
                  <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-md border ${style.bg} ${style.text}`}>
                    {val}
                  </span>
                );
              },
            },
            {
              key: "_lice_value", label: "Lice", sortable: true, align: "center" as const,
              render: (val: any) => (
                <span className={`text-xs font-mono ${
                  (val || 0) < 0.1 ? "text-emerald-400" :
                  (val || 0) < 0.3 ? "text-ocean-400" :
                  (val || 0) < 0.5 ? "text-amber-400" : "text-rose-400"
                }`}>
                  {val != null ? formatNumber(val, locale, 3) : "\u2014"}
                </span>
              ),
            },
            {
              key: "_pa_count", label: "PAs", sortable: true, align: "center" as const,
            },
            {
              key: "company_name", label: "", sortable: false, width: "32px",
              render: () => <ChevronRight className="w-3 h-3 text-[var(--text-secondary)]" />,
            },
          ] as Column[]}
        />
      </GlassCard>

      {/* Company Detail Panel */}
      {selected && (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
          <GlassCard delay={0} accent="ocean">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-lg font-bold text-[var(--text-primary)]">{selected.company_name}</h3>
                <p className="text-[11px] text-[var(--text-secondary)]">
                  {selected.ticker && <span className="text-ocean-400 font-mono mr-2">{selected.ticker}</span>}
                  {selected.n_localities} sites &middot; PA {selected.production_areas?.join(", ")}
                </p>
              </div>
              <div className="text-right">
                <span className={`text-2xl font-bold ${
                  selected.overall_percentile >= 80 ? "text-emerald-400" :
                  selected.overall_percentile >= 60 ? "text-ocean-400" :
                  selected.overall_percentile >= 40 ? "text-amber-400" : "text-rose-400"
                }`}>
                  {selected.overall_percentile != null ? formatNumber(selected.overall_percentile, locale) : "\u2014"}
                </span>
                <span className="text-[10px] text-[var(--text-secondary)] block">percentile</span>
              </div>
            </div>

            {/* Metric Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
              {(selected.benchmarks || []).map((b: any) => {
                const style = VERDICT_STYLE[b.verdict] || VERDICT_STYLE.Average;
                return (
                  <div key={b.metric} className={`p-3 rounded-xl border ${style.bg}`}>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-[11px] font-semibold text-[var(--text-primary)]">{b.metric}</span>
                      <span className={`text-[10px] font-bold ${style.text}`}>{b.verdict}</span>
                    </div>
                    <p className="text-[12px] text-[var(--text-primary)] font-medium mb-2">
                      {b.narrative}
                    </p>
                    <div className="flex items-center gap-2 mb-1">
                      <div className="flex-1 h-2 bg-white/[0.06] rounded-full overflow-hidden relative">
                        {/* Peer range */}
                        <div className="absolute h-full bg-white/[0.08] rounded-full"
                          style={{ left: "5%", width: "90%" }} />
                        {/* Your position */}
                        <div
                          className={`absolute w-2 h-2 rounded-full top-0 ${
                            b.percentile >= 60 ? "bg-emerald-400" : b.percentile >= 40 ? "bg-amber-400" : "bg-rose-400"
                          }`}
                          style={{ left: `${b.percentile}%`, transform: "translateX(-50%)" }}
                        />
                      </div>
                      <span className="text-[10px] font-mono text-[var(--text-secondary)] w-10 text-right">
                        P{formatNumber(b.percentile, locale)}
                      </span>
                    </div>
                    <div className="flex justify-between text-[9px] text-[var(--text-secondary)]">
                      <span>You: {b.your_value}</span>
                      <span>Avg: {b.peer_avg}</span>
                      <span>Median: {b.peer_median}</span>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* PA-Level Benchmarks */}
            {selected.pa_benchmarks?.length > 0 && (
              <div>
                <h4 className="text-[11px] font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <MapPin className="w-3.5 h-3.5" /> Production Area Comparison
                </h4>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                  {selected.pa_benchmarks.map((pa: any) => (
                    <div key={pa.pa} className="p-2.5 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[11px] font-semibold">PA-{pa.pa}</span>
                        <span className={`text-[9px] font-bold ${
                          pa.percentile >= 70 ? "text-emerald-400" : pa.percentile >= 40 ? "text-amber-400" : "text-rose-400"
                        }`}>
                          P{formatNumber(pa.percentile, locale)}
                        </span>
                      </div>
                      <p className="text-[10px] text-[var(--text-primary)]">{pa.narrative}</p>
                      <div className="flex justify-between mt-1 text-[9px] text-[var(--text-secondary)]">
                        <span>You: {pa.your_lice}</span>
                        <span>PA avg: {pa.pa_avg}</span>
                        <span>{pa.n_peers} peers</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </GlassCard>
        </motion.div>
      )}

      <p className="text-[9px] text-[var(--text-secondary)] text-center opacity-50">
        Benchmarks computed from BarentsWatch lice data (NLOD 2.0) for {summary?.n_companies || "100+"} Norwegian salmon producers.
        All comparisons are anonymous. Updated hourly.
      </p>
    </div>
  );
}
