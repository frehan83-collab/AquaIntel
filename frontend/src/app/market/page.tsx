/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { motion } from "framer-motion";
import { DollarSign, RefreshCw, TrendingUp, TrendingDown, BarChart2, Activity } from "lucide-react";
import GlassCard from "@/components/GlassCard";
import KPICard from "@/components/KPICard";
import DataQualityBadge from "@/components/DataQualityBadge";
import { OcButton } from "@/components/ui/Button";
import { api } from "@/lib/api";
import type { FuturesForwardCurve } from "@/types/api";
import { useApiError } from "@/lib/useApiError";
import dynamic from "next/dynamic";
import ErrorBoundary from "@/components/ErrorBoundary";
const InteractiveChart = dynamic(() => import("@/components/InteractiveChart"), { ssr: false, loading: () => <div className="h-48 bg-white/[0.04] rounded-lg animate-pulse" /> });
import FreshnessIndicator from "@/components/FreshnessIndicator";
import TickerStrip from "@/components/TickerStrip";
import { useTranslation, formatNumber, formatCurrency } from "@/lib/i18n";
import { chartPalette, colors } from "@/lib/design-tokens";

// ─── Types ────────────────────────────────────────────────────────────────────

interface FishPoolPoint { week: string; price: number; change_pct: number }
interface EquityPrices { prices: Record<string, number>; changes: Record<string, number>; timestamps: Record<string, string> }
interface SsbPoint { week: string; price_nok_kg: number }
interface SeasonalPoint { week_of_year: number; median_price: number }
interface ExportDest { country: string; volume_tonnes: number; value_nok_mill: number; share_pct: number }
interface FuturesPoint { month: string; price: number }
interface HedgeSignal { type: string; ticker: string; rationale: string; confidence: number }

// ─── Skeleton ─────────────────────────────────────────────────────────────────

function Skeleton({ className }: { className?: string }) {
  return (
    <div className={`animate-pulse bg-white/[0.06] rounded-lg ${className ?? ""}`} />
  );
}

// ─── Fish Pool SVG Chart ───────────────────────────────────────────────────────

function FishPoolChart({ data }: { data: FishPoolPoint[] }) {
  if (!data || data.length < 2) return <Skeleton className="h-40 w-full" />;

  const W = 800; const H = 160;
  const PAD = { top: 16, right: 64, bottom: 32, left: 52 };
  const prices = data.map((d) => d.price);
  const minP = prices.length > 0 ? Math.min(...prices) : 0;
  const maxP = prices.length > 0 ? Math.max(...prices) : 1;
  const range = maxP - minP || 1;

  const x = (i: number) => PAD.left + (i / (data.length - 1)) * (W - PAD.left - PAD.right);
  const y = (p: number) => PAD.top + (1 - (p - minP) / range) * (H - PAD.top - PAD.bottom);

  const linePts = data.map((d, i) => `${x(i)},${y(d.price)}`).join(" ");
  const areaPath =
    `M${x(0)},${y(data[0].price)} ` +
    data.map((d, i) => `L${x(i)},${y(d.price)}`).join(" ") +
    ` L${x(data.length - 1)},${H - PAD.bottom} L${x(0)},${H - PAD.bottom} Z`;

  const hiIdx = prices.indexOf(maxP);
  const loIdx = prices.indexOf(minP);
  const latest = data[data.length - 1];
  const xTicks = data.filter((_, i) => i % 13 === 0);
  const yTicks = Array.from({ length: 4 }, (_, i) => minP + (range / 3) * i);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" preserveAspectRatio="none" style={{ overflow: "visible" }}>
      <defs>
        <linearGradient id="fpArea" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#0ea5e9" stopOpacity={0.3} />
          <stop offset="100%" stopColor="#0ea5e9" stopOpacity={0} />
        </linearGradient>
        <linearGradient id="fpLine" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#06b6d4" />
          <stop offset="100%" stopColor="#38bdf8" />
        </linearGradient>
      </defs>
      {yTicks.map((val, i) => (
        <g key={i}>
          <line x1={PAD.left} y1={y(val)} x2={W - PAD.right} y2={y(val)}
            stroke="rgba(255,255,255,0.05)" strokeWidth={1} />
          <text x={PAD.left - 6} y={y(val) + 4} textAnchor="end"
            fill="rgba(255,255,255,0.35)" fontSize={10}>{val.toFixed(0)}</text>
        </g>
      ))}
      {xTicks.map((d, i) => {
        const idx = data.indexOf(d);
        return (
          <text key={i} x={x(idx)} y={H - PAD.bottom + 14} textAnchor="middle"
            fill="rgba(255,255,255,0.35)" fontSize={9}>{d.week.slice(0, 7)}</text>
        );
      })}
      <path d={areaPath} fill="url(#fpArea)" />
      <polyline points={linePts} fill="none" stroke="url(#fpLine)" strokeWidth={2}
        strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={x(hiIdx)} cy={y(maxP)} r={4} fill={colors.positive} />
      <text x={x(hiIdx)} y={y(maxP) - 8} textAnchor="middle" fontSize={9} fill={colors.positive}>
        H {maxP.toFixed(1)}
      </text>
      <circle cx={x(loIdx)} cy={y(minP)} r={4} fill={colors.negative} />
      <text x={x(loIdx)} y={y(minP) + 16} textAnchor="middle" fontSize={9} fill={colors.negative}>
        L {minP.toFixed(1)}
      </text>
      <circle cx={x(data.length - 1)} cy={y(latest.price)} r={4} fill="#38bdf8" />
      <rect x={x(data.length - 1) - 26} y={y(latest.price) - 18} width={52} height={16} rx={4}
        fill="rgba(14,165,233,0.25)" />
      <text x={x(data.length - 1)} y={y(latest.price) - 7} textAnchor="middle" fontSize={10}
        fill="#7dd3fc" fontWeight="600">{latest.price.toFixed(1)} NOK</text>
    </svg>
  );
}

// ─── SSB Seasonal Bar Chart ───────────────────────────────────────────────────

