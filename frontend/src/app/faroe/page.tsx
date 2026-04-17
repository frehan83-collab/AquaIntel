"use client";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Globe2, RefreshCw, Fish, AlertTriangle, Activity,
  Thermometer, Shield, TrendingUp, BarChart3, Droplets, Download, Building2,
} from "lucide-react";
import { exportToCSV } from "@/lib/export";
import KPICard from "@/components/KPICard";
import GlassCard from "@/components/GlassCard";
import { OcButton } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { useTranslation, formatNumber } from "@/lib/i18n";
import DataQualityBadge from "@/components/DataQualityBadge";
import ErrorBoundary from "@/components/ErrorBoundary";

/* eslint-disable @typescript-eslint/no-explicit-any */

export default function FaroePage() {
  const { t, locale } = useTranslation();
  const [snapshot, setSnapshot] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const [snap] = await Promise.allSettled([api.faroeSnapshot()]);
      if (snap.status === "fulfilled") setSnapshot(snap.value);
    } catch { /* empty */ }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const production = snapshot?.production_history || [];
  const latest = production.length > 0 ? production[production.length - 1] : null;
  const prev = production.length > 1 ? production[production.length - 2] : null;
  const yoyGrowth = latest && prev && prev.total_t > 0
    ? formatNumber((latest.total_t - prev.total_t) / prev.total_t * 100, locale, 1)
    : null;
  const regions = snapshot?.regions || [];

  return (
    <ErrorBoundary fallbackTitle="Faroe Islands error">
    <div className="space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] flex items-center gap-3">
            <span className="text-lg">🇫🇴</span>
            {t("nav.faroe_islands")}
          </h1>
          <div className="flex items-center gap-2 mt-1">
            <p className="text-sm text-[var(--text-secondary)]">
              Hagstova Føroya &mdash; Bakkafrost dominates ~95% of production
            </p>
            <DataQualityBadge source="Hagstova" quality="live" />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <OcButton variant="ghost" size="sm"
            leftIcon={<Download className="w-3.5 h-3.5" />}
            onClick={() => production.length > 0 && exportToCSV(production, "faroe_production")}>
            CSV
          </OcButton>
          <OcButton variant="secondary" size="sm" onClick={load} loading={loading}
            leftIcon={<RefreshCw className="w-3.5 h-3.5" />}>Refresh</OcButton>
        </div>
      </motion.div>

      {/* KPI Row */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <KPICard
          label="Latest Production"
          value={latest ? `${formatNumber(latest.total_t / 1000, locale, 0)}K t` : "—"}
          delta={yoyGrowth ? `${yoyGrowth}% YoY` : "—"}
          deltaType={yoyGrowth && parseFloat(yoyGrowth) > 0 ? "positive" : "negative"}
          icon={BarChart3}
          delay={0}
        />
        <KPICard
          label="Bakkafrost Share"
          value="~95%"
          delta="Single-company dominance"
          deltaType="neutral"
          icon={TrendingUp}
          delay={0.03}
        />
        <KPICard
          label="Disease Events"
          value={snapshot?.disease_events ?? "—"}
          delta="Low pressure (vaccinated)"
          deltaType={snapshot?.disease_events > 0 ? "negative" : "positive"}
          icon={AlertTriangle}
          delay={0.06}
        />
        <KPICard
          label="SST"
          value={snapshot?.sst_c != null ? `${snapshot.sst_c}°C` : "—"}
          delta="CMEMS Global"
          deltaType="neutral"
          icon={Thermometer}
          delay={0.09}
        />
        <KPICard
          label="Bloom Risk"
          value={snapshot?.bloom_risk || "—"}
          delta={snapshot?.chl_a_mg_m3 != null ? `Chl-a: ${snapshot.chl_a_mg_m3} mg/m³` : "—"}
          deltaType={snapshot?.bloom_risk === "HIGH" || snapshot?.bloom_risk === "CRITICAL" ? "negative" : "positive"}
          icon={Droplets}
          delay={0.12}
        />
      </div>

      {/* ISA Vaccination Banner */}
      <GlassCard delay={0.15} accent="emerald">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center flex-shrink-0">
            <Shield className="w-7 h-7 text-emerald-400" />
          </div>
          <div className="flex-1">
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">
              Mandatory ISA Vaccination Since 2016
            </h3>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">
              The Faroe Islands mandated ISA vaccination for all farmed salmon in 2016, making it
              the most disease-resilient salmon-producing nation. Single-generation, single-fjord
              production strategy minimizes cross-contamination risk.
            </p>
          </div>
          <div className="text-right flex-shrink-0">
            <p className="text-lg font-bold text-emerald-400">Vaccinated</p>
            <p className="text-[10px] text-[var(--text-secondary)]">since 2016</p>
          </div>
        </div>
      </GlassCard>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Production History */}
        <GlassCard delay={0.18}>
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-ocean-400" />
            Production History
            <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-ocean-500/10 text-ocean-400 border border-ocean-500/20 ml-auto">
              Hagstova PxWeb
            </span>
          </h3>
          {production.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-[11px]">
                <thead>
                  <tr className="text-[var(--text-secondary)] border-b border-white/[0.06]">
                    <th className="text-left py-1.5 font-medium">Year</th>
                    <th className="text-right py-1.5 font-medium">Salmon (t)</th>
                    <th className="text-right py-1.5 font-medium">Trout (t)</th>
                    <th className="text-right py-1.5 font-medium">Total (t)</th>
                  </tr>
                </thead>
                <tbody>
                  {production.map((p: any) => (
                    <tr key={p.year} className="border-b border-white/[0.03] hover:bg-white/[0.02]">
                      <td className="py-1.5 text-[var(--text-primary)] font-medium">{p.year}</td>
                      <td className="text-right py-1.5 tabular-nums">{p.salmon_t?.toLocaleString() || "—"}</td>
                      <td className="text-right py-1.5 tabular-nums">{p.trout_t?.toLocaleString() || "—"}</td>
                      <td className="text-right py-1.5 tabular-nums font-semibold text-ocean-400">
                        {p.total_t?.toLocaleString() || "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-xs text-[var(--text-secondary)] py-4 text-center opacity-60">
              Loading Hagstova data...
            </p>
          )}
        </GlassCard>

        {/* Regional Overview */}
        <GlassCard delay={0.21}>
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <Fish className="w-4 h-4 text-violet-400" />
            Farm Regions
            <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-violet-500/10 text-violet-400 border border-violet-500/20 ml-auto">
              {regions.length} fjords
            </span>
          </h3>
          <div className="space-y-1.5">
            {regions.length > 0 ? regions.map((r: any, i: number) => (
              <div key={i} className="flex items-center justify-between p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                <span className="text-[11px] font-medium text-[var(--text-primary)]">
                  {r.name || r.region || `Fjord ${i + 1}`}
                </span>
                <div className="flex items-center gap-3">
                  {r.company && (
                    <span className="text-[10px] text-[var(--text-secondary)]">{r.company}</span>
                  )}
                  {r.isa_vaccination && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400">
                      ISA Vacc.
                    </span>
                  )}
                </div>
              </div>
            )) : (
              <p className="text-xs text-[var(--text-secondary)] py-4 text-center opacity-60">
                Loading regional data...
              </p>
            )}
          </div>

          {/* Data Sources */}
          <div className="mt-4 p-3 rounded-xl bg-ocean-500/[0.04] border border-ocean-500/[0.1]">
            <p className="text-[10px] font-semibold text-ocean-400 mb-1">Data Sources</p>
            <div className="space-y-1 text-[10px] text-[var(--text-secondary)]">
              <p>Hagstova Føroya (PxWeb API) — official aquaculture harvest statistics</p>
              <p>CMEMS Global — SST + chlorophyll-a satellite data</p>
              <p>WOAH WAHIS — disease outbreak surveillance</p>
            </div>
          </div>
        </GlassCard>
      </div>

      {/* Industry Structure */}
      <GlassCard delay={0.24}>
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <Building2 className="w-4 h-4 text-amber-400" />
          Industry Structure
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06]">
            <p className="text-[10px] text-[var(--text-secondary)] uppercase tracking-wider mb-1">Market Dominance</p>
            <p className="text-lg font-bold text-amber-400">~95%</p>
            <p className="text-[10px] text-[var(--text-secondary)] mt-1">
              Bakkafrost controls nearly all Faroese salmon production.
              Vertically integrated: smolt, sea farming, processing, and sales.
            </p>
          </div>
          <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06]">
            <p className="text-[10px] text-[var(--text-secondary)] uppercase tracking-wider mb-1">ISA Vaccination</p>
            <p className="text-lg font-bold text-emerald-400">Mandatory</p>
            <p className="text-[10px] text-[var(--text-secondary)] mt-1">
              Since 2016, all farmed salmon must be ISA-vaccinated.
              Result: near-zero ISA outbreaks, lowest disease pressure globally.
            </p>
          </div>
          <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06]">
            <p className="text-[10px] text-[var(--text-secondary)] uppercase tracking-wider mb-1">Regulation vs Norway</p>
            <p className="text-lg font-bold text-ocean-400">Individual</p>
            <p className="text-[10px] text-[var(--text-secondary)] mt-1">
              Norway uses MAB (production area caps) + Traffic Light.
              Faroe: individual company licenses, single-generation fjord strategy.
            </p>
          </div>
        </div>
      </GlassCard>

      {/* Insights */}
      {snapshot?.insights?.length > 0 && (
        <GlassCard delay={0.27} accent="ocean">
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <Activity className="w-4 h-4 text-ocean-400" />
            Intelligence
          </h3>
          <div className="space-y-2">
            {snapshot.insights.map((ins: string, i: number) => (
              <div key={i} className="flex items-start gap-2 p-2.5 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                <Globe2 className="w-3.5 h-3.5 text-ocean-400 flex-shrink-0 mt-0.5" />
                <p className="text-[11px] text-[var(--text-primary)] leading-relaxed">{ins}</p>
              </div>
            ))}
          </div>
        </GlassCard>
      )}

      <p className="text-[9px] text-[var(--text-secondary)] text-center opacity-50">
        Data: Hagstova Føroya (hagstova.fo), Copernicus CMEMS, WOAH WAHIS.
        3% of global Atlantic salmon supply. Not financial or regulatory advice.
      </p>
    </div>
    </ErrorBoundary>
  );
}
