"use client";
import {
  Fish, AlertTriangle, BarChart3, DollarSign, Wheat, Globe2, Shield,
  ChevronDown, ChevronUp,
} from "lucide-react";
import KPICard from "@/components/KPICard";
import GlassCard from "@/components/GlassCard";
import { formatNumber } from "@/lib/i18n";
import type { Locale } from "@/lib/i18n";
import type { LiceSummary } from "@/types/api";
import type { DashboardMacro, DashboardSupply, DashboardLeader } from "@/components/useDashboardData";

interface DashboardKPIStripProps {
  isVisible: boolean;
  order: number;
  metricsExpanded: boolean;
  setMetricsExpanded: (v: boolean) => void;
  ssbSpot: number;
  summary: LiceSummary | null;
  safeLeaders: DashboardLeader[];
  companiesWithData: number;
  macro: DashboardMacro | null;
  supply: DashboardSupply | null;
  diseaseCount: number;
  locale: Locale;
  t: (key: string) => string;
}

export default function DashboardKPIStrip({
  isVisible, order, metricsExpanded, setMetricsExpanded,
  ssbSpot, summary, safeLeaders, companiesWithData,
  macro, supply, diseaseCount, locale, t,
}: DashboardKPIStripProps) {
  if (!isVisible) return null;

  return (
    <div style={{ order }}><div>
      <button
        onClick={() => setMetricsExpanded(!metricsExpanded)}
        className="flex items-center gap-2 mb-3 text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
      >
        {metricsExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        {t("dashboard.key_metrics")}
      </button>
    </div>

    {metricsExpanded && <>
    {/* Hero KPI -- asymmetric: spot price hero + 3 supporting metrics */}
    <div className="grid grid-cols-1 lg:grid-cols-[2fr_1fr_1fr_1fr] gap-4">
      {/* HERO: Spot Price -- 3x prominence */}
      <GlassCard accent="ocean" className="relative overflow-hidden">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[10px] uppercase tracking-wider text-[var(--text-secondary)] mb-1">{t("dashboard.spot_price")}</p>
            <p className="text-5xl font-bold text-kpi text-[var(--text-primary)] leading-none">
              {ssbSpot > 0 ? formatNumber(ssbSpot, locale, 1) : "\u2014"}
            </p>
            <p className="text-sm text-[var(--text-secondary)] mt-1">NOK/kg</p>
            <p className="text-[10px] text-[var(--positive)] mt-2 flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              Live SSB Table 03024
            </p>
          </div>
          <DollarSign className="w-14 h-14 text-ocean-500/20 absolute right-4 top-4" />
        </div>
      </GlassCard>

      <KPICard
        label={t("dashboard.lice_avg")}
        value={summary?.avg_adult_female_lice != null ? formatNumber(summary.avg_adult_female_lice, locale, 3) : "\u2014"}
        delta={(summary?.avg_adult_female_lice ?? 0) < 0.5 ? "Below threshold" : "ABOVE LIMIT"}
        deltaType={(summary?.avg_adult_female_lice ?? 0) < 0.5 ? "positive" : "negative"}
        icon={Fish}
        delay={0.04}
      />
      <KPICard
        label="Max Lice"
        value={summary?.max_adult_female_lice != null ? formatNumber(summary.max_adult_female_lice, locale, 2) : "\u2014"}
        delta={(summary?.max_adult_female_lice ?? 0) > 0.5 ? "ABOVE LIMIT" : "Within limit"}
        deltaType={(summary?.max_adult_female_lice ?? 0) > 0.5 ? "negative" : "positive"}
        icon={AlertTriangle}
        delay={0.08}
      />
      <KPICard
        label="Companies"
        value={companiesWithData || "\u2014"}
        delta={`${Array.isArray(safeLeaders) ? safeLeaders.length : 0} ranked`}
        deltaType="neutral"
        icon={BarChart3}
        delay={0.12}
      />
    </div>

    {/* Macro Context Row */}
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <KPICard
        label={t("dashboard.feed_pressure")}
        value={macro?.indices?.feed_pressure?.value != null ? `${formatNumber(macro.indices.feed_pressure.value, locale, 1)}/100` : "\u2014"}
        delta={(macro?.indices?.feed_pressure?.value ?? 0) > 65 ? "Elevated \u2014 margin risk" : (macro?.indices?.feed_pressure?.value ?? 0) > 45 ? "Moderate" : "Low pressure"}
        deltaType={(macro?.indices?.feed_pressure?.value ?? 0) > 65 ? "negative" : (macro?.indices?.feed_pressure?.value ?? 0) > 45 ? "neutral" : "positive"}
        icon={Wheat}
        delay={0.1}
      />
      <KPICard
        label={t("dashboard.nok_usd")}
        value={macro?.benchmarks?.nok_usd != null ? formatNumber(macro.benchmarks.nok_usd, locale, 2) : "\u2014"}
        delta={macro?.yoy_changes?.nok_usd ? `${macro.yoy_changes.nok_usd > 0 ? "+" : ""}${macro.yoy_changes.nok_usd}% YoY` : undefined}
        deltaType={(macro?.yoy_changes?.nok_usd ?? 0) > 0 ? "negative" : "positive"}
        icon={DollarSign}
        delay={0.13}
      />
      <KPICard
        label={t("dashboard.supply_balance")}
        value={supply?.balance ? supply.balance.charAt(0).toUpperCase() + supply.balance.slice(1).replace(/_/g, " ") : "\u2014"}
        delta={supply?.supply_deficit_pct != null ? `Deficit: ${supply.supply_deficit_pct}%` : undefined}
        deltaType={(supply?.supply_deficit_pct ?? 0) > 2 ? "negative" : "positive"}
        icon={Globe2}
        delay={0.16}
      />
      <KPICard
        label={t("dashboard.disease_outbreaks")}
        value={diseaseCount > 0 ? `${formatNumber(diseaseCount, locale)} active` : "Clear"}
        delta="Mattilsynet + WOAH"
        deltaType={diseaseCount > 3 ? "negative" : diseaseCount > 0 ? "neutral" : "positive"}
        icon={Shield}
        delay={0.19}
      />
    </div>
    </>}</div>
  );
}
