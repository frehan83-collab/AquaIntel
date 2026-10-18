"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  AlertTriangle,
  BellPlus,
  Bot,
  Check,
  ChevronDown,
  Copy,
  Database,
  Loader2,
  Lock,
  Send,
  ShieldCheck,
  Sparkles,
  User,
} from "lucide-react";
import GlassCard from "@/components/GlassCard";
import { api } from "@/lib/api";
import type {
  ChatAnswerResponse,
  ChatFactSource,
  ChatHistoryTurn,
  ChatSaveAlertResponse,
  ChatUsageStatus,
  WorkbenchCatalog,
  WorkbenchDocument,
} from "@/types/api";

const SUGGESTIONS = [
  "What is the margin per kg right now?",
  "When was the last verified lice report?",
  "How old is the newest chlorophyll scene?",
  "Which origin is cheapest to land in the US?",
];

const PROVENANCE_STYLE: Record<string, string> = {
  live: "bg-emerald-400/10 text-emerald-300 border-emerald-400/20",
  degraded: "bg-amber-400/10 text-amber-300 border-amber-400/20",
  stale: "bg-rose-400/10 text-rose-300 border-rose-400/20",
  unavailable: "bg-white/5 text-[var(--text-secondary)] border-white/10",
};

interface Turn {
  id: string;
  role: "user" | "assistant";
  text: string;
  answer?: ChatAnswerResponse;
  pending?: boolean;
}

function newId(): string {
  return Math.random().toString(36).slice(2, 10);
}

function provenanceLabel(value: string): string {
  if (value === "live") return "live";
  if (value === "degraded") return "modelled";
  if (value === "stale") return "stale";
  return "missing";
}

function SourceRow({ source }: { source: ChatFactSource }) {
  return (
    <li className="flex items-start gap-2 border-b border-white/[0.04] py-1.5 last:border-0">
      <span
        className={`mt-0.5 shrink-0 rounded-md border px-1.5 py-0.5 text-[9px] uppercase tracking-wide ${
          PROVENANCE_STYLE[source.provenance] || PROVENANCE_STYLE.unavailable
        }`}
      >
        {provenanceLabel(source.provenance)}
      </span>
      <span className="min-w-0">
        <span className="block text-[11px] leading-snug text-[var(--text-primary)]">
          {source.label}
        </span>
        <span className="block text-[10px] leading-snug text-[var(--text-secondary)]">
          {source.source}
          {source.as_of ? ` · as of ${source.as_of}` : ""}
          {source.age_days != null ? ` · ${source.age_days}d old` : ""}
        </span>
      </span>
    </li>
  );
}

function AnswerCard({
  answer,
  onSaveAlert,
  saved,
}: {
  answer: ChatAnswerResponse;
  onSaveAlert: (question: string) => Promise<ChatSaveAlertResponse | null>;
  saved: ChatSaveAlertResponse | null;
}) {
  const [showSources, setShowSources] = useState(false);
  const [copied, setCopied] = useState(false);
  const [saving, setSaving] = useState(false);

  const copy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(answer.answer);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable — no state change */
    }
  }, [answer.answer]);

  const save = useCallback(async () => {
    setSaving(true);
    try {
      await onSaveAlert(answer.question);
    } finally {
      setSaving(false);
    }
  }, [answer.question, onSaveAlert]);

  const numbersOnly = answer.mode === "grounded_fallback";

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-[10px]">
        <span className="inline-flex items-center gap-1 rounded-md border border-ocean-400/20 bg-ocean-400/10 px-1.5 py-0.5 text-ocean-300">
          <ShieldCheck className="h-3 w-3" />
          {answer.mode === "refusal" ? "policy answer" : numbersOnly ? "numbers only" : "grounded"}
        </span>
        {answer.degraded && !numbersOnly ? (
          <span className="inline-flex items-center gap-1 rounded-md border border-amber-400/20 bg-amber-400/10 px-1.5 py-0.5 text-amber-300">
            <AlertTriangle className="h-3 w-3" /> some data is old
          </span>
        ) : null}
        {answer.latency_ms ? (
          <span className="text-[var(--text-secondary)]">{Math.round(answer.latency_ms)} ms</span>
        ) : null}
      </div>

      <div className="whitespace-pre-wrap text-sm leading-relaxed text-[var(--text-primary)]">
        {answer.answer}
      </div>

      <div className="flex flex-wrap items-center gap-2 pt-1">
        {answer.sources?.length ? (
          <button
            type="button"
            onClick={() => setShowSources((value) => !value)}
            aria-expanded={showSources}
            className="inline-flex items-center gap-1 rounded-lg border border-white/10 bg-white/[0.03] px-2 py-1 text-[10px] text-[var(--text-secondary)] hover:bg-white/[0.06]"
          >
            <Database className="h-3 w-3" />
            {answer.sources.length} sources
            <ChevronDown
              className={`h-3 w-3 transition-transform ${showSources ? "rotate-180" : ""}`}
            />
          </button>
        ) : null}
        <button
          type="button"
          onClick={copy}
          className="inline-flex items-center gap-1 rounded-lg border border-white/10 bg-white/[0.03] px-2 py-1 text-[10px] text-[var(--text-secondary)] hover:bg-white/[0.06]"
        >
          {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
          {copied ? "copied" : "copy"}
        </button>
        {answer.mode !== "refusal" && answer.mode !== "unavailable" ? (
          <button
            type="button"
            onClick={save}
            disabled={saving}
            className="inline-flex items-center gap-1 rounded-lg border border-ocean-400/20 bg-ocean-400/10 px-2 py-1 text-[10px] text-ocean-300 hover:bg-ocean-400/20 disabled:opacity-50"
          >
            {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <BellPlus className="h-3 w-3" />}
            watch this
          </button>
        ) : null}
      </div>

      <AnimatePresence initial={false}>
        {showSources ? (
          <motion.ul
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden rounded-lg border border-white/[0.06] bg-black/20 px-2"
          >
            {answer.sources.map((source) => (
              <SourceRow key={source.key} source={source} />
            ))}
          </motion.ul>
        ) : null}
      </AnimatePresence>

      {saved ? (
        <div
          className={`rounded-lg border px-2.5 py-2 text-[11px] ${
            saved.saved
              ? "border-emerald-400/20 bg-emerald-400/10 text-emerald-200"
              : "border-amber-400/20 bg-amber-400/10 text-amber-200"
          }`}
        >
          {saved.message}
        </div>
      ) : null}
    </div>
  );
}

