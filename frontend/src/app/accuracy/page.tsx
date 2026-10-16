"use client";
/**
 * Public Accuracy & Method page. It shows artifact-backed metrics only: when no
 * artifact exists it says so and names the command that produces one. The
 * fallback disclosure is part of the product, not fine print.
 */
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { AlertTriangle, CheckCircle2, Info, ShieldQuestion } from "lucide-react";
import GlassCard from "@/components/GlassCard";
import { api } from "@/lib/api";
import { useApiError } from "@/lib/useApiError";
import type { AccuracySummary } from "@/types/api";

export default function AccuracyPage() {
  const handleError = useApiError();
  const [data, setData] = useState<AccuracySummary | null>(null);

  useEffect(() => {
    api.accuracy().then(setData).catch(handleError("accuracy"));
  }, [handleError]);

  const disclosure = data?.fallback_disclosure ?? {};
  const modelsAvailable = disclosure["foundation_models_available"] as
    | boolean
    | undefined;

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-2xl font-semibold text-[var(--text-primary)]">
          Accuracy &amp; Method
        </h1>
        <p className="text-sm text-[var(--text-secondary)] mt-1">
          Every figure here was produced by a real walk-forward evaluation and is
          stored as a versioned artifact. Nothing is estimated or illustrative.
        </p>
      </motion.div>

      <GlassCard accent={data?.published ? "emerald" : "amber"} delay={0.05}>
        <div className="flex items-start gap-2">
          {data?.published ? (
            <CheckCircle2 className="w-4 h-4 mt-0.5 text-emerald-400 shrink-0" />
          ) : (
            <ShieldQuestion className="w-4 h-4 mt-0.5 text-amber-400 shrink-0" />
          )}
          <div>
            <p className="text-xs text-[var(--text-primary)]">{data?.statement}</p>
            {!data?.published && (
              <p className="mt-1 font-mono text-[10px] text-[var(--text-secondary)]">
                {data?.how_to_publish}
              </p>
            )}
          </div>
        </div>
      </GlassCard>

      {data && data.metrics.length > 0 && (
        <GlassCard accent="ocean" delay={0.1}>
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">
            Published metrics
          </h2>
          <table className="w-full mt-2 text-[11px]">
            <thead>
              <tr className="text-white/40">
                <th className="text-left font-normal">Model</th>
                <th className="text-left font-normal">Target</th>
                <th className="text-right font-normal">MAPE</th>
                <th className="text-right font-normal">Coverage</th>
                <th className="text-right font-normal">n</th>
                <th className="text-right font-normal">Fallback</th>
              </tr>
            </thead>
            <tbody>
              {data.metrics.map((m) => (
                <tr key={m.artifact_id}>
                  <td className="text-[var(--text-primary)]">{m.model}</td>
                  <td className="text-[var(--text-secondary)]">{m.target}</td>
                  <td className="text-right text-[var(--text-primary)]">
                    {m.mape_pct.toFixed(2)}%
                  </td>
                  <td className="text-right text-[var(--text-secondary)]">
                    {m.coverage_pct === null ? "—" : `${m.coverage_pct}%`}
                  </td>
                  <td className="text-right text-[var(--text-secondary)]">{m.n_obs}</td>
                  <td className="text-right text-[var(--text-secondary)]">
                    {m.fallback_used ? "yes" : "no"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-[10px] text-white/40">
            {data.metrics.length} artifact(s) · schema v{data.schema_version} ·{" "}
            {data.fallback_used_count} measured on the honest fallback
          </p>
        </GlassCard>
      )}

      <GlassCard accent="violet" delay={0.15}>
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">
          Fallback disclosure
        </h2>
        <p className="text-xs text-[var(--text-secondary)] mt-1">
          {String(disclosure["policy"] ?? "")}
        </p>
        <div className="mt-2 flex flex-wrap gap-2 text-[10px]">
          <span className="px-1.5 py-0.5 rounded bg-white/5 text-white/50">
            foundation models: {modelsAvailable === undefined ? "?" : modelsAvailable ? "available" : "unavailable"}
          </span>
          <span className="px-1.5 py-0.5 rounded bg-white/5 text-white/50">
            legacy data/ artifact:{" "}
            {String(disclosure["legacy_backtest_artifact_present"] ?? "?")}
          </span>
        </div>
        {modelsAvailable === false && (
          <p className="mt-2 flex items-start gap-1.5 text-[10px] text-amber-400">
            <AlertTriangle className="w-3 h-3 mt-0.5 shrink-0" />
            <span>{String(disclosure["foundation_models_note"] ?? "")}</span>
          </p>
        )}
      </GlassCard>

      <p className="mt-4 flex items-start gap-1.5 text-[10px] text-white/40">
        <Info className="w-3 h-3 mt-0.5 shrink-0" />
        <span>
          Contract and evaluation protocol:{" "}
          {data?.methodology_url ?? "/api/accuracy/method"} — walk-forward, with
          prediction intervals calibrated in-sample and coverage measured
          out-of-sample.
        </span>
      </p>
    </div>
  );
}