function SeasonalBars({ data }: { data: SeasonalPoint[] }) {
  if (!data.length) {
    return (
      <div className="flex items-center justify-center h-32 text-white/30 text-sm italic">
        Seasonal data unavailable
      </div>
    );
  }
  const W = 800; const H = 120;
  const maxP = Math.max(...data.map((d) => d.median_price));
  const minP = Math.min(...data.map((d) => d.median_price));
  const range = maxP - minP || 1;
  const gap = W / data.length;
  const barW = gap * 0.7;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" preserveAspectRatio="none">
      {data.map((d, i) => {
        const barH = Math.max(2, ((d.median_price - minP) / range) * (H - 20));
        const t = (d.median_price - minP) / range;
        const r = Math.round(t * 139);
        const g = Math.round(212 - t * 132);
        const b = Math.round(200 + t * 55);
        return (
          <rect key={i} x={i * gap + (gap - barW) / 2} y={H - 16 - barH}
            width={barW} height={barH} rx={2} fill={`rgb(${r},${g},${b})`} opacity={0.8} />
        );
      })}
      {data.filter((_, i) => i % 8 === 0).map((d, i) => {
        const origIdx = data.indexOf(d);
        return (
          <text key={i} x={origIdx * gap + gap / 2} y={H - 2} textAnchor="middle"
            fill="rgba(255,255,255,0.35)" fontSize={9}>W{d.week_of_year}</text>
        );
      })}
    </svg>
  );
}

// ─── Export Destinations ──────────────────────────────────────────────────────

const COUNTRY_CODES: Record<string, string> = {
  Poland: "PL", France: "FR", Denmark: "DK", Netherlands: "NL",
  USA: "US", UK: "GB", Germany: "DE", Japan: "JP",
  China: "CN", Spain: "ES", Italy: "IT", Sweden: "SE",
  Portugal: "PT", Belgium: "BE", Finland: "FI", Brazil: "BR",
  Thailand: "TH", "South Korea": "KR", Singapore: "SG",
};

function ExportBars({ data }: { data: ExportDest[] }) {
  if (!data.length) return <Skeleton className="h-40 w-full" />;
  const top5 = data.slice(0, 5);
  const maxVol = Math.max(...top5.map((d) => d.volume_tonnes));
  return (
    <div className="flex flex-col gap-3">
      {top5.map((d) => (
        <div key={d.country} className="flex items-center gap-3">
          <span className="text-xs font-mono bg-white/[0.06] px-1.5 py-0.5 rounded text-[var(--text-secondary)] w-7 text-center flex-shrink-0">
            {COUNTRY_CODES[d.country] ?? "--"}
          </span>
          <span className="text-xs text-white/70 w-24 flex-shrink-0 font-medium">{d.country}</span>
          <div className="flex-1 relative h-5">
            <div className="absolute inset-y-0 left-0 rounded-full bg-ocean-500/20 w-full" />
            <motion.div
              className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-ocean-500 to-cyan-400"
              initial={{ width: 0 }}
              animate={{ width: `${(d.volume_tonnes / maxVol) * 100}%` }}
              transition={{ duration: 0.8, ease: "easeOut" }}
            />
          </div>
          <span className="text-xs text-white/50 w-20 text-right flex-shrink-0">
            {(d.volume_tonnes / 1000).toFixed(1)}kt
          </span>
          <span className="text-xs text-ocean-400 w-12 text-right flex-shrink-0 font-semibold">
            {d.share_pct.toFixed(1)}%
          </span>
        </div>
      ))}
    </div>
  );
}

// ─── Futures Curve SVG ────────────────────────────────────────────────────────

function FuturesCurveChart({ data }: { data: FuturesPoint[] }) {
  if (!data.length) {
    return (
      <div className="flex items-center justify-center h-24 text-white/30 text-sm italic">
        Futures data unavailable
      </div>
    );
  }
  const W = 600; const H = 100;
  const PAD = { top: 12, right: 20, bottom: 24, left: 48 };
  const prices = data.map((d) => d.price);
  const minP = Math.min(...prices); const maxP = Math.max(...prices);
  const range = maxP - minP || 1;
  const x = (i: number) => PAD.left + (i / (data.length - 1)) * (W - PAD.left - PAD.right);
  const y = (p: number) => PAD.top + (1 - (p - minP) / range) * (H - PAD.top - PAD.bottom);
  const pts = data.map((d, i) => `${x(i)},${y(d.price)}`).join(" ");
  const area = `M${x(0)},${y(data[0].price)} ${data.map((d, i) => `L${x(i)},${y(d.price)}`).join(" ")} L${x(data.length - 1)},${H - PAD.bottom} L${x(0)},${H - PAD.bottom} Z`;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" preserveAspectRatio="none">
      <defs>
        <linearGradient id="fcArea" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#818cf8" stopOpacity={0.25} />
          <stop offset="100%" stopColor="#818cf8" stopOpacity={0} />
        </linearGradient>
      </defs>
      <path d={area} fill="url(#fcArea)" />
      <polyline points={pts} fill="none" stroke="#818cf8" strokeWidth={2}
        strokeLinecap="round" strokeLinejoin="round" />
      {data.map((d, i) => (
        <g key={i}>
          <circle cx={x(i)} cy={y(d.price)} r={3} fill="#a5b4fc" />
          <text x={x(i)} y={H - PAD.bottom + 12} textAnchor="middle"
            fill="rgba(255,255,255,0.4)" fontSize={8}>{d.month.slice(0, 6)}</text>
        </g>
      ))}
      <text x={PAD.left - 4} y={y(maxP) + 4} textAnchor="end" fill="rgba(255,255,255,0.35)" fontSize={9}>
        {maxP.toFixed(0)}
      </text>
      <text x={PAD.left - 4} y={y(minP) + 4} textAnchor="end" fill="rgba(255,255,255,0.35)" fontSize={9}>
        {minP.toFixed(0)}
      </text>
    </svg>
  );
}

