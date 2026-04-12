"use client";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Settings, Server, CreditCard, Check, Zap, RefreshCw,
  Database, Shield, Bell, Moon, Eye, Activity, RotateCcw,
} from "lucide-react";
import GlassCard from "@/components/GlassCard";
import KPICard from "@/components/KPICard";
import { OcButton } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { resetOnboarding } from "@/components/OnboardingWizard";
import { useTranslation } from "@/lib/i18n";
import ErrorBoundary from "@/components/ErrorBoundary";

/* eslint-disable @typescript-eslint/no-explicit-any */

export default function SettingsPage() {
  const { t } = useTranslation();
  const [tiers, setTiers] = useState<any[]>([]);
  const [health, setHealth] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [currentTier] = useState("pro");

  const load = () => {
    setLoading(true);
    Promise.allSettled([
      api.tiers().then((d) => setTiers(Array.isArray(d) ? d : d?.tiers || [])),
      api.health().then(setHealth),
    ]).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  return (
    <ErrorBoundary fallbackTitle="Settings error">
    <div className="space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] flex items-center gap-3">
            <Settings className="w-6 h-6 text-ocean-400" />
            {t("nav.settings")}
          </h1>
          <p className="text-sm text-[var(--text-secondary)] mt-1">
            Platform configuration, data sources &amp; subscription management
          </p>
        </div>
        <OcButton variant="secondary" size="sm" onClick={load} loading={loading}
          leftIcon={<RefreshCw className="w-3.5 h-3.5" />}>Refresh</OcButton>
      </motion.div>

      {/* System Status KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KPICard label="API Status"
          value={health?.status === "healthy" ? "Healthy" : "Unknown"}
          deltaType={health?.status === "healthy" ? "positive" : undefined}
          icon={Activity} delay={0} />
        <KPICard label="Database"
          value={health?.database === "ok" ? "Connected" : "Unknown"}
          deltaType={health?.database === "ok" ? "positive" : undefined}
          icon={Database} delay={0.04} />
        <KPICard label="API Endpoint"
          value={process.env.NEXT_PUBLIC_API_URL ? "Configured" : "Default"}
          delta={process.env.NEXT_PUBLIC_API_URL || "localhost:8000"}
          icon={Server} delay={0.08} />
        <KPICard label="Subscription"
          value="Pro"
          delta="Active"
          deltaType="positive"
          icon={Zap} delay={0.12} />
      </div>

      {/* Data Sources */}
      <GlassCard delay={0.1} accent="ocean">
        <div className="flex items-center gap-2 mb-4">
          <Database className="w-4 h-4 text-ocean-400" />
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">Data Sources</h3>
        </div>
        <div className="space-y-0">
          {[
            { name: "BarentsWatch", desc: "Lice data, 1,815 farm localities", status: "live", interval: "15 min" },
            { name: "SSB Table 03024", desc: "Salmon export prices (NOK/kg)", status: "live", interval: "6 hours" },
            { name: "FRED (12 series)", desc: "Commodities, FX, macro indicators", status: "live", interval: "2 hours" },
            { name: "Copernicus CMEMS", desc: "Satellite chlorophyll-a, bloom risk", status: "live", interval: "1 hour" },
            { name: "Yahoo Finance", desc: "Oslo equities (MOWI, SALM, LSG, GSF, BAKKA)", status: "live", interval: "10 min" },
            { name: "Fiskeridirektoratet", desc: "Official production stats (8,333 records)", status: "loaded", interval: "On startup" },
          ].map((src) => (
            <div key={src.name} className="flex items-center justify-between py-3 border-b border-white/[0.04] last:border-0">
              <div>
                <span className="text-[12px] font-semibold text-[var(--text-primary)]">{src.name}</span>
                <p className="text-[10px] text-[var(--text-secondary)]">{src.desc}</p>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-[10px] text-[var(--text-secondary)]">{src.interval}</span>
                <span className={`text-[9px] px-1.5 py-0.5 rounded-full border ${
                  src.status === "live"
                    ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                    : "bg-ocean-500/10 text-ocean-400 border-ocean-500/20"
                }`}>
                  {src.status.toUpperCase()}
                </span>
              </div>
            </div>
          ))}
        </div>
      </GlassCard>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Platform Config */}
        <GlassCard delay={0.15}>
          <div className="flex items-center gap-2 mb-4">
            <Server className="w-4 h-4 text-ocean-400" />
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">Platform Configuration</h3>
          </div>
          <div className="space-y-0">
            {[
              { key: "Data License", value: "NLOD 2.0 (Norwegian Open Data)" },
              { key: "Cost Model", value: "Learned-principles (17yr Fiskeridirektoratet)" },
              { key: "FCR", value: "1.30 (official, range 1.21-1.35)" },
              { key: "MTB Capacity", value: "947,943 tonnes (PA-regulated)" },
              { key: "ML Ensemble", value: "Prophet + LSTM + XGBoost + Causal" },
              { key: "Signal Mode", value: "Discretionary (manual confirmation)" },
            ].map((item) => (
              <div key={item.key} className="flex items-center justify-between py-2.5 border-b border-white/[0.04] last:border-0">
                <span className="text-[10px] text-[var(--text-secondary)] uppercase tracking-wider">{item.key}</span>
                <span className="text-[11px] text-[var(--text-primary)] font-medium">{item.value}</span>
              </div>
            ))}
          </div>
        </GlassCard>

        {/* Preferences */}
        <GlassCard delay={0.2}>
          <div className="flex items-center gap-2 mb-4">
            <Bell className="w-4 h-4 text-ocean-400" />
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">Preferences</h3>
          </div>
          <div className="space-y-3">
            {[
              { icon: Bell, label: "Email notifications for new signals", checked: true },
              { icon: RefreshCw, label: "Auto-refresh dashboard every 5 min", checked: true },
              { icon: Moon, label: "Dark mode", checked: true, disabled: true },
              { icon: Eye, label: "Show disclaimer on every page", checked: false },
              { icon: Shield, label: "Require confirmation for all trades", checked: true },
            ].map(({ icon: Icon, label, checked, disabled }) => (
              <label key={label} className="flex items-center justify-between p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.04] hover:bg-white/[0.04] transition-colors cursor-pointer">
                <div className="flex items-center gap-2.5">
                  <Icon className="w-3.5 h-3.5 text-[var(--text-secondary)]" />
                  <span className="text-[11px] text-[var(--text-secondary)]">{label}</span>
                </div>
                <input type="checkbox" defaultChecked={checked} disabled={disabled}
                  className="accent-ocean-500 w-4 h-4" />
              </label>
            ))}

            {/* Restart Onboarding */}
            <div className="mt-4 pt-4 border-t border-white/[0.06]">
              <OcButton
                variant="ghost"
                size="sm"
                onClick={() => resetOnboarding()}
                leftIcon={<RotateCcw className="w-3.5 h-3.5" />}
              >
                Restart Onboarding Wizard
              </OcButton>
              <p className="text-[10px] text-[var(--text-secondary)] mt-1 ml-1">
                Re-run the setup wizard to change your role, region, farms, and alert preferences.
              </p>
            </div>
          </div>
        </GlassCard>
      </div>

      {/* Subscription Tiers */}
      <div>
        <div className="flex items-center gap-2 mb-4">
          <CreditCard className="w-4 h-4 text-violet-400" />
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">Subscription Tiers</h3>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-48 rounded-2xl bg-white/[0.03] animate-pulse" />
            ))}
          </div>
        ) : tiers.length === 0 ? (
          <GlassCard delay={0}>
            <div className="py-8 text-center">
              <CreditCard className="w-8 h-8 mx-auto mb-3 opacity-20" />
              <p className="text-sm text-[var(--text-secondary)]">Subscription tiers not configured</p>
              <p className="text-[10px] text-[var(--text-secondary)] opacity-60 mt-1">Contact sales for pricing information</p>
            </div>
          </GlassCard>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {tiers.map((tier, i) => {
              const isActive = tier.id === currentTier;
              return (
                <GlassCard
                  key={tier.id || i}
                  delay={0.25 + i * 0.08}
                  glow={isActive}
                  className={isActive ? "border-ocean-500/30" : ""}
                >
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="text-lg font-bold text-[var(--text-primary)]">{tier.name}</h4>
                    {isActive && (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-ocean-500/15 text-ocean-400 border border-ocean-500/20">
                        <Zap className="w-3 h-3" /> Current
                      </span>
                    )}
                  </div>

                  <div className="mb-4">
                    <span className="text-3xl font-bold text-[var(--text-primary)]">
                      {tier.price === 0 ? "Free" : `${tier.price} NOK`}
                    </span>
                    {tier.price > 0 && (
                      <span className="text-xs text-[var(--text-secondary)]"> /month</span>
                    )}
                  </div>

                  <div className="space-y-2 mb-4">
                    {(tier.features || []).map((feature: string, j: number) => (
                      <div key={j} className="flex items-center gap-2">
                        <Check className="w-3.5 h-3.5 text-ocean-400 shrink-0" />
                        <span className="text-[11px] text-[var(--text-secondary)]">{feature}</span>
                      </div>
                    ))}
                  </div>

                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    disabled={isActive}
                    className={`w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all ${
                      isActive
                        ? "bg-white/[0.04] border border-white/[0.06] text-[var(--text-secondary)] cursor-default"
                        : "bg-ocean-500/15 border border-ocean-500/20 text-ocean-400 hover:bg-ocean-500/25"
                    }`}
                  >
                    {isActive ? "Current Plan" : "Upgrade"}
                  </motion.button>
                </GlassCard>
              );
            })}
          </div>
        )}
      </div>

      <p className="text-[9px] text-[var(--text-secondary)] text-center opacity-50">
        Data: BarentsWatch (NLOD 2.0), SSB (CC BY 4.0), FRED (public domain), Copernicus (open access).
        All calculations use learned-principles model with live data only.
      </p>
    </div>
    </ErrorBoundary>
  );
}
