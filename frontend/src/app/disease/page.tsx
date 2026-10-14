"use client";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Shield, RefreshCw, AlertTriangle, Activity, Globe2,
  Bug, Syringe, Building2, Thermometer, Download,
} from "lucide-react";
import { exportToCSV } from "@/lib/export";
import { useTranslation } from "@/lib/i18n";
import KPICard from "@/components/KPICard";
import GlassCard from "@/components/GlassCard";
import TrendComparison from "@/components/TrendComparison";
import DataTable, { Column } from "@/components/DataTable";
import { OcButton } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { useApiError } from "@/lib/useApiError";
import ErrorBoundary from "@/components/ErrorBoundary";
import InteractiveChart, { DataPoint } from "@/components/InteractiveChart";
import FreshnessIndicator from "@/components/FreshnessIndicator";
import DataQualityBadge from "@/components/DataQualityBadge";
import dynamic from "next/dynamic";
import type { PADataPoint } from "@/components/RegionalHeatmap";
import type { DiseaseByCompany } from "@/types/api";

const RegionalHeatmap = dynamic(() => import("@/components/RegionalHeatmap"), {
  loading: () => <div className="h-[300px] bg-slate-800/50 rounded-xl animate-pulse flex items-center justify-center"><span className="text-slate-400">Loading heatmap...</span></div>,
});

/* eslint-disable @typescript-eslint/no-explicit-any */

const SEVERITY_STYLES: Record<string, string> = {
  critical: "bg-rose-500/10 text-rose-400 border-rose-500/20",
  high: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  medium: "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
  low: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
};

