"use client";
/**
 * Public landing page.
 *
 * Honesty rules (WS-20, docs/VALUE_ANALYSIS.md section 3; guarded by
 * tests/test_public_claims.py): no testimonials until a real customer agrees to
 * be quoted, no typed counts that go stale, no capability the platform does not
 * serve today, and every price read from /api/billing/catalog.
 */
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import {
  Fish, BarChart3, Shield, TrendingUp, Bug, FileCheck,
  Code2, Play, ArrowRight, Scale,
} from "lucide-react";
import { api } from "@/lib/api";
import { formatNumber, useTranslation } from "@/lib/i18n";
import { useApiError } from "@/lib/useApiError";
import type { BillingCatalog } from "@/types/api";

const FEATURES = [
  { icon: Bug, title: "Lice by farm", desc: "Weekly adult female lice counts per farm from BarentsWatch, with the reporting week and source on every figure", color: "text-rose-400" },
  { icon: TrendingUp, title: "Price outlook", desc: "2-20 week outlook from SSB weekly export prices; the naive baseline it has to beat is published in the accuracy registry", color: "text-ocean-400" },
  { icon: BarChart3, title: "Production costs", desc: "Feed-ingredient prices from FRED applied to Fiskeridirektoratet's official cost structure", color: "text-amber-400" },
  { icon: Shield, title: "Disease cases", desc: "ISA and PD cases from Mattilsynet, by farm and company", color: "text-violet-400" },
  { icon: Scale, title: "Open method", desc: "Published index methods and a walk-forward accuracy registry that labels fallbacks as fallbacks", color: "text-emerald-400" },
  { icon: FileCheck, title: "Provenance", desc: "Market and index outputs state their source, whether they are live and a confidence, and say why when they fall back", color: "text-cyan-400" },
];

export default function LandingPage() {
  const { locale } = useTranslation();
  const handleError = useApiError();
  const [catalog, setCatalog] = useState<BillingCatalog | null>(null);
  const [catalogState, setCatalogState] = useState<"loading" | "ready" | "failed">("loading");

  useEffect(() => {
    api.billingCatalog()
      .then((c) => { setCatalog(c); setCatalogState("ready"); })
      .catch((e) => { setCatalogState("failed"); handleError("billing_catalog")(e); });
  }, [handleError]);

  return (
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
              Weekly salmon market and biology intelligence for farmers, buyers, traders and
              investors, built on public Norwegian data with an open method and a public
              accuracy registry.
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

            {/* How to check us */}
            <div className="flex flex-wrap items-center justify-center gap-6 sm:gap-8 mt-10 text-sm">
              {[
                { href: "/accuracy", label: "Accuracy & method" },
                { href: "/indices", label: "Published indices" },
                { href: "/privacy", label: "Data sources & licences" },
                { href: "/pricing", label: "Plans" },
              ].map(l => (
                <Link key={l.href} href={l.href} className="text-ocean-400 hover:text-ocean-300 transition-colors">
                  {l.label}
                </Link>
              ))}
            </div>
          </motion.div>
        </div>
      </section>

      {/* Features Grid */}
      <section className="max-w-6xl mx-auto px-6 py-16">
        <h2 className="text-xl sm:text-2xl font-bold text-center text-[var(--text-primary)] mb-12">
          What the platform covers
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
                  <span className="text-[11px] text-ocean-400 font-medium">OpenAPI 3</span>
                </div>
              </div>
              <p className="text-sm text-[var(--text-secondary)] leading-relaxed mb-4">
                REST endpoints for lice, prices, disease, supply and model outputs. Market and
                index responses carry a data_provenance block with the source, the time the
                answer was computed, a confidence score and, when a fallback was used, the
                reason.
              </p>
              <div className="flex flex-wrap gap-2 mb-4">
                {["JWT Auth", "Rate Limited", "Swagger UI", "ReDoc", "Data Provenance"].map(tag => (
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
{`GET /api/lice/summary

{
  "year": 2026,
  "week": 15,
  "avg_adult_female_lice": 0.09,
  "records": 34,
  "data_provenance": {
    "source": "BarentsWatch Fishhealth API",
    "is_live": false,
    "confidence": 0.4,
    "fallback_reason": "27 weeks stale"
  }
}`}
              </pre>
            </div>
          </div>
        </motion.div>
      </section>

      {/* Pricing: from the canonical plan catalog, never typed here */}
      <section className="max-w-6xl mx-auto px-6 py-16">
        <h2 className="text-xl sm:text-2xl font-bold text-center text-[var(--text-primary)] mb-4">Plans</h2>
        <p className="text-sm text-[var(--text-secondary)] text-center mb-12">
          Prices come from the live plan catalog.{" "}
          <Link href="/pricing" className="text-ocean-400 hover:text-ocean-300">Compare plans in full</Link>
        </p>
        {catalogState === "loading" && (
          <p className="text-sm text-[var(--text-secondary)] text-center">Loading plans…</p>
        )}
        {catalogState === "failed" && (
          <p className="text-sm text-[var(--text-secondary)] text-center">
            Plans are unavailable right now.{" "}
            <Link href="/pricing" className="text-ocean-400 hover:text-ocean-300">See the pricing page</Link>
          </p>
        )}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
          {(catalog?.plans ?? []).map((plan, i) => (
            <motion.div
              key={plan.plan}
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 + i * 0.05 }}
              className="p-6 rounded-2xl border bg-white/[0.03] border-white/[0.06]"
            >
              <h3 className="text-lg font-bold text-[var(--text-primary)]">{plan.name}</h3>
              <div className="mt-2 mb-2">
                <span className="text-2xl font-bold text-[var(--text-primary)]">
                  {plan.amount_nok === 0 ? "Free" : `NOK ${formatNumber(plan.amount_nok, locale, 0)}`}
                </span>
                {plan.amount_nok > 0 && <span className="text-sm text-[var(--text-secondary)]"> /mo</span>}
              </div>
              <p className="text-[11px] text-[var(--text-secondary)]">{plan.audience}</p>
            </motion.div>
          ))}
        </div>
        {catalog?.licensed_tier && (
          <p className="text-[11px] text-[var(--text-secondary)] text-center mt-6">
            {catalog.licensed_tier.name}: {catalog.licensed_tier.audience}. {catalog.licensed_tier.note}
          </p>
        )}
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
            <Link href="/pricing" className="hover:text-ocean-400 transition-colors">Pricing</Link>
            <Link href="/accuracy" className="hover:text-ocean-400 transition-colors">Accuracy</Link>
            <Link href="/welcome" className="hover:text-ocean-400 transition-colors">Demo</Link>
          </div>
          <p className="text-[10px] text-[var(--text-secondary)] opacity-50 text-center sm:text-right">
            Data: BarentsWatch (NLOD 2.0), SSB (CC BY 4.0), FRED, Copernicus CMEMS. Not financial advice.
          </p>
        </div>
      </footer>
    </div>
  );
}
