"use client";
import { useEffect, useState, useCallback } from "react";
import { useTranslation } from "@/lib/i18n";
import { motion } from "framer-motion";
import {
  Shield, Activity, Database, Clock, Server, AlertTriangle,
  CheckCircle2, XCircle, RefreshCw, Cpu, HardDrive, Syringe,
  BarChart3, Droplets, DollarSign, Cloud, Leaf,
  Download, FileJson, FileSpreadsheet, Loader2,
  ScrollText, ChevronLeft, ChevronRight, Filter,
} from "lucide-react";
import GlassCard from "@/components/GlassCard";
import KPICard from "@/components/KPICard";
import { api } from "@/lib/api";
import DataQualityBadge from "@/components/DataQualityBadge";
import ErrorBoundary from "@/components/ErrorBoundary";

/* eslint-disable @typescript-eslint/no-explicit-any */

/** Traffic-light color for data freshness */
function freshnessColor(status: string): string {
  switch (status) {
    case "fresh": return "text-emerald-400";
    case "recent": return "text-emerald-300";
    case "aging": return "text-amber-400";
    case "stale": return "text-rose-400";
    default: return "text-[var(--text-secondary)]";
  }
}

function freshnessIcon(status: string) {
  switch (status) {
    case "fresh":
    case "recent":
      return <CheckCircle2 className="w-4 h-4 text-emerald-400" />;
    case "aging":
      return <AlertTriangle className="w-4 h-4 text-amber-400" />;
    case "stale":
      return <XCircle className="w-4 h-4 text-rose-400" />;
    default:
      return <AlertTriangle className="w-4 h-4 text-[var(--text-secondary)]" />;
  }
}

function freshnessLabel(status: string): string {
  switch (status) {
    case "fresh": return "Fresh (<1h)";
    case "recent": return "Recent (<6h)";
    case "aging": return "Aging (<24h)";
    case "stale": return "Stale (>24h)";
    case "no_cache": return "Not cached";
    default: return "Unknown";
  }
}

const SOURCE_META: Record<string, { label: string; icon: any }> = {
  lice_data: { label: "Lice Data (BarentsWatch)", icon: Droplets },
  price_data: { label: "Price Data (SSB)", icon: DollarSign },
  weather: { label: "Weather (MET.no)", icon: Cloud },
  bloom_data: { label: "Bloom Data (CMEMS)", icon: Leaf },
};

/** Dataset format/date state per export row */
interface ExportRowState {
  format: "csv" | "json";
  fromDate: string;
  toDate: string;
}