function AllowanceMeter({ usage }: { usage: ChatUsageStatus | null }) {
  if (!usage) return null;
  const unlimited = usage.unlimited;
  const allowance = usage.allowance;
  const used = usage.used ?? 0;
  const pct = unlimited ? 8 : allowance > 0 ? Math.min(100, (used / allowance) * 100) : 100;
  const tone = unlimited || pct < 70 ? "bg-emerald-400" : pct < 95 ? "bg-amber-400" : "bg-rose-400";
  return (
    <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-2.5">
      <div className="flex items-baseline justify-between">
        <p className="text-[10px] uppercase tracking-wide text-[var(--text-secondary)]">
          {usage.plan_name || usage.plan} allowance
        </p>
        <p className="text-[11px] font-semibold text-[var(--text-primary)]">
          {unlimited ? "unlimited" : `${used} / ${allowance}`}
        </p>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
        <div className={`h-full rounded-full ${tone}`} style={{ width: `${pct}%` }} />
      </div>
      <p className="mt-1.5 text-[9px] text-[var(--text-secondary)]">
        {unlimited
          ? "fair-use metered; no monthly cap on this plan"
          : `resets ${usage.resets_on}${
              usage.cost_usd ? ` · $${usage.cost_usd.toFixed(2)} of model cost this month` : ""
            }`}
      </p>
    </div>
  );
}

function LockedPanel({
  payload,
  usage,
}: {
  payload: Record<string, unknown> | null;
  usage: ChatUsageStatus | null;
}) {
  const message =
    (payload?.message as string) ||
    "Grounded chat is included from Operator upwards: 100 questions a month on Operator, 300 on Desk.";
  const upgrade = (payload?.upgrade_url as string) || "/billing";
  const planName = (payload?.suggested_plan_name as string) || "Operator";
  return (
    <GlassCard delay={0.1}>
      <div className="flex items-start gap-3">
        <div className="rounded-xl border border-amber-400/20 bg-amber-400/10 p-2">
          <Lock className="h-5 w-5 text-amber-300" />
        </div>
        <div className="min-w-0 flex-1">
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">
            Chat is a paid surface, and it says why
          </h2>
          <p className="mt-1 text-xs leading-relaxed text-[var(--text-secondary)]">{message}</p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <a
              href={upgrade}
              className="rounded-lg bg-ocean-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-ocean-400"
            >
              Add {planName}
            </a>
            <a
              href="/accuracy"
              className="rounded-lg border border-white/10 px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-white/[0.04]"
            >
              See the method first
            </a>
          </div>
          <p className="mt-3 text-[10px] leading-relaxed text-[var(--text-secondary)]">
            Every answer is assembled from the platform&apos;s verified feeds — the feed index,
            the SSB export price, the margin bridge, lice reports, the traffic-light decisions
            and the US tariff register — and each number keeps its observation date. Nothing is
            estimated to fill a gap.
          </p>
        </div>
      </div>
      <div className="mt-3">
        <AllowanceMeter usage={usage} />
      </div>
    </GlassCard>
  );
}


