/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Shield, RefreshCw, AlertTriangle, Zap, Bug, Thermometer,
  BarChart3, TrendingUp, DollarSign, Activity, CheckCircle, Clock,
} from "lucide-react";
import GlassCard from "@/components/GlassCard";
import KPICard from "@/components/KPICard";
import { OcButton } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { exportToCSV } from "@/lib/export";
import ErrorBoundary from "@/components/ErrorBoundary";
import { useTranslation } from "@/lib/i18n";
import DataQualityBadge from "@/components/DataQualityBadge";

const PRODUCT_ICONS: Record<string, any> = {
  lice_outbreak: Bug,
  hab_crisis: AlertTriangle,
  disease_outbreak: Shield,
  temperature_stress: Thermometer,
  supply_disruption: Zap,
};

const PRODUCT_COLORS: Record<string, string> = {
  lice_outbreak: "ocean",
  hab_crisis: "emerald",
  disease_outbreak: "rose",
  temperature_stress: "amber",
  supply_disruption: "violet",
};

const STATUS_STYLE: Record<string, string> = {
  confirmed: "bg-rose-500/10 text-rose-400 border-rose-500/20",
  pending_confirmation: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  expired: "bg-white/[0.04] text-[var(--text-secondary)] border-white/[0.08]",
};

