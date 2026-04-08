"use client";
import { useState, useEffect, useCallback } from "react";
import { useTranslation, formatDate, formatNumber, formatCurrency } from "@/lib/i18n";
import { motion } from "framer-motion";
import {
  FileCheck, Calendar, AlertTriangle, CheckCircle2,
  Clock, Download, RefreshCw, ChevronDown,
  FileText, Activity, Shield, XCircle,
} from "lucide-react";
import KPICard from "@/components/KPICard";
import GlassCard from "@/components/GlassCard";
import ErrorBoundary from "@/components/ErrorBoundary";
import { api } from "@/lib/api";

/* ── Types ──────────────────────────────────────────────────────── */

interface Deadline {
  report_type: string;
  due_date: string;
  locality_no: number | null;
  status: string;
  description: string;
}

interface ComplianceScoreData {
  locality_no: number;
  compliance_score: number;
  grade: string;
  status: string;
  on_time_rate: number;
  data_completeness: number;
  discrepancy_count: number;
  treatment_documentation_count: number;
  weeks_with_data: number;
  expected_weeks: number;
}

interface GeneratedReport {
  report_type: string;
  locality_no: number;
  period: string;
  generated_at: string;
  data: Record<string, any>;
  warnings: string[];
  validation_errors: string[];
}

/* ── Helpers ────────────────────────────────────────────────────── */

function urgencyColor(dueDate: string): { bg: string; text: string; label: string } {
  const due = new Date(dueDate);
  const now = new Date();
  const daysUntil = Math.ceil((due.getTime() - now.getTime()) / 86_400_000);

  if (daysUntil < 0) return { bg: "bg-rose-500/20", text: "text-rose-400", label: "Overdue" };
  if (daysUntil <= 7) return { bg: "bg-amber-500/20", text: "text-amber-400", label: "Due this week" };
  return { bg: "bg-emerald-500/20", text: "text-emerald-400", label: "Upcoming" };
}

function reportTypeLabel(type: string): string {
  switch (type) {
    case "weekly_lice": return "Weekly Lice Report";
    case "monthly_treatment": return "Monthly Treatment Summary";
    case "quarterly_biomass": return "Quarterly Biomass Report";
    default: return type;
  }
}

function reportTypeIcon(type: string) {
  switch (type) {
    case "weekly_lice": return Activity;
    case "monthly_treatment": return FileText;
    case "quarterly_biomass": return Shield;
    default: return FileCheck;
  }
}

function gradeColor(grade: string): string {
  switch (grade) {
    case "A": return "text-emerald-400 bg-emerald-500/20 border-emerald-500/30";
    case "B": return "text-sky-400 bg-sky-500/20 border-sky-500/30";
    case "C": return "text-amber-400 bg-amber-500/20 border-amber-500/30";
    default: return "text-rose-400 bg-rose-500/20 border-rose-500/30";
  }
}

/* ── Main Component ─────────────────────────────────────────────── */

