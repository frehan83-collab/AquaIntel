"use client";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Globe2, RefreshCw, Fish, Activity, Thermometer, Shield,
  TrendingUp, BarChart3, Wind, Droplets, Award, Ship, Download,
} from "lucide-react";
import { exportToCSV } from "@/lib/export";
import KPICard from "@/components/KPICard";
import GlassCard from "@/components/GlassCard";
import { OcButton } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";

/* eslint-disable @typescript-eslint/no-explicit-any */

export default function IcelandPage() {
  const { t } = useTranslation();
  const [snapshot, setSnapshot] = useState<any>(null);
  const [production, setProduction] = useState<any>(null);
  const [exports, setExports] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const [snap, prod, exp] = await Promise.allSettled([
        api.icelandSnapshot(),
        api.icelandProduction(),
        api.icelandExports(),
      ]);
      if (snap.status === "fulfilled") setSnapshot(snap.value);
      if (prod.status === "fulfilled") setProduction(prod.value);
      if (exp.status === "fulfilled") setExports(exp.value);
    } catch { /* empty */ }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const sea = snapshot?.sea_conditions || {};
  const west = sea.westfjords || {};
  const east = sea.eastfjords || {};
  const licenses = snapshot?.licenses || [];
  const prodHistory = production?.production_history || snapshot?.production_history || [];
  const exportHistory = exports?.exports || snapshot?.exports || [];

  // Growth rate from last 2 years
  const lastProd = prodHistory.length > 0 ? prodHistory[prodHistory.length - 1] : null;
  const prevProd = prodHistory.length > 1 ? prodHistory[prodHistory.length - 2] : null;
  const growthPct = lastProd && prevProd && prevProd.total_tonnes > 0
    ? ((lastProd.total_tonnes - prevProd.total_tonnes) / prevProd.total_tonnes * 100).toFixed(1)
    : null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] flex items-center gap-3">
            <span className="text-lg">🇮🇸</span>
            {t("nav.iceland")}
          </h1>
          <p className="text-sm text-[var(--text-secondary)] mt-1">
            5 live sources &mdash; fastest-growing Atlantic salmon producer (35% CAGR since 2016)
          </p>
        </div>
        <div className="flex items-center gap-2">
          <OcButton variant="ghost" size="sm"
            leftIcon={<Download className="w-3.5 h-3.5" />}
            onClick={() => prodHistory.length > 0 && exportToCSV(prodHistory, "iceland_production")}>
            CSV
          </OcButton>
          <OcButton variant="secondary" size="sm" onClick={load} loading={loading}
            leftIcon={<RefreshCw className="w-3.5 h-3.5" />}>Refresh</OcButton>
        </div>
      </motion.div>

      {/* KPI Row */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <KPICard
          label="Total MAB"
          value={snapshot?.total_mab_tonnes ? `${(snapshot.total_mab_tonnes / 1000).toFixed(1)}K t` : "—"}
          delta="Maximum Allowed Biomass"
          deltaType="neutral"
          icon={BarChart3}
          delay={0}
        />
        <KPICard
          label="Active Farms"
          value={snapshot?.farms_count || "—"}
          delta="Arnarlax + Arctic Fish"
          deltaType="neutral"
          icon={Fish}
          delay={0.03}
        />
        <KPICard
          label="Disease Status"
          value={snapshot?.disease_status || "—"}
          delta={`${snapshot?.disease_events || 0} events`}
          deltaType={snapshot?.disease_status === "Disease-free" ? "positive" : "negative"}
          icon={Shield}
          delay={0.06}
        />
        <KPICard
          label="Westfjords SST"
          value={west.sst_c != null ? `${west.sst_c}°C` : "—"}
          delta={`Bloom: ${west.bloom_risk || "unknown"}`}
          deltaType={west.bloom_risk === "HIGH" || west.bloom_risk === "CRITICAL" ? "negative" : "positive"}
          icon={Thermometer}
          delay={0.09}
        />
        <KPICard
          label="Eastfjords SST"
          value={east.sst_c != null ? `${east.sst_c}°C` : "—"}
          delta={`Bloom: ${east.bloom_risk || "unknown"}`}
          deltaType={east.bloom_risk === "HIGH" || east.bloom_risk === "CRITICAL" ? "negative" : "positive"}
          icon={Thermometer}
          delay={0.12}
        />
      </div>

      {/* Disease-Free Banner */}
      <GlassCard delay={0.15} accent="emerald">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center flex-shrink-0">
            <Award className="w-7 h-7 text-emerald-400" />
          </div>
          <div className="flex-1">
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">
              Disease-Free Status
            </h3>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">
              Iceland maintains disease-free status for ISA, VHS, IHN, and BKD. MAST (Icelandic Food
              and Veterinary Authority) conducts active surveillance. No per-site lice data is
              publicly available &mdash; MAST publishes only in PDF inspection reports.
            </p>
          </div>
          <div className="text-right flex-shrink-0">
            <p className="text-lg font-bold text-emerald-400">{snapshot?.disease_status || "Disease-free"}</p>
            <p className="text-[10px] text-[var(--text-secondary)]">confirmed 2024</p>
          </div>
        </div>
      </GlassCard>

      {/* Westfjords vs Eastfjords + Licenses */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <GlassCard delay={0.18}>
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <Thermometer className="w-4 h-4 text-ocean-400" />
            Westfjords vs Eastfjords
          </h3>
          <div className="grid grid-cols-2 gap-3">
            {/* Westfjords */}
            <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06]">
              <p className="text-[10px] text-ocean-400 font-semibold mb-2">Westfjords (Arnarlax)</p>
              <div className="space-y-1.5">
                <div className="flex justify-between">
                  <span className="text-[10px] text-[var(--text-secondary)]">SST</span>
                  <span className="text-[11px] font-mono text-[var(--text-primary)]">{west.sst_c ?? "—"}°C</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[10px] text-[var(--text-secondary)]">Chl-a</span>
                  <span className="text-[11px] font-mono text-[var(--text-primary)]">{west.chl_a_mg_m3 ?? "—"} mg/m³</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[10px] text-[var(--text-secondary)]">Bloom</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                    west.bloom_risk === "HIGH" || west.bloom_risk === "CRITICAL"
                      ? "bg-rose-500/10 text-rose-400"
                      : "bg-emerald-500/10 text-emerald-400"
                  }`}>{west.bloom_risk || "—"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[10px] text-[var(--text-secondary)]">Air Temp</span>
                  <span className="text-[11px] font-mono text-[var(--text-primary)]">{west.air_temp_c ?? "—"}°C</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[10px] text-[var(--text-secondary)]">Wind</span>
                  <span className="text-[11px] font-mono text-[var(--text-primary)]">{west.wind_ms ?? "—"} m/s</span>
                </div>
              </div>
            </div>
            {/* Eastfjords */}
            <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06]">
              <p className="text-[10px] text-violet-400 font-semibold mb-2">Eastfjords (Arctic Fish)</p>
              <div className="space-y-1.5">
                <div className="flex justify-between">
                  <span className="text-[10px] text-[var(--text-secondary)]">SST</span>
                  <span className="text-[11px] font-mono text-[var(--text-primary)]">{east.sst_c ?? "—"}°C</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[10px] text-[var(--text-secondary)]">Chl-a</span>
                  <span className="text-[11px] font-mono text-[var(--text-primary)]">{east.chl_a_mg_m3 ?? "—"} mg/m³</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[10px] text-[var(--text-secondary)]">Bloom</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                    east.bloom_risk === "HIGH" || east.bloom_risk === "CRITICAL"
                      ? "bg-rose-500/10 text-rose-400"
                      : "bg-emerald-500/10 text-emerald-400"
                  }`}>{east.bloom_risk || "—"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[10px] text-[var(--text-secondary)]">Air Temp</span>
                  <span className="text-[11px] font-mono text-[var(--text-primary)]">{east.air_temp_c ?? "—"}°C</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[10px] text-[var(--text-secondary)]">Wind</span>
                  <span className="text-[11px] font-mono text-[var(--text-primary)]">{east.wind_ms ?? "—"} m/s</span>
                </div>
              </div>
            </div>
          </div>
        </GlassCard>

        {/* License Holders */}
        <GlassCard delay={0.21}>
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <Award className="w-4 h-4 text-amber-400" />
            MAB License Holders
            <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 ml-auto">
              Fiskistofa
            </span>
          </h3>
          {licenses.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-[11px]">
                <thead>
                  <tr className="text-[var(--text-secondary)] border-b border-white/[0.06]">
                    <th className="text-left py-1.5 font-medium">Company</th>
                    <th className="text-left py-1.5 font-medium">Location</th>
                    <th className="text-left py-1.5 font-medium">Region</th>
                    <th className="text-right py-1.5 font-medium">MAB (t)</th>
                  </tr>
                </thead>
                <tbody>
                  {licenses.map((l: any, i: number) => (
                    <tr key={i} className="border-b border-white/[0.03] hover:bg-white/[0.02]">
                      <td className="py-1.5 text-[var(--text-primary)] font-medium">{l.company}</td>
                      <td className="py-1.5 text-[var(--text-secondary)]">{l.location}</td>
                      <td className="py-1.5">
                        <span className={l.region === "Westfjords" ? "text-ocean-400" : "text-violet-400"}>
                          {l.region}
                        </span>
                      </td>
                      <td className="text-right py-1.5 tabular-nums font-semibold text-ocean-400">
                        {l.mab_tonnes?.toLocaleString() || "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-xs text-[var(--text-secondary)] py-4 text-center opacity-60">
              Loading Fiskistofa license data...
            </p>
          )}
        </GlassCard>
      </div>

      {/* Production History + Exports */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <GlassCard delay={0.24}>
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-emerald-400" />
            Production History
            {growthPct && (
              <span className={`text-[9px] px-1.5 py-0.5 rounded-full ml-auto ${
                parseFloat(growthPct) > 0
                  ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                  : "bg-rose-500/10 text-rose-400 border border-rose-500/20"
              }`}>
                {parseFloat(growthPct) > 0 ? "+" : ""}{growthPct}% YoY
              </span>
            )}
          </h3>
          {prodHistory.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-[11px]">
                <thead>
                  <tr className="text-[var(--text-secondary)] border-b border-white/[0.06]">
                    <th className="text-left py-1.5 font-medium">Year</th>
                    <th className="text-right py-1.5 font-medium">Salmon (t)</th>
                    <th className="text-right py-1.5 font-medium">Arctic Char (t)</th>
                    <th className="text-right py-1.5 font-medium">Rainbow (t)</th>
                    <th className="text-right py-1.5 font-medium">Total (t)</th>
                  </tr>
                </thead>
                <tbody>
                  {prodHistory.map((p: any) => (
                    <tr key={p.year} className="border-b border-white/[0.03] hover:bg-white/[0.02]">
                      <td className="py-1.5 text-[var(--text-primary)] font-medium">{p.year}</td>
                      <td className="text-right py-1.5 tabular-nums">{p.salmon_tonnes?.toLocaleString() || "—"}</td>
                      <td className="text-right py-1.5 tabular-nums">{p.arctic_char_tonnes?.toLocaleString() || "—"}</td>
                      <td className="text-right py-1.5 tabular-nums">{p.rainbow_trout_tonnes?.toLocaleString() || "—"}</td>
                      <td className="text-right py-1.5 tabular-nums font-semibold text-ocean-400">
                        {p.total_tonnes?.toLocaleString() || "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-xs text-[var(--text-secondary)] py-4 text-center opacity-60">
              Loading Statistics Iceland data...
            </p>
          )}
        </GlassCard>

        {/* Export Data */}
        <GlassCard delay={0.27}>
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <Ship className="w-4 h-4 text-amber-400" />
            Export History
            <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 ml-auto">
              Statistics Iceland
            </span>
          </h3>
          {exportHistory.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-[11px]">
                <thead>
                  <tr className="text-[var(--text-secondary)] border-b border-white/[0.06]">
                    <th className="text-left py-1.5 font-medium">Year</th>
                    <th className="text-right py-1.5 font-medium">Value (ISK M)</th>
                    <th className="text-right py-1.5 font-medium">Weight (t)</th>
                  </tr>
                </thead>
                <tbody>
                  {exportHistory.map((e: any) => (
                    <tr key={e.year} className="border-b border-white/[0.03] hover:bg-white/[0.02]">
                      <td className="py-1.5 text-[var(--text-primary)] font-medium">{e.year}</td>
                      <td className="text-right py-1.5 tabular-nums font-semibold text-amber-400">
                        {e.value_isk_m?.toLocaleString() || "—"}
                      </td>
                      <td className="text-right py-1.5 tabular-nums">
                        {e.weight_t?.toLocaleString() || "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-xs text-[var(--text-secondary)] py-4 text-center opacity-60">
              Loading export data...
            </p>
          )}
        </GlassCard>
      </div>

      {/* Insights */}
      {snapshot?.insights?.length > 0 && (
        <GlassCard delay={0.30} accent="ocean">
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

      {/* Data Sources + Note */}
      <div className="p-3 rounded-xl bg-ocean-500/[0.04] border border-ocean-500/[0.1]">
        <p className="text-[10px] font-semibold text-ocean-400 mb-1">5 Live Data Sources</p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-1 text-[10px] text-[var(--text-secondary)]">
          <p>Statistics Iceland (PxWeb) — production + exports</p>
          <p>CMEMS Arctic — SST + chlorophyll (regional)</p>
          <p>Vedur.is (apis.is) — air temp + wind</p>
          <p>Fiskistofa — MAB licenses (scraped)</p>
          <p>WOAH WAHIS — disease surveillance</p>
        </div>
        {snapshot?.data_note && (
          <p className="text-[9px] text-amber-400/80 mt-2">{snapshot.data_note}</p>
        )}
      </div>

      <p className="text-[9px] text-[var(--text-secondary)] text-center opacity-50">
        Data: Statistics Iceland, Fiskistofa, Vedur.is, CMEMS Arctic, WOAH.
        ~2% of global Atlantic salmon supply. Not financial or regulatory advice.
      </p>
    </div>
  );
}
