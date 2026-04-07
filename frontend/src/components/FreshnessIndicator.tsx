"use client";

import { useTranslation } from "@/lib/i18n";

interface Props {
  lastUpdated: string | Date | null;
  className?: string;
}

function getAge(
  lastUpdated: string | Date | null,
  t: (key: string) => string
): { minutes: number; label: string; color: string; pulse: boolean } {
  if (!lastUpdated) {
    return { minutes: -1, label: t("status.unknown"), color: "gray", pulse: false };
  }

  const ts = typeof lastUpdated === "string" ? new Date(lastUpdated) : lastUpdated;
  if (isNaN(ts.getTime())) {
    return { minutes: -1, label: t("status.unknown"), color: "gray", pulse: false };
  }

  const diffMs = Date.now() - ts.getTime();
  const minutes = Math.max(0, Math.floor(diffMs / 60_000));

  if (minutes < 1) {
    return { minutes, label: t("time.just_now"), color: "green", pulse: true };
  }
  if (minutes < 5) {
    return { minutes, label: `${minutes}${t("time.minutes_ago")}`, color: "green", pulse: true };
  }
  if (minutes < 60) {
    return { minutes, label: `${minutes}${t("time.minutes_ago")}`, color: "emerald", pulse: false };
  }
  const hours = Math.floor(minutes / 60);
  if (hours < 6) {
    return { minutes, label: `${hours}${t("time.hours_ago")}`, color: "amber", pulse: false };
  }
  if (hours < 24) {
    return { minutes, label: `${hours}${t("time.hours_ago")}`, color: "rose", pulse: false };
  }
  const days = Math.floor(hours / 24);
  return { minutes, label: `${days}${t("time.days_ago")}`, color: "rose", pulse: false };
}

const COLOR_MAP: Record<string, { dot: string; text: string }> = {
  green:   { dot: "bg-emerald-400", text: "text-emerald-400" },
  emerald: { dot: "bg-emerald-500", text: "text-emerald-500/80" },
  amber:   { dot: "bg-amber-400",   text: "text-amber-400/80" },
  rose:    { dot: "bg-rose-400",     text: "text-rose-400/80" },
  gray:    { dot: "bg-gray-500",     text: "text-gray-400/60" },
};

export default function FreshnessIndicator({ lastUpdated, className }: Props) {
  const { t } = useTranslation();
  const { label, color, pulse } = getAge(lastUpdated, t);
  const colors = COLOR_MAP[color] || COLOR_MAP.gray;

  return (
    <span className={`inline-flex items-center gap-1.5 ${className ?? ""}`}>
      <span
        className={`w-1.5 h-1.5 rounded-full ${colors.dot} ${pulse ? "animate-pulse shadow-[0_0_6px_rgba(52,211,153,0.5)]" : ""}`}
      />
      <span className={`text-[10px] font-medium ${colors.text}`}>
        {label}
      </span>
    </span>
  );
}
