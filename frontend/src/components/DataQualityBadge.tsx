"use client";

type Quality = "live" | "degraded" | "simulated" | "synthetic";

export interface DataProvenanceDTO {
  source: string;
  is_live: boolean;
  freshness: string;
  confidence: number;
  fallback_reason?: string | null;
}

interface Props {
  quality?: Quality;
  source?: string;
  reason?: string;
  provenance?: DataProvenanceDTO | null;
}

function qualityFromProvenance(p: DataProvenanceDTO): Quality {
  if (p.confidence >= 0.7 && p.is_live) return "live";
  if (p.confidence >= 0.4) return "degraded";
  if (p.source === "simulated") return "simulated";
  return "synthetic";
}

export default function DataQualityBadge({ quality, source, reason, provenance }: Props) {
  const q = provenance ? qualityFromProvenance(provenance) : (quality ?? "degraded");
  const src = provenance?.source ?? source;
  const note = provenance?.fallback_reason ?? reason;
  const conf = provenance ? `${Math.round(provenance.confidence * 100)}%` : null;

  const config = {
    live: { color: "bg-emerald-500", label: "Live", ring: "ring-emerald-500/30" },
    degraded: { color: "bg-amber-500", label: "Degraded", ring: "ring-amber-500/30" },
    simulated: { color: "bg-rose-500", label: "Simulated", ring: "ring-rose-500/30" },
    synthetic: { color: "bg-violet-500", label: "Synthetic", ring: "ring-violet-500/30" },
  };
  const c = config[q];

  return (
    <div className="group relative inline-flex items-center gap-1.5">
      <span className={`w-2 h-2 rounded-full ${c.color} ring-2 ${c.ring}`} />
      <span className="text-[10px] text-[var(--text-secondary)]">
        {c.label}{conf && ` · ${conf}`}
      </span>
      {(src || note) && (
        <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block z-50 w-56 p-2 rounded-md bg-[var(--surface-3)] border border-white/[0.1] text-[10px] text-[var(--text-secondary)] shadow-lg">
          {src && <div className="mb-0.5">Source: {src}</div>}
          {conf && <div className="mb-0.5">Confidence: {conf}</div>}
          {provenance?.freshness && (
            <div className="mb-0.5" suppressHydrationWarning>Updated: {new Date(provenance.freshness).toLocaleString()}</div>
          )}
          {note && <div className="text-amber-400/80">Note: {note}</div>}
        </div>
      )}
    </div>
  );
}
