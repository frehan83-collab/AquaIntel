"use client";
import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  CreditCard, Check, X, AlertTriangle, Receipt,
  ArrowUpRight, Crown, Zap, Building2, TrendingUp,
} from "lucide-react";
import KPICard from "@/components/KPICard";
import GlassCard from "@/components/GlassCard";
import { OcButton } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { useTranslation, formatDate } from "@/lib/i18n";

const TIER_DETAILS: Record<string, { icon: any; color: string; features: string[] }> = {
  professional: {
    icon: Zap,
    color: "ocean",
    features: [
      "Real-time alerts (15-min polling)",
      "Farm-level lice forecasts",
      "Harvest timing optimizer",
      "ML baselines (Chronos-2)",
      "Treatment recommendations",
      "5,000 API calls/month",
    ],
  },
  enterprise: {
    icon: Building2,
    color: "emerald",
    features: [
      "Everything in Professional",
      "Market Terminal &amp; signals",
      "EU Traceability tools",
      "Supply chain intelligence",
      "Global supply monitoring",
      "50,000 API calls/month",
    ],
  },
  investor: {
    icon: Crown,
    color: "amber",
    features: [
      "Everything in Enterprise",
      "Trading signals &amp; execution",
      "Performance tracking",
      "Full API access",
      "Custom datasets &amp; reports",
      "100,000 API calls/month",
    ],
  },
};

