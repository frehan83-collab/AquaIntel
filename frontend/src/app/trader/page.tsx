"use client";
import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  TrendingUp, TrendingDown, BarChart3, AlertTriangle,
  RefreshCw, Zap, Activity, Newspaper, LineChart, Save, Trash2, FolderOpen,
} from "lucide-react";
import dynamic from "next/dynamic";
import KPICard from "@/components/KPICard";
import GlassCard from "@/components/GlassCard";
const ConfidenceBand = dynamic(() => import("@/components/ConfidenceBand"), { ssr: false, loading: () => <div className="h-48 bg-white/[0.04] rounded-lg animate-pulse" /> });
import { OcButton } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { useApiError } from "@/lib/useApiError";
import ErrorBoundary from "@/components/ErrorBoundary";
import { useTranslation, formatNumber, formatCurrency, formatDate } from "@/lib/i18n";

/* eslint-disable @typescript-eslint/no-explicit-any */

const TABS = ["ISA Outbreak", "Traffic Light", "Feed Shock"] as const;
const TAB_KEYS: Record<Tab, string> = {
  "ISA Outbreak": "trader.isa_outbreak",
  "Traffic Light": "trader.traffic_light_change",
  "Feed Shock": "trader.feed_shock",
};
type Tab = (typeof TABS)[number];

