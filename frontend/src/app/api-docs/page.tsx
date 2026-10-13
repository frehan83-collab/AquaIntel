"use client";
import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ChevronDown, ChevronUp, Copy, Check, ExternalLink,
  Bug, Shield, DollarSign, Brain, Ship, Sparkles, Bell,
  Globe2, Layers, FlaskConical, Lock, Zap, BookOpen, Code2,
  Key, Plus, RotateCw, Trash2, AlertTriangle, Eye, EyeOff,
} from "lucide-react";
import { api } from "@/lib/api";
import { useTranslation, formatDate } from "@/lib/i18n";

const BASE_URL = "https://api.fishintel.io";

type EndpointCategory = {
  tag: string;
  icon: any;
  color: string;
  description: string;
  endpoints: { method: string; path: string; summary: string; sample?: string }[];
};

const CATEGORIES: EndpointCategory[] = [
  {
    tag: "Lice Intelligence",
    icon: Bug,
    color: "text-rose-400",
    description: "Real-time sea lice data from 1,815 Norwegian farms via BarentsWatch. GNN spread prediction and anomaly detection.",
    endpoints: [
      { method: "GET", path: "/api/lice/summary", summary: "Aggregated lice statistics by production area", sample: '{ "pa": 3, "avg_adult_female": 0.12, "farms_above_limit": 4, "data_provenance": { "source": "BarentsWatch", "confidence": 0.95 } }' },
      { method: "GET", path: "/api/lice/weekly?pa={pa}", summary: "Weekly lice time series for a production area" },
      { method: "GET", path: "/api/gnn/predict?locality={id}", summary: "GNN-based lice spread forecast for a farm" },
    ],
  },
  {
    tag: "Disease Monitoring",
    icon: Shield,
    color: "text-amber-400",
    description: "ISA, PD, and other disease alerts from Mattilsynet, WOAH, and Sernapesca. Per-company exposure tracking.",
    endpoints: [
      { method: "GET", path: "/api/disease/alerts", summary: "Active disease outbreaks across all monitored countries", sample: '{ "alerts": [{ "country": "Norway", "disease": "ISA", "pa": 4, "date": "2026-03-28" }], "total": 3 }' },
      { method: "GET", path: "/api/disease/norway", summary: "Norwegian disease cases from Mattilsynet" },
      { method: "GET", path: "/api/disease/treatments/{year}", summary: "Treatment and resistance data by year" },
      { method: "GET", path: "/api/disease/by-company", summary: "Per-company disease exposure counts" },
      { method: "GET", path: "/api/anomaly/scores", summary: "Composite anomaly scores (lice + SST + mortality + disease)" },
    ],
  },
  {
    tag: "Market & Pricing",
    icon: DollarSign,
    color: "text-emerald-400",
    description: "SSB spot prices, TFT price predictions, feed cost models, forward curves, and sentiment analysis. 12 FRED series.",
    endpoints: [
      { method: "GET", path: "/api/market/price-outlook", summary: "Current spot price + TFT prediction with quantile bands", sample: '{ "spot_nok": 94.4, "prediction": { "horizon_weeks": 8, "median": 97.2, "q10": 88.1, "q90": 105.3 }, "data_provenance": { "source": "SSB + TFT" } }' },
      { method: "GET", path: "/api/feed-cost/composite-index", summary: "Proprietary weighted feed cost index from 5 FRED ingredients" },
      { method: "GET", path: "/api/competitiveness/origin-index", summary: "FX-adjusted cost ranking across 6 origins" },
      { method: "GET", path: "/api/market/spot-price", summary: "Latest SSB salmon spot price in NOK and USD" },
      { method: "GET", path: "/api/market/forward-curve", summary: "Synthetic forward curve (marked as synthetic)" },
      { method: "GET", path: "/api/sentiment/summary", summary: "Aggregated market sentiment from RSS feeds" },
      { method: "GET", path: "/api/feed-cost/peru-anchovy", summary: "Peru anchovy season + ONI fishmeal lead indicator" },
      { method: "POST", path: "/api/competitiveness/tariff-scenario", summary: "Recalculate origin rankings with modified tariffs" },
    ],
  },
  {
    tag: "Decision Engine",
    icon: Brain,
    color: "text-cyan-400",
    description: "Farm-level decision cards combining GNN, lice data, SST, MET.no forecasts, and treatment economics into actionable TREAT/MONITOR/WAIT signals.",
    endpoints: [
      { method: "GET", path: "/api/decision/{locality_no}", summary: "Decision card for a specific farm", sample: '{ "action": "TREAT_NOW", "method": "MECHANICAL", "roi": 3.2, "lice_current": 0.45, "ocean_forecast": { "sst": 11.2 } }' },
      { method: "GET", path: "/api/decision/portfolio/{company}", summary: "All decision cards for a company portfolio" },
      { method: "POST", path: "/api/treatment/log-outcome", summary: "Log farmer-reported treatment outcome" },
      { method: "GET", path: "/api/treatment/efficacy-by-method", summary: "Aggregated efficacy statistics per treatment method" },
      { method: "GET", path: "/api/ocean/forecast/pa/{pa}", summary: "MET.no ocean forecast for a production area" },
      { method: "GET", path: "/api/traffic-light/current", summary: "Current traffic light status for all 13 PAs" },
    ],
  },
  {
    tag: "Supply Chain",
    icon: Ship,
    color: "text-blue-400",
    description: "7-country supply balance model, smolt-to-harvest forecasting, AIS vessel tracking, and global disruption monitoring.",
    endpoints: [
      { method: "GET", path: "/api/supply/summary", summary: "Global supply balance across 7 countries" },
      { method: "GET", path: "/api/supply/smolt-forecast", summary: "18-month cohort-based supply pipeline", sample: '{ "pipeline": [{ "month_label": "2026-06", "projected_harvest_tonnes": 142000, "lo80": 118000, "hi80": 166000 }], "horizon_months": 18, "total_harvest_tonnes": 1720000, "data_provenance": { "source": "Smolt model + Fiskeridirektoratet + BarentsWatch", "is_live": true, "confidence": 0.75 } }' },
      { method: "GET", path: "/api/supply/demand-balance", summary: "Supply-demand balance with price pressure signal" },
      { method: "GET", path: "/api/ais/harvest-intelligence", summary: "AIS vessel activity and harvest signal detection" },
      { method: "GET", path: "/api/canada/snapshot", summary: "Canada/BC aquaculture intelligence from DFO" },
      { method: "GET", path: "/api/scotland/snapshot", summary: "Scotland aquaculture snapshot" },
      { method: "GET", path: "/api/iceland/snapshot", summary: "Iceland aquaculture snapshot (5 live sources)" },
      { method: "GET", path: "/api/faroe/snapshot", summary: "Faroe Islands aquaculture snapshot" },
    ],
  },
  {
    tag: "ML Models",
    icon: Sparkles,
    color: "text-violet-400",
    description: "Temporal Fusion Transformer, Chronos-2 zero-shot baselines, XGBoost fallback, and model comparison framework.",
    endpoints: [
      { method: "GET", path: "/api/ml/chronos/price", summary: "Chronos-2 zero-shot price forecast" },
      { method: "GET", path: "/api/ml/chronos/lice", summary: "Chronos-2 zero-shot lice forecast" },
      { method: "GET", path: "/api/ml/chronos/compare", summary: "Model comparison: Chronos vs TFT vs naive (MAPE, RMSE)", sample: '{ "models": [{ "name": "TFT", "mape": 4.2, "rmse": 3.1 }, { "name": "Chronos", "mape": 5.8, "rmse": 4.0 }] }' },
      { method: "GET", path: "/api/causal/granger", summary: "Granger causality relationships and lag structure" },
      { method: "GET", path: "/api/causal/transfer-entropy", summary: "Transfer entropy lice-to-price lag analysis" },
      { method: "POST", path: "/api/ml/chronos/custom", summary: "Custom time series forecast with Chronos-2" },
    ],
  },
  {
    tag: "Notifications",
    icon: Bell,
    color: "text-pink-400",
    description: "Threshold-based alert system for lice, price, and temperature breaches with configurable thresholds.",
    endpoints: [
      { method: "GET", path: "/api/notifications/alerts", summary: "Current active threshold alerts" },
      { method: "GET", path: "/api/notifications/thresholds", summary: "Configured alert thresholds" },
      { method: "POST", path: "/api/notifications/thresholds", summary: "Create or update an alert threshold" },
    ],
  },
  {
    tag: "Countries",
    icon: Globe2,
    color: "text-teal-400",
    description: "Per-country intelligence for Norway, Canada/BC, Scotland, Iceland, Faroe Islands, Chile, and China demand indicators.",
    endpoints: [
      { method: "GET", path: "/api/norway/production/monthly", summary: "Norwegian monthly production volumes" },
      { method: "GET", path: "/api/canada/lice", summary: "Canada DFO per-farm monthly lice data" },
      { method: "GET", path: "/api/canada/farms", summary: "BC farm GeoJSON with DFO-extracted locations" },
      { method: "GET", path: "/api/iceland/production", summary: "Iceland production from Statistics Iceland PxWeb" },
      { method: "GET", path: "/api/iceland/exports", summary: "Iceland export data by species and country" },
      { method: "GET", path: "/api/chile/farms", summary: "Chile farm regions with ISA/SRS overlay" },
    ],
  },
  {
    tag: "Scenarios",
    icon: Layers,
    color: "text-orange-400",
    description: "Event impact modeling, compound scenario sandbox, and saved scenario management for what-if analysis.",
    endpoints: [
      { method: "POST", path: "/api/scenarios/compound", summary: "Run compound multi-event scenario simulation", sample: '{ "events": ["ISA_OUTBREAK", "FEED_SHOCK"], "compound_multiplier": 1.15, "total_impact_nok": -2400000000 }' },
      { method: "POST", path: "/api/scenarios/save", summary: "Save a scenario configuration" },
      { method: "GET", path: "/api/scenarios/list", summary: "List saved scenarios for current user" },
      { method: "DELETE", path: "/api/scenarios/{id}", summary: "Delete a saved scenario" },
    ],
  },
  {
    tag: "Efficacy Marketplace",
    icon: FlaskConical,
    color: "text-lime-400",
    description: "Crowdsourced treatment efficacy data with privacy-preserving aggregation. Minimum 3 data points per cell.",
    endpoints: [
      { method: "GET", path: "/api/efficacy/benchmarks", summary: "Industry-wide efficacy benchmarks per treatment method", sample: '{ "methods": [{ "method": "MECHANICAL", "avg_reduction": 78.2, "sample_size": 142 }] }' },
      { method: "GET", path: "/api/efficacy/by-region", summary: "PA x method efficacy matrix" },
      { method: "GET", path: "/api/efficacy/by-season", summary: "Monthly/seasonal efficacy patterns" },
      { method: "GET", path: "/api/efficacy/explore", summary: "Multi-dimensional efficacy query (method, PA, temp, season)" },
    ],
  },
];

