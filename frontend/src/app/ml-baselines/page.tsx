"use client";
import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Sparkles, TrendingUp, Thermometer, Bug, Ship, Play } from "lucide-react";
import KPICard from "@/components/KPICard";
import GlassCard from "@/components/GlassCard";
import { OcButton } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";

type Series = "price" | "lice" | "temperature" | "supply";
type Model = "chronos" | "timesfm" | "moirai";

const SERIES_KEYS: Record<Series, string> = {
  price: "ml.price_series",
  lice: "ml.lice_series",
  temperature: "ml.temp_series",
  supply: "ml.supply_series",
};

const SERIES_CONFIG: Record<Series, { label: string; icon: any; unit: string }> = {
  price: { label: "Salmon Price", icon: TrendingUp, unit: "NOK/kg" },
  lice: { label: "Lice Count", icon: Bug, unit: "lice/fish" },
  temperature: { label: "Sea Temperature", icon: Thermometer, unit: "\u00B0C" },
  supply: { label: "Export Volume", icon: Ship, unit: "tonnes" },
};

export default function MLBaselinesPage() {
  const { t } = useTranslation();
  const [series, setSeries] = useState<Series>("price");
  const [model, setModel] = useState<Model>("chronos");
  const [horizon, setHorizon] = useState(4);
  const [localityNo, setLocalityNo] = useState(10469);
  const [forecast, setForecast] = useState<any>(null);
  const [comparison, setComparison] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [comparing, setComparing] = useState(false);

  const MODEL_CONFIG: Record<Model, { label: string; params: string; color: string }> = {
    chronos: { label: "Chronos-2", params: "120M", color: "ocean" },
    timesfm: { label: "TimesFM 2.5", params: "200M", color: "violet" },
    moirai: { label: "MOIRAI-2", params: "30M", color: "emerald" },
  };

  const runForecast = async () => {
    setLoading(true);
    setForecast(null);
    try {
      let result;
      if (model === "chronos") {
        if (series === "price") result = await api.chronosPriceForecast(horizon);
        else if (series === "lice") result = await api.chronosLiceForecast(localityNo, horizon);
        else if (series === "temperature") result = await api.chronosTemperatureForecast(localityNo, horizon);
        else result = await api.chronosSupplyForecast(horizon);
      } else if (model === "timesfm") {
        if (series === "price") result = await api.timesfmPriceForecast(horizon);
        else if (series === "lice") result = await api.timesfmLiceForecast(localityNo, horizon);
        else if (series === "temperature") result = await api.timesfmTemperatureForecast(localityNo, horizon);
        else result = await api.timesfmSupplyForecast(horizon);
      } else {
        if (series === "price") result = await api.moiraiPriceForecast(horizon);
        else if (series === "lice") result = await api.moiraiLiceForecast(localityNo, horizon);
        else result = await api.moiraiSupplyForecast(horizon);
      }
      setForecast(result);
    } catch { /* empty */ }
    setLoading(false);
  };

  const runComparison = async () => {
    setComparing(true);
    setComparison(null);
    try {
      const s = series === "lice" || series === "temperature" ? "price" : series;
      // Use TimesFM comparison endpoint (includes all 3 models)
      const result = await api.timesfmModelComparison(s, horizon);
      setComparison(result);
    } catch { /* empty */ }
    setComparing(false);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">{t("ml.title")}</h1>
          <p className="text-sm text-[var(--text-secondary)] mt-1">
            Chronos-2 vs TimesFM 2.5 vs MOIRAI-2 &mdash; zero-shot time series forecasting
          </p>
        </div>
      </motion.div>

      {/* Controls */}
      <GlassCard delay={0.1} accent="ocean">
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <label className="block text-[10px] text-[var(--text-secondary)] uppercase tracking-wider mb-1">{t("ml.select_series")}</label>
            <div className="flex gap-1">
              {(Object.keys(SERIES_CONFIG) as Series[]).map((s) => {
                const Icon = SERIES_CONFIG[s].icon;
                return (
                  <button
                    key={s}
                    onClick={() => setSeries(s)}
                    className={`flex items-center gap-1 px-2.5 py-1.5 rounded-md text-xs transition-colors ${
                      series === s
                        ? "bg-ocean-500/20 text-ocean-400"
                        : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] bg-white/[0.03]"
                    }`}
                  >
                    <Icon className="w-3 h-3" />
                    {t(SERIES_KEYS[s])}
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <label className="block text-[10px] text-[var(--text-secondary)] uppercase tracking-wider mb-1">Model</label>
            <div className="flex gap-1">
              {(Object.keys(MODEL_CONFIG) as Model[]).map((m) => (
                <button
                  key={m}
                  onClick={() => setModel(m)}
                  className={`flex items-center gap-1 px-2.5 py-1.5 rounded-md text-xs transition-colors ${
                    model === m
                      ? `bg-${MODEL_CONFIG[m].color}-500/20 text-${MODEL_CONFIG[m].color}-400`
                      : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] bg-white/[0.03]"
                  }`}
                >
                  <Sparkles className="w-3 h-3" />
                  {MODEL_CONFIG[m].label}
                  <span className="text-[9px] opacity-60">{MODEL_CONFIG[m].params}</span>
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-[10px] text-[var(--text-secondary)] uppercase tracking-wider mb-1">{t("ml.forecast_horizon")}</label>
            <input
              type="range" min={2} max={12} value={horizon}
              onChange={(e) => setHorizon(parseInt(e.target.value))}
              className="w-32 accent-ocean-400"
            />
            <span className="ml-2 text-xs text-[var(--text-primary)]">{horizon} {t("ml.weeks_ahead")}</span>
          </div>

          {(series === "lice" || series === "temperature") && (
            <div>
              <label className="block text-[10px] text-[var(--text-secondary)] uppercase tracking-wider mb-1">Locality</label>
              <input
                type="number"
                value={localityNo}
                onChange={(e) => setLocalityNo(parseInt(e.target.value) || 10469)}
                className="w-24 bg-white/[0.06] border border-white/[0.1] rounded-md px-2 py-1.5 text-xs text-[var(--text-primary)]"
              />
            </div>
          )}

          <div className="flex gap-2">
            <OcButton onClick={runForecast} loading={loading} leftIcon={<Play className="w-3.5 h-3.5" />}>
              Forecast
            </OcButton>
            <OcButton variant="secondary" onClick={runComparison} loading={comparing} leftIcon={<Sparkles className="w-3.5 h-3.5" />}>
              {t("ml.compare_models")}
            </OcButton>
          </div>
        </div>
      </GlassCard>

      {/* Forecast Result */}
      {forecast && (
        <GlassCard delay={0.2} accent="emerald">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">
              {t(SERIES_KEYS[series])} — {t("ml.median_forecast")}
            </h3>
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-ocean-500/10 text-ocean-400">
              {forecast.model}
            </span>
          </div>

          {forecast.error ? (
            <p className="text-xs text-rose-400">{forecast.error}</p>
          ) : (
            <>
              <div className="grid grid-cols-3 gap-3 mb-4">
                <div className="text-xs">
                  <span className="text-[var(--text-secondary)]">Last Observed</span>
                  <div className="text-lg font-bold text-[var(--text-primary)]">
                    {forecast.last_value?.toFixed(2)} <span className="text-xs font-normal">{SERIES_CONFIG[series].unit}</span>
                  </div>
                </div>
                <div className="text-xs">
                  <span className="text-[var(--text-secondary)]">Context Length</span>
                  <div className="text-lg font-bold text-[var(--text-primary)]">{forecast.context_length}</div>
                </div>
                <div className="text-xs">
                  <span className="text-[var(--text-secondary)]">Horizon</span>
                  <div className="text-lg font-bold text-[var(--text-primary)]">{forecast.horizon} steps</div>
                </div>
              </div>

              {/* SVG Forecast Chart */}
              <div className="w-full h-48 relative">
                <svg viewBox="0 0 600 180" className="w-full h-full">
                  {(() => {
                    const median = forecast.median || [];
                    const lo80 = forecast.lo80 || [];
                    const hi80 = forecast.hi80 || [];
                    if (!median.length) return null;

                    const allVals = [...median, ...lo80, ...hi80];
                    const minV = Math.min(...allVals);
                    const maxV = Math.max(...allVals);
                    const range = maxV - minV || 1;
                    const pad = 20;
                    const w = 560;
                    const h = 140;

                    const x = (i: number) => pad + (i / (median.length - 1 || 1)) * w;
                    const y = (v: number) => pad + h - ((v - minV) / range) * h;

                    const bandPath = lo80.map((v: number, i: number) => `${x(i)},${y(v)}`).join(" ")
                      + " " + [...hi80].reverse().map((v: number, i: number) => `${x(hi80.length - 1 - i)},${y(v)}`).join(" ");

                    const medianPath = median.map((v: number, i: number) => `${i === 0 ? "M" : "L"}${x(i)},${y(v)}`).join(" ");

                    return (
                      <>
                        <polygon points={bandPath} fill="rgba(56,189,248,0.15)" />
                        <path d={medianPath} fill="none" stroke="rgb(56,189,248)" strokeWidth="2" />
                        {median.map((v: number, i: number) => (
                          <circle key={i} cx={x(i)} cy={y(v)} r="3" fill="rgb(56,189,248)" />
                        ))}
                        {/* Y-axis labels */}
                        <text x="2" y={pad + 4} className="text-[9px] fill-[var(--text-secondary)]">{maxV.toFixed(1)}</text>
                        <text x="2" y={pad + h} className="text-[9px] fill-[var(--text-secondary)]">{minV.toFixed(1)}</text>
                      </>
                    );
                  })()}
                </svg>
              </div>

              {/* Table */}
              <div className="space-y-1 mt-2">
                <div className="flex text-[10px] font-medium text-[var(--text-secondary)] uppercase tracking-wider pb-1 border-b border-white/[0.06]">
                  <span className="w-12">Step</span>
                  <span className="flex-1 text-right">{t("ml.median_forecast")}</span>
                  <span className="flex-1 text-right">{t("ml.confidence_band")} Low</span>
                  <span className="flex-1 text-right">{t("ml.confidence_band")} High</span>
                </div>
                {(forecast.median || []).map((v: number, i: number) => (
                  <div key={i} className="flex text-xs py-1 border-b border-white/[0.03]">
                    <span className="w-12 text-[var(--text-secondary)]">+{i + 1}</span>
                    <span className="flex-1 text-right text-[var(--text-primary)] font-medium">{v.toFixed(2)}</span>
                    <span className="flex-1 text-right text-[var(--text-secondary)]">{forecast.lo80?.[i]?.toFixed(2)}</span>
                    <span className="flex-1 text-right text-[var(--text-secondary)]">{forecast.hi80?.[i]?.toFixed(2)}</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </GlassCard>
      )}

      {/* Model Comparison */}
      {comparison && (
        <GlassCard delay={0.3} accent="amber">
          <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3">
            Model Comparison &mdash; {comparison.series} ({comparison.horizon}-step)
          </h3>

          {comparison.error ? (
            <p className="text-xs text-rose-400">{comparison.error}</p>
          ) : (
            <>
              {/* WS-23: accuracy figures come only from the accuracy registry; the
                  comparison shows forecasts, and says why its metrics are withheld */}
              {comparison.metrics_withheld ? (
                <p className="text-[11px] text-amber-400/80">
                  Accuracy metrics withheld: {comparison.metrics_withheld.reason}. See{" "}
                  {comparison.metrics_withheld.registry}.
                </p>
              ) : (
                <p className="text-[11px] text-[var(--text-secondary)]">
                  Accuracy figures are published only through /api/accuracy.
                </p>
              )}

              {/* Actual vs predicted overlay */}
              <div className="mt-4">
                <h4 className="text-xs font-medium text-[var(--text-secondary)] mb-2">Actual vs Predicted</h4>
                <div className="space-y-1">
                  <div className="flex text-[10px] font-medium text-[var(--text-secondary)] uppercase tracking-wider pb-1 border-b border-white/[0.06]">
                    <span className="w-12">Step</span>
                    <span className="flex-1 text-right">Actual</span>
                    {Object.keys(comparison.models || {}).map((name) => (
                      <span key={name} className="flex-1 text-right">{name}</span>
                    ))}
                  </div>
                  {(comparison.actual || []).map((a: number, i: number) => (
                    <div key={i} className="flex text-xs py-1 border-b border-white/[0.03]">
                      <span className="w-12 text-[var(--text-secondary)]">+{i + 1}</span>
                      <span className="flex-1 text-right text-[var(--text-primary)] font-bold">{a.toFixed(2)}</span>
                      {Object.values(comparison.models || {}).map((m: any, j: number) => (
                        <span key={j} className="flex-1 text-right text-[var(--text-secondary)]">
                          {m.median?.[i]?.toFixed(2) ?? "\u2014"}
                        </span>
                      ))}
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </GlassCard>
      )}
    </div>
  );
}
