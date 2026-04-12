/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { motion } from "framer-motion";
import {
  Radio, Ship, MessageSquare, Network, Shield, Globe2,
  GitBranch, RefreshCw, Wifi, WifiOff, Activity, AlertTriangle,
} from "lucide-react";
import GlassCard from "@/components/GlassCard";
import KPICard from "@/components/KPICard";
import { OcButton } from "@/components/ui/Button";
import { useToast } from "@/components/Toast";
import ErrorBoundary from "@/components/ErrorBoundary";
import { useWebSocket } from "@/lib/useWebSocket";
import { useTranslation } from "@/lib/i18n";
import DataQualityBadge from "@/components/DataQualityBadge";

/* ── WebSocket URLs ─────────────────────────────────────────────── */
const BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000")
  .replace("http://", "ws://")
  .replace("https://", "wss://");

const WS_COMMAND = `${BASE}/ws/command-centre`;
const WS_ALERTS = `${BASE}/ws/alerts`;

/* ── Polling fallback URL ───────────────────────────────────────── */
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function CommandCentrePage() {
  const { t } = useTranslation();
  const { addToast } = useToast();
  const [data, setData] = useState<any>(null);
  const [alertData, setAlertData] = useState<any>(null);
  const [updates, setUpdates] = useState(0);
  const [lastUpdate, setLastUpdate] = useState<string>("");
  const [polling, setPolling] = useState(false);
  const pollTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const toastFired = useRef(false);

  /* ── Command Centre WebSocket ─────────────────────────────────── */
  const handleCommandMessage = useCallback((payload: any) => {
    setData(payload);
    setUpdates((prev) => prev + 1);
    setLastUpdate(new Date().toLocaleTimeString());
    // If we were polling, stop — WS is back
    if (pollTimer.current) {
      clearInterval(pollTimer.current);
      pollTimer.current = null;
      setPolling(false);
    }
  }, []);

  const {
    connected: cmdConnected,
    reconnecting: cmdReconnecting,
    reconnect: cmdReconnect,
  } = useWebSocket(WS_COMMAND, handleCommandMessage);

  /* ── Alerts WebSocket ─────────────────────────────────────────── */
  const handleAlertMessage = useCallback((payload: any) => {
    setAlertData(payload);
  }, []);

  const {
    connected: alertsConnected,
    reconnecting: alertsReconnecting,
  } = useWebSocket(WS_ALERTS, handleAlertMessage);

  /* ── Toast on connect/disconnect ──────────────────────────────── */
  useEffect(() => {
    if (cmdConnected && !toastFired.current) {
      addToast({ type: "success", title: "Command Centre", message: "Connected to intelligence stream" });
      toastFired.current = true;
    }
    if (!cmdConnected && toastFired.current) {
      toastFired.current = false;
    }
  }, [cmdConnected, addToast]);

  /* ── Polling fallback when WS disconnects ─────────────────────── */
  useEffect(() => {
    // Start polling if command WS is disconnected and we aren't already polling
    if (!cmdConnected && !pollTimer.current) {
      const poll = async () => {
        try {
          const [brief, alerts] = await Promise.allSettled([
            fetch(`${API_BASE}/api/brief`).then((r) => r.json()),
            fetch(`${API_BASE}/api/alerts`).then((r) => r.json()),
          ]);
          if (brief.status === "fulfilled") {
            setData((prev: any) => ({ ...prev, _polled: true, brief: brief.value }));
            setUpdates((prev) => prev + 1);
            setLastUpdate(new Date().toLocaleTimeString());
          }
          if (alerts.status === "fulfilled") {
            setAlertData(alerts.value);
          }
          setPolling(true);
        } catch {
          /* polling failure — will retry next interval */
        }
      };
      // Initial poll after 3s grace period (give WS time to reconnect)
      const grace = setTimeout(() => {
        if (!cmdConnected) {
          poll();
          pollTimer.current = setInterval(poll, 30_000);
        }
      }, 3000);
      return () => {
        clearTimeout(grace);
        if (pollTimer.current) {
          clearInterval(pollTimer.current);
          pollTimer.current = null;
        }
      };
    }
    // Clean up polling when WS reconnects
    if (cmdConnected && pollTimer.current) {
      clearInterval(pollTimer.current);
      pollTimer.current = null;
      setPolling(false);
    }
  }, [cmdConnected]);

  /* ── Derived data ─────────────────────────────────────────────── */
  const ais = data?.ais || {};
  const sentiment = data?.sentiment || {};
  const farmNetwork = data?.farm_network || {};
  const regimeAlerts = data?.regime_alerts || [];
  const chile = data?.chile || {};
  const pairs = data?.pairs || {};
  const thresholdAlerts = alertData?.alerts || [];
  const alertCount = alertData?.count || 0;
  const criticalCount = alertData?.critical || 0;

  /* ── Connection status ────────────────────────────────────────── */
  const connectionLabel = cmdConnected
    ? "Connected"
    : cmdReconnecting
      ? "Reconnecting..."
      : polling
        ? "Offline (polling)"
        : "Disconnected";

  const connectionColor = cmdConnected
    ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-400"
    : cmdReconnecting
      ? "bg-amber-500/10 border-amber-500/20 text-amber-400"
      : "bg-rose-500/10 border-rose-500/20 text-rose-400";

  return (
    <ErrorBoundary fallbackTitle="Command Centre error">
    <div className="space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] flex items-center gap-3">
            <Radio className="w-6 h-6 text-ocean-400" />
            {t("nav.command_centre")}
            <DataQualityBadge quality="live" source="Multi-source real-time" />
          </h1>
          <p className="text-sm text-[var(--text-secondary)] mt-1">
            Real-time market intelligence stream &mdash; {cmdConnected ? "live WebSocket" : polling ? "30s poll fallback" : "connecting..."}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Connection status badge */}
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full border ${connectionColor}`}>
            {cmdConnected ? (
              <>
                {/* Pulsing green dot */}
                <span className="relative flex h-2.5 w-2.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500" />
                </span>
                <span className="text-[11px] font-semibold">LIVE</span>
              </>
            ) : cmdReconnecting ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                <span className="text-[11px] font-semibold">RECONNECTING</span>
              </>
            ) : (
              <>
                <WifiOff className="w-3.5 h-3.5" />
                <span className="text-[11px] font-semibold">{polling ? "POLLING" : "OFFLINE"}</span>
              </>
            )}
          </div>

          {/* Alerts WebSocket status (small secondary indicator) */}
          <div className={`flex items-center gap-1 px-2 py-1 rounded-full border text-[9px] font-medium ${
            alertsConnected
              ? "bg-emerald-500/5 border-emerald-500/10 text-emerald-400/70"
              : alertsReconnecting
                ? "bg-amber-500/5 border-amber-500/10 text-amber-400/70"
                : "bg-rose-500/5 border-rose-500/10 text-rose-400/70"
          }`}>
            <AlertTriangle className="w-2.5 h-2.5" />
            Alerts {alertsConnected ? "live" : "..."}
          </div>

          <span className="text-[10px] text-[var(--text-secondary)]">
            {updates} updates &middot; {lastUpdate || "waiting..."}
          </span>
          {!cmdConnected && (
            <OcButton variant="secondary" size="sm" onClick={cmdReconnect}
              leftIcon={<RefreshCw className="w-3.5 h-3.5" />}>Reconnect</OcButton>
          )}
        </div>
      </motion.div>

      {/* KPI Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        <KPICard label="AIS Vessels"
          value={ais.active_vessels || ais.n_vessels || ais.tracks?.length || 0}
          icon={Ship} delay={0} />
        <KPICard label="Sentiment Score"
          value={(sentiment.score || sentiment.avg_score || 0).toFixed(2)}
          deltaType={sentiment.direction === "bullish" ? "positive" : sentiment.direction === "bearish" ? "negative" : "neutral"}
          icon={MessageSquare} delay={0.03} />
        <KPICard label="Farm Network"
          value={`${farmNetwork.n_farms || 0} farms`}
          delta={`${farmNetwork.n_above_threshold || 0} above limit`}
          icon={Network} delay={0.06} />
        <KPICard label="Regime Alerts"
          value={Array.isArray(regimeAlerts) ? regimeAlerts.length : 0}
          icon={Shield} delay={0.09} />
        <KPICard label="Chile Supply"
          value={chile.status || chile.supply_status || "\u2014"}
          icon={Globe2} delay={0.12} />
        <KPICard label="Threshold Alerts"
          value={alertCount}
          delta={criticalCount > 0 ? `${criticalCount} critical` : undefined}
          deltaType={criticalCount > 0 ? "negative" : "neutral"}
          icon={AlertTriangle} delay={0.15} />
      </div>

      {!data ? (
        <GlassCard delay={0.1}>
          <div className="flex flex-col items-center justify-center py-16">
            <Activity className="w-8 h-8 text-ocean-500/40 animate-pulse mb-3" />
            <p className="text-sm text-[var(--text-secondary)]">
              {cmdConnected ? "Waiting for first intelligence update..." : "Connecting to intelligence stream..."}
            </p>
            <p className="text-[10px] text-[var(--text-secondary)] mt-1">
              {connectionLabel}
            </p>
          </div>
        </GlassCard>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

          {/* AIS Vessel Activity */}
          <GlassCard delay={0.1} accent="ocean">
            <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
              <Ship className="w-4 h-4 text-ocean-400" />
              AIS Vessel Activity
              <span className="ml-auto text-[9px] px-1.5 py-0.5 rounded-full bg-ocean-500/10 text-ocean-400 border border-ocean-500/20">
                {cmdConnected ? "LIVE" : "CACHED"}
              </span>
            </h3>
            <div className="space-y-2 max-h-[300px] overflow-y-auto">
              {(ais.harvest_signals || ais.tracks || []).slice(0, 8).map((v: any, i: number) => (
                <div key={i} className="p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                  <div className="flex items-center justify-between mb-0.5">
                    <span className="text-[11px] font-semibold text-[var(--text-primary)]">{v.vessel_name || v.name || "Vessel"}</span>
                    <span className={`text-[9px] font-semibold px-1.5 py-0.5 rounded ${
                      v.signal_type === "harvest" ? "bg-emerald-500/10 text-emerald-400" :
                      v.signal_type === "treatment" ? "bg-amber-500/10 text-amber-400" :
                      "bg-white/[0.04] text-[var(--text-secondary)]"
                    }`}>{v.signal_type || v.type || "track"}</span>
                  </div>
                  <p className="text-[9px] text-[var(--text-secondary)] truncate">{v.location || v.farm_name || "Position tracking"}</p>
                </div>
              ))}
              {(ais.harvest_signals || ais.tracks || []).length === 0 && (
                <p className="text-[11px] text-[var(--text-secondary)] text-center py-4">No vessel signals</p>
              )}
            </div>
          </GlassCard>

          {/* Sentiment Feed */}
          <GlassCard delay={0.15} accent="amber">
            <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
              <MessageSquare className="w-4 h-4 text-amber-400" />
              Sentiment Feed
              <span className="ml-auto text-[9px] px-1.5 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">NLP</span>
            </h3>
            <div className="space-y-2 max-h-[300px] overflow-y-auto">
              {(sentiment.articles || sentiment.recent || data?.articles || []).slice(0, 6).map((a: any, i: number) => (
                <div key={i} className="p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                  <p className="text-[11px] text-[var(--text-primary)] font-medium truncate">{a.title || a.headline || "Article"}</p>
                  <div className="flex items-center justify-between mt-1">
                    <span className="text-[9px] text-[var(--text-secondary)]">{a.source || "News"}</span>
                    <span className={`text-[9px] font-semibold ${
                      (a.sentiment || a.score || 0) > 0 ? "text-emerald-400" :
                      (a.sentiment || a.score || 0) < 0 ? "text-rose-400" : "text-amber-400"
                    }`}>{(a.sentiment || a.score || 0).toFixed(2)}</span>
                  </div>
                </div>
              ))}
              {(sentiment.articles || sentiment.recent || data?.articles || []).length === 0 && (
                <p className="text-[11px] text-[var(--text-secondary)] text-center py-4">No sentiment data</p>
              )}
            </div>
          </GlassCard>

          {/* Alerts & Pairs */}
          <GlassCard delay={0.2} accent="violet">
            <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
              <Shield className="w-4 h-4 text-violet-400" />
              Alerts &amp; Signals
            </h3>
            <div className="space-y-3">
              {/* Threshold alerts (from /ws/alerts) */}
              {thresholdAlerts.length > 0 && (
                <div>
                  <p className="text-[10px] text-[var(--text-secondary)] uppercase tracking-wider mb-1.5">
                    Threshold Alerts
                    {alertsConnected && (
                      <span className="ml-1 inline-flex items-center gap-0.5">
                        <span className="relative flex h-1.5 w-1.5">
                          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                          <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-500" />
                        </span>
                      </span>
                    )}
                  </p>
                  {thresholdAlerts.slice(0, 4).map((a: any, i: number) => (
                    <div key={`ta-${i}`} className="p-2 rounded-lg bg-white/[0.03] border border-white/[0.06] mb-1">
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] font-semibold">{a.metric || a.type || "Alert"}</span>
                        <span className={`text-[9px] font-semibold px-1.5 py-0.5 rounded ${
                          a.severity === "critical" ? "bg-rose-500/10 text-rose-400" :
                          a.severity === "warning" ? "bg-amber-500/10 text-amber-400" :
                          "bg-white/[0.04] text-[var(--text-secondary)]"
                        }`}>{a.severity || "info"}</span>
                      </div>
                      <p className="text-[9px] text-[var(--text-secondary)] truncate">{a.message || a.description || ""}</p>
                    </div>
                  ))}
                </div>
              )}

              {/* Regime alerts */}
              <div>
                <p className="text-[10px] text-[var(--text-secondary)] uppercase tracking-wider mb-1.5">Regime Alerts</p>
                {(Array.isArray(regimeAlerts) ? regimeAlerts : []).slice(0, 3).map((a: any, i: number) => (
                  <div key={i} className="p-2 rounded-lg bg-white/[0.03] border border-white/[0.06] mb-1">
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] font-semibold">PA {a.production_area || a.pa}</span>
                      <span className="text-[9px] text-amber-400">{a.current} &rarr; {a.predicted}</span>
                    </div>
                  </div>
                ))}
                {(Array.isArray(regimeAlerts) ? regimeAlerts : []).length === 0 && (
                  <p className="text-[10px] text-emerald-400">No color changes predicted</p>
                )}
              </div>

              {/* Pairs signals */}
              <div>
                <p className="text-[10px] text-[var(--text-secondary)] uppercase tracking-wider mb-1.5">Pairs Trading</p>
                {(pairs.signals || data?.pairs_signals || []).slice(0, 3).map((ps: any, i: number) => (
                  <div key={i} className="p-2 rounded-lg bg-white/[0.03] border border-white/[0.06] mb-1">
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] font-bold">{ps.pair || ps.name}</span>
                      <span className={`text-[9px] font-semibold px-1.5 py-0.5 rounded ${
                        (ps.signal || "").includes("LONG") ? "bg-emerald-500/10 text-emerald-400" :
                        (ps.signal || "").includes("SHORT") ? "bg-rose-500/10 text-rose-400" :
                        "bg-white/[0.04] text-[var(--text-secondary)]"
                      }`}>{ps.signal || "MONITOR"}</span>
                    </div>
                    <p className="text-[9px] text-[var(--text-secondary)]">z={ps.z_score?.toFixed(2)}</p>
                  </div>
                ))}
                {(pairs.signals || data?.pairs_signals || []).length === 0 && (
                  <p className="text-[10px] text-[var(--text-secondary)]">No pairs signals</p>
                )}
              </div>
            </div>
          </GlassCard>
        </div>
      )}

      <GlassCard delay={0.3} accent="none" hover={false}>
        <details>
          <summary className="text-[11px] text-[var(--text-secondary)] cursor-pointer hover:text-ocean-400 transition-colors">
            Raw intelligence payload (debug)
          </summary>
          <pre className="mt-2 text-[9px] text-[var(--text-secondary)] overflow-x-auto max-h-[200px] overflow-y-auto whitespace-pre-wrap">
            {data ? JSON.stringify(data, null, 2).slice(0, 2000) : "No data yet"}
          </pre>
          {alertData && (
            <>
              <p className="mt-2 text-[10px] text-[var(--text-secondary)] font-semibold">Alerts stream:</p>
              <pre className="mt-1 text-[9px] text-[var(--text-secondary)] overflow-x-auto max-h-[150px] overflow-y-auto whitespace-pre-wrap">
                {JSON.stringify(alertData, null, 2).slice(0, 1000)}
              </pre>
            </>
          )}
        </details>
      </GlassCard>

      <p className="text-[10px] text-[var(--text-secondary)] text-center opacity-60">
        Intelligence aggregated from 7 engines: AIS Tracker, Sentiment NLP, Farm Network, Regime Detector, Chile Monitor, Pairs Engine, Threshold Alerts.
        {cmdConnected ? " WebSocket streaming live." : polling ? " Polling every 30 seconds (WebSocket disconnected)." : " Reconnecting..."}
      </p>
    </div>
    </ErrorBoundary>
  );
}
