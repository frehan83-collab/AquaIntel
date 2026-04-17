"use client";
import { useEffect, useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  AlertTriangle, Droplets, Thermometer, MapPin, Bell,
  ArrowUp, ArrowDown, Minus, Shield, Download,
} from "lucide-react";
import { exportToCSV } from "@/lib/export";
import { useTranslation, formatNumber } from "@/lib/i18n";
import KPICard from "@/components/KPICard";
import GlassCard from "@/components/GlassCard";
import { OcButton } from "@/components/ui/Button";
import dynamic from "next/dynamic";
import { api } from "@/lib/api";
import ErrorBoundary from "@/components/ErrorBoundary";
import DataQualityBadge from "@/components/DataQualityBadge";

const BloomMap = dynamic(() => import("@/components/BloomMap"), {
  loading: () => <div className="h-[500px] bg-slate-800/50 rounded-xl animate-pulse flex items-center justify-center"><span className="text-slate-400">Loading map...</span></div>,
  ssr: false,
});

// Types
interface RiskAssessment {
  locality_no: number;
  locality_name: string;
  owner_company: string | null;
  latitude: number;
  longitude: number;
  risk_level: "LOW" | "ELEVATED" | "HIGH" | "CRITICAL";
  risk_score: number;
  chl_a: number;
  sst: number | null;
  chl_a_trend: number;
  chl_a_sparkline: number[];
  assessed_at: string;
  factors: string;
}

interface BloomAlert {
  id: number;
  locality_no: number;
  risk_level: string;
  channel: string;
  delivery_status: string;
  sent_at: string;
  message: string;
}

const RISK_COLORS: Record<string, string> = {
  LOW: "#10B981",
  ELEVATED: "#F59E0B",
  HIGH: "#F97316",
  CRITICAL: "#EF4444",
};

const RISK_BG: Record<string, string> = {
  LOW: "bg-emerald-500/10 border-emerald-500/15 text-emerald-400",
  ELEVATED: "bg-amber-500/10 border-amber-500/15 text-amber-400",
  HIGH: "bg-orange-500/10 border-orange-500/15 text-orange-400",
  CRITICAL: "bg-rose-500/10 border-rose-500/15 text-rose-400",
};

function RiskBadge({ level }: { level: string }) {
  return (
    <span className={`inline-flex items-center px-2.5 py-1 rounded-lg text-[11px] font-semibold border ${RISK_BG[level] || RISK_BG.LOW}`}>
      {level === "CRITICAL" && <AlertTriangle className="w-3 h-3 mr-1" />}
      {level}
    </span>
  );
}

function TrendIcon({ trend }: { trend: number }) {
  if (trend > 0.3) return <ArrowUp className="w-3.5 h-3.5 text-rose-400" />;
  if (trend < -0.3) return <ArrowDown className="w-3.5 h-3.5 text-emerald-400" />;
  return <Minus className="w-3.5 h-3.5 text-[var(--text-secondary)]" />;
}

function ChlSparkline({ data }: { data: number[] }) {
  if (!data || data.length < 2) return null;
  const max = Math.max(...data, 0.1);
  const min = Math.min(...data, 0);
  const range = max - min || 0.1;
  const w = 72;
  const h = 20;
  const points = data
    .map((v, i) => `${(i / (data.length - 1)) * w},${h - ((v - min) / range) * h}`)
    .join(" ");

  // Color based on last value vs threshold
  const last = data[data.length - 1];
  const color = last >= 5 ? "#F43F5E" : last >= 2 ? "#F59E0B" : "#10B981";

  return (
    <svg width={w} height={h} className="opacity-70">
      {/* Threshold line at chl-a = 2 (elevated) */}
      {max >= 1.5 && (
        <line
          x1={0} y1={h - ((2 - min) / range) * h}
          x2={w} y2={h - ((2 - min) / range) * h}
          stroke="#F59E0B" strokeWidth={0.5} strokeDasharray="2 2" opacity={0.3}
        />
      )}
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* End dot */}
      <circle
        cx={w}
        cy={h - ((last - min) / range) * h}
        r={2}
        fill={color}
      />
    </svg>
  );
}

