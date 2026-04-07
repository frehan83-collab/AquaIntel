"use client";
import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Layers, Plus, X, Play, Save, FolderOpen, AlertTriangle,
  TrendingDown, Activity, ChevronDown, Trash2, Info, RefreshCw,
} from "lucide-react";
import KPICard from "@/components/KPICard";
import GlassCard from "@/components/GlassCard";
import DataQualityBadge from "@/components/DataQualityBadge";
import { OcButton } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { useTranslation, formatDate } from "@/lib/i18n";
import ErrorBoundary from "@/components/ErrorBoundary";

/* eslint-disable @typescript-eslint/no-explicit-any */

// ── Event type definitions ─────────────────────────────────────────

type EventType = "isa" | "traffic_light" | "feed_shock" | "generic";

interface ScenarioEvent {
  id: string;
  type: EventType;
  label: string;
  params: Record<string, any>;
}

const EVENT_TYPES: { value: EventType; label: string; description: string }[] = [
  { value: "isa", label: "ISA Outbreak", description: "Infectious Salmon Anaemia outbreak in a production area" },
  { value: "traffic_light", label: "Traffic Light Change", description: "Regulatory traffic light color change for a PA" },
  { value: "feed_shock", label: "Feed Price Shock", description: "Fishmeal/feed cost spike affecting all producers" },
  { value: "generic", label: "Custom Event", description: "Generic production disruption with custom parameters" },
];

const PA_OPTIONS = Array.from({ length: 13 }, (_, i) => i + 1);
const COLORS = ["green", "yellow", "red"] as const;

function generateId() {
  return Math.random().toString(36).slice(2, 9);
}

function getEventLabel(e: ScenarioEvent): string {
  switch (e.type) {
    case "isa":
      return `ISA Outbreak PA ${e.params.production_area || 3}`;
    case "traffic_light":
      return `PA ${e.params.pa || 3} -> ${(e.params.color || "red").toUpperCase()}`;
    case "feed_shock":
      return `Feed ${e.params.fishmeal_change_pct > 0 ? "+" : ""}${e.params.fishmeal_change_pct || 15}%`;
    case "generic":
      return e.params.description || `Generic -${e.params.production_loss_pct || 1}%`;
    default:
      return "Unknown Event";
  }
}

// ── Severity badge ─────────────────────────────────────────────────

