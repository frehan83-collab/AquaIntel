"use client";
import { useEffect, useState, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Bell, MessageSquare, User, TrendingUp, CheckCheck, AlertTriangle, ShieldAlert, Activity, BarChart3, Bug, Waves, Sun, Moon } from "lucide-react";
import { useTheme } from "@/lib/useTheme";
import { useTranslation } from "@/lib/i18n";
import { OcButton } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { useApiError } from "@/lib/useApiError";

/* eslint-disable @typescript-eslint/no-explicit-any */

const SEVERITY_COLORS: Record<string, string> = {
  critical: "bg-[var(--danger)]",
  high: "bg-[var(--warning)]",
  medium: "bg-yellow-500",
  low: "bg-[var(--accent)]",
  info: "bg-slate-500",
};

const SEVERITY_TEXT: Record<string, string> = {
  critical: "text-[var(--danger)]",
  high: "text-[var(--warning)]",
  medium: "text-yellow-400",
  low: "text-[var(--accent)]",
  info: "text-[var(--text-secondary)]",
};

const CATEGORY_ICONS: Record<string, any> = {
  lice: Bug,
  disease: ShieldAlert,
  price: BarChart3,
  regime: AlertTriangle,
  supply: Waves,
  feed_cost: Activity,
  anomaly: Activity,
};

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export default function TopBar() {
  const router = useRouter();
  const handleError = useApiError();
  const [pendingSignals, setPendingSignals] = useState<number>(0);
  const [spotPrice, setSpotPrice] = useState<number | null>(null);

  // Alert notification state
  const [alertSummary, setAlertSummary] = useState<any>(null);
  const [recentAlerts, setRecentAlerts] = useState<any[]>([]);
  const [bellOpen, setBellOpen] = useState(false);
  const bellRef = useRef<HTMLDivElement>(null);

  // Threshold alert state
  const [thresholdAlerts, setThresholdAlerts] = useState<any>(null);

  // Theme toggle
  const { theme, toggleTheme } = useTheme();

  // Language toggle
  const { t, locale, setLocale } = useTranslation();

  const fetchAlertSummary = useCallback(() => {
    api.alertsSummary().then((data: any) => {
      setAlertSummary(data);
    }).catch(handleError("topbar_alerts_summary"));
  }, []);

  const fetchRecentAlerts = useCallback(() => {
    api.alerts(undefined, undefined, false, 5).then((data: any) => {
      setRecentAlerts(Array.isArray(data) ? data : []);
    }).catch(handleError("topbar_recent_alerts"));
  }, []);

  const fetchThresholdAlerts = useCallback(() => {
    api.activeAlerts().then((data: any) => {
      setThresholdAlerts(data);
    }).catch(handleError("topbar_threshold_alerts"));
  }, []);

  useEffect(() => {
    // Load pending signals count
    api.signals().then((data: any) => {
      const arr = Array.isArray(data) ? data : data?.signals || [];
      setPendingSignals(arr.filter((s: any) => s.status === "pending").length);
    }).catch(handleError("topbar_signals"));

    // Load SSB spot price
    api.ssbPriceHistory(4).then((data: any) => {
      const spot = data?.spot_nok ?? data?.history?.[data?.history?.length - 1]?.price_nok_kg;
      if (spot) setSpotPrice(parseFloat(spot));
    }).catch(handleError("topbar_spot_price"));

    // Initial alert check + summary
    api.alertsCheck().catch(handleError("topbar_alerts_check"));
    fetchAlertSummary();
    fetchThresholdAlerts();

    // Poll alert summary + threshold alerts every 60 seconds
    const interval = setInterval(() => {
      fetchAlertSummary();
      fetchThresholdAlerts();
    }, 60_000);

    return () => clearInterval(interval);
  }, [fetchAlertSummary, fetchThresholdAlerts]);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (bellRef.current && !bellRef.current.contains(e.target as Node)) {
        setBellOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleBellClick = () => {
    if (!bellOpen) {
      fetchRecentAlerts();
      fetchAlertSummary();
      fetchThresholdAlerts();
    }
    setBellOpen(!bellOpen);
  };

  const handleMarkAllRead = () => {
    api.alertsMarkAllRead().then(() => {
      fetchAlertSummary();
      fetchRecentAlerts();
    }).catch(handleError("topbar_mark_all_read"));
  };

  const handleMarkRead = (id: string) => {
    api.alertMarkRead(id).then(() => {
      fetchAlertSummary();
      setRecentAlerts((prev) => prev.map((a) => a.id === id ? { ...a, read: true } : a));
    }).catch(handleError("topbar_mark_read"));
  };

  const thresholdCount = thresholdAlerts?.count || 0;
  const unreadCount = (alertSummary?.unread_count || 0) + thresholdCount;
  const maxSeverity = alertSummary?.max_severity || "info";

  // Dot color for bell badge
  const dotColor = maxSeverity === "critical" ? "bg-[var(--danger)] shadow-[0_0_8px_rgba(244,63,94,0.6)]"
    : maxSeverity === "high" ? "bg-[var(--warning)] shadow-[0_0_8px_rgba(245,158,11,0.5)]"
    : "bg-[var(--accent)] shadow-[0_0_8px_rgba(0,212,200,0.4)]";

  return (
    <header className="h-12 bg-white/80 dark:bg-fjord-midwater/80 backdrop-blur-xl border-b border-slate-200 dark:border-white/[0.05] flex items-center justify-between px-6 sticky top-0 z-30">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5">
          <div className="w-1.5 h-1.5 rounded-full bg-[var(--success)] animate-pulse" />
          <span className="text-[10px] font-semibold text-[var(--success)]/80 uppercase tracking-wider">{t("status.live")}</span>
        </div>
        {spotPrice !== null && (
          <div
            className="flex items-center gap-1.5 cursor-pointer hover:opacity-80 transition-opacity"
            onClick={() => router.push("/price-outlook")}
            title="Go to Price Outlook"
            role="link"
            tabIndex={0}
            aria-label={`Spot price ${spotPrice?.toFixed(1)} NOK per kg - Go to Price Outlook`}
            onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") router.push("/price-outlook"); }}
          >
            <span className="text-[13px] font-data font-semibold text-[var(--text-primary)]">
              {spotPrice.toFixed(1)}
            </span>
            <span className="text-[10px] text-[var(--text-secondary)]">NOK/kg</span>
          </div>
        )}
      </div>

      <div className="flex items-center gap-3">
        {/* Role Switcher */}
        <select
          className="bg-slate-100 dark:bg-white/[0.04] backdrop-blur border border-slate-200 dark:border-white/[0.08] rounded-xl px-3 py-1.5 text-xs text-[var(--text-primary)] focus:outline-none focus:border-ocean-500/30 transition-colors appearance-none cursor-pointer"
          aria-label={t("topbar.select_role")}
        >
          <option>{t("topbar.farmer")}</option>
          <option>{t("topbar.buyer")}</option>
          <option>{t("topbar.investor")}</option>
          <option>{t("topbar.admin")}</option>
        </select>

        {/* Language Toggle */}
        <button
          onClick={() => setLocale(locale === "en" ? "no" : "en")}
          className="px-2 py-1 rounded-lg text-[11px] font-bold tracking-wide text-slate-500 dark:text-[var(--text-secondary)] hover:text-slate-700 dark:hover:text-[var(--text-primary)] hover:bg-slate-100 dark:hover:bg-white/[0.06] border border-slate-200 dark:border-white/[0.08] transition-colors"
          aria-label={locale === "en" ? "Switch to Norwegian" : "Bytt til engelsk"}
          title={locale === "en" ? "Switch to Norwegian" : "Bytt til engelsk"}
        >
          {locale === "en" ? "NO" : "EN"}
        </button>

        {/* Theme Toggle */}
        <button
          onClick={toggleTheme}
          className="p-1.5 rounded-lg text-slate-500 dark:text-[var(--text-secondary)] hover:text-slate-700 dark:hover:text-[var(--text-primary)] hover:bg-slate-100 dark:hover:bg-white/[0.06] transition-colors"
          aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        >
          {theme === "dark" ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
        </button>

        {/* Alert Notification Bell */}
        <div className="relative" ref={bellRef}>
          <OcButton
            variant="icon"
            size="icon_md"
            aria-label="View alerts"
            onClick={handleBellClick}
          >
            <div className="relative">
              <Bell className="w-4 h-4" />
              {unreadCount > 0 ? (
                <span className="absolute -top-2 -right-2.5 min-w-[16px] h-4 rounded-full bg-[var(--danger)] flex items-center justify-center shadow-[0_0_8px_rgba(244,63,94,0.4)] px-0.5">
                  <span className="text-[8px] font-bold text-white leading-none">
                    {unreadCount > 99 ? "99+" : unreadCount}
                  </span>
                </span>
              ) : maxSeverity !== "info" && (
                <span className={`absolute -top-1 -right-1 w-2 h-2 rounded-full ${dotColor}`} />
              )}
            </div>
          </OcButton>

          {/* Alert Dropdown */}
          {bellOpen && (
            <div role="region" aria-label="Alert notifications" aria-live="polite" className="absolute right-0 top-12 w-[380px] max-h-[480px] overflow-hidden rounded-2xl border border-slate-200 dark:border-white/[0.08] bg-white/95 dark:bg-ocean-950/95 backdrop-blur-2xl shadow-[0_16px_48px_rgba(0,0,0,0.12)] dark:shadow-[0_16px_48px_rgba(0,0,0,0.5)] z-50">
              {/* Header */}
              <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06]">
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-semibold text-[var(--text-primary)]">{t("alerts.title")}</h3>
                  {unreadCount > 0 && (
                    <span className="text-[10px] font-bold text-rose-400 bg-rose-500/[0.12] px-1.5 py-0.5 rounded-full">
                      {unreadCount} {t("alerts.new")}
                    </span>
                  )}
                </div>
                {unreadCount > 0 && (
                  <button
                    onClick={handleMarkAllRead}
                    className="flex items-center gap-1 text-[11px] text-ocean-400 hover:text-ocean-300 transition-colors"
                  >
                    <CheckCheck className="w-3 h-3" />
                    {t("btn.mark_all_read")}
                  </button>
                )}
              </div>

              {/* Alert List */}
              <div className="overflow-y-auto max-h-[360px]">
                {recentAlerts.length === 0 ? (
                  <div className="px-4 py-8 text-center">
                    <Bell className="w-8 h-8 text-white/[0.15] mx-auto mb-2" />
                    <p className="text-xs text-[var(--text-secondary)]">{t("alerts.no_alerts")}</p>
                    <p className="text-[10px] text-[var(--text-secondary)] mt-1 opacity-60">
                      Alerts will appear when anomalies, price moves, or regime changes are detected
                    </p>
                  </div>
                ) : (
                  recentAlerts.map((alert) => {
                    const Icon = CATEGORY_ICONS[alert.category] || Activity;
                    return (
                      <button
                        key={alert.id}
                        onClick={() => handleMarkRead(alert.id)}
                        className={`w-full text-left px-4 py-3 border-b border-white/[0.04] hover:bg-white/[0.03] transition-colors ${
                          !alert.read ? "bg-white/[0.02]" : "opacity-60"
                        }`}
                      >
                        <div className="flex items-start gap-3">
                          <div className={`mt-0.5 p-1.5 rounded-lg ${SEVERITY_COLORS[alert.severity]}/[0.12]`}>
                            <Icon className={`w-3.5 h-3.5 ${SEVERITY_TEXT[alert.severity]}`} />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${SEVERITY_COLORS[alert.severity]}`} />
                              <span className="text-xs font-semibold text-[var(--text-primary)] truncate">
                                {alert.title}
                              </span>
                            </div>
                            <p className="text-[11px] text-[var(--text-secondary)] mt-0.5 line-clamp-2">
                              {alert.message}
                            </p>
                            <div className="flex items-center gap-2 mt-1">
                              <span className="text-[10px] text-[var(--text-secondary)] opacity-50">
                                {alert.created_at ? timeAgo(alert.created_at) : ""}
                              </span>
                              <span className="text-[10px] text-[var(--text-secondary)] opacity-40 uppercase">
                                {alert.category}
                              </span>
                            </div>
                          </div>
                          {!alert.read && (
                            <div className="w-2 h-2 rounded-full bg-ocean-400 flex-shrink-0 mt-1.5" />
                          )}
                        </div>
                      </button>
                    );
                  })
                )}
              </div>

              {/* Threshold Alerts Section */}
              {thresholdAlerts && thresholdAlerts.count > 0 && (
                <div className="border-t border-white/[0.06]">
                  <div className="px-4 py-2 flex items-center gap-2">
                    <TrendingUp className="w-3 h-3 text-ocean-400" />
                    <span className="text-[10px] font-semibold text-ocean-400 uppercase tracking-wider">Threshold Breaches</span>
                    {thresholdAlerts.critical > 0 && (
                      <span className="text-[9px] font-bold text-rose-400 bg-rose-500/[0.12] px-1.5 py-0.5 rounded-full">
                        {thresholdAlerts.critical} critical
                      </span>
                    )}
                  </div>
                  <div className="max-h-[120px] overflow-y-auto">
                    {(thresholdAlerts.alerts || []).slice(0, 5).map((ta: any) => {
                      const Icon = CATEGORY_ICONS[ta.category] || AlertTriangle;
                      return (
                        <div
                          key={ta.id}
                          className="px-4 py-2 border-b border-white/[0.03] hover:bg-white/[0.03] transition-colors"
                        >
                          <div className="flex items-start gap-2">
                            <div className={`mt-0.5 p-1 rounded ${SEVERITY_COLORS[ta.severity]}/[0.12]`}>
                              <Icon className={`w-3 h-3 ${SEVERITY_TEXT[ta.severity]}`} />
                            </div>
                            <div className="flex-1 min-w-0">
                              <span className="text-[11px] font-semibold text-[var(--text-primary)] truncate block">
                                {ta.title}
                              </span>
                              <p className="text-[10px] text-[var(--text-secondary)] mt-0.5 line-clamp-1">
                                {ta.message}
                              </p>
                            </div>
                            <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 mt-1.5 ${SEVERITY_COLORS[ta.severity]}`} />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Footer */}
              {recentAlerts.length > 0 && (
                <div className="px-4 py-2.5 border-t border-white/[0.06]">
                  <button
                    onClick={() => { setBellOpen(false); router.push("/signals"); }}
                    className="w-full text-center text-[11px] font-medium text-ocean-400 hover:text-ocean-300 transition-colors"
                  >
                    {t("alerts.view_all")}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Signals badge */}
        {pendingSignals > 0 && (
          <OcButton
            variant="icon"
            size="icon_md"
            aria-label="View signals"
            onClick={() => router.push("/signals")}
          >
            <div className="relative">
              <Activity className="w-4 h-4" />
              <span className="absolute -top-1.5 -right-1.5 w-4 h-4 rounded-full bg-[var(--warning)] flex items-center justify-center shadow-[0_0_8px_rgba(245,158,11,0.4)]">
                <span className="text-[8px] font-bold text-white">
                  {pendingSignals > 9 ? "9+" : pendingSignals}
                </span>
              </span>
            </div>
          </OcButton>
        )}

        {/* AI Chat */}
        <OcButton
          variant="accent"
          size="icon_md"
          aria-label="Open AI Chat"
          onClick={() => router.push("/chat")}
        >
          <MessageSquare className="w-4 h-4" />
        </OcButton>

        {/* User */}
        <div className="flex items-center gap-2 pl-3 border-l border-slate-200 dark:border-white/[0.06]">
          <button
            aria-label="User menu"
            className="w-8 h-8 rounded-full bg-gradient-to-br from-ocean-500 to-ocean-600 flex items-center justify-center shadow-[0_0_12px_rgba(0,212,200,0.15)]"
          >
            <User className="w-4 h-4 text-white" />
          </button>
        </div>
      </div>
    </header>
  );
}