export default function TraderPage() {
  const { t, locale } = useTranslation();
  const handleError = useApiError();
  const [spotPrice, setSpotPrice] = useState<any>(null);
  const [feedIndex, setFeedIndex] = useState<any>(null);
  const [supplyBalance, setSupplyBalance] = useState<any>(null);
  const [sentimentData, setSentimentData] = useState<any>(null);
  const [signals, setSignals] = useState<any[]>([]);
  const [forwardCurve, setForwardCurve] = useState<any>(null);
  const [priceOutlook, setPriceOutlook] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  // Event Impact Simulator state
  const [activeTab, setActiveTab] = useState<Tab>("ISA Outbreak");
  const [isaPA, setIsaPA] = useState(3);
  const [tlPA, setTlPA] = useState(3);
  const [tlColor, setTlColor] = useState("red");
  const [feedPct, setFeedPct] = useState(15);
  const [impactResult, setImpactResult] = useState<any>(null);
  const [modeling, setModeling] = useState(false);
  const [savedScenarios, setSavedScenarios] = useState<any[]>([]);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setLoading(true);
    const [r1, r2, r3, r4, r5, r6, r7] = await Promise.allSettled([
      api.spotPrice(),
      api.feedCostCompositeIndex(),
      api.supplyDemandBalance(),
      api.sentimentSummary(),
      api.signals(),
      api.forwardCurve(12),
      api.priceOutlookMulti().catch(handleError("trader_price_outlook_multi")),
    ]);
    if (r1.status === "fulfilled") setSpotPrice(r1.value);
    if (r2.status === "fulfilled") setFeedIndex(r2.value);
    if (r3.status === "fulfilled") setSupplyBalance(r3.value);
    if (r4.status === "fulfilled") setSentimentData(r4.value);
    if (r5.status === "fulfilled") {
      const sigs = Array.isArray(r5.value) ? r5.value : r5.value?.signals || [];
      setSignals(sigs);
    }
    if (r6.status === "fulfilled") setForwardCurve(r6.value);
    if (r7.status === "fulfilled") setPriceOutlook(r7.value);
    setLoading(false);
  };

  useEffect(() => {
    load();
    api.listScenarios().then(setSavedScenarios).catch(handleError("trader_list_scenarios"));
  }, []);

  const runModel = async () => {
    setModeling(true);
    setImpactResult(null);
    try {
      let result;
      if (activeTab === "ISA Outbreak") {
        result = await api.eventImpactISA(isaPA);
      } else if (activeTab === "Traffic Light") {
        result = await api.eventImpactTrafficLight(tlPA, tlColor);
      } else {
        result = await api.eventImpactFeedShock(feedPct);
      }
      setImpactResult(result);
    } catch {
      setImpactResult({ error: "Model failed" });
    }
    setModeling(false);
  };

  const saveCurrentScenario = async () => {
    if (!impactResult) return;
    setSaving(true);
    const params = activeTab === "ISA Outbreak" ? { pa: isaPA }
      : activeTab === "Traffic Light" ? { pa: tlPA, color: tlColor }
      : { fishmeal_change_pct: feedPct };
    try {
      await api.saveScenario({
        scenario_type: activeTab.toLowerCase().replace(/ /g, "_"),
        scenario_name: `${activeTab} — ${formatDate(new Date(), locale)}`,
        parameters: params,
        results: impactResult,
      });
      const updated = await api.listScenarios();
      setSavedScenarios(updated);
    } catch (e) { handleError("trader_save_scenario")(e); }
    setSaving(false);
  };

  const deleteScenario = async (id: number) => {
    try {
      await api.deleteScenario(id);
      setSavedScenarios((prev) => prev.filter((s) => s.id !== id));
    } catch (e) { handleError("trader_delete_scenario")(e); }
  };

  const sentScore = sentimentData?.avg_sentiment_24h ?? sentimentData?.overall_score ?? 0;
  const sentLabel = sentScore > 0.1 ? "Bullish" : sentScore < -0.1 ? "Bearish" : "Neutral";

  if (loading) {
    return (
      <div className="p-6 space-y-6">
        <div className="h-10 w-64 bg-white/5 animate-pulse rounded-lg" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-28 bg-white/5 animate-pulse rounded-xl" />
          ))}
        </div>
        <div className="h-96 bg-white/5 animate-pulse rounded-xl" />
      </div>
    );
  }

  return (
    <ErrorBoundary fallbackTitle="Trader Intelligence error">
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="p-6 space-y-6"
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <BarChart3 className="w-7 h-7 text-ocean-400" />
            {t("trader.title")}
          </h1>
          <p className="text-sm text-white/50 mt-1">
            Event-to-financial impact models, signals, and sentiment
          </p>
        </div>
        <OcButton variant="ghost" onClick={load}>
          <RefreshCw className="w-4 h-4 mr-2" /> Refresh
        </OcButton>
      </div>

      {/* KPI Strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KPICard
          label="SSB Spot Price"
          value={spotPrice?.price_nok != null ? formatCurrency(spotPrice.price_nok, locale) : "--"}
          delta={spotPrice?.week || "Latest"}
          icon={BarChart3}
        />
        <KPICard
          label="Feed Cost Index"
          value={feedIndex?.composite_index != null ? formatNumber(feedIndex.composite_index, locale, 1) : "--"}
          delta={feedIndex?.alert || "Composite"}
          icon={Activity}
        />
        <KPICard
          label="Supply Balance"
          value={supplyBalance?.balance_label || supplyBalance?.signal || "--"}
          delta={supplyBalance?.total_supply_tonnes != null ? `${formatNumber(supplyBalance.total_supply_tonnes / 1000, locale)}kt` : ""}
          icon={TrendingUp}
        />
        <KPICard
          label="Sentiment Score"
          value={sentLabel}
          delta={`Score: ${sentScore > 0 ? "+" : ""}${formatNumber(sentScore, locale, 2)}`}
          icon={sentScore > 0.1 ? TrendingUp : sentScore < -0.1 ? TrendingDown : Activity}
        />
      </div>

      {/* Event Impact Simulator */}
      <GlassCard>
        <div className="flex items-center gap-2 mb-4">
          <div className="w-8 h-8 rounded-lg bg-orange-500/20 flex items-center justify-center">
            <Zap className="w-5 h-5 text-orange-400" />
          </div>
          <h2 className="text-lg font-semibold text-white">{t("trader.event_simulator")}</h2>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-4">
          {TABS.map((tab) => (
            <button
              key={tab}
              onClick={() => { setActiveTab(tab); setImpactResult(null); }}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === tab
                  ? "bg-ocean-500/30 text-ocean-300 border border-ocean-500/40"
                  : "bg-white/5 text-white/60 hover:bg-white/10 border border-transparent"
              }`}
            >
              {t(TAB_KEYS[tab])}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div className="flex flex-wrap items-end gap-4 mb-4">
          {activeTab === "ISA Outbreak" && (
            <div className="flex items-end gap-3">
              <div>
                <label className="block text-xs text-white/50 mb-1">Production Area</label>
                <select
                  value={isaPA}
                  onChange={(e) => setIsaPA(Number(e.target.value))}
                  className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                >
                  {Array.from({ length: 13 }, (_, i) => i + 1).map((pa) => (
                    <option key={pa} value={pa} className="bg-ocean-900">PA {pa}</option>
                  ))}
                </select>
              </div>
            </div>
          )}

          {activeTab === "Traffic Light" && (
            <div className="flex items-end gap-3">
              <div>
                <label className="block text-xs text-white/50 mb-1">Production Area</label>
                <select
                  value={tlPA}
                  onChange={(e) => setTlPA(Number(e.target.value))}
                  className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                >
                  {Array.from({ length: 13 }, (_, i) => i + 1).map((pa) => (
                    <option key={pa} value={pa} className="bg-ocean-900">PA {pa}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-white/50 mb-1">New Color</label>
                <select
                  value={tlColor}
                  onChange={(e) => setTlColor(e.target.value)}
                  className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                >
                  <option value="green" className="bg-ocean-900">Green (+6% MAB)</option>
                  <option value="yellow" className="bg-ocean-900">Yellow (no change)</option>
                  <option value="red" className="bg-ocean-900">Red (-6% MAB)</option>
                </select>
              </div>
            </div>
          )}

          {activeTab === "Feed Shock" && (
            <div className="flex items-end gap-3">
              <div>
                <label className="block text-xs text-white/50 mb-1">Fishmeal Price Change (%)</label>
                <input
                  type="number"
                  value={feedPct}
                  onChange={(e) => setFeedPct(Number(e.target.value))}
                  className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm w-28"
                  min={-50}
                  max={100}
                />
              </div>
            </div>
          )}

          <OcButton onClick={runModel} disabled={modeling}>
            {modeling ? t("common.loading") : t("trader.simulate")}
          </OcButton>
        </div>

        {/* Impact Results */}
        {impactResult && !impactResult.error && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-3"
          >
            {/* Cascade Narrative + Save */}
            <div className="bg-white/5 rounded-lg p-3 border border-white/10">
              <div className="flex items-start justify-between mb-1">
                <p className="text-xs text-white/40">{t("trader.impact_results")}</p>
                <button
                  onClick={saveCurrentScenario}
                  disabled={saving}
                  className="flex items-center gap-1 px-2 py-1 text-[10px] text-ocean-400 bg-ocean-500/10 border border-ocean-500/20 rounded-md hover:bg-ocean-500/20 transition-colors disabled:opacity-50"
                >
                  <Save className="w-3 h-3" /> {saving ? "Saving..." : "Save Scenario"}
                </button>
              </div>
              <p className="text-sm text-white/80">{impactResult.cascade_narrative}</p>
            </div>

            {/* Severity + Summary */}
            <div className="flex gap-4 text-sm">
              <span className={`px-2 py-1 rounded text-xs font-medium ${
                impactResult.severity === "critical" ? "bg-rose-500/20 text-rose-400" :
                impactResult.severity === "high" ? "bg-orange-500/20 text-orange-400" :
                impactResult.severity === "medium" ? "bg-amber-500/20 text-amber-400" :
                "bg-emerald-500/20 text-emerald-400"
              }`}>
                {impactResult.severity?.toUpperCase()}
              </span>
              {impactResult.price_impact_pct !== undefined && (
                <span className="text-white/60">
                  Price impact: <span className={impactResult.price_impact_pct >= 0 ? "text-emerald-400" : "text-rose-400"}>
                    {impactResult.price_impact_pct >= 0 ? "+" : ""}{formatNumber(impactResult.price_impact_pct, locale, 2)}%
                  </span>
                </span>
              )}
            </div>

            {/* Per-Company Table */}
            {impactResult.company_impacts?.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-white/40 text-xs border-b border-white/10">
                      <th className="text-left py-2 px-2">Ticker</th>
                      <th className="text-right py-2 px-2">Exposure</th>
                      <th className="text-right py-2 px-2">{t("trader.biomass_loss")}</th>
                      <th className="text-right py-2 px-2">{t("trader.revenue_impact")}</th>
                      <th className="text-right py-2 px-2">EBIT Impact</th>
                      <th className="text-right py-2 px-2">EBIT %</th>
                      <th className="text-right py-2 px-2">{t("trader.stock_move")}</th>
                      <th className="text-right py-2 px-2">Stock (NOK)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {impactResult.company_impacts.map((ci: any, idx: number) => (
                      <tr key={idx} className="border-b border-white/5 hover:bg-white/5">
                        <td className="py-2 px-2 font-medium text-white">{ci.ticker}</td>
                        <td className="py-2 px-2 text-right text-white/70">{ci.exposure_pct}%</td>
                        <td className="py-2 px-2 text-right text-white/70">
                          {ci.production_impact_tonnes != null ? `${formatNumber(ci.production_impact_tonnes, locale)}t` : "--"}
                        </td>
                        <td className={`py-2 px-2 text-right ${ci.revenue_impact_mnok < 0 ? "text-rose-400" : "text-emerald-400"}`}>
                          {ci.revenue_impact_mnok != null ? `${ci.revenue_impact_mnok > 0 ? "+" : ""}${formatNumber(ci.revenue_impact_mnok, locale, 1)}` : "\u2014"}
                        </td>
                        <td className={`py-2 px-2 text-right ${ci.ebit_impact_mnok < 0 ? "text-rose-400" : "text-emerald-400"}`}>
                          {ci.ebit_impact_mnok != null ? `${ci.ebit_impact_mnok > 0 ? "+" : ""}${formatNumber(ci.ebit_impact_mnok, locale, 1)}` : "\u2014"}
                        </td>
                        <td className={`py-2 px-2 text-right ${ci.ebit_impact_pct < 0 ? "text-rose-400" : "text-emerald-400"}`}>
                          {ci.ebit_impact_pct != null ? `${ci.ebit_impact_pct > 0 ? "+" : ""}${formatNumber(ci.ebit_impact_pct, locale, 2)}%` : "\u2014"}
                        </td>
                        <td className={`py-2 px-2 text-right font-medium ${ci.expected_stock_move_pct < 0 ? "text-rose-400" : "text-emerald-400"}`}>
                          {ci.expected_stock_move_pct != null ? `${ci.expected_stock_move_pct > 0 ? "+" : ""}${formatNumber(ci.expected_stock_move_pct, locale, 2)}%` : "\u2014"}
                        </td>
                        <td className={`py-2 px-2 text-right ${ci.expected_stock_move_nok < 0 ? "text-rose-400" : "text-emerald-400"}`}>
                          {ci.expected_stock_move_nok != null ? `${ci.expected_stock_move_nok > 0 ? "+" : ""}${formatNumber(ci.expected_stock_move_nok, locale, 1)}` : "\u2014"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Disclaimer */}
            <p className="text-xs text-white/30 italic">
              {impactResult.disclaimer}
            </p>
          </motion.div>
        )}
        {impactResult?.error && (
          <p className="text-rose-400 text-sm">{impactResult.error}</p>
        )}
      </GlassCard>

      {/* Bottom grid: Signals + Sentiment + Forward Curve */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Active Signals */}
        <GlassCard>
          <div className="flex items-center gap-2 mb-4">
            <div className="w-8 h-8 rounded-lg bg-blue-500/20 flex items-center justify-center">
              <BarChart3 className="w-5 h-5 text-blue-400" />
            </div>
            <h2 className="text-lg font-semibold text-white">{t("trader.active_signals")}</h2>
          </div>
          {signals.length === 0 ? (
            <p className="text-white/40 text-sm">{t("common.no_data")}</p>
          ) : (
            <div className="space-y-2 max-h-72 overflow-y-auto">
              {signals.slice(0, 8).map((sig: any, i: number) => (
                <div key={i} className="flex items-center justify-between bg-white/5 rounded-lg p-3">
                  <div className="flex items-center gap-2">
                    <span className={`text-xs font-bold px-2 py-0.5 rounded ${
                      sig.direction === "SHORT" || sig.direction === "short"
                        ? "bg-rose-500/20 text-rose-400"
                        : "bg-emerald-500/20 text-emerald-400"
                    }`}>
                      {sig.direction?.toUpperCase()}
                    </span>
                    <span className="text-white font-medium text-sm">{sig.ticker}</span>
                  </div>
                  <div className="text-right">
                    <div className="text-xs text-white/50">Strength</div>
                    <div className="text-sm text-white font-medium">
                      {typeof sig.strength === "number" ? `${formatNumber(sig.strength * 100, locale)}%` : sig.strength}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </GlassCard>

        {/* Market Sentiment */}
        <GlassCard>
          <div className="flex items-center gap-2 mb-4">
            <div className="w-8 h-8 rounded-lg bg-purple-500/20 flex items-center justify-center">
              <Newspaper className="w-5 h-5 text-purple-400" />
            </div>
            <h2 className="text-lg font-semibold text-white">Market Sentiment</h2>
          </div>
          {sentimentData?.articles_24h > 0 || sentimentData?.articles ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between text-sm">
                <span className="text-white/50">24h Articles</span>
                <span className="text-white font-medium">{sentimentData.articles_24h ?? sentimentData.articles ?? 0}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-white/50">Trend</span>
                <span className={`font-medium ${
                  sentimentData.sentiment_trend === "improving" ? "text-emerald-400" :
                  sentimentData.sentiment_trend === "deteriorating" ? "text-rose-400" :
                  "text-amber-400"
                }`}>
                  {sentimentData.sentiment_trend || "stable"}
                </span>
              </div>
              {sentimentData.high_impact_articles > 0 && (
                <div className="flex items-center gap-2 bg-amber-500/10 rounded-lg p-2">
                  <AlertTriangle className="w-4 h-4 text-amber-400" />
                  <span className="text-xs text-amber-300">
                    {sentimentData.high_impact_articles} high-impact article(s)
                  </span>
                </div>
              )}
              {sentimentData.signals?.slice(0, 3).map((s: any, i: number) => (
                <div key={i} className="bg-white/5 rounded p-2">
                  <div className="flex items-center justify-between">
                    <span className="text-white text-sm font-medium">{s.ticker}</span>
                    <span className={`text-xs px-2 py-0.5 rounded ${
                      s.sentiment === "bullish" || s.sentiment === "very_bullish"
                        ? "bg-emerald-500/20 text-emerald-400"
                        : s.sentiment === "bearish" || s.sentiment === "very_bearish"
                        ? "bg-rose-500/20 text-rose-400"
                        : "bg-white/10 text-white/50"
                    }`}>
                      {s.sentiment}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-8 text-white/30">
              <Activity className="w-8 h-8 mb-2 animate-pulse" />
              <p className="text-sm">Sentiment engine activating...</p>
              <p className="text-xs mt-1">Polling RSS feeds in background</p>
            </div>
          )}
        </GlassCard>

        {/* Forward Curve */}
        <GlassCard>
          <div className="flex items-center gap-2 mb-4">
            <div className="w-8 h-8 rounded-lg bg-cyan-500/20 flex items-center justify-center">
              <LineChart className="w-5 h-5 text-cyan-400" />
            </div>
            <h2 className="text-lg font-semibold text-white">Forward Curve</h2>
          </div>

          {/* Prominent disclaimer */}
          <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-2 mb-3">
            <p className="text-xs text-amber-300 font-medium text-center">
              Synthetic Model &mdash; Not Market Futures
            </p>
          </div>

          {forwardCurve?.curve?.length > 0 ? (
            <div className="space-y-1 max-h-56 overflow-y-auto">
              {forwardCurve.curve.map((pt: any, i: number) => (
                <div key={i} className="flex justify-between text-sm py-1 border-b border-white/5">
                  <span className="text-white/60">{pt.month || pt.label || `M+${i + 1}`}</span>
                  <span className="text-white font-medium">
                    {pt.price_nok != null ? formatCurrency(pt.price_nok, locale) : pt.price != null ? formatCurrency(pt.price, locale) : "--"}
                  </span>
                </div>
              ))}
            </div>
          ) : forwardCurve?.points?.length > 0 ? (
            <div className="space-y-1 max-h-56 overflow-y-auto">
              {forwardCurve.points.map((pt: any, i: number) => (
                <div key={i} className="flex justify-between text-sm py-1 border-b border-white/5">
                  <span className="text-white/60">{pt.month || pt.label || `M+${i + 1}`}</span>
                  <span className="text-white font-medium">
                    {pt.price_nok != null ? formatCurrency(pt.price_nok, locale) : pt.price != null ? formatCurrency(pt.price, locale) : "--"}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-white/40 text-sm">{t("common.no_data")}</p>
          )}

          {/* Confidence Band Visualization */}
          {(() => {
            // Build confidence band data from price outlook (has p80/p95 bands)
            const horizons = priceOutlook?.horizons;
            if (horizons && horizons.length >= 2) {
              const bandData = horizons.map((h: any, i: number) => ({
                x: h.horizon ?? i + 1,
                y: h.predicted ?? h.predicted_price ?? 0,
                lo80: h.lo80,
                hi80: h.hi80,
                lo95: h.lo95,
                hi95: h.hi95,
              }));
              // Prepend current spot if available
              if (priceOutlook?.current_spot_nok) {
                bandData.unshift({
                  x: 0,
                  y: priceOutlook.current_spot_nok,
                  lo80: priceOutlook.current_spot_nok,
                  hi80: priceOutlook.current_spot_nok,
                  lo95: priceOutlook.current_spot_nok,
                  hi95: priceOutlook.current_spot_nok,
                });
              }
              return (
                <div className="mt-3 pt-3 border-t border-white/5">
                  <ConfidenceBand
                    title="Price Forecast with Confidence Bands"
                    unit=" NOK/kg"
                    xLabel="Weeks ahead"
                    data={bandData}
                  />
                </div>
              );
            }
            // Fallback: build from forward curve points (no bands)
            const pts = forwardCurve?.curve || forwardCurve?.points || [];
            if (pts.length >= 2) {
              const curveData = pts.map((pt: any, i: number) => ({
                x: i + 1,
                y: pt.price_nok ?? pt.price ?? 0,
              }));
              return (
                <div className="mt-3 pt-3 border-t border-white/5">
                  <ConfidenceBand
                    title="Forward Curve (no confidence bands available)"
                    unit=" NOK/kg"
                    xLabel="Month"
                    data={curveData}
                  />
                </div>
              );
            }
            return null;
          })()}

          {forwardCurve?.methodology && (
            <p className="text-xs text-white/30 mt-2">{forwardCurve.methodology}</p>
          )}
        </GlassCard>
      </div>

      {/* Saved Scenarios */}
      {savedScenarios.length > 0 && (
        <GlassCard delay={0.4}>
          <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
            <FolderOpen className="w-4 h-4 text-ocean-400" />
            {t("trader.saved_scenarios")} ({savedScenarios.length})
          </h3>
          <div className="space-y-2">
            {savedScenarios.slice(0, 10).map((sc: any) => (
              <div key={sc.id} className="flex items-center justify-between p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                <div className="flex-1 min-w-0">
                  <p className="text-[11px] font-medium text-[var(--text-primary)] truncate">{sc.scenario_name}</p>
                  <p className="text-[9px] text-[var(--text-secondary)]">
                    {sc.scenario_type?.replace(/_/g, " ")} · {sc.created_at ? formatDate(sc.created_at, locale) : ""}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setImpactResult(sc.results)}
                    className="text-[9px] px-2 py-1 text-ocean-400 bg-ocean-500/10 border border-ocean-500/20 rounded hover:bg-ocean-500/20"
                  >
                    Load
                  </button>
                  <button
                    onClick={() => deleteScenario(sc.id)}
                    className="text-[9px] p-1 text-rose-400/50 hover:text-rose-400"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </GlassCard>
      )}
    </motion.div>
    </ErrorBoundary>
  );
}