function SeverityBadge({ severity }: { severity: string }) {
  const colors: Record<string, string> = {
    critical: "bg-rose-500/20 text-rose-300 border-rose-500/30",
    high: "bg-amber-500/20 text-amber-300 border-amber-500/30",
    medium: "bg-yellow-500/20 text-yellow-300 border-yellow-500/30",
    low: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
  };
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium border ${colors[severity] || colors.medium}`}>
      {severity.toUpperCase()}
    </span>
  );
}

// ── Event parameter forms ──────────────────────────────────────────

function ISAParams({ params, onChange }: { params: any; onChange: (p: any) => void }) {
  return (
    <div className="flex items-center gap-3">
      <label className="text-xs text-[var(--text-secondary)]">Production Area</label>
      <select
        value={params.production_area || 3}
        onChange={(e) => onChange({ ...params, production_area: Number(e.target.value) })}
        className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-[var(--text-primary)] focus:outline-none focus:border-salmon/40"
      >
        {PA_OPTIONS.map((pa) => (
          <option key={pa} value={pa} className="bg-fjord-abyss">PA {pa}</option>
        ))}
      </select>
    </div>
  );
}

function TrafficLightParams({ params, onChange }: { params: any; onChange: (p: any) => void }) {
  return (
    <div className="flex items-center gap-4">
      <div className="flex items-center gap-2">
        <label className="text-xs text-[var(--text-secondary)]">PA</label>
        <select
          value={params.pa || 3}
          onChange={(e) => onChange({ ...params, pa: Number(e.target.value) })}
          className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-[var(--text-primary)] focus:outline-none focus:border-salmon/40"
        >
          {PA_OPTIONS.map((pa) => (
            <option key={pa} value={pa} className="bg-fjord-abyss">PA {pa}</option>
          ))}
        </select>
      </div>
      <div className="flex items-center gap-2">
        <label className="text-xs text-[var(--text-secondary)]">Color</label>
        <div className="flex gap-1">
          {COLORS.map((c) => (
            <button
              key={c}
              onClick={() => onChange({ ...params, color: c })}
              className={`w-8 h-8 rounded-full border-2 transition-all ${
                params.color === c ? "border-white scale-110" : "border-white/20 hover:border-white/40"
              }`}
              style={{ backgroundColor: c === "green" ? "#10b981" : c === "yellow" ? "#f59e0b" : "#ef4444" }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function FeedShockParams({ params, onChange }: { params: any; onChange: (p: any) => void }) {
  const pct = params.fishmeal_change_pct ?? 15;
  return (
    <div className="flex items-center gap-3">
      <label className="text-xs text-[var(--text-secondary)]">Fishmeal Change</label>
      <input
        type="range"
        min={-30}
        max={60}
        step={5}
        value={pct}
        onChange={(e) => onChange({ ...params, fishmeal_change_pct: Number(e.target.value) })}
        className="w-40 accent-salmon"
      />
      <span className={`text-sm font-mono min-w-[4rem] text-right ${pct > 0 ? "text-rose-400" : pct < 0 ? "text-emerald-400" : "text-[var(--text-secondary)]"}`}>
        {pct > 0 ? "+" : ""}{pct}%
      </span>
    </div>
  );
}

function GenericParams({ params, onChange }: { params: any; onChange: (p: any) => void }) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-3">
        <label className="text-xs text-[var(--text-secondary)]">Production Loss %</label>
        <input
          type="number"
          min={0}
          max={50}
          step={0.5}
          value={params.production_loss_pct ?? 1}
          onChange={(e) => onChange({ ...params, production_loss_pct: Number(e.target.value) })}
          className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-sm w-20 text-[var(--text-primary)] focus:outline-none focus:border-salmon/40"
        />
      </div>
      <div className="flex items-center gap-3">
        <label className="text-xs text-[var(--text-secondary)]">Description</label>
        <input
          type="text"
          value={params.description || ""}
          placeholder="E.g. algal bloom in northern fjords"
          onChange={(e) => onChange({ ...params, description: e.target.value })}
          className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-sm flex-1 text-[var(--text-primary)] focus:outline-none focus:border-salmon/40"
        />
      </div>
    </div>
  );
}

function EventParamEditor({ event, onChange }: { event: ScenarioEvent; onChange: (p: any) => void }) {
  switch (event.type) {
    case "isa": return <ISAParams params={event.params} onChange={onChange} />;
    case "traffic_light": return <TrafficLightParams params={event.params} onChange={onChange} />;
    case "feed_shock": return <FeedShockParams params={event.params} onChange={onChange} />;
    case "generic": return <GenericParams params={event.params} onChange={onChange} />;
    default: return null;
  }
}

// ── Default params per event type ──────────────────────────────────

function defaultParams(type: EventType): Record<string, any> {
  switch (type) {
    case "isa": return { production_area: 3 };
    case "traffic_light": return { pa: 3, color: "red" };
    case "feed_shock": return { fishmeal_change_pct: 15 };
    case "generic": return { production_loss_pct: 1, description: "" };
    default: return {};
  }
}

// ── Main Page ──────────────────────────────────────────────────────

export default function ScenarioLabPage() {
  const { t, locale } = useTranslation();
  // Event builder state
  const [events, setEvents] = useState<ScenarioEvent[]>([]);
  const [addingType, setAddingType] = useState<EventType>("isa");
  const [showDropdown, setShowDropdown] = useState(false);

  // Simulation state
  const [result, setResult] = useState<any>(null);
  const [running, setRunning] = useState(false);

  // Saved scenarios
  const [savedScenarios, setSavedScenarios] = useState<any[]>([]);
  const [saving, setSaving] = useState(false);
  const [loadingScenarios, setLoadingScenarios] = useState(false);

  // Load saved scenarios on mount
  useEffect(() => {
    loadSavedScenarios();
  }, []);

  const loadSavedScenarios = async () => {
    setLoadingScenarios(true);
    try {
      const data = await api.listScenarios("anonymous");
      const compound = (Array.isArray(data) ? data : []).filter(
        (s: any) => s.scenario_type === "compound"
      );
      setSavedScenarios(compound);
    } catch { /* ignore */ }
    setLoadingScenarios(false);
  };

  const addEvent = () => {
    const newEvent: ScenarioEvent = {
      id: generateId(),
      type: addingType,
      label: "",
      params: defaultParams(addingType),
    };
    newEvent.label = getEventLabel(newEvent);
    setEvents((prev) => [...prev, newEvent]);
    setShowDropdown(false);
  };

  const removeEvent = (id: string) => {
    setEvents((prev) => prev.filter((e) => e.id !== id));
  };

  const updateEventParams = (id: string, params: any) => {
    setEvents((prev) =>
      prev.map((e) => {
        if (e.id !== id) return e;
        const updated = { ...e, params };
        updated.label = getEventLabel(updated);
        return updated;
      })
    );
  };

  const runSimulation = async () => {
    if (events.length === 0) return;
    setRunning(true);
    setResult(null);
    try {
      const payload = events.map((e) => ({ type: e.type, params: e.params }));
      const data = await api.runCompoundScenario(payload);
      setResult(data);
    } catch (err: any) {
      setResult({ error: err.message || "Simulation failed" });
    }
    setRunning(false);
  };

  const saveScenario = async () => {
    if (!result || result.error) return;
    setSaving(true);
    try {
      await api.saveScenario({
        user_email: "anonymous",
        scenario_type: "compound",
        scenario_name: `Compound: ${events.map((e) => e.label).join(" + ")}`,
        parameters: { events: events.map((e) => ({ type: e.type, params: e.params })) },
        results: result,
      });
      await loadSavedScenarios();
    } catch { /* ignore */ }
    setSaving(false);
  };

  const loadScenario = (scenario: any) => {
    const params = scenario.parameters;
    if (params?.events) {
      const loaded = params.events.map((e: any) => {
        const ev: ScenarioEvent = {
          id: generateId(),
          type: e.type,
          label: "",
          params: e.params || {},
        };
        ev.label = getEventLabel(ev);
        return ev;
      });
      setEvents(loaded);
      setResult(scenario.results || null);
    }
  };

  const deleteScenario = async (id: number) => {
    try {
      await api.deleteScenario(id);
      await loadSavedScenarios();
    } catch { /* ignore */ }
  };

  const compound = result?.compound_impact;

  return (
    <ErrorBoundary fallbackTitle="Scenario Lab error">
    <div className="min-h-screen p-6 md:p-8 space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-display text-[var(--text-primary)] flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500/20 to-purple-600/20 border border-violet-500/20 flex items-center justify-center">
              <Layers className="w-5 h-5 text-violet-400" />
            </div>
            {t("scenarios.title")}
          </h1>
          <p className="text-sm text-[var(--text-secondary)] mt-1">
            Combine multiple events and see cascading impacts across the Norwegian salmon sector
          </p>
        </div>
        {result?.data_provenance && (
          <DataQualityBadge provenance={result.data_provenance} />
        )}
      </div>

      {/* KPI strip (only when results exist) */}
      {compound && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="grid grid-cols-2 md:grid-cols-4 gap-4"
        >
          <KPICard
            label="Revenue Impact"
            value={`${compound.total_revenue_impact_mnok > 0 ? "+" : ""}${compound.total_revenue_impact_mnok} MNOK`}
            icon={TrendingDown}
            deltaType={compound.total_revenue_impact_mnok < 0 ? "negative" : "positive"}
          />
          <KPICard
            label="Production Impact"
            value={`${compound.national_production_impact_pct > 0 ? "+" : ""}${compound.national_production_impact_pct.toFixed(3)}%`}
            icon={Activity}
          />
          <KPICard
            label="Price Effect"
            value={`${compound.price_impact_pct > 0 ? "+" : ""}${compound.price_impact_pct.toFixed(2)}%`}
            icon={TrendingDown}
          />
          <KPICard
            label={t("scenarios.compound_impact")}
            value={`${compound.interaction_multiplier.toFixed(2)}x`}
            icon={Layers}
            delta={compound.severity.toUpperCase()}
            deltaType={compound.severity === "critical" || compound.severity === "high" ? "negative" : "neutral"}
          />
        </motion.div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* LEFT: Event Builder */}
        <div className="lg:col-span-1 space-y-4">
          <GlassCard>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-display text-[var(--text-primary)]">Event Builder</h2>
              <span className="text-xs text-[var(--text-secondary)]">{events.length} event{events.length !== 1 ? "s" : ""}</span>
            </div>

            {/* Event chips */}
            <div className="space-y-3 mb-4">
              <AnimatePresence>
                {events.map((event) => (
                  <motion.div
                    key={event.id}
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    className="bg-white/[0.03] border border-white/[0.06] rounded-xl p-3 space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className={`w-2 h-2 rounded-full ${
                          event.type === "isa" ? "bg-rose-400" :
                          event.type === "traffic_light" ? "bg-amber-400" :
                          event.type === "feed_shock" ? "bg-orange-400" :
                          "bg-violet-400"
                        }`} />
                        <span className="text-sm font-medium text-[var(--text-primary)]">{event.label}</span>
                      </div>
                      <button
                        onClick={() => removeEvent(event.id)}
                        className="p-1 hover:bg-white/10 rounded-lg transition-colors"
                      >
                        <X className="w-3.5 h-3.5 text-[var(--text-secondary)]" />
                      </button>
                    </div>
                    <EventParamEditor
                      event={event}
                      onChange={(params) => updateEventParams(event.id, params)}
                    />
                  </motion.div>
                ))}
              </AnimatePresence>

              {events.length === 0 && (
                <div className="text-center py-8 text-[var(--text-secondary)] text-sm">
                  <Layers className="w-8 h-8 mx-auto mb-2 opacity-30" />
                  Add events to build a compound scenario
                </div>
              )}
            </div>

            {/* Add event dropdown */}
            <div className="relative">
              <div className="flex gap-2">
                <button
                  onClick={() => setShowDropdown(!showDropdown)}
                  className="flex-1 flex items-center justify-between gap-2 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-[var(--text-primary)] hover:bg-white/[0.08] transition-colors"
                >
                  <span>{EVENT_TYPES.find((et) => et.value === addingType)?.label}</span>
                  <ChevronDown className={`w-4 h-4 transition-transform ${showDropdown ? "rotate-180" : ""}`} />
                </button>
                <OcButton onClick={addEvent} size="sm">
                  <Plus className="w-4 h-4 mr-1" /> {t("scenarios.add_event")}
                </OcButton>
              </div>

              <AnimatePresence>
                {showDropdown && (
                  <motion.div
                    initial={{ opacity: 0, y: -5 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -5 }}
                    className="absolute z-20 top-full left-0 right-0 mt-1 bg-fjord-abyss/95 border border-white/10 rounded-xl overflow-hidden backdrop-blur-xl shadow-xl"
                  >
                    {EVENT_TYPES.map((et) => (
                      <button
                        key={et.value}
                        onClick={() => { setAddingType(et.value); setShowDropdown(false); }}
                        className={`w-full text-left px-4 py-3 hover:bg-white/5 transition-colors ${
                          addingType === et.value ? "bg-salmon/10" : ""
                        }`}
                      >
                        <div className="text-sm font-medium text-[var(--text-primary)]">{et.label}</div>
                        <div className="text-xs text-[var(--text-secondary)]">{et.description}</div>
                      </button>
                    ))}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Run button */}
            <div className="mt-4">
              <OcButton
                onClick={runSimulation}
                disabled={events.length === 0 || running}
                className="w-full"
              >
                {running ? (
                  <><RefreshCw className="w-4 h-4 mr-2 animate-spin" /> Running Simulation...</>
                ) : (
                  <><Play className="w-4 h-4 mr-2" /> {t("scenarios.run_simulation")}</>
                )}
              </OcButton>
            </div>
          </GlassCard>

          {/* Saved Scenarios */}
          <GlassCard>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-display text-[var(--text-primary)] flex items-center gap-2">
                <FolderOpen className="w-4 h-4 text-salmon/60" /> Saved Scenarios
              </h3>
              {result && !result.error && (
                <OcButton onClick={saveScenario} variant="ghost" size="sm" disabled={saving}>
                  <Save className="w-3.5 h-3.5 mr-1" /> {saving ? "Saving..." : "Save"}
                </OcButton>
              )}
            </div>
            <div className="space-y-2 max-h-60 overflow-y-auto">
              {loadingScenarios && (
                <div className="text-xs text-[var(--text-secondary)] text-center py-3">Loading...</div>
              )}
              {!loadingScenarios && savedScenarios.length === 0 && (
                <div className="text-xs text-[var(--text-secondary)] text-center py-3">No saved compound scenarios</div>
              )}
              {savedScenarios.map((s) => (
                <div
                  key={s.id}
                  className="flex items-center justify-between bg-white/[0.02] border border-white/[0.04] rounded-lg px-3 py-2"
                >
                  <button
                    onClick={() => loadScenario(s)}
                    className="flex-1 text-left"
                  >
                    <div className="text-xs font-medium text-[var(--text-primary)] truncate">{s.scenario_name}</div>
                    <div className="text-[10px] text-[var(--text-secondary)]">
                      {s.created_at ? formatDate(s.created_at, locale) : ""}
                    </div>
                  </button>
                  <button
                    onClick={() => deleteScenario(s.id)}
                    className="p-1 hover:bg-white/10 rounded transition-colors ml-2"
                  >
                    <Trash2 className="w-3 h-3 text-[var(--text-secondary)]" />
                  </button>
                </div>
              ))}
            </div>
          </GlassCard>
        </div>

        {/* RIGHT: Results Panel */}
        <div className="lg:col-span-2 space-y-4">
          {/* Error state */}
          {result?.error && (
            <GlassCard>
              <div className="flex items-center gap-3 text-rose-400">
                <AlertTriangle className="w-5 h-5" />
                <span className="text-sm">{result.error}</span>
              </div>
            </GlassCard>
          )}

          {/* Cascade Narrative */}
          {result?.cascade_narrative && (
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
              <GlassCard className="border-violet-500/20 bg-gradient-to-br from-violet-500/[0.04] to-transparent">
                <div className="flex items-start gap-3">
                  <div className="w-8 h-8 rounded-lg bg-violet-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <Info className="w-4 h-4 text-violet-400" />
                  </div>
                  <div>
                    <h3 className="text-sm font-display text-violet-300 mb-2">Cascade Narrative</h3>
                    <pre className="text-xs text-[var(--text-secondary)] whitespace-pre-wrap font-sans leading-relaxed">
                      {result.cascade_narrative}
                    </pre>
                  </div>
                </div>
              </GlassCard>
            </motion.div>
          )}

          {/* Individual Event Impacts */}
          {result?.individual_impacts && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.1 }}>
              <GlassCard>
                <h3 className="text-sm font-display text-[var(--text-primary)] mb-4">Individual Event Impacts</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {result.individual_impacts.map((imp: any, i: number) => (
                    <div
                      key={i}
                      className={`rounded-xl border p-4 ${
                        imp.error
                          ? "bg-rose-500/5 border-rose-500/20"
                          : "bg-white/[0.02] border-white/[0.06]"
                      }`}
                    >
                      {imp.error ? (
                        <div className="text-xs text-rose-400">
                          <span className="font-medium">Event {i + 1} failed:</span> {imp.error}
                        </div>
                      ) : (
                        <>
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-xs font-medium text-[var(--text-primary)]">
                              {imp.event_description || imp.event_type}
                            </span>
                            <SeverityBadge severity={imp.severity || "medium"} />
                          </div>
                          <div className="grid grid-cols-2 gap-2 text-xs">
                            <div>
                              <span className="text-[var(--text-secondary)]">Revenue</span>
                              <div className="font-mono text-[var(--text-primary)]">
                                {(imp.total_revenue_impact_mnok || 0).toFixed(1)} MNOK
                              </div>
                            </div>
                            <div>
                              <span className="text-[var(--text-secondary)]">Production</span>
                              <div className="font-mono text-[var(--text-primary)]">
                                {(imp.national_production_impact_pct || 0).toFixed(3)}%
                              </div>
                            </div>
                            <div>
                              <span className="text-[var(--text-secondary)]">Price Effect</span>
                              <div className="font-mono text-[var(--text-primary)]">
                                {(imp.price_impact_pct || 0).toFixed(2)}%
                              </div>
                            </div>
                            <div>
                              <span className="text-[var(--text-secondary)]">Companies</span>
                              <div className="font-mono text-[var(--text-primary)]">
                                {(imp.company_impacts || []).length} affected
                              </div>
                            </div>
                          </div>
                        </>
                      )}
                    </div>
                  ))}
                </div>
              </GlassCard>
            </motion.div>
          )}

          {/* Interaction Effects */}
          {result?.interaction_effects && result.interaction_effects.length > 0 && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.2 }}>
              <GlassCard className="border-amber-500/20">
                <h3 className="text-sm font-display text-amber-300 mb-3 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4" /> Interaction Effects (Stress Cascades)
                </h3>
                <div className="space-y-3">
                  {result.interaction_effects.map((ix: any, i: number) => (
                    <div key={i} className="bg-amber-500/[0.04] border border-amber-500/10 rounded-lg p-3">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-medium text-amber-300">
                          {ix.combination.join(" + ")}
                        </span>
                        <span className="text-xs font-mono text-amber-400">
                          {ix.multiplier}x ({ix.additional_impact_mnok > 0 ? "+" : ""}{ix.additional_impact_mnok} MNOK)
                        </span>
                      </div>
                      <p className="text-xs text-[var(--text-secondary)] leading-relaxed">{ix.narrative}</p>
                      <p className="text-[10px] text-[var(--text-secondary)] mt-1 opacity-60">Source: {ix.source}</p>
                    </div>
                  ))}
                </div>
              </GlassCard>
            </motion.div>
          )}

          {/* Company Impact Breakdown */}
          {compound?.company_impacts && compound.company_impacts.length > 0 && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }}>
              <GlassCard>
                <h3 className="text-sm font-display text-[var(--text-primary)] mb-3">Company Impact Summary</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-white/[0.06]">
                        <th className="text-left py-2 text-[var(--text-secondary)] font-medium">Company</th>
                        <th className="text-right py-2 text-[var(--text-secondary)] font-medium">Revenue MNOK</th>
                        <th className="text-right py-2 text-[var(--text-secondary)] font-medium">EBIT MNOK</th>
                        <th className="text-right py-2 text-[var(--text-secondary)] font-medium">Production (t)</th>
                        <th className="text-right py-2 text-[var(--text-secondary)] font-medium">Events</th>
                      </tr>
                    </thead>
                    <tbody>
                      {compound.company_impacts.map((ci: any, i: number) => (
                        <tr key={i} className="border-b border-white/[0.03] hover:bg-white/[0.02]">
                          <td className="py-2 text-[var(--text-primary)]">
                            <span className="font-medium">{ci.ticker}</span>
                            <span className="text-[var(--text-secondary)] ml-1">{ci.company_name}</span>
                          </td>
                          <td className={`py-2 text-right font-mono ${ci.total_revenue_impact_mnok < 0 ? "text-rose-400" : "text-emerald-400"}`}>
                            {ci.total_revenue_impact_mnok.toFixed(1)}
                          </td>
                          <td className={`py-2 text-right font-mono ${ci.total_ebit_impact_mnok < 0 ? "text-rose-400" : "text-emerald-400"}`}>
                            {ci.total_ebit_impact_mnok.toFixed(1)}
                          </td>
                          <td className="py-2 text-right font-mono text-[var(--text-primary)]">
                            {ci.total_production_impact_tonnes.toLocaleString()}
                          </td>
                          <td className="py-2 text-right text-[var(--text-secondary)]">{ci.events_affecting}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </GlassCard>
            </motion.div>
          )}

          {/* Empty state */}
          {!result && (
            <GlassCard>
              <div className="text-center py-16">
                <Layers className="w-12 h-12 mx-auto mb-4 text-violet-400/30" />
                <h3 className="text-lg font-display text-[var(--text-primary)] mb-2">Build Your Scenario</h3>
                <p className="text-sm text-[var(--text-secondary)] max-w-md mx-auto">
                  Add multiple events from the builder on the left, then run the simulation to see
                  how they interact. Example: ISA outbreak in PA 3 + feed spike + red traffic light in PA 5.
                </p>
              </div>
            </GlassCard>
          )}
        </div>
      </div>
    </div>
    </ErrorBoundary>
  );
}