export default function BillingPage() {
  const { t, locale } = useTranslation();
  const [status, setStatus] = useState<any>(null);
  const [invoices, setInvoices] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [upgrading, setUpgrading] = useState<string | null>(null);
  const [showCancel, setShowCancel] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const [s, inv] = await Promise.allSettled([
        api.billingSubscriptionStatus(),
        api.billingInvoiceHistory(),
      ]);
      if (s.status === "fulfilled") setStatus(s.value);
      if (inv.status === "fulfilled") setInvoices(inv.value);
    } catch { /* empty */ }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleUpgrade = async (tier: string) => {
    setUpgrading(tier);
    try {
      const result = await api.billingCreateCheckout(tier);
      if (result?.checkout_url) {
        window.location.href = result.checkout_url;
      } else if (result?.demo_mode) {
        alert("Stripe not configured. Set STRIPE_SECRET_KEY to enable payments.");
      }
    } catch { /* empty */ }
    setUpgrading(null);
  };

  const handleCancel = async () => {
    try {
      await api.billingCancel();
      setShowCancel(false);
      load();
    } catch { /* empty */ }
  };

  const currentTier = status?.tier || "free";
  const sub = status?.subscription;

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between"
      >
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">
            {t("page.billing.title")}
          </h1>
          <p className="text-sm text-[var(--text-secondary)] mt-1">
            Manage your OpenClaw subscription and payment history
          </p>
        </div>
        <OcButton onClick={load} loading={loading}>Refresh</OcButton>
      </motion.div>

      {/* Current Subscription KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KPICard
          label="Current Tier"
          value={currentTier.charAt(0).toUpperCase() + currentTier.slice(1)}
          icon={CreditCard}
          delay={0}
        />
        <KPICard
          label="Monthly Price"
          value={sub ? `${sub.monthly_price_nok?.toLocaleString()} NOK` : "Free"}
          icon={Receipt}
          delay={0.05}
        />
        <KPICard
          label="API Calls"
          value={sub ? `${sub.api_calls_month} / ${sub.api_calls_limit}` : "0 / 100"}
          icon={TrendingUp}
          delay={0.1}
        />
        <KPICard
          label="Status"
          value={
            sub?.cancel_at_period_end
              ? "Cancelling"
              : sub?.is_active
              ? "Active"
              : "Inactive"
          }
          icon={sub?.is_active ? Check : AlertTriangle}
          delay={0.15}
        />
      </div>

      {/* Active Subscription Details */}
      {sub?.is_active && (
        <GlassCard delay={0.2} accent="ocean">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-semibold text-[var(--text-primary)]">
              Active Subscription
            </h2>
            {!sub.cancel_at_period_end && (
              <OcButton
                variant="ghost"
                size="sm"
                onClick={() => setShowCancel(true)}
              >
                Cancel Subscription
              </OcButton>
            )}
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-[var(--text-secondary)]">Started</span>
              <div className="text-[var(--text-primary)] font-medium">
                {sub.started_at ? formatDate(sub.started_at, locale) : "\u2014"}
              </div>
            </div>
            <div>
              <span className="text-[var(--text-secondary)]">Current Period Ends</span>
              <div className="text-[var(--text-primary)] font-medium">
                {sub.current_period_end
                  ? formatDate(sub.current_period_end, locale)
                  : "\u2014"}
              </div>
            </div>
            <div>
              <span className="text-[var(--text-secondary)]">Price</span>
              <div className="text-[var(--text-primary)] font-medium">
                {sub.monthly_price_nok?.toLocaleString()} NOK/mo
              </div>
            </div>
            <div>
              <span className="text-[var(--text-secondary)]">Auto-Renew</span>
              <div className="text-[var(--text-primary)] font-medium">
                {sub.cancel_at_period_end ? "No (cancelling)" : "Yes"}
              </div>
            </div>
          </div>

          {/* Cancel confirmation */}
          {showCancel && (
            <div className="mt-4 p-3 rounded-lg bg-rose-500/10 border border-rose-500/20">
              <p className="text-sm text-rose-300 mb-2">
                Are you sure? Your subscription will remain active until the end of the current billing period.
              </p>
              <div className="flex gap-2">
                <OcButton size="sm" onClick={handleCancel}>
                  Confirm Cancel
                </OcButton>
                <OcButton variant="ghost" size="sm" onClick={() => setShowCancel(false)}>
                  Keep Subscription
                </OcButton>
              </div>
            </div>
          )}
        </GlassCard>
      )}

      {/* Tier Comparison */}
      <h2 className="text-lg font-semibold text-[var(--text-primary)]">
        Available Plans
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {Object.entries(TIER_DETAILS).map(([tier, info], i) => {
          const Icon = info.icon;
          const price = status?.available_tiers?.[tier]?.price_nok
            ?? (tier === "professional" ? 2990 : tier === "enterprise" ? 14900 : 24900);
          const isCurrent = currentTier === tier;

          return (
            <GlassCard key={tier} delay={0.1 * (i + 1)} accent={info.color as any}>
              <div className="flex items-center gap-2 mb-3">
                <Icon className="w-5 h-5 text-ocean-400" />
                <h3 className="text-base font-semibold text-[var(--text-primary)]">
                  {tier.charAt(0).toUpperCase() + tier.slice(1)}
                </h3>
              </div>
              <div className="text-2xl font-bold text-[var(--text-primary)] mb-1">
                {price.toLocaleString()} <span className="text-sm font-normal text-[var(--text-secondary)]">NOK/mo</span>
              </div>
              <ul className="space-y-1.5 mt-3 mb-4">
                {info.features.map((f, j) => (
                  <li key={j} className="flex items-start gap-2 text-xs text-[var(--text-secondary)]">
                    <Check className="w-3 h-3 text-emerald-400 mt-0.5 flex-shrink-0" />
                    <span dangerouslySetInnerHTML={{ __html: f }} />
                  </li>
                ))}
              </ul>
              {isCurrent ? (
                <div className="px-3 py-1.5 rounded-full bg-ocean-500/10 text-ocean-400 text-xs font-medium text-center">
                  Current Plan
                </div>
              ) : (
                <OcButton
                  onClick={() => handleUpgrade(tier)}
                  loading={upgrading === tier}
                  className="w-full"
                  leftIcon={<ArrowUpRight className="w-4 h-4" />}
                >
                  Upgrade
                </OcButton>
              )}
            </GlassCard>
          );
        })}
      </div>

      {/* Invoice History */}
      <GlassCard delay={0.4} accent="none">
        <h2 className="text-lg font-semibold text-[var(--text-primary)] mb-3">
          Invoice History
        </h2>
        {invoices?.demo_mode && (
          <p className="text-xs text-amber-400 mb-2">
            Demo mode &mdash; Stripe not configured. Set STRIPE_SECRET_KEY to enable real billing.
          </p>
        )}
        {(!invoices?.invoices || invoices.invoices.length === 0) ? (
          <p className="text-sm text-[var(--text-secondary)]">No invoices yet.</p>
        ) : (
          <div className="space-y-1">
            <div className="flex items-center text-[10px] font-medium text-[var(--text-secondary)] uppercase tracking-wider pb-1 border-b border-white/[0.06]">
              <span className="flex-1">Date</span>
              <span className="w-24 text-right">Amount</span>
              <span className="w-20 text-right">Status</span>
              <span className="w-16 text-right">Link</span>
            </div>
            {invoices.invoices.map((inv: any) => (
              <div key={inv.id} className="flex items-center text-xs py-1.5 border-b border-white/[0.03]">
                <span className="flex-1 text-[var(--text-primary)]">
                  {inv.created ? formatDate(inv.created, locale) : "\u2014"}
                </span>
                <span className="w-24 text-right text-[var(--text-primary)]">
                  {inv.amount_nok?.toLocaleString()} NOK
                </span>
                <span className="w-20 text-right">
                  <span className={`px-1.5 py-0.5 rounded-full text-[10px] ${
                    inv.status === "paid"
                      ? "bg-emerald-500/10 text-emerald-400"
                      : "bg-amber-500/10 text-amber-400"
                  }`}>
                    {inv.status}
                  </span>
                </span>
                <span className="w-16 text-right">
                  {inv.invoice_url && (
                    <a
                      href={inv.invoice_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-ocean-400 hover:text-ocean-300"
                    >
                      View
                    </a>
                  )}
                </span>
              </div>
            ))}
          </div>
        )}
      </GlassCard>
    </div>
  );
}
