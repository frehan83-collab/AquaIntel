"use client";
import { motion } from "framer-motion";
import Link from "next/link";
import { AlertTriangle, CheckCircle2 } from "lucide-react";
import StatusBadge from "@/components/StatusBadge";
import type { AlertItem } from "@/types/api";

interface DashboardHeroAlertProps {
  heroAlert: AlertItem | null;
  alertsLoaded: boolean;
  isVisible: boolean;
  order: number;
}

export default function DashboardHeroAlert({ heroAlert, alertsLoaded, isVisible, order }: DashboardHeroAlertProps) {
  if (!isVisible || !alertsLoaded) return null;

  return (
    <div style={{ order }}>
      <motion.div
        initial={{ opacity: 0, y: -6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        {heroAlert && (heroAlert.severity === "critical" || heroAlert.severity === "high") ? (
          <div className={`rounded-2xl p-5 mb-1 border ${
            heroAlert.severity === "critical"
              ? "bg-rose-500/[0.08] border-rose-500/20"
              : "bg-amber-500/[0.08] border-amber-500/20"
          }`}>
            <div className="flex items-center gap-4">
              <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${
                heroAlert.severity === "critical"
                  ? "bg-rose-500/15"
                  : "bg-amber-500/15"
              }`}>
                <AlertTriangle className={`w-6 h-6 ${
                  heroAlert.severity === "critical" ? "text-rose-400" : "text-amber-400"
                }`} />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <StatusBadge
                    status={heroAlert.severity === "critical" ? "critical" : "high"}
                    label={heroAlert.severity === "critical" ? "CRITICAL" : "HIGH"}
                    pulse
                    size="sm"
                  />
                </div>
                <h2 className={`text-base font-bold ${
                  heroAlert.severity === "critical" ? "text-rose-300" : "text-amber-300"
                }`}>
                  {heroAlert.title || heroAlert.message?.slice(0, 60) || "Alert Triggered"}
                </h2>
                <p className={`text-sm mt-0.5 ${
                  heroAlert.severity === "critical" ? "text-rose-200/70" : "text-amber-200/70"
                }`}>
                  {heroAlert.message || heroAlert.description || "A threshold breach has been detected that may require attention."}
                </p>
              </div>
              <Link
                href="/farmer-daily"
                className={`ml-auto flex-shrink-0 px-4 py-2 rounded-xl text-sm font-semibold transition-colors ${
                  heroAlert.severity === "critical"
                    ? "bg-rose-500/20 text-rose-300 hover:bg-rose-500/30 border border-rose-500/30"
                    : "bg-amber-500/20 text-amber-300 hover:bg-amber-500/30 border border-amber-500/30"
                }`}
              >
                Take Action &rarr;
              </Link>
            </div>
          </div>
        ) : (
          <div className="rounded-2xl bg-emerald-500/[0.06] border border-emerald-500/15 p-4 mb-1">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-emerald-500/15 flex items-center justify-center flex-shrink-0">
                <CheckCircle2 className="w-5 h-5 text-emerald-400" />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-emerald-300">All Clear</h2>
                <p className="text-xs text-emerald-200/60">No critical alerts. Operations are running within normal parameters.</p>
              </div>
            </div>
          </div>
        )}
      </motion.div>
    </div>
  );
}