export default function RegulatoryReportsPage() {
  const { t, locale } = useTranslation();

  // ── State ──
  const [deadlines, setDeadlines] = useState<Deadline[]>([]);
  const [complianceScore, setComplianceScore] = useState<ComplianceScoreData | null>(null);
  const [generatedReport, setGeneratedReport] = useState<GeneratedReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);

  // Report generator form
  const [selectedLocality, setSelectedLocality] = useState(10362);
  const [reportType, setReportType] = useState<"weekly_lice" | "monthly_treatment">("weekly_lice");
  const [reportWeek, setReportWeek] = useState(() => {
    const now = new Date();
    const iso = getISOWeek(now);
    return Math.max(1, iso - 1); // default to last week
  });
  const [reportYear, setReportYear] = useState(new Date().getFullYear());
  const [reportMonth, setReportMonth] = useState(Math.max(1, new Date().getMonth())); // last month

  function getISOWeek(d: Date): number {
    const date = new Date(d.getTime());
    date.setHours(0, 0, 0, 0);
    date.setDate(date.getDate() + 3 - ((date.getDay() + 6) % 7));
    const week1 = new Date(date.getFullYear(), 0, 4);
    return 1 + Math.round(((date.getTime() - week1.getTime()) / 86400000 - 3 + ((week1.getDay() + 6) % 7)) / 7);
  }

  // ── Load data ──
  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [deadlinesRes, scoreRes] = await Promise.allSettled([
        api.complianceDeadlines(),
        api.complianceScore(selectedLocality),
      ]);
      if (deadlinesRes.status === "fulfilled") setDeadlines(deadlinesRes.value?.deadlines || []);
      if (scoreRes.status === "fulfilled") setComplianceScore(scoreRes.value);
    } finally {
      setLoading(false);
    }
  }, [selectedLocality]);

  useEffect(() => { loadData(); }, [loadData]);

  // ── Generate report ──
  const handleGenerate = async () => {
    setGenerating(true);
    setGeneratedReport(null);
    try {
      let result;
      if (reportType === "weekly_lice") {
        result = await api.weeklyLiceReport(selectedLocality, reportWeek, reportYear);
      } else {
        result = await api.monthlyTreatmentReport(selectedLocality, reportYear, reportMonth);
      }
      setGeneratedReport(result);
    } catch {
      // handled by useApiError pattern
    } finally {
      setGenerating(false);
    }
  };

  // ── Quick actions ──
  const handleQuickLice = async () => {
    setGenerating(true);
    setGeneratedReport(null);
    try {
      const now = new Date();
      const week = Math.max(1, getISOWeek(now) - 1);
      const result = await api.weeklyLiceReport(selectedLocality, week, now.getFullYear());
      setGeneratedReport(result);
      setReportType("weekly_lice");
      setReportWeek(week);
      setReportYear(now.getFullYear());
    } finally {
      setGenerating(false);
    }
  };

  const handleQuickTreatment = async () => {
    setGenerating(true);
    setGeneratedReport(null);
    try {
      const now = new Date();
      const m = now.getMonth() === 0 ? 12 : now.getMonth();
      const y = now.getMonth() === 0 ? now.getFullYear() - 1 : now.getFullYear();
      const result = await api.monthlyTreatmentReport(selectedLocality, y, m);
      setGeneratedReport(result);
      setReportType("monthly_treatment");
      setReportMonth(m);
      setReportYear(y);
    } finally {
      setGenerating(false);
    }
  };

  // ── Download as CSV ──
  const downloadCSV = () => {
    if (!generatedReport?.data) return;
    const data = generatedReport.data;
    const rows: string[][] = [];

    // Header row
    rows.push(Object.keys(data).filter(k => typeof data[k] !== "object"));

    // Data row
    rows.push(
      Object.entries(data)
        .filter(([, v]) => typeof v !== "object")
        .map(([, v]) => String(v ?? ""))
    );

    // If treatment methods exist, add method breakdown
    if (data.methods && typeof data.methods === "object") {
      rows.push([]);
      rows.push(["Method", "Count", "Avg Pre-Lice", "Avg Post-Lice", "Reduction %", "Cost NOK"]);
      for (const [method, stats] of Object.entries(data.methods as Record<string, any>)) {
        rows.push([
          method, String(stats.count), String(stats.avg_pre_lice),
          String(stats.avg_post_lice), String(stats.avg_reduction_pct), String(stats.total_cost_nok),
        ]);
      }
    }

    const bom = "\uFEFF";
    const csv = bom + rows.map(r => r.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${generatedReport.report_type}_${generatedReport.period}_loc${generatedReport.locality_no}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // KPI computations
  const overdueCount = deadlines.filter(d => {
    const due = new Date(d.due_date);
    return due < new Date();
  }).length;
  const dueThisWeek = deadlines.filter(d => {
    const due = new Date(d.due_date);
    const now = new Date();
    const daysUntil = Math.ceil((due.getTime() - now.getTime()) / 86_400_000);
    return daysUntil >= 0 && daysUntil <= 7;
  }).length;

  return (
    <ErrorBoundary>
      <div className="space-y-6">
        {/* ── Header ── */}
        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <FileCheck className="w-7 h-7 text-sky-400" />
            {t("compliance.title")}
          </h1>
          <p className="text-sm text-white/60 mt-1">
            {t("compliance.subtitle")}
          </p>
        </motion.div>

        {/* ── KPI Row ── */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <KPICard
            label={t("compliance.deadlines")}
            value={`${deadlines.length}`}
            icon={Calendar}
          />
          <KPICard
            label={t("compliance.overdue")}
            value={`${overdueCount}`}
            delta={overdueCount > 0 ? `${overdueCount} overdue` : undefined}
            deltaType={overdueCount > 0 ? "negative" : "neutral"}
            icon={AlertTriangle}
          />
          <KPICard
            label="Due This Week"
            value={`${dueThisWeek}`}
            icon={Clock}
          />
          <KPICard
            label={t("compliance.score")}
            value={complianceScore ? `${complianceScore.compliance_score}%` : "\u2014"}
            delta={complianceScore ? `Grade ${complianceScore.grade}` : undefined}
            deltaType={complianceScore?.grade === "A" ? "positive" : complianceScore?.grade === "B" ? "positive" : "negative"}
            icon={Shield}
          />
        </div>

        {/* ── Compliance Score Detail ── */}
        {complianceScore && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.1 }}>
            <GlassCard>
              <div className="flex items-center gap-3 mb-4">
                <Shield className="w-5 h-5 text-sky-400" />
                <h2 className="text-lg font-semibold text-white">{t("compliance.score")} &mdash; Locality {complianceScore.locality_no}</h2>
                <span className={`px-3 py-1 rounded-full text-sm font-bold border ${gradeColor(complianceScore.grade)}`}>
                  {complianceScore.grade}
                </span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <p className="text-xs text-white/50 uppercase">{t("compliance.on_time")}</p>
                  <p className="text-xl font-bold text-white">{formatNumber(complianceScore.on_time_rate, locale, 1)}%</p>
                  <div className="mt-1 h-2 bg-white/10 rounded-full overflow-hidden">
                    <div className="h-full bg-emerald-500 rounded-full" style={{ width: `${complianceScore.on_time_rate}%` }} />
                  </div>
                </div>
                <div>
                  <p className="text-xs text-white/50 uppercase">Data Completeness</p>
                  <p className="text-xl font-bold text-white">{formatNumber(complianceScore.data_completeness, locale, 1)}%</p>
                  <div className="mt-1 h-2 bg-white/10 rounded-full overflow-hidden">
                    <div className="h-full bg-sky-500 rounded-full" style={{ width: `${complianceScore.data_completeness}%` }} />
                  </div>
                </div>
                <div>
                  <p className="text-xs text-white/50 uppercase">Discrepancies</p>
                  <p className="text-xl font-bold text-white">{complianceScore.discrepancy_count}</p>
                  <p className="text-xs text-white/40">{complianceScore.discrepancy_count === 0 ? "No issues" : "Needs review"}</p>
                </div>
                <div>
                  <p className="text-xs text-white/50 uppercase">Weeks Reported</p>
                  <p className="text-xl font-bold text-white">{complianceScore.weeks_with_data}/{complianceScore.expected_weeks}</p>
                  <p className="text-xs text-white/40">Last 12 weeks</p>
                </div>
              </div>
            </GlassCard>
          </motion.div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* ── Compliance Calendar ── */}
          <motion.div initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.15 }}>
            <GlassCard>
              <div className="flex items-center gap-2 mb-4">
                <Calendar className="w-5 h-5 text-amber-400" />
                <h2 className="text-lg font-semibold text-white">{t("compliance.deadlines")}</h2>
              </div>
              {deadlines.length === 0 ? (
                <p className="text-white/40 text-sm py-4">{t("compliance.no_deadlines")}</p>
              ) : (
                <div className="space-y-2 max-h-[420px] overflow-y-auto pr-1">
                  {deadlines.map((d, i) => {
                    const urg = urgencyColor(d.due_date);
                    const Icon = reportTypeIcon(d.report_type);
                    return (
                      <div key={i} className={`flex items-center gap-3 p-3 rounded-lg border border-white/5 ${urg.bg}`}>
                        <Icon className={`w-4 h-4 ${urg.text} shrink-0`} />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm text-white font-medium truncate">{d.description}</p>
                          <p className="text-xs text-white/50">
                            Due: {formatDate(d.due_date, locale)}
                          </p>
                        </div>
                        <span className={`text-xs px-2 py-0.5 rounded-full ${urg.bg} ${urg.text} whitespace-nowrap`}>
                          {urg.label}
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
            </GlassCard>
          </motion.div>

          {/* ── Report Generator ── */}
          <motion.div initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.2 }}>
            <GlassCard>
              <div className="flex items-center gap-2 mb-4">
                <FileText className="w-5 h-5 text-sky-400" />
                <h2 className="text-lg font-semibold text-white">{t("compliance.generate_report")}</h2>
              </div>

              <div className="space-y-3">
                {/* Locality */}
                <div>
                  <label className="text-xs text-white/50 uppercase block mb-1">Locality No</label>
                  <input
                    type="number"
                    value={selectedLocality}
                    onChange={e => setSelectedLocality(Number(e.target.value))}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-sky-500/50"
                  />
                </div>

                {/* Report Type */}
                <div>
                  <label className="text-xs text-white/50 uppercase block mb-1">Report Type</label>
                  <select
                    value={reportType}
                    onChange={e => setReportType(e.target.value as any)}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-sky-500/50"
                  >
                    <option value="weekly_lice">{t("compliance.weekly_lice")}</option>
                    <option value="monthly_treatment">{t("compliance.monthly_treatment")}</option>
                  </select>
                </div>

                {/* Period selector */}
                {reportType === "weekly_lice" ? (
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-xs text-white/50 uppercase block mb-1">Week</label>
                      <input type="number" min={1} max={53} value={reportWeek}
                        onChange={e => setReportWeek(Number(e.target.value))}
                        className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-sky-500/50"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-white/50 uppercase block mb-1">Year</label>
                      <input type="number" min={2020} max={2030} value={reportYear}
                        onChange={e => setReportYear(Number(e.target.value))}
                        className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-sky-500/50"
                      />
                    </div>
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-xs text-white/50 uppercase block mb-1">Month</label>
                      <input type="number" min={1} max={12} value={reportMonth}
                        onChange={e => setReportMonth(Number(e.target.value))}
                        className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-sky-500/50"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-white/50 uppercase block mb-1">Year</label>
                      <input type="number" min={2020} max={2030} value={reportYear}
                        onChange={e => setReportYear(Number(e.target.value))}
                        className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-sky-500/50"
                      />
                    </div>
                  </div>
                )}

                <button
                  onClick={handleGenerate}
                  disabled={generating}
                  className="w-full py-2 px-4 bg-sky-500/20 hover:bg-sky-500/30 border border-sky-500/30 rounded-lg text-sky-400 font-medium text-sm transition-colors disabled:opacity-50"
                >
                  {generating ? (
                    <span className="flex items-center justify-center gap-2">
                      <RefreshCw className="w-4 h-4 animate-spin" /> Generating...
                    </span>
                  ) : (
                    <span className="flex items-center justify-center gap-2">
                      <FileCheck className="w-4 h-4" /> {t("compliance.generate_report")}
                    </span>
                  )}
                </button>
              </div>

              {/* Quick Actions */}
              <div className="mt-4 pt-4 border-t border-white/10">
                <p className="text-xs text-white/50 uppercase mb-2">Quick Actions</p>
                <div className="grid grid-cols-1 gap-2">
                  <button
                    onClick={handleQuickLice}
                    disabled={generating}
                    className="flex items-center gap-2 p-2 bg-white/5 hover:bg-white/10 rounded-lg text-sm text-white/80 transition-colors disabled:opacity-50"
                  >
                    <Activity className="w-4 h-4 text-emerald-400" />
                    Generate This Week&apos;s Lice Report
                  </button>
                  <button
                    onClick={handleQuickTreatment}
                    disabled={generating}
                    className="flex items-center gap-2 p-2 bg-white/5 hover:bg-white/10 rounded-lg text-sm text-white/80 transition-colors disabled:opacity-50"
                  >
                    <FileText className="w-4 h-4 text-amber-400" />
                    Generate Last Month&apos;s Treatment Summary
                  </button>
                </div>
              </div>
            </GlassCard>
          </motion.div>
        </div>

        {/* ── Generated Report ── */}
        {generatedReport && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
            <GlassCard>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                  <h2 className="text-lg font-semibold text-white">{t("compliance.report_generated")}</h2>
                  <span className="text-xs text-white/50 ml-2">
                    {reportTypeLabel(generatedReport.report_type)} &mdash; {generatedReport.period}
                  </span>
                </div>
                <button
                  onClick={downloadCSV}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/30 rounded-lg text-emerald-400 text-sm transition-colors"
                >
                  <Download className="w-4 h-4" />
                  {t("compliance.download")}
                </button>
              </div>

              {/* Warnings */}
              {generatedReport.warnings.length > 0 && (
                <div className="mb-4 space-y-1">
                  {generatedReport.warnings.map((w, i) => (
                    <div key={i} className="flex items-start gap-2 p-2 bg-amber-500/10 rounded-lg">
                      <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                      <p className="text-sm text-amber-300">{w}</p>
                    </div>
                  ))}
                </div>
              )}

              {/* Validation errors */}
              {generatedReport.validation_errors.length > 0 && (
                <div className="mb-4 space-y-1">
                  {generatedReport.validation_errors.map((e, i) => (
                    <div key={i} className="flex items-start gap-2 p-2 bg-rose-500/10 rounded-lg">
                      <XCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                      <p className="text-sm text-rose-300">{e}</p>
                    </div>
                  ))}
                </div>
              )}

              {/* Report data table */}
              <div className="bg-white/5 rounded-lg overflow-hidden">
                <table className="w-full text-sm">
                  <tbody>
                    {Object.entries(generatedReport.data)
                      .filter(([k, v]) => typeof v !== "object" && k !== "status")
                      .map(([key, value]) => (
                        <tr key={key} className="border-b border-white/5 last:border-0">
                          <td className="px-4 py-2 text-white/50 font-medium whitespace-nowrap">
                            {key.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase())}
                          </td>
                          <td className="px-4 py-2 text-white">
                            {value === true ? (
                              <CheckCircle2 className="w-4 h-4 text-emerald-400 inline" />
                            ) : value === false ? (
                              <XCircle className="w-4 h-4 text-rose-400 inline" />
                            ) : (
                              String(value ?? "\u2014")
                            )}
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>

              {/* Treatment method breakdown */}
              {generatedReport.data.methods && Object.keys(generatedReport.data.methods).length > 0 && (
                <div className="mt-4">
                  <h3 className="text-sm font-semibold text-white/70 mb-2">Treatment Methods</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                    {Object.entries(generatedReport.data.methods as Record<string, any>).map(([method, stats]) => (
                      <div key={method} className="bg-white/5 rounded-lg p-3">
                        <p className="text-sm font-medium text-white capitalize">{method}</p>
                        <div className="mt-2 space-y-1 text-xs text-white/60">
                          <p>Treatments: <span className="text-white">{stats.count}</span></p>
                          <p>Avg reduction: <span className="text-emerald-400">{stats.avg_reduction_pct}%</span></p>
                          <p>Cost: <span className="text-white">{formatCurrency(stats.total_cost_nok, locale)}</span></p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </GlassCard>
          </motion.div>
        )}
      </div>
    </ErrorBoundary>
  );
}