const RUN_ICON = "•";

function DeepAnalysis({
  catalog,
  onRun,
  running,
  document,
  error,
}: {
  catalog: WorkbenchCatalog | null;
  onRun: (kind: string) => void;
  running: string | null;
  document: WorkbenchDocument | null;
  error: string | null;
}) {
  const [open, setOpen] = useState(false);
  if (!catalog) return null;
  const credits = catalog.credits;
  return (
    <GlassCard delay={0.12}>
      <div className="flex items-start justify-between gap-2">
        <div>
          <h2 className="text-xs font-semibold text-[var(--text-primary)]">Deep analysis</h2>
          <p className="mt-1 text-[10px] leading-snug text-[var(--text-secondary)]">
            Documents, not chat turns. Each run reads several engines and writes a short note
            with its sources.
          </p>
        </div>
        <span className="shrink-0 rounded-md border border-white/10 bg-white/[0.03] px-2 py-1 text-[10px] text-[var(--text-secondary)]">
          {credits == null ? "credit ledger unavailable" : `${credits} run${credits === 1 ? "" : "s"}`}
        </span>
      </div>

      <ul className="mt-3 space-y-1.5">
        {catalog.runs.map((run) => (
          <li key={run.key}>
            <button
              type="button"
              onClick={() => onRun(run.key)}
              disabled={running !== null || credits === 0}
              className="w-full rounded-lg border border-white/10 bg-white/[0.02] px-2.5 py-2 text-left hover:bg-white/[0.05] disabled:opacity-50"
            >
              <span className="flex items-center justify-between gap-2">
                <span className="text-[11px] font-semibold text-[var(--text-primary)]">
                  {running === run.key ? "writing…" : run.name}
                </span>
                <span className="text-[9px] text-[var(--text-secondary)]">
                  {run.credits} run
                </span>
              </span>
              <span className="mt-0.5 block text-[10px] leading-snug text-[var(--text-secondary)]">
                {run.blurb}
              </span>
            </button>
          </li>
        ))}
      </ul>

      {credits === 0 ? (
        <p className="mt-2 rounded-lg border border-amber-400/20 bg-amber-400/10 px-2 py-1.5 text-[10px] text-amber-200">
          No runs left. Packs: {catalog.packs.map((pack) => `${pack.runs} for NOK ${pack.price_nok}`).join(" · ")}
          . {catalog.validity_note}
        </p>
      ) : null}
      {error ? (
        <p className="mt-2 rounded-lg border border-rose-400/20 bg-rose-400/10 px-2 py-1.5 text-[10px] text-rose-200">
          {error}
        </p>
      ) : null}

      {document ? (
        <div className="mt-3 rounded-lg border border-white/[0.06] bg-black/20 p-2.5">
          <div className="flex items-center justify-between gap-2">
            <p className="text-[11px] font-semibold text-[var(--text-primary)]">
              {document.title}
            </p>
            <span
              className={`rounded-md border px-1.5 py-0.5 text-[9px] uppercase ${
                document.mode === "model"
                  ? "border-emerald-400/20 bg-emerald-400/10 text-emerald-300"
                  : "border-amber-400/20 bg-amber-400/10 text-amber-300"
              }`}
            >
              {document.mode === "model" ? "model" : "data digest"}
            </span>
          </div>
          <div className="mt-2 max-h-[320px] overflow-y-auto whitespace-pre-wrap text-[11px] leading-relaxed text-[var(--text-primary)]">
            {document.document}
          </div>
          <p className="mt-2 text-[9px] text-[var(--text-secondary)]">{document.charge_note}</p>
          {document.sources.length ? (
            <button
              type="button"
              onClick={() => setOpen((value) => !value)}
              aria-expanded={open}
              className="mt-1 inline-flex items-center gap-1 text-[9px] text-[var(--text-secondary)] underline"
            >
              {document.sources.length} sources
              <ChevronDown className={`h-3 w-3 transition-transform ${open ? "rotate-180" : ""}`} />
            </button>
          ) : null}
          {open ? (
            <ul className="mt-1">
              {document.sources.map((source) => (
                <SourceRow key={source.key} source={source} />
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </GlassCard>
  );
}

export default function ChatPage() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [usage, setUsage] = useState<ChatUsageStatus | null>(null);
  const [locked, setLocked] = useState<Record<string, unknown> | null>(null);
  const [lastSaved, setLastSaved] = useState<Record<string, ChatSaveAlertResponse>>({});
  const [catalog, setCatalog] = useState<WorkbenchCatalog | null>(null);
  const [running, setRunning] = useState<string | null>(null);
  const [document, setDocument] = useState<WorkbenchDocument | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .chatUsage()
      .then((status) => {
        if (!cancelled) setUsage(status);
      })
      .catch(() => {
        /* the meter is not critical to rendering */
      });
    api
      .workbenchCatalog()
      .then((value) => {
        if (!cancelled) setCatalog(value);
      })
      .catch(() => {
        /* the panel simply does not render */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns]);

  const history: ChatHistoryTurn[] = useMemo(
    () =>
      turns
        .filter((turn) => !turn.pending)
        .slice(-6)
        .map((turn) => ({
          role: turn.role === "assistant" ? ("assistant" as const) : ("user" as const),
          content: turn.text,
        })),
    [turns],
  );

  const ask = useCallback(
    async (question: string) => {
      const trimmed = question.trim();
      if (!trimmed || busy) return;
      setBusy(true);
      setInput("");
      setTurns((prev) => [
        ...prev,
        { id: newId(), role: "user", text: trimmed },
        { id: newId(), role: "assistant", text: "", pending: true },
      ]);
      try {
        const result = await api.chat(trimmed, history);
        if (!result.ok) {
          setTurns((prev) => prev.filter((turn) => !turn.pending));
          const body = (result.body as unknown as Record<string, unknown>) || {};
          setLocked(body);
          if (body.chat) setUsage(body.chat as ChatUsageStatus);
          return;
        }
        const answer = result.body as ChatAnswerResponse;
        setTurns((prev) =>
          prev.map((turn) =>
            turn.pending ? { ...turn, pending: false, text: answer.answer, answer } : turn,
          ),
        );
        if (answer.chat) setUsage(answer.chat);
        setLocked(null);
      } catch {
        setTurns((prev) =>
          prev.map((turn) =>
            turn.pending
              ? {
                  ...turn,
                  pending: false,
                  text: "The request failed before it reached the platform. Nothing was charged and no answer was produced.",
                }
              : turn,
          ),
        );
      } finally {
        setBusy(false);
      }
    },
    [busy, history],
  );


  const runAnalysis = useCallback(async (kind: string) => {
    setRunning(kind);
    setRunError(null);
    try {
      const result = await api.workbenchRun(kind);
      if (!result.ok) {
        const body = (result.body as unknown as Record<string, unknown>) || {};
        setRunError(
          (body.message as string) || "That run needs a credit, and none are left on this account.",
        );
        return;
      }
      setDocument(result.body as WorkbenchDocument);
      setCatalog((prev) =>
        prev
          ? { ...prev, credits: (result.body as WorkbenchDocument).credits_after }
          : prev,
      );
    } catch {
      setRunError("The run failed before it reached the platform.");
    } finally {
      setRunning(null);
    }
  }, []);

  const saveAlert = useCallback(async (question: string) => {
    const result = await api.chatSaveAlert(question);
    setLastSaved((prev) => ({ ...prev, [question]: result }));
    return result;
  }, []);

  const suggestions = useMemo(() => {
    const latest = [...turns].reverse().find((turn) => turn.answer?.followups?.length);
    return latest?.answer?.followups?.length ? latest.answer.followups : SUGGESTIONS;
  }, [turns]);

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-semibold text-[var(--text-primary)]">
            <Sparkles className="h-5 w-5 text-ocean-400" />
            Ask the data
          </h1>
          <p className="mt-1 text-xs text-[var(--text-secondary)]">
            Answers are built from verified platform feeds. Every number carries its source and
            observation date, and gaps are named rather than filled.
          </p>
        </div>
        <div className="w-full max-w-[260px]">
          <AllowanceMeter usage={usage} />
        </div>
      </div>

      <div className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-[1fr_280px]">
        <GlassCard delay={0.05} className="flex min-h-[520px] flex-col">
          <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto pr-1">
            {turns.length === 0 && !locked ? (
              <div className="flex h-full flex-col items-center justify-center gap-3 py-10 text-center">
                <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-3">
                  <Bot className="h-6 w-6 text-ocean-300" />
                </div>
                <p className="max-w-sm text-sm text-[var(--text-secondary)]">
                  Ask about lice pressure, the margin bridge, feed costs, bloom coverage,
                  regulation or origin competitiveness. If the data cannot settle it, the answer
                  says what is missing.
                </p>
              </div>
            ) : null}

            {turns.map((turn) =>
              turn.role === "user" ? (
                <div key={turn.id} className="flex justify-end">
                  <div className="max-w-[85%] rounded-2xl rounded-br-md border border-ocean-400/20 bg-ocean-400/10 px-3 py-2">
                    <div className="mb-1 flex items-center gap-1 text-[9px] uppercase tracking-wide text-ocean-300">
                      <User className="h-3 w-3" /> you
                    </div>
                    <p className="whitespace-pre-wrap text-sm text-[var(--text-primary)]">
                      {turn.text}
                    </p>
                  </div>
                </div>
              ) : (
                <div key={turn.id} className="flex gap-2">
                  <div className="mt-1 h-7 w-7 shrink-0 rounded-lg border border-white/10 bg-white/[0.03] p-1.5">
                    <Bot className="h-full w-full text-ocean-300" />
                  </div>
                  <div className="min-w-0 flex-1 rounded-2xl rounded-bl-md border border-white/[0.06] bg-white/[0.02] px-3 py-2.5">
                    {turn.pending ? (
                      <div className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        reading the verified feeds…
                      </div>
                    ) : turn.answer ? (
                      <AnswerCard
                        answer={turn.answer}
                        onSaveAlert={saveAlert}
                        saved={lastSaved[turn.answer.question] || null}
                      />
                    ) : (
                      <p className="text-sm text-[var(--text-primary)]">{turn.text}</p>
                    )}
                  </div>
                </div>
              ),
            )}
          </div>

          <div className="mt-3 border-t border-white/[0.06] pt-3">
            <div className="mb-2 flex flex-wrap gap-1.5">
              {suggestions.slice(0, 4).map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => ask(suggestion)}
                  disabled={busy || Boolean(locked)}
                  className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-[10px] text-[var(--text-secondary)] hover:bg-white/[0.06] disabled:opacity-40"
                >
                  {suggestion}
                </button>
              ))}
            </div>
            <div className="flex items-end gap-2">
              <textarea
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    void ask(input);
                  }
                }}
                rows={2}
                placeholder={
                  locked ? "Chat is not included in your plan" : "Ask a question… (Enter to send)"
                }
                disabled={Boolean(locked)}
                aria-label="Ask a question"
                className="min-h-[52px] flex-1 resize-none rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-secondary)] focus:border-ocean-400/40 focus:outline-none disabled:opacity-50"
              />
              <button
                type="button"
                onClick={() => ask(input)}
                disabled={busy || !input.trim() || Boolean(locked)}
                className="inline-flex h-[52px] items-center gap-1.5 rounded-xl bg-ocean-500 px-4 text-sm font-semibold text-white hover:bg-ocean-400 disabled:opacity-40"
              >
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                Ask
              </button>
            </div>
          </div>
        </GlassCard>

        <div className="space-y-3">
          {locked ? <LockedPanel payload={locked} usage={usage} /> : null}
          <DeepAnalysis
            catalog={catalog}
            onRun={runAnalysis}
            running={running}
            document={document}
            error={runError}
          />
          <GlassCard delay={0.1}>
            <h2 className="text-xs font-semibold text-[var(--text-primary)]">What it reads</h2>
            <ul className="mt-2 space-y-1.5 text-[11px] leading-snug text-[var(--text-secondary)]">
              <li>• Lice reports: verified rows only, with the week they cover</li>
              <li>• SSB export price and the margin bridge, with the feed month named</li>
              <li>• Satellite chlorophyll, with the scene date and its age</li>
              <li>• Traffic-light decisions and the § 8 lice limit per week</li>
              <li>• The dated US tariff register</li>
            </ul>
            <h2 className="mt-3 text-xs font-semibold text-[var(--text-primary)]">
              What it will not
            </h2>
            <ul className="mt-2 space-y-1.5 text-[11px] leading-snug text-[var(--text-secondary)]">
              <li>• Give a buy / sell / hold call on a listed company</li>
              <li>• Estimate a number that is not in its sources</li>
              <li>• Speak about stale data in the present tense</li>
            </ul>
          </GlassCard>
          {usage && !usage.included ? (
            <GlassCard delay={0.15}>
              <p className="text-[11px] leading-relaxed text-[var(--text-secondary)]">
                Your plan does not include grounded chat. Operator includes 100 questions a month
                and every Operator surface (lice forecasting, treatment costs, compliance pack) at
                NOK 4,900.
              </p>
              <a
                href="/billing"
                className="mt-2 inline-block rounded-lg bg-ocean-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-ocean-400"
              >
                Compare plans
              </a>
            </GlassCard>
          ) : null}
        </div>
      </div>
    </div>
  );
}
