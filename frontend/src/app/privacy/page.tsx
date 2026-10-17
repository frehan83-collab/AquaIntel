"use client";
import { motion } from "framer-motion";
import { Shield, Database, Eye, Lock, Trash2, Brain, Mail, Cookie, Scale, Globe2 } from "lucide-react";
import GlassCard from "@/components/GlassCard";
import { useTranslation } from "@/lib/i18n";

const sections = [
  {
    icon: Globe2,
    title: "Who We Are",
    accent: "ocean" as const,
    content: (
      <>
        <p>FishIntel / AquaIntel is an aquaculture intelligence platform operated from Norway. We provide data-driven decision support for salmon farming professionals, traders, and analysts.</p>
        <p className="mt-2">Our mission is to aggregate public and licensed open data sources into actionable intelligence, while maintaining the highest standards of data privacy and transparency.</p>
      </>
    ),
  },
  {
    icon: Database,
    title: "Data We Collect",
    accent: "salmon" as const,
    content: (
      <div className="space-y-3">
        <div>
          <h4 className="text-sm font-semibold text-[var(--text-primary)] mb-1">Account Data</h4>
          <p>Email address, company name, role, and subscription tier. Collected at registration and used for authentication and service delivery.</p>
        </div>
        <div>
          <h4 className="text-sm font-semibold text-[var(--text-primary)] mb-1">Treatment Outcomes (Farmer-Contributed)</h4>
          <p>Voluntary treatment efficacy reports submitted via the Daily Check feature. These are aggregated and anonymized to production area (PA) level before inclusion in the Efficacy Marketplace.</p>
        </div>
        <div>
          <h4 className="text-sm font-semibold text-[var(--text-primary)] mb-1">Usage Analytics</h4>
          <p>Page views, feature usage frequency, and session duration. Used solely to improve platform functionality. No third-party analytics services are employed.</p>
        </div>
      </div>
    ),
  },
  {
    icon: Eye,
    title: "How We Use Data",
    accent: "emerald" as const,
    content: (
      <ul className="space-y-2 list-disc list-inside marker:text-emerald-400/60">
        <li><strong>Platform Operation</strong> — Authentication, subscription management, personalized dashboards, and locality persistence.</li>
        <li><strong>Aggregated Analytics</strong> — Treatment efficacy benchmarks, regional comparisons, and trend analysis. All aggregations are anonymized and require a minimum of 3 data points per cell.</li>
        <li><strong>Decision Support</strong> — AI-generated recommendations for treatment timing, harvest optimization, and risk assessment. These are advisory only and never the sole basis for operational decisions.</li>
      </ul>
    ),
  },
  {
    icon: Scale,
    title: "Data Sources & Licences",
    accent: "violet" as const,
    content: (
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-white/[0.08]">
              <th className="text-left py-2 pr-4 text-[var(--text-secondary)] font-medium">Source</th>
              <th className="text-left py-2 pr-4 text-[var(--text-secondary)] font-medium">Licence</th>
              <th className="text-left py-2 text-[var(--text-secondary)] font-medium">Data Type</th>
            </tr>
          </thead>
          <tbody className="text-[var(--text-secondary)]">
            {[
              ["BarentsWatch", "NLOD 2.0 (Norwegian Licence for Open Government Data)", "Sea lice counts, farm locations, production areas"],
              ["Statistics Norway (SSB)", "CC BY 4.0", "Salmon spot prices (Table 03024), production statistics"],
              ["Copernicus Marine Service", "CC BY (EU Open Data)", "Sea surface temperature, chlorophyll-a, ocean forecasts"],
              ["MET.no (Norwegian Meteorological Institute)", "CC BY 4.0", "Ocean forecasts, weather data, sea temperature history"],
              ["Fiskeridirektoratet", "NLOD", "Production volumes, MAB allocations, biomass data"],
              ["DFO Canada", "Open Government Licence (Canada)", "BC farm lice counts, mortality events, health audits"],
              ["Mattilsynet", "NLOD", "Disease cases (ISA/PD), lice treatments, resistance data"],
              ["WOAH (WAHIS)", "Public domain", "International disease outbreak notifications"],
              ["Sernapesca (Chile)", "Public data", "Chilean salmon production and disease status"],
              ["FRED (Federal Reserve)", "Public domain", "Commodity prices, exchange rates, macro indicators"],
            ].map(([source, licence, dataType], i) => (
              <tr key={i} className="border-b border-white/[0.04]">
                <td className="py-2.5 pr-4 font-medium text-[var(--text-primary)]">{source}</td>
                <td className="py-2.5 pr-4">
                  <span className="inline-block px-2 py-0.5 rounded-full text-xs bg-violet-500/10 text-violet-300 border border-violet-500/20">
                    {licence}
                  </span>
                </td>
                <td className="py-2.5">{dataType}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    ),
  },
  {
    icon: Lock,
    title: "Your Rights (GDPR Articles 15\u201320)",
    accent: "ocean" as const,
    content: (
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {[
          ["Right of Access (Art. 15)", "Request a copy of all personal data we hold about you."],
          ["Right to Rectification (Art. 16)", "Correct inaccurate or incomplete personal data."],
          ["Right to Erasure (Art. 17)", "Request deletion of your personal data. Account deletion removes all associated data within 30 days."],
          ["Right to Restriction (Art. 18)", "Request that we limit processing of your data while a dispute is resolved."],
          ["Right to Portability (Art. 20)", "Receive your data in a structured, machine-readable format (JSON/CSV)."],
          ["Right to Object (Art. 21)", "Object to processing based on legitimate interests, including profiling."],
        ].map(([right, desc], i) => (
          <div key={i} className="p-3 rounded-lg bg-white/[0.02] border border-white/[0.05]">
            <h4 className="text-sm font-semibold text-ocean-300 mb-1">{right}</h4>
            <p className="text-xs text-[var(--text-secondary)]">{desc}</p>
          </div>
        ))}
      </div>
    ),
  },
  {
    icon: Trash2,
    title: "Data Retention",
    accent: "amber" as const,
    content: (
      <div className="space-y-2">
        <div className="flex items-start gap-3">
          <div className="w-2 h-2 rounded-full bg-amber-400 mt-2 flex-shrink-0" />
          <div>
            <strong className="text-[var(--text-primary)]">Account data</strong>
            <span className="text-[var(--text-secondary)]"> — Retained until you request deletion. Deletion is processed within 30 days and is irreversible.</span>
          </div>
        </div>
        <div className="flex items-start gap-3">
          <div className="w-2 h-2 rounded-full bg-emerald-400 mt-2 flex-shrink-0" />
          <div>
            <strong className="text-[var(--text-primary)]">Aggregated analytics</strong>
            <span className="text-[var(--text-secondary)]"> — Retained indefinitely. This data is fully anonymized and cannot be traced back to individual users or farms.</span>
          </div>
        </div>
        <div className="flex items-start gap-3">
          <div className="w-2 h-2 rounded-full bg-ocean-400 mt-2 flex-shrink-0" />
          <div>
            <strong className="text-[var(--text-primary)]">Treatment outcomes</strong>
            <span className="text-[var(--text-secondary)]"> — Aggregated to PA level within 24 hours of submission. Raw submissions are purged after aggregation.</span>
          </div>
        </div>
      </div>
    ),
  },
  {
    icon: Shield,
    title: "Efficacy Marketplace Privacy",
    accent: "salmon" as const,
    content: (
      <div className="space-y-2">
        <p>The Treatment Efficacy Marketplace employs strict privacy safeguards to prevent identification of individual farms:</p>
        <ul className="space-y-1.5 list-disc list-inside marker:text-salmon/60">
          <li><strong>Minimum 3 data points per cell</strong> — No efficacy metric is displayed unless at least 3 independent reports contribute to that aggregation cell.</li>
          <li><strong>PA-level aggregation</strong> — All data is aggregated to Production Area level. Individual farm locations are never exposed.</li>
          <li><strong>No individual farm identification</strong> — Company names, farm names, and locality numbers are stripped before aggregation.</li>
          <li><strong>Temporal smoothing</strong> — Data is aggregated across seasonal windows to prevent re-identification through timing.</li>
        </ul>
      </div>
    ),
  },
  {
    icon: Brain,
    title: "AI Transparency (EU AI Act Compliance)",
    accent: "violet" as const,
    content: (
      <div className="space-y-2">
        <p>FishIntel uses machine learning models for predictions and recommendations. In accordance with the EU AI Act:</p>
        <ul className="space-y-1.5 list-disc list-inside marker:text-violet-400/60">
          <li>All AI-generated predictions are clearly labelled with confidence scores and data provenance.</li>
          <li>Predictions are <strong>advisory only</strong> and must never be the sole basis for operational decisions.</li>
          <li>Model types include rule-based price and decision engines, plus optional machine-learning tiers (gradient-boosted trees, a graph neural network, foundation-model forecasts) that run only when installed and are labelled when they do not.</li>
          <li>Data quality badges indicate whether outputs are derived from live data, degraded sources, or simulated fallbacks.</li>
          <li>Users can inspect the data sources and confidence level behind any recommendation via the Data Provenance system.</li>
        </ul>
      </div>
    ),
  },
  {
    icon: Mail,
    title: "Contact & Data Controller",
    accent: "ocean" as const,
    content: (
      <div className="space-y-3">
        <div>
          <h4 className="text-sm font-semibold text-[var(--text-primary)] mb-1">Data Controller</h4>
          <p>FishIntel / AquaIntel<br />Norway</p>
          <p className="mt-1">Email: <span className="text-ocean-300">privacy@fishintel.io</span></p>
        </div>
        <div>
          <h4 className="text-sm font-semibold text-[var(--text-primary)] mb-1">Supervisory Authority</h4>
          <p>If you are unsatisfied with our handling of your data, you have the right to lodge a complaint with the Norwegian Data Protection Authority (Datatilsynet).</p>
          <p className="mt-1 text-xs text-[var(--text-secondary)]">Datatilsynet &mdash; datatilsynet.no &mdash; Postboks 458 Sentrum, 0105 Oslo, Norway</p>
        </div>
      </div>
    ),
  },
  {
    icon: Cookie,
    title: "Cookies & Local Storage",
    accent: "amber" as const,
    content: (
      <div className="space-y-2">
        <p>FishIntel uses minimal client-side storage. We do not use third-party tracking cookies.</p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm mt-2">
            <thead>
              <tr className="border-b border-white/[0.08]">
                <th className="text-left py-2 pr-4 text-[var(--text-secondary)] font-medium">Item</th>
                <th className="text-left py-2 pr-4 text-[var(--text-secondary)] font-medium">Type</th>
                <th className="text-left py-2 text-[var(--text-secondary)] font-medium">Purpose</th>
              </tr>
            </thead>
            <tbody className="text-[var(--text-secondary)]">
              {[
                ["JWT Token", "localStorage", "Authentication session (expires per server config)"],
                ["Demo Mode", "localStorage", "Remembers demo persona selection (Farmer/Trader/Analyst)"],
                ["Locality Preference", "localStorage", "Persists selected farm/locality across sessions"],
                ["Sidebar State", "localStorage", "Collapsed/expanded sidebar preference"],
              ].map(([item, type, purpose], i) => (
                <tr key={i} className="border-b border-white/[0.04]">
                  <td className="py-2 pr-4 font-medium text-[var(--text-primary)]">{item}</td>
                  <td className="py-2 pr-4"><code className="text-xs px-1.5 py-0.5 rounded bg-white/[0.05]">{type}</code></td>
                  <td className="py-2">{purpose}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    ),
  },
];

export default function PrivacyPage() {
  const { t } = useTranslation();

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-2xl font-bold text-[var(--text-primary)] flex items-center gap-3">
          <Shield className="w-6 h-6 text-ocean-400" />
          {t("nav.privacy")}
        </h1>
        <p className="text-[var(--text-secondary)] mt-1">
          How FishIntel handles your data &mdash; GDPR compliant
        </p>
        <p className="text-xs text-[var(--text-secondary)] mt-2 opacity-60">
          Last updated: April 2026 &middot; Effective immediately
        </p>
      </motion.div>

      {/* Sections */}
      {sections.map((s, i) => (
        <GlassCard key={i} accent={s.accent} delay={i * 0.04}>
          <div className="flex items-center gap-3 mb-4">
            <div className="w-8 h-8 rounded-lg bg-white/[0.05] flex items-center justify-center flex-shrink-0">
              <s.icon className="w-4 h-4 text-[var(--text-secondary)]" />
            </div>
            <h2 className="text-lg font-semibold text-[var(--text-primary)]">{s.title}</h2>
          </div>
          <div className="text-sm text-[var(--text-secondary)] leading-relaxed">
            {s.content}
          </div>
        </GlassCard>
      ))}

      {/* Legal basis footer */}
      <GlassCard accent="none" tier="secondary" delay={0.4}>
        <p className="text-xs text-[var(--text-secondary)] text-center leading-relaxed">
          Processing is based on: (a) contractual necessity for platform operation (Art. 6(1)(b) GDPR),
          (b) legitimate interest for aggregated analytics (Art. 6(1)(f) GDPR),
          and (c) consent for voluntary treatment outcome submissions (Art. 6(1)(a) GDPR).
        </p>
      </GlassCard>
    </div>
  );
}
