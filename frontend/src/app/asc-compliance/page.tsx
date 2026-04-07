"use client";
import { useState, useEffect } from "react";
import { useTranslation } from "@/lib/i18n";
import { motion } from "framer-motion";
import {
  ShieldCheck, Clock, AlertTriangle, CheckCircle2,
  XCircle, MinusCircle, ChevronDown, ChevronRight,
  RefreshCw, Building2,
} from "lucide-react";
import KPICard from "@/components/KPICard";
import GlassCard from "@/components/GlassCard";
import ErrorBoundary from "@/components/ErrorBoundary";
import { api } from "@/lib/api";

type CheckStatus = "pass" | "partial" | "fail";

interface IndicatorCheck {
  indicator: string;
  category: string;
  title: string;
  status: CheckStatus;
  data_completeness_pct: number;
  detail: string;
}

interface FarmSummary {
  locality_no: number;
  locality_name: string;
  company: string;
  readiness_score: number;
  readiness_grade: string;
  passing: number;
  partial: number;
  failing: number;
  pre_audit_window_ok: boolean;
}

const STATUS_STYLES: Record<CheckStatus, { bg: string; text: string; icon: any }> = {
  pass: { bg: "bg-emerald-500/20", text: "text-emerald-400", icon: CheckCircle2 },
  partial: { bg: "bg-amber-500/20", text: "text-amber-400", icon: MinusCircle },
  fail: { bg: "bg-rose-500/20", text: "text-rose-400", icon: XCircle },
};