export default function AdminPage() {
  const { t } = useTranslation();
  const [status, setStatus] = useState<any>(null);
  const [quality, setQuality] = useState<any>(null);
  const [exportSummary, setExportSummary] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [exportStates, setExportStates] = useState<Record<string, ExportRowState>>({});
  const [exporting, setExporting] = useState<Record<string, boolean>>({});

  // Audit log state
  const [auditLog, setAuditLog] = useState<any>(null);
  const [auditFilter, setAuditFilter] = useState("");
  const [auditOffset, setAuditOffset] = useState(0);
  const AUDIT_LIMIT = 20;

  const fetchAuditLog = useCallback(async (filter?: string, offset?: number) => {
    try {
      const params: any = { limit: AUDIT_LIMIT, offset: offset ?? auditOffset };
      if (filter) params.action = filter;
      const data = await api.adminAuditLog(params);
      setAuditLog(data);
    } catch {
      // silently handle
    }
  }, [auditOffset]);

  const fetchData = useCallback(async () => {
    try {
      const [s, q, e] = await Promise.allSettled([
        api.adminStatus(),
        api.adminDataQuality(),
        api.adminExportSummary(),
      ]);
      if (s.status === "fulfilled") setStatus(s.value);
      if (q.status === "fulfilled") setQuality(q.value);
      if (e.status === "fulfilled") {
        setExportSummary(e.value);
        // Initialize per-dataset export state
        const datasets = e.value?.datasets || {};
        const initial: Record<string, ExportRowState> = {};
        for (const key of Object.keys(datasets)) {
          initial[key] = { format: "csv", fromDate: "", toDate: "" };
        }
        setExportStates((prev) => {
          // Preserve existing state if already set (e.g. user edits)
          const merged = { ...initial };
          for (const k of Object.keys(prev)) {
            if (merged[k]) merged[k] = prev[k];
          }
          return merged;
        });
      }
      setLastRefresh(new Date());
    } catch {
      // Silently handle
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    fetchAuditLog();
    const interval = setInterval(() => { fetchData(); fetchAuditLog(auditFilter || undefined, auditOffset); }, 60_000);
    return () => clearInterval(interval);
  }, [fetchData, fetchAuditLog, auditFilter, auditOffset]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-ocean-500" />
      </div>
    );
  }

  const treatmentByMethod = quality?.treatment_outcomes?.by_method || {};
  const treatmentByMonth = quality?.treatment_outcomes?.by_month || [];
  const staleWarnings = quality?.stale_warnings || [];
  const sources = quality?.sources || {};

  return (
    <ErrorBoundary fallbackTitle="Admin Dashboard error">
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-ocean-500/10 flex items-center justify-center">
              <Shield className="w-5 h-5 text-ocean-500" />
            </div>
            {t("admin.title")}
          </h1>
          <div className="flex items-center gap-2 mt-1">
            <p className="text-sm text-[var(--text-secondary)]">
              Platform health, data quality monitoring, and system status
            </p>
            <DataQualityBadge source="Platform Health" quality="live" />
          </div>
        </div>
        <div className="flex items-center gap-3">
          {lastRefresh && (
            <span className="text-xs text-[var(--text-secondary)]">
              Updated {lastRefresh.toLocaleTimeString()}
            </span>
          )}
          <button
            onClick={() => { setLoading(true); fetchData(); }}
            className="p-2 rounded-lg bg-fjord-midwater/50 border border-white/[0.08] text-[var(--text-secondary)] hover:text-ocean-400 transition-colors"
            aria-label="Refresh data"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
          <span className="text-[10px] uppercase tracking-wider text-[var(--text-secondary)] bg-fjord-midwater/30 px-2 py-1 rounded">
            Auto-refresh 60s
          </span>
        </div>
      </div>

      {/* Platform Health KPIs */}
      <section>
        <h2 className="text-sm font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-4 flex items-center gap-2">
          <Activity className="w-4 h-4" />
          {t("admin.platform_health")}
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          <KPICard
            label="Status"
            value={status?.status === "healthy" ? "Healthy" : "Degraded"}
            deltaType={status?.status === "healthy" ? "positive" : "negative"}
            icon={Server}
            delay={0}
          />
          <KPICard
            label="Uptime"
            value={status?.uptime_human || "--"}
            icon={Clock}
            delay={0.05}
          />
          <KPICard
            label="Routes"
            value={status?.route_count || 0}
            icon={Activity}
            delay={0.1}
          />
          <KPICard
            label="Engines"
            value={status?.engine_count || 0}
            icon={Cpu}
            delay={0.15}
          />
          <KPICard
            label="DB Tables"
            value={status?.db_table_count || 0}
            icon={Database}
            delay={0.2}
          />
          <KPICard
            label="Cache Hit Rate"
            value={`${status?.cache?.hit_rate ?? 0}%`}
            delta={`${status?.cache?.entries ?? 0} entries`}
            icon={HardDrive}
            delay={0.25}
          />
        </div>
      </section>

      {/* Process & Cache Details */}
      {status?.process && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <GlassCard accent="ocean" delay={0.3}>
            <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
              <Cpu className="w-4 h-4 text-ocean-500" />
              Process Info
            </h3>
            <div className="space-y-2 text-sm">
              {status.process.memory_rss_mb && (
                <div className="flex justify-between">
                  <span className="text-[var(--text-secondary)]">Memory (RSS)</span>
                  <span className="text-[var(--text-primary)] font-data">{status.process.memory_rss_mb} MB</span>
                </div>
              )}
              {status.process.cpu_percent !== undefined && (
                <div className="flex justify-between">
                  <span className="text-[var(--text-secondary)]">CPU</span>
                  <span className="text-[var(--text-primary)] font-data">{status.process.cpu_percent}%</span>
                </div>
              )}
              {status.process.threads && (
                <div className="flex justify-between">
                  <span className="text-[var(--text-secondary)]">Threads</span>
                  <span className="text-[var(--text-primary)] font-data">{status.process.threads}</span>
                </div>
              )}
              {status.process.note && (
                <p className="text-xs text-[var(--text-secondary)] italic">{status.process.note}</p>
              )}
            </div>
          </GlassCard>

          <GlassCard accent="ocean" delay={0.35}>
            <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
              <HardDrive className="w-4 h-4 text-ocean-500" />
              {t("admin.cache_stats")}
            </h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-[var(--text-secondary)]">Entries</span>
                <span className="text-[var(--text-primary)] font-data">{status?.cache?.entries ?? 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--text-secondary)]">Hits</span>
                <span className="text-emerald-400 font-data">{status?.cache?.hits ?? 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--text-secondary)]">Misses</span>
                <span className="text-amber-400 font-data">{status?.cache?.misses ?? 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--text-secondary)]">Hit Rate</span>
                <span className="text-[var(--text-primary)] font-data font-bold">{status?.cache?.hit_rate ?? 0}%</span>
              </div>
            </div>
          </GlassCard>
        </div>
      )}

      {/* Data Quality Section */}
      <section>
        <h2 className="text-sm font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-4 flex items-center gap-2">
          <Database className="w-4 h-4" />
          {t("admin.data_quality")}
        </h2>
        <GlassCard accent="emerald" delay={0.4}>
          <div className="space-y-3">
            {Object.entries(sources).map(([key, src]: [string, any]) => {
              const meta = SOURCE_META[key] || { label: key, icon: Database };
              const Icon = meta.icon;
              return (
                <div key={key} className="flex items-center justify-between py-2 border-b border-white/[0.04] last:border-0">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-fjord-midwater/50 flex items-center justify-center">
                      <Icon className="w-4 h-4 text-[var(--text-secondary)]" />
                    </div>
                    <div>
                      <span className="text-sm text-[var(--text-primary)]">{meta.label}</span>
                      {src.last_update && src.last_update !== "cached" && (
                        <p className="text-[10px] text-[var(--text-secondary)]">
                          Last: {new Date(src.last_update).toLocaleString()}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {src.age_hours !== null && src.age_hours !== undefined && (
                      <span className="text-xs text-[var(--text-secondary)] font-data">
                        {src.age_hours < 1 ? "<1h" : `${src.age_hours}h`} ago
                      </span>
                    )}
                    <div className="flex items-center gap-1.5">
                      {freshnessIcon(src.status)}
                      <span className={`text-xs font-medium ${freshnessColor(src.status)}`}>
                        {freshnessLabel(src.status)}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
            {Object.keys(sources).length === 0 && (
              <p className="text-sm text-[var(--text-secondary)] text-center py-4">
                No data source information available
              </p>
            )}
          </div>
        </GlassCard>
      </section>

      {/* Stale Data Alerts */}
      {staleWarnings.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-rose-400 uppercase tracking-wider mb-4 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" />
            Active Alerts ({staleWarnings.length})
          </h2>
          <GlassCard accent="rose" delay={0.45}>
            <div className="space-y-2">
              {staleWarnings.map((w: any, i: number) => (
                <div key={i} className="flex items-center gap-3 py-2 border-b border-white/[0.04] last:border-0">
                  <XCircle className="w-4 h-4 text-rose-400 flex-shrink-0" />
                  <div>
                    <span className="text-sm text-[var(--text-primary)] font-medium">{w.source}</span>
                    <p className="text-xs text-[var(--text-secondary)]">{w.issue}</p>
                  </div>
                </div>
              ))}
            </div>
          </GlassCard>
        </section>
      )}

      {/* Treatment Outcomes */}
      <section>
        <h2 className="text-sm font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-4 flex items-center gap-2">
          <Syringe className="w-4 h-4" />
          Treatment Outcomes
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Summary + By Method */}
          <GlassCard accent="violet" delay={0.5}>
            <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3">
              Submissions by Method
            </h3>
            <div className="mb-4">
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-bold text-[var(--text-primary)] font-data">
                  {quality?.treatment_outcomes?.total ?? status?.treatment_outcomes?.total_count ?? 0}
                </span>
                <span className="text-sm text-[var(--text-secondary)]">total outcomes</span>
              </div>
              {status?.treatment_outcomes?.last_submission && (
                <p className="text-xs text-[var(--text-secondary)] mt-1">
                  Last submission: {new Date(status.treatment_outcomes.last_submission).toLocaleString()}
                </p>
              )}
            </div>
            {Object.keys(treatmentByMethod).length > 0 ? (
              <div className="space-y-2">
                {Object.entries(treatmentByMethod)
                  .sort(([, a]: any, [, b]: any) => b - a)
                  .map(([method, count]: [string, any]) => {
                    const total = quality?.treatment_outcomes?.total || 1;
                    const pct = Math.round((count / total) * 100);
                    const colors: Record<string, string> = {
                      mechanical: "bg-ocean-500",
                      freshwater: "bg-emerald-500",
                      medicinal: "bg-amber-500",
                      thermal: "bg-rose-500",
                      biological: "bg-violet-500",
                    };
                    return (
                      <div key={method}>
                        <div className="flex justify-between text-xs mb-1">
                          <span className="text-[var(--text-primary)] capitalize">{method}</span>
                          <span className="text-[var(--text-secondary)] font-data">{count} ({pct}%)</span>
                        </div>
                        <div className="h-2 bg-fjord-midwater/50 rounded-full overflow-hidden">
                          <motion.div
                            initial={{ width: 0 }}
                            animate={{ width: `${pct}%` }}
                            transition={{ duration: 0.6, delay: 0.5 }}
                            className={`h-full rounded-full ${colors[method] || "bg-ocean-500"}`}
                          />
                        </div>
                      </div>
                    );
                  })}
              </div>
            ) : (
              <p className="text-sm text-[var(--text-secondary)] text-center py-4">
                No treatment outcomes recorded yet
              </p>
            )}
          </GlassCard>

          {/* Monthly Trend */}
          <GlassCard accent="salmon" delay={0.55}>
            <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-salmon" />
              Monthly Trend (12 months)
            </h3>
            {treatmentByMonth.length > 0 ? (
              <div className="space-y-1.5">
                {treatmentByMonth.map((m: any) => {
                  const maxCount = Math.max(...treatmentByMonth.map((x: any) => x.count), 1);
                  const pct = Math.round((m.count / maxCount) * 100);
                  return (
                    <div key={m.month} className="flex items-center gap-2">
                      <span className="text-[10px] text-[var(--text-secondary)] font-data w-14 text-right">
                        {m.month}
                      </span>
                      <div className="flex-1 h-4 bg-fjord-midwater/30 rounded overflow-hidden">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${pct}%` }}
                          transition={{ duration: 0.5, delay: 0.6 }}
                          className="h-full bg-gradient-to-r from-salmon/80 to-salmon rounded"
                        />
                      </div>
                      <span className="text-xs text-[var(--text-primary)] font-data w-8 text-right">
                        {m.count}
                      </span>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <BarChart3 className="w-8 h-8 text-[var(--text-secondary)] mb-2 opacity-30" />
                <p className="text-sm text-[var(--text-secondary)]">
                  No monthly data available yet
                </p>
                <p className="text-xs text-[var(--text-secondary)] mt-1">
                  Treatment outcomes will appear here once farmers report data
                </p>
              </div>
            )}
          </GlassCard>
        </div>
      </section>

      {/* Data Export Section */}
      <section>
        <h2 className="text-sm font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-4 flex items-center gap-2">
          <Download className="w-4 h-4" />
          {t("admin.export_data")}
        </h2>
        <GlassCard accent="ocean" delay={0.6}>
          {exportSummary?.datasets && Object.keys(exportSummary.datasets).length > 0 ? (
            <div className="space-y-4">
              {/* Header row */}
              <div className="hidden md:grid md:grid-cols-[1fr_100px_140px_140px_90px_80px] gap-3 text-[10px] uppercase tracking-wider text-[var(--text-secondary)] pb-2 border-b border-white/[0.06]">
                <span>Dataset</span>
                <span>Rows</span>
                <span>From</span>
                <span>To</span>
                <span>Format</span>
                <span></span>
              </div>

              {Object.entries(exportSummary.datasets).map(([key, ds]: [string, any]) => {
                const st = exportStates[key] || { format: "csv", fromDate: "", toDate: "" };
                const isExporting = exporting[key] || false;

                return (
                  <div key={key} className="grid grid-cols-1 md:grid-cols-[1fr_100px_140px_140px_90px_80px] gap-3 items-center py-2 border-b border-white/[0.04] last:border-0">
                    {/* Dataset name + description */}
                    <div>
                      <span className="text-sm text-[var(--text-primary)] font-medium">{ds.label}</span>
                      <p className="text-[10px] text-[var(--text-secondary)] mt-0.5">{ds.description}</p>
                    </div>

                    {/* Row count */}
                    <div className="font-data text-sm text-[var(--text-primary)]">
                      {ds.row_count.toLocaleString()}
                    </div>

                    {/* From date */}
                    <input
                      type="date"
                      value={st.fromDate}
                      onChange={(e) =>
                        setExportStates((prev) => ({
                          ...prev,
                          [key]: { ...prev[key], fromDate: e.target.value },
                        }))
                      }
                      className="bg-fjord-midwater/50 border border-white/[0.08] rounded px-2 py-1 text-xs text-[var(--text-primary)] focus:outline-none focus:border-ocean-500"
                      placeholder="From"
                    />

                    {/* To date */}
                    <input
                      type="date"
                      value={st.toDate}
                      onChange={(e) =>
                        setExportStates((prev) => ({
                          ...prev,
                          [key]: { ...prev[key], toDate: e.target.value },
                        }))
                      }
                      className="bg-fjord-midwater/50 border border-white/[0.08] rounded px-2 py-1 text-xs text-[var(--text-primary)] focus:outline-none focus:border-ocean-500"
                      placeholder="To"
                    />

                    {/* Format toggle */}
                    <div className="flex gap-1">
                      <button
                        onClick={() =>
                          setExportStates((prev) => ({
                            ...prev,
                            [key]: { ...prev[key], format: "csv" },
                          }))
                        }
                        className={`flex items-center gap-1 px-2 py-1 rounded text-[10px] font-medium transition-colors ${
                          st.format === "csv"
                            ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                            : "bg-fjord-midwater/30 text-[var(--text-secondary)] border border-white/[0.06] hover:text-[var(--text-primary)]"
                        }`}
                        aria-label="Export as CSV"
                      >
                        <FileSpreadsheet className="w-3 h-3" />
                        CSV
                      </button>
                      <button
                        onClick={() =>
                          setExportStates((prev) => ({
                            ...prev,
                            [key]: { ...prev[key], format: "json" },
                          }))
                        }
                        className={`flex items-center gap-1 px-2 py-1 rounded text-[10px] font-medium transition-colors ${
                          st.format === "json"
                            ? "bg-ocean-500/20 text-ocean-400 border border-ocean-500/30"
                            : "bg-fjord-midwater/30 text-[var(--text-secondary)] border border-white/[0.06] hover:text-[var(--text-primary)]"
                        }`}
                        aria-label="Export as JSON"
                      >
                        <FileJson className="w-3 h-3" />
                        JSON
                      </button>
                    </div>

                    {/* Export button */}
                    <button
                      disabled={ds.row_count === 0 || isExporting}
                      onClick={() => {
                        setExporting((prev) => ({ ...prev, [key]: true }));
                        const url = api.adminExportDataset(key, st.format, st.fromDate || undefined, st.toDate || undefined);
                        // Trigger browser download
                        const a = document.createElement("a");
                        a.href = url;
                        a.download = "";
                        document.body.appendChild(a);
                        a.click();
                        document.body.removeChild(a);
                        // Clear exporting after brief delay
                        setTimeout(() => setExporting((prev) => ({ ...prev, [key]: false })), 2000);
                      }}
                      className="flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg bg-ocean-500/10 border border-ocean-500/20 text-ocean-400 text-xs font-medium hover:bg-ocean-500/20 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                      aria-label={`Export ${ds.label}`}
                    >
                      {isExporting ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Download className="w-3.5 h-3.5" />
                      )}
                      Export
                    </button>
                  </div>
                );
              })}

              {/* Export All */}
              <div className="pt-3 border-t border-white/[0.06] flex items-center justify-between">
                <div className="text-xs text-[var(--text-secondary)]">
                  {Object.values(exportSummary.datasets).reduce(
                    (sum: number, ds: any) => sum + (ds.row_count || 0),
                    0
                  ).toLocaleString()}{" "}
                  total rows across {Object.keys(exportSummary.datasets).length} datasets
                </div>
                <button
                  onClick={() => {
                    // Sequential downloads for all datasets with rows
                    const datasets = Object.entries(exportSummary.datasets).filter(
                      ([, ds]: [string, any]) => ds.row_count > 0
                    );
                    datasets.forEach(([key]: [string, any], i: number) => {
                      const st = exportStates[key] || { format: "csv", fromDate: "", toDate: "" };
                      setTimeout(() => {
                        const url = api.adminExportDataset(key, st.format, st.fromDate || undefined, st.toDate || undefined);
                        const a = document.createElement("a");
                        a.href = url;
                        a.download = "";
                        document.body.appendChild(a);
                        a.click();
                        document.body.removeChild(a);
                      }, i * 500); // stagger downloads 500ms apart
                    });
                  }}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-ocean-500/20 border border-ocean-500/30 text-ocean-400 text-sm font-medium hover:bg-ocean-500/30 transition-colors"
                  aria-label="Export all datasets"
                >
                  <Download className="w-4 h-4" />
                  Export All Datasets
                </button>
              </div>
            </div>
          ) : (
            <p className="text-sm text-[var(--text-secondary)] text-center py-4">
              No export data available
            </p>
          )}
        </GlassCard>
      </section>

      {/* Audit Log Section */}
      <section>
        <h2 className="text-sm font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-4 flex items-center gap-2">
          <ScrollText className="w-4 h-4" />
          {t("admin.audit_log")}
        </h2>
        <GlassCard accent="ocean" delay={0.65}>
          {/* Filter bar */}
          <div className="flex items-center gap-3 mb-4 flex-wrap">
            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4 text-[var(--text-secondary)]" />
              <select
                value={auditFilter}
                onChange={(e) => {
                  setAuditFilter(e.target.value);
                  setAuditOffset(0);
                  fetchAuditLog(e.target.value || undefined, 0);
                }}
                className="bg-fjord-midwater/50 border border-white/[0.08] rounded px-2 py-1 text-xs text-[var(--text-primary)] focus:outline-none focus:border-ocean-500"
              >
                <option value="">All Actions</option>
                <option value="login">Login</option>
                <option value="login_failed">Login Failed</option>
                <option value="register">Register</option>
                <option value="create_webhook">Create Webhook</option>
                <option value="delete_webhook">Delete Webhook</option>
                <option value="generate_api_key">Generate API Key</option>
                <option value="revoke_api_key">Revoke API Key</option>
                <option value="log_treatment">Log Treatment</option>
                <option value="create_alert_rule">Create Alert Rule</option>
                <option value="delete_alert_rule">Delete Alert Rule</option>
                <option value="export">Data Export</option>
              </select>
            </div>
            <span className="text-[10px] text-[var(--text-secondary)]">
              {auditLog?.total ?? 0} total entries
            </span>
          </div>

          {/* Entries list */}
          {auditLog?.entries && auditLog.entries.length > 0 ? (
            <div className="space-y-1">
              {auditLog.entries.map((entry: any) => {
                const actionColors: Record<string, string> = {
                  login: "text-emerald-400",
                  login_failed: "text-rose-400",
                  register: "text-ocean-400",
                  create_webhook: "text-violet-400",
                  delete_webhook: "text-rose-400",
                  generate_api_key: "text-amber-400",
                  revoke_api_key: "text-rose-400",
                  log_treatment: "text-emerald-400",
                  create_alert_rule: "text-violet-400",
                  delete_alert_rule: "text-rose-400",
                  export: "text-ocean-400",
                };
                return (
                  <div
                    key={entry.id}
                    className="flex items-center gap-3 py-2 px-2 rounded hover:bg-white/[0.02] border-b border-white/[0.04] last:border-0"
                  >
                    {/* Timestamp */}
                    <span className="text-[10px] text-[var(--text-secondary)] font-data w-36 flex-shrink-0">
                      {entry.timestamp ? new Date(entry.timestamp).toLocaleString() : "--"}
                    </span>

                    {/* Action badge */}
                    <span
                      className={`text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded bg-fjord-midwater/50 flex-shrink-0 ${actionColors[entry.action] || "text-[var(--text-secondary)]"}`}
                    >
                      {entry.action?.replace(/_/g, " ")}
                    </span>

                    {/* User */}
                    <span className="text-xs text-[var(--text-secondary)] w-16 flex-shrink-0 font-data">
                      {entry.user_id ? `#${entry.user_id}` : "anon"}
                    </span>

                    {/* Resource */}
                    <span className="text-xs text-[var(--text-primary)] truncate flex-1">
                      {entry.resource || ""}
                    </span>

                    {/* IP */}
                    <span className="text-[10px] text-[var(--text-secondary)] font-data w-28 flex-shrink-0 text-right">
                      {entry.ip_address || ""}
                    </span>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <ScrollText className="w-8 h-8 text-[var(--text-secondary)] mb-2 opacity-30" />
              <p className="text-sm text-[var(--text-secondary)]">
                No audit log entries yet
              </p>
              <p className="text-xs text-[var(--text-secondary)] mt-1">
                Actions like login, exports, and config changes will appear here
              </p>
            </div>
          )}

          {/* Pagination */}
          {auditLog && auditLog.total > AUDIT_LIMIT && (
            <div className="flex items-center justify-between mt-4 pt-3 border-t border-white/[0.06]">
              <span className="text-[10px] text-[var(--text-secondary)]">
                Showing {auditOffset + 1}&ndash;{Math.min(auditOffset + AUDIT_LIMIT, auditLog.total)} of {auditLog.total}
              </span>
              <div className="flex items-center gap-2">
                <button
                  disabled={auditOffset === 0}
                  onClick={() => {
                    const newOffset = Math.max(0, auditOffset - AUDIT_LIMIT);
                    setAuditOffset(newOffset);
                    fetchAuditLog(auditFilter || undefined, newOffset);
                  }}
                  className="p-1.5 rounded bg-fjord-midwater/50 border border-white/[0.08] text-[var(--text-secondary)] hover:text-ocean-400 disabled:opacity-30 transition-colors"
                  aria-label="Previous page"
                >
                  <ChevronLeft className="w-3.5 h-3.5" />
                </button>
                <button
                  disabled={auditOffset + AUDIT_LIMIT >= auditLog.total}
                  onClick={() => {
                    const newOffset = auditOffset + AUDIT_LIMIT;
                    setAuditOffset(newOffset);
                    fetchAuditLog(auditFilter || undefined, newOffset);
                  }}
                  className="p-1.5 rounded bg-fjord-midwater/50 border border-white/[0.08] text-[var(--text-secondary)] hover:text-ocean-400 disabled:opacity-30 transition-colors"
                  aria-label="Next page"
                >
                  <ChevronRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          )}
        </GlassCard>
      </section>

      {/* Version footer */}
      <div className="text-center text-xs text-[var(--text-secondary)] pt-4 pb-8">
        OpenClaw v{status?.version || "2.1.0"} &middot; {status?.route_count || 0} routes &middot; {status?.engine_count || 0} engines &middot; {status?.db_table_count || 0} tables
      </div>
    </div>
    </ErrorBoundary>
  );
}
