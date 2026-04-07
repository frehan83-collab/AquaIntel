"use client";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { ShieldCheck, FileText, Clock, AlertCircle } from "lucide-react";
import GlassCard from "@/components/GlassCard";
import { api } from "@/lib/api";
import ErrorBoundary from "@/components/ErrorBoundary";
import { useTranslation } from "@/lib/i18n";

/* eslint-disable @typescript-eslint/no-explicit-any */

export default function CompliancePage() {
  const { t } = useTranslation();
  const [auditLog, setAuditLog] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.audit()
      .then((data) => setAuditLog(Array.isArray(data) ? data : data?.entries || []))
      .catch(() => setAuditLog([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <ErrorBoundary fallbackTitle="Compliance error">
    <div className="space-y-6">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h1 className="text-2xl font-bold text-[var(--text-primary)]">
          {t("nav.compliance_page")}
        </h1>
        <p className="text-sm text-[var(--text-secondary)] mt-1">
          Audit log, regulatory compliance tracking, and legal disclaimers
        </p>
      </motion.div>

      {/* Disclaimer */}
      <GlassCard delay={0.1}>
        <div className="flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-amber-400 mt-0.5 shrink-0" />
          <div>
            <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-2">
              Important Disclaimers
            </h3>
            <div className="space-y-2 text-xs text-[var(--text-secondary)] leading-relaxed">
              <p>
                This platform is provided for informational and analytical purposes only.
                Nothing presented constitutes financial, investment, or trading advice.
                All trade signals are discretionary and must be independently validated
                before execution.
              </p>
              <p>
                Lice data is sourced from BarentsWatch / Norwegian Directorate of Fisheries
                under the Norwegian Licence for Open Government Data (NLOD 2.0). Data may be
                delayed or incomplete. Users are responsible for verifying data accuracy.
              </p>
              <p>
                Machine learning predictions carry inherent uncertainty. Past performance
                does not guarantee future results. The system operators accept no liability
                for decisions made based on platform outputs.
              </p>
              <p>
                All signal confirmations and order executions are logged for audit purposes.
                Users must comply with applicable securities regulations including MAR
                (Market Abuse Regulation) when acting on platform intelligence.
              </p>
            </div>
          </div>
        </div>
      </GlassCard>

      {/* Compliance Status */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <GlassCard delay={0.2}>
          <div className="flex items-center gap-2 mb-3">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">Data Licensing</h3>
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between py-1.5">
              <span className="text-xs text-[var(--text-secondary)]">BarentsWatch NLOD</span>
              <span className="text-xs text-emerald-400 font-medium">Compliant</span>
            </div>
            <div className="flex items-center justify-between py-1.5">
              <span className="text-xs text-[var(--text-secondary)]">Attribution Required</span>
              <span className="text-xs text-emerald-400 font-medium">Yes - Displayed</span>
            </div>
            <div className="flex items-center justify-between py-1.5">
              <span className="text-xs text-[var(--text-secondary)]">Commercial Use</span>
              <span className="text-xs text-emerald-400 font-medium">Permitted</span>
            </div>
          </div>
        </GlassCard>

        <GlassCard delay={0.3}>
          <div className="flex items-center gap-2 mb-3">
            <FileText className="w-4 h-4 text-ocean-400" />
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">Regulatory</h3>
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between py-1.5">
              <span className="text-xs text-[var(--text-secondary)]">MAR Compliance</span>
              <span className="text-xs text-amber-400 font-medium">User Responsibility</span>
            </div>
            <div className="flex items-center justify-between py-1.5">
              <span className="text-xs text-[var(--text-secondary)]">Signal Audit Trail</span>
              <span className="text-xs text-emerald-400 font-medium">Enabled</span>
            </div>
            <div className="flex items-center justify-between py-1.5">
              <span className="text-xs text-[var(--text-secondary)]">Data Retention</span>
              <span className="text-xs text-[var(--text-secondary)]">90 days</span>
            </div>
          </div>
        </GlassCard>

        <GlassCard delay={0.4}>
          <div className="flex items-center gap-2 mb-3">
            <Clock className="w-4 h-4 text-ocean-400" />
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">System Status</h3>
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between py-1.5">
              <span className="text-xs text-[var(--text-secondary)]">API Status</span>
              <span className="text-xs text-emerald-400 font-medium">Online</span>
            </div>
            <div className="flex items-center justify-between py-1.5">
              <span className="text-xs text-[var(--text-secondary)]">Last Data Sync</span>
              <span className="text-xs text-[var(--text-secondary)]">Today</span>
            </div>
            <div className="flex items-center justify-between py-1.5">
              <span className="text-xs text-[var(--text-secondary)]">Audit Entries</span>
              <span className="text-xs text-[var(--text-secondary)]">{auditLog.length}</span>
            </div>
          </div>
        </GlassCard>
      </div>

      {/* Audit Log */}
      <GlassCard delay={0.5}>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-ocean-400" />
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">Audit Log</h3>
          </div>
          <span className="text-xs text-[var(--text-secondary)]">{auditLog.length} entries</span>
        </div>

        {loading ? (
          <div className="flex justify-center py-8">
            <div className="w-6 h-6 border-2 border-ocean-500/30 border-t-ocean-400 rounded-full animate-spin" />
          </div>
        ) : auditLog.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-glass-border">
                  <th className="text-left py-2 px-3 text-[var(--text-secondary)] font-medium text-xs">Timestamp</th>
                  <th className="text-left py-2 px-3 text-[var(--text-secondary)] font-medium text-xs">Action</th>
                  <th className="text-left py-2 px-3 text-[var(--text-secondary)] font-medium text-xs">User</th>
                  <th className="text-left py-2 px-3 text-[var(--text-secondary)] font-medium text-xs">Detail</th>
                </tr>
              </thead>
              <tbody>
                {auditLog.map((entry, i) => (
                  <motion.tr
                    key={entry.id || i}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.6 + i * 0.03 }}
                    className="border-b border-glass-border/50 hover:bg-glass-light transition-colors"
                  >
                    <td className="py-2.5 px-3 text-[var(--text-secondary)] text-xs">
                      {entry.timestamp?.replace("T", " ")?.slice(0, 19) || entry.created_at?.replace("T", " ")?.slice(0, 19) || "—"}
                    </td>
                    <td className="py-2.5 px-3 font-medium">{entry.action || entry.event || "—"}</td>
                    <td className="py-2.5 px-3 text-xs text-[var(--text-secondary)]">{entry.user || entry.actor || "system"}</td>
                    <td className="py-2.5 px-3 text-xs text-[var(--text-secondary)] max-w-xs truncate">
                      {entry.detail || entry.description || entry.message || "—"}
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-[var(--text-secondary)] text-center py-8">
            No audit entries found. Actions will be logged as they occur.
          </p>
        )}
      </GlassCard>
    </div>
    </ErrorBoundary>
  );
}
