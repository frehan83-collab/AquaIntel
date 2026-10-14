"use client";
import { useState, useEffect, useMemo } from "react";
import { useTranslation } from "@/lib/i18n";
import { motion } from "framer-motion";
import {
  Newspaper, RefreshCw, TrendingUp, TrendingDown, Bug, Shield,
  Wheat, Ship, Leaf, DollarSign, Fish, BarChart3, Zap, Sun,
  AlertTriangle, Activity, ArrowUpRight, ArrowDownRight, Download,
} from "lucide-react";
import GlassCard from "@/components/GlassCard";
import KPICard from "@/components/KPICard";
import DataQualityBadge from "@/components/DataQualityBadge";
import { OcButton } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { colors } from "@/lib/design-tokens";
import type { LucideIcon } from "lucide-react";
import type {
  AnomalyScores,
  BriefSection,
  FeedCostLatest,
  MorningBrief,
} from "@/types/api";

const ICON_MAP: Record<string, LucideIcon> = {
  fish: Fish, chart: BarChart3, bug: Bug, shield: Shield,
  wheat: Wheat, ship: Ship, leaf: Leaf, currency: DollarSign,
  alert: AlertTriangle, activity: Activity,
};

const SENTIMENT_STYLE: Record<string, { bg: string; border: string; dot: string }> = {
  bullish: { bg: "bg-emerald-500/[0.06]", border: "border-emerald-500/20", dot: "bg-emerald-400" },
  bearish: { bg: "bg-rose-500/[0.06]", border: "border-rose-500/20", dot: "bg-rose-400" },
  alert:   { bg: "bg-amber-500/[0.06]", border: "border-amber-500/20", dot: "bg-amber-400 animate-pulse" },
  neutral: { bg: "bg-white/[0.03]", border: "border-white/[0.06]", dot: "bg-white/30" },
};

const MOOD_CONFIG: Record<string, { label: string; color: string; icon: LucideIcon; gradient: string }> = {
  bullish:  { label: "Bullish",  color: "text-emerald-400", icon: TrendingUp,   gradient: "from-emerald-500/[0.12] to-emerald-500/[0.02]" },
  bearish:  { label: "Bearish",  color: "text-rose-400",    icon: TrendingDown,  gradient: "from-rose-500/[0.12] to-rose-500/[0.02]" },
  mixed:    { label: "Mixed",    color: "text-amber-400",   icon: Zap,           gradient: "from-amber-500/[0.10] to-amber-500/[0.02]" },
  neutral:  { label: "Neutral",  color: "text-[var(--text-secondary)]", icon: Sun, gradient: "from-ocean-500/[0.08] to-violet-500/[0.08]" },
  cautious: { label: "Cautious", color: "text-amber-400",   icon: Shield,        gradient: "from-amber-500/[0.10] to-orange-500/[0.04]" },
};

const SEVERITY_BADGE: Record<string, { bg: string; text: string; ring: string }> = {
  CRITICAL: { bg: "bg-rose-500/20",   text: "text-rose-300",   ring: "ring-rose-500/40" },
  HIGH:     { bg: "bg-orange-500/20",  text: "text-orange-300", ring: "ring-orange-500/40" },
  MEDIUM:   { bg: "bg-amber-500/15",   text: "text-amber-300",  ring: "ring-amber-500/30" },
  LOW:      { bg: "bg-sky-500/15",     text: "text-sky-300",    ring: "ring-sky-500/30" },
  ELEVATED: { bg: "bg-amber-500/15",   text: "text-amber-300",  ring: "ring-amber-500/30" },
};

/** Extract a severity keyword from the Early Warning headline */
function extractSeverity(headline: string): string {
  const upper = headline.toUpperCase();
  if (upper.includes("CRITICAL")) return "CRITICAL";
  if (upper.includes("HIGH")) return "HIGH";
  if (upper.includes("ELEVATED")) return "ELEVATED";
  if (upper.includes("MEDIUM")) return "MEDIUM";
  return "LOW";
}

