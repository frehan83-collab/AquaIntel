"use client";
import { AlertTriangle, GitBranch, Ship, Network } from "lucide-react";
import GlassCard from "@/components/GlassCard";
import { formatNumber } from "@/lib/i18n";
import type { Locale } from "@/lib/i18n";
import type { RegimeAlert, PairsSignal } from "@/types/api";
import type { DashboardAIS } from "@/components/useDashboardData";

/* eslint-disable @typescript-eslint/no-explicit-any */

interface DashboardLiveIntelligenceProps {
  isVisible: boolean;
  order: number;
  regimeAlerts: RegimeAlert[];
  pairsSignals: PairsSignal[];
  aisData: DashboardAIS | null;
  locale: Locale;
  t: (key: string) => string;
}

export default function DashboardLiveIntelligence({
  isVisible, order, regimeAlerts, pairsSignals, aisData, locale, t,
}: DashboardLiveIntelligenceProps) {
  if (!isVisible) return null;

  return (
    <div style={{ order }}><GlassCard delay={0.2} accent="ocean">
      <div className="flex items-center gap-2 mb-3">
        <Network className="w-4 h-4 text-ocean-400" />
        <h3 className="text-sm font-semibold text-[var(--text-primary)]">
          {t("dashboard.live_intelligence")}
        </h3>
        <span className="ml-auto text-[9px] px-1.5 py-0.5 rounded-full bg-ocean-500/10 text-ocean-400 border border-ocean-500/20">
          Real-time
        </span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {/* Regime Alerts Summary */}
        <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06]">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className={`w-3.5 h-3.5 ${regimeAlerts.length > 0 ? "text-amber-400" : "text-emerald-400"}`} />
            <span className="text-[11px] font-semibold text-[var(--text-primary)]">{t("dashboard.regime_alerts")}</span>
            <span className={`ml-auto text-xs font-bold tabular-nums ${regimeAlerts.length > 0 ? "text-amber-400" : "text-emerald-400"}`}>
              {regimeAlerts.length}
            </span>
          </div>
          {regimeAlerts.length > 0 ? (
            <p className="text-[10px] text-[var(--text-secondary)] leading-relaxed">
              Top: {regimeAlerts[0]?.pa_name || `PA ${regimeAlerts[0]?.pa}`} &mdash;{" "}
              {regimeAlerts[0]?.message?.slice(0, 80) || "Regime change detected"}
            </p>
          ) : (
            <p className="text-[10px] text-[var(--text-secondary)] opacity-60">All production areas nominal</p>
          )}
        </div>

        {/* Pairs Signals Summary */}
        <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06]">
          <div className="flex items-center gap-2 mb-2">
            <GitBranch className={`w-3.5 h-3.5 ${pairsSignals.length > 0 ? "text-purple-400" : "text-emerald-400"}`} />
            <span className="text-[11px] font-semibold text-[var(--text-primary)]">{t("dashboard.pairs_signals")}</span>
            <span className={`ml-auto text-xs font-bold tabular-nums ${pairsSignals.length > 0 ? "text-purple-400" : "text-emerald-400"}`}>
              {pairsSignals.length}
            </span>
          </div>
          {pairsSignals.length > 0 ? (
            <div className="flex flex-wrap gap-1">
              {pairsSignals.slice(0, 3).map((ps: any, i: number) => (
                <span key={i} className={`text-[9px] font-semibold px-1.5 py-0.5 rounded ${
                  ps.signal?.includes("LONG") ? "bg-emerald-500/10 text-emerald-400" :
                  ps.signal?.includes("SHORT") ? "bg-rose-500/10 text-rose-400" :
                  "bg-white/5 text-[var(--text-secondary)]"
                }`}>
                  {ps.pair} z={ps.z_score != null ? formatNumber(ps.z_score, locale, 1) : "\u2014"}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-[10px] text-[var(--text-secondary)] opacity-60">Spreads at normal levels</p>
          )}
        </div>

        {/* AIS Vessel Summary */}
        <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06]">
          <div className="flex items-center gap-2 mb-2">
            <Ship className="w-3.5 h-3.5 text-cyan-400" />
            <span className="text-[11px] font-semibold text-[var(--text-primary)]">{t("dashboard.ais_vessels")}</span>
            <span className="ml-auto text-xs font-bold tabular-nums text-cyan-400">
              {aisData ? (Array.isArray(aisData) ? aisData.length : (aisData?.signals?.length || 0)) : 0}
            </span>
          </div>
          {aisData && (Array.isArray(aisData) ? aisData.length : (aisData?.signals?.length || 0)) > 0 ? (
            <p className="text-[10px] text-[var(--text-secondary)] leading-relaxed">
              {(() => {
                const vessels = Array.isArray(aisData) ? aisData : (aisData?.signals || []);
                const topVessel = vessels[0];
                return topVessel
                  ? `${topVessel.vessel_name || "Wellboat"} near ${topVessel.locality_name || topVessel.farm_name || "farm"} (${topVessel.signal_type || "harvest"})`
                  : "Active vessel signals detected";
              })()}
            </p>
          ) : (
            <p className="text-[10px] text-[var(--text-secondary)] opacity-60">No harvest vessel activity</p>
          )}
        </div>
      </div>
    </GlassCard></div>
  );
}
