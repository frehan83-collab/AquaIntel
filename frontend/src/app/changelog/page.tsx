"use client";
import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  Sparkles, Zap, Wrench, Tag, Calendar, ChevronDown, ChevronUp,
} from "lucide-react";
import GlassCard from "@/components/GlassCard";
import { useTranslation, formatDate } from "@/lib/i18n";
import { useApiError } from "@/lib/useApiError";

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const LATEST_VERSION = "2.5.0";
const LS_KEY = "fishintel_last_viewed_changelog";

type ChangeType = "new" | "enhanced" | "fixed";

type Change = {
  type: ChangeType;
  text: string;
};

type Release = {
  version: string;
  date: string;
  title: string;
  changes: Change[];
};

const RELEASES: Release[] = [
  {
    version: "2.5.0",
    date: "2026-04-04",
    title: "Integrations & Developer",
    changes: [
      { type: "new", text: "Webhook alerts (Slack, Teams, generic)" },
      { type: "new", text: "API key management with rotation" },
      { type: "new", text: "Farm Portfolio multi-farm overview" },
      { type: "new", text: "Company comparison with radar chart" },
      { type: "new", text: "Treatment cost comparison calculator" },
      { type: "enhanced", text: "API caching with ETag + 304 support" },
    ],
  },
  {
    version: "2.4.0",
    date: "2026-04-04",
    title: "Quality & Real-Time",
    changes: [
      { type: "new", text: "WebSocket Command Centre with LIVE streaming" },
      { type: "new", text: "Dark/Light theme toggle" },
      { type: "new", text: "Notification Center with filters" },
      { type: "new", text: "Admin dashboard for data quality monitoring" },
      { type: "new", text: "Supply Chain Sankey diagram" },
      { type: "new", text: "Regional Heatmap (PA-level)" },
      { type: "enhanced", text: "WCAG accessibility audit (ARIA, skip-to-content)" },
      { type: "enhanced", text: "Excel export from DataTable" },
    ],
  },
  {
    version: "2.3.0",
    date: "2026-04-04",
    title: "Production Polish",
    changes: [
      { type: "new", text: "Bio Risk Map time slider (8-week snapshots)" },
      { type: "new", text: "Efficacy Marketplace (production-ready)" },
      { type: "new", text: "Decision Engine feedback loop" },
      { type: "enhanced", text: "Satellite intelligence (SST, chlorophyll, clusters)" },
      { type: "enhanced", text: "InteractiveChart on 7 pages" },
      { type: "enhanced", text: "ErrorBoundary on 19 pages" },
      { type: "fixed", text: "pandas deprecation warnings" },
    ],
  },
  {
    version: "2.2.0",
    date: "2026-04-03",
    title: "Full Async + DevEx",
    changes: [
      { type: "new", text: "WebSocket /ws/alerts streaming" },
      { type: "new", text: "API Developer Portal" },
      { type: "enhanced", text: "63 async DB refs across platform" },
      { type: "enhanced", text: "Landing page polish" },
    ],
  },
  {
    version: "2.1.0",
    date: "2026-04-03",
    title: "Scale & Mobile",
    changes: [
      { type: "new", text: "Mobile responsive sidebar" },
      { type: "new", text: "Error boundaries + loading states" },
      { type: "new", text: "Notification/alert system" },
      { type: "new", text: "Pydantic v2 response schemas" },
      { type: "enhanced", text: "130 tests (was 69)" },
    ],
  },
  {
    version: "2.0.0",
    date: "2026-04-03",
    title: "Architecture Overhaul",
    changes: [
      { type: "new", text: "18 router modules (api.py -70%)" },
      { type: "new", text: "Unified Scenario Sandbox" },
      { type: "new", text: "Async DB foundation" },
      { type: "new", text: "100+ endpoints with DataProvenance" },
    ],
  },
];

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

const TYPE_CONFIG: Record<ChangeType, { label: string; bg: string; text: string; icon: typeof Sparkles }> = {
  new:      { label: "New",      bg: "bg-emerald-500/10 dark:bg-emerald-500/15", text: "text-emerald-600 dark:text-emerald-400", icon: Sparkles },
  enhanced: { label: "Enhanced", bg: "bg-sky-500/10 dark:bg-sky-500/15",         text: "text-sky-600 dark:text-sky-400",         icon: Zap },
  fixed:    { label: "Fixed",    bg: "bg-amber-500/10 dark:bg-amber-500/15",     text: "text-amber-600 dark:text-amber-400",     icon: Wrench },
};

function formatReleaseDate(iso: string, locale: Parameters<typeof formatDate>[1]) {
  return formatDate(iso + "T00:00:00", locale);
}

/* ------------------------------------------------------------------ */
/*  Components                                                         */
/* ------------------------------------------------------------------ */