/** Parse ESG movers detail string into structured list */
function parseEsgMovers(detail: string): { name: string; delta: number; score: number }[] {
  if (!detail) return [];
  return detail.split(";").map((part) => {
    const trimmed = part.trim();
    // Format: "CompanyName: +3.2 -> 72"  or  "CompanyName: -1.5 -> 68"
    const colonIdx = trimmed.indexOf(":");
    if (colonIdx < 0) return null;
    const name = trimmed.slice(0, colonIdx).trim();
    const rest = trimmed.slice(colonIdx + 1).trim();
    // rest looks like "+3.2 -> 72" or "+3.2 → 72"
    const arrowMatch = rest.match(/([+-]?\d+\.?\d*)\s*[→\->]+\s*(\d+\.?\d*)/);
    if (!arrowMatch) return null;
    return { name, delta: parseFloat(arrowMatch[1]), score: parseFloat(arrowMatch[2]) };
  }).filter(Boolean) as { name: string; delta: number; score: number }[];
}

/** Brief section plus the page's locally computed ordering priority */
type ScoredSection = BriefSection & { _priority: number };

/** Extract a numeric value from a section value or headline */
function extractNumber(sec: BriefSection | undefined): number | null {
  if (!sec) return null;
  if (sec.value) {
    const n = parseFloat(sec.value.replace(/[^0-9.\-]/g, ""));
    if (!isNaN(n)) return n;
  }
  const m = sec.headline?.match(/([\d.]+)/);
  return m ? parseFloat(m[1]) : null;
}

