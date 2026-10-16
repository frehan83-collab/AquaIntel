"use client";
/**
 * Public pricing page — driven by /api/billing/catalog (the canonical plan
 * catalog + Stripe prices), never by a hardcoded feature list. `mock: true`
 * means Stripe is not configured on this deployment, so the page says so
 * instead of pretending the ids are live.
 */
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Check, CreditCard, Info } from "lucide-react";
import GlassCard from "@/components/GlassCard";
import { OcButton } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { formatNumber, useTranslation } from "@/lib/i18n";
import { useApiError } from "@/lib/useApiError";
import type { BillingCatalog, BillingPlan } from "@/types/api";

export default function PricingPage() {
  const { locale } = useTranslation();
  const handleError = useApiError();
  const [catalog, setCatalog] = useState<BillingCatalog | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.billingCatalog().then(setCatalog).catch(handleError("billing_catalog"));
  }, [handleError]);

  const startCheckout = async (plan: BillingPlan) => {
    setBusy(plan.plan);
    setNotice(null);
    setError(null);
    try {
      const res = await api.billingCheckout(plan.plan);
      if (res.demo_mode) {
        setNotice(
          `Demo mode: Stripe is not configured on this deployment. Mock checkout for ` +
            `${plan.name} at ${res.checkout_url}`,
        );
      } else if (res.checkout_url) {
        window.location.assign(res.checkout_url);
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Checkout failed";
      setError(
        msg.includes("401")
          ? "Sign in first — checkout is tied to your account."
          : msg,
      );
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-2xl font-semibold text-[var(--text-primary)]">Pricing</h1>
        <p className="text-sm text-[var(--text-secondary)] mt-1">
          Plans unlock the premium outputs (2–20 week price path, supply tension,
          AIS harvest intelligence, contract risk, harvest optimizer).
          Anonymous browsing is never gated.
        </p>
      </motion.div>

      {catalog?.plans.some((p) => p.mock) && (
        <div className="mt-4 flex items-start gap-2 text-xs text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded-lg p-3">
          <Info className="w-4 h-4 mt-0.5 shrink-0" />
          <span>
            Stripe is not configured on this deployment, so prices are shown from the
            canonical plan catalog and checkout runs in demo mode.
          </span>
        </div>
      )}
      {notice && (
        <div className="mt-3 text-xs text-ocean-400 bg-ocean-500/10 border border-ocean-500/20 rounded-lg p-3">
          {notice}
        </div>
      )}
      {error && (
        <div className="mt-3 text-xs text-rose-400 bg-rose-500/10 border border-rose-500/20 rounded-lg p-3">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-6">
        {(catalog?.plans ?? []).map((plan, i) => (
          <GlassCard key={plan.plan} accent={plan.premium_outputs_included ? "ocean" : "violet"} delay={i * 0.05}>
            <div className="flex items-baseline justify-between">
              <h2 className="text-lg font-semibold text-[var(--text-primary)]">{plan.name}</h2>
              <span className="text-sm text-[var(--text-secondary)]">
                {plan.amount_nok === 0
                  ? "Free"
                  : `NOK ${formatNumber(plan.amount_nok, locale, 0)}/mo`}
              </span>
            </div>
            <p className="text-xs text-[var(--text-secondary)] mt-1">{plan.audience}</p>
            <ul className="mt-3 space-y-1.5">
              {plan.features.map((f) => (
                <li key={f} className="flex items-start gap-2 text-xs text-[var(--text-secondary)]">
                  <Check className="w-3.5 h-3.5 mt-0.5 text-emerald-400 shrink-0" />
                  <span>{f}</span>
                </li>
              ))}
            </ul>
            <div className="mt-3 text-[10px] text-white/40">
              {plan.api_calls_per_day > 0
                ? `${formatNumber(plan.api_calls_per_day, locale, 0)} API calls/day`
                : "Unlimited API calls"}
              {plan.seats > 0 ? ` · ${plan.seats} seats` : " · unlimited seats"}
              {plan.sites > 0 ? ` · ${plan.sites} sites` : ""}
            </div>
            <div className="mt-4">
              <OcButton
                onClick={() => startCheckout(plan)}
                disabled={busy === plan.plan || plan.amount_nok === 0}
              >
                <CreditCard className="w-3.5 h-3.5 mr-1.5" />
                {busy === plan.plan
                  ? "Starting…"
                  : plan.amount_nok === 0
                    ? "Included"
                    : `Choose ${plan.name}`}
              </OcButton>
            </div>
          </GlassCard>
        ))}
      </div>

      {catalog?.licensed_tier && (
        <GlassCard accent="emerald" delay={0.25}>
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">
            {catalog.licensed_tier.name}
          </h2>
          <p className="text-xs text-[var(--text-secondary)] mt-1">
            {catalog.licensed_tier.audience} — {catalog.licensed_tier.note}
          </p>
        </GlassCard>
      )}
    </div>
  );
}