export default function DiseasePage() {
  const { t } = useTranslation();
  const handleError = useApiError();
  const [alerts, setAlerts] = useState<any>(null);
  const [norway, setNorway] = useState<any>(null);
  const [treatments, setTreatments] = useState<any>(null);
  const [byCompany, setByCompany] = useState<DiseaseByCompany | null>(null);
  const [loading, setLoading] = useState(true);
  const [yoyDisease, setYoyDisease] = useState<any>(null);
  const [fetchedAt, setFetchedAt] = useState<Date | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const [a, n, tr, c] = await Promise.allSettled([
        api.diseaseAlerts(),
        api.diseaseNorway(),
        api.diseaseTreatments(2026),
        api.diseaseByCompany(),
      ]);
      if (a.status === "fulfilled") setAlerts(a.value);
      if (n.status === "fulfilled") setNorway(n.value);
      if (tr.status === "fulfilled") setTreatments(tr.value);
      if (c.status === "fulfilled") setByCompany(c.value);
    } catch (e) { handleError("disease_load")(e); }
    setLoading(false);
    setFetchedAt(new Date());
  };

  useEffect(() => {
    load();
    api.yoyComparison("disease").then(setYoyDisease).catch(handleError("disease_yoy"));
  }, []);

  // Defensive: API returns {active_outbreaks: [...], ...} — extract the array
  // Falls back through every possible key, then to empty array
  const norwayCases: any[] = (() => {
    if (!norway) return [];
    if (Array.isArray(norway)) return norway;
    if (Array.isArray(norway.cases)) return norway.cases;
    if (Array.isArray(norway.active_outbreaks)) return norway.active_outbreaks;
    if (Array.isArray(norway.data)) return norway.data;
    return [];
  })();
  const isaCount = norwayCases.filter((c: any) => c.disease === "ISA" || c.disease_type?.includes("ILA") || c.disease_type?.includes("ISA")).length;
  const pdCount = norwayCases.filter((c: any) => c.disease === "PD" || c.disease_type?.includes("PANKREAS")).length;
  const treatmentReports = treatments?.reports || [];
  const resistanceCount = treatments?.with_resistance_suspicions || 0;
  const companyList = Object.entries(byCompany?.companies ?? {}).map(([name, c]) => ({
    name,
    ...c,
  }));
  const alertList = alerts?.alerts || (Array.isArray(alerts) ? alerts : []);

  return (
    <ErrorBoundary fallbackTitle="Disease Intelligence error">
    <div className="space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] flex items-center gap-3">
            <Shield className="w-6 h-6 text-rose-400" />
            {t("disease.title")}
          </h1>
          <div className="flex items-center gap-2 mt-1">
            <p className="text-sm text-[var(--text-secondary)]">
              {t("disease.source_mattilsynet")} + {t("disease.source_woah")} {"\u2014"}real-time surveillance
            </p>
            <FreshnessIndicator lastUpdated={fetchedAt} />
            <DataQualityBadge source="Mattilsynet + WOAH" quality="live" />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => window.print()}
            className="print:hidden flex items-center gap-1.5 px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:text-ocean-400 bg-white/[0.04] border border-white/[0.08] rounded-lg transition-colors"
            title="Export as PDF"
            aria-label="Export as PDF"
          >
            <Download className="w-3.5 h-3.5" /> PDF
          </button>
          <OcButton variant="ghost" size="sm"
            onClick={() => exportToCSV([...norwayCases, ...alertList], "disease_intelligence")}
            leftIcon={<Download className="w-3.5 h-3.5" />}>Export CSV</OcButton>
          <OcButton variant="secondary" size="sm" onClick={load} loading={loading}
            leftIcon={<RefreshCw className="w-3.5 h-3.5" />}>Refresh</OcButton>
        </div>
      </motion.div>

      {/* KPI Row */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <KPICard
          label={t("disease.active_outbreaks")}
          value={norwayCases.length || alertList.length || "\u2014"}
          delta="All sources"
          deltaType={norwayCases.length > 0 ? "negative" : "positive"}
          icon={AlertTriangle}
          delay={0}
        />
        <KPICard
          label={t("disease.isa_cases")}
          value={isaCount || 0}
          delta="Infectious Salmon Anaemia"
          deltaType={isaCount > 0 ? "negative" : "positive"}
          icon={Bug}
          delay={0.03}
        />
        <KPICard
          label={t("disease.pd_cases")}
          value={pdCount || 0}
          delta="Pancreas Disease (SAV)"
          deltaType={pdCount > 3 ? "negative" : "neutral"}
          icon={Bug}
          delay={0.06}
        />
        <KPICard
          label={t("disease.resistance_suspicions")}
          value={resistanceCount}
          delta={`of ${treatments?.total_reports || 0} reports`}
          deltaType={resistanceCount > 0 ? "negative" : "positive"}
          icon={Syringe}
          delay={0.09}
        />
        <KPICard
          label={t("disease.companies_affected")}
          value={companyList.filter((c) => (c.total || c.isa + c.pd + (c.other || 0)) > 0).length || "\u2014"}
          delta="With active cases"
          deltaType="neutral"
          icon={Building2}
          delay={0.12}
        />
      </div>

      {/* Disease Cases Year-over-Year */}
      {yoyDisease && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <TrendComparison
            metric="disease"
            label="Disease Cases (monthly)"
            unit="cases"
            currentYear={yoyDisease.current_year || []}
            previousYear={yoyDisease.previous_year || []}
            twoYearsAgo={yoyDisease.two_years_ago || []}
            years={yoyDisease.years}
          />
          {yoyDisease.current_year?.length > 1 && (
            <GlassCard>
              <InteractiveChart
                title="Disease Trend (current year)"
                data={(yoyDisease.current_year as any[]).map((v: any, i: number): DataPoint => ({
                  x: i + 1,
                  y: typeof v === "number" ? v : v?.value ?? 0,
                  label: `Month ${i + 1}`,
                }))}
                unit="cases"
                color="#fb7185"
                fillColor="#fb7185"
                height={180}
              />
            </GlassCard>
          )}
        </div>
      )}

      {/* Production Area Disease Overview */}
      <GlassCard delay={0.13}>
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <Activity className="w-4 h-4 text-ocean-400" />
          Norway Production Areas — Disease Status
          <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-ocean-500/10 text-ocean-400 border border-ocean-500/20 ml-auto">
            PA 1&ndash;13 overview
          </span>
        </h3>
        <div className="grid grid-cols-13 gap-1.5 mb-3">
          {Array.from({ length: 13 }, (_, i) => i + 1).map(pa => {
            const cases = norwayCases.filter((c: any) => {
              const cpa = c.production_area ?? c.pa ?? c.zone;
              return cpa === pa || cpa === String(pa);
            });
            const hasISA = cases.some((c: any) => {
              const d = c.disease || c.disease_type || "";
              return d.includes("ISA") || d.includes("ILA");
            });
            const hasPD = cases.some((c: any) => {
              const d = c.disease || c.disease_type || "";
              return d.includes("PD") || d.includes("PANKREAS");
            });
            return (
              <div
                key={pa}
                title={`PA ${pa}: ${hasISA ? "ISA Active" : hasPD ? "PD Active" : "Clear"} (${cases.length} case${cases.length !== 1 ? "s" : ""})`}
                className={`aspect-square rounded-lg flex items-center justify-center text-[10px] font-bold transition-colors
                  ${hasISA
                    ? "bg-rose-500/20 text-rose-400 border border-rose-500/30"
                    : hasPD
                      ? "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                      : "bg-emerald-500/10 text-emerald-400/50 border border-emerald-500/10"
                  }`}
              >
                {pa}
              </div>
            );
          })}
        </div>
        {/* Legend */}
        <div className="flex items-center gap-4 text-[10px] text-[var(--text-secondary)]">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-xs bg-rose-500/60" />
            <span>ISA Active</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-xs bg-amber-500/60" />
            <span>PD Active</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-xs bg-emerald-500/30" />
            <span>Clear</span>
          </div>
          <span className="ml-auto text-[9px] opacity-50">
            Based on {norwayCases.length} active case{norwayCases.length !== 1 ? "s" : ""} from Mattilsynet
          </span>
        </div>
      </GlassCard>

      {/* Regional Disease Heatmap */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <GlassCard delay={0.14}>
          <RegionalHeatmap
            title="Disease Outbreak Density by PA"
            metric="cases"
            data={Array.from({ length: 13 }, (_, i) => {
              const pa = i + 1;
              const cases = norwayCases.filter((c: any) => {
                const cpa = c.production_area ?? c.pa ?? c.zone;
                return cpa === pa || cpa === String(pa);
              });
              const hasISA = cases.some((c: any) => {
                const d = c.disease || c.disease_type || "";
                return d.includes("ISA") || d.includes("ILA");
              });
              const hasPD = cases.some((c: any) => {
                const d = c.disease || c.disease_type || "";
                return d.includes("PD") || d.includes("PANKREAS");
              });
              return {
                pa,
                value: cases.length,
                label: hasISA ? "ISA active" : hasPD ? "PD active" : cases.length > 0 ? "Other disease" : "Clear",
              } as PADataPoint;
            })}
          />
        </GlassCard>

        <div className="lg:col-span-2">
      {/* Global Alerts */}
      <GlassCard delay={0.15} accent="rose">
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <Globe2 className="w-4 h-4 text-rose-400" />
          {t("disease.global_alerts")}
          <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20 ml-auto">
            WOAH + Mattilsynet + Sernapesca
          </span>
        </h3>
        <div className="space-y-1.5 max-h-64 overflow-y-auto">
          {alertList.length > 0 ? alertList.slice(0, 20).map((a: any, i: number) => (
            <div key={i} className="flex items-center gap-3 p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
              <span className={`text-[9px] px-1.5 py-0.5 rounded-full border ${
                SEVERITY_STYLES[a.severity] || SEVERITY_STYLES.medium
              }`}>
                {(a.severity || "info").toUpperCase()}
              </span>
              <span className="text-[11px] text-[var(--text-primary)] flex-1">
                {a.disease || a.type || "Alert"} {"\u2014"}{a.country || a.source || "Global"}
              </span>
              {a.date && (
                <span className="text-[10px] text-[var(--text-secondary)] flex-shrink-0">{a.date}</span>
              )}
            </div>
          )) : (
            <p className="text-xs text-[var(--text-secondary)] py-4 text-center opacity-60">
              {loading ? t("common.loading") : t("common.no_data")}
            </p>
          )}
        </div>
      </GlassCard>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Norway Disease Detail */}
        <GlassCard delay={0.18}>
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <Bug className="w-4 h-4 text-amber-400" />
            {t("disease.norway_detail")}
            <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 ml-auto">
              Mattilsynet
            </span>
          </h3>
          <div className="space-y-1.5 max-h-72 overflow-y-auto">
            {norwayCases.length > 0 ? norwayCases.slice(0, 25).map((c: any, i: number) => {
              const disease = c.disease || c.disease_type || "Unknown";
              const isCritical = disease.includes("ISA") || disease.includes("ILA");
              return (
                <div key={i} className="p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-medium text-[var(--text-primary)]">
                      {c.locality_name || c.locality || `Locality ${c.locality_no || i}`}
                    </span>
                    <span className={`text-[9px] px-1.5 py-0.5 rounded-full border ${
                      isCritical ? SEVERITY_STYLES.critical : SEVERITY_STYLES.high
                    }`}>
                      {disease.replace("PANKREASSYKDOM", "PD").replace("INFEKSIØS_LAKSEANEMI", "ISA").replace("ILA", "ISA")}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 mt-1 text-[10px] text-[var(--text-secondary)]">
                    {c.suspicion_date && <span>Suspected: {c.suspicion_date.split("T")[0]}</span>}
                    {c.diagnosis_date && <span>Diagnosed: {c.diagnosis_date.split("T")[0]}</span>}
                    {c.status && (
                      <span className={c.status === "active" ? "text-rose-400" : "text-emerald-400"}>
                        {c.status}
                      </span>
                    )}
                  </div>
                </div>
              );
            }) : (
              <p className="text-xs text-[var(--text-secondary)] py-4 text-center opacity-60">
                {loading ? t("common.loading") : t("common.no_data")}
              </p>
            )}
          </div>
        </GlassCard>

        {/* Company Disease Exposure */}
        <GlassCard delay={0.21}>
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <Building2 className="w-4 h-4 text-violet-400" />
            {t("disease.company_exposure")}
          </h3>
          <div className="space-y-1.5 max-h-72 overflow-y-auto">
            {companyList.length > 0 ? companyList.map((c, i: number) => {
              const total = c.total || (c.isa || 0) + (c.pd || 0) + (c.other || 0);
              if (total === 0) return null;
              return (
                <div key={i} className="flex items-center justify-between p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                  <span className="text-[11px] font-medium text-[var(--text-primary)]">{c.name}</span>
                  <div className="flex items-center gap-2">
                    {(c.isa || 0) > 0 && (
                      <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20">
                        ISA: {c.isa}
                      </span>
                    )}
                    {(c.pd || 0) > 0 && (
                      <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">
                        PD: {c.pd}
                      </span>
                    )}
                    {(c.other || 0) > 0 && (
                      <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-gray-500/10 text-gray-400 border border-gray-500/20">
                        Other: {c.other}
                      </span>
                    )}
                  </div>
                </div>
              );
            }).filter(Boolean) : (
              <p className="text-xs text-[var(--text-secondary)] py-4 text-center opacity-60">
                {loading ? t("common.loading") : t("common.no_data")}
              </p>
            )}
          </div>
        </GlassCard>
      </div>

      {/* Treatment & Resistance — Interactive DataTable */}
      <GlassCard delay={0.24}>
        <div className="flex items-center gap-2 mb-3">
          <Syringe className="w-4 h-4 text-ocean-400" />
          <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-ocean-500/10 text-ocean-400 border border-ocean-500/20">
            {treatments?.year || 2026} — {treatments?.total_reports || 0} reports
          </span>
        </div>
        <DataTable
          title={t("disease.treatment_resistance")}
          data={treatmentReports}
          searchKeys={["locality_name", "locality_no", "company"]}
          exportFilename="treatment_reports"
          compact
          columns={[
            { key: "locality_name", label: "Locality", render: (v: any, row: any) => v || row.locality_no || "—" },
            { key: "company", label: "Company" },
            { key: "week", label: "Wk", align: "center", width: "50px" },
            {
              key: "lice", label: "AF Lice", align: "right", width: "70px",
              render: (_v: any, row: any) => {
                const af = row.lice?.adult_female;
                return af != null ? (
                  <span className={af > 0.5 ? "text-rose-400" : "text-emerald-400"}>{af.toFixed(2)}</span>
                ) : "—";
              },
            },
            {
              key: "treatments", label: "Treatment", align: "center",
              render: (v: any) => {
                if (!v) return "—";
                return [v.non_medicinal ? "Non-med" : null, v.medicinal ? "Medicinal" : null, v.combination ? "Combo" : null]
                  .filter(Boolean).join(", ") || "—";
              },
            },
            {
              key: "resistance_suspicions", label: "Resistance", align: "center", width: "80px",
              render: (v: any) => v
                ? <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-rose-500/10 text-rose-400">YES</span>
                : <span className="text-[9px] text-[var(--text-secondary)]">—</span>,
            },
          ] as Column[]}
        />
      </GlassCard>

      <p className="text-[9px] text-[var(--text-secondary)] text-center opacity-50">
        {t("disease.source_mattilsynet")} (mattilsynet.no), {t("disease.source_woah")} (wahis.woah.org), Sernapesca (sernapesca.cl).
        Disease data is reported in real-time. Not veterinary or financial advice.
      </p>
    </div>
    </ErrorBoundary>
  );
}