export default function BriefPage() {
  const { t } = useTranslation();
  const [brief, setBrief] = useState<MorningBrief | null>(null);
  const [loading, setLoading] = useState(true);
  const [anomalyData, setAnomalyData] = useState<AnomalyScores | null>(null);
  const [feedData, setFeedData] = useState<FeedCostLatest | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const [briefRes, anomalyRes, feedRes] = await Promise.allSettled([
        api.brief(),
        api.anomalyScores(),
        api.feedCostLatest(),
      ]);
      if (briefRes.status === "fulfilled") setBrief(briefRes.value);
      if (anomalyRes.status === "fulfilled") setAnomalyData(anomalyRes.value);
      if (feedRes.status === "fulfilled") setFeedData(feedRes.value);
    } catch { /* empty */ }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const mood = MOOD_CONFIG[brief?.market_mood ?? "neutral"] || MOOD_CONFIG.neutral;
  const MoodIcon = mood.icon;

  // Extract KPI values from brief sections
  const priceSec = brief?.sections?.find((s) => s.title === "Salmon Price");
  const liceSec = brief?.sections?.find((s) => s.title === "Lice Pressure");
  const feedSec = brief?.sections?.find((s) => s.title === "Feed & Margins");
  const esgSec = brief?.sections?.find((s) => s.title === "ESG Movers");
  const warningSec = brief?.sections?.find((s) => s.title === "Early Warning");

  // Separate special sections from regular ones
  const rawRegularSections = brief?.sections?.filter(
    (s) => s.title !== "ESG Movers" && s.title !== "Early Warning"
  ) || [];

  // ── Priority scoring for dynamic section ordering ───────────────────────────
  const regularSections = useMemo(() => {
    if (!rawRegularSections.length) return rawRegularSections;

    const scoreSectionPriority = (sec: BriefSection): number => {
      let score = 10; // default neutral
      const headline = (sec.headline || "").toUpperCase();
      const title = (sec.title || "").toUpperCase();
      const detail = (sec.detail || "").toUpperCase();
      const combined = `${headline} ${title} ${detail}`;

      // Severity keywords
      if (combined.includes("CRITICAL")) score = Math.max(score, 100);
      if (combined.includes("HIGH") && (combined.includes("RISK") || combined.includes("ALERT") || combined.includes("SEVERITY"))) score = Math.max(score, 95);

      // Disease alerts
      if (title.includes("DISEASE") || combined.includes("ISA OUTBREAK") || combined.includes("PD OUTBREAK")) score = Math.max(score, 90);

      // Lice above threshold
      if (title.includes("LICE")) {
        const liceVal = extractNumber(sec);
        if (liceVal != null && liceVal > 0.5) score = Math.max(score, 85);
        else if (sec.sentiment === "alert") score = Math.max(score, 85);
        else score = Math.max(score, 40);
      }

      // Large price moves
      const pctMatch = (sec.headline || "").match(/([+-]?\d+\.?\d*)%/);
      if (pctMatch) {
        const absPct = Math.abs(parseFloat(pctMatch[1]));
        if (absPct > 5) score = Math.max(score, 80);
        else if (absPct > 2) score = Math.max(score, 50);
      }

      // Sentiment-based boost
      if (sec.sentiment === "alert") score = Math.max(score, 70);
      if (sec.sentiment === "bearish") score = Math.max(score, 45);
      if (sec.sentiment === "bullish") score = Math.max(score, 30);

      // Feed & margin pressure
      if (title.includes("FEED") && (combined.includes("PRESSURE") || combined.includes("RISING") || combined.includes("SPIKE"))) {
        score = Math.max(score, 65);
      }

      return score;
    };

    return [...rawRegularSections]
      .map((sec) => ({ ...sec, _priority: scoreSectionPriority(sec) }))
      .sort((a, b) => b._priority - a._priority);
  }, [rawRegularSections]) as ScoredSection[];

  // KPI values
  const spotPrice = priceSec ? extractNumber(priceSec) : null;
  const spotDelta = priceSec?.headline?.match(/([+-]?\d+\.?\d*%)/)?.[1] || null;
  const liceAvg = liceSec ? extractNumber(liceSec) : null;
  const liceDelta = liceSec?.sentiment === "alert" ? "Above limit" : liceSec?.sentiment === "bearish" ? "Elevated" : null;
  const anomalyScore = anomalyData?.composite_score ?? null;
  const anomalyLevel = anomalyData?.risk_level ?? null;
  const feedPressure = feedSec?.value || (feedData?.margin_pct ? `${feedData.margin_pct.toFixed(0)}%` : null);
  const feedTrend = feedData?.margin_trend || null;

  return (
    <div className="space-y-6 max-w-3xl mx-auto">

      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-[var(--text-primary)] flex items-center gap-3">
              <Newspaper className="w-6 h-6 text-ocean-400" />
              {t("brief.title")}
            </h1>
            <div className="flex items-center gap-2 mt-1">
              <p className="text-sm text-[var(--text-secondary)]">
                {brief?.greeting || "Your daily salmon market intelligence digest"}
              </p>
              {brief?.data_provenance && <DataQualityBadge provenance={brief.data_provenance} />}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <OcButton variant="secondary" size="sm" onClick={() => window.print()}
              leftIcon={<Download className="w-3.5 h-3.5" />}>{t("brief.export_pdf")}</OcButton>
            <OcButton variant="secondary" size="sm" onClick={load} loading={loading}
              leftIcon={<RefreshCw className="w-3.5 h-3.5" />}>Refresh</OcButton>
          </div>
        </div>
      </motion.div>

      {/* Market Mood Banner */}
      {brief && (
        <motion.div
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          className={`p-4 rounded-2xl bg-gradient-to-r ${mood.gradient} border border-white/[0.08]`}
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-[10px] text-[var(--text-secondary)] uppercase tracking-wider mb-1">{t("brief.market_mood")}</p>
              <div className="flex items-center gap-2">
                <MoodIcon className={`w-5 h-5 ${mood.color}`} />
                <span className={`text-lg font-bold ${mood.color}`}>
                  {brief?.market_mood === "bullish" ? t("brief.bullish") : brief?.market_mood === "bearish" ? t("brief.bearish") : t("brief.neutral")}
                </span>
              </div>
            </div>
            <div className="text-right max-w-xs">
              <p className="text-[10px] text-[var(--text-secondary)] uppercase tracking-wider mb-1">Top Insight</p>
              <p className="text-[12px] text-[var(--text-primary)] font-medium leading-snug">
                {brief.top_insight}
              </p>
            </div>
          </div>
        </motion.div>
      )}

      {/* KPI Strip */}
      {brief && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <KPICard
            label="SSB Spot Price"
            value={spotPrice != null ? `NOK ${spotPrice.toFixed(1)}` : "--"}
            delta={spotDelta || undefined}
            deltaType={priceSec?.sentiment === "bullish" ? "positive" : priceSec?.sentiment === "bearish" ? "negative" : "neutral"}
            icon={Fish}
            delay={0}
          />
          <KPICard
            label="Feed Pressure"
            value={feedPressure || "--"}
            delta={feedTrend || undefined}
            deltaType={feedTrend === "improving" ? "positive" : feedTrend === "worsening" ? "negative" : "neutral"}
            icon={Wheat}
            delay={0.05}
          />
          <KPICard
            label="Anomaly Score"
            value={anomalyScore != null ? `${anomalyScore}/100` : "--"}
            delta={anomalyLevel || undefined}
            deltaType={anomalyScore != null && anomalyScore >= 70 ? "negative" : anomalyScore != null && anomalyScore >= 30 ? "neutral" : "positive"}
            icon={Activity}
            pulse={anomalyScore != null && anomalyScore >= 70}
            delay={0.1}
          />
          <KPICard
            label="Lice Average"
            value={liceAvg != null ? liceAvg.toFixed(3) : "--"}
            delta={liceDelta || undefined}
            deltaType={liceSec?.sentiment === "alert" ? "negative" : liceSec?.sentiment === "bearish" ? "negative" : "positive"}
            icon={Bug}
            delay={0.15}
          />
        </div>
      )}

      {/* Early Warning Section */}
      {warningSec && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <EarlyWarningCard section={warningSec} anomalyData={anomalyData} />
        </motion.div>
      )}

      {/* ESG Movers Section */}
      {esgSec && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
        >
          <EsgMoversCard section={esgSec} />
        </motion.div>
      )}

      {/* Regular Brief Sections */}
      {regularSections.length > 0 ? (
        <div className="space-y-3">
          {regularSections.map((sec, i: number) => {
            const Icon = ICON_MAP[sec.icon ?? ""] || Zap;
            const style = SENTIMENT_STYLE[sec.sentiment ?? "neutral"] || SENTIMENT_STYLE.neutral;

            return (
              <motion.div
                key={sec.title}
                initial={{ opacity: 0, x: -12 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.2 + i * 0.05 }}
                className={`p-4 rounded-xl border ${style.bg} ${style.border} transition-all duration-200 hover:border-white/[0.12]`}
              >
                <div className="flex items-start gap-3">
                  {/* Priority indicator bar — uses design token colors */}
                  <div
                    className="w-1 self-stretch rounded-full flex-shrink-0"
                    style={{
                      backgroundColor: sec._priority >= 80 ? colors.danger
                        : sec._priority >= 60 ? colors.salmon
                        : sec._priority >= 40 ? colors.warning
                        : "rgba(255,255,255,0.08)",
                    }}
                  />
                  <div className="flex items-center gap-2 flex-shrink-0 mt-0.5">
                    <div className={`w-2 h-2 rounded-full ${style.dot}`} />
                    <div className={`w-7 h-7 rounded-lg flex items-center justify-center ${
                      sec.sentiment === "alert" ? "bg-amber-500/10" :
                      sec.sentiment === "bullish" ? "bg-emerald-500/10" :
                      sec.sentiment === "bearish" ? "bg-rose-500/10" :
                      "bg-white/[0.04]"
                    }`}>
                      <Icon className={`w-3.5 h-3.5 ${
                        sec.sentiment === "alert" ? "text-amber-400" :
                        sec.sentiment === "bullish" ? "text-emerald-400" :
                        sec.sentiment === "bearish" ? "text-rose-400" :
                        "text-[var(--text-secondary)]"
                      }`} />
                    </div>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-0.5">
                      <span className="section-header text-[11px] font-semibold text-[var(--text-secondary)] uppercase tracking-wider">
                        {sec.title}
                      </span>
                      {sec.value && (
                        <span className={`text-sm font-bold font-mono ${
                          sec.sentiment === "bullish" ? "text-emerald-400" :
                          sec.sentiment === "bearish" ? "text-rose-400" :
                          sec.sentiment === "alert" ? "text-amber-400" :
                          "text-[var(--text-primary)]"
                        }`}>
                          {sec.value}
                        </span>
                      )}
                    </div>
                    <p className="text-[13px] font-medium text-[var(--text-primary)] leading-snug">
                      {sec.headline}
                    </p>
                    {sec.detail && (
                      <p className="text-[11px] text-[var(--text-secondary)] mt-1 leading-relaxed">
                        {sec.detail}
                      </p>
                    )}
                  </div>
                </div>
              </motion.div>
            );
          })}
        </div>
      ) : loading ? (
        <div className="space-y-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-16 rounded-xl bg-white/[0.03] animate-pulse" />
          ))}
        </div>
      ) : !brief ? (
        <GlassCard>
          <div className="py-12 text-center">
            <Newspaper className="w-10 h-10 mx-auto mb-3 opacity-20" />
            <p className="text-sm text-[var(--text-secondary)]">{t("common.loading")}</p>
          </div>
        </GlassCard>
      ) : null}

      <p className="text-[9px] text-[var(--text-secondary)] text-center opacity-50">
        Generated from live platform data: SSB, Oslo B&oslash;rs, BarentsWatch, FRED, Copernicus CMEMS.
        Updated every 30 minutes. Not financial advice.
      </p>
    </div>
  );
}