export default function InsurancePage() {
  const { t } = useTranslation();
  const [dashboard, setDashboard] = useState<any>(null);
  const [products, setProducts] = useState<any[]>([]);
  const [scanning, setScanning] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    const [d, p] = await Promise.allSettled([
      api.parametricDashboard(),
      api.parametricProducts(),
    ]);
    if (d.status === "fulfilled") setDashboard(d.value);
    if (p.status === "fulfilled") setProducts(p.value || []);
    setLoading(false);
  };

  const runScan = async () => {
    setScanning(true);
    try {
      await api.parametricScan();
      await load();
    } catch { /* empty */ }
    setScanning(false);
  };

  useEffect(() => { load(); }, []);

  const triggers = dashboard?.recent_triggers || [];
  const confirmed = dashboard?.confirmed_triggers || 0;
  const pending = dashboard?.pending_triggers || 0;
  const totalPayout = dashboard?.estimated_total_payout_nok || 0;

  return (
    <ErrorBoundary fallbackTitle="Insurance Dashboard error">
    <div className="space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] flex items-center gap-3">
            <Shield className="w-6 h-6 text-emerald-400" />
            {t("nav.insurance")}
            <DataQualityBadge quality="live" source="MET.no + BarentsWatch" />
          </h1>
          <p className="text-sm text-[var(--text-secondary)] mt-1">
            Index-based trigger monitoring &mdash; 5 products across lice, HAB, disease, temperature, supply
          </p>
        </div>
        <div className="flex items-center gap-2">
          {triggers.length > 0 && (
            <OcButton variant="ghost" size="sm"
              onClick={() => exportToCSV(triggers, "parametric_triggers")}
              leftIcon={<BarChart3 className="w-3.5 h-3.5" />}>Export</OcButton>
          )}
          <OcButton variant="primary" size="sm" onClick={runScan} loading={scanning}
            leftIcon={<Activity className="w-3.5 h-3.5" />}>Scan Triggers</OcButton>
          <OcButton variant="secondary" size="sm" onClick={load} loading={loading}
            leftIcon={<RefreshCw className="w-3.5 h-3.5" />}>Refresh</OcButton>
        </div>
      </motion.div>

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <KPICard label="Total Triggers" value={dashboard?.total_triggers || 0}
          icon={AlertTriangle} delay={0} />
        <KPICard label="Confirmed" value={confirmed}
          deltaType={confirmed > 0 ? "negative" : "positive"}
          delta={confirmed > 0 ? "Payouts pending" : "No active payouts"}
          icon={CheckCircle} delay={0.03} />
        <KPICard label="Pending" value={pending}
          icon={Clock} delay={0.06} />
        <KPICard label="Est. Payout"
          value={`NOK ${(totalPayout / 1_000_000).toFixed(1)}M`}
          icon={DollarSign} delay={0.09} />
        <KPICard label="Products Active" value={dashboard?.products_available || 5}
          icon={Shield} delay={0.12} />
      </div>

      {/* Products Catalog */}
      <GlassCard delay={0.1} accent="ocean">
        <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-4 flex items-center gap-2">
          <Shield className="w-4 h-4 text-ocean-400" />
          Insurance Products
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {products.map((p: any) => {
            const Icon = PRODUCT_ICONS[p.id] || Shield;
            const color = PRODUCT_COLORS[p.id] || "ocean";
            const triggerCount = (dashboard?.by_product || {})[p.id] || 0;
            return (
              <div key={p.id} className={`p-4 rounded-xl border border-${color}-500/20 bg-${color}-500/[0.04]`}>
                <div className="flex items-center gap-2 mb-2">
                  <Icon className={`w-4 h-4 text-${color}-400`} />
                  <span className="text-sm font-semibold text-[var(--text-primary)]">{p.name}</span>
                </div>
                <p className="text-[10px] text-[var(--text-secondary)] mb-3">{p.description}</p>
                <div className="space-y-1.5 text-[10px]">
                  <div className="flex justify-between">
                    <span className="text-[var(--text-secondary)]">Trigger</span>
                    <span className="text-[var(--text-primary)] font-mono">{p.trigger_metric} &ge; {p.threshold}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[var(--text-secondary)]">Confirmation</span>
                    <span className="text-[var(--text-primary)]">{p.confirmation_periods} {p.frequency} periods</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[var(--text-secondary)]">Data Source</span>
                    <span className="text-ocean-400">{p.data_source}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[var(--text-secondary)]">Active Triggers</span>
                    <span className={triggerCount > 0 ? "text-rose-400 font-semibold" : "text-emerald-400"}>{triggerCount}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </GlassCard>

      {/* Trigger Events */}
      <GlassCard delay={0.2} accent={confirmed > 0 ? "rose" : "emerald"}>
        <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-400" />
          Trigger Events
          <span className="ml-auto text-[10px] text-[var(--text-secondary)]">
            {triggers.length} events &middot; Last scan: {dashboard?.last_scan?.slice(11, 19) || "never"}
          </span>
        </h3>
        {triggers.length === 0 ? (
          <div className="text-center py-12">
            <CheckCircle className="w-8 h-8 mx-auto text-emerald-400/40 mb-3" />
            <p className="text-sm text-emerald-400">No triggers detected</p>
            <p className="text-[10px] text-[var(--text-secondary)] mt-1">All monitored indices within normal range</p>
          </div>
        ) : (
          <div className="space-y-2">
            {triggers.map((t: any, i: number) => {
              const Icon = PRODUCT_ICONS[t.product] || Shield;
              return (
                <motion.div
                  key={t.id || i}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.05 + i * 0.03 }}
                  className="flex items-center gap-3 p-3 rounded-xl bg-white/[0.03] border border-white/[0.06]"
                >
                  <Icon className="w-4 h-4 text-[var(--text-secondary)] flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="text-[11px] font-semibold text-[var(--text-primary)]">{t.product_name}</span>
                      <span className={`text-[9px] font-semibold px-1.5 py-0.5 rounded border ${STATUS_STYLE[t.status] || STATUS_STYLE.expired}`}>
                        {t.status?.replace("_", " ").toUpperCase()}
                      </span>
                      {t.locality_name && (
                        <span className="text-[9px] text-[var(--text-secondary)]">{t.locality_name}</span>
                      )}
                    </div>
                    <div className="flex items-center gap-3 text-[9px] text-[var(--text-secondary)]">
                      <span>Value: <span className="text-rose-400 font-semibold">{t.actual_value}</span> (threshold: {t.threshold})</span>
                      <span>+{t.breach_pct?.toFixed(0)}% above</span>
                      <span>Confirmation: {t.confirmation_progress}/{t.confirmation_required}</span>
                    </div>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <div className="text-xs font-bold text-[var(--text-primary)]">
                      NOK {((t.estimated_payout_nok || 0) / 1000).toFixed(0)}K
                    </div>
                    <div className="text-[9px] text-[var(--text-secondary)]">{t.data_source}</div>
                  </div>
                </motion.div>
              );
            })}
          </div>
        )}
      </GlassCard>

      {/* PA Breakdown */}
      {dashboard?.by_production_area && Object.keys(dashboard.by_production_area).length > 0 && (
        <GlassCard delay={0.3}>
          <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-violet-400" />
            Triggers by Production Area
          </h3>
          <div className="grid grid-cols-4 md:grid-cols-7 lg:grid-cols-13 gap-2">
            {Array.from({ length: 13 }, (_, i) => i + 1).map((pa) => {
              const count = (dashboard.by_production_area || {})[pa] || 0;
              return (
                <div key={pa} className={`p-2 rounded-lg text-center border ${
                  count > 2 ? "border-rose-500/20 bg-rose-500/[0.06]" :
                  count > 0 ? "border-amber-500/20 bg-amber-500/[0.06]" :
                  "border-white/[0.06] bg-white/[0.02]"
                }`}>
                  <div className="text-[10px] text-[var(--text-secondary)]">PA-{pa}</div>
                  <div className={`text-sm font-bold ${count > 0 ? "text-rose-400" : "text-emerald-400"}`}>{count}</div>
                </div>
              );
            })}
          </div>
        </GlassCard>
      )}

      {/* Footer */}
      <p className="text-[10px] text-[var(--text-secondary)] text-center opacity-60">
        Parametric insurance triggers are index-based and fire automatically when thresholds are breached.
        All triggers require confirmation periods to reduce false positives.
        Data sources: BarentsWatch (lice), CMEMS (HAB), Mattilsynet (disease), MET.no (SST), Anomaly Engine (composite).
        This is an analytical tool for underwriters — not a binding insurance contract.
      </p>
    </div>
    </ErrorBoundary>
  );
}