function ChangeBadge({ type }: { type: ChangeType }) {
  const cfg = TYPE_CONFIG[type];
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold uppercase tracking-wide ${cfg.bg} ${cfg.text}`}>
      <cfg.icon className="w-3 h-3" />
      {cfg.label}
    </span>
  );
}

function ReleaseCard({ release, isLatest, index }: { release: Release; isLatest: boolean; index: number }) {
  const { locale } = useTranslation();
  const [expanded, setExpanded] = useState(isLatest);

  const grouped: Record<ChangeType, Change[]> = { new: [], enhanced: [], fixed: [] };
  for (const c of release.changes) {
    grouped[c.type].push(c);
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.08, duration: 0.4 }}
      className="relative pl-8"
    >
      {/* Timeline dot */}
      <div className="absolute left-0 top-6 w-4 h-4 rounded-full border-[3px] border-white dark:border-fjord-abyss bg-salmon shadow-[0_0_0_3px_rgba(232,115,74,0.2)]" />

      <GlassCard>
        {/* Header */}
        <button
          onClick={() => setExpanded(!expanded)}
          className="w-full flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 text-left"
        >
          <div className="flex items-center gap-3 flex-1 min-w-0">
            {/* Version badge */}
            <span className="flex-shrink-0 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-salmon/10 text-salmon font-mono text-sm font-bold">
              <Tag className="w-3.5 h-3.5" />
              v{release.version}
            </span>

            {isLatest && (
              <span className="flex-shrink-0 inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-500 text-[10px] font-bold uppercase tracking-wider animate-pulse">
                <Sparkles className="w-3 h-3" />
                Latest
              </span>
            )}

            <h3 className="text-base font-display text-[var(--text-primary)] truncate">
              {release.title}
            </h3>
          </div>

          <div className="flex items-center gap-3 text-xs text-[var(--text-secondary)]">
            <span className="inline-flex items-center gap-1">
              <Calendar className="w-3.5 h-3.5" />
              {formatReleaseDate(release.date, locale)}
            </span>
            <span className="text-[var(--text-secondary)]/80">
              {release.changes.length} changes
            </span>
            {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </div>
        </button>

        {/* Change list */}
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            transition={{ duration: 0.25 }}
            className="mt-4 pt-4 border-t border-slate-200/60 dark:border-white/[0.06] space-y-4"
          >
            {(["new", "enhanced", "fixed"] as ChangeType[]).map((type) => {
              const items = grouped[type];
              if (items.length === 0) return null;
              return (
                <div key={type}>
                  <div className="mb-2">
                    <ChangeBadge type={type} />
                  </div>
                  <ul className="space-y-1.5 ml-1">
                    {items.map((c, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-[var(--text-secondary)]">
                        <span className={`mt-1.5 w-1.5 h-1.5 rounded-full flex-shrink-0 ${TYPE_CONFIG[type].bg} ${TYPE_CONFIG[type].text}`} />
                        {c.text}
                      </li>
                    ))}
                  </ul>
                </div>
              );
            })}
          </motion.div>
        )}
      </GlassCard>
    </motion.div>
  );
}

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function ChangelogPage() {
  const { t } = useTranslation();
  const handleError = useApiError();

  // Mark as viewed on mount
  useEffect(() => {
    try {
      localStorage.setItem(LS_KEY, LATEST_VERSION);
    } catch (e) { handleError("changelog_local_storage")(e); }
  }, []);

  // Stats
  const totalNew = RELEASES.reduce((s, r) => s + r.changes.filter((c) => c.type === "new").length, 0);
  const totalEnhanced = RELEASES.reduce((s, r) => s + r.changes.filter((c) => c.type === "enhanced").length, 0);
  const totalFixed = RELEASES.reduce((s, r) => s + r.changes.filter((c) => c.type === "fixed").length, 0);

  return (
    <main className="min-h-screen p-4 md:p-8 max-w-4xl mx-auto">
      {/* Skip-to-content target */}
      <a id="main-content" tabIndex={-1} className="sr-only">Changelog</a>

      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -16 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-8"
      >
        <h1 className="text-3xl md:text-4xl font-display text-[var(--text-primary)] tracking-tight">
          {t("page.changelog.title")}
        </h1>
        <p className="mt-2 text-[var(--text-secondary)] text-sm leading-relaxed max-w-2xl">
          Platform releases and updates. Every improvement to FishIntel is documented here so you
          always know what&apos;s new.
        </p>

        {/* Summary strip */}
        <div className="mt-4 flex flex-wrap gap-3">
          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 text-xs font-semibold">
            <Sparkles className="w-3.5 h-3.5" />
            {totalNew} new features
          </span>
          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-500/10 text-sky-600 dark:text-sky-400 text-xs font-semibold">
            <Zap className="w-3.5 h-3.5" />
            {totalEnhanced} enhancements
          </span>
          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400 text-xs font-semibold">
            <Wrench className="w-3.5 h-3.5" />
            {totalFixed} fixes
          </span>
          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-500/10 text-[var(--text-secondary)] text-xs font-semibold">
            {RELEASES.length} releases
          </span>
        </div>
      </motion.div>

      {/* Timeline */}
      <div className="relative">
        {/* Vertical line */}
        <div className="absolute left-[7px] top-6 bottom-6 w-[2px] bg-gradient-to-b from-salmon/40 via-salmon/20 to-transparent" />

        <div className="space-y-6">
          {RELEASES.map((release, i) => (
            <ReleaseCard
              key={release.version}
              release={release}
              isLatest={i === 0}
              index={i}
            />
          ))}
        </div>
      </div>

      {/* Footer */}
      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.6 }}
        className="mt-12 text-center text-xs text-[var(--text-secondary)]/70"
      >
        FishIntel Aquaculture Intelligence Platform &mdash; Built in Norway
      </motion.p>
    </main>
  );
}
