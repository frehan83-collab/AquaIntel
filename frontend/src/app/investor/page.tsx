"use client";
import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  Briefcase, RefreshCw, TrendingUp, TrendingDown, Shield,
  BarChart3, AlertTriangle, Leaf, Bug, Zap, Globe2, Wheat, Activity,
} from "lucide-react";
import KPICard from "@/components/KPICard";
import GlassCard from "@/components/GlassCard";
import { OcButton } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { useApiError } from "@/lib/useApiError";
import { useTranslation } from "@/lib/i18n";

/* eslint-disable @typescript-eslint/no-explicit-any */

const TICKERS = ["MOWI", "SALM", "LSG", "GSF", "BAKKA"];

export default function InvestorPage() {
  const { t } = useTranslation();
  const handleError = useApiError();
  const [companies, setCompanies] = useState<any[]>([]);
  const [esg, setEsg] = useState<any[]>([]);
  const [equity, setEquity] = useState<any>(null);
  const [regime, setRegime] = useState<any[]>([]);
  const [lice, setLice] = useState<any>(null);
  const [supply, setSupply] = useState<any>(null);
  const [disease, setDisease] = useState<any>(null);
  const [diseaseByCompany, setDiseaseByCompany] = useState<any>({});
  const [anomaly, setAnomaly] = useState<any>(null);
  const [macro, setMacro] = useState<any>(null);
  const [macroNok, setMacroNok] = useState<any>(null);
  const [macroOilInv, setMacroOilInv] = useState<any>(null);
  const [macroSoy, setMacroSoy] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    const [r1, r2, r3, r4, r5, r6, r7, r8, r9, r10] = await Promise.allSettled([
      api.leadersTop30(),
      api.esgScores(),
      api.equityPrices(),
      api.regimeStates(),
      api.liceSummary(),
      api.globalSupply(),
      api.diseaseNorway(),
      api.diseaseByCompany(),
      api.anomalyScores(),
      api.macroSnapshot(),
    ]);
    if (r1.status === "fulfilled") {
      const v: any = r1.value;
      setCompanies(Array.isArray(v) ? v : Array.isArray(v?.data) ? v.data : []);
    }
    if (r2.status === "fulfilled") setEsg(r2.value || []);
    if (r3.status === "fulfilled") setEquity(r3.value);
    if (r4.status === "fulfilled") setRegime(r4.value || []);
    if (r5.status === "fulfilled") setLice(r5.value);
    if (r6.status === "fulfilled") setSupply(r6.value);
    if (r7.status === "fulfilled") setDisease(r7.value);
    if (r8.status === "fulfilled") setDiseaseByCompany(r8.value || {});
    if (r9.status === "fulfilled") setAnomaly(r9.value);
    if (r10.status === "fulfilled") setMacro(r10.value);
    api.macroSeries("nok_usd", 24).then(setMacroNok).catch(handleError("investor_macro_nok"));
    api.macroSeries("brent_crude", 24).then(setMacroOilInv).catch(handleError("investor_macro_oil"));
    api.macroSeries("soybeans", 24).then(setMacroSoy).catch(handleError("investor_macro_soy"));
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  // Filter to public companies only
  const publicCos = companies.filter((c: any) =>
    c.ticker && TICKERS.some(t => c.ticker?.includes(t))
  );

  // Match ESG scores
  const esgMap = new Map(esg.map((e: any) => [e.company_name, e]));
  const prices = equity?.prices_nok || {};

  // Regime risk: count red/yellow PAs
  const redPAs = regime.filter((s: any) => s.current_color === "red").length;
  const yellowPAs = regime.filter((s: any) => s.current_color === "yellow").length;

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] flex items-center gap-3">
            <Briefcase className="w-6 h-6 text-violet-400" />
            {t("nav.investor_intel")}
          </h1>
          <p className="text-sm text-[var(--text-secondary)] mt-1">
            Portfolio exposure, ESG scoring, regulatory risk &mdash; institutional-grade analytics
          </p>
        </div>
        <OcButton variant="secondary" size="sm" onClick={load} loading={loading}
          leftIcon={<RefreshCw className="w-3.5 h-3.5" />}>Refresh</OcButton>
      </motion.div>

      {/* Market KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <KPICard label="Disease Outbreaks"
          value={disease?.active_cases ?? "\u2014"}
          delta={disease?.by_disease ? Object.entries(disease.by_disease).map(([k,v]) => `${v} ${k.split('(')[0].trim()}`).join(", ") : undefined}
          deltaType={(disease?.active_cases || 0) > 5 ? "negative" : "positive"}
          icon={AlertTriangle} delay={0} />
        <KPICard label="Avg Lice (National)"
          value={lice ? `${Number(lice.avg_adult_female_lice).toFixed(3)}` : "\u2014"}
          delta={lice ? `${lice.sites_above_threshold} sites >0.5` : undefined}
          deltaType={lice?.avg_adult_female_lice > 0.3 ? "negative" : "positive"}
          icon={Bug} delay={0} />
        <KPICard label="Regime Risk"
          value={`${redPAs}R / ${yellowPAs}Y`}
          delta={`of ${regime.length} PAs`}
          deltaType={redPAs > 2 ? "negative" : "positive"}
          icon={Shield} delay={0.04} />
        <KPICard label="Global Supply"
          value={supply ? supply.balance.replace("_", " ") : "\u2014"}
          delta={supply ? `Deficit: ${supply.supply_deficit_pct}%` : undefined}
          deltaType={supply?.supply_deficit_pct > 2 ? "negative" : "positive"}
          icon={Globe2} delay={0.08} />
        <KPICard label="Norway Premium"
          value={supply ? `${supply.norway_premium_pct > 0 ? "+" : ""}${supply.norway_premium_pct}%` : "\u2014"}
          delta="vs global benchmark"
          icon={TrendingUp} delay={0.12} />
      </div>

      {/* Risk Intelligence */}
      {(anomaly || macro) && (
        <GlassCard delay={0.13} accent="rose">
          <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
            <Zap className="w-4 h-4 text-rose-400" />
            Risk Intelligence
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Anomaly composite score */}
            {anomaly && (
              <div className="flex flex-col items-center justify-center p-4 rounded-xl bg-white/[0.03] border border-white/[0.06]">
                <span className={`text-3xl font-black font-mono ${
                  (anomaly.composite_score ?? 0) >= 70 ? "text-rose-400" :
                  (anomaly.composite_score ?? 0) >= 50 ? "text-orange-400" :
                  (anomaly.composite_score ?? 0) >= 30 ? "text-amber-400" : "text-emerald-400"
                }`}>
                  {anomaly.composite_score ?? "\u2014"}
                </span>
                <span className={`text-[10px] font-bold mt-1 px-2 py-0.5 rounded-full border ${
                  anomaly.risk_level === "CRITICAL" ? "bg-rose-500/10 text-rose-400 border-rose-500/20" :
                  anomaly.risk_level === "HIGH" ? "bg-orange-500/10 text-orange-400 border-orange-500/20" :
                  anomaly.risk_level === "MEDIUM" ? "bg-amber-500/10 text-amber-400 border-amber-500/20" :
                  "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                }`}>
                  {anomaly.risk_level || "N/A"}
                </span>
                <p className="text-[9px] text-[var(--text-secondary)] mt-2 text-center">Composite Risk Score</p>
              </div>
            )}

            {/* Summary */}
            {anomaly?.summary && (
              <div className="p-4 rounded-xl bg-white/[0.03] border border-white/[0.06] flex items-center">
                <p className="text-[11px] text-[var(--text-secondary)] leading-relaxed">
                  {anomaly.summary}
                </p>
              </div>
            )}

            {/* Macro indicators */}
            <div className="space-y-3">
              {macro?.indices?.feed_pressure && (
                <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06]">
                  <div className="flex justify-between items-center mb-1.5">
                    <span className="text-[10px] text-[var(--text-secondary)] flex items-center gap-1">
                      <Wheat className="w-3 h-3" /> Feed Pressure Index
                    </span>
                    <span className="text-[11px] font-mono font-bold">
                      {Number(macro.indices.feed_pressure.value).toFixed(1)}
                    </span>
                  </div>
                  <div className="w-full h-1.5 rounded-full bg-white/[0.06]">
                    <div
                      className={`h-full rounded-full ${
                        macro.indices.feed_pressure.value > 70 ? "bg-rose-400" :
                        macro.indices.feed_pressure.value > 40 ? "bg-amber-400" : "bg-emerald-400"
                      }`}
                      style={{ width: `${Math.min(100, Math.max(0, macro.indices.feed_pressure.value))}%` }}
                    />
                  </div>
                </div>
              )}
              {macro?.benchmarks?.nok_usd && (
                <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06] flex justify-between items-center">
                  <span className="text-[10px] text-[var(--text-secondary)] flex items-center gap-1">
                    <Activity className="w-3 h-3" /> NOK/USD
                  </span>
                  <span className="text-[11px] font-mono font-bold text-ocean-300">
                    {Number(macro.benchmarks.nok_usd).toFixed(4)}
                  </span>
                </div>
              )}
            </div>
          </div>
        </GlassCard>
      )}

      {/* Public Company Cards */}
      <GlassCard delay={0.15}>
        <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
          <BarChart3 className="w-4 h-4 text-violet-400" />
          Oslo-Listed Salmon Equities
          <span className="text-[10px] text-[var(--text-secondary)] ml-auto">
            {publicCos.length} companies
          </span>
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {publicCos.map((co: any, i: number) => {
            const ticker = co.ticker || "";
            const price = prices[`${ticker}.OL`] || prices[ticker] || prices[ticker.replace(".OL", "")];
            const esgScore = esgMap.get(co.name);
            const isSelected = selected === co.name;

            return (
              <motion.div
                key={co.name}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
                onClick={() => setSelected(isSelected ? null : co.name)}
                className={`p-4 rounded-xl border cursor-pointer transition-all ${
                  isSelected
                    ? "border-violet-500/30 bg-violet-500/[0.06]"
                    : "border-white/[0.06] bg-white/[0.03] hover:bg-white/[0.05]"
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <div>
                    <span className="text-sm font-bold font-mono text-[var(--text-primary)]">{ticker}</span>
                    <p className="text-[10px] text-[var(--text-secondary)]">{co.name}</p>
                  </div>
                  {price && (
                    <span className="text-sm font-bold text-ocean-300">NOK {Number(price).toFixed(0)}</span>
                  )}
                </div>

                {/* Mini metrics grid */}
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div>
                    <p className={`text-xs font-bold ${
                      co.avg_lice > 0.3 ? "text-rose-400" : co.avg_lice > 0.15 ? "text-amber-400" : "text-emerald-400"
                    }`}>{co.avg_lice?.toFixed(3) || "\u2014"}</p>
                    <p className="text-[8px] text-[var(--text-secondary)]">Avg Lice</p>
                  </div>
                  <div>
                    <p className={`text-xs font-bold ${
                      (esgScore?.grade || "").startsWith("A") ? "text-emerald-400" :
                      (esgScore?.grade || "").startsWith("B") ? "text-ocean-400" : "text-amber-400"
                    }`}>{esgScore?.grade || "\u2014"}</p>
                    <p className="text-[8px] text-[var(--text-secondary)]">ESG</p>
                  </div>
                  <div>
                    <p className={`text-xs font-bold ${
                      co.risk_level === "LOW" ? "text-emerald-400" :
                      co.risk_level === "HIGH" ? "text-rose-400" : "text-amber-400"
                    }`}>{co.risk_level || "\u2014"}</p>
                    <p className="text-[8px] text-[var(--text-secondary)]">Risk</p>
                  </div>
                </div>

                {/* Expanded detail */}
                {isSelected && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    className="mt-3 pt-3 border-t border-white/[0.06] space-y-1.5 text-[10px]"
                  >
                    <div className="flex justify-between">
                      <span className="text-[var(--text-secondary)]">Sites</span>
                      <span>{co.n_localities}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[var(--text-secondary)]">Production Areas</span>
                      <span>{co.production_areas?.map((p: number) => `PA${p}`).join(", ")}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[var(--text-secondary)]">Performance Score</span>
                      <span className="font-bold">{co.performance_score?.toFixed(0)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[var(--text-secondary)]">% Above Threshold</span>
                      <span className={co.pct_above_threshold > 20 ? "text-rose-400" : "text-emerald-400"}>
                        {co.pct_above_threshold?.toFixed(1)}%
                      </span>
                    </div>
                    {esgScore && (
                      <>
                        <div className="flex justify-between">
                          <span className="text-[var(--text-secondary)]">ESG Total</span>
                          <span>{esgScore.total}/100</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-[var(--text-secondary)]">E / S / G</span>
                          <span>{esgScore.environmental}/40 &middot; {esgScore.social}/30 &middot; {esgScore.governance}/30</span>
                        </div>
                      </>
                    )}
                    {(() => {
                      const dbc = diseaseByCompany[co.name];
                      const total = dbc?.total ?? 0;
                      const isa = dbc?.ISA ?? 0;
                      const pd = dbc?.PD ?? 0;
                      return (
                        <div className="flex justify-between">
                          <span className="text-[var(--text-secondary)]">Disease Outbreaks</span>
                          <span className={`font-bold ${
                            isa > 0 ? "text-rose-400" : pd > 0 ? "text-amber-400" : "text-emerald-400"
                          }`}>
                            {total === 0 ? "Clear" : `${total} (${isa > 0 ? `${isa} ISA` : ""}${isa > 0 && pd > 0 ? ", " : ""}${pd > 0 ? `${pd} PD` : ""})`}
                          </span>
                        </div>
                      );
                    })()}
                    <div className="flex justify-between">
                      <span className="text-[var(--text-secondary)]">Outlook</span>
                      <span className={`flex items-center gap-1 ${
                        co.outlook_direction === "positive" ? "text-emerald-400" :
                        co.outlook_direction === "negative" ? "text-rose-400" : "text-amber-400"
                      }`}>
                        {co.outlook_direction === "positive" ? <TrendingUp className="w-3 h-3" /> :
                         co.outlook_direction === "negative" ? <TrendingDown className="w-3 h-3" /> : null}
                        {co.outlook_direction}
                      </span>
                    </div>
                  </motion.div>
                )}
              </motion.div>
            );
          })}
        </div>
      </GlassCard>

      {/* Benchmarks */}
      {equity?.benchmarks && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <GlassCard delay={0.2} accent="ocean">
            <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-ocean-400" />
              Market Benchmarks
            </h3>
            <div className="space-y-2">
              {equity.benchmarks.fpi_eur_per_kg && (
                <div className="flex justify-between p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                  <span className="text-[11px] text-[var(--text-secondary)]">Fish Pool Index</span>
                  <span className="text-[11px] font-mono font-bold text-amber-300">
                    &euro;{Number(equity.benchmarks.fpi_eur_per_kg).toFixed(2)}/kg
                  </span>
                </div>
              )}
              {equity.benchmarks.ssb_nok_per_kg && (
                <div className="flex justify-between p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                  <span className="text-[11px] text-[var(--text-secondary)]">SSB Export Spot</span>
                  <span className="text-[11px] font-mono font-bold text-ocean-300">
                    NOK {Number(equity.benchmarks.ssb_nok_per_kg).toFixed(1)}/kg
                  </span>
                </div>
              )}
              {supply?.global_salmon_usd_kg > 0 && (
                <div className="flex justify-between p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                  <span className="text-[11px] text-[var(--text-secondary)]">Global Salmon (FRED)</span>
                  <span className="text-[11px] font-mono font-bold text-violet-300">
                    ${supply.global_salmon_usd_kg}/kg
                  </span>
                </div>
              )}
            </div>
          </GlassCard>

          <GlassCard delay={0.25} accent="emerald">
            <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
              <Leaf className="w-4 h-4 text-emerald-400" />
              ESG Leaders (Public Companies)
            </h3>
            <div className="space-y-2">
              {esg
                .filter((e: any) => e.ticker && TICKERS.some(t => e.ticker?.includes(t)))
                .slice(0, 5)
                .map((e: any) => (
                  <div key={e.company_name} className="flex items-center justify-between p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] font-mono font-bold">{e.ticker}</span>
                      <span className="text-[10px] text-[var(--text-secondary)]">{e.company_name}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${
                        e.grade?.startsWith("A") ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" :
                        e.grade?.startsWith("B") ? "bg-ocean-500/10 text-ocean-400 border-ocean-500/20" :
                        "bg-amber-500/10 text-amber-400 border-amber-500/20"
                      }`}>{e.grade}</span>
                      <span className="text-[10px] font-mono text-[var(--text-secondary)]">{e.total}/100</span>
                    </div>
                  </div>
                ))
              }
            </div>
          </GlassCard>
        </div>
      )}

      {/* Macro Environment */}
      <GlassCard delay={0.4}>
        <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
          <Activity className="w-4 h-4 text-violet-400" />
          Macro Environment
        </h3>
        <div className="grid grid-cols-3 gap-4">
          {[
            { label: "NOK/USD", data: macroNok, prefix: "", suffix: "" },
            { label: "Brent Crude Oil", data: macroOilInv, prefix: "$", suffix: "" },
            { label: "Soybeans", data: macroSoy, prefix: "$", suffix: "/t" },
          ].map(({ label, data, prefix, suffix }) => {
            // Honest rendering: never fabricate a $0.00 quote when the series failed.
            const v = data?.latest_value ?? data?.value ?? data?.data?.[data?.data?.length - 1]?.value;
            return (
              <div key={label} className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06]">
                <div className="text-[10px] text-[var(--text-secondary)] uppercase tracking-wider mb-1">{label}</div>
                <div className="text-lg font-bold text-[var(--text-primary)]">
                  {v != null ? `${prefix}${Number(v).toFixed(2)}${suffix}` : "\u2014"}
                </div>
                <div className="text-[10px] text-[var(--text-secondary)] mt-0.5">
                  {v != null ? "24-month FRED data" : "FRED series unavailable"}
                </div>
              </div>
            );
          })}
        </div>
      </GlassCard>

      <p className="text-[9px] text-[var(--text-secondary)] text-center opacity-50">
        Data: Oslo B&oslash;rs (Yahoo Finance), SSB (CC BY 4.0), BarentsWatch (NLOD 2.0), FRED, Mattilsynet (disease outbreaks).
        ESG scores computed from biological performance data. Not investment advice.
      </p>
    </div>
  );
}
