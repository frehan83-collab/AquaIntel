"use client";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { AlertTriangle, ShieldCheck, ShieldAlert, Shield, Syringe, MapPin, Search, Loader2, Brain, Network, Waves, Anchor } from "lucide-react";
import KPICard from "@/components/KPICard";
import GlassCard from "@/components/GlassCard";
import TrendComparison from "@/components/TrendComparison";
import { OcButton } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";
import { useApiError } from "@/lib/useApiError";

/* eslint-disable @typescript-eslint/no-explicit-any */

export default function FarmerPage() {
  const { t } = useTranslation();
  const handleError = useApiError();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [localityNo, setLocalityNo] = useState(10469);
  const [gnnPred, setGnnPred] = useState<any>(null);
  const [farmGraphData, setFarmGraphData] = useState<any>(null);
  const [oceanForecast, setOceanForecast] = useState<any>(null);
  const [selectedPa, setSelectedPa] = useState(3);
  const [oceanStatus, setOceanStatus] = useState<any>(null);
  const [yoyLice, setYoyLice] = useState<any>(null);

  const fetchData = async (loc: number) => {
    setLoading(true);
    try {
      const [advisory, gnn, graph] = await Promise.all([
        api.farmerAdvisory(loc),
        api.gnnPredict(loc).catch(() => null),
        api.farmGraphFarm(loc).catch(() => null),
      ]);
      setData(advisory);
      setGnnPred(gnn);
      setFarmGraphData(graph);
      // Fetch ocean forecast (best-effort, PA derived from locality or selected PA)
      try {
        const ocean = await api.oceanForecastPa(selectedPa);
        setOceanForecast(ocean);
      } catch { /* optional */ }
      // Fetch ocean currents status (best-effort)
      api.oceanCurrentsStatus().then(setOceanStatus).catch(handleError("farmer_ocean_currents_status"));
      // Fetch lice YoY for selected PA
      api.yoyComparison("lice", selectedPa).then(setYoyLice).catch(handleError("farmer_yoy_lice_comparison"));
    } catch {
      setData(null);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchData(localityNo);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [localityNo, selectedPa]);

  const riskCounts = data?.risk_distribution || { critical: 0, high: 0, moderate: 0, low: 0 };
  const treatments = data?.treatments || [];
  const farm = data?.farm_detail || null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between"
      >
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] tracking-tight">
            {t("nav.farm_advisory")}
          </h1>
          <p className="text-sm text-[var(--text-secondary)] mt-1">
            Per-locality risk assessment and treatment recommendations
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs text-[var(--text-secondary)]">Locality:</label>
          <input
            type="number"
            value={localityNo}
            onChange={(e) => setLocalityNo(Number(e.target.value))}
            onKeyDown={(e) => e.key === "Enter" && fetchData(localityNo)}
            className="w-24 px-3 py-2 rounded-xl bg-white/[0.04] backdrop-blur border border-white/[0.08] text-sm text-[var(--text-primary)] focus:outline-hidden focus:border-ocean-500/30 transition-colors"
            aria-label="Locality number"
          />
          <label className="text-xs text-[var(--text-secondary)]">PA:</label>
          <select
            value={selectedPa}
            onChange={(e) => setSelectedPa(Number(e.target.value))}
            className="w-16 px-2 py-2 rounded-xl bg-white/[0.04] backdrop-blur border border-white/[0.08] text-sm text-[var(--text-primary)] focus:outline-hidden focus:border-ocean-500/30 transition-colors"
            aria-label="Production Area"
          >
            {Array.from({ length: 13 }, (_, i) => i + 1).map((pa) => (
              <option key={pa} value={pa} className="bg-[#1a1a2e] text-[var(--text-primary)]">
                {pa}
              </option>
            ))}
          </select>
          <OcButton
            variant="accent"
            size="sm"
            onClick={() => fetchData(localityNo)}
            leftIcon={<Search className="w-3.5 h-3.5" />}
            role_accent="farmer"
          >
            Load
          </OcButton>
        </div>
      </motion.div>

      {loading && (
        <GlassCard delay={0}>
          <div className="flex flex-col items-center justify-center py-16">
            <Loader2 className="w-8 h-8 text-ocean-500/60 animate-spin mb-3" />
            <p className="text-sm text-[var(--text-secondary)]">Loading advisory data...</p>
          </div>
        </GlassCard>
      )}

      {!loading && (
        <>
          {/* Risk Distribution KPIs */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <KPICard
              label="Critical"
              value={riskCounts.critical}
              delta="Immediate action"
              deltaType={riskCounts.critical > 0 ? "negative" : "positive"}
              icon={AlertTriangle}
              delay={0.05}
            />
            <KPICard
              label="High Risk"
              value={riskCounts.high}
              delta="Monitor closely"
              deltaType={riskCounts.high > 0 ? "negative" : "neutral"}
              icon={ShieldAlert}
              delay={0.1}
            />
            <KPICard
              label="Moderate"
              value={riskCounts.moderate}
              delta="Standard watch"
              deltaType="neutral"
              icon={Shield}
              delay={0.15}
            />
            <KPICard
              label="Low Risk"
              value={riskCounts.low}
              delta="All clear"
              deltaType="positive"
              icon={ShieldCheck}
              delay={0.2}
            />
          </div>

          {/* Lice Year-over-Year for Selected PA */}
          {yoyLice && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <TrendComparison
                metric="lice"
                label={`PA-${selectedPa} Lice YoY`}
                unit="lice/fish"
                currentYear={yoyLice.current_year || []}
                previousYear={yoyLice.previous_year || []}
                twoYearsAgo={yoyLice.two_years_ago || []}
                years={yoyLice.years}
              />
            </div>
          )}

          {/* Treatments Table */}
          <GlassCard delay={0.25} accent="amber">
            <div className="flex items-center gap-2 mb-4">
              <div className="w-7 h-7 rounded-lg bg-amber-500/[0.08] flex items-center justify-center">
                <Syringe className="w-3.5 h-3.5 text-amber-400" />
              </div>
              <h3 className="text-sm font-semibold text-[var(--text-primary)]">
                Treatment Recommendations
              </h3>
            </div>
            {treatments.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-white/[0.06]">
                      <th className="text-left py-2.5 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Locality</th>
                      <th className="text-left py-2.5 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Method</th>
                      <th className="text-left py-2.5 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Urgency</th>
                      <th className="text-left py-2.5 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Est. Cost (NOK)</th>
                      <th className="text-left py-2.5 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Notes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {treatments.map((t: any, i: number) => (
                      <motion.tr
                        key={i}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: 0.3 + i * 0.04 }}
                        className="border-b border-white/[0.04] hover:bg-white/[0.02] transition-colors"
                      >
                        <td className="py-3 px-3 font-semibold">{t.locality || "—"}</td>
                        <td className="py-3 px-3">{t.method || "—"}</td>
                        <td className="py-3 px-3">
                          <span className={`inline-flex px-2.5 py-1 rounded-lg text-[11px] font-semibold ${
                            t.urgency === "critical"
                              ? "bg-rose-500/10 text-rose-400 border border-rose-500/15"
                              : t.urgency === "high"
                              ? "bg-amber-500/10 text-amber-400 border border-amber-500/15"
                              : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/15"
                          }`}>
                            {t.urgency || "normal"}
                          </span>
                        </td>
                        <td className="py-3 px-3 text-[var(--text-secondary)] font-mono">
                          {t.estimated_cost?.toLocaleString() || "—"}
                        </td>
                        <td className="py-3 px-3 text-xs text-[var(--text-secondary)]">{t.notes || "—"}</td>
                      </motion.tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm text-[var(--text-secondary)] text-center py-8">
                No treatment recommendations at this time.
              </p>
            )}
          </GlassCard>

          {/* GNN + Network Graph Row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* GNN Prediction */}
            <GlassCard delay={0.28} accent="ocean">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-7 h-7 rounded-lg bg-ocean-500/[0.08] flex items-center justify-center">
                  <Brain className="w-3.5 h-3.5 text-ocean-400" />
                </div>
                <h3 className="text-sm font-semibold text-[var(--text-primary)]">GNN Lice Forecast</h3>
                <span className="ml-auto text-[9px] text-ocean-400 px-1.5 py-0.5 rounded bg-ocean-500/10">
                  {gnnPred ? "LIVE" : "UNAVAILABLE"}
                </span>
              </div>
              {gnnPred ? (
                <div className="space-y-2">
                  <div className="flex items-center justify-between p-3 rounded-xl bg-ocean-500/[0.04] border border-ocean-500/[0.1]">
                    <span className="text-xs text-[var(--text-secondary)]">Predicted 4-week lice</span>
                    <span className={`text-lg font-bold font-mono ${
                      (gnnPred.predicted_lice ?? gnnPred.pred_lice ?? 0) > 0.5 ? "text-rose-400" :
                      (gnnPred.predicted_lice ?? gnnPred.pred_lice ?? 0) > 0.2 ? "text-amber-400" : "text-emerald-400"
                    }`}>
                      {(gnnPred.predicted_lice ?? gnnPred.pred_lice ?? 0).toFixed(3)}
                    </span>
                  </div>
                  {gnnPred.outbreak_prob !== undefined && (
                    <div className="flex items-center justify-between p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                      <span className="text-[11px] text-[var(--text-secondary)]">Outbreak probability</span>
                      <span className={`text-[11px] font-bold ${
                        gnnPred.outbreak_prob > 0.6 ? "text-rose-400" : gnnPred.outbreak_prob > 0.3 ? "text-amber-400" : "text-emerald-400"
                      }`}>
                        {(gnnPred.outbreak_prob * 100).toFixed(1)}%
                      </span>
                    </div>
                  )}
                  {gnnPred.confidence && (
                    <p className="text-[10px] text-[var(--text-secondary)] mt-1 opacity-60">
                      Model confidence: {(gnnPred.confidence * 100).toFixed(0)}% · GATv2 temporal graph network
                    </p>
                  )}
                </div>
              ) : (
                <p className="text-xs text-[var(--text-secondary)] py-4 text-center opacity-60">
                  GNN not trained yet — go to Predictions page to train the graph neural network
                </p>
              )}
            </GlassCard>

            {/* Farm Network Graph */}
            <GlassCard delay={0.29} accent="violet">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-7 h-7 rounded-lg bg-violet-500/[0.08] flex items-center justify-center">
                  <Network className="w-3.5 h-3.5 text-violet-400" />
                </div>
                <h3 className="text-sm font-semibold text-[var(--text-primary)]">Network Connectivity</h3>
              </div>
              {farmGraphData ? (
                <div className="space-y-2">
                  {[
                    ["Locality", farmGraphData.locality_no ?? localityNo],
                    ["Company", farmGraphData.company ?? "—"],
                    ["Connected farms", farmGraphData.n_neighbors ?? "—"],
                    ["Cluster ID", farmGraphData.cluster_id ?? "—"],
                    ["Cluster risk", farmGraphData.cluster_risk ?? "—"],
                    ["Upstream farms", farmGraphData.n_upstream ?? "—"],
                    ["Cascade risk score", farmGraphData.cascade_risk?.toFixed(2) ?? "—"],
                  ].map(([label, val]) => (
                    <div key={label as string} className="flex items-center justify-between py-1 border-b border-white/[0.04] last:border-0">
                      <span className="text-[11px] text-[var(--text-secondary)]">{label}</span>
                      <span className="text-[11px] font-mono text-[var(--text-primary)]">{val}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-[var(--text-secondary)] py-4 text-center opacity-60">
                  Farm graph not built yet — run the intelligence agent to generate network data
                </p>
              )}
            </GlassCard>
          </div>

          {/* Ocean Forecast */}
          {oceanForecast && (
            <GlassCard delay={0.31} accent="ocean">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-7 h-7 rounded-lg bg-ocean-500/[0.08] flex items-center justify-center">
                  <Waves className="w-3.5 h-3.5 text-ocean-400" />
                </div>
                <h3 className="text-sm font-semibold text-[var(--text-primary)]">Ocean Forecast</h3>
                <span className="ml-auto text-[9px] text-ocean-400 px-1.5 py-0.5 rounded bg-ocean-500/10">
                  MET.no
                </span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {oceanForecast.sst_current != null && (
                  <div className="p-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06] text-center">
                    <p className="text-lg font-bold text-ocean-400 tabular-nums">{oceanForecast.sst_current}°C</p>
                    <p className="text-[9px] text-[var(--text-secondary)]">Current SST</p>
                  </div>
                )}
                {oceanForecast.sst_forecast != null && (
                  <div className="p-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06] text-center">
                    <p className="text-lg font-bold text-amber-400 tabular-nums">{oceanForecast.sst_forecast}°C</p>
                    <p className="text-[9px] text-[var(--text-secondary)]">Forecast SST</p>
                  </div>
                )}
                {oceanForecast.current_speed != null && (
                  <div className="p-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06] text-center">
                    <p className="text-lg font-bold text-violet-400 tabular-nums">{oceanForecast.current_speed} m/s</p>
                    <p className="text-[9px] text-[var(--text-secondary)]">Current Speed</p>
                  </div>
                )}
                {oceanForecast.wave_height != null && (
                  <div className="p-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06] text-center">
                    <p className="text-lg font-bold text-emerald-400 tabular-nums">{oceanForecast.wave_height} m</p>
                    <p className="text-[9px] text-[var(--text-secondary)]">Wave Height</p>
                  </div>
                )}
              </div>
              {oceanForecast.forecast_hours && Array.isArray(oceanForecast.forecast_hours) && (
                <div className="mt-3 space-y-1 max-h-32 overflow-y-auto">
                  {oceanForecast.forecast_hours.slice(0, 6).map((h: any, i: number) => (
                    <div key={i} className="flex items-center justify-between text-[10px] p-1.5 rounded bg-white/[0.02]">
                      <span className="text-[var(--text-secondary)]">{h.time || `+${(i + 1) * 6}h`}</span>
                      <span className="text-ocean-400 tabular-nums">{h.sst ?? "—"}°C</span>
                      {h.wind_speed != null && <span className="text-[var(--text-secondary)]">{h.wind_speed} m/s</span>}
                    </div>
                  ))}
                </div>
              )}
            </GlassCard>
          )}

          {/* Ocean Currents Status */}
          {oceanStatus && (
            <GlassCard delay={0.33} accent="violet">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-7 h-7 rounded-lg bg-violet-500/[0.08] flex items-center justify-center">
                  <Anchor className="w-3.5 h-3.5 text-violet-400" />
                </div>
                <h3 className="text-sm font-semibold text-[var(--text-primary)]">Ocean Currents Status</h3>
                <span className="ml-auto text-[9px] text-violet-400 px-1.5 py-0.5 rounded bg-violet-500/10">
                  {oceanStatus.source || "CMEMS"}
                </span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {oceanStatus.speed != null && (
                  <div className="p-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06] text-center">
                    <p className="text-lg font-bold text-violet-400 tabular-nums">{oceanStatus.speed} m/s</p>
                    <p className="text-[9px] text-[var(--text-secondary)]">Current Speed</p>
                  </div>
                )}
                {oceanStatus.direction != null && (
                  <div className="p-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06] text-center">
                    <p className="text-lg font-bold text-ocean-400 tabular-nums">{oceanStatus.direction}&deg;</p>
                    <p className="text-[9px] text-[var(--text-secondary)]">Direction</p>
                  </div>
                )}
                {oceanStatus.temperature != null && (
                  <div className="p-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06] text-center">
                    <p className="text-lg font-bold text-amber-400 tabular-nums">{oceanStatus.temperature}&deg;C</p>
                    <p className="text-[9px] text-[var(--text-secondary)]">Water Temp</p>
                  </div>
                )}
                {oceanStatus.salinity != null && (
                  <div className="p-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06] text-center">
                    <p className="text-lg font-bold text-emerald-400 tabular-nums">{oceanStatus.salinity} PSU</p>
                    <p className="text-[9px] text-[var(--text-secondary)]">Salinity</p>
                  </div>
                )}
              </div>
              {oceanStatus.status && (
                <p className="text-[10px] text-[var(--text-secondary)] mt-2 opacity-60">
                  Status: {oceanStatus.status}
                  {oceanStatus.updated && ` \u00B7 Updated: ${oceanStatus.updated}`}
                </p>
              )}
            </GlassCard>
          )}

          {/* Farm Detail Panel */}
          <GlassCard delay={0.32} accent="emerald">
            <div className="flex items-center gap-2 mb-4">
              <div className="w-7 h-7 rounded-lg bg-emerald-500/[0.08] flex items-center justify-center">
                <MapPin className="w-3.5 h-3.5 text-emerald-400" />
              </div>
              <h3 className="text-sm font-semibold text-[var(--text-primary)]">
                Farm Detail
              </h3>
            </div>
            {farm ? (
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                {Object.entries(farm).map(([key, value]) => (
                  <div key={key} className="p-3.5 rounded-xl bg-white/[0.03] border border-white/[0.06]">
                    <span className="text-[10px] text-[var(--text-secondary)] uppercase tracking-wider">
                      {key.replace(/_/g, " ")}
                    </span>
                    <p className="text-sm font-medium text-[var(--text-primary)] mt-1.5">
                      {String(value) || "—"}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-[var(--text-secondary)] text-center py-8">
                No farm detail available for locality {localityNo}.
              </p>
            )}
          </GlassCard>
        </>
      )}
    </div>
  );
}
