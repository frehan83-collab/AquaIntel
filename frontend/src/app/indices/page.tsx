"use client";
/**
 * Public indices page — AI-STI (AI-LPI v1.0 withdrawn) + the Bio→Price Weekly digest, driven
 * entirely by /api/indices. Shows the method version, component contributions and
 * a provenance badge, so a reader can see why a number is what it is.
 */
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { AlertTriangle, Info } from "lucide-react";
import GlassCard from "@/components/GlassCard";
import { api } from "@/lib/api";
import { useApiError } from "@/lib/useApiError";
import type { BioPriceWeekly, IndicesResponse, IndexResult } from "@/types/api";

const BAND_COLOR: Record<string, string> = {
  severe: "text-rose-400",
  elevated: "text-amber-400",
  moderate: "text-ocean-400",
  low: "text-emerald-400",
  minimal: "text-emerald-400",
};

function IndexCard({ result }: { result: IndexResult }) {
  const withdrawn = result.status === "withdrawn";
  const degraded = !result.provenance?.is_live;
  return (
    <GlassCard accent={degraded ? "amber" : "ocean"}>
      <div className="flex items-baseline justify-between">
        <div>
          <h3 className="text-base font-semibold text-[var(--text-primary)]">
            {result.index}
          </h3>
          <p className="text-[11px] text-[var(--text-secondary)]">{result.name}</p>
        </div>
        <div className="text-right">
          <div className={`text-2xl font-semibold ${BAND_COLOR[result.band ?? ""] ?? ""}`}>
            {result.value === null ? "—" : result.value.toFixed(1)}
          </div>
          <div className="text-[11px] text-[var(--text-secondary)]">
            {withdrawn ? "withdrawn" : result.band ?? "unavailable"} · {result.week}
          </div>
        </div>
      </div>

      <table className="w-full mt-3 text-[11px]">
        <thead>
          <tr className="text-white/40">
            <th className="text-left font-normal">Component</th>
            <th className="text-right font-normal">Wt</th>
            <th className="text-right font-normal">Score</th>
            <th className="text-right font-normal">Source</th>
          </tr>
        </thead>
        <tbody>
          {result.components.map((c) => (
            <tr key={c.name} className={c.used ? "" : "opacity-50"}>
              <td className="text-[var(--text-secondary)]">{c.name}</td>
              <td className="text-right text-[var(--text-secondary)]">
                {Math.round(c.weight * 100)}%
              </td>
              <td className="text-right text-[var(--text-primary)]">
                {c.used ? c.score.toFixed(0) : "n/a"}
              </td>
              <td className="text-right text-[var(--text-secondary)] truncate max-w-[9rem]">
                {c.source}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="mt-3 flex items-center gap-2 text-[10px]">
        <span className="px-1.5 py-0.5 rounded bg-white/5 text-white/50">
          method v{withdrawn ? result.withdrawn?.version ?? result.version : result.version}
        </span>
        <span
          className={`px-1.5 py-0.5 rounded ${
            degraded
              ? "bg-amber-500/10 text-amber-400"
              : "bg-emerald-500/10 text-emerald-400"
          }`}
        >
          {withdrawn ? "withdrawn" : degraded ? "degraded" : "live"}
        </span>
        <span className="text-white/40">
          {result.components_used}/{result.components.length} components
        </span>
      </div>
      {degraded && result.provenance?.fallback_reason && (
        <p className="mt-2 text-[10px] text-amber-400">
          {result.provenance.fallback_reason}
        </p>
      )}
    </GlassCard>
  );
}


export default function IndicesPage() {
  const handleError = useApiError();
  const [data, setData] = useState<IndicesResponse | null>(null);
  const [weekly, setWeekly] = useState<BioPriceWeekly | null>(null);

  useEffect(() => {
    api.indices().then(setData).catch(handleError("indices"));
    api.bioPriceWeekly().then(setWeekly).catch(handleError("bio_price_weekly"));
  }, [handleError]);

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-2xl font-semibold text-[var(--text-primary)]">Indices</h1>
        <p className="text-sm text-[var(--text-secondary)] mt-1">
          Published, versioned indicators. Every value carries its method version,
          component contributions and provenance.
        </p>
      </motion.div>

      {weekly && (
        <GlassCard accent="emerald" delay={0.05}>
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">
            Bio→Price Weekly · {weekly.week}
          </h2>
          <p className="text-xs text-[var(--text-secondary)] mt-1">{weekly.headline}</p>
          <div className="mt-2 flex items-center gap-2 text-[10px] text-white/40">
            <span className="px-1.5 py-0.5 rounded bg-white/5">
              read: {weekly.transmission.read}
            </span>
            <span className="px-1.5 py-0.5 rounded bg-white/5">
              report v{weekly.version}
            </span>
          </div>
          {weekly.caveats.length > 0 && (
            <ul className="mt-2 space-y-1">
              {weekly.caveats.map((c) => (
                <li key={c} className="flex items-start gap-1.5 text-[10px] text-amber-400">
                  <AlertTriangle className="w-3 h-3 mt-0.5 shrink-0" />
                  <span>{c}</span>
                </li>
              ))}
            </ul>
          )}
        </GlassCard>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
        {Object.values(data?.indices ?? {}).map((r) => (
          <IndexCard key={r.index} result={r} />
        ))}
      </div>

      <p className="mt-4 flex items-start gap-1.5 text-[10px] text-white/40">
        <Info className="w-3 h-3 mt-0.5 shrink-0" />
        <span>
          Method v{data?.method_version ?? "?"} — reproducible from{" "}
          {data?.methodology_url ?? "/api/indices/methodology"}. Index output, not
          investment advice.
        </span>
      </p>
    </div>
  );
}
