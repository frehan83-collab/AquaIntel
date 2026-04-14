"use client";
import Link from "next/link";
import {
  AlertTriangle, GitBranch, Ship, BarChart3, BarChart2, Zap, ArrowRight,
} from "lucide-react";
import GlassCard from "@/components/GlassCard";
import { formatNumber } from "@/lib/i18n";
import type { Locale } from "@/lib/i18n";
import type { RegimeAlert, PairsSignal } from "@/types/api";
import type { DashboardAIS, ProductionSummary } from "@/components/useDashboardData";

/* eslint-disable @typescript-eslint/no-explicit-any */

interface DashboardProductionProps {
  isVisible: boolean;
  order: number;
  regimeAlerts: RegimeAlert[];
  pairsSignals: PairsSignal[];
  aisData: DashboardAIS | null;
  production: ProductionSummary | null;
  counties: Array<{ county: string; harvest_tonnes: number }>;
  locale: Locale;
  t: (key: string) => string;
}

export default function DashboardProduction({
  isVisible, order, regimeAlerts, pairsSignals, aisData, production, counties, locale, t,
}: DashboardProductionProps) {
  if (!isVisible) return null;

  return (
    <div style={{ order }}><div className="grid grid-cols-1 lg:grid-cols-4 gap-4">

      {/* Regime Alerts */}
      <GlassCard delay={0.22}>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            {t("dashboard.regime_alerts")}
          </h3>
          <Link href="/lice" className="text-[10px] text-ocean-400 hover:text-ocean-300 transition-colors flex items-center gap-1">
            View all <ArrowRight className="w-3 h-3" />
          </Link>
        </div>
        {regimeAlerts.length === 0 ? (
          <p className="text-xs text-[var(--text-secondary)] py-4 text-center opacity-60">No active regime alerts</p>
        ) : (
          <div className="space-y-1.5">
            {regimeAlerts.slice(0, 4).map((alert: any, i: number) => (
              <div key={i} className="flex items-start gap-2 p-2 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                <div className={`w-2 h-2 rounded-full flex-shrink-0 mt-1 ${
                  alert.severity === "critical" ? "bg-rose-400" :
                  alert.severity === "high" ? "bg-amber-400" : "bg-yellow-400"
                }`} />
                <div className="min-w-0">
                  <p className="text-[11px] font-medium text-[var(--text-primary)] truncate">{alert.pa_name || `PA ${alert.pa}`}</p>
                  <p className="text-[10px] text-[var(--text-secondary)] truncate">{alert.message?.slice(0, 60)}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </GlassCard>

      {/* Pairs Signals */}
      <GlassCard delay={0.24}>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold flex items-center gap-2">
            <GitBranch className="w-4 h-4 text-purple-400" />
            {t("dashboard.pairs_signals")}
          </h3>
          <Link href="/signals" className="text-[10px] text-ocean-400 hover:text-ocean-300 transition-colors flex items-center gap-1">
            View all <ArrowRight className="w-3 h-3" />
          </Link>
        </div>
        {pairsSignals.length === 0 ? (
          <p className="text-xs text-[var(--text-secondary)] py-4 text-center opacity-60">No pairs signals &mdash; neutral spread</p>
        ) : (
          <div className="space-y-1.5">
            {pairsSignals.slice(0, 4).map((ps: any, i: number) => (
              <div key={i} className="flex items-center justify-between p-2 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                <div>
                  <p className="text-[11px] font-semibold text-[var(--text-primary)]">{ps.pair}</p>
                  <p className="text-[10px] text-[var(--text-secondary)]">z={ps.z_score != null ? formatNumber(ps.z_score, locale, 2) : "\u2014"} &middot; {ps.signal?.replace(/_/g, " ")}</p>
                </div>
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded-md ${
                  ps.signal?.includes("LONG") ? "bg-emerald-500/10 text-emerald-400" :
                  ps.signal?.includes("SHORT") ? "bg-rose-500/10 text-rose-400" :
                  "bg-white/5 text-[var(--text-secondary)]"
                }`}>
                  {ps.signal?.split("_").pop()}
                </span>
              </div>
            ))}
          </div>
        )}
      </GlassCard>

      {/* AIS Activity */}
      <GlassCard delay={0.26}>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold flex items-center gap-2">
            <Ship className="w-4 h-4 text-ocean-400" />
            {t("dashboard.ais_vessels")}
          </h3>
          <span className="text-[10px] text-[var(--text-secondary)]">72h window</span>
        </div>
        {!aisData ? (
          <p className="text-xs text-[var(--text-secondary)] py-4 text-center opacity-60">{t("common.loading")}</p>
        ) : (
          <div className="space-y-2">
            <div className="flex items-center justify-between p-2.5 rounded-lg bg-ocean-500/[0.04] border border-ocean-500/[0.1]">
              <span className="text-xs text-[var(--text-secondary)]">Harvest signals</span>
              <span className="text-sm font-bold text-ocean-400">{Array.isArray(aisData) ? aisData.length : (aisData?.signals?.length || 0)}</span>
            </div>
            {Array.isArray(aisData) && aisData.slice(0, 3).map((sig: any, i: number) => (
              <div key={i} className="flex items-center gap-2 p-1.5 rounded-md bg-white/[0.02]">
                <Zap className="w-3 h-3 text-amber-400 flex-shrink-0" />
                <div className="min-w-0">
                  <p className="text-[11px] text-[var(--text-primary)] truncate">{sig.vessel_name || sig.locality_name || "Wellboat"}</p>
                  <p className="text-[10px] text-[var(--text-secondary)]">{sig.signal_type || "harvest"}</p>
                </div>
              </div>
            ))}
            <Link href="/command-centre" className="flex items-center gap-1 text-[10px] text-ocean-400 hover:text-ocean-300 transition-colors mt-1">
              <BarChart2 className="w-3 h-3" />
              Open Command Centre
            </Link>
          </div>
        )}
      </GlassCard>

      {/* Production */}
      <GlassCard delay={0.28}>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-emerald-400" />
            {t("dashboard.production_stats")}
          </h3>
        </div>
        {!production ? (
          <p className="text-xs text-[var(--text-secondary)] py-4 text-center opacity-60">{t("common.loading")}</p>
        ) : (
          <div className="space-y-2">
            <div className="flex items-center justify-between p-2.5 rounded-lg bg-emerald-500/[0.04] border border-emerald-500/[0.1]">
              <span className="text-xs text-[var(--text-secondary)]">Annual (latest)</span>
              <span className="text-sm font-bold text-emerald-400">
                {production.total_tonnes ? `${formatNumber(production.total_tonnes / 1000, locale, 0)}k t` : production.latest_year || "\u2014"}
              </span>
            </div>
            {production.salmon_tonnes && (
              <div className="flex items-center justify-between p-1.5 rounded-md bg-white/[0.02]">
                <span className="text-[10px] text-[var(--text-secondary)]">Salmon</span>
                <span className="text-[11px] font-mono">{formatNumber(production.salmon_tonnes / 1000, locale, 0)}k t</span>
              </div>
            )}
            {production.yoy_change_pct != null && (
              <div className="flex items-center justify-between p-1.5 rounded-md bg-white/[0.02]">
                <span className="text-[10px] text-[var(--text-secondary)]">YoY Change</span>
                <span className={`text-[11px] font-mono ${production.yoy_change_pct > 0 ? "text-emerald-400" : "text-rose-400"}`}>
                  {production.yoy_change_pct > 0 ? "+" : ""}{production.yoy_change_pct}%
                </span>
              </div>
            )}
            {counties.length > 0 && (
              <div className="mt-2 pt-2 border-t border-white/[0.06]">
                <p className="text-[9px] text-[var(--text-secondary)] uppercase tracking-wider mb-1.5">Top Counties</p>
                {counties.map((c: any, i: number) => {
                  const h = c.harvest_tonnes || 0;
                  const maxH = counties[0]?.harvest_tonnes || 1;
                  return (
                    <div key={i} className="flex items-center gap-2 py-0.5">
                      <span className="text-[10px] text-[var(--text-secondary)] w-20 truncate">{c.county || c.name || `#${i + 1}`}</span>
                      <div className="flex-1 h-2 bg-white/[0.04] rounded-full overflow-hidden">
                        <div className="h-full bg-emerald-500/40 rounded-full" style={{ width: `${(h / maxH) * 100}%` }} />
                      </div>
                      <span className="text-[10px] text-[var(--text-primary)] tabular-nums w-12 text-right">{formatNumber(h / 1000, locale, 0)}k</span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </GlassCard>
    </div></div>
  );
}
