"use client";
import { useEffect, useState, useCallback, useRef, Suspense } from "react";
import { useTranslation, formatDate } from "@/lib/i18n";
import type { Locale } from "@/lib/i18n";
import { motion, AnimatePresence } from "framer-motion";
import {
  Bell, BellOff, Check, CheckCheck, RefreshCw,
  AlertTriangle, Bug, DollarSign, Thermometer, Fish,
  Filter, ChevronDown, Info, ShieldAlert, XCircle,
  Plus, Trash2, ToggleLeft, ToggleRight, Zap, Settings2,
  Play, Edit3, X, Square, CheckSquare, MinusSquare, EyeOff,
} from "lucide-react";
import GlassCard from "@/components/GlassCard";
import { OcButton } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { useQueryParams } from "@/lib/useQueryParams";
import ErrorBoundary from "@/components/ErrorBoundary";
import DataQualityBadge from "@/components/DataQualityBadge";

/* eslint-disable @typescript-eslint/no-explicit-any */

// ── Types ─────────────────────────────────────────────────────────────

interface Notification {
  id: string;
  title: string;
  message: string;
  severity: "info" | "warning" | "critical";
  category: "lice" | "price" | "disease" | "temperature";
  timestamp: string;
  read: boolean;
  source?: string;
  metric_value?: number;
  threshold?: number;
}

interface AlertRule {
  id: number;
  user_id?: number;
  name: string;
  metric: string;
  operator: string;
  threshold: number;
  production_area?: number | null;
  is_active: boolean;
  notify_webhook: boolean;
  created_at?: string;
  last_triggered?: string;
  trigger_count: number;
}

interface EvalResult {
  rule_id: number;
  rule_name: string;
  metric: string;
  operator: string;
  threshold: number;
  current_value?: number | null;
  triggered: boolean;
  production_area?: number | null;
  message?: string;
}

// ── Constants ─────────────────────────────────────────────────────────

const SEVERITY_CONFIG = {
  critical: {
    bg: "bg-rose-500/10",
    border: "border-rose-500/20",
    text: "text-rose-400",
    dot: "bg-rose-400",
    icon: XCircle,
    label: "Critical",
  },
  warning: {
    bg: "bg-amber-500/10",
    border: "border-amber-500/20",
    text: "text-amber-400",
    dot: "bg-amber-400",
    icon: AlertTriangle,
    label: "Warning",
  },
  info: {
    bg: "bg-ocean-500/10",
    border: "border-ocean-500/20",
    text: "text-ocean-400",
    dot: "bg-ocean-400",
    icon: Info,
    label: "Info",
  },
};

const CATEGORY_CONFIG: Record<string, { icon: any; label: string; color: string }> = {
  lice: { icon: Bug, label: "Lice", color: "text-amber-400" },
  price: { icon: DollarSign, label: "Price", color: "text-emerald-400" },
  disease: { icon: ShieldAlert, label: "Disease", color: "text-rose-400" },
  temperature: { icon: Thermometer, label: "Temperature", color: "text-ocean-400" },
};

const METRIC_OPTIONS = [
  { value: "lice_avg", label: "Lice Average", unit: "lice/fish" },
  { value: "spot_price", label: "Spot Price", unit: "NOK/kg" },
  { value: "sst", label: "Sea Temperature", unit: "\u00B0C" },
  { value: "disease_count", label: "Disease Count", unit: "cases" },
  { value: "bloom_risk", label: "Bloom Risk", unit: "score" },
];

const OPERATOR_OPTIONS = [
  { value: ">", label: ">" },
  { value: "<", label: "<" },
  { value: ">=", label: ">=" },
  { value: "<=", label: "<=" },
  { value: "==", label: "==" },
];

const REFRESH_INTERVAL = 30_000;

// ── Helpers ───────────────────────────────────────────────────────────

function relativeTime(iso: string, locale?: Locale): string {
  try {
    const d = new Date(iso);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const mins = Math.floor(diffMs / 60_000);
    if (mins < 1) return "Just now";
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    if (days < 7) return `${days}d ago`;
    return formatDate(d, locale ?? "en");
  } catch {
    return "Unknown";
  }
}

function metricLabel(metric: string): string {
  return METRIC_OPTIONS.find((m) => m.value === metric)?.label || metric;
}

function metricUnit(metric: string): string {
  return METRIC_OPTIONS.find((m) => m.value === metric)?.unit || "";
}

// ══════════════════════════════════════════════════════════════════════
// ALERT RULES SECTION
// ══════════════════════════════════════════════════════════════════════

