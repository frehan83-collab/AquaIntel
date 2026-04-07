"use client";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Sigma, AlertTriangle, RefreshCw, ChevronRight,
  ArrowUp, ArrowDown, Minus, Activity, Info,
} from "lucide-react";
import KPICard from "@/components/KPICard";
import GlassCard from "@/components/GlassCard";
import { OcButton } from "@/components/ui/Button";
import ErrorBoundary from "@/components/ErrorBoundary";
import DataTable, { Column } from "@/components/DataTable";
import { api } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";
import { useApiError } from "@/lib/useApiError";

/* eslint-disable @typescript-eslint/no-explicit-any */

const STATUS_STYLES: Record<string, { bg: string; text: string; border: string }> = {
  healthy: { bg: "bg-emerald-500/20", text: "text-emerald-400", border: "border-emerald-500/30" },
  moderate: { bg: "bg-sky-500/20", text: "text-sky-400", border: "border-sky-500/30" },
  warning: { bg: "bg-amber-500/20", text: "text-amber-400", border: "border-amber-500/30" },
  over_quota: { bg: "bg-rose-500/20", text: "text-rose-400", border: "border-rose-500/30" },
};

function statusBadge(status: string, label: string) {
  const s = STATUS_STYLES[status] || STATUS_STYLES.moderate;
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-semibold ${s.bg} ${s.text} border ${s.border}`}>
      {label}
    </span>
  );
}

function utilizationBar(pct: number) {
  const clamped = Math.min(pct, 150);
  const width = Math.min(clamped / 1.5, 100); // scale 0-150% to 0-100% bar width
  let color = "bg-emerald-500";
  if (pct > 100) color = "bg-rose-500";
  else if (pct > 80) color = "bg-amber-500";
  else if (pct > 50) color = "bg-sky-500";

  return (
    <div className="flex items-center gap-2">
      <div className="w-24 h-2.5 bg-white/10 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color} transition-all duration-500`} style={{ width: `${width}%` }} />
      </div>
      <span className="text-xs text-slate-300 w-12 text-right">{pct.toFixed(1)}%</span>
    </div>
  );
}

