"use client";
import { useState } from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import {
  Fish, BarChart3, Shield, TrendingUp, Globe2, Brain,
  Zap, Leaf, Ship, Trophy, Bug, Newspaper, ChevronRight, Check,
  Code2, Play, Quote, ArrowRight,
} from "lucide-react";
import { useTranslation } from "@/lib/i18n";
import ErrorBoundary from "@/components/ErrorBoundary";

const FEATURES = [
  { icon: Bug, title: "Lice Intelligence", desc: "Real-time lice data for 1,815 Norwegian farms with GNN spread prediction", color: "text-rose-400" },
  { icon: TrendingUp, title: "Price Prediction", desc: "Temporal Fusion Transformer with 7 quantile bands, 2-20 week horizons", color: "text-ocean-400" },
  { icon: BarChart3, title: "Production Costs", desc: "Live feed prices (FRED) + official Fiskeridirektoratet cost structure", color: "text-amber-400" },
  { icon: Leaf, title: "ESG Scoring", desc: "100 companies graded A+ to F on environmental, social, governance metrics", color: "text-emerald-400" },
  { icon: Globe2, title: "Global Supply", desc: "7-country supply balance model with disruption alerts", color: "text-violet-400" },
  { icon: Brain, title: "Causal Engine", desc: "12-week lice-to-price lag discovered via Transfer Entropy (z=3.26)", color: "text-cyan-400" },
  { icon: Ship, title: "AIS Vessel Tracking", desc: "418 vessels monitored — harvest and treatment signal detection", color: "text-blue-400" },
  { icon: Trophy, title: "Peer Benchmarking", desc: "Anonymous performance comparison across 100 producers", color: "text-yellow-400" },
  { icon: Newspaper, title: "Morning Brief", desc: "Daily market digest — price, lice, regime, bloom, macro in 60 seconds", color: "text-pink-400" },
];

const TIERS = [
  {
    name: "Free", price: "0", period: "",
    features: ["Dashboard overview", "Morning Brief", "Basic lice summary"],
    cta: "Get Started", highlight: false,
  },
  {
    name: "Professional", price: "2,500", period: "NOK/mo",
    features: ["Everything in Free", "Production Costs", "ESG Scores", "Bloom Monitoring", "Exposure Map", "Farm Advisory", "100+ company rankings"],
    cta: "Start Trial", highlight: false,
  },
  {
    name: "Market Intelligence", price: "5,000", period: "NOK/mo",
    features: ["Everything in Pro", "Trading Signals", "Market Terminal", "Price Predictions (TFT)", "Causal Engine", "Global Supply", "AIS Vessel Intel", "Peer Benchmarking"],
    cta: "Contact Sales", highlight: true,
  },
  {
    name: "Institutional", price: "15,000", period: "NOK/mo",
    features: ["Everything in Market", "Full API (50K calls/day)", "Custom datasets", "White-label reports", "Priority support"],
    cta: "Contact Sales", highlight: false,
  },
];

const TESTIMONIALS = [
  {
    quote: "FishIntel replaced three separate data subscriptions for our trading desk. The causal engine alone paid for itself in the first month.",
    author: "Head of Seafood Trading",
    org: "Nordic Investment Bank",
    color: "from-ocean-500/10 to-transparent",
  },
  {
    quote: "The daily decision cards save our site managers 30 minutes every morning. We went from spreadsheets to one-click treatment decisions.",
    author: "Operations Director",
    org: "Leading Norwegian Farmer",
    color: "from-emerald-500/10 to-transparent",
  },
  {
    quote: "We integrated the API into our risk models in under a day. The data provenance fields give our compliance team exactly what they need.",
    author: "Quantitative Analyst",
    org: "London Hedge Fund",
    color: "from-violet-500/10 to-transparent",
  },
];

const STATS = [
  { value: "229", label: "API Endpoints" },
  { value: "53", label: "Market Engines" },
  { value: "7", label: "Countries" },
  { value: "Real-time", label: "Data" },
];