// ─── Equity Mini Sparkline (5-bar proxy) ─────────────────────────────────────

function MiniBar5({ change }: { change: number }) {
  const bases = [0.3, 0.5, 0.4, 0.7, 1.0];
  const bars = bases.map((b) => Math.max(0.05, b + change / 20));
  const max = Math.max(...bars);
  return (
    <svg viewBox="0 0 28 16" width={28} height={16}>
      {bars.map((b, i) => {
        const h = Math.max(2, (b / max) * 14);
        return (
          <rect key={i} x={i * 6} y={16 - h} width={4} height={h} rx={1}
            fill={change >= 0 ? colors.success : colors.negative} opacity={0.65 + i * 0.07} />
        );
      })}
    </svg>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function MarketTerminalPage() {
  const { t, locale } = useTranslation();
  const handleError = useApiError();
  const [fishPool, setFishPool] = useState<FishPoolPoint[]>([]);
  const [equity, setEquity] = useState<EquityPrices | null>(null);
  const [ssbHistory, setSsbHistory] = useState<SsbPoint[]>([]);
  const [seasonal, setSeasonal] = useState<SeasonalPoint[]>([]);
  const [exports, setExports] = useState<ExportDest[]>([]);
  const [futures, setFutures] = useState<FuturesPoint[]>([]);
  const [futuresSynthetic, setFuturesSynthetic] = useState(false);
  const [seasonalYears, setSeasonalYears] = useState<string | null>(null);
  const [signals, setSignals] = useState<HedgeSignal[]>([]);
  const [sentimentArticles, setSentimentArticles] = useState<any[]>([]);
  const [harvestIntel, setHarvestIntel] = useState<any>(null);
  const [sentSummary, setSentSummary] = useState<any>(null);
  const [macroNOK, setMacroNOK] = useState<any>(null);
  const [macroOil, setMacroOil] = useState<any>(null);
  const [nokUsd, setNokUsd] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchAll = useCallback(async (showRefresh = false) => {
    if (showRefresh) setRefreshing(true);
    else setLoading(true);
    try {
      const [fpRes, eqRes, ssbRes, seasonRes, expRes, futRes, sigRes] = await Promise.allSettled([
        Promise.resolve({ data: [] }),  // Fish Pool removed — dead since 2025
        api.equityPrices(),
        api.ssbPriceHistory(52),
        api.ssbSeasonal(),
        api.exportDestinations(12),
        api.futuresForwardCurve(12),
        api.hedgerSignals(),
      ]);
      if (fpRes.status === "fulfilled") setFishPool((fpRes.value as any).data ?? []);
      if (eqRes.status === "fulfilled") setEquity(eqRes.value as EquityPrices);
      // /api/market/ssb-price-history returns {spot_nok, history:[{week, price_nok,…}]}
      // — map to the SsbPoint contract the price chart + sparkline consume.
      if (ssbRes.status === "fulfilled") {
        const hist = ((ssbRes.value as any).history ?? []) as Array<Record<string, unknown>>;
        setSsbHistory(
          hist.map((h) => ({ week: String(h.week ?? ""), price_nok_kg: Number(h.price_nok) })),
        );
      }
      // /api/market/ssb-seasonal returns {seasonal_pattern: {"1": median, …}, data_years}
      // — keys are ISO week numbers, values are multi-year medians (SSB table 03024).
      if (seasonRes.status === "fulfilled") {
        const sv = seasonRes.value as {
          seasonal_pattern?: Record<string, number>;
          data_years?: string;
        };
        setSeasonal(
          Object.entries(sv?.seasonal_pattern ?? {})
            .map(([week, price]) => ({ week_of_year: Number(week), median_price: Number(price) }))
            .sort((a, b) => a.week_of_year - b.week_of_year),
        );
        setSeasonalYears(sv?.data_years ?? null);
      }
      if (expRes.status === "fulfilled") setExports((expRes.value as any).destinations ?? []);
      // /api/futures/forward-curve: Fish Pool live forwards → SSB synthetic fallback
      if (futRes.status === "fulfilled") {
        const fv = futRes.value as Partial<FuturesForwardCurve>;
        // Fail-safe honesty: only an explicit is_synthetic=false (live Fish Pool
        // forwards) may ever show the Fish Pool badge; unknown payloads read synthetic.
        setFuturesSynthetic(fv.is_synthetic !== false);
        setFutures((Array.isArray(fv.curve) ? fv.curve : []).map((c) => ({ month: c.month, price: c.price_nok_kg })));
      }
      if (sigRes.status === "fulfilled") setSignals((sigRes.value as any).signals ?? []);
      // Fetch NOK/USD, sentiment, AIS
      try {
        const macro = await api.macroSnapshot();
        setNokUsd(macro?.benchmarks?.nok_usd || 0);
      } catch (e) { handleError("market_macro_snapshot")(e); }
      try {
        const articles = await api.sentimentArticles(24);
        setSentimentArticles((articles as any)?.articles || (Array.isArray(articles) ? articles : []));
      } catch (e) { handleError("market_sentiment_articles")(e); }
      try {
        const harvest = await api.aisHarvestIntelligence();
        setHarvestIntel(harvest);
      } catch (e) { handleError("market_ais_harvest")(e); }
      api.sentimentSummary().then(setSentSummary).catch(handleError("market_sentiment_summary"));
      api.macroSeries("nok_usd", 12).then(setMacroNOK).catch(handleError("market_macro_nok"));
      api.macroSeries("brent_crude", 12).then(setMacroOil).catch(handleError("market_macro_oil"));
      setLastUpdated(new Date());
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const latestFP = fishPool[fishPool.length - 1];
  const fpChange = latestFP?.change_pct ?? 0;
  const latestSSB = ssbHistory[ssbHistory.length - 1];
  const mowiPrice = equity?.prices?.MOWI;
  const mowiChange = equity?.changes?.MOWI ?? 0;

  const signalBadgeColor = (type: string) =>
    type === "HEDGE"
      ? "bg-ocean-500/20 text-ocean-300 border-ocean-500/30"
      : type === "UNHEDGE"
      ? "bg-rose-500/20 text-rose-300 border-rose-500/30"
      : "bg-amber-500/20 text-amber-300 border-amber-500/30";

  const equityTickers = ["MOWI", "SALM", "LSG", "GSF", "BAKKA"] as const;

  // ── Market Narrative Summary ────────────────────────────────────────────────
  const narrative = useMemo(() => {
    if (!ssbHistory.length) return null;
    const latest = ssbHistory[ssbHistory.length - 1];
    const prev = ssbHistory.length > 1 ? ssbHistory[ssbHistory.length - 2] : null;
    const priceDelta = prev ? ((latest.price_nok_kg - prev.price_nok_kg) / prev.price_nok_kg * 100) : 0;

    const parts: string[] = [`Salmon spot at NOK ${latest.price_nok_kg?.toFixed(1)}/kg`];
    if (prev) parts.push(`${priceDelta > 0 ? "+" : ""}${priceDelta.toFixed(1)}% WoW`);

    // Equity context
    if (equity?.prices) {
      const mowi = equity.prices.MOWI;
      const mowiDelta = equity.changes?.MOWI;
      const salm = equity.prices.SALM;
      const salmDelta = equity.changes?.SALM;
      if (mowi != null && mowiDelta != null) {
        parts.push(`MOWI ${mowiDelta >= 0 ? "+" : ""}${mowiDelta.toFixed(1)}%`);
      }
      if (salm != null && salmDelta != null) {
        parts.push(`SALM ${salmDelta >= 0 ? "+" : ""}${salmDelta.toFixed(1)}%`);
      }
    }

    // Sentiment context
    if (sentSummary) {
      const dir = (sentSummary.direction || sentSummary.sentiment || "").toLowerCase();
      if (dir.includes("bull")) parts.push("Sentiment bullish");
      else if (dir.includes("bear")) parts.push("Sentiment bearish");
      else if (dir) parts.push("Sentiment mixed");
    }

    // Feed cost / macro context
    if (macroOil) {
      const oilVal = macroOil.latest_value || macroOil.value || macroOil.data?.[macroOil.data?.length - 1]?.value;
      if (oilVal != null) parts.push(`Brent $${Number(oilVal).toFixed(0)}`);
    }

    return parts.join(" · ");
  }, [ssbHistory, equity, sentSummary, macroOil]);

  return (
    <ErrorBoundary fallbackTitle="Market Terminal error">
    <div className="min-h-screen bg-[var(--bg-base)] p-6 space-y-6">

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="flex items-start justify-between"
      >
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-ocean-500/10 border border-ocean-500/20 flex items-center justify-center">
            <DollarSign className="w-6 h-6 text-ocean-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-[var(--text-primary)]">
              {t("market.title")}
            </h1>
            <div className="flex items-center gap-2 mt-0.5">
              <p className="text-sm text-[var(--text-secondary)]">
                Fish Pool · SSB · Futures · Equity
              </p>
              {/* No invented confidence numbers: endpoint provenance is not
                  available here, so classify by whether SSB data arrived. */}
              <DataQualityBadge
                quality={ssbHistory.length > 0 ? "live" : "degraded"}
                source="SSB 03024 + Yahoo Finance + FRED"
                reason={ssbHistory.length === 0 ? "SSB data unavailable" : undefined}
              />
              <FreshnessIndicator lastUpdated={lastUpdated} />
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {lastUpdated && (
            <span className="text-xs text-white/30">
              Updated {lastUpdated.toLocaleTimeString()}
            </span>
          )}
          <OcButton
            variant="secondary"
            size="sm"
            leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />}
            onClick={() => fetchAll(true)}
            loading={refreshing}
          >
            Refresh
          </OcButton>
        </div>
      </motion.div>

      {/* ── Market Narrative Banner ──────────────────────────────────────── */}
      {narrative && (
        <motion.div
          initial={{ opacity: 0, y: -6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="rounded-xl bg-gradient-to-r from-ocean-500/[0.08] to-violet-500/[0.06] border border-ocean-500/20 px-5 py-3"
        >
          <p className="text-sm text-[var(--text-primary)] font-medium">{narrative}</p>
        </motion.div>
      )}

      {/* ── Ticker Strip ──────────────────────────────────────────────────── */}
      {!loading && (
        <TickerStrip
          className="rounded-xl"
          speed={36}
          items={[
            ...(latestSSB ? [{
              label: "SSB Spot",
              value: `${formatCurrency(latestSSB.price_nok_kg, locale)}/kg`,
            }] : []),
            ...(latestFP ? [{
              label: "Fish Pool",
              value: `${formatNumber(latestFP.price, locale, 1)} NOK`,
              change: fpChange,
            }] : []),
            ...(mowiPrice != null ? [{
              label: "MOWI",
              value: `${formatNumber(mowiPrice, locale, 1)} NOK`,
              change: mowiChange,
            }] : []),
            ...(equity?.prices?.SALM != null ? [{
              label: "SALM",
              value: `${formatNumber(equity.prices.SALM, locale, 1)} NOK`,
              change: equity.changes?.SALM ?? 0,
            }] : []),
            ...(equity?.prices?.LSG != null ? [{
              label: "LSG",
              value: `${formatNumber(equity.prices.LSG, locale, 1)} NOK`,
              change: equity.changes?.LSG ?? 0,
            }] : []),
            ...(equity?.prices?.GSF != null ? [{
              label: "GSF",
              value: `${formatNumber(equity.prices.GSF, locale, 1)} NOK`,
              change: equity.changes?.GSF ?? 0,
            }] : []),
            ...(equity?.prices?.BAKKA != null ? [{
              label: "BAKKA",
              value: `${formatNumber(equity.prices.BAKKA, locale, 1)} NOK`,
              change: equity.changes?.BAKKA ?? 0,
            }] : []),
            ...(nokUsd > 0 ? [{
              label: "NOK/USD",
              value: formatNumber(nokUsd, locale, 2),
            }] : []),
          ]}
        />
      )}

      {/* ── KPI Row ─────────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {loading ? (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-28" />)
        ) : (
          <>
            <KPICard
              label="Fish Pool Index"
              value={latestFP ? `${formatNumber(latestFP.price, locale, 1)} NOK` : "\u2014"}
              delta={latestFP ? `W${latestFP.week.slice(-2)}` : undefined}
              deltaType="neutral"
              icon={Activity}
              delay={0}
              sparkline={fishPool.slice(-10).map((d) => d.price)}
            />
            <KPICard
              label="WoW Change"
              value={latestFP ? `${fpChange >= 0 ? "+" : ""}${formatNumber(fpChange, locale, 2)}%` : "\u2014"}
              deltaType={fpChange > 0 ? "positive" : fpChange < 0 ? "negative" : "neutral"}
              icon={fpChange >= 0 ? TrendingUp : TrendingDown}
              delay={0.05}
            />
            <KPICard
              label={t("market.spot_price")}
              value={latestSSB ? `${formatCurrency(latestSSB.price_nok_kg, locale)}/kg` : "\u2014"}
              delta={latestSSB && nokUsd > 0
                ? `$${formatNumber(latestSSB.price_nok_kg / nokUsd, locale, 2)}/kg USD \u00b7 ${latestSSB.week}`
                : latestSSB ? latestSSB.week : undefined}
              deltaType="neutral"
              icon={BarChart2}
              delay={0.1}
              sparkline={ssbHistory.slice(-10).map((d) => d.price_nok_kg)}
            />
            <KPICard
              label="MOWI (Oslo B\u00f8rs)"
              value={mowiPrice != null ? `${formatCurrency(mowiPrice, locale)}` : "\u2014"}
              delta={mowiChange ? `${mowiChange >= 0 ? "+" : ""}${formatNumber(mowiChange, locale, 2)}%` : undefined}
              deltaType={mowiChange > 0 ? "positive" : mowiChange < 0 ? "negative" : "neutral"}
              icon={DollarSign}
              delay={0.15}
            />
          </>
        )}
      </div>

      {/* ── SSB Price Chart (Interactive) ────────────────────────────────── */}
      <GlassCard accent="ocean" delay={0.1}>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-semibold text-[var(--text-primary)]">
              {t("market.price_history")}
            </h2>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">NOK/kg &middot; Hover for crosshair</p>
          </div>
          <span className="text-xs px-2 py-0.5 rounded-full bg-ocean-500/10 text-ocean-400 border border-ocean-500/20">
            SSB 03024
          </span>
        </div>
        {loading ? (
          <Skeleton className="h-48" />
        ) : (
          <InteractiveChart
            data={ssbHistory.map((d, i) => ({
              x: i,
              y: d.price_nok_kg,
              label: d.week?.replace("W", "W") ?? `W${i}`,
            }))}
            unit="NOK/kg"
            color={chartPalette[0]}
            height={200}
          />
        )}
      </GlassCard>

      {/* ── Equity + SSB Seasonal ─────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        <GlassCard accent="violet" delay={0.15}>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-[var(--text-primary)]">{t("market.equity_prices")}</h2>
            <span className="text-xs px-2 py-0.5 rounded-full bg-violet-500/10 text-violet-400 border border-violet-500/20">
              Oslo Børs
            </span>
          </div>
          {loading ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-9" />)}
            </div>
          ) : !equity ? (
            <p className="text-xs text-white/30 text-center py-8">{t("common.no_data")}</p>
          ) : (
            <div className="space-y-1">
              {equityTickers.map((ticker) => {
                const price = equity.prices?.[ticker];
                const change = equity.changes?.[ticker] ?? 0;
                const isPos = change >= 0;
                return (
                  <div key={ticker}
                    className="flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-white/[0.03] transition-colors">
                    <span className="text-xs font-bold text-[var(--text-primary)] w-12 font-mono">
                      {ticker}
                    </span>
                    <span className="text-sm font-semibold text-[var(--text-primary)] flex-1">
                      {price != null ? formatNumber(price, locale, 2) : "\u2014"}
                      <span className="text-[10px] text-white/30 ml-1">NOK</span>
                    </span>
                    <span className={`text-xs font-semibold w-16 text-right ${isPos ? "text-emerald-400" : "text-rose-400"}`}>
                      {change != null ? `${isPos ? "+" : ""}${formatNumber(change, locale, 2)}%` : "\u2014"}
                    </span>
                    <MiniBar5 change={change} />
                  </div>
                );
              })}
            </div>
          )}
        </GlassCard>

        <GlassCard accent="emerald" delay={0.2}>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-[var(--text-primary)]">{t("market.weekly_avg")}</h2>
            <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              52 weeks
            </span>
          </div>
          {loading ? <Skeleton className="h-32" /> : <SeasonalBars data={seasonal} />}
          <p className="text-[10px] text-white/25 mt-3">
            Historical seasonality from SSB table 03024 · median NOK/kg by week-of-year
            {seasonalYears ? ` (${seasonalYears})` : ""}
          </p>
        </GlassCard>
      </div>

      {/* ── Export Destinations + Futures Curve ──────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        <GlassCard accent="amber" delay={0.25}>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-[var(--text-primary)]">Export Destinations</h2>
            <span className="text-xs px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">
              Top 5 · 12 months
            </span>
          </div>
          {loading ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-7" />)}
            </div>
          ) : (
            <ExportBars data={exports} />
          )}
          {!loading && exports.length > 0 && (
            <div className="flex gap-6 mt-4 pt-4 border-t border-white/[0.04]">
              <div>
                <p className="text-[10px] text-white/30 uppercase tracking-wide">Total Volume</p>
                <p className="text-sm font-semibold text-[var(--text-primary)]">
                  {formatNumber(exports.reduce((s, d) => s + d.volume_tonnes, 0) / 1000, locale, 1)}kt
                </p>
              </div>
              <div>
                <p className="text-[10px] text-white/30 uppercase tracking-wide">Total Value</p>
                <p className="text-sm font-semibold text-[var(--text-primary)]">
                  {formatNumber(exports.reduce((s, d) => s + d.value_nok_mill, 0), locale, 0)} MNOK
                </p>
              </div>
            </div>
          )}
        </GlassCard>

        <GlassCard accent="violet" delay={0.3}>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-[var(--text-primary)]">Futures Forward Curve</h2>
            {futures.length > 0 && (
              <span
                className={`text-xs px-2 py-0.5 rounded-full border ${
                  futuresSynthetic
                    ? "bg-amber-500/10 text-amber-400 border-amber-500/20"
                    : "bg-violet-500/10 text-violet-400 border-violet-500/20"
                }`}
              >
                {futuresSynthetic ? "SSB synthetic" : "Fish Pool"}
              </span>
            )}
          </div>
          {loading ? <Skeleton className="h-28" /> : <FuturesCurveChart data={futures} />}
          {!loading && futures.length > 0 && (
            <div className="flex gap-6 mt-3 pt-3 border-t border-white/[0.04]">
              <div>
                <p className="text-[10px] text-white/30 uppercase tracking-wide">Front Month</p>
                <p className="text-sm font-semibold text-[var(--text-primary)]">
                  {futures[0]?.price != null ? `${formatNumber(futures[0].price, locale, 1)} NOK` : "\u2014"}
                </p>
              </div>
              <div>
                <p className="text-[10px] text-white/30 uppercase tracking-wide">Far Month</p>
                <p className="text-sm font-semibold text-[var(--text-primary)]">
                  {futures[futures.length - 1]?.price != null ? `${formatNumber(futures[futures.length - 1].price, locale, 1)} NOK` : "\u2014"}
                </p>
              </div>
              <div>
                <p className="text-[10px] text-white/30 uppercase tracking-wide">Contango / Backw.</p>
                <p className={`text-sm font-semibold ${
                  (futures[futures.length - 1]?.price ?? 0) > (futures[0]?.price ?? 0)
                    ? "text-rose-400"
                    : "text-emerald-400"
                }`}>
                  {formatNumber((futures[futures.length - 1]?.price ?? 0) - (futures[0]?.price ?? 0), locale, 1)} NOK
                </p>
              </div>
            </div>
          )}
        </GlassCard>
      </div>

      {/* ── Hedger Signals ───────────────────────────────────────────────── */}
      <GlassCard accent="rose" delay={0.35}>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-semibold text-[var(--text-primary)]">Hedger Signals</h2>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">AI-generated hedge recommendations</p>
          </div>
          <span className="text-xs px-2 py-0.5 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20">
            {signals.length} active
          </span>
        </div>
        {loading ? (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-14" />)}
          </div>
        ) : signals.length === 0 ? (
          <p className="text-xs text-white/30 text-center py-8">{t("common.no_data")}</p>
        ) : (
          <div className="space-y-3">
            {signals.slice(0, 5).map((sig, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -12 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.35 + i * 0.06 }}
                className="flex items-start gap-3 p-3 rounded-xl bg-white/[0.02] border border-white/[0.04] hover:border-white/[0.08] transition-colors"
              >
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded border flex-shrink-0 mt-0.5 ${signalBadgeColor(sig.type)}`}>
                  {sig.type}
                </span>
                <span className="text-xs font-bold text-[var(--text-primary)] w-14 flex-shrink-0 font-mono mt-0.5">
                  {sig.ticker}
                </span>
                <p className="text-xs text-[var(--text-secondary)] flex-1 leading-relaxed">
                  {sig.rationale}
                </p>
                <div className="flex flex-col items-end gap-1 flex-shrink-0 w-20">
                  <span className="text-[10px] text-white/30">Confidence</span>
                  <div className="w-full h-1.5 rounded-full bg-white/[0.06]">
                    <motion.div
                      className="h-full rounded-full bg-gradient-to-r from-ocean-500 to-cyan-400"
                      initial={{ width: 0 }}
                      animate={{ width: `${formatNumber(sig.confidence * 100, locale, 0)}%` }}
                      transition={{ delay: 0.5 + i * 0.06, duration: 0.6 }}
                    />
                  </div>
                  <span className="text-[10px] font-semibold text-ocean-400">
                    {formatNumber(sig.confidence * 100, locale, 0)}%
                  </span>
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </GlassCard>

      {/* ── Macro Intelligence Widget ─────────────────────────────────── */}
      <MacroWidget />

      {/* ── News & Sentiment ──────────────────────────────────────────── */}
      {sentimentArticles.length > 0 && (
        <GlassCard delay={0.45}>
          <h3 className="text-xs font-semibold mb-3 flex items-center gap-2">
            <Activity className="w-3.5 h-3.5 text-ocean-400" />
            {t("market.news_sentiment")}
            <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-ocean-500/10 text-ocean-400 border border-ocean-500/20 ml-auto">
              Last 24h
            </span>
          </h3>
          <div className="space-y-1.5 max-h-48 overflow-y-auto">
            {sentimentArticles.slice(0, 10).map((a: any, i: number) => {
              const score = a.sentiment_score ?? a.score ?? 0;
              return (
                <div key={i} className="flex items-center gap-3 p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                  <span className={`text-[9px] px-1.5 py-0.5 rounded-full border flex-shrink-0 ${
                    score > 0.2 ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                    : score < -0.2 ? "bg-rose-500/10 text-rose-400 border-rose-500/20"
                    : "bg-gray-500/10 text-gray-400 border-gray-500/20"
                  }`}>
                    {score > 0.2 ? "Bullish" : score < -0.2 ? "Bearish" : "Neutral"}
                  </span>
                  <span className="text-[11px] text-[var(--text-primary)] flex-1 truncate">{a.headline || a.title || "Article"}</span>
                  <span className="text-[10px] text-[var(--text-secondary)] flex-shrink-0">{a.source || ""}</span>
                </div>
              );
            })}
          </div>
        </GlassCard>
      )}

      {/* ── AIS Harvest Intelligence ──────────────────────────────────── */}
      {harvestIntel && (
        <GlassCard delay={0.48}>
          <h3 className="text-xs font-semibold mb-3 flex items-center gap-2">
            <BarChart2 className="w-3.5 h-3.5 text-amber-400" />
            {t("market.harvest_intel")}
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {harvestIntel.active_vessels != null && (
              <div className="p-2 rounded-lg bg-white/[0.03] border border-white/[0.06] text-center">
                <p className="text-lg font-bold text-ocean-400 tabular-nums">{harvestIntel.active_vessels}</p>
                <p className="text-[9px] text-[var(--text-secondary)]">Active Vessels</p>
              </div>
            )}
            {harvestIntel.harvest_signals != null && (
              <div className="p-2 rounded-lg bg-white/[0.03] border border-white/[0.06] text-center">
                <p className="text-lg font-bold text-amber-400 tabular-nums">{harvestIntel.harvest_signals}</p>
                <p className="text-[9px] text-[var(--text-secondary)]">Harvest Signals</p>
              </div>
            )}
            {harvestIntel.treatment_signals != null && (
              <div className="p-2 rounded-lg bg-white/[0.03] border border-white/[0.06] text-center">
                <p className="text-lg font-bold text-violet-400 tabular-nums">{harvestIntel.treatment_signals}</p>
                <p className="text-[9px] text-[var(--text-secondary)]">Treatment Signals</p>
              </div>
            )}
            {harvestIntel.estimated_supply_impact && (
              <div className="p-2 rounded-lg bg-white/[0.03] border border-white/[0.06] text-center">
                <p className="text-[11px] font-bold text-[var(--text-primary)]">{harvestIntel.estimated_supply_impact}</p>
                <p className="text-[9px] text-[var(--text-secondary)]">Supply Impact</p>
              </div>
            )}
          </div>
          {harvestIntel.signals && Array.isArray(harvestIntel.signals) && harvestIntel.signals.length > 0 && (
            <div className="mt-3 space-y-1">
              {harvestIntel.signals.slice(0, 5).map((s: any, i: number) => (
                <div key={i} className="flex items-center gap-2 text-[10px] p-1.5 rounded bg-white/[0.02]">
                  <span className="text-ocean-400">{s.vessel_name || "Vessel"}</span>
                  <span className="text-[var(--text-secondary)]">{s.signal_type || s.type || ""}</span>
                  <span className="ml-auto text-[var(--text-secondary)]">{s.time || ""}</span>
                </div>
              ))}
            </div>
          )}
        </GlassCard>
      )}

      {/* Macro Indicators */}
        <GlassCard delay={0.3}>
          <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
            <Activity className="w-4 h-4 text-violet-400" />
            {t("market.macro_indicators")}
          </h3>
          <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
            {sentSummary && (
              <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06]">
                <div className="text-[10px] text-[var(--text-secondary)] uppercase tracking-wider mb-1">Market Sentiment</div>
                <div className={`text-lg font-bold ${
                  (sentSummary.direction || sentSummary.sentiment || "").toLowerCase().includes("bull") ? "text-emerald-400" :
                  (sentSummary.direction || sentSummary.sentiment || "").toLowerCase().includes("bear") ? "text-rose-400" : "text-amber-400"
                }`}>
                  {sentSummary.score != null ? formatNumber(sentSummary.score, locale, 2) : (sentSummary.sentiment || "Neutral")}
                </div>
                <div className="text-[10px] text-[var(--text-secondary)] mt-0.5">{sentSummary.articles_analyzed || 0} articles</div>
              </div>
            )}
            {macroNOK && (
              <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06]">
                <div className="text-[10px] text-[var(--text-secondary)] uppercase tracking-wider mb-1">NOK/USD</div>
                <div className="text-lg font-bold text-[var(--text-primary)]">
                  {formatNumber(macroNOK.latest_value || macroNOK.value || macroNOK.data?.[macroNOK.data?.length - 1]?.value || 0, locale, 2)}
                </div>
                <div className="text-[10px] text-[var(--text-secondary)] mt-0.5">FRED live</div>
              </div>
            )}
            {macroOil && (
              <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06]">
                <div className="text-[10px] text-[var(--text-secondary)] uppercase tracking-wider mb-1">Brent Crude</div>
                <div className="text-lg font-bold text-[var(--text-primary)]">
                  ${formatNumber(macroOil.latest_value || macroOil.value || macroOil.data?.[macroOil.data?.length - 1]?.value || 0, locale, 1)}
                </div>
                <div className="text-[10px] text-[var(--text-secondary)] mt-0.5">FRED live</div>
              </div>
            )}
          </div>
        </GlassCard>

      {/* ── Footer ──────────────────────────────────────────────────────── */}
      <p className="text-[10px] text-white/20 text-center pb-4">
        Market data is for informational purposes only and does not constitute financial advice.
        Sources: SSB (CC BY 4.0) &middot; Oslo B&oslash;rs &middot; FRED (St. Louis Fed).
      </p>

    </div>
    </ErrorBoundary>
  );
}


// ── Collapsible Macro Intelligence Widget ────────────────────────────────────
function MacroWidget() {
  const handleError = useApiError();
  const [data, setData] = useState<any>(null);
  const [open, setOpen] = useState(true);

  useEffect(() => {
    api.macroSnapshot().then(setData).catch(handleError("market_macro_widget"));
  }, []);

  if (!data) return null;

  const idx = data.indices || {};
  const bm = data.benchmarks || {};
  const alerts = data.alerts || [];
  const yoy = data.yoy_changes || {};

  const idxColor = (v: number) =>
    v > 65 ? "text-rose-400" : v > 45 ? "text-amber-400" : "text-emerald-400";

  const idxBg = (v: number) =>
    v > 65 ? "bg-rose-500" : v > 45 ? "bg-amber-500" : "bg-emerald-500";

  return (
    <GlassCard delay={0.3} accent="violet">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between text-left"
      >
        <h3 className="text-sm font-semibold flex items-center gap-2">
          <Activity className="w-4 h-4 text-violet-400" />
          Commodity &amp; Macro Intelligence
          <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-violet-500/10 text-violet-400 border border-violet-500/20">
            FRED
          </span>
        </h3>
        <motion.span
          animate={{ rotate: open ? 180 : 0 }}
          className="text-[var(--text-secondary)]"
        >
          <TrendingDown className="w-3.5 h-3.5" />
        </motion.span>
      </button>

      {open && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          exit={{ opacity: 0, height: 0 }}
          className="mt-4 space-y-4"
        >
          {/* Composite Indices — compact row */}
          <div className="grid grid-cols-3 gap-2">
            {Object.entries(idx).map(([key, val]: [string, any]) => (
              <div key={key} className="p-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06] text-center">
                <p className="text-[9px] text-[var(--text-secondary)] uppercase tracking-wider mb-1">
                  {val.label}
                </p>
                <div className="flex items-center justify-center gap-2">
                  <div className="w-10 h-1.5 bg-white/[0.06] rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${idxBg(val.value)}`}
                      style={{ width: `${val.value}%` }}
                    />
                  </div>
                  <span className={`text-sm font-bold font-mono ${idxColor(val.value)}`}>
                    {val.value}
                  </span>
                </div>
              </div>
            ))}
          </div>

          {/* Key Benchmarks — compact 2×3 grid */}
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            {bm.global_salmon_usd_kg > 0 && (
              <div className="flex items-center justify-between p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                <span className="text-[10px] text-[var(--text-secondary)]">Global Salmon</span>
                <span className="text-[11px] font-mono font-semibold text-ocean-300">
                  ${bm.global_salmon_usd_kg}/kg
                </span>
              </div>
            )}
            {bm.norway_premium_pct !== 0 && (
              <div className="flex items-center justify-between p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                <span className="text-[10px] text-[var(--text-secondary)]">Norway Premium</span>
                <span className={`text-[11px] font-mono font-semibold ${
                  bm.norway_premium_pct > 0 ? "text-emerald-400" : "text-rose-400"
                }`}>
                  {bm.norway_premium_pct > 0 ? "+" : ""}{bm.norway_premium_pct}%
                </span>
              </div>
            )}
            <div className="flex items-center justify-between p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
              <span className="text-[10px] text-[var(--text-secondary)]">NOK/USD</span>
              <span className="text-[11px] font-mono font-semibold text-[var(--text-primary)]">
                {bm.nok_usd?.toFixed(2)}
                {yoy.nok_usd ? (
                  <span className={`ml-1 text-[9px] ${yoy.nok_usd > 0 ? "text-rose-400" : "text-emerald-400"}`}>
                    {yoy.nok_usd > 0 ? "+" : ""}{yoy.nok_usd}%
                  </span>
                ) : null}
              </span>
            </div>
            {bm.eur_nok > 0 && (
              <div className="flex items-center justify-between p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                <span className="text-[10px] text-[var(--text-secondary)]">EUR/NOK</span>
                <span className="text-[11px] font-mono font-semibold text-[var(--text-primary)]">
                  {bm.eur_nok?.toFixed(2)}
                </span>
              </div>
            )}
            {bm.nok_cny > 0 && (
              <div className="flex items-center justify-between p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                <span className="text-[10px] text-[var(--text-secondary)]">NOK/CNY</span>
                <span className="text-[11px] font-mono font-semibold text-[var(--text-primary)]">
                  {bm.nok_cny?.toFixed(4)}
                </span>
              </div>
            )}
            <div className="flex items-center justify-between p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
              <span className="text-[10px] text-[var(--text-secondary)]">Brent Crude</span>
              <span className="text-[11px] font-mono font-semibold text-[var(--text-primary)]">
                ${bm.brent_crude_usd}
                {yoy.brent_crude ? (
                  <span className={`ml-1 text-[9px] ${yoy.brent_crude > 0 ? "text-rose-400" : "text-emerald-400"}`}>
                    {yoy.brent_crude > 0 ? "+" : ""}{yoy.brent_crude}%
                  </span>
                ) : null}
              </span>
            </div>
            <div className="flex items-center justify-between p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
              <span className="text-[10px] text-[var(--text-secondary)]">NatGas EU</span>
              <span className="text-[11px] font-mono font-semibold text-[var(--text-primary)]">
                ${bm.natgas_eu_usd}
                {yoy.natgas_eu ? (
                  <span className={`ml-1 text-[9px] ${yoy.natgas_eu > 0 ? "text-rose-400" : "text-emerald-400"}`}>
                    {yoy.natgas_eu > 0 ? "+" : ""}{yoy.natgas_eu}%
                  </span>
                ) : null}
              </span>
            </div>
            {bm.norway_rate_pct > 0 && (
              <div className="flex items-center justify-between p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                <span className="text-[10px] text-[var(--text-secondary)]">NO Rate</span>
                <span className="text-[11px] font-mono font-semibold text-[var(--text-primary)]">
                  {bm.norway_rate_pct}%
                </span>
              </div>
            )}
          </div>

          {/* Alerts — compact */}
          {alerts.length > 0 && (
            <div className="space-y-1.5">
              {alerts.slice(0, 3).map((alert: string, i: number) => (
                <div key={i} className="flex items-start gap-2 p-2 rounded-lg bg-violet-500/[0.04] border border-violet-500/[0.08]">
                  <BarChart2 className="w-3 h-3 text-violet-400 flex-shrink-0 mt-0.5" />
                  <p className="text-[10px] text-[var(--text-primary)] leading-relaxed">{alert}</p>
                </div>
              ))}
            </div>
          )}

          <p className="text-[8px] text-[var(--text-secondary)] opacity-40">
            Source: FRED (Federal Reserve Economic Data) &middot; Monthly updates &middot; Free public data
          </p>
        </motion.div>
      )}
    </GlassCard>
  );
}