function AlertRulesSection() {
  const { t, locale } = useTranslation();
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [evalResults, setEvalResults] = useState<EvalResult[] | null>(null);

  // Form state
  const [formName, setFormName] = useState("");
  const [formMetric, setFormMetric] = useState("lice_avg");
  const [formOperator, setFormOperator] = useState(">");
  const [formThreshold, setFormThreshold] = useState("");
  const [formPA, setFormPA] = useState("");
  const [formWebhook, setFormWebhook] = useState(false);
  const [formError, setFormError] = useState("");
  const [saving, setSaving] = useState(false);

  const loadRules = useCallback(async () => {
    try {
      const data = await api.alertRulesList();
      setRules(Array.isArray(data) ? data : []);
    } catch {
      // keep existing
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadRules();
  }, [loadRules]);

  const resetForm = () => {
    setFormName("");
    setFormMetric("lice_avg");
    setFormOperator(">");
    setFormThreshold("");
    setFormPA("");
    setFormWebhook(false);
    setFormError("");
  };

  const handleCreate = async () => {
    setFormError("");
    if (!formName.trim()) { setFormError("Name is required"); return; }
    if (!formThreshold.trim() || isNaN(Number(formThreshold))) {
      setFormError("Valid threshold number is required"); return;
    }

    setSaving(true);
    try {
      await api.alertRulesCreate({
        name: formName.trim(),
        metric: formMetric,
        operator: formOperator,
        threshold: Number(formThreshold),
        production_area: formPA ? Number(formPA) : null,
        notify_webhook: formWebhook,
      });
      resetForm();
      setShowForm(false);
      await loadRules();
    } catch (e: any) {
      setFormError(e?.message || "Failed to create rule");
    } finally {
      setSaving(false);
    }
  };

  const handleToggleActive = async (rule: AlertRule) => {
    // Optimistic update
    setRules((prev) =>
      prev.map((r) => (r.id === rule.id ? { ...r, is_active: !r.is_active } : r))
    );
    try {
      await api.alertRulesUpdate(rule.id, { is_active: !rule.is_active });
    } catch {
      loadRules(); // revert
    }
  };

  const handleDelete = async (id: number) => {
    setRules((prev) => prev.filter((r) => r.id !== id));
    try {
      await api.alertRulesDelete(id);
    } catch {
      loadRules();
    }
  };

  const handleEvaluate = async () => {
    setEvaluating(true);
    setEvalResults(null);
    try {
      const data = await api.alertRulesEvaluate();
      setEvalResults(data.results || []);
    } catch {
      setEvalResults([]);
    } finally {
      setEvaluating(false);
    }
  };

  const getEvalForRule = (ruleId: number): EvalResult | undefined =>
    evalResults?.find((r) => r.rule_id === ruleId);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-violet-500/10 flex items-center justify-center">
            <Settings2 className="w-5 h-5 text-violet-400" />
          </div>
          <div>
            <h2 className="text-xl font-display text-[var(--text-primary)]">{t("notifications.alert_rules")}</h2>
            <p className="text-xs text-[var(--text-secondary)]">
              {rules.length} rules, {rules.filter((r) => r.is_active).length} active
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <OcButton
            variant="ghost"
            size="sm"
            onClick={handleEvaluate}
            disabled={evaluating || rules.filter((r) => r.is_active).length === 0}
            aria-label="Evaluate all rules now"
          >
            <Play className={`w-4 h-4 mr-1.5 ${evaluating ? "animate-pulse" : ""}`} />
            {evaluating ? "Evaluating..." : "Evaluate Now"}
          </OcButton>
          <OcButton
            variant="ghost"
            size="sm"
            onClick={() => { setShowForm(!showForm); resetForm(); }}
            aria-label="Create new alert rule"
          >
            {showForm ? <X className="w-4 h-4 mr-1.5" /> : <Plus className="w-4 h-4 mr-1.5" />}
            {showForm ? "Cancel" : t("notifications.create_rule")}
          </OcButton>
        </div>
      </div>

      {/* Create Rule Form */}
      <AnimatePresence>
        {showForm && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <GlassCard tier="secondary" accent="none" hover={false}>
              <div className="space-y-4">
                <h3 className="text-sm font-semibold text-[var(--text-primary)]">New Alert Rule</h3>

                {/* Row 1: Name */}
                <div>
                  <label className="text-xs text-[var(--text-secondary)] font-medium block mb-1">Rule Name</label>
                  <input
                    type="text"
                    value={formName}
                    onChange={(e) => setFormName(e.target.value)}
                    placeholder="e.g. High lice in PA 3"
                    maxLength={100}
                    className="w-full bg-fjord-abyss/50 border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-[var(--text-primary)] placeholder-[var(--text-secondary)]/50 focus:border-salmon/30 focus:outline-none"
                    aria-label="Rule name"
                  />
                </div>

                {/* Row 2: Metric, Operator, Threshold */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div>
                    <label className="text-xs text-[var(--text-secondary)] font-medium block mb-1">{t("notifications.metric")}</label>
                    <select
                      value={formMetric}
                      onChange={(e) => setFormMetric(e.target.value)}
                      className="w-full bg-fjord-abyss/50 border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-[var(--text-primary)] focus:border-salmon/30 focus:outline-none"
                      aria-label="Metric"
                    >
                      {METRIC_OPTIONS.map((m) => (
                        <option key={m.value} value={m.value}>{m.label} ({m.unit})</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-[var(--text-secondary)] font-medium block mb-1">{t("notifications.operator")}</label>
                    <select
                      value={formOperator}
                      onChange={(e) => setFormOperator(e.target.value)}
                      className="w-full bg-fjord-abyss/50 border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-[var(--text-primary)] focus:border-salmon/30 focus:outline-none"
                      aria-label="Operator"
                    >
                      {OPERATOR_OPTIONS.map((o) => (
                        <option key={o.value} value={o.value}>{o.label}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-[var(--text-secondary)] font-medium block mb-1">
                      {t("notifications.threshold")} ({metricUnit(formMetric)})
                    </label>
                    <input
                      type="number"
                      step="any"
                      value={formThreshold}
                      onChange={(e) => setFormThreshold(e.target.value)}
                      placeholder="0.5"
                      className="w-full bg-fjord-abyss/50 border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-[var(--text-primary)] placeholder-[var(--text-secondary)]/50 focus:border-salmon/30 focus:outline-none"
                      aria-label="Threshold value"
                    />
                  </div>
                </div>

                {/* Row 3: PA filter + webhook */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-[var(--text-secondary)] font-medium block mb-1">
                      Production Area (optional)
                    </label>
                    <select
                      value={formPA}
                      onChange={(e) => setFormPA(e.target.value)}
                      className="w-full bg-fjord-abyss/50 border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-[var(--text-primary)] focus:border-salmon/30 focus:outline-none"
                      aria-label="Production area filter"
                    >
                      <option value="">All PAs</option>
                      {Array.from({ length: 13 }, (_, i) => i + 1).map((pa) => (
                        <option key={pa} value={pa}>PA {pa}</option>
                      ))}
                    </select>
                  </div>
                  <div className="flex items-end">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={formWebhook}
                        onChange={(e) => setFormWebhook(e.target.checked)}
                        className="rounded border-white/20 bg-fjord-abyss/50 text-salmon focus:ring-salmon/30"
                      />
                      <span className="text-sm text-[var(--text-secondary)]">Notify via webhook</span>
                    </label>
                  </div>
                </div>

                {/* Error + Submit */}
                {formError && (
                  <p className="text-xs text-rose-400">{formError}</p>
                )}
                <div className="flex justify-end">
                  <OcButton variant="primary" size="sm" onClick={handleCreate} disabled={saving}>
                    {saving ? "Creating..." : "Create Rule"}
                  </OcButton>
                </div>
              </div>
            </GlassCard>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Evaluation Results Banner */}
      <AnimatePresence>
        {evalResults !== null && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
          >
            <GlassCard tier="secondary" accent="none" hover={false}>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Zap className="w-4 h-4 text-amber-400" />
                  <span className="text-sm font-semibold text-[var(--text-primary)]">
                    Evaluation Results
                  </span>
                </div>
                <button
                  onClick={() => setEvalResults(null)}
                  className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                  aria-label="Dismiss results"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
              <div className="flex gap-4 text-xs text-[var(--text-secondary)] mb-3">
                <span>Evaluated: {evalResults.length}</span>
                <span className="text-rose-400 font-bold">
                  Triggered: {evalResults.filter((r) => r.triggered).length}
                </span>
                <span className="text-emerald-400">
                  OK: {evalResults.filter((r) => !r.triggered).length}
                </span>
              </div>
              {evalResults.length === 0 && (
                <p className="text-xs text-[var(--text-secondary)]">No active rules to evaluate.</p>
              )}
            </GlassCard>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Rules List */}
      <GlassCard accent="violet" aria-label="Alert rules list">
        {loading ? (
          <div className="space-y-3">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-16 bg-slate-800/50 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : rules.length === 0 ? (
          <div className="py-12 text-center">
            <Settings2 className="w-10 h-10 mx-auto text-[var(--text-secondary)] opacity-40 mb-3" />
            <h3 className="text-base font-display text-[var(--text-primary)] mb-1">No Alert Rules</h3>
            <p className="text-sm text-[var(--text-secondary)] max-w-sm mx-auto">
              Create your first custom alert rule to get notified when metrics exceed your thresholds.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {rules.map((rule, idx) => {
              const eval_ = getEvalForRule(rule.id);
              const isTriggered = eval_?.triggered;
              const statusColor = !rule.is_active
                ? "border-white/[0.04] bg-fjord-midwater/20 opacity-50"
                : isTriggered
                  ? "border-rose-500/20 bg-rose-500/5"
                  : eval_ !== undefined
                    ? "border-emerald-500/20 bg-emerald-500/5"
                    : "border-white/[0.06] bg-white/[0.02]";

              return (
                <motion.div
                  key={rule.id}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.03 }}
                  className={`flex items-center gap-3 p-4 rounded-xl border transition-all ${statusColor}`}
                >
                  {/* Status indicator */}
                  <div className="flex-shrink-0">
                    {isTriggered ? (
                      <div className="w-2.5 h-2.5 rounded-full bg-rose-400 animate-pulse" />
                    ) : rule.is_active ? (
                      <div className="w-2.5 h-2.5 rounded-full bg-emerald-400" />
                    ) : (
                      <div className="w-2.5 h-2.5 rounded-full bg-slate-600" />
                    )}
                  </div>

                  {/* Rule details */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="text-sm font-semibold text-[var(--text-primary)] truncate">
                        {rule.name}
                      </span>
                      {rule.production_area && (
                        <span className="px-1.5 py-0.5 rounded text-[10px] bg-ocean-500/10 text-ocean-400 font-medium">
                          PA {rule.production_area}
                        </span>
                      )}
                      {rule.notify_webhook && (
                        <span className="px-1.5 py-0.5 rounded text-[10px] bg-violet-500/10 text-violet-400 font-medium">
                          Webhook
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
                      <span className="font-mono">
                        {metricLabel(rule.metric)} {rule.operator} {rule.threshold}
                        {metricUnit(rule.metric) ? ` ${metricUnit(rule.metric)}` : ""}
                      </span>
                      {eval_ && eval_.current_value !== null && eval_.current_value !== undefined && (
                        <span className={`font-bold ${isTriggered ? "text-rose-400" : "text-emerald-400"}`}>
                          (current: {eval_.current_value.toFixed(3)})
                        </span>
                      )}
                    </div>
                    {rule.trigger_count > 0 && (
                      <p className="text-[10px] text-[var(--text-secondary)] mt-0.5">
                        Triggered {rule.trigger_count}x
                        {rule.last_triggered ? ` \u2014 last ${relativeTime(rule.last_triggered, locale)}` : ""}
                      </p>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-1 flex-shrink-0">
                    <button
                      onClick={() => handleToggleActive(rule)}
                      className="p-1.5 rounded-lg hover:bg-white/[0.06] transition-colors"
                      title={rule.is_active ? "Deactivate" : "Activate"}
                      aria-label={rule.is_active ? "Deactivate rule" : "Activate rule"}
                    >
                      {rule.is_active ? (
                        <ToggleRight className="w-5 h-5 text-emerald-400" />
                      ) : (
                        <ToggleLeft className="w-5 h-5 text-slate-500" />
                      )}
                    </button>
                    <button
                      onClick={() => handleDelete(rule.id)}
                      className="p-1.5 rounded-lg hover:bg-rose-500/10 transition-colors"
                      title="Delete rule"
                      aria-label={`Delete rule "${rule.name}"`}
                    >
                      <Trash2 className="w-4 h-4 text-[var(--text-secondary)] hover:text-rose-400" />
                    </button>
                  </div>
                </motion.div>
              );
            })}
          </div>
        )}
      </GlassCard>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════
// NOTIFICATION CENTER (existing)
// ══════════════════════════════════════════════════════════════════════

function NotificationCenter() {
  const { t, locale } = useTranslation();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [unreadCount, setUnreadCount] = useState(0);
  const [totalCount, setTotalCount] = useState(0);
  const [hideRead, setHideRead] = useState(false);

  // Filters — synced with URL query params for bookmarkable views
  const [filters, setFilters] = useQueryParams({
    severity: "all",
    category: "all",
  });
  const severityFilter = filters.severity;
  const categoryFilter = filters.category;
  const [showFilters, setShowFilters] = useState(false);

  // Bulk selection
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const lastClickedIndexRef = useRef<number | null>(null);
  const [focusedIndex, setFocusedIndex] = useState<number>(-1);
  const listRef = useRef<HTMLDivElement>(null);

  // Auto-refresh
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  // Visible notifications (after hideRead filter)
  const visibleNotifications = hideRead
    ? notifications.filter((n) => !n.read)
    : notifications;

  const load = useCallback(async () => {
    try {
      const params: any = { limit: 100 };
      if (severityFilter !== "all") params.severity = severityFilter;
      if (categoryFilter !== "all") params.category = categoryFilter;

      const data = await api.notificationHistory(params);
      setNotifications(data.notifications || []);
      setUnreadCount(data.unread_count || 0);
      setTotalCount(data.total || 0);
    } catch {
      // keep existing data on error
    } finally {
      setLoading(false);
    }
  }, [severityFilter, categoryFilter]);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load]);

  // Auto-refresh every 30s
  useEffect(() => {
    intervalRef.current = setInterval(load, REFRESH_INTERVAL);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [load]);

  // Clear selection when filters change
  useEffect(() => {
    setSelectedIds(new Set());
    lastClickedIndexRef.current = null;
  }, [severityFilter, categoryFilter, hideRead]);

  // Keyboard shortcuts: Ctrl+A to select all, Space to toggle focused
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Ctrl+A / Cmd+A — select all visible
      if ((e.ctrlKey || e.metaKey) && e.key === "a") {
        // Only capture if focus is inside our list or on body (not in an input)
        const active = document.activeElement;
        const isInput = active instanceof HTMLInputElement || active instanceof HTMLTextAreaElement || active instanceof HTMLSelectElement;
        if (!isInput) {
          e.preventDefault();
          setSelectedIds(new Set(visibleNotifications.map((n) => n.id)));
        }
      }

      // Space — toggle selection on focused notification
      if (e.key === " " && focusedIndex >= 0 && focusedIndex < visibleNotifications.length) {
        const active = document.activeElement;
        const isInput = active instanceof HTMLInputElement || active instanceof HTMLTextAreaElement || active instanceof HTMLSelectElement;
        if (!isInput) {
          e.preventDefault();
          const id = visibleNotifications[focusedIndex].id;
          setSelectedIds((prev) => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
          });
        }
      }

      // Arrow keys for focus navigation in the list
      if (e.key === "ArrowDown" && focusedIndex < visibleNotifications.length - 1) {
        e.preventDefault();
        setFocusedIndex((i) => i + 1);
      }
      if (e.key === "ArrowUp" && focusedIndex > 0) {
        e.preventDefault();
        setFocusedIndex((i) => i - 1);
      }
    };

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [visibleNotifications, focusedIndex]);

  // Selection helpers
  const toggleSelection = (id: string, index: number, shiftKey: boolean) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);

      if (shiftKey && lastClickedIndexRef.current !== null) {
        // Range select
        const start = Math.min(lastClickedIndexRef.current, index);
        const end = Math.max(lastClickedIndexRef.current, index);
        for (let i = start; i <= end; i++) {
          next.add(visibleNotifications[i].id);
        }
      } else {
        if (next.has(id)) next.delete(id);
        else next.add(id);
      }

      return next;
    });
    lastClickedIndexRef.current = index;
    setFocusedIndex(index);
  };

  const selectAll = () => {
    setSelectedIds(new Set(visibleNotifications.map((n) => n.id)));
  };

  const deselectAll = () => {
    setSelectedIds(new Set());
    lastClickedIndexRef.current = null;
  };

  const allSelected = visibleNotifications.length > 0 && selectedIds.size === visibleNotifications.length;
  const someSelected = selectedIds.size > 0 && !allSelected;

  const handleMarkRead = async (id: string) => {
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, read: true } : n))
    );
    setUnreadCount((c) => Math.max(0, c - 1));

    try {
      await api.markNotificationsRead([id]);
    } catch {
      load();
    }
  };

  const handleMarkAllRead = async () => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
    setUnreadCount(0);

    try {
      await api.markAllNotificationsRead();
    } catch {
      load();
    }
  };

  // Bulk: mark selected as read
  const handleBulkMarkRead = async () => {
    const ids = Array.from(selectedIds);
    const unreadIds = ids.filter((id) => {
      const n = notifications.find((nn) => nn.id === id);
      return n && !n.read;
    });

    setNotifications((prev) =>
      prev.map((n) => (selectedIds.has(n.id) ? { ...n, read: true } : n))
    );
    setUnreadCount((c) => Math.max(0, c - unreadIds.length));
    setSelectedIds(new Set());
    lastClickedIndexRef.current = null;

    try {
      if (unreadIds.length > 0) {
        await api.markNotificationsRead(unreadIds);
      }
    } catch {
      load();
    }
  };

  // Bulk: delete selected (remove from view)
  const handleBulkDelete = async () => {
    const ids = Array.from(selectedIds);
    const unreadIds = ids.filter((id) => {
      const n = notifications.find((nn) => nn.id === id);
      return n && !n.read;
    });

    // Mark as read first (backend), then remove from view
    setNotifications((prev) => prev.filter((n) => !selectedIds.has(n.id)));
    setUnreadCount((c) => Math.max(0, c - unreadIds.length));
    setTotalCount((c) => Math.max(0, c - ids.length));
    setSelectedIds(new Set());
    lastClickedIndexRef.current = null;

    try {
      if (unreadIds.length > 0) {
        await api.markNotificationsRead(unreadIds);
      }
    } catch {
      load();
    }
  };

  return (
    <div className="space-y-6 pb-20">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-salmon/10 flex items-center justify-center">
            <Bell className="w-5 h-5 text-salmon" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-display text-[var(--text-primary)]">
                {t("notifications.title")}
              </h1>
              <DataQualityBadge quality="live" source="Platform alerts" />
            </div>
            <p className="text-sm text-[var(--text-secondary)]">
              {totalCount} {t("notifications.all")}, {unreadCount} {t("notifications.unread")}
            </p>
          </div>
          {unreadCount > 0 && (
            <motion.span
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              className="ml-1 px-2.5 py-0.5 rounded-full bg-salmon/20 text-salmon text-xs font-bold"
            >
              {unreadCount}
            </motion.span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <OcButton
            variant="ghost"
            size="sm"
            onClick={() => setShowFilters(!showFilters)}
            aria-label="Toggle filters"
          >
            <Filter className="w-4 h-4 mr-1.5" />
            Filters
            <ChevronDown className={`w-3.5 h-3.5 ml-1 transition-transform ${showFilters ? "rotate-180" : ""}`} />
          </OcButton>
          <OcButton
            variant="ghost"
            size="sm"
            onClick={() => setHideRead(!hideRead)}
            aria-label={hideRead ? "Show read notifications" : "Hide read notifications"}
          >
            <EyeOff className={`w-4 h-4 mr-1.5 ${hideRead ? "text-salmon" : ""}`} />
            {hideRead ? "Show Read" : "Clear Read"}
          </OcButton>
          {unreadCount > 0 && (
            <OcButton variant="ghost" size="sm" onClick={handleMarkAllRead} aria-label="Mark all as read">
              <CheckCheck className="w-4 h-4 mr-1.5" />
              Mark All Read
            </OcButton>
          )}
          <OcButton variant="ghost" size="sm" onClick={() => { setLoading(true); load(); }} aria-label="Refresh notifications">
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </OcButton>
        </div>
      </div>

      {/* Filter Bar */}
      <AnimatePresence>
        {showFilters && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <GlassCard tier="secondary" accent="none" hover={false}>
              <div className="flex flex-wrap gap-4">
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs text-[var(--text-secondary)] font-medium">Severity</label>
                  <select
                    value={severityFilter}
                    onChange={(e) => setFilters({ severity: e.target.value })}
                    className="bg-fjord-abyss/50 border border-white/[0.08] rounded-lg px-3 py-1.5 text-sm text-[var(--text-primary)] focus:border-salmon/30 focus:outline-none"
                    aria-label="Filter by severity"
                  >
                    <option value="all">All Severities</option>
                    <option value="critical">Critical</option>
                    <option value="warning">Warning</option>
                    <option value="info">Info</option>
                  </select>
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs text-[var(--text-secondary)] font-medium">Category</label>
                  <select
                    value={categoryFilter}
                    onChange={(e) => setFilters({ category: e.target.value })}
                    className="bg-fjord-abyss/50 border border-white/[0.08] rounded-lg px-3 py-1.5 text-sm text-[var(--text-primary)] focus:border-salmon/30 focus:outline-none"
                    aria-label="Filter by category"
                  >
                    <option value="all">All Categories</option>
                    <option value="lice">Lice</option>
                    <option value="price">Price</option>
                    <option value="disease">Disease</option>
                    <option value="temperature">Temperature</option>
                  </select>
                </div>
                {(severityFilter !== "all" || categoryFilter !== "all") && (
                  <div className="flex items-end">
                    <OcButton
                      variant="ghost"
                      size="sm"
                      onClick={() => setFilters({ severity: "all", category: "all" })}
                    >
                      Clear Filters
                    </OcButton>
                  </div>
                )}
              </div>
            </GlassCard>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {(["critical", "warning", "info"] as const).map((sev) => {
          const count = notifications.filter((n) => n.severity === sev && !n.read).length;
          const cfg = SEVERITY_CONFIG[sev];
          const Icon = cfg.icon;
          return (
            <GlassCard key={sev} tier="secondary" accent="none" hover={true}>
              <div className="flex items-center gap-3">
                <div className={`w-8 h-8 rounded-lg ${cfg.bg} flex items-center justify-center`}>
                  <Icon className={`w-4 h-4 ${cfg.text}`} />
                </div>
                <div>
                  <p className="text-xl font-bold text-[var(--text-primary)]">{count}</p>
                  <p className="text-xs text-[var(--text-secondary)]">{cfg.label}</p>
                </div>
              </div>
            </GlassCard>
          );
        })}
        <GlassCard tier="secondary" accent="none" hover={true}>
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center">
              <Check className="w-4 h-4 text-emerald-400" />
            </div>
            <div>
              <p className="text-xl font-bold text-[var(--text-primary)]">
                {notifications.filter((n) => n.read).length}
              </p>
              <p className="text-xs text-[var(--text-secondary)]">Read</p>
            </div>
          </div>
        </GlassCard>
      </div>

      {/* Notification List */}
      <GlassCard accent="salmon" aria-label="Notification list">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            {/* Select All / Deselect All checkbox */}
            {visibleNotifications.length > 0 && (
              <button
                onClick={() => allSelected ? deselectAll() : selectAll()}
                className="p-1 rounded-lg hover:bg-white/[0.06] transition-colors"
                aria-label={allSelected ? "Deselect all notifications" : "Select all notifications"}
                title={allSelected ? "Deselect all" : "Select all"}
              >
                {allSelected ? (
                  <CheckSquare className="w-5 h-5 text-salmon" />
                ) : someSelected ? (
                  <MinusSquare className="w-5 h-5 text-salmon/60" />
                ) : (
                  <Square className="w-5 h-5 text-[var(--text-secondary)]" />
                )}
              </button>
            )}
            <h2 className="text-lg font-display text-[var(--text-primary)]">
              {severityFilter !== "all" || categoryFilter !== "all"
                ? t("notifications.title")
                : hideRead
                  ? t("notifications.unread")
                  : t("notifications.all")}
            </h2>
          </div>
          <span className="text-xs text-[var(--text-secondary)]">
            {selectedIds.size > 0
              ? `${selectedIds.size} selected`
              : "Auto-refreshes every 30s"}
          </span>
        </div>

        {loading && notifications.length === 0 ? (
          <div className="space-y-3">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-20 bg-slate-800/50 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : visibleNotifications.length === 0 ? (
          <div className="py-16 text-center">
            <BellOff className="w-12 h-12 mx-auto text-[var(--text-secondary)] opacity-40 mb-4" />
            <h3 className="text-lg font-display text-[var(--text-primary)] mb-1">
              {hideRead ? "No Unread Notifications" : "No Notifications"}
            </h3>
            <p className="text-sm text-[var(--text-secondary)] max-w-md mx-auto">
              {hideRead
                ? "All notifications have been read. Toggle \"Show Read\" to see them."
                : severityFilter !== "all" || categoryFilter !== "all"
                  ? "No notifications match your current filters. Try adjusting them."
                  : "All clear! No active alerts or notifications right now. The system monitors lice levels, price movements, disease outbreaks, and sea temperature."}
            </p>
          </div>
        ) : (
          <div className="space-y-2" ref={listRef}>
            <AnimatePresence mode="popLayout">
              {visibleNotifications.map((n, idx) => {
                const sevCfg = SEVERITY_CONFIG[n.severity] || SEVERITY_CONFIG.info;
                const catCfg = CATEGORY_CONFIG[n.category] || CATEGORY_CONFIG.lice;
                const CatIcon = catCfg.icon;
                const SevIcon = sevCfg.icon;
                const isSelected = selectedIds.has(n.id);
                const isFocused = focusedIndex === idx;

                return (
                  <motion.div
                    key={n.id}
                    layout
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, x: -20 }}
                    transition={{ delay: idx * 0.02, duration: 0.25 }}
                    className={`
                      relative flex items-start gap-3 p-4 rounded-xl border transition-all duration-200 group
                      ${isSelected
                        ? "bg-salmon/5 border-salmon/30 ring-1 ring-salmon/20"
                        : n.read
                          ? "bg-fjord-midwater/20 border-white/[0.04] opacity-60"
                          : `${sevCfg.bg} ${sevCfg.border} border`
                      }
                      ${!n.read && !isSelected ? "hover:border-salmon/20" : ""}
                      ${isFocused ? "ring-2 ring-ocean-400/40" : ""}
                    `}
                    onClick={(e) => {
                      // Only toggle selection if clicking the row background (not buttons)
                      if ((e.target as HTMLElement).closest("button")) return;
                      toggleSelection(n.id, idx, e.shiftKey);
                    }}
                    role="option"
                    aria-selected={isSelected}
                    tabIndex={isFocused ? 0 : -1}
                  >
                    {/* Selection checkbox */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleSelection(n.id, idx, e.shiftKey);
                      }}
                      className="mt-0.5 p-0.5 rounded transition-colors flex-shrink-0 hover:bg-white/[0.06]"
                      aria-label={isSelected ? `Deselect "${n.title}"` : `Select "${n.title}"`}
                    >
                      {isSelected ? (
                        <CheckSquare className="w-4 h-4 text-salmon" />
                      ) : (
                        <Square className="w-4 h-4 text-[var(--text-secondary)] opacity-40 group-hover:opacity-100 transition-opacity" />
                      )}
                    </button>

                    {!n.read && (
                      <div className={`absolute top-4 left-1.5 w-1.5 h-1.5 rounded-full ${sevCfg.dot} animate-pulse`} />
                    )}
                    <div className={`mt-0.5 w-9 h-9 rounded-lg ${sevCfg.bg} flex items-center justify-center flex-shrink-0`}>
                      <CatIcon className={`w-4 h-4 ${catCfg.color}`} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2">
                        <h3 className={`text-sm font-semibold ${n.read ? "text-[var(--text-secondary)]" : "text-[var(--text-primary)]"} truncate`}>
                          {n.title}
                        </h3>
                        <div className="flex items-center gap-2 flex-shrink-0">
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${sevCfg.bg} ${sevCfg.text} border ${sevCfg.border}`}>
                            <SevIcon className="w-2.5 h-2.5" />
                            {sevCfg.label}
                          </span>
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium text-[var(--text-secondary)] bg-white/[0.04] border border-white/[0.06]">
                            {catCfg.label}
                          </span>
                        </div>
                      </div>
                      <p className="text-xs text-[var(--text-secondary)] mt-0.5 line-clamp-2">
                        {n.message}
                      </p>
                      <div className="flex items-center justify-between mt-2">
                        <span className="text-[10px] text-[var(--text-secondary)] opacity-70">
                          {relativeTime(n.timestamp, locale)}
                        </span>
                        {!n.read && (
                          <button
                            onClick={(e) => { e.stopPropagation(); handleMarkRead(n.id); }}
                            className="text-[10px] text-salmon/70 hover:text-salmon transition-colors flex items-center gap-1"
                            aria-label={`Mark "${n.title}" as read`}
                          >
                            <Check className="w-3 h-3" />
                            Mark read
                          </button>
                        )}
                      </div>
                    </div>
                  </motion.div>
                );
              })}
            </AnimatePresence>
          </div>
        )}
      </GlassCard>

      {/* Floating Bulk Action Bar */}
      <AnimatePresence>
        {selectedIds.size > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 30 }}
            transition={{ type: "spring", damping: 25, stiffness: 350 }}
            className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50"
          >
            <div className="flex items-center gap-3 px-5 py-3 rounded-2xl border border-white/[0.12] bg-[var(--card-bg,rgba(15,23,42,0.85))] backdrop-blur-xl shadow-2xl shadow-black/40">
              {/* Selected count */}
              <span className="text-sm font-semibold text-[var(--text-primary)] whitespace-nowrap">
                {selectedIds.size} selected
              </span>

              <div className="w-px h-6 bg-white/[0.1]" />

              {/* Mark as read */}
              <button
                onClick={handleBulkMarkRead}
                className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium
                  bg-emerald-500/10 text-emerald-400 border border-emerald-500/20
                  hover:bg-emerald-500/20 hover:border-emerald-500/30
                  transition-all duration-200 whitespace-nowrap"
                aria-label={`Mark ${selectedIds.size} selected as read`}
              >
                <CheckCheck className="w-4 h-4" />
                Mark {selectedIds.size} Read
              </button>

              {/* Delete selected */}
              <button
                onClick={handleBulkDelete}
                className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium
                  bg-rose-500/10 text-rose-400 border border-rose-500/20
                  hover:bg-rose-500/20 hover:border-rose-500/30
                  transition-all duration-200 whitespace-nowrap"
                aria-label={`Delete ${selectedIds.size} selected notifications`}
              >
                <Trash2 className="w-4 h-4" />
                Delete {selectedIds.size}
              </button>

              <div className="w-px h-6 bg-white/[0.1]" />

              {/* Deselect */}
              <button
                onClick={deselectAll}
                className="p-2 rounded-xl text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-white/[0.06] transition-all"
                aria-label="Deselect all"
                title="Deselect all"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════
// PAGE: TABS
// ══════════════════════════════════════════════════════════════════════

function NotificationsPageContent() {
  const { t } = useTranslation();
  const [tabState, setTabState] = useQueryParams({ tab: "notifications" });
  const activeTab = tabState.tab as "notifications" | "rules";
  const setActiveTab = (t: "notifications" | "rules") => setTabState({ tab: t });

  return (
    <div className="space-y-6">
      {/* Tab Switcher */}
      <div className="flex gap-1 p-1 bg-fjord-abyss/30 rounded-xl w-fit border border-white/[0.06]">
        <button
          onClick={() => setActiveTab("notifications")}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
            activeTab === "notifications"
              ? "bg-salmon/20 text-salmon"
              : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          }`}
          aria-label="View notifications"
        >
          <Bell className="w-4 h-4 inline mr-1.5 -mt-0.5" />
          {t("notifications.title")}
        </button>
        <button
          onClick={() => setActiveTab("rules")}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
            activeTab === "rules"
              ? "bg-violet-500/20 text-violet-400"
              : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          }`}
          aria-label="Manage alert rules"
        >
          <Settings2 className="w-4 h-4 inline mr-1.5 -mt-0.5" />
          {t("notifications.alert_rules")}
        </button>
      </div>

      {/* Tab Content */}
      {activeTab === "notifications" ? <NotificationCenter /> : <AlertRulesSection />}
    </div>
  );
}

export default function NotificationsPage() {
  return (
    <ErrorBoundary>
      <Suspense>
        <NotificationsPageContent />
      </Suspense>
    </ErrorBoundary>
  );
}
