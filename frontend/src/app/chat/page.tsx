/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Bot, Send, Circle, Zap, Activity, Fish } from "lucide-react";
import GlassCard from "@/components/GlassCard";
import { OcButton } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";

// ─────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────

interface Message {
  id: string;
  role: "user" | "ai";
  content: string;
  timestamp: Date;
}

interface ContextStatus {
  liceActive: boolean;
  pricesActive: boolean;
  signalCount: number;
}

// ─────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────

function genId(): string {
  return Math.random().toString(36).slice(2, 10);
}

function formatNum(n: number, decimals = 1): string {
  return n.toFixed(decimals);
}

function formatLice(n: number): string {
  return n.toFixed(3);
}

/** Render **bold** markdown spans inline */
function BoldText({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith("**") && part.endsWith("**")) {
          return (
            <strong key={i} className="text-ocean-300 font-semibold">
              {part.slice(2, -2)}
            </strong>
          );
        }
        return <span key={i}>{part}</span>;
      })}
    </>
  );
}

/** Render multi-line AI message with bold + bullet + heading support */
function AIMessageContent({ content }: { content: string }) {
  const lines = content.split("\n");
  return (
    <div className="space-y-1 leading-relaxed text-sm text-white/80">
      {lines.map((line, i) => {
        if (line === "") return <div key={i} className="h-1" />;
        // Standalone heading: entire line is **text**
        if (/^\*\*[^*]+\*\*$/.test(line.trim())) {
          return (
            <p key={i} className="font-semibold text-white/95 mt-2 text-[13px]">
              {line.trim().slice(2, -2)}
            </p>
          );
        }
        // Bullet point
        if (/^- /.test(line)) {
          return (
            <div key={i} className="flex items-start gap-1.5">
              <span className="text-ocean-400 mt-0.5 flex-shrink-0 select-none">•</span>
              <p><BoldText text={line.slice(2)} /></p>
            </div>
          );
        }
        return <p key={i}><BoldText text={line} /></p>;
      })}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────
// Smart AI response engine
// ─────────────────────────────────────────────────────────────────

// State to carry follow-up suggestions out of getAIResponse
let _lastFollowUps: string[] = [];

async function getAIResponse(message: string): Promise<string> {
  // ── Primary: use server-side intelligence chat endpoint ───────────
  try {
    const result = await api.chat(message);
    const text = result?.answer || result?.response;
    if (text) {
      _lastFollowUps = result.follow_up || [];
      return text;
    }
  } catch {
    // Fall through to client-side fallback
  }

  // ── Fallback: lightweight client-side rule-based responses ────────
  const isLice = /lice|sea lice|caligus|parasite/i.test(message);
  const isPrice = /price|market|nok|eur|salmon|cost|value|spot/i.test(message);
  const isSignal = /signal|trade|trading|buy|sell|position|alert/i.test(message);
  const isRisk = /risk|farm|locality|exposure|high.risk|dangerous/i.test(message);
  const isRegime = /regime|regulation|regulatory|barentswatch|authority|zone|production area/i.test(message);
  const isForecast = /forecast|predict|outlook|future|expect|model|projection/i.test(message);

  try {
    if (isLice) {
      const data = await api.liceSummary();
      const areas: any[] = data?.production_areas ?? data?.areas ?? [];
      const overall: any = data?.overall ?? data?.summary ?? {};
      const avgLice: number = overall?.avg_lice ?? overall?.average_lice ?? 0;
      const threshold: number = overall?.threshold ?? 0.5;
      const aboveThreshold: number = overall?.above_threshold ?? overall?.farms_above ?? 0;

      let resp = `**Sea Lice Intelligence Report**\n\n`;
      resp += `Current average lice count across Norwegian production areas: **${formatLice(avgLice)} lice/fish** (regulatory threshold: ${formatLice(threshold)}).\n`;

      if (aboveThreshold > 0) {
        resp += `\n⚠ **${aboveThreshold} farms** are currently above the treatment threshold.\n`;
      } else {
        resp += `\nAll monitored farms are currently within regulatory limits.\n`;
      }

      if (areas.length > 0) {
        resp += `\n**Production Area Breakdown:**\n`;
        areas.slice(0, 6).forEach((a: any) => {
          const name = a.name ?? a.area_name ?? `PA ${a.pa ?? a.id}`;
          const count: number = a.avg_lice ?? a.lice_count ?? a.value ?? 0;
          const status = count > threshold ? "⚠ Above limit" : "✓ Within limit";
          resp += `  • ${name}: **${formatLice(count)}** — ${status}\n`;
        });
      }

      resp += `\nData sourced from BarentsWatch weekly lice monitoring. Updated every 7 days.`;
      return resp;
    }

    if (isPrice) {
      const data = await api.intelligenceSummary();
      const prices: any = data?.prices ?? data?.market ?? {};
      const spot: number = prices?.spot ?? prices?.current ?? prices?.spot_price ?? 0;
      const weekChange: number = prices?.week_change ?? prices?.weekly_change ?? 0;
      const outlook: string = prices?.outlook ?? prices?.trend ?? "";

      let resp = `**Salmon Market Intelligence**\n\n`;

      if (spot > 0) {
        resp += `Current NorSalmon spot price: **NOK ${formatNum(spot, 1)}/kg**.\n`;
        if (weekChange !== 0) {
          const dir = weekChange > 0 ? "up" : "down";
          resp += `Prices are **${dir} ${formatNum(Math.abs(weekChange), 1)}%** from last week.\n`;
        }
      } else {
        resp += `Live price data is sourced from SSB and Fish Pool Index.\n`;
      }

      resp += `\n**Key Market Drivers:**\n`;
      resp += `  • Norwegian harvest volumes and seasonal supply cycles\n`;
      resp += `  • European and Asian export demand dynamics\n`;
      resp += `  • Lice treatment pressure reducing harvest capacity\n`;
      resp += `  • Currency movements (EUR/NOK)\n`;

      if (outlook) {
        resp += `\n**Near-term outlook:** ${outlook.charAt(0).toUpperCase() + outlook.slice(1)}. Our ML price model runs Monte Carlo across 1,000 scenarios.`;
      }

      return resp;
    }

    if (isSignal) {
      const data = await api.signals();
      const signals: any[] = Array.isArray(data) ? data : (data?.signals ?? []);
      const active = signals.filter(
        (s: any) => s.status === "active" || s.status === "pending" || !s.status
      );

      if (active.length === 0) {
        return `**Trading Signals**\n\nNo active trading signals at this time. FishIntel monitors Norwegian aquaculture equities for momentum, mean-reversion, and lice-driven supply shocks.\n\nSignals are generated when statistical confidence exceeds our threshold. Check back shortly or view the Signals dashboard for historical performance.`;
      }

      let resp = `**Active Trading Signals** (${active.length} total)\n\n`;
      active.slice(0, 3).forEach((s: any, i: number) => {
        const ticker = s.ticker ?? s.symbol ?? s.company ?? "Unknown";
        const direction = s.direction ?? s.signal ?? s.type ?? "—";
        const confidence: number = s.confidence ?? s.score ?? 0;
        const reason: string = s.reason ?? s.rationale ?? s.notes ?? "";
        resp += `**${i + 1}. ${ticker}** — ${String(direction).toUpperCase()}\n`;
        if (confidence > 0) {
          resp += `   Confidence: **${formatNum(confidence * 100, 0)}%**\n`;
        }
        if (reason) {
          resp += `   Rationale: ${reason}\n`;
        }
        resp += `\n`;
      });

      resp += `FishIntel signals combine lice data, supply forecasts, sentiment analysis, and statistical pair relationships.`;
      return resp;
    }

    if (isRisk) {
      const data = await api.intelligenceSummary();
      const farms: any[] = data?.high_risk_farms ?? data?.risk_farms ?? data?.farms ?? [];
      const riskSummary: any = data?.risk ?? {};

      let resp = `**Farm Risk Assessment**\n\n`;

      if (farms.length > 0) {
        resp += `**Highest Risk Localities:**\n`;
        farms.slice(0, 5).forEach((f: any) => {
          const name = f.name ?? f.locality ?? `Locality ${f.locality_no ?? f.id}`;
          const score: number = f.risk_score ?? f.score ?? f.lice ?? 0;
          const flag: string = f.flag ?? f.issue ?? "";
          resp += `  • **${name}** — Risk score: ${formatNum(score, 1)}`;
          if (flag) resp += ` (${flag})`;
          resp += `\n`;
        });
      } else {
        resp += `Risk data aggregates lice counts, bloom alerts, vessel signals, and regulatory regime states.\n`;
      }

      const cascades = riskSummary?.cascade_risk ?? riskSummary?.network_risk ?? null;
      if (cascades) {
        resp += `\n**Network Cascade Risk:** ${cascades}. Farm-to-farm lice transmission is modeled via our graph neural network.\n`;
      }

      resp += `\nRisk factors include: sea lice pressure, algal bloom proximity, vessel treatment activity, and regulatory zone classification.`;
      return resp;
    }

    if (isRegime) {
      const data = await api.intelligenceSummary();
      const regimes: any[] = data?.regimes ?? data?.regime_states ?? [];

      let resp = `**Regulatory Regime Intelligence**\n\n`;
      resp += `Norway's aquaculture production areas use a traffic light system:\n`;
      resp += `  • **Red zones** — capacity must decrease 6%\n`;
      resp += `  • **Yellow zones** — no change, under monitoring\n`;
      resp += `  • **Green zones** — capacity may increase 6%\n\n`;

      if (Array.isArray(regimes) && regimes.length > 0) {
        resp += `**Current Zone Status:**\n`;
        regimes.slice(0, 6).forEach((r: any) => {
          const pa = r.pa ?? r.production_area ?? r.id ?? "—";
          const name = r.name ?? r.area ?? `Production Area ${pa}`;
          const color: string = r.color ?? r.status ?? r.regime ?? "yellow";
          const emoji = color === "red" ? "🔴" : color === "green" ? "🟢" : "🟡";
          resp += `  ${emoji} PA ${pa} — ${name}: **${color.toUpperCase()}**\n`;
        });
      } else {
        resp += `Live regime data is sourced from BarentsWatch, updated each regulatory cycle.\n`;
      }

      resp += `\nRegime classifications directly affect equity valuations — a red zone reduces production license value.`;
      return resp;
    }

    if (isForecast) {
      const data = await api.intelligenceSummary();
      const priceOutlook: any = data?.price_outlook ?? {};
      const forecast: any = data?.forecast ?? data?.supply_forecast ?? {};

      let resp = `**Intelligence Forecast Summary**\n\n`;
      resp += `FishIntel runs multiple predictive models in parallel:\n\n`;
      resp += `**1. Supply Forecast**\n`;
      resp += `  ML models trained on Norwegian slaughter volumes, sea temperature, and lice treatment cycles.\n\n`;
      resp += `**2. Price Outlook**\n`;

      const horizon: number = priceOutlook?.horizon ?? 4;
      const scenarios: number = priceOutlook?.scenarios ?? 1000;
      resp += `  Monte Carlo simulation: **${scenarios.toLocaleString()} scenarios** over **${horizon}-week horizon**.\n\n`;

      resp += `**3. Lice GNN Predictions**\n`;
      resp += `  Graph Neural Network models lice spread across the farm network via ocean currents and treatment cascades.\n\n`;

      const bias: string = forecast?.bias ?? priceOutlook?.bias ?? "";
      if (bias) {
        resp += `**Current Forecast Bias:** ${bias}\n\n`;
      }

      resp += `Navigate to **Forecast** or **Price Outlook** in the sidebar for interactive charts and scenario breakdowns.`;
      return resp;
    }

    // General fallback
    const data = await api.intelligenceSummary();
    const signalCount: number = data?.signal_count ?? data?.active_signals ?? 0;
    const avgLice: number = data?.avg_lice ?? data?.lice?.average ?? 0;

    let resp = `**FishIntel Intelligence Overview**\n\n`;
    resp += `I'm here to help navigate Norwegian salmon market intelligence. Live status:\n\n`;

    if (signalCount > 0) {
      resp += `  • **${signalCount} active trading signals** across Norwegian aquaculture equities\n`;
    }
    if (avgLice > 0) {
      resp += `  • **Average lice count:** ${formatLice(avgLice)} lice/fish across production areas\n`;
    }

    resp += `  • Real-time price tracking via Fish Pool Index and SSB data\n`;
    resp += `  • Regulatory regime monitoring across 13 production areas\n`;
    resp += `  • AIS vessel tracking for harvest and treatment activity\n\n`;
    resp += `Ask me about **lice levels**, **salmon prices**, **trading signals**, **farm risk**, **regulatory regimes**, or **supply forecasts**. What would you like to explore?`;
    return resp;
  } catch {
    return `I encountered an issue reaching the FishIntel data services right now. The API endpoint may be temporarily unavailable.\n\nYou can try:\n  • Refreshing the page to re-establish the data connection\n  • Checking system health in the Settings panel\n  • Browsing the dashboards directly for live data\n\nI'll respond normally once the data services reconnect.`;
  }
}

// ─────────────────────────────────────────────────────────────────
// Suggested question chips
// ─────────────────────────────────────────────────────────────────

const SUGGESTIONS = [
  { label: "What's the current lice situation?", icon: Fish },
  { label: "Show me active trading signals", icon: Zap },
  { label: "What's driving salmon prices?", icon: Activity },
  { label: "Which farms have the highest risk?", icon: Circle },
] as const;

// ─────────────────────────────────────────────────────────────────
// Thinking indicator
// ─────────────────────────────────────────────────────────────────

function ThinkingDots() {
  return (
    <div className="flex items-center gap-1 py-0.5">
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="w-1.5 h-1.5 rounded-full bg-ocean-400"
          animate={{ opacity: [0.3, 1, 0.3], scale: [0.8, 1.1, 0.8] }}
          transition={{
            duration: 1,
            repeat: Infinity,
            delay: i * 0.18,
            ease: "easeInOut",
          }}
        />
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────
// Message bubble
// ─────────────────────────────────────────────────────────────────

function MessageBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === "user";
  const [showTime, setShowTime] = useState(false);

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.32, ease: "easeOut" }}
      className={`flex gap-3 ${isUser ? "flex-row-reverse" : "flex-row"}`}
    >
      {/* Avatar — AI only */}
      {!isUser && (
        <div className="flex-shrink-0 mt-1">
          <div className="w-8 h-8 rounded-xl bg-ocean-500/20 border border-ocean-500/30 flex items-center justify-center">
            <Bot className="w-4 h-4 text-ocean-400" />
          </div>
        </div>
      )}

      {/* Bubble */}
      <div
        className={`relative max-w-[78%] flex flex-col ${isUser ? "items-end" : "items-start"}`}
        onMouseEnter={() => setShowTime(true)}
        onMouseLeave={() => setShowTime(false)}
      >
        <div
          className={`px-4 py-3 rounded-2xl text-sm leading-relaxed ${
            isUser
              ? "bg-ocean-500/20 border border-ocean-500/25 text-white rounded-tr-sm"
              : "bg-white/[0.05] border border-white/[0.07] rounded-tl-sm"
          }`}
        >
          {isUser ? (
            <span className="text-white/90">{msg.content}</span>
          ) : (
            <AIMessageContent content={msg.content} />
          )}
        </div>

        {/* Timestamp on hover */}
        <AnimatePresence>
          {showTime && (
            <motion.span
              initial={{ opacity: 0, y: -3 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -3 }}
              transition={{ duration: 0.13 }}
              className={`text-[10px] text-white/25 mt-1 px-1 ${isUser ? "text-right" : "text-left"}`}
            >
              {msg.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
            </motion.span>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}

// ─────────────────────────────────────────────────────────────────
// Initial greeting message
// ─────────────────────────────────────────────────────────────────

const GREETING: Message = {
  id: "greeting",
  role: "ai",
  content:
    "Hello! I'm FishIntel's intelligence assistant. I can answer questions about lice levels, salmon prices, trading signals, regulatory regimes, and market conditions. What would you like to know?",
  timestamp: new Date(),
};

// ─────────────────────────────────────────────────────────────────
// Chat page
// ─────────────────────────────────────────────────────────────────

export default function ChatPage() {
  const { t } = useTranslation();
  const [messages, setMessages] = useState<Message[]>([GREETING]);
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const [briefingLoading, setBriefingLoading] = useState(false);
  const [contextStatus, setContextStatus] = useState<ContextStatus>({
    liceActive: false,
    pricesActive: false,
    signalCount: 0,
  });

  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const hasOnlyGreeting = messages.length === 1 && messages[0].id === "greeting";

  const generateBriefing = async () => {
    setBriefingLoading(true);
    try {
      const result = await api.chatBriefing({ pas: [3, 4, 5, 6], companies: ["Mowi", "SalMar", "Lerøy"] });
      setMessages((prev: any[]) => [...prev, {
        id: genId(),
        role: "ai",
        content: result.briefing || "Briefing generated.",
        timestamp: new Date(),
      }]);
    } catch { /* empty */ }
    setBriefingLoading(false);
  };

  // Fetch context status on mount
  useEffect(() => {
    api
      .intelligenceSummary()
      .then((data: any) => {
        setContextStatus({
          liceActive: true,
          pricesActive: !!(data?.prices || data?.market || data?.spot_price),
          signalCount: data?.signal_count ?? data?.active_signals ?? 0,
        });
      })
      .catch(() => {
        // Context bar stays with defaults on failure
      });
  }, []);

  // Scroll to bottom whenever messages or thinking state changes
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, thinking]);

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || thinking) return;

      const userMsg: Message = {
        id: genId(),
        role: "user",
        content: trimmed,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, userMsg]);
      setInput("");
      setThinking(true);

      // Simulated thinking delay: 800–1500 ms
      const delay = 800 + Math.random() * 700;
      await new Promise((resolve) => setTimeout(resolve, delay));

      const responseText = await getAIResponse(trimmed);

      const aiMsg: Message = {
        id: genId(),
        role: "ai",
        content: responseText,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, aiMsg]);
      setThinking(false);

      setTimeout(() => inputRef.current?.focus(), 60);
    },
    [thinking]
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-[#040d14] text-white overflow-hidden">
      {/* ── Header ──────────────────────────────────────────────── */}
      <div className="flex-shrink-0 border-b border-white/[0.06] bg-white/[0.02] backdrop-blur-md px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-ocean-500/15 border border-ocean-500/25 flex items-center justify-center">
            <Bot className="w-5 h-5 text-ocean-400" />
          </div>
          <div>
            <h1 className="text-base font-semibold text-white tracking-tight">
              {t("nav.ai_chat")}
            </h1>
            <p className="text-xs text-white/35 mt-0.5">Powered by FishIntel Intelligence</p>
          </div>

          {/* Live badge */}
          <div className="ml-auto flex items-center gap-2">
            <motion.span
              className="w-2 h-2 rounded-full bg-emerald-400"
              animate={{ opacity: [1, 0.35, 1] }}
              transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut" }}
            />
            <span className="text-[11px] text-white/35 font-mono">LIVE</span>
          </div>
        </div>
      </div>

      {/* ── Message list ────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-4 md:px-8 py-6 space-y-5 scroll-smooth">
        <AnimatePresence initial={false}>
          {messages.map((msg) => (
            <MessageBubble key={msg.id} msg={msg} />
          ))}
        </AnimatePresence>

        {/* Thinking bubble */}
        <AnimatePresence>
          {thinking && (
            <motion.div
              key="thinking"
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 14 }}
              transition={{ duration: 0.25 }}
              className="flex items-start gap-3"
            >
              <div className="flex-shrink-0 mt-1 w-8 h-8 rounded-xl bg-ocean-500/20 border border-ocean-500/30 flex items-center justify-center">
                <Bot className="w-4 h-4 text-ocean-400" />
              </div>
              <div className="bg-white/[0.05] border border-white/[0.07] rounded-2xl rounded-tl-sm px-4 py-3.5">
                <ThinkingDots />
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Suggestion chips — only visible with just the greeting */}
        <AnimatePresence>
          {hasOnlyGreeting && !thinking && (
            <motion.div
              key="suggestions"
              initial={{ opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 10 }}
              transition={{ duration: 0.4, delay: 0.25 }}
              className="pt-2"
            >
              <p className="text-[11px] text-white/25 mb-3 pl-11 tracking-wide uppercase">
                Suggested questions
              </p>
              <div className="flex flex-wrap gap-2 pl-11">
                {SUGGESTIONS.map(({ label, icon: Icon }) => (
                  <button
                    key={label}
                    onClick={() => sendMessage(label)}
                    className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs text-ocean-300 bg-ocean-500/[0.07] border border-ocean-500/20 hover:bg-ocean-500/[0.14] hover:border-ocean-500/30 transition-all duration-200 cursor-pointer"
                    aria-label={`Ask: ${label}`}
                  >
                    <Icon className="w-3 h-3 opacity-60" />
                    {label}
                  </button>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <div ref={bottomRef} />
      </div>

      {/* ── Context status bar ──────────────────────────────────── */}
      <div className="flex-shrink-0 border-t border-white/[0.04] bg-white/[0.01] px-6 py-2 flex items-center gap-6">
        <div className="flex items-center gap-1.5">
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              contextStatus.liceActive ? "bg-emerald-400" : "bg-white/20"
            }`}
          />
          <span className="text-[11px] text-white/30">Lice data: live</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              contextStatus.pricesActive ? "bg-emerald-400" : "bg-white/20"
            }`}
          />
          <span className="text-[11px] text-white/30">Prices: live</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-ocean-400/80" />
          <span className="text-[11px] text-white/30">
            Signals:{" "}
            <span className="text-ocean-400 font-medium">
              {contextStatus.signalCount} active
            </span>
          </span>
        </div>
      </div>

      {/* ── Quick Actions ──────────────────────────────────────── */}
      <div className="flex-shrink-0 px-4 md:px-6 pt-3 pb-1">
        <div className="flex flex-wrap gap-2">
          <OcButton variant="primary" size="sm" loading={briefingLoading}
            onClick={generateBriefing} leftIcon={<Zap className="w-3.5 h-3.5" />}>
            Generate Briefing
          </OcButton>
          {["Why did lice spike in PA-6?", "What is the price outlook?", "Show disease risk for Mowi"].map((q) => (
            <button key={q} onClick={() => { setInput(q); }}
              className="text-[11px] px-3 py-1.5 rounded-full bg-white/[0.04] border border-white/[0.06] text-[var(--text-secondary)] hover:text-ocean-400 hover:border-ocean-500/30 transition-colors"
              aria-label={`Set question: ${q}`}>
              {q}
            </button>
          ))}
        </div>
      </div>

      {/* ── Input bar ───────────────────────────────────────────── */}
      <div className="flex-shrink-0 border-t border-white/[0.06] bg-white/[0.02] backdrop-blur-md px-4 md:px-6 py-4">
        <GlassCard className="p-0 flex items-end gap-2" hover={false} accent="none">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={thinking}
            rows={1}
            placeholder="Ask about lice levels, salmon prices, trading signals…"
            className={[
              "flex-1 resize-none bg-transparent px-4 py-3",
              "text-sm text-white/85 placeholder:text-white/22",
              "focus:outline-hidden leading-relaxed",
              "min-h-[46px] max-h-[130px] overflow-y-auto",
              "disabled:opacity-40 disabled:cursor-not-allowed",
            ].join(" ")}
          />
          <div className="flex-shrink-0 pr-3 pb-3">
            <OcButton
              variant="primary"
              size="icon_md"
              disabled={thinking || !input.trim()}
              onClick={() => sendMessage(input)}
              aria-label="Send message"
            >
              <Send className="w-4 h-4" />
            </OcButton>
          </div>
        </GlassCard>
        <p className="text-[10px] text-white/18 text-center mt-2 select-none">
          Enter to send · Shift+Enter for new line
        </p>
      </div>
    </div>
  );
}
