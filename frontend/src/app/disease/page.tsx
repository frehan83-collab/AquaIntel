"use client";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Shield, RefreshCw, AlertTriangle, Activity, Globe2,
  Bug, Syringe, Building2, Download,
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
import type { DiseaseByCompany } from "@/types/api";
import type {
  DiseaseAlertRow,
  DiseaseAlerts,
  DiseaseNorway,
  DiseaseOutbreak,
  DiseaseTreatmentReport,
  DiseaseTreatments,
  YoYComparison,
} from "@/types/api";

const SEVERITY_STYLES: Record<string, string> = {
  critical: "bg-rose-500/10 text-rose-400 border-rose-500/20",
  high: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  medium: "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
  low: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
};

export default function DiseasePage() {
  const { t } = useTranslation();
  const handleError = useApiError();
  const [alerts, setAlerts] = useState<DiseaseAlerts | null>(null);
  const [norway, setNorway] = useState<DiseaseNorway | null>(null);
  const [treatments, setTreatments] = useState<DiseaseTreatments | null>(null);
  const [byCompany, setByCompany] = useState<DiseaseByCompany | null>(null);
  const [loading, setLoading] = useState(true);
  const [yoyDisease, setYoyDisease] = useState<YoYComparison | null>(null);
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

  // Real contract: /api/disease/norway returns {active_outbreaks: [...]} and
  // the disease field carries DISPLAY names ("Infectious Salmon Anaemia
  // (ISA)") — the old exact-match counters ("ISA"/"PD") were always 0.
  const norwayCases: DiseaseOutbreak[] = norway?.active_outbreaks ?? [];
  const isaCount = norwayCases.filter((c) => {
    const d = (c.disease ?? "").toUpperCase();
    return d.includes("ISA") || d.includes("ILA");
  }).length;
  const pdCount = norwayCases.filter((c) => {
    const d = (c.disease ?? "").toUpperCase();
    return d.includes("PD") || d.includes("PANKREAS");
  }).length;
  const treatmentReports: DiseaseTreatmentReport[] = treatments?.reports ?? [];
  const resistanceCount = treatments?.with_resistance_suspicions ?? 0;
  const companyList = Object.entries(byCompany?.companies ?? {}).map(([name, c]) => ({
    name,
    ...c,
  }));
  const alertList: DiseaseAlertRow[] = alerts?.alerts ?? [];

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
            <DataQualityBadge
              source="Mattilsynet + WOAH"
              provenance={norway?.data_provenance ?? alerts?.data_provenance}
            />
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
                data={yoyDisease.current_year.map((v, i: number): DataPoint => ({
                  x: i + 1,
                  y: v.value ?? 0,
                  label: `M${v.week}`,
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

      {/* Disease Breakdown (real by_disease counts) */}
      <GlassCard delay={0.13}>
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <Activity className="w-4 h-4 text-ocean-400" />
          Active Cases by Disease
          <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-ocean-500/10 text-ocean-400 border border-ocean-500/20 ml-auto">
            Mattilsynet classification
          </span>
        </h3>
        {(() => {
          // NOTE: the API does not expose a production-area field per
          // outbreak (only locality), so the old PA 1-13 grid could never
          // colour a cell — it always read "Clear". This breakdown uses the
          // real by_disease counts instead of inventing PA data.
          const byDisease = Object.entries(norway?.by_disease ?? {}).sort(
            ([, a], [, b]) => b - a,
          );
          if (byDisease.length === 0) {
            return (
              <p className="text-xs text-[var(--text-secondary)] py-4 text-center opacity-60">
                {loading ? t("common.loading") : t("common.no_data")}
              </p>
            );
          }
          const maxCount = Math.max(...byDisease.map(([, n]) => n), 1);
          return (
            <div className="space-y-1.5">
              {byDisease.map(([name, count]) => {
                const isISA = name.toUpperCase().includes("ISA") || name.toUpperCase().includes("ILA");
                const isPD = name.toUpperCase().includes("PD") || name.toUpperCase().includes("PANKREAS");
                return (
                  <div key={name} className="flex items-center gap-3">
                    <span className="text-[11px] text-[var(--text-primary)] w-56 flex-shrink-0 truncate">{name}</span>
                    <div className="flex-1 h-3 bg-white/[0.04] rounded overflow-hidden">
                      <div
                        className={`h-full rounded ${isISA ? "bg-rose-500/60" : isPD ? "bg-amber-500/60" : "bg-ocean-500/50"}`}
                        style={{ width: `${(count / maxCount) * 100}%` }}
                      />
                    </div>
                    <span className="text-[11px] font-mono font-semibold text-[var(--text-primary)] w-10 text-right">{count}</span>
                  </div>
                );
              })}
            </div>
          );
        })()}
        <div className="flex items-center gap-4 text-[10px] text-[var(--text-secondary)] mt-3">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-xs bg-rose-500/60" />
            <span>ISA (critical)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-xs bg-amber-500/60" />
            <span>PD (high)</span>
          </div>
          <span className="ml-auto text-[9px] opacity-50">
            Based on {norwayCases.length} active case{norwayCases.length !== 1 ? "s" : ""} from Mattilsynet
          </span>
        </div>
      </GlassCard>

      {/* Regional Disease Heatmap */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <GlassCard delay={0.14}>
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <Activity className="w-4 h-4 text-ocean-400" />
            PA-level Disease Density
            <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 ml-auto">
              Unavailable
            </span>
          </h3>
          <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
            The Mattilsynet outbreak feed identifies cases per <em>locality</em> only — it
            exposes no production-area field, so a PA 1&ndash;13 density map cannot be drawn
            from this source (the previous grid could never colour a cell and always read
            &ldquo;Clear&rdquo;). Use the &ldquo;Active Cases by Disease&rdquo; breakdown above and the
            per-locality list below instead.
          </p>
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
          {alertList.length > 0 ? alertList.slice(0, 20).map((a, i: number) => (
            <div key={i} className="flex items-center gap-3 p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
              <span className={`text-[9px] px-1.5 py-0.5 rounded-full border ${
                SEVERITY_STYLES[a.severity ?? "medium"] || SEVERITY_STYLES.medium
              }`}>
                {(a.severity || "info").toUpperCase()}
              </span>
              <span className="text-[11px] text-[var(--text-primary)] flex-1">
                {a.disease || "Alert"} {"\u2014"}{a.country || a.source || "Global"}
              </span>
              {a.report_date && (
                <span className="text-[10px] text-[var(--text-secondary)] flex-shrink-0">{a.report_date}</span>
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
            {norwayCases.length > 0 ? norwayCases.slice(0, 25).map((c, i: number) => {
              const disease = c.disease || "Unknown";
              const isCritical = disease.toUpperCase().includes("ISA") || disease.toUpperCase().includes("ILA");
              return (
                <div key={i} className="p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-medium text-[var(--text-primary)]">
                      {c.locality_name || `Locality ${c.locality_no ?? i}`}
                    </span>
                    <span className={`text-[9px] px-1.5 py-0.5 rounded-full border ${
                      isCritical ? SEVERITY_STYLES.critical : SEVERITY_STYLES.high
                    }`}>
                      {disease}
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
            { key: "locality_name", label: "Locality", render: (v, row) => v || row.locality_no || "\u2014" },
            { key: "company", label: "Company" },
            { key: "week", label: "Wk", align: "center", width: "50px" },
            {
              key: "lice", label: "AF Lice", align: "right", width: "70px",
              render: (_v, row) => {
                const af = row.lice?.adult_female;
                return af != null ? (
                  <span className={af > 0.5 ? "text-rose-400" : "text-emerald-400"}>{af.toFixed(2)}</span>
                ) : "\u2014";
              },
            },
            {
              key: "treatments", label: "Treatment", align: "center",
              render: (v: DiseaseTreatmentReport["treatments"]) => {
                if (!v) return "\u2014";
                return [v.non_medicinal ? "Non-med" : null, v.medicinal ? "Medicinal" : null, v.combination ? "Combo" : null]
                  .filter(Boolean).join(", ") || "\u2014";
              },
            },
            {
              key: "resistance_suspicions", label: "Resistance", align: "center", width: "80px",
              render: (v: number | undefined) => v
                ? <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-rose-500/10 text-rose-400">YES</span>
                : <span className="text-[9px] text-[var(--text-secondary)]">\u2014</span>,
            },
          ] as Column<DiseaseTreatmentReport>[]}
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