/* ─── Early Warning Card ──────────────────────────────────────────── */
function EarlyWarningCard({ section, anomalyData }: { section: BriefSection; anomalyData: AnomalyScores | null }) {
  const { t } = useTranslation();
  const severity = extractSeverity(section.headline ?? "");
  const badge = SEVERITY_BADGE[severity] || SEVERITY_BADGE.LOW;

  // Parse the anomaly component breakdown (real key: component_scores —
  // the old code read `breakdown`, so the Key Risks bars never rendered).
  const breakdown: Record<string, number> = anomalyData?.component_scores ?? {};
  const categories = Object.entries(breakdown).filter(
    ([, val]) => typeof val === "number" && val > 0
  );
  const sources = Array.from(
    new Set((anomalyData?.anomalies ?? []).map((a) => a.source).filter(Boolean) as string[])
  );

  return (
    <GlassCard>
      <div className="flex items-center gap-3 mb-3">
        <div className="w-8 h-8 rounded-lg bg-amber-500/10 flex items-center justify-center">
          <AlertTriangle className="w-4 h-4 text-amber-400" />
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-semibold text-[var(--text-secondary)] uppercase tracking-wider">
              Early Warning System
            </span>
            <span className={`text-[9px] font-bold uppercase px-2 py-0.5 rounded-full ring-1 ${badge.bg} ${badge.text} ${badge.ring}`}>
              {severity}
            </span>
          </div>
        </div>
        {anomalyData?.composite_score != null && (
          <div className="text-right">
            <span className={`text-xl font-bold font-mono ${
              anomalyData.composite_score >= 70 ? "text-rose-400" :
              anomalyData.composite_score >= 50 ? "text-orange-400" :
              anomalyData.composite_score >= 30 ? "text-amber-400" :
              "text-emerald-400"
            }`}>
              {anomalyData.composite_score}
            </span>
            <span className="text-[10px] text-[var(--text-secondary)]">/100</span>
          </div>
        )}
      </div>

      <p className="text-[13px] font-medium text-[var(--text-primary)] leading-snug mb-2">
        {section.headline}
      </p>
      {section.detail && (
        <p className="text-[11px] text-[var(--text-secondary)] leading-relaxed mb-3">
          {section.detail}
        </p>
      )}

      {/* Anomaly breakdown bars */}
      {categories.length > 0 && (
        <div className="space-y-2 pt-2 border-t border-white/[0.06]">
          <p className="text-[10px] text-[var(--text-secondary)] uppercase tracking-wider">{t("brief.key_risks")}</p>
          {categories.map(([key, score]) => {
            const barColor = score >= 70 ? "bg-rose-500" : score >= 50 ? "bg-orange-500" : score >= 30 ? "bg-amber-500" : "bg-emerald-500";
            return (
              <div key={key} className="flex items-center gap-2">
                <span className="text-[10px] text-[var(--text-secondary)] w-20 truncate capitalize">
                  {key.replace(/_/g, " ")}
                </span>
                <div className="flex-1 h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
                  <div
                    className={`h-full rounded-full ${barColor} transition-all duration-500`}
                    style={{ width: `${Math.min(score, 100)}%` }}
                  />
                </div>
                <span className="text-[10px] font-mono text-[var(--text-secondary)] w-8 text-right">
                  {score}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* Source attribution (real key: anomalies[].source — the old code
          read a nonexistent `sources` array) */}
      {sources.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {sources.map((src) => (
            <span key={src} className="text-[9px] px-1.5 py-0.5 rounded bg-white/[0.04] text-[var(--text-secondary)]">
              {src}
            </span>
          ))}
        </div>
      )}
    </GlassCard>
  );
}

/* ─── ESG Movers Card ─────────────────────────────────────────────── */
function EsgMoversCard({ section }: { section: BriefSection }) {
  const movers = parseEsgMovers(section.detail ?? "");
  const isStable = section.sentiment === "neutral" && movers.length === 0;

  return (
    <GlassCard>
      <div className="flex items-center gap-3 mb-3">
        <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center">
          <Leaf className="w-4 h-4 text-emerald-400" />
        </div>
        <span className="text-[11px] font-semibold text-[var(--text-secondary)] uppercase tracking-wider">
          ESG Movers
        </span>
      </div>

      <p className="text-[13px] font-medium text-[var(--text-primary)] leading-snug mb-3">
        {section.headline}
      </p>

      {movers.length > 0 ? (
        <div className="space-y-2">
          {movers.map((m, i) => {
            const improving = m.delta > 0;
            return (
              <div
                key={m.name}
                className={`flex items-center gap-3 p-2.5 rounded-lg border ${
                  improving
                    ? "bg-emerald-500/[0.04] border-emerald-500/15"
                    : "bg-rose-500/[0.04] border-rose-500/15"
                }`}
              >
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] font-bold text-[var(--text-secondary)] w-5">
                    #{i + 1}
                  </span>
                  {improving ? (
                    <ArrowUpRight className="w-3.5 h-3.5 text-emerald-400" />
                  ) : (
                    <ArrowDownRight className="w-3.5 h-3.5 text-rose-400" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <span className="text-[12px] font-medium text-[var(--text-primary)] truncate block">
                    {m.name}
                  </span>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <span className={`text-[12px] font-bold font-mono ${
                    improving ? "text-emerald-400" : "text-rose-400"
                  }`}>
                    {improving ? "+" : ""}{m.delta.toFixed(1)}
                  </span>
                  <div className="w-px h-3 bg-white/[0.1]" />
                  <span className="text-[11px] font-mono text-[var(--text-secondary)]">
                    {m.score.toFixed(0)}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      ) : isStable ? (
        <p className="text-[11px] text-[var(--text-secondary)]">
          All ESG scores within normal range. No significant day-over-day movements.
        </p>
      ) : null}
    </GlassCard>
  );
}
