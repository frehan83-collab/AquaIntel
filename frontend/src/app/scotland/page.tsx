"use client";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Globe2, RefreshCw, Fish, AlertTriangle, Activity,
  Thermometer, Shield, TrendingUp, BarChart3, Download,
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

const REGION_COLORS: Record<string, string> = {
  Shetland: "text-ocean-400",
  Orkney: "text-emerald-400",
  "NW Highlands": "text-amber-400",
  "Skye & Lochalsh": "text-violet-400",
  Argyll: "text-rose-400",
  "Outer Hebrides": "text-sky-400",
  "Loch Linnhe": "text-orange-400",
};

export default function ScotlandPage() {
  const { t, locale } = useTranslation();
  const [snapshot, setSnapshot] = useState<any>(null);
  const [norwayLice, setNorwayLice] = useState<number>(0);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const [snap, norLice] = await Promise.allSettled([
        api.scotlandSnapshot(),
        api.liceSummary(),
      ]);
      if (snap.status === "fulfilled") setSnapshot(snap.value);
      if (norLice.status === "fulfilled") setNorwayLice(norLice.value?.avg_adult_female_lice || 0);
    } catch { /* empty */ }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const sea = snapshot?.sea_conditions || {};
  const regions = snapshot?.regions || [];

  return (
    <ErrorBoundary fallbackTitle="Scotland error">
    <div className="space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] flex items-center gap-3">
            <span className="text-lg">🏴󠁧󠁢󠁳󠁣󠁴󠁿</span>
            {t("nav.scotland")}
          </h1>
          <div className="flex items-center gap-2 mt-1">
            <p className="text-sm text-[var(--text-secondary)]">
              Marine Scotland — ~207,000 tonnes/year, 7% of global Atlantic salmon supply
            </p>
            <DataQualityBadge source="Marine Scotland" quality="live" />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <OcButton variant="ghost" size="sm"
            leftIcon={<Download className="w-3.5 h-3.5" />}
            onClick={() => regions.length > 0 && exportToCSV(regions, "scotland_regions")}>
            CSV
          </OcButton>
          <OcButton variant="secondary" size="sm" onClick={load} loading={loading}
            leftIcon={<RefreshCw className="w-3.5 h-3.5" />}>Refresh</OcButton>
        </div>
      </motion.div>

      {/* KPI Row */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <KPICard
          label="Annual Production"
          value={snapshot?.production_tonnes ? `${formatNumber(snapshot.production_tonnes / 1000, locale, 0)}K t` : "—"}
          delta="7% of global supply"
          deltaType="neutral"
          icon={BarChart3}
          delay={0}
        />
        <KPICard
          label="Active Sites"
          value={snapshot?.total_sites || "—"}
          delta="5 major companies"
          deltaType="neutral"
          icon={Fish}
          delay={0.03}
        />
        <KPICard
          label="Disease Events"
          value={snapshot?.disease_events ?? "—"}
          delta="WOAH notifications"
          deltaType={snapshot?.disease_events > 0 ? "negative" : "positive"}
          icon={AlertTriangle}
          delay={0.06}
        />
        <KPICard
          label="PD Status"
          value={snapshot?.pd_status || "—"}
          delta="Pancreas Disease (SAV)"
          deltaType={snapshot?.pd_status === "Endemic" ? "negative" : "neutral"}
          icon={Shield}
          delay={0.09}
        />
        <KPICard
          label="SST"
          value={sea.sst_c != null ? `${sea.sst_c}°C` : "—"}
          delta={`Bloom: ${sea.bloom_risk || "unknown"}`}
          deltaType={sea.bloom_risk === "HIGH" || sea.bloom_risk === "CRITICAL" ? "negative" : "positive"}
          icon={Thermometer}
          delay={0.12}
        />
      </div>

      {/* Endemic PD Banner */}
      <GlassCard delay={0.15} accent="amber">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-2xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center flex-shrink-0">
            <Shield className="w-7 h-7 text-amber-400" />
          </div>
          <div className="flex-1">
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">
              Endemic Pancreas Disease (PD)
            </h3>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">
              SAV2 and SAV3 are endemic in Scottish salmon farming. PD causes chronic inflammation
              of the pancreas, heart, and skeletal muscle. Industry manages through vaccination
              and zone management rather than eradication.
            </p>
          </div>
          <div className="text-right flex-shrink-0">
            <p className="text-lg font-bold text-amber-400">{snapshot?.pd_status || "Endemic"}</p>
            <p className="text-[10px] text-[var(--text-secondary)]">status</p>
          </div>
        </div>
      </GlassCard>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Regional Overview */}
        <GlassCard delay={0.18}>
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <Fish className="w-4 h-4 text-ocean-400" />
            Farm Regions
            <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-ocean-500/10 text-ocean-400 border border-ocean-500/20 ml-auto">
              7 regions
            </span>
          </h3>
          <div className="space-y-1.5">
            {regions.length > 0 ? regions.map((r: any, i: number) => (
              <div key={i} className="flex items-center justify-between p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                <span className={`text-[11px] font-medium ${REGION_COLORS[r.name || r.region] || "text-[var(--text-primary)]"}`}>
                  {r.name || r.region || `Region ${i + 1}`}
                </span>
                <div className="flex items-center gap-3">
                  {r.company && (
                    <span className="text-[10px] text-[var(--text-secondary)]">{r.company}</span>
                  )}
                  {r.sst_c != null && (
                    <span className="text-[10px] text-ocean-400">{r.sst_c}°C</span>
                  )}
                  {r.bloom_risk && (
                    <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                      r.bloom_risk === "HIGH" || r.bloom_risk === "CRITICAL"
                        ? "bg-rose-500/10 text-rose-400"
                        : r.bloom_risk === "MODERATE"
                        ? "bg-amber-500/10 text-amber-400"
                        : "bg-emerald-500/10 text-emerald-400"
                    }`}>
                      {r.bloom_risk}
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
        </GlassCard>

        {/* Scotland vs Norway Comparison */}
        <GlassCard delay={0.21}>
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-violet-400" />
            Scotland vs Norway
          </h3>
          <div className="space-y-3">
            <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06]">
              <div className="text-[10px] text-[var(--text-secondary)] uppercase tracking-wider mb-2">
                Key Metrics Comparison
              </div>
              <div className="grid grid-cols-3 gap-2">
                <div className="text-center">
                  <p className="text-[9px] text-[var(--text-secondary)]">Metric</p>
                </div>
                <div className="text-center">
                  <p className="text-[9px] text-[var(--text-secondary)]">🏴󠁧󠁢󠁳󠁣󠁴󠁿 Scotland</p>
                </div>
                <div className="text-center">
                  <p className="text-[9px] text-[var(--text-secondary)]">🇳🇴 Norway</p>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-2 mt-2">
                <div className="text-[10px] text-[var(--text-secondary)]">Production</div>
                <div className="text-center text-[11px] font-bold text-[var(--text-primary)]">~207K t</div>
                <div className="text-center text-[11px] font-bold text-[var(--text-primary)]">~1,600K t</div>
              </div>
              <div className="grid grid-cols-3 gap-2 mt-1">
                <div className="text-[10px] text-[var(--text-secondary)]">Lice Regime</div>
                <div className="text-center text-[11px] text-amber-400">Weekly reports</div>
                <div className="text-center text-[11px] text-ocean-400">Traffic Light</div>
              </div>
              <div className="grid grid-cols-3 gap-2 mt-1">
                <div className="text-[10px] text-[var(--text-secondary)]">PD Status</div>
                <div className="text-center text-[11px] text-rose-400">Endemic</div>
                <div className="text-center text-[11px] text-amber-400">Sporadic</div>
              </div>
              <div className="grid grid-cols-3 gap-2 mt-1">
                <div className="text-[10px] text-[var(--text-secondary)]">Avg Lice</div>
                <div className="text-center text-[11px] text-[var(--text-primary)]">{snapshot?.avg_lice != null ? formatNumber(Number(snapshot.avg_lice), locale, 3) : "—"}</div>
                <div className="text-center text-[11px] text-[var(--text-primary)]">{norwayLice > 0 ? formatNumber(norwayLice, locale, 3) : "—"}</div>
              </div>
              <div className="grid grid-cols-3 gap-2 mt-1">
                <div className="text-[10px] text-[var(--text-secondary)]">Regulator</div>
                <div className="text-center text-[11px] text-amber-400">SEPA / Marine Scot.</div>
                <div className="text-center text-[11px] text-ocean-400">Mattilsynet</div>
              </div>
              <div className="grid grid-cols-3 gap-2 mt-1">
                <div className="text-[10px] text-[var(--text-secondary)]">Global Share</div>
                <div className="text-center text-[11px] text-[var(--text-primary)]">~7%</div>
                <div className="text-center text-[11px] text-[var(--text-primary)]">~55%</div>
              </div>
            </div>

            {/* PD Endemic Detail */}
            <div className="p-3 rounded-xl bg-amber-500/[0.04] border border-amber-500/[0.1]">
              <p className="text-[10px] font-semibold text-amber-400 mb-1">Pancreas Disease (PD) — Endemic in Scotland</p>
              <div className="space-y-1 text-[10px] text-[var(--text-secondary)]">
                <p>SAV2 dominant in Shetland; SAV3 in mainland west coast</p>
                <p>Chronic inflammation: pancreas, heart, skeletal muscle</p>
                <p>Norway: PD is sporadic and regionally controlled via zones</p>
                <p>Scotland: Zone management + vaccination (no eradication target)</p>
              </div>
            </div>

            <div className="p-3 rounded-xl bg-ocean-500/[0.04] border border-ocean-500/[0.1]">
              <p className="text-[10px] font-semibold text-ocean-400 mb-1">Data Sources</p>
              <div className="space-y-1 text-[10px] text-[var(--text-secondary)]">
                <p>Marine Scotland DKAN — historical lice monitoring (CSV)</p>
                <p>CMEMS NW Shelf — SST + chlorophyll-a satellite data</p>
                <p>WOAH WAHIS — disease outbreak notifications</p>
              </div>
              <p className="text-[9px] text-ocean-400 mt-2">
                Crown Copyright — Open Government Licence (Scotland).
              </p>
            </div>
          </div>
        </GlassCard>
      </div>

      {/* Insights */}
      {snapshot?.insights?.length > 0 && (
        <GlassCard delay={0.24} accent="ocean">
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
        Data: Marine Scotland (gov.scot), Copernicus CMEMS NW Shelf, WOAH WAHIS.
        Not financial or regulatory advice.
      </p>
    </div>
    </ErrorBoundary>
  );
}