function StatusBadge({ status }: { status: CheckStatus }) {
  const { t } = useTranslation();
  const s = STATUS_STYLES[status];
  const Icon = s.icon;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${s.bg} ${s.text}`}>
      <Icon className="w-3 h-3" />
      {status === "pass" ? t("asc.pass") : status === "partial" ? t("asc.partial") : t("asc.fail")}
    </span>
  );
}

function GradeBadge({ grade, size = "sm" }: { grade: string; size?: "sm" | "lg" }) {
  const colors: Record<string, string> = {
    A: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
    B: "bg-sky-500/20 text-sky-400 border-sky-500/30",
    C: "bg-amber-500/20 text-amber-400 border-amber-500/30",
    D: "bg-orange-500/20 text-orange-400 border-orange-500/30",
    F: "bg-rose-500/20 text-rose-400 border-rose-500/30",
  };
  const cls = colors[grade] || colors.F;
  const sizeClass = size === "lg" ? "text-3xl px-4 py-2" : "text-sm px-2 py-0.5";
  return (
    <span className={`inline-flex items-center justify-center rounded-lg border font-bold ${cls} ${sizeClass}`}>
      {grade}
    </span>
  );
}

function ASCComplianceContent() {
  const { t } = useTranslation();
  const [summary, setSummary] = useState<any>(null);
  const [checklist, setChecklist] = useState<any>(null);
  const [selectedFarm, setSelectedFarm] = useState<number | null>(null);
  const [farmDetail, setFarmDetail] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set());

  const load = async () => {
    setLoading(true);
    try {
      const [s, c] = await Promise.allSettled([
        api.ascReadinessSummary(),
        api.ascChecklist(),
      ]);
      if (s.status === "fulfilled") setSummary(s.value);
      if (c.status === "fulfilled") setChecklist(c.value);
    } catch { /* empty */ }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const loadFarmDetail = async (localityNo: number) => {
    setSelectedFarm(localityNo);
    setDetailLoading(true);
    try {
      const r = await api.ascReadiness(localityNo);
      setFarmDetail(r);
      // Auto-expand all categories
      if (r?.checks) {
        const cats = new Set(r.checks.map((c: IndicatorCheck) => c.category));
        setExpandedCategories(cats as Set<string>);
      }
    } catch { /* empty */ }
    setDetailLoading(false);
  };

  const toggleCategory = (cat: string) => {
    setExpandedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat);
      else next.add(cat);
      return next;
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <RefreshCw className="w-8 h-8 animate-spin text-ocean-400" />
      </div>
    );
  }

  const daysLeft = summary?.days_until_mandatory ?? 0;
  const avgReadiness = summary?.avg_readiness ?? 0;
  const dist = summary?.readiness_distribution ?? {};

  // Group checklist indicators by category
  const checksByCategory: Record<string, IndicatorCheck[]> = {};
  if (farmDetail?.checks) {
    for (const c of farmDetail.checks) {
      if (!checksByCategory[c.category]) checksByCategory[c.category] = [];
      checksByCategory[c.category].push(c);
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <ShieldCheck className="w-7 h-7 text-emerald-400" />
            {t("asc.title")}
          </h1>
          <p className="text-sm text-white/60 mt-1">
            Audit readiness dashboard — mandatory from May 2027
          </p>
        </div>
        <button
          onClick={load}
          className="p-2 rounded-lg bg-white/5 hover:bg-white/10 transition"
          aria-label="Refresh data"
        >
          <RefreshCw className="w-4 h-4 text-white/60" />
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KPICard
          label={t("asc.readiness_score")}
          value={`${avgReadiness}%`}
          delta={avgReadiness >= 80 ? "Audit Ready" : avgReadiness >= 50 ? "Needs Work" : "Not Ready"}
          deltaType={avgReadiness >= 80 ? "positive" : avgReadiness >= 50 ? "neutral" : "negative"}
        />
        <KPICard
          label={t("asc.mandatory_date")}
          value={String(daysLeft)}
          delta={daysLeft > 365 ? "On Track" : daysLeft > 180 ? "6 Months Left" : "Urgent"}
          deltaType={daysLeft > 365 ? "positive" : daysLeft > 180 ? "neutral" : "negative"}
        />
        <KPICard
          label="Audit Ready"
          value={String(dist.audit_ready ?? 0)}
          delta={`of ${summary?.checked_farms ?? 0} farms`}
          deltaType="positive"
        />
        <KPICard
          label="Not Ready"
          value={String(dist.not_ready ?? 0)}
          delta="Action Required"
          deltaType="negative"
        />
      </div>

      {/* Countdown Banner */}
      {daysLeft <= 365 && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 flex items-center gap-3"
        >
          <Clock className="w-6 h-6 text-amber-400 flex-shrink-0" />
          <div>
            <p className="text-amber-300 font-medium">
              {daysLeft} {t("asc.days_remaining")}
            </p>
            <p className="text-amber-300/70 text-sm">
              Farms need 6 months of continuous pre-audit data. Start collecting now.
            </p>
          </div>
        </motion.div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Farm List */}
        <GlassCard className="lg:col-span-1">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Building2 className="w-5 h-5 text-ocean-400" />
            Farm Readiness
          </h2>
          <div className="space-y-2 max-h-[500px] overflow-y-auto">
            {(summary?.farms ?? []).length === 0 ? (
              <p className="text-white/40 text-sm">{t("common.no_data")}</p>
            ) : (
              (summary?.farms ?? []).map((f: FarmSummary) => (
                <button
                  key={f.locality_no}
                  onClick={() => loadFarmDetail(f.locality_no)}
                  className={`w-full text-left p-3 rounded-lg transition ${
                    selectedFarm === f.locality_no
                      ? "bg-ocean-500/20 border border-ocean-500/30"
                      : "bg-white/5 hover:bg-white/10 border border-transparent"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="min-w-0">
                      <p className="text-white text-sm font-medium truncate">
                        {f.locality_name}
                      </p>
                      <p className="text-white/40 text-xs truncate">{f.company}</p>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <span className="text-white/60 text-sm">{f.readiness_score}%</span>
                      <GradeBadge grade={f.readiness_grade} />
                    </div>
                  </div>
                  <div className="mt-2 h-1.5 rounded-full bg-white/10 overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${
                        f.readiness_score >= 80
                          ? "bg-emerald-500"
                          : f.readiness_score >= 50
                          ? "bg-amber-500"
                          : "bg-rose-500"
                      }`}
                      style={{ width: `${f.readiness_score}%` }}
                    />
                  </div>
                </button>
              ))
            )}
          </div>
        </GlassCard>

        {/* Farm Detail / Indicator Checklist */}
        <GlassCard className="lg:col-span-2">
          {!farmDetail && !detailLoading ? (
            <div className="flex flex-col items-center justify-center h-64 text-white/40">
              <ShieldCheck className="w-12 h-12 mb-3 opacity-30" />
              <p>Select a farm to view indicator checklist</p>
            </div>
          ) : detailLoading ? (
            <div className="flex items-center justify-center h-64">
              <RefreshCw className="w-6 h-6 animate-spin text-ocean-400" />
            </div>
          ) : (
            <div>
              {/* Farm header */}
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-lg font-semibold text-white">
                    {farmDetail.locality_name}
                  </h2>
                  <p className="text-sm text-white/50">{farmDetail.company}</p>
                </div>
                <div className="flex items-center gap-3">
                  <div className="text-right">
                    <p className="text-2xl font-bold text-white">{farmDetail.readiness_score}%</p>
                    <p className="text-xs text-white/40">Readiness</p>
                  </div>
                  <GradeBadge grade={farmDetail.readiness_grade} size="lg" />
                </div>
              </div>

              {/* Summary badges */}
              <div className="flex gap-3 mb-4">
                <span className="text-xs px-2 py-1 rounded bg-emerald-500/20 text-emerald-400">
                  {farmDetail.summary?.passing ?? 0} passing
                </span>
                <span className="text-xs px-2 py-1 rounded bg-amber-500/20 text-amber-400">
                  {farmDetail.summary?.partial ?? 0} partial
                </span>
                <span className="text-xs px-2 py-1 rounded bg-rose-500/20 text-rose-400">
                  {farmDetail.summary?.failing ?? 0} failing
                </span>
                <span className={`text-xs px-2 py-1 rounded ${
                  farmDetail.pre_audit_window_ok
                    ? "bg-emerald-500/20 text-emerald-400"
                    : "bg-rose-500/20 text-rose-400"
                }`}>
                  {farmDetail.pre_audit_window_ok ? "6-month window OK" : "6-month window incomplete"}
                </span>
              </div>

              {/* Indicator checks by category */}
              <div className="space-y-2">
                {Object.entries(checksByCategory).map(([category, checks]) => (
                  <div key={category} className="rounded-lg bg-white/5 overflow-hidden">
                    <button
                      onClick={() => toggleCategory(category)}
                      className="w-full flex items-center justify-between p-3 hover:bg-white/5 transition"
                    >
                      <span className="text-white font-medium text-sm">{category}</span>
                      <div className="flex items-center gap-2">
                        {checks.map((c) => (
                          <StatusBadge key={c.indicator} status={c.status} />
                        ))}
                        {expandedCategories.has(category) ? (
                          <ChevronDown className="w-4 h-4 text-white/40" />
                        ) : (
                          <ChevronRight className="w-4 h-4 text-white/40" />
                        )}
                      </div>
                    </button>
                    {expandedCategories.has(category) && (
                      <div className="border-t border-white/10">
                        {checks.map((c) => (
                          <div key={c.indicator} className="p-3 border-b border-white/5 last:border-0">
                            <div className="flex items-center justify-between mb-1">
                              <div className="flex items-center gap-2">
                                <span className="text-white/40 text-xs font-mono">{c.indicator}</span>
                                <span className="text-white text-sm">{c.title}</span>
                              </div>
                              <StatusBadge status={c.status} />
                            </div>
                            <p className="text-white/50 text-xs">{c.detail}</p>
                            <div className="mt-1.5 h-1 rounded-full bg-white/10 overflow-hidden">
                              <div
                                className={`h-full rounded-full ${
                                  c.status === "pass"
                                    ? "bg-emerald-500"
                                    : c.status === "partial"
                                    ? "bg-amber-500"
                                    : "bg-rose-500"
                                }`}
                                style={{ width: `${c.data_completeness_pct}%` }}
                              />
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {/* Data Gaps */}
              {farmDetail.data_gaps?.length > 0 && (
                <div className="mt-4 p-3 rounded-lg bg-rose-500/10 border border-rose-500/20">
                  <h3 className="text-sm font-medium text-rose-400 flex items-center gap-2 mb-2">
                    <AlertTriangle className="w-4 h-4" />
                    Data Gaps ({farmDetail.data_gaps.length})
                  </h3>
                  <ul className="space-y-1">
                    {farmDetail.data_gaps.map((g: any) => (
                      <li key={g.indicator} className="text-xs text-rose-300/70">
                        <span className="font-mono">{g.indicator}</span> {g.title}: {g.detail}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </GlassCard>
      </div>

      {/* ASC Indicator Reference */}
      {checklist && (
        <GlassCard>
          <h2 className="text-lg font-semibold text-white mb-4">
            {t("asc.checklist")}
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-white/50 text-left border-b border-white/10">
                  <th className="pb-2 pr-4">ID</th>
                  <th className="pb-2 pr-4">Category</th>
                  <th className="pb-2 pr-4">Title</th>
                  <th className="pb-2 pr-4">Description</th>
                  <th className="pb-2 text-right">Weight</th>
                </tr>
              </thead>
              <tbody>
                {(checklist.indicators ?? []).map((ind: any) => (
                  <tr key={ind.id} className="border-b border-white/5 text-white/70">
                    <td className="py-2 pr-4 font-mono text-xs">{ind.id}</td>
                    <td className="py-2 pr-4">{ind.category}</td>
                    <td className="py-2 pr-4 text-white">{ind.title}</td>
                    <td className="py-2 pr-4 text-xs">{ind.description}</td>
                    <td className="py-2 text-right">{ind.weight}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </GlassCard>
      )}
    </div>
  );
}

export default function ASCCompliancePage() {
  return (
    <ErrorBoundary>
      <ASCComplianceContent />
    </ErrorBoundary>
  );
}