export default function LandingPage() {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);

  return (
    <ErrorBoundary fallbackTitle="Landing error">
    <div className="min-h-screen bg-ocean-950">
      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-ocean-500/[0.05] to-transparent" />
        <div className="max-w-6xl mx-auto px-6 pt-20 pb-16 relative">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="text-center">
            <div className="flex items-center justify-center gap-3 mb-6">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-ocean-500 to-ocean-600 flex items-center justify-center shadow-[0_0_40px_rgba(0,212,200,0.3)]">
                <Fish className="w-7 h-7 text-white" />
              </div>
            </div>
            <h1 className="text-4xl sm:text-5xl md:text-6xl font-bold text-[var(--text-primary)] tracking-tight mb-4">
              FishIntel
            </h1>
            <p className="text-lg sm:text-xl md:text-2xl text-ocean-400 font-medium mb-2">
              Aquaculture Intelligence Platform
            </p>
            <p className="text-base sm:text-lg text-[var(--text-secondary)] max-w-2xl mx-auto mb-8 px-2">
              Real-time salmon market intelligence for farmers, buyers, traders, and investors.
              1,815 farms monitored. PhD-level cost models. TFT price prediction.
            </p>

            {/* CTA Buttons */}
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3 mb-6">
              <Link
                href="/welcome"
                className="px-8 py-3 bg-gradient-to-r from-ocean-500 to-ocean-600 text-white font-semibold rounded-xl text-sm shadow-[0_0_20px_rgba(0,212,200,0.2)] hover:shadow-[0_0_30px_rgba(0,212,200,0.3)] transition-all flex items-center gap-2"
              >
                <Play className="w-4 h-4" />
                Try Demo
              </Link>
              <Link
                href="/api-docs"
                className="px-8 py-3 bg-white/[0.06] text-[var(--text-primary)] font-semibold rounded-xl text-sm border border-white/[0.08] hover:bg-white/[0.1] transition-all flex items-center gap-2"
              >
                <Code2 className="w-4 h-4 text-ocean-400" />
                API Access
              </Link>
            </div>

            {/* Waitlist */}
            <div className="max-w-md mx-auto">
              {submitted ? (
                <motion.div initial={{ scale: 0.9 }} animate={{ scale: 1 }}
                  className="p-4 rounded-2xl bg-emerald-500/[0.08] border border-emerald-500/20 text-emerald-400">
                  <Check className="w-5 h-5 inline mr-2" />
                  You&apos;re on the list! We&apos;ll be in touch.
                </motion.div>
              ) : (
                <div className="flex gap-2">
                  <input
                    type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                    placeholder="your@email.com"
                    className="flex-1 px-4 py-3 bg-white/[0.04] border border-white/[0.08] rounded-xl text-sm text-[var(--text-primary)] placeholder:text-white/20 focus:outline-none focus:border-ocean-500/30"
                  />
                  <button
                    onClick={() => { if (email.includes("@")) setSubmitted(true); }}
                    className="px-6 py-3 bg-gradient-to-r from-ocean-500 to-ocean-600 text-white font-semibold rounded-xl text-sm shadow-[0_0_20px_rgba(0,212,200,0.2)] hover:shadow-[0_0_30px_rgba(0,212,200,0.3)] transition-all"
                  >
                    Join Waitlist
                  </button>
                </div>
              )}
            </div>

            {/* Live stats */}
            <div className="flex flex-wrap items-center justify-center gap-6 sm:gap-8 mt-12 text-sm">
              {[
                { label: "Farms monitored", value: "1,815" },
                { label: "API routes", value: "229" },
                { label: "FRED series", value: "12" },
                { label: "Satellites", value: "CMEMS" },
              ].map(s => (
                <div key={s.label} className="text-center">
                  <p className="text-lg font-bold text-ocean-400">{s.value}</p>
                  <p className="text-[11px] text-[var(--text-secondary)]">{s.label}</p>
                </div>
              ))}
            </div>
          </motion.div>
        </div>
      </section>

      {/* Stats Strip */}
      <section className="border-y border-white/[0.06] bg-white/[0.02]">
        <div className="max-w-6xl mx-auto px-6 py-5">
          <div className="flex flex-wrap items-center justify-center gap-3 sm:gap-4 text-center">
            {STATS.map((s, i) => (
              <div key={s.label} className="flex items-center gap-1.5">
                <span className="text-sm sm:text-base font-bold text-ocean-400">{s.value}</span>
                <span className="text-[11px] sm:text-xs text-[var(--text-secondary)]">{s.label}</span>
                {i < STATS.length - 1 && (
                  <span className="text-white/10 ml-2 sm:ml-3 hidden sm:inline">|</span>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features Grid */}
      <section className="max-w-6xl mx-auto px-6 py-16">
        <h2 className="text-xl sm:text-2xl font-bold text-center text-[var(--text-primary)] mb-12">
          Everything you need. Nothing your competitors have.
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
          {FEATURES.map((f, i) => (
            <motion.div
              key={f.title}
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 + i * 0.05 }}
              className="p-5 rounded-2xl bg-white/[0.03] border border-white/[0.06] hover:bg-white/[0.05] transition-colors"
            >
              <f.icon className={`w-6 h-6 ${f.color} mb-3`} />
              <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-1">{f.title}</h3>
              <p className="text-[12px] text-[var(--text-secondary)] leading-relaxed">{f.desc}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* API Access Section */}
      <section className="max-w-6xl mx-auto px-6 py-16">
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-2xl bg-gradient-to-br from-ocean-500/[0.06] to-violet-500/[0.04] border border-ocean-500/[0.12] p-6 sm:p-8 md:p-10"
        >
          <div className="flex flex-col md:flex-row md:items-center gap-6 md:gap-10">
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-10 h-10 rounded-xl bg-ocean-500/20 flex items-center justify-center">
                  <Code2 className="w-5 h-5 text-ocean-400" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-[var(--text-primary)]">Developer API</h2>
                  <span className="text-[11px] text-ocean-400 font-medium">v2.1.0 &mdash; OpenAPI 3.0</span>
                </div>
              </div>
              <p className="text-sm text-[var(--text-secondary)] leading-relaxed mb-4">
                Build on top of 229 REST endpoints covering lice intelligence, price prediction,
                disease monitoring, supply chain, and ML models. Every response includes data provenance
                so you always know the source, freshness, and confidence of the data.
              </p>
              <div className="flex flex-wrap gap-2 mb-4">
                {["JWT Auth", "Rate Limited", "Swagger UI", "ReDoc", "Data Provenance", "WebSocket"].map(tag => (
                  <span key={tag} className="px-2 py-0.5 rounded-md bg-white/[0.06] border border-white/[0.06] text-[10px] text-[var(--text-secondary)]">
                    {tag}
                  </span>
                ))}
              </div>
              <Link
                href="/api-docs"
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-ocean-500 hover:bg-ocean-600 text-white font-semibold rounded-xl text-sm transition-colors"
              >
                Explore API Docs <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
            <div className="md:w-[320px] flex-shrink-0">
              <pre className="text-[10px] text-[var(--text-secondary)] bg-black/40 rounded-xl p-4 font-mono leading-relaxed overflow-x-auto border border-white/[0.06]">
{`GET /api/lice/summary?pa=3
Authorization: Bearer eyJ...

{
  "pa": 3,
  "avg_adult_female": 0.12,
  "farms_above_limit": 4,
  "data_provenance": {
    "source": "BarentsWatch",
    "confidence": 0.95,
    "freshness": "live"
  }
}`}
              </pre>
            </div>
          </div>
        </motion.div>
      </section>

      {/* Testimonials */}
      <section className="max-w-6xl mx-auto px-6 py-16">
        <h2 className="text-xl sm:text-2xl font-bold text-center text-[var(--text-primary)] mb-3">
          Trusted by Industry Leaders
        </h2>
        <p className="text-sm text-[var(--text-secondary)] text-center mb-10">
          From trading desks to farm sites, FishIntel powers decisions across the value chain
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {TESTIMONIALS.map((t, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.15 + i * 0.08 }}
              className={`p-5 rounded-2xl bg-gradient-to-br ${t.color} border border-white/[0.06] flex flex-col`}
            >
              <Quote className="w-5 h-5 text-white/10 mb-3" />
              <p className="text-[12px] text-[var(--text-secondary)] leading-relaxed flex-1 italic">
                &ldquo;{t.quote}&rdquo;
              </p>
              <div className="mt-4 pt-3 border-t border-white/[0.06]">
                <p className="text-[11px] font-semibold text-[var(--text-primary)]">{t.author}</p>
                <p className="text-[10px] text-[var(--text-secondary)]">{t.org}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Pricing */}
      <section className="max-w-6xl mx-auto px-6 py-16">
        <h2 className="text-xl sm:text-2xl font-bold text-center text-[var(--text-primary)] mb-4">Pricing</h2>
        <p className="text-sm text-[var(--text-secondary)] text-center mb-12">
          From free exploration to institutional-grade intelligence
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
          {TIERS.map((t, i) => (
            <motion.div
              key={t.name}
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 + i * 0.08 }}
              className={`p-6 rounded-2xl border ${
                t.highlight
                  ? "bg-ocean-500/[0.06] border-ocean-500/20 shadow-[0_0_30px_rgba(0,212,200,0.1)]"
                  : "bg-white/[0.03] border-white/[0.06]"
              }`}
            >
              {t.highlight && (
                <span className="text-[9px] font-semibold text-ocean-400 uppercase tracking-wider">Most Popular</span>
              )}
              <h3 className="text-lg font-bold text-[var(--text-primary)] mt-1">{t.name}</h3>
              <div className="mt-2 mb-4">
                <span className="text-3xl font-bold text-[var(--text-primary)]">{t.price}</span>
                {t.period && <span className="text-sm text-[var(--text-secondary)]"> {t.period}</span>}
              </div>
              <div className="space-y-2 mb-6">
                {t.features.map(f => (
                  <div key={f} className="flex items-center gap-2 text-[11px] text-[var(--text-secondary)]">
                    <Check className="w-3 h-3 text-ocean-400 flex-shrink-0" />
                    {f}
                  </div>
                ))}
              </div>
              <button className={`w-full py-2.5 rounded-xl text-sm font-semibold transition-all ${
                t.highlight
                  ? "bg-ocean-500 text-white hover:bg-ocean-600"
                  : "bg-white/[0.06] text-[var(--text-primary)] hover:bg-white/[0.1]"
              }`}>
                {t.cta}
              </button>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/[0.06] py-8">
        <div className="max-w-6xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-lg bg-ocean-500/20 flex items-center justify-center">
              <Fish className="w-3.5 h-3.5 text-ocean-400" />
            </div>
            <span className="text-sm font-semibold text-[var(--text-secondary)]">FishIntel</span>
          </div>
          <div className="flex items-center gap-4 text-[10px] text-[var(--text-secondary)] opacity-50">
            <Link href="/api-docs" className="hover:text-ocean-400 transition-colors">API Docs</Link>
            <Link href="/billing" className="hover:text-ocean-400 transition-colors">Pricing</Link>
            <Link href="/welcome" className="hover:text-ocean-400 transition-colors">Demo</Link>
          </div>
          <p className="text-[10px] text-[var(--text-secondary)] opacity-50 text-center sm:text-right">
            Data: BarentsWatch (NLOD 2.0), SSB (CC BY 4.0), FRED, Copernicus CMEMS. Not financial advice.
          </p>
        </div>
      </footer>
    </div>
    </ErrorBoundary>
  );
}
