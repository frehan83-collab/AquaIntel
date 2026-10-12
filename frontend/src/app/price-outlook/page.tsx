"use client";
import { useEffect, useState } from "react";
import {
  TrendingUp, TrendingDown, Minus, DollarSign, BarChart3,
  Target, Shield, AlertTriangle, Activity, Zap,
} from "lucide-react";
import KPICard from "@/components/KPICard";
import GlassCard from "@/components/GlassCard";
import { ChartContainer, ForecastCone } from "@/components/charts";
import InteractiveChart from "@/components/InteractiveChart";
import { OcButton } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { useApiError } from "@/lib/useApiError";
import { useTranslation, formatNumber, formatCurrency } from "@/lib/i18n";

/* eslint-disable @typescript-eslint/no-explicit-any */

export default function PriceOutlookPage() {
  const { t, locale } = useTranslation();
  const handleError = useApiError();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [outlook, setOutlook] = useState<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [multiHorizon, setMultiHorizon] = useState<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [curve, setCurve] = useState<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [hedgerSignals, setHedgerSignals] = useState<any[]>([]);
  const [predHistory, setPredHistory] = useState<any>(null);
  const [priceExplain, setPriceExplain] = useState<any>(null);
  const [horizon, setHorizon] = useState(4);
  const [loading, setLoading] = useState(false);
  const [viewMode, setViewMode] = useState<"simple" | "terminal">("terminal");

  const fetchAll = async () => {
    setLoading(true);
    try {
      const [o, m, c, h] = await Promise.all([
        api.priceOutlook(horizon).catch(handleError("price_outlook")),
        api.priceOutlookMulti().catch(handleError("price_outlook_multi")),
        api.futuresCurve().catch(handleError("futures_curve")),
        api.hedgerSignals().catch(handleError("hedger_signals")),
      ]);
      setOutlook(o);
      setMultiHorizon(m);
      setCurve(c);
      setHedgerSignals(h as any[]);
      api.predictionHistory(horizon, 30).then(setPredHistory).catch(handleError("prediction_history"));
      api.priceOutlookExplain(horizon).then(setPriceExplain).catch(handleError("price_outlook_explain"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchAll(); }, [horizon]);

  const signalBadge = (signal: string) => {
    const map: Record<string, string> = {
      bullish: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
      bearish: "bg-rose-500/10 text-rose-400 border-rose-500/20",
      neutral: "bg-amber-500/10 text-amber-400 border-amber-500/20",
      contango: "bg-violet-500/10 text-violet-400 border-violet-500/20",
      backwardation: "bg-ocean-500/10 text-ocean-400 border-ocean-500/20",
      flat: "bg-white/[0.04] text-[var(--text-secondary)] border-white/[0.08]",
    };
    return map[signal] || map.neutral;
  };

  const directionIcon = (dir: string) => {
    if (dir === "bullish") return <TrendingUp className="w-4 h-4 text-emerald-400" />;
    if (dir === "bearish") return <TrendingDown className="w-4 h-4 text-rose-400" />;
    return <Minus className="w-4 h-4 text-amber-400" />;
  };

  // Build forecast cone data from multi-horizon response
  const coneData = multiHorizon?.horizons?.map((h: { horizon: number; predicted: number; lo80: number; hi80: number; lo95: number; hi95: number }) => ({
    label: `W+${h.horizon}`,
    forecast: h.predicted,
    upper80: h.hi80,
    lower80: h.lo80,
    upper95: h.hi95,
    lower95: h.lo95,
  })) || [];

  // Prepend current spot
  if (multiHorizon?.current_spot_nok && coneData.length > 0) {
    coneData.unshift({
      label: "Now",
      forecast: multiHorizon.current_spot_nok,
      upper80: multiHorizon.current_spot_nok,
      lower80: multiHorizon.current_spot_nok,
      upper95: multiHorizon.current_spot_nok,
      lower95: multiHorizon.current_spot_nok,
    });
  }

  // ── Simple Card View (Farmer/Buyer) ──────────────────────
  if (viewMode === "simple") {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">{t("nav.price_predictions")}</h1>
            <p className="text-sm text-[var(--text-secondary)] mt-1">
              Salmon spot price forecast driven by biological simulations
            </p>
          </div>
          <div className="flex items-center gap-3">
            <OcButton
              variant="ghost"
              size="sm"
              onClick={() => setViewMode("terminal")}
            >
              Detailed View
            </OcButton>
          </div>
        </div>

        {outlook && (
          <GlassCard accent="ocean" className="max-w-xl mx-auto">
            <div className="text-center space-y-4">
              <div className="flex items-center justify-center gap-2 text-sm text-[var(--text-secondary)]">
                <DollarSign className="w-4 h-4" />
                <span>{horizon}-Week Price Outlook</span>
              </div>
              <div className="flex items-center justify-center gap-4">
                {directionIcon(outlook.direction)}
                <span className="text-4xl font-bold tracking-tight">
                  {outlook.predicted_nok != null ? formatNumber(outlook.predicted_nok, locale, 1) : "\u2014"} <span className="text-lg text-[var(--text-secondary)]">NOK/kg</span>
                </span>
              </div>
              <div className="flex items-center justify-center gap-2">
                <span className={`px-3 py-1 rounded-full text-xs font-semibold border ${signalBadge(outlook.direction)}`}>
                  {outlook.signals?.combined || "NEUTRAL"}
                </span>
              </div>
              <div className="text-sm text-[var(--text-secondary)]">
                80% range: {outlook.bands?.p80?.[0] != null ? formatNumber(outlook.bands.p80[0], locale, 1) : "\u2014"} – {outlook.bands?.p80?.[1] != null ? formatNumber(outlook.bands.p80[1], locale, 1) : "\u2014"} NOK/kg
              </div>
              <div className="pt-3 border-t border-white/[0.06] text-xs text-[var(--text-secondary)]">
                <p>{outlook.model?.accuracy_statement}</p>
              </div>
            </div>
          </GlassCard>
        )}

        <p className="text-[10px] text-[var(--text-secondary)] text-center opacity-60">
          {outlook?.disclaimer}
        </p>
      </div>
    );
  }

  // ── Terminal View (Trader/Investor) ──────────────────────
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            {t("nav.price_predictions")}
          </h1>
          <p className="text-sm text-[var(--text-secondary)] mt-1">
            ML ensemble forecasting — biological + market signal fusion
          </p>
        </div>
        <div className="flex items-center gap-3">
          <OcButton
            variant="ghost"
            size="sm"
            onClick={() => setViewMode("simple")}
          >
            Simple View
          </OcButton>
          <select
            value={horizon}
            onChange={(e) => setHorizon(Number(e.target.value))}
            className="bg-white/[0.04] backdrop-blur border border-white/[0.08] rounded-xl px-3 py-2 text-sm focus:outline-hidden focus:border-ocean-500/30 transition-colors"
          >
            {[2, 4, 6, 8, 10, 12, 14, 16, 18, 20].map(h => (
              <option key={h} value={h}>{h} weeks</option>
            ))}
          </select>
          <OcButton
            variant="secondary"
            size="sm"
            loading={loading}
            onClick={fetchAll}
            leftIcon={<Activity className="w-3.5 h-3.5" />}
          >
            Refresh
          </OcButton>
        </div>
      </div>

      {/* KPI Row */}
      {outlook && (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
          <KPICard
            label="Current Spot"
            value={outlook.current_spot_nok != null ? `${formatNumber(outlook.current_spot_nok, locale, 1)} NOK` : "\u2014"}
            icon={DollarSign}
            delay={0}
          />
          <KPICard
            label={`${horizon}w Forecast`}
            value={outlook.predicted_nok != null ? `${formatNumber(outlook.predicted_nok, locale, 1)} NOK` : "\u2014"}
            delta={outlook.signals?.combined}
            deltaType={outlook.direction === "bullish" ? "positive" : outlook.direction === "bearish" ? "negative" : "neutral"}
            icon={Target}
            delay={0.03}
          />
          <KPICard
            label="80% Band"
            value={outlook.bands?.p80 ? `${formatNumber(outlook.bands.p80[0], locale, 1)}-${formatNumber(outlook.bands.p80[1], locale, 1)}` : "\u2014"}
            icon={Shield}
            delay={0.06}
          />
          <KPICard
            label="Confidence"
            value={`${formatNumber((outlook.confidence || 0) * 100, locale)}%`}
            icon={Zap}
            delay={0.09}
          />
          <KPICard
            label="Backtest MAPE"
            value={outlook.model?.mape_backtest != null ? `${formatNumber(outlook.model.mape_backtest, locale, 1)}%` : "\u2014"}
            delta={outlook.model?.mape_backtest != null ? (outlook.model.mape_backtest < 10 ? "Good" : "Moderate") : "No validated backtest"}
            deltaType={outlook.model?.mape_backtest != null && outlook.model.mape_backtest < 10 ? "positive" : "neutral"}
            icon={BarChart3}
            delay={0.12}
          />
        </div>
      )}

      {/* Forecast Cone + Signal Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <ChartContainer
          title="Price Forecast Cone (NOK/kg)"
          subtitle="ML ensemble with 80% and 95% conformal prediction bands"
          className="lg:col-span-2"
          delay={0.1}
          badge={
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-ocean-500/10 text-ocean-400 border border-ocean-500/20">
              {outlook?.model?.version || "ensemble_v1"}
            </span>
          }
          footer={
            <p className="text-[10px] text-[var(--text-secondary)]">
              Inner band: 80% coverage. Outer band: 95% coverage. Based on {outlook?.model?.n_scenarios || 1000} Monte Carlo scenarios.
            </p>
          }
        >
          {coneData.length > 0 ? (
            <ForecastCone
              data={coneData}
              height={280}
              threshold={undefined}
              unit=" NOK"
              color="ocean"
            />
          ) : (
            <div className="h-[280px] flex items-center justify-center text-sm text-[var(--text-secondary)]">
              Loading forecast data...
            </div>
          )}
        </ChartContainer>

        {/* Signal Breakdown */}
        <GlassCard delay={0.15}>
          <h3 className="text-sm font-semibold mb-4">Signal Breakdown</h3>
          {outlook && (
            <div className="space-y-2.5">
              {[
                { label: "Lice Impact", value: outlook.signals?.lice, icon: AlertTriangle },
                { label: "Supply/Biomass", value: outlook.signals?.supply, icon: BarChart3 },
                { label: "Seasonal", value: outlook.signals?.seasonal, icon: Activity },
                { label: "Export Demand", value: outlook.signals?.export, icon: TrendingUp },
                { label: "Futures Curve", value: outlook.signals?.futures, icon: DollarSign },
              ].map(({ label, value, icon: Icon }) => (
                <div
                  key={label}
                  className="flex items-center justify-between p-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06] transition-all hover:bg-white/[0.05]"
                >
                  <div className="flex items-center gap-2">
                    <Icon className="w-3.5 h-3.5 text-[var(--text-secondary)]" />
                    <span className="text-xs text-[var(--text-secondary)]">{label}</span>
                  </div>
                  <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-md border ${signalBadge(value || "neutral")}`}>
                    {(value || "neutral").toUpperCase()}
                  </span>
                </div>
              ))}

              {/* Combined */}
              <div className="mt-3 p-3 rounded-xl bg-ocean-500/[0.04] border border-ocean-500/[0.08]">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold text-[var(--text-primary)]">Combined Signal</span>
                  <span className={`text-sm font-bold ${
                    outlook.signals?.combined?.includes("BULLISH") ? "text-emerald-400" :
                    outlook.signals?.combined?.includes("BEARISH") ? "text-rose-400" :
                    "text-amber-400"
                  }`}>
                    {outlook.signals?.combined}
                  </span>
                </div>
                <p className="text-[11px] text-[var(--text-secondary)] leading-relaxed">
                  {outlook.rationale || "Waiting for signals..."}
                </p>
              </div>
            </div>
          )}
        </GlassCard>
      </div>

      {/* Scenario Distribution + Futures Curve */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Scenario Distribution */}
        {outlook?.scenarios && (
          <GlassCard delay={0.2} accent="violet">
            <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-violet-500" />
              Scenario Distribution ({outlook.model?.n_scenarios} runs)
            </h3>
            <div className="space-y-3">
              {[
                { label: "P10 (downside)", value: outlook.scenarios.p10, color: "text-rose-400" },
                { label: "P25", value: outlook.scenarios.p25, color: "text-amber-400" },
                { label: "P50 (median)", value: outlook.scenarios.p50, color: "text-[var(--text-primary)]" },
                { label: "P75", value: outlook.scenarios.p75, color: "text-emerald-400" },
                { label: "P90 (upside)", value: outlook.scenarios.p90, color: "text-emerald-400" },
              ].map(({ label, value, color }) => (
                <div key={label} className="flex items-center justify-between">
                  <span className="text-xs text-[var(--text-secondary)]">{label}</span>
                  <div className="flex items-center gap-3">
                    <div className="w-24 h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-ocean-600 to-ocean-400"
                        style={{ width: `${Math.min(100, Math.max(5, ((value - (outlook.scenarios.p10 - 5)) / ((outlook.scenarios.p90 + 5) - (outlook.scenarios.p10 - 5))) * 100))}%` }}
                      />
                    </div>
                    <span className={`text-sm font-mono font-semibold tabular-nums ${color}`}>
                      {value != null ? formatNumber(value, locale, 1) : "\u2014"} NOK
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </GlassCard>
        )}

        {/* SSB Price History */}
        {curve?.history && curve.history.length > 0 && (
          <GlassCard delay={0.25} accent="amber">
            <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
              <DollarSign className="w-4 h-4 text-amber-500" />
              SSB Export Price History
              <span className="text-[10px] px-2 py-0.5 rounded-full border bg-emerald-500/10 text-emerald-400 border-emerald-500/20 ml-auto">
                REAL DATA
              </span>
            </h3>

            {/* Interactive price chart */}
            <InteractiveChart
              data={curve.history.slice(-16).map((h: { label: string; price_nok: number; volume_tonnes: number }, i: number) => ({
                x: i,
                y: h.price_nok,
                label: h.label,
              }))}
              title=""
              unit=" NOK/kg"
              height={200}
              color="#f59e0b"
              fillColor="#f59e0b"
            />

            <div className="space-y-2 mt-3">
              <div className="flex items-center justify-between p-2.5 rounded-xl bg-ocean-500/[0.06] border border-ocean-500/[0.1]">
                <span className="text-xs font-semibold text-ocean-400">CURRENT SPOT</span>
                <span className="text-sm font-bold text-[var(--text-primary)]">{curve.spot_nok != null ? formatNumber(curve.spot_nok, locale, 1) : "\u2014"} NOK/kg</span>
              </div>
              {curve.history.slice(-8).map((h: { label: string; price_nok: number; volume_tonnes: number }) => (
                <div key={h.label} className="flex items-center justify-between p-2 rounded-xl bg-white/[0.03] border border-white/[0.06]">
                  <span className="text-xs font-mono text-[var(--text-secondary)]">{h.label}</span>
                  <div className="flex items-center gap-3">
                    <span className="text-[10px] text-[var(--text-secondary)]">{h.volume_tonnes != null ? formatNumber(h.volume_tonnes, locale) : "\u2014"}t</span>
                    <span className="text-sm font-mono font-semibold tabular-nums">{h.price_nok != null ? formatNumber(h.price_nok, locale, 1) : "\u2014"} NOK</span>
                  </div>
                </div>
              ))}
              <p className="text-[10px] text-[var(--text-secondary)] pt-1">
                Source: {curve.source}
              </p>
            </div>
          </GlassCard>
        )}
      </div>

      {/* Multi-Horizon Table */}
      {multiHorizon?.horizons && multiHorizon.horizons.length > 0 && (
        <GlassCard delay={0.28} accent="ocean">
          <h3 className="text-sm font-semibold mb-3 text-[var(--text-primary)] flex items-center gap-2">
            <Activity className="w-4 h-4 text-ocean-400" />
            Forecast Horizon (all modelled points)
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.06]">
                  <th className="text-left py-2 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Horizon</th>
                  <th className="text-left py-2 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Predicted</th>
                  <th className="text-left py-2 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Change</th>
                  <th className="text-left py-2 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">80% CI</th>
                  <th className="text-left py-2 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Direction</th>
                </tr>
              </thead>
              <tbody>
                {multiHorizon.horizons.map((h: any, i: number) => (
                  <tr
                    key={h.horizon || i}
                    className={`border-b border-white/[0.04] hover:bg-white/[0.02] transition-colors ${
                      h.horizon === horizon ? "bg-ocean-500/[0.04]" : ""
                    }`}
                  >
                    <td className="py-2.5 px-3 font-mono text-xs">
                      <span className={h.horizon === horizon ? "text-ocean-400 font-bold" : "text-[var(--text-secondary)]"}>
                        W+{h.horizon}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 font-mono font-semibold text-[var(--text-primary)]">
                      {formatNumber(h.predicted || h.predicted_price || 0, locale, 1)} NOK
                    </td>
                    <td className="py-2.5 px-3">
                      <span className={`text-xs font-semibold ${
                        (h.change_pct || 0) > 0 ? "text-emerald-400" :
                        (h.change_pct || 0) < 0 ? "text-rose-400" : "text-[var(--text-secondary)]"
                      }`}>
                        {(h.change_pct || 0) > 0 ? "+" : ""}{formatNumber(h.change_pct || 0, locale, 1)}%
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-xs text-[var(--text-secondary)] font-mono">
                      {h.lo80 && h.hi80 ? `${formatNumber(h.lo80, locale, 1)} \u2013 ${formatNumber(h.hi80, locale, 1)}` : "\u2014"}
                    </td>
                    <td className="py-2.5 px-3">
                      <span className={`text-[10px] font-medium px-2 py-0.5 rounded-md ${
                        (h.direction || "").includes("up") ? "bg-emerald-500/10 text-emerald-400" :
                        (h.direction || "").includes("down") ? "bg-rose-500/10 text-rose-400" :
                        "bg-white/5 text-[var(--text-secondary)]"
                      }`}>
                        {h.direction || h.combined_signal || "\u2014"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </GlassCard>
      )}

      {/* Hedger Signals */}
      {hedgerSignals.length > 0 && (
        <GlassCard delay={0.3} accent="emerald">
          <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
            <Shield className="w-4 h-4 text-emerald-500" />
            Market Hedger Signals
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.06]">
                  <th className="text-left py-2 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Time</th>
                  <th className="text-left py-2 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Ticker</th>
                  <th className="text-left py-2 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Direction</th>
                  <th className="text-left py-2 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Strength</th>
                  <th className="text-left py-2 px-3 text-[var(--text-secondary)] font-medium text-[11px] uppercase tracking-wider">Rationale</th>
                </tr>
              </thead>
              <tbody>
                {hedgerSignals.slice(0, 8).map((sig, i) => (
                  <tr key={sig.id || i} className="border-b border-white/[0.04] hover:bg-white/[0.02]">
                    <td className="py-2.5 px-3 text-xs font-mono text-[var(--text-secondary)]">
                      {sig.created_at?.slice(0, 16)?.replace("T", " ") || "—"}
                    </td>
                    <td className="py-2.5 px-3 font-semibold">{sig.ticker}</td>
                    <td className="py-2.5 px-3">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-lg text-[11px] font-semibold border ${
                        sig.direction === "SHORT" ? "bg-rose-500/10 text-rose-400 border-rose-500/15" :
                        "bg-emerald-500/10 text-emerald-400 border-emerald-500/15"
                      }`}>
                        {sig.direction}
                      </span>
                    </td>
                    <td className="py-2.5 px-3">
                      <div className="flex items-center gap-2">
                        <div className="w-16 h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
                          <div
                            className="h-full rounded-full bg-gradient-to-r from-ocean-600 to-ocean-400"
                            style={{ width: `${(sig.strength || 0) * 100}%` }}
                          />
                        </div>
                        <span className="text-xs text-[var(--text-secondary)] font-mono">
                          {formatNumber((sig.strength || 0) * 100, locale)}%
                        </span>
                      </div>
                    </td>
                    <td className="py-2.5 px-3 text-xs text-[var(--text-secondary)] max-w-xs truncate">
                      {sig.rationale?.replace("[HEDGER] ", "") || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </GlassCard>
      )}

      {/* Prediction Track Record */}
      {predHistory && (
        <GlassCard delay={0.32} accent="violet">
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-violet-400" />
            Prediction Track Record
            <span className="ml-auto text-[10px] px-2 py-0.5 rounded-full bg-violet-500/10 text-violet-400 border border-violet-500/20">
              Last 30 days
            </span>
          </h3>
          <div className="space-y-1.5">
            {(predHistory.records || predHistory.predictions || predHistory || []).slice(0, 10).map((r: any, i: number) => (
              <div key={i} className="flex items-center justify-between p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                <span className="text-[11px] font-mono text-[var(--text-secondary)]">{r.date || r.week || `Record ${i + 1}`}</span>
                <div className="flex items-center gap-4">
                  <span className="text-[11px] text-[var(--text-secondary)]">
                    Pred: <span className="text-ocean-400 font-semibold">{formatNumber(r.predicted || r.predicted_nok || 0, locale, 1)}</span>
                  </span>
                  <span className="text-[11px] text-[var(--text-secondary)]">
                    Actual: <span className="text-[var(--text-primary)] font-semibold">{formatNumber(r.actual || r.actual_nok || 0, locale, 1)}</span>
                  </span>
                  <span className={`text-[10px] font-mono ${Math.abs(r.error_pct || ((r.predicted || 0) - (r.actual || 0)) / Math.max(r.actual || 1, 1) * 100) < 5 ? "text-emerald-400" : "text-amber-400"}`}>
                    {(r.error_pct || ((r.predicted || 0) - (r.actual || 0)) / Math.max(r.actual || 1, 1) * 100).toFixed(1)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </GlassCard>
      )}

      {/* Price Drivers Explained */}
      {priceExplain && (
        <GlassCard delay={0.34} accent="amber">
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            Price Drivers Explained
          </h3>
          <p className="text-xs text-[var(--text-secondary)] leading-relaxed mb-4">
            {priceExplain.explanation || priceExplain.summary || "Analyzing price drivers..."}
          </p>
          {(priceExplain.factors || priceExplain.drivers || []).length > 0 && (
            <div className="space-y-2">
              {(priceExplain.factors || priceExplain.drivers || []).map((f: any, i: number) => (
                <div key={i} className="flex items-center justify-between p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                  <span className="text-[11px] text-[var(--text-primary)] font-medium">{f.name || f.factor || f.label}</span>
                  <div className="flex items-center gap-3">
                    <div className="w-20 h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-amber-600 to-amber-400"
                        style={{ width: `${Math.min(100, Math.abs(f.weight || f.impact || 0) * 100)}%` }}
                      />
                    </div>
                    <span className={`text-[10px] font-mono font-semibold ${(f.direction || "").includes("up") || (f.impact || 0) > 0 ? "text-emerald-400" : "text-rose-400"}`}>
                      {(f.weight || f.impact || 0) > 0 ? "+" : ""}{formatNumber((f.weight || f.impact || 0) * 100, locale)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </GlassCard>
      )}

      {/* Accuracy + Model Info */}
      {outlook?.model && (
        <GlassCard delay={0.35} accent="none" hover={false}>
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
            <div className="space-y-1">
              <p className="text-xs font-semibold text-[var(--text-primary)]">
                Model Transparency
              </p>
              <p className="text-[11px] text-[var(--text-secondary)] leading-relaxed max-w-2xl">
                {outlook.model.accuracy_statement}
              </p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <span className="text-[10px] px-2 py-1 rounded-lg bg-white/[0.04] text-[var(--text-secondary)] border border-white/[0.06]">
                {outlook.model.version}
              </span>
              <span className="text-[10px] px-2 py-1 rounded-lg bg-white/[0.04] text-[var(--text-secondary)] border border-white/[0.06]">
                {outlook.model.n_scenarios} scenarios
              </span>
            </div>
          </div>
        </GlassCard>
      )}

      {/* Disclaimer */}
      <p className="text-[10px] text-[var(--text-secondary)] text-center opacity-60">
        {outlook?.disclaimer || "Price forecasts are probabilistic and not financial advice. Historical patterns do not guarantee future results."}
      </p>
    </div>
  );
}