const CODE_EXAMPLES = {
  python: `import httpx

# Option 1: JWT Token
client = httpx.Client(
    base_url="${BASE_URL}",
    headers={"Authorization": f"Bearer {token}"}
)

# Option 2: API Key (recommended for scripts)
client = httpx.Client(
    base_url="${BASE_URL}",
    headers={"X-API-Key": "oc_live_your_key_here"}
)

# Fetch lice summary for Production Area 3
resp = client.get("/api/lice/summary", params={"pa": 3})
data = resp.json()
print(f"Avg adult female lice: {data['avg_adult_female']}")
print(f"Source: {data['data_provenance']['source']}")`,

  javascript: `// Using API Key
const response = await fetch(
  "${BASE_URL}/api/market/price-outlook",
  {
    headers: {
      "X-API-Key": "oc_live_your_key_here",
      "Content-Type": "application/json"
    }
  }
);

const data = await response.json();
console.log(\`Spot: \${data.spot_nok} NOK/kg\`);
console.log(\`8-week forecast: \${data.prediction.median}\`);`,

  curl: `# Using API Key header
curl -X GET "${BASE_URL}/api/decision/12345" \\
  -H "X-API-Key: oc_live_your_key_here"

# Or using query parameter
curl "${BASE_URL}/api/decision/12345?api_key=oc_live_your_key_here"

# Response:
# {
#   "action": "TREAT_NOW",
#   "method": "MECHANICAL",
#   "roi": 3.2,
#   "lice_current": 0.45
# }`,
};

