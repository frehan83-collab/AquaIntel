"use client";
import { useState, useEffect, useCallback } from "react";
import GlassCard from "@/components/GlassCard";
import { OcButton } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { useTranslation, formatDate } from "@/lib/i18n";

interface WebhookEvent {
  id: string;
  label: string;
  description: string;
}

interface Webhook {
  id: number;
  name: string;
  url: string;
  webhook_type: string;
  events: string[];
  is_active: boolean;
  created_at: string | null;
  last_triggered: string | null;
  failure_count: number;
}

const TYPE_OPTIONS = [
  { value: "generic", label: "Generic (JSON)" },
  { value: "slack", label: "Slack" },
  { value: "teams", label: "Microsoft Teams" },
];

export default function WebhooksSettingsPage() {
  const { locale } = useTranslation();
  const [webhooks, setWebhooks] = useState<Webhook[]>([]);
  const [events, setEvents] = useState<WebhookEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [testingId, setTestingId] = useState<number | null>(null);
  const [testResult, setTestResult] = useState<{ id: number; status: string; message: string } | null>(null);

  // Form state
  const [formName, setFormName] = useState("");
  const [formUrl, setFormUrl] = useState("");
  const [formType, setFormType] = useState("generic");
  const [formEvents, setFormEvents] = useState<string[]>([]);
  const [formError, setFormError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [whRes, evRes] = await Promise.allSettled([
        api.webhooksList(),
        api.webhooksEvents(),
      ]);
      if (whRes.status === "fulfilled") setWebhooks(whRes.value.webhooks || []);
      if (evRes.status === "fulfilled") setEvents(evRes.value.events || []);
    } catch { /* ignore */ } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleCreate = async () => {
    setFormError("");
    if (!formUrl.trim()) { setFormError("URL is required"); return; }
    if (!formUrl.startsWith("http://") && !formUrl.startsWith("https://")) {
      setFormError("URL must start with http:// or https://"); return;
    }
    if (formEvents.length === 0) { setFormError("Select at least one event"); return; }

    setSubmitting(true);
    try {
      await api.webhooksCreate({
        name: formName || "Unnamed Webhook",
        url: formUrl,
        webhook_type: formType,
        events: formEvents,
      });
      setShowForm(false);
      setFormName(""); setFormUrl(""); setFormType("generic"); setFormEvents([]);
      await fetchData();
    } catch (e: any) {
      setFormError(e.message || "Failed to create webhook");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.webhooksDelete(id);
      setWebhooks(prev => prev.filter(w => w.id !== id));
    } catch { /* ignore */ }
  };

  const handleTest = async (id: number) => {
    setTestingId(id);
    setTestResult(null);
    try {
      const res = await api.webhooksTest(id);
      setTestResult({ id, status: res.status, message: res.message });
    } catch (e: any) {
      setTestResult({ id, status: "error", message: e.message });
    } finally {
      setTestingId(null);
    }
  };

  const toggleEvent = (eventId: string) => {
    setFormEvents(prev =>
      prev.includes(eventId)
        ? prev.filter(e => e !== eventId)
        : [...prev, eventId]
    );
  };

  if (loading) {
    return (
      <div className="p-6 space-y-4">
        <h1 className="text-2xl font-bold text-white">Webhook Integrations</h1>
        <div className="animate-pulse space-y-3">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-24 rounded-xl bg-white/5" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Webhook Integrations</h1>
          <p className="text-sm text-gray-400 mt-1">
            Receive FishIntel alerts in Slack, Teams, or any HTTP endpoint
          </p>
        </div>
        <OcButton onClick={() => setShowForm(!showForm)}>
          {showForm ? "Cancel" : "+ Add Webhook"}
        </OcButton>
      </div>

      {/* Add Webhook Form */}
      {showForm && (
        <GlassCard>
          <h2 className="text-lg font-semibold text-white mb-4">New Webhook</h2>
          <div className="space-y-4">
            {/* Name */}
            <div>
              <label className="block text-sm text-gray-300 mb-1">Name</label>
              <input
                type="text"
                value={formName}
                onChange={e => setFormName(e.target.value)}
                placeholder="e.g. Production Slack Channel"
                className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white placeholder-gray-500 focus:border-cyan-500 focus:outline-hidden"
              />
            </div>

            {/* URL */}
            <div>
              <label className="block text-sm text-gray-300 mb-1">Webhook URL *</label>
              <input
                type="url"
                value={formUrl}
                onChange={e => setFormUrl(e.target.value)}
                placeholder="https://hooks.slack.com/services/..."
                className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white placeholder-gray-500 focus:border-cyan-500 focus:outline-hidden"
              />
            </div>

            {/* Type */}
            <div>
              <label className="block text-sm text-gray-300 mb-1">Type</label>
              <div className="flex gap-3">
                {TYPE_OPTIONS.map(opt => (
                  <button
                    key={opt.value}
                    onClick={() => setFormType(opt.value)}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                      formType === opt.value
                        ? "bg-cyan-600 text-white"
                        : "bg-white/5 text-gray-300 hover:bg-white/10"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Events */}
            <div>
              <label className="block text-sm text-gray-300 mb-2">Events *</label>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {events.map(ev => (
                  <label
                    key={ev.id}
                    className={`flex items-start gap-3 p-3 rounded-lg cursor-pointer transition-colors ${
                      formEvents.includes(ev.id)
                        ? "bg-cyan-900/30 border border-cyan-500/30"
                        : "bg-white/5 border border-white/5 hover:bg-white/10"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={formEvents.includes(ev.id)}
                      onChange={() => toggleEvent(ev.id)}
                      className="mt-0.5 accent-cyan-500"
                    />
                    <div>
                      <div className="text-sm font-medium text-white">{ev.label}</div>
                      <div className="text-xs text-gray-400">{ev.description}</div>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            {formError && (
              <div className="text-sm text-rose-400 bg-rose-900/20 px-3 py-2 rounded-lg">
                {formError}
              </div>
            )}

            <div className="flex gap-3">
              <OcButton onClick={handleCreate} disabled={submitting}>
                {submitting ? "Creating..." : "Create Webhook"}
              </OcButton>
              <OcButton variant="ghost" onClick={() => setShowForm(false)}>
                Cancel
              </OcButton>
            </div>
          </div>
        </GlassCard>
      )}

      {/* Webhooks List */}
      {webhooks.length === 0 && !showForm ? (
        <GlassCard>
          <div className="text-center py-12">
            <div className="text-4xl mb-3">🔗</div>
            <h3 className="text-lg font-semibold text-white mb-1">No webhooks configured</h3>
            <p className="text-sm text-gray-400 mb-4">
              Add a webhook to receive FishIntel alerts in Slack, Teams, or any HTTP endpoint.
            </p>
            <OcButton onClick={() => setShowForm(true)}>+ Add Your First Webhook</OcButton>
          </div>
        </GlassCard>
      ) : (
        <div className="space-y-3">
          {webhooks.map(hook => (
            <GlassCard key={hook.id}>
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="text-base font-semibold text-white truncate">{hook.name}</h3>
                    {/* Status badge */}
                    {hook.is_active ? (
                      <span className="px-2 py-0.5 text-xs rounded-full bg-emerald-900/40 text-emerald-400 border border-emerald-500/20">
                        Active
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 text-xs rounded-full bg-rose-900/40 text-rose-400 border border-rose-500/20">
                        Disabled
                      </span>
                    )}
                    {/* Type badge */}
                    <span className="px-2 py-0.5 text-xs rounded-full bg-white/10 text-gray-300">
                      {hook.webhook_type === "slack" ? "Slack" : hook.webhook_type === "teams" ? "Teams" : "Generic"}
                    </span>
                    {/* Failure warning */}
                    {hook.failure_count > 0 && (
                      <span className="px-2 py-0.5 text-xs rounded-full bg-amber-900/40 text-amber-400 border border-amber-500/20">
                        {hook.failure_count} failure{hook.failure_count > 1 ? "s" : ""}
                      </span>
                    )}
                  </div>

                  <p className="text-xs text-gray-500 font-mono truncate mb-2">{hook.url}</p>

                  {/* Event tags */}
                  <div className="flex flex-wrap gap-1.5">
                    {hook.events.map(ev => (
                      <span key={ev} className="px-2 py-0.5 text-xs rounded bg-cyan-900/30 text-cyan-300 border border-cyan-500/20">
                        {ev.replace(/_/g, " ")}
                      </span>
                    ))}
                  </div>

                  {/* Meta */}
                  <div className="flex gap-4 mt-2 text-xs text-gray-500">
                    {hook.created_at && (
                      <span>Created {formatDate(hook.created_at, locale)}</span>
                    )}
                    {hook.last_triggered && (
                      <span>Last triggered {formatDate(hook.last_triggered, locale)}</span>
                    )}
                  </div>

                  {/* Test result */}
                  {testResult && testResult.id === hook.id && (
                    <div className={`mt-2 text-xs px-3 py-1.5 rounded-lg ${
                      testResult.status === "success"
                        ? "bg-emerald-900/20 text-emerald-400"
                        : "bg-rose-900/20 text-rose-400"
                    }`}>
                      {testResult.message}
                    </div>
                  )}
                </div>

                {/* Actions */}
                <div className="flex gap-2 shrink-0">
                  <OcButton
                    variant="ghost"
                    size="sm"
                    onClick={() => handleTest(hook.id)}
                    disabled={testingId === hook.id}
                  >
                    {testingId === hook.id ? "Testing..." : "Test"}
                  </OcButton>
                  <OcButton
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDelete(hook.id)}
                    className="text-rose-400 hover:text-rose-300"
                  >
                    Delete
                  </OcButton>
                </div>
              </div>
            </GlassCard>
          ))}
        </div>
      )}

      {/* Info section */}
      <GlassCard>
        <h3 className="text-sm font-semibold text-white mb-2">How Webhooks Work</h3>
        <ul className="text-xs text-gray-400 space-y-1.5">
          <li><strong className="text-gray-300">Slack:</strong> Paste your Slack Incoming Webhook URL. Alerts are formatted as rich Block Kit messages.</li>
          <li><strong className="text-gray-300">Teams:</strong> Use your Teams Incoming Webhook URL. Alerts are sent as Adaptive Cards.</li>
          <li><strong className="text-gray-300">Generic:</strong> Any HTTP endpoint. Receives a JSON payload with event, title, message, severity, and data fields.</li>
          <li><strong className="text-gray-300">Auto-disable:</strong> Webhooks are automatically disabled after 5 consecutive delivery failures.</li>
        </ul>
      </GlassCard>
    </div>
  );
}