export default function BloomPage() {
  const { t, locale } = useTranslation();
  const [risks, setRisks] = useState<RiskAssessment[]>([]);
  const [alerts, setAlerts] = useState<BloomAlert[]>([]);
  const [filter, setFilter] = useState<string>("ALL");
  const [sortAsc, setSortAsc] = useState(false); // false = high risk first
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.bloomRisk().catch(() => []),
      api.bloomAlerts().catch(() => []),
    ]).then(([r, a]) => {
      setRisks(r);
      setAlerts(a);
      setLoading(false);
    });
  }, []);

  // KPI metrics
  const stats = useMemo(() => {
    const critical = risks.filter((r) => r.risk_level === "CRITICAL").length;
    const high = risks.filter((r) => r.risk_level === "HIGH").length;
    const elevated = risks.filter((r) => r.risk_level === "ELEVATED").length;
    const low = risks.filter((r) => r.risk_level === "LOW").length;
    const avgChl = risks.length
      ? formatNumber(risks.reduce((s, r) => s + (r.chl_a || 0), 0) / risks.length, locale, 2)
      : "0.00";
    const avgSst = risks.length
      ? formatNumber(risks.reduce((s, r) => s + (r.sst || 0), 0) / risks.filter(r => r.sst != null).length, locale, 1)
      : "—";
    return { critical, high, elevated, low, total: risks.length, avgChl, avgSst };
  }, [risks, locale]);

  // Filtered localities
  const filteredRisks = useMemo(() => {
    if (filter === "ALL") return risks;
    return risks.filter((r) => r.risk_level === filter);
  }, [risks, filter]);

  // Sort by risk score (toggle high→low / low→high)
  const sortedRisks = useMemo(
    () => [...filteredRisks].sort((a, b) =>
      sortAsc ? a.risk_score - b.risk_score : b.risk_score - a.risk_score
    ),
    [filteredRisks, sortAsc]
  );

  return (
    <ErrorBoundary fallbackTitle="Bloom Risk error">
    <div className="space-y-6">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between"
      >
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-[var(--text-primary)]">
              Algal Bloom Early Warning
            </h1>
            <DataQualityBadge quality="live" source="CMEMS Chlorophyll-a" />
          </div>
          <p className="text-[var(--text-secondary)] text-sm mt-1">
            Satellite chlorophyll-a monitoring via Copernicus Marine Service
          </p>
        </div>
        <div className="flex items-center gap-2">
          <OcButton variant="ghost" size="sm"
            leftIcon={<Download className="w-3.5 h-3.5" />}
            onClick={() => risks.length > 0 && exportToCSV(
              risks.map(r => ({
                locality_no: r.locality_no,
                locality_name: r.locality_name,
                company: r.owner_company,
                risk_level: r.risk_level,
                risk_score: r.risk_score,
                chl_a: r.chl_a,
                sst: r.sst,
                chl_a_trend: r.chl_a_trend,
                assessed_at: r.assessed_at,
              })),
              "bloom_risk"
            )}>
            CSV
          </OcButton>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/[0.03] backdrop-blur border border-white/[0.06]">
            <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.5)]" />
            <span className="text-xs text-emerald-400 font-medium">Live monitoring</span>
          </div>
        </div>
      </motion.div>

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        <KPICard label="Localities" value={stats.total} icon={MapPin} delay={0} />
        <KPICard
          label="Critical"
          value={stats.critical}
          delta={stats.critical > 0 ? "Immediate risk" : undefined}
          deltaType="negative"
          icon={AlertTriangle}
          pulse={stats.critical > 0}
          delay={0.05}
        />
        <KPICard
          label="High"
          value={stats.high}
          delta={stats.high > 0 ? "Active bloom" : undefined}
          deltaType="negative"
          icon={Droplets}
          delay={0.1}
        />
        <KPICard label="Elevated" value={stats.elevated} icon={Shield} delay={0.15} />
        <KPICard label="Avg Chl-a" value={`${stats.avgChl} mg/m3`} icon={Thermometer} delay={0.2} />
      </div>

      {/* Risk Distribution Summary */}
      {risks.length > 0 && (
        <GlassCard delay={0.22} accent="none" className="!p-4">
          <h3 className="text-[11px] font-semibold text-[var(--text-primary)] uppercase tracking-wider mb-3">
            Risk Distribution
          </h3>
          <div className="flex items-center gap-2 h-5 rounded-full overflow-hidden bg-white/[0.03]">
            {stats.critical > 0 && (
              <div
                className="h-full bg-rose-500/70 rounded-l-full flex items-center justify-center"
                style={{ width: `${(stats.critical / stats.total) * 100}%`, minWidth: stats.critical > 0 ? 32 : 0 }}
              >
                <span className="text-[9px] font-bold text-white px-1">{stats.critical}</span>
              </div>
            )}
            {stats.high > 0 && (
              <div
                className="h-full bg-orange-500/70 flex items-center justify-center"
                style={{ width: `${(stats.high / stats.total) * 100}%`, minWidth: stats.high > 0 ? 32 : 0 }}
              >
                <span className="text-[9px] font-bold text-white px-1">{stats.high}</span>
              </div>
            )}
            {stats.elevated > 0 && (
              <div
                className="h-full bg-amber-500/70 flex items-center justify-center"
                style={{ width: `${(stats.elevated / stats.total) * 100}%`, minWidth: stats.elevated > 0 ? 32 : 0 }}
              >
                <span className="text-[9px] font-bold text-white px-1">{stats.elevated}</span>
              </div>
            )}
            {stats.low > 0 && (
              <div
                className="h-full bg-emerald-500/70 rounded-r-full flex items-center justify-center"
                style={{ width: `${(stats.low / stats.total) * 100}%`, minWidth: stats.low > 0 ? 32 : 0 }}
              >
                <span className="text-[9px] font-bold text-white px-1">{stats.low}</span>
              </div>
            )}
          </div>
          <div className="flex items-center gap-4 mt-2 text-[10px] text-[var(--text-secondary)]">
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-rose-500" /> CRITICAL: {stats.critical}</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-orange-500" /> HIGH: {stats.high}</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-500" /> ELEVATED: {stats.elevated}</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-500" /> LOW: {stats.low}</span>
            <span className="ml-auto">Avg SST: {stats.avgSst}°C</span>
          </div>
        </GlassCard>
      )}

      {/* Filter tabs */}
      <GlassCard className="!p-3" hover={false} delay={0.25} accent="none">
        <div className="flex items-center gap-2 flex-wrap">
          {["ALL", "CRITICAL", "HIGH", "ELEVATED", "LOW"].map((level) => {
            const count = level === "ALL"
              ? risks.length
              : risks.filter((r) => r.risk_level === level).length;
            return (
              <OcButton
                key={level}
                variant={filter === level ? "accent" : "ghost"}
                size="sm"
                onClick={() => setFilter(level)}
                ripple={false}
              >
                {level} ({count})
              </OcButton>
            );
          })}
          <div className="w-px h-6 bg-white/[0.08] mx-1" />
          <OcButton
            variant={sortAsc ? "accent" : "secondary"}
            size="sm"
            onClick={() => setSortAsc(!sortAsc)}
            ripple={false}
          >
            {sortAsc ? "LOW → HIGH" : "HIGH → LOW"}
          </OcButton>
        </div>
      </GlassCard>

      {/* Algal Bloom Map */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
      >
        <GlassCard hover={false} delay={0.3} accent="ocean" className="!p-0 overflow-hidden">
          <div className="px-5 py-3 border-b border-white/[0.06] flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-[var(--text-primary)]">
                Bloom Risk Map
              </h2>
              <p className="text-[11px] text-[var(--text-secondary)] mt-0.5">
                Chlorophyll-a satellite data · farm sites coloured by risk level · heatmap weighted by Chl-a
              </p>
            </div>
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/[0.08] border border-emerald-500/[0.15]">
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-[10px] text-emerald-400 font-medium">Copernicus CMEMS</span>
            </div>
          </div>
          <div className="p-3">
            <BloomMap risks={risks} />
          </div>
        </GlassCard>
      </motion.div>

      {/* Main content: Risk table + Alerts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Risk Table */}
        <GlassCard className="lg:col-span-2 !p-0 overflow-hidden" hover={false} delay={0.3} accent="ocean">
          <div className="p-5 border-b border-white/[0.06]">
            <h2 className="text-sm font-semibold text-[var(--text-primary)]">
              Farm Risk Assessment
            </h2>
            <p className="text-[11px] text-[var(--text-secondary)] mt-0.5">
              {sortedRisks.length} localities
            </p>
          </div>

          <div className="overflow-x-auto max-h-[600px] overflow-y-auto">
            {loading ? (
              <div className="flex items-center justify-center h-40">
                <div className="w-6 h-6 border-2 border-ocean-500/30 border-t-ocean-400 rounded-full animate-spin" />
              </div>
            ) : sortedRisks.length === 0 ? (
              <div className="text-center py-12 text-[var(--text-secondary)]">
                No bloom data available yet. Waiting for agent cycle.
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-ocean-950/95 backdrop-blur-xl z-10">
                  <tr className="text-[var(--text-secondary)] text-[11px] uppercase tracking-wider">
                    <th className="text-left px-5 py-3">Locality</th>
                    <th className="text-left px-3 py-3">Company</th>
                    <th className="text-left px-3 py-3">Risk</th>
                    <th className="text-right px-3 py-3">Score</th>
                    <th className="text-right px-3 py-3">Chl-a</th>
                    <th className="text-right px-3 py-3">SST</th>
                    <th className="text-center px-3 py-3">Trend</th>
                  </tr>
                </thead>
                <tbody>
                  <AnimatePresence>
                    {sortedRisks.slice(0, 100).map((r, i) => (
                      <motion.tr
                        key={r.locality_no}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: i * 0.01 }}
                        className="border-t border-white/[0.04] hover:bg-white/[0.02] transition-colors"
                      >
                        <td className="px-5 py-3">
                          <div className="font-semibold text-[var(--text-primary)]">
                            {r.locality_name || `Locality ${r.locality_no}`}
                          </div>
                          <div className="text-[11px] text-[var(--text-secondary)] font-mono">
                            #{r.locality_no}
                          </div>
                        </td>
                        <td className="px-3 py-3">
                          <span className="text-xs text-[var(--text-secondary)]">
                            {r.owner_company || "—"}
                          </span>
                        </td>
                        <td className="px-3 py-3">
                          <RiskBadge level={r.risk_level} />
                        </td>
                        <td className="px-3 py-3 text-right font-mono font-semibold text-[var(--text-primary)] tabular-nums">
                          {formatNumber(r.risk_score, locale, 0)}
                        </td>
                        <td className="px-3 py-3 text-right font-mono tabular-nums">
                          <span
                            style={{ color: r.chl_a >= 5 ? RISK_COLORS.HIGH : r.chl_a >= 2 ? RISK_COLORS.ELEVATED : RISK_COLORS.LOW }}
                          >
                            {formatNumber(r.chl_a, locale, 2)}
                          </span>
                        </td>
                        <td className="px-3 py-3 text-right font-mono text-[var(--text-secondary)] tabular-nums">
                          {r.sst != null ? `${formatNumber(r.sst, locale, 1)}C` : "—"}
                        </td>
                        <td className="px-3 py-3 text-center">
                          {r.chl_a_sparkline && r.chl_a_sparkline.length >= 2 ? (
                            <ChlSparkline data={r.chl_a_sparkline} />
                          ) : (
                            <TrendIcon trend={r.chl_a_trend || 0} />
                          )}
                        </td>
                      </motion.tr>
                    ))}
                  </AnimatePresence>
                </tbody>
              </table>
            )}
          </div>
        </GlassCard>

        {/* Alert Log */}
        <GlassCard className="!p-0 overflow-hidden" hover={false} delay={0.35} accent="amber">
          <div className="p-5 border-b border-white/[0.06] flex items-center gap-2">
            <Bell className="w-4 h-4 text-amber-400" />
            <h2 className="text-sm font-semibold text-[var(--text-primary)]">
              Alert Log
            </h2>
          </div>

          <div className="max-h-[600px] overflow-y-auto">
            {alerts.length === 0 ? (
              <div className="text-center py-12 text-[var(--text-secondary)]">
                No alerts sent yet.
              </div>
            ) : (
              <div className="divide-y divide-white/[0.04]">
                {alerts.slice(0, 30).map((a) => (
                  <div key={a.id} className="px-5 py-3 hover:bg-white/[0.02] transition-colors">
                    <div className="flex items-center justify-between mb-1">
                      <RiskBadge level={a.risk_level} />
                      <span className="text-[11px] text-[var(--text-secondary)] font-mono">
                        {a.sent_at ? new Date(a.sent_at).toLocaleString("nb-NO", {
                          month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
                        }) : ""}
                      </span>
                    </div>
                    <div className="text-[11px] text-[var(--text-secondary)] mt-1 flex items-center gap-2">
                      <span className="uppercase tracking-wider font-medium">{a.channel}</span>
                      <span className={a.delivery_status === "sent" ? "text-emerald-400" : "text-rose-400"}>
                        {a.delivery_status}
                      </span>
                    </div>
                    <p className="text-[11px] text-[var(--text-secondary)] mt-1 line-clamp-2">
                      Locality #{a.locality_no}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </GlassCard>
      </div>

      {/* Risk Level Legend */}
      <GlassCard hover={false} delay={0.4} className="!p-4" accent="none">
        <div className="flex items-center gap-6 text-[11px] text-[var(--text-secondary)] flex-wrap">
          <span className="font-semibold text-[var(--text-primary)]">Risk Thresholds:</span>
          <span className="flex items-center gap-1.5">
            <div className="w-2.5 h-2.5 rounded-full shadow-[0_0_6px_currentColor]" style={{ background: RISK_COLORS.LOW, color: RISK_COLORS.LOW }} />
            LOW (&lt;2 mg/m3)
          </span>
          <span className="flex items-center gap-1.5">
            <div className="w-2.5 h-2.5 rounded-full shadow-[0_0_6px_currentColor]" style={{ background: RISK_COLORS.ELEVATED, color: RISK_COLORS.ELEVATED }} />
            ELEVATED (2-5 mg/m3)
          </span>
          <span className="flex items-center gap-1.5">
            <div className="w-2.5 h-2.5 rounded-full shadow-[0_0_6px_currentColor]" style={{ background: RISK_COLORS.HIGH, color: RISK_COLORS.HIGH }} />
            HIGH (5-10 mg/m3)
          </span>
          <span className="flex items-center gap-1.5">
            <div className="w-2.5 h-2.5 rounded-full shadow-[0_0_6px_currentColor]" style={{ background: RISK_COLORS.CRITICAL, color: RISK_COLORS.CRITICAL }} />
            CRITICAL (&gt;10 mg/m3 or bloom + warm SST)
          </span>
        </div>
      </GlassCard>
    </div>
    </ErrorBoundary>
  );
}