const METHOD_COLORS: Record<string, string> = {
  GET: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
  POST: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  PUT: "bg-amber-500/20 text-amber-400 border-amber-500/30",
  DELETE: "bg-rose-500/20 text-rose-400 border-rose-500/30",
};

function MethodBadge({ method }: { method: string }) {
  return (
    <span className={`inline-block px-2 py-0.5 text-[10px] font-bold rounded border ${METHOD_COLORS[method] || "bg-white/10 text-white/60"}`}>
      {method}
    </span>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000); }}
      className="p-1.5 rounded-lg hover:bg-white/[0.08] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
      title="Copy to clipboard"
      aria-label="Copy to clipboard"
    >
      {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
    </button>
  );
}

function CollapsibleSection({ category }: { category: EndpointCategory }) {
  const [open, setOpen] = useState(false);
  const Icon = category.icon;

  return (
    <div className="rounded-2xl bg-white/[0.03] border border-white/[0.06] overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-3 px-5 py-4 hover:bg-white/[0.02] transition-colors text-left"
        aria-label={`${open ? "Collapse" : "Expand"} ${category.tag} endpoints`}
      >
        <Icon className={`w-5 h-5 ${category.color} flex-shrink-0`} />
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">{category.tag}</h3>
          <p className="text-[11px] text-[var(--text-secondary)] truncate">{category.description}</p>
        </div>
        <span className="text-[10px] text-[var(--text-secondary)] px-2 py-0.5 rounded-full bg-white/[0.06] flex-shrink-0">
          {category.endpoints.length}
        </span>
        {open ? <ChevronUp className="w-4 h-4 text-[var(--text-secondary)]" /> : <ChevronDown className="w-4 h-4 text-[var(--text-secondary)]" />}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="px-5 pb-4 space-y-2 border-t border-white/[0.04] pt-3">
              {category.endpoints.map((ep, i) => (
                <div key={i} className="group rounded-xl bg-white/[0.02] border border-white/[0.04] p-3 hover:bg-white/[0.04] transition-colors">
                  <div className="flex items-center gap-2 mb-1">
                    <MethodBadge method={ep.method} />
                    <code className="text-[12px] text-ocean-400 font-mono flex-1 truncate">{ep.path}</code>
                    <CopyButton text={`${BASE_URL}${ep.path}`} />
                  </div>
                  <p className="text-[11px] text-[var(--text-secondary)] ml-1">{ep.summary}</p>
                  {ep.sample && (
                    <div className="mt-2 relative">
                      <pre className="text-[10px] text-[var(--text-secondary)] bg-black/30 rounded-lg p-2.5 overflow-x-auto font-mono leading-relaxed">
                        {ep.sample}
                      </pre>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

type APIKeyInfo = {
  id: number;
  name: string | null;
  key_prefix: string | null;
  tier: string;
  is_active: boolean;
  created_at: string | null;
  last_used: string | null;
  expires_at: string | null;
  rate_limit: number;
  raw_key?: string;
};

function APIKeysSection() {
  const { locale } = useTranslation();
  const [keys, setKeys] = useState<APIKeyInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [newKeyName, setNewKeyName] = useState("My API Key");
  const [creating, setCreating] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newlyCreatedKey, setNewlyCreatedKey] = useState<string | null>(null);
  const [copiedKey, setCopiedKey] = useState(false);
  const [revealedKey, setRevealedKey] = useState(false);

  const loadKeys = useCallback(async () => {
    try {
      setLoading(true);
      const data = await api.apiKeysList();
      setKeys(data.keys || []);
      setError(null);
    } catch {
      setError("Sign in to manage API keys");
      setKeys([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadKeys(); }, [loadKeys]);

  const handleCreate = async () => {
    setCreating(true);
    try {
      const result = await api.apiKeysCreate({ name: newKeyName });
      setNewlyCreatedKey(result.raw_key);
      setRevealedKey(false);
      setCopiedKey(false);
      setShowCreateForm(false);
      setNewKeyName("My API Key");
      await loadKeys();
    } catch (e: any) {
      setError(e.message || "Failed to create key");
    } finally {
      setCreating(false);
    }
  };

  const handleRevoke = async (id: number) => {
    try {
      await api.apiKeysRevoke(id);
      await loadKeys();
    } catch (e: any) {
      setError(e.message || "Failed to revoke key");
    }
  };

  const handleRotate = async (id: number) => {
    try {
      const result = await api.apiKeysRotate(id);
      setNewlyCreatedKey(result.raw_key);
      setRevealedKey(false);
      setCopiedKey(false);
      await loadKeys();
    } catch (e: any) {
      setError(e.message || "Failed to rotate key");
    }
  };

  const copyNewKey = () => {
    if (newlyCreatedKey) {
      navigator.clipboard.writeText(newlyCreatedKey);
      setCopiedKey(true);
      setTimeout(() => setCopiedKey(false), 2000);
    }
  };

  return (
    <div className="space-y-4">
      {/* Newly created key warning */}
      <AnimatePresence>
        {newlyCreatedKey && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="rounded-xl bg-amber-500/10 border border-amber-500/20 p-4"
          >
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-amber-400 mb-1">Save your API key now</p>
                <p className="text-[11px] text-[var(--text-secondary)] mb-3">
                  This is the only time the full key will be shown. Copy it and store it securely.
                </p>
                <div className="flex items-center gap-2 bg-black/30 rounded-lg px-3 py-2">
                  <code className="text-sm text-ocean-400 font-mono flex-1 truncate">
                    {revealedKey ? newlyCreatedKey : newlyCreatedKey.slice(0, 12) + "..." + newlyCreatedKey.slice(-4)}
                  </code>
                  <button
                    onClick={() => setRevealedKey(!revealedKey)}
                    className="p-1 rounded hover:bg-white/[0.08] text-[var(--text-secondary)]"
                    title={revealedKey ? "Hide key" : "Reveal key"}
                    aria-label={revealedKey ? "Hide API key" : "Reveal API key"}
                  >
                    {revealedKey ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                  </button>
                  <button
                    onClick={copyNewKey}
                    className="p-1 rounded hover:bg-white/[0.08] text-[var(--text-secondary)]"
                    title="Copy key"
                    aria-label="Copy API key"
                  >
                    {copiedKey ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  </button>
                </div>
                <button
                  onClick={() => setNewlyCreatedKey(null)}
                  className="mt-2 text-[11px] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                  aria-label="Dismiss API key notification"
                >
                  I&apos;ve saved my key
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Error */}
      {error && (
        <div className="text-[11px] text-amber-400 bg-amber-500/10 rounded-lg px-3 py-2">
          {error}
        </div>
      )}

      {/* Keys table */}
      {loading ? (
        <div className="text-center text-[var(--text-secondary)] text-[12px] py-6">Loading keys...</div>
      ) : keys.length === 0 && !error ? (
        <div className="text-center py-6">
          <Key className="w-8 h-8 text-[var(--text-secondary)] mx-auto mb-2 opacity-40" />
          <p className="text-[12px] text-[var(--text-secondary)]">No API keys yet. Create one to get started.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {keys.map((k) => (
            <div
              key={k.id}
              className={`rounded-xl border p-3 flex items-center gap-3 ${
                k.is_active
                  ? "bg-white/[0.02] border-white/[0.06]"
                  : "bg-white/[0.01] border-white/[0.03] opacity-50"
              }`}
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="text-[12px] font-semibold text-[var(--text-primary)]">{k.name || "Unnamed"}</span>
                  <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-medium ${
                    k.is_active
                      ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                      : "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                  }`}>
                    {k.is_active ? "Active" : "Revoked"}
                  </span>
                  <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-white/[0.04] text-[var(--text-secondary)] border border-white/[0.06]">
                    {k.tier}
                  </span>
                </div>
                <div className="flex items-center gap-3 text-[10px] text-[var(--text-secondary)]">
                  <code className="font-mono">{k.key_prefix}...****</code>
                  <span>Created {k.created_at ? formatDate(k.created_at, locale) : "N/A"}</span>
                  {k.last_used && <span>Last used {formatDate(k.last_used, locale)}</span>}
                  <span>{k.rate_limit} req/min</span>
                  {k.expires_at && (
                    <span className={new Date(k.expires_at) < new Date() ? "text-rose-400" : ""}>
                      Expires {formatDate(k.expires_at, locale)}
                    </span>
                  )}
                </div>
              </div>
              {k.is_active && (
                <div className="flex items-center gap-1 flex-shrink-0">
                  <button
                    onClick={() => handleRotate(k.id)}
                    className="p-1.5 rounded-lg hover:bg-white/[0.08] text-[var(--text-secondary)] hover:text-ocean-400 transition-colors"
                    title="Rotate key"
                    aria-label={`Rotate API key "${k.name || "Unnamed"}"`}
                  >
                    <RotateCw className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => handleRevoke(k.id)}
                    className="p-1.5 rounded-lg hover:bg-rose-500/10 text-[var(--text-secondary)] hover:text-rose-400 transition-colors"
                    title="Revoke key"
                    aria-label={`Revoke API key "${k.name || "Unnamed"}"`}
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Create form */}
      <AnimatePresence>
        {showCreateForm && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="rounded-xl bg-white/[0.02] border border-white/[0.06] p-4 space-y-3"
          >
            <div>
              <label className="text-[11px] text-[var(--text-secondary)] uppercase tracking-wider font-medium">Key Name</label>
              <input
                value={newKeyName}
                onChange={(e) => setNewKeyName(e.target.value)}
                className="mt-1 w-full bg-black/30 rounded-lg px-3 py-2 text-sm text-[var(--text-primary)] border border-white/[0.06] outline-hidden focus:border-ocean-500/40"
                placeholder="e.g., Production App, CI Pipeline"
              />
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleCreate}
                disabled={creating || !newKeyName.trim()}
                className="px-4 py-2 rounded-lg bg-ocean-500/20 text-ocean-400 text-[12px] font-medium hover:bg-ocean-500/30 disabled:opacity-40 transition-colors border border-ocean-500/20"
                aria-label="Generate API key"
              >
                {creating ? "Generating..." : "Generate Key"}
              </button>
              <button
                onClick={() => setShowCreateForm(false)}
                className="px-4 py-2 rounded-lg text-[var(--text-secondary)] text-[12px] font-medium hover:bg-white/[0.06] transition-colors"
                aria-label="Cancel key creation"
              >
                Cancel
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Generate button */}
      {!showCreateForm && (
        <button
          onClick={() => setShowCreateForm(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-ocean-500/20 text-ocean-400 text-[12px] font-medium hover:bg-ocean-500/30 transition-colors border border-ocean-500/20"
          aria-label="Generate new API key"
        >
          <Plus className="w-3.5 h-3.5" />
          Generate New Key
        </button>
      )}

      {/* Usage instructions */}
      <div className="rounded-xl bg-white/[0.02] border border-white/[0.04] p-4 space-y-2">
        <p className="text-[11px] font-medium text-[var(--text-primary)]">Using API Keys</p>
        <div className="space-y-1.5 text-[10px] text-[var(--text-secondary)] font-mono">
          <p className="text-[10px] text-[var(--text-secondary)] font-sans mb-1">Pass your key via header or query parameter:</p>
          <div className="bg-black/30 rounded-lg p-2.5 leading-relaxed">
            <p className="text-ocean-400"># Header (recommended)</p>
            <p>curl -H &quot;X-API-Key: oc_live_...&quot; {BASE_URL}/api/lice/summary</p>
            <p className="text-ocean-400 mt-2"># Query parameter</p>
            <p>curl &quot;{BASE_URL}/api/lice/summary?api_key=oc_live_...&quot;</p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function APIDocsPage() {
  const { t, locale } = useTranslation();
  const [activeTab, setActiveTab] = useState<"python" | "javascript" | "curl">("python");

  return (
    <div className="min-h-screen p-4 md:p-8 space-y-8 max-w-5xl mx-auto">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex flex-col sm:flex-row sm:items-center gap-4 mb-2">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-ocean-500 to-ocean-600 flex items-center justify-center shadow-[0_0_24px_rgba(0,212,200,0.2)]">
              <Code2 className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-2xl md:text-3xl font-bold text-[var(--text-primary)] tracking-tight">{t("page.api_docs.title")}</h1>
              <p className="text-[11px] text-[var(--text-secondary)]">Aquaculture Intelligence for Developers</p>
            </div>
          </div>
          <div className="flex items-center gap-2 sm:ml-auto">
            <span className="px-2.5 py-1 rounded-full bg-ocean-500/[0.12] text-ocean-400 text-[11px] font-semibold border border-ocean-500/20">
              v2.1.0
            </span>
            <a href="/api/docs" target="_blank" className="px-3 py-1.5 rounded-lg bg-white/[0.06] text-[var(--text-secondary)] hover:text-[var(--text-primary)] text-[11px] font-medium flex items-center gap-1.5 hover:bg-white/[0.1] transition-colors border border-white/[0.06]">
              Swagger <ExternalLink className="w-3 h-3" />
            </a>
            <a href="/api/redoc" target="_blank" className="px-3 py-1.5 rounded-lg bg-white/[0.06] text-[var(--text-secondary)] hover:text-[var(--text-primary)] text-[11px] font-medium flex items-center gap-1.5 hover:bg-white/[0.1] transition-colors border border-white/[0.06]">
              ReDoc <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        </div>
      </motion.div>

      {/* Quick Start */}
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}
        className="rounded-2xl bg-white/[0.03] border border-white/[0.06] p-5 md:p-6 space-y-5"
      >
        <div className="flex items-center gap-2 mb-1">
          <Zap className="w-4 h-4 text-amber-400" />
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">Quick Start</h2>
        </div>

        {/* Base URL */}
        <div>
          <p className="text-[11px] text-[var(--text-secondary)] uppercase tracking-wider font-medium mb-1.5">Base URL</p>
          <div className="flex items-center gap-2 bg-black/30 rounded-lg px-3 py-2">
            <code className="text-sm text-ocean-400 font-mono flex-1">{BASE_URL}</code>
            <CopyButton text={BASE_URL} />
          </div>
        </div>

        {/* Auth Flow */}
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Lock className="w-3.5 h-3.5 text-amber-400" />
            <p className="text-[11px] text-[var(--text-secondary)] uppercase tracking-wider font-medium">Authentication (JWT)</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {[
              { step: "1", title: "Register", code: "POST /api/auth/register\n{ \"email\": \"dev@example.com\",\n  \"password\": \"...\" }" },
              { step: "2", title: "Login", code: "POST /api/auth/login\n{ \"email\": \"dev@example.com\",\n  \"password\": \"...\" }\n=> { \"token\": \"eyJ...\" }" },
              { step: "3", title: "Use Token", code: "GET /api/lice/summary\nAuthorization: Bearer eyJ..." },
            ].map((s) => (
              <div key={s.step} className="rounded-xl bg-white/[0.02] border border-white/[0.04] p-3">
                <div className="flex items-center gap-2 mb-2">
                  <span className="w-5 h-5 rounded-full bg-ocean-500/20 text-ocean-400 text-[10px] font-bold flex items-center justify-center">{s.step}</span>
                  <span className="text-[12px] font-semibold text-[var(--text-primary)]">{s.title}</span>
                </div>
                <pre className="text-[10px] text-[var(--text-secondary)] font-mono leading-relaxed whitespace-pre-wrap">{s.code}</pre>
              </div>
            ))}
          </div>
        </div>

        {/* Rate Limits */}
        <div>
          <p className="text-[11px] text-[var(--text-secondary)] uppercase tracking-wider font-medium mb-1.5">Rate Limits</p>
          <div className="flex flex-wrap gap-2">
            {[
              { tier: "Global", limit: "200/min" },
              { tier: "Login", limit: "10/min" },
              { tier: "Register", limit: "5/min" },
              { tier: "Institutional", limit: "50K/day" },
            ].map((r) => (
              <span key={r.tier} className="px-2.5 py-1 rounded-lg bg-white/[0.04] border border-white/[0.06] text-[11px] text-[var(--text-secondary)]">
                <span className="text-[var(--text-primary)] font-medium">{r.tier}:</span> {r.limit}
              </span>
            ))}
          </div>
        </div>
      </motion.div>

      {/* API Keys Management */}
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08 }}
        className="rounded-2xl bg-white/[0.03] border border-white/[0.06] p-5 md:p-6"
      >
        <div className="flex items-center gap-2 mb-4">
          <Key className="w-4 h-4 text-violet-400" />
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">API Keys</h2>
          <span className="text-[10px] text-[var(--text-secondary)] ml-1">Programmatic access for developers &amp; integrators</span>
        </div>
        <APIKeysSection />
      </motion.div>

      {/* Endpoint Categories */}
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
        <div className="flex items-center gap-2 mb-4">
          <BookOpen className="w-4 h-4 text-ocean-400" />
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">Endpoint Reference</h2>
          <span className="text-[11px] text-[var(--text-secondary)] ml-1">229 endpoints across 10 categories</span>
        </div>
        <div className="space-y-3">
          {CATEGORIES.map((cat) => (
            <CollapsibleSection key={cat.tag} category={cat} />
          ))}
        </div>
      </motion.div>

      {/* Code Examples */}
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}
        className="rounded-2xl bg-white/[0.03] border border-white/[0.06] overflow-hidden"
      >
        <div className="px-5 pt-5 pb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Code2 className="w-4 h-4 text-violet-400" />
            <h2 className="text-lg font-semibold text-[var(--text-primary)]">Code Examples</h2>
          </div>
          <div className="flex rounded-lg bg-white/[0.04] border border-white/[0.06] p-0.5">
            {(["python", "javascript", "curl"] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-3 py-1 rounded-md text-[11px] font-medium transition-colors ${
                  activeTab === tab
                    ? "bg-ocean-500/20 text-ocean-400"
                    : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                }`}
                aria-label={`Show ${tab === "python" ? "Python" : tab === "javascript" ? "JavaScript" : "cURL"} example`}
              >
                {tab === "python" ? "Python" : tab === "javascript" ? "JavaScript" : "cURL"}
              </button>
            ))}
          </div>
        </div>
        <div className="px-5 pb-5 relative">
          <div className="absolute top-2 right-7">
            <CopyButton text={CODE_EXAMPLES[activeTab]} />
          </div>
          <pre className="text-[11px] text-[var(--text-secondary)] bg-black/30 rounded-xl p-4 overflow-x-auto font-mono leading-relaxed">
            {CODE_EXAMPLES[activeTab]}
          </pre>
        </div>
      </motion.div>

      {/* Data Provenance Explainer */}
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
        className="rounded-2xl bg-white/[0.03] border border-white/[0.06] p-5 md:p-6"
      >
        <div className="flex items-center gap-2 mb-3">
          <Shield className="w-4 h-4 text-emerald-400" />
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">Data Provenance</h2>
        </div>
        <p className="text-[12px] text-[var(--text-secondary)] leading-relaxed mb-4">
          Every FishIntel API response includes a <code className="text-ocean-400 bg-ocean-500/10 px-1 rounded">data_provenance</code> field
          that tells you exactly where the data comes from, how fresh it is, and how confident the system is in the result.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {[
            { field: "source", desc: "Origin of the data (e.g., BarentsWatch, SSB, FRED, MET.no)", example: '"BarentsWatch NLOD 2.0"' },
            { field: "confidence", desc: "0.0 to 1.0 confidence score. Below 0.5 indicates degraded or simulated data.", example: "0.95" },
            { field: "freshness", desc: "How recently the data was fetched: live, recent, stale, or historical.", example: '"live"' },
          ].map((f) => (
            <div key={f.field} className="rounded-xl bg-white/[0.02] border border-white/[0.04] p-3">
              <code className="text-[12px] text-ocean-400 font-mono font-semibold">{f.field}</code>
              <p className="text-[11px] text-[var(--text-secondary)] mt-1 leading-relaxed">{f.desc}</p>
              <p className="text-[10px] text-[var(--text-secondary)] mt-1.5 font-mono bg-black/20 rounded px-1.5 py-0.5 inline-block">{f.example}</p>
            </div>
          ))}
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <span className="px-2 py-1 rounded-lg text-[10px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">LIVE: confidence &ge; 0.8</span>
          <span className="px-2 py-1 rounded-lg text-[10px] font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">DEGRADED: 0.5 &ndash; 0.8</span>
          <span className="px-2 py-1 rounded-lg text-[10px] font-medium bg-rose-500/10 text-rose-400 border border-rose-500/20">SIMULATED: &lt; 0.5</span>
          <span className="px-2 py-1 rounded-lg text-[10px] font-medium bg-violet-500/10 text-violet-400 border border-violet-500/20">SYNTHETIC: model-generated</span>
        </div>
      </motion.div>

      {/* Bottom Links */}
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }}
        className="flex flex-col sm:flex-row gap-3"
      >
        <a href="/billing" className="flex-1 rounded-2xl bg-white/[0.03] border border-white/[0.06] p-5 hover:bg-white/[0.05] transition-colors group">
          <div className="flex items-center gap-2 mb-1">
            <DollarSign className="w-4 h-4 text-amber-400" />
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">Pricing &amp; Plans</h3>
          </div>
          <p className="text-[11px] text-[var(--text-secondary)]">
            From free exploration to Institutional tier with 50K API calls/day. View plans and upgrade.
          </p>
        </a>
        <a href="/api/docs" target="_blank" className="flex-1 rounded-2xl bg-white/[0.03] border border-white/[0.06] p-5 hover:bg-white/[0.05] transition-colors group">
          <div className="flex items-center gap-2 mb-1">
            <BookOpen className="w-4 h-4 text-ocean-400" />
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">Interactive Docs</h3>
          </div>
          <p className="text-[11px] text-[var(--text-secondary)]">
            Try endpoints directly in the browser with Swagger UI. Full request/response schemas.
          </p>
        </a>
      </motion.div>

      <div className="pb-8" />
    </div>
  );
}