export default function LiceQuotaPage() {
  const { t } = useTranslation();
  const handleError = useApiError();
  const [national, setNational] = useState<any>(null);
  const [selectedPa, setSelectedPa] = useState<number | null>(null);
  const [paDetail, setPaDetail] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);

  const fetchNational = async () => {
    setLoading(true);
    try {
      const data = await api.liceQuotaNational();
      setNational(data);
    } catch (e) {
      handleError("lice_quota_national")(e);
    } finally {
      setLoading(false);
    }
  };

  const fetchPaDetail = async (pa: number) => {
    setSelectedPa(pa);
    setDetailLoading(true);
    try {
      const data = await api.liceQuotaPA(pa);
      setPaDetail(data);
    } catch (e) {
      handleError("lice_quota_pa_detail")(e);
    } finally {
      setDetailLoading(false);
    }
  };

  useEffect(() => { fetchNational(); }, []);

  const paColumns: Column[] = [
    { key: "production_area", label: "PA", sortable: true },
    { key: "name", label: "Name", sortable: true },
    { key: "region", label: "Region", sortable: true },
    { key: "estimated_emission", label: "Emission", sortable: true,
      render: (v: number) => v.toLocaleString("nb-NO", { maximumFractionDigits: 1 }) },
    { key: "hypothetical_quota", label: "Quota", sortable: true,
      render: (v: number) => v.toLocaleString("nb-NO", { maximumFractionDigits: 0 }) },
    { key: "utilization_pct", label: "Utilization", sortable: true,
      render: (_v: number, row: any) => utilizationBar(row.utilization_pct) },
    { key: "status_label", label: "Status", sortable: true,
      render: (v: string, row: any) => statusBadge(row.status, v) },
    { key: "farms_reporting", label: "Farms", sortable: true },
    { key: "_action", label: "", render: (_v: any, row: any) => (
      <button
        onClick={() => fetchPaDetail(row.production_area)}
        className="text-sky-400 hover:text-sky-300 transition-colors"
        aria-label={`View details for PA ${row.production_area}`}
      >
        <ChevronRight className="w-4 h-4" />
      </button>
    )},
  ];

  const emitterColumns: Column[] = [
    { key: "locality_no", label: "Locality", sortable: true },
    { key: "locality_name", label: "Name", sortable: true },
    { key: "company", label: "Company", sortable: true },
    { key: "avg_lice", label: "Avg Lice/Fish", sortable: true,
      render: (v: number) => v.toFixed(3) },
    { key: "estimated_emission", label: "Emission", sortable: true,
      render: (v: number) => v.toLocaleString("nb-NO", { maximumFractionDigits: 1 }) },
  ];

  return (
    <ErrorBoundary>
      <div className="space-y-6">
        {/* Projected regulation banner */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4 flex items-start gap-3"
        >
          <AlertTriangle className="w-5 h-5 text-amber-400 mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-amber-300 font-semibold text-sm">
              PROJECTED &mdash; Regulation Not Yet Finalized
            </p>
            <p className="text-amber-200/70 text-xs mt-1">
              Norway is transitioning from the traffic light system to tradable lice emission quotas
              per production area (targeted 2026-2028). All quotas and emissions shown here are
              hypothetical estimates based on IMR carrying capacity assessments. Quotas cannot be
              traded across regions. A fee on lice emissions is also under consideration.
            </p>
          </div>
        </motion.div>

        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500/30 to-purple-500/30 flex items-center justify-center">
              <Sigma className="w-5 h-5 text-violet-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold bg-gradient-to-r from-violet-400 to-purple-400 bg-clip-text text-transparent">
                {t("lice_quota.title")}
              </h1>
              <p className="text-slate-400 text-sm">
                Projected emission tracking under the upcoming quota system
              </p>
            </div>
          </div>
          <OcButton onClick={fetchNational} variant="ghost" size="sm">
            <RefreshCw className={`w-4 h-4 mr-1 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </OcButton>
        </div>

        {/* KPI Cards */}
        {national && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <KPICard
              label={t("lice_quota.national_overview")}
              value={national.total_national_emission?.toLocaleString("nb-NO", { maximumFractionDigits: 0 }) || "---"}
              unit="lice-eq"
              icon={Activity}
            />
            <KPICard
              label="National Quota"
              value={national.total_national_quota?.toLocaleString("nb-NO", { maximumFractionDigits: 0 }) || "---"}
              unit="lice-eq"
              icon={Sigma}
            />
            <KPICard
              label={t("lice_quota.pa_utilization")}
              value={`${national.national_utilization_pct ?? "---"}%`}
              delta={national.national_utilization_pct > 80 ? "Approaching limit" : "Within bounds"}
              deltaType={national.national_utilization_pct > 80 ? "negative" : "positive"}
              icon={Activity}
            />
            <KPICard
              label="PAs Over Quota"
              value={national.pas_over_quota ?? 0}
              unit="of 13"
              delta={national.pas_over_quota > 0 ? "Action needed" : "All within quota"}
              deltaType={national.pas_over_quota > 0 ? "negative" : "positive"}
              icon={AlertTriangle}
            />
          </div>
        )}

        {/* PA Emission Table */}
        <GlassCard>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <Sigma className="w-5 h-5 text-violet-400" />
              Production Area Emissions
            </h2>
            <div className="flex items-center gap-1 text-xs text-slate-400">
              <Info className="w-3.5 h-3.5" />
              Click a row for details
            </div>
          </div>
          {national?.production_areas ? (
            <DataTable
              columns={paColumns}
              data={national.production_areas}
              searchKeys={["name", "region", "status_label"]}
            />
          ) : loading ? (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="w-6 h-6 text-violet-400 animate-spin" />
              <span className="ml-2 text-slate-400">Loading emission data...</span>
            </div>
          ) : (
            <div className="text-center py-12 text-slate-400">
              No emission data available. Ensure lice records are loaded.
            </div>
          )}
        </GlassCard>

        {/* PA Detail Panel */}
        {selectedPa && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <GlassCard>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-white">
                  PA {selectedPa} &mdash; {paDetail?.name || "Loading..."}
                </h2>
                <button
                  onClick={() => { setSelectedPa(null); setPaDetail(null); }}
                  className="text-slate-400 hover:text-white text-sm"
                >
                  Close
                </button>
              </div>

              {detailLoading ? (
                <div className="flex items-center justify-center py-8">
                  <RefreshCw className="w-5 h-5 text-violet-400 animate-spin" />
                  <span className="ml-2 text-slate-400">Loading PA details...</span>
                </div>
              ) : paDetail ? (
                <div className="space-y-4">
                  {/* PA Summary */}
                  <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                    <div className="bg-white/5 rounded-lg p-3">
                      <div className="text-xs text-slate-400">Total Emission</div>
                      <div className="text-lg font-bold text-white">
                        {paDetail.total_estimated_emission?.toLocaleString("nb-NO", { maximumFractionDigits: 1 })}
                      </div>
                    </div>
                    <div className="bg-white/5 rounded-lg p-3">
                      <div className="text-xs text-slate-400">Hypothetical Quota</div>
                      <div className="text-lg font-bold text-white">
                        {paDetail.hypothetical_quota?.toLocaleString("nb-NO")}
                      </div>
                    </div>
                    <div className="bg-white/5 rounded-lg p-3">
                      <div className="text-xs text-slate-400">Utilization</div>
                      <div className="text-lg font-bold text-white">
                        {paDetail.utilization_pct?.toFixed(1)}%
                      </div>
                    </div>
                    <div className="bg-white/5 rounded-lg p-3">
                      <div className="text-xs text-slate-400">Farms Reporting</div>
                      <div className="text-lg font-bold text-white">
                        {paDetail.farms_reporting} / {paDetail.total_farms}
                      </div>
                    </div>
                    <div className="bg-white/5 rounded-lg p-3">
                      <div className="text-xs text-slate-400">Water Factor</div>
                      <div className="text-lg font-bold text-white">
                        {paDetail.water_volume_factor}
                      </div>
                    </div>
                  </div>

                  {/* Top Emitters */}
                  {paDetail.top_emitters?.length > 0 && (
                    <div>
                      <h3 className="text-sm font-semibold text-slate-300 mb-2">
                        Top Emitting Farms
                      </h3>
                      <DataTable
                        columns={emitterColumns}
                        data={paDetail.top_emitters}
                        compact
                        searchKeys={["locality_name", "company"]}
                      />
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-center py-8 text-slate-400">
                  No data available for this production area.
                </div>
              )}
            </GlassCard>
          </motion.div>
        )}

        {/* Methodology Note */}
        <GlassCard>
          <h3 className="text-sm font-semibold text-slate-300 mb-2 flex items-center gap-2">
            <Info className="w-4 h-4 text-sky-400" />
            Methodology &amp; Data Sources
          </h3>
          <div className="text-xs text-slate-400 space-y-1">
            <p>
              <strong>Emission model:</strong> lice_emission = avg_lice_per_fish &times; fish_count / water_volume_factor.
              Fish count estimated from biomass (Fiskeridirektoratet MAB allocation, 93.5% utilization) at 4.5 kg average weight.
            </p>
            <p>
              <strong>Quotas:</strong> Hypothetical values based on IMR (Havforskningsinstituttet) carrying capacity assessments
              and NorKyst800 hydrodynamic modeling. NOT official regulatory values.
            </p>
            <p>
              <strong>Water volume factor:</strong> Captures local hydrographic conditions (flushing, currents).
              Higher values indicate more open/flushed areas with lower emission impact per louse.
            </p>
            <p>
              <strong>Sources:</strong> BarentsWatch (lice counts), Fiskeridirektoratet (biomass/MAB),
              IMR (carrying capacity), NorKyst800 (hydrodynamics).
            </p>
          </div>
        </GlassCard>
      </div>
    </ErrorBoundary>
  );
}
