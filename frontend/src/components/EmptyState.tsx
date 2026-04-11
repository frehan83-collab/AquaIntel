"use client";
import { useTranslation } from "@/lib/i18n";

type EmptyVariant = "no-data" | "no-alerts" | "no-signals" | "error" | "offline";

interface Props {
  title?: string;
  message?: string;
  icon?: React.ReactNode;
  variant?: EmptyVariant;
  action?: { label: string; onClick: () => void };
}

/* ── SVG Illustrations (~80px, ocean-themed, abstract) ──────────────────── */

function NoDataIllustration() {
  return (
    <svg width="80" height="80" viewBox="0 0 80 80" fill="none" aria-hidden="true">
      <path d="M10 38 Q25 32 40 38 Q55 44 70 38" stroke="var(--accent)" strokeWidth="2.5" strokeLinecap="round" fill="none" opacity="0.7" />
      <path d="M10 46 Q25 40 40 46 Q55 52 70 46" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" fill="none" opacity="0.5" />
      <path d="M10 54 Q25 48 40 54 Q55 60 70 54" stroke="var(--accent)" strokeWidth="1.5" strokeLinecap="round" fill="none" opacity="0.3" />
    </svg>
  );
}

function NoAlertsIllustration() {
  return (
    <svg width="80" height="80" viewBox="0 0 80 80" fill="none" aria-hidden="true">
      <path d="M40 16 L56 52 H24 Z" stroke="var(--positive)" strokeWidth="2" strokeLinejoin="round" fill="none" opacity="0.5" />
      <rect x="28" y="24" width="24" height="28" rx="4" stroke="var(--positive)" strokeWidth="2" fill="none" opacity="0.7" />
      <path d="M34 40 L38 44 L46 34" stroke="var(--positive)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" opacity="0.9" />
    </svg>
  );
}

function NoSignalsIllustration() {
  return (
    <svg width="80" height="80" viewBox="0 0 80 80" fill="none" aria-hidden="true">
      <line x1="10" y1="48" x2="70" y2="48" stroke="var(--text-secondary)" strokeWidth="1.5" strokeLinecap="round" opacity="0.4" />
      <circle cx="52" cy="48" r="3" fill="var(--accent)" opacity="0.6" />
      <circle cx="52" cy="48" r="7" stroke="var(--accent)" strokeWidth="1" fill="none" opacity="0.25" />
      <circle cx="52" cy="48" r="12" stroke="var(--accent)" strokeWidth="0.7" fill="none" opacity="0.12" />
    </svg>
  );
}

function ErrorIllustration() {
  return (
    <svg width="80" height="80" viewBox="0 0 80 80" fill="none" aria-hidden="true">
      <path d="M10 44 Q20 36 30 44 Q35 48 38 42" stroke="var(--danger)" strokeWidth="2.5" strokeLinecap="round" fill="none" opacity="0.7" />
      <path d="M42 50 L48 38 L54 46" stroke="var(--danger)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" fill="none" opacity="0.5" />
      <path d="M56 44 Q62 40 70 44" stroke="var(--danger)" strokeWidth="1.5" strokeLinecap="round" fill="none" opacity="0.35" />
    </svg>
  );
}

function OfflineIllustration() {
  return (
    <svg width="80" height="80" viewBox="0 0 80 80" fill="none" aria-hidden="true">
      <path d="M24 46 Q28 34 40 34 Q52 34 56 46" stroke="var(--text-secondary)" strokeWidth="2" strokeLinecap="round" fill="none" opacity="0.5" />
      <path d="M28 46 H52 Q54 46 54 48 V52 Q54 54 52 54 H28 Q26 54 26 52 V48 Q26 46 28 46 Z" stroke="var(--text-secondary)" strokeWidth="1.5" fill="none" opacity="0.4" />
      <line x1="33" y1="41" x2="47" y2="55" stroke="var(--text-secondary)" strokeWidth="2" strokeLinecap="round" opacity="0.6" />
      <line x1="47" y1="41" x2="33" y2="55" stroke="var(--text-secondary)" strokeWidth="2" strokeLinecap="round" opacity="0.6" />
    </svg>
  );
}

const VARIANT_ILLUSTRATIONS: Record<EmptyVariant, React.FC> = {
  "no-data": NoDataIllustration,
  "no-alerts": NoAlertsIllustration,
  "no-signals": NoSignalsIllustration,
  "error": ErrorIllustration,
  "offline": OfflineIllustration,
};

const VARIANT_DEFAULTS: Record<EmptyVariant, { titleKey: string; descKey: string; titleFallback: string; descFallback: string }> = {
  "no-data": {
    titleKey: "empty.title",
    descKey: "empty.message",
    titleFallback: "No data available",
    descFallback: "Data will appear here when available",
  },
  "no-alerts": {
    titleKey: "empty.no_alerts_title",
    descKey: "empty.no_alerts_message",
    titleFallback: "All Clear",
    descFallback: "No critical alerts at this time",
  },
  "no-signals": {
    titleKey: "empty.no_signals_title",
    descKey: "empty.no_signals_message",
    titleFallback: "No Active Signals",
    descFallback: "Signals will appear when market conditions change",
  },
  "error": {
    titleKey: "empty.error_title",
    descKey: "empty.error_message",
    titleFallback: "Something went wrong",
    descFallback: "We're working on it. Try refreshing.",
  },
  "offline": {
    titleKey: "empty.offline_title",
    descKey: "empty.offline_message",
    titleFallback: "You're offline",
    descFallback: "Check your connection and try again",
  },
};

export default function EmptyState({
  title,
  message,
  icon,
  variant = "no-data",
  action,
}: Props) {
  const { t } = useTranslation();
  const defaults = VARIANT_DEFAULTS[variant];
  const Illustration = VARIANT_ILLUSTRATIONS[variant];

  // User-provided title/message override defaults; translation keys tried first, then hardcoded fallbacks
  const resolvedTitle = title ?? (t(defaults.titleKey) !== defaults.titleKey ? t(defaults.titleKey) : defaults.titleFallback);
  const resolvedMessage = message ?? (t(defaults.descKey) !== defaults.descKey ? t(defaults.descKey) : defaults.descFallback);

  return (
    <div className="flex flex-col items-center justify-center py-16 opacity-60">
      {icon ? (
        <div className="w-12 h-12 rounded-2xl bg-white/[0.04] border border-white/[0.06] flex items-center justify-center mb-3">
          {icon}
        </div>
      ) : (
        <div className="mb-3">
          <Illustration />
        </div>
      )}
      <h3 className="text-sm font-medium text-[var(--text-primary)] mb-1">{resolvedTitle}</h3>
      <p className="text-xs text-[var(--text-secondary)] text-center max-w-xs">{resolvedMessage}</p>
      {action && (
        <button
          onClick={action.onClick}
          className="mt-4 px-4 py-1.5 text-xs font-medium rounded-lg bg-[var(--accent)]/10 border border-[var(--accent)]/20 text-[var(--accent)] hover:bg-[var(--accent)]/20 transition-colors"
        >
          {action.label}
        </button>
      )}
    </div>
  );
}
