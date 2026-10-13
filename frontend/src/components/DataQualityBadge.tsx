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
    live: { color: "bg-[var(--success)]", label: "Live", ring: "ring-[var(--success)]/30" },
    degraded: { color: "bg-[var(--warning)]", label: "Degraded", ring: "ring-[var(--warning)]/30" },
    simulated: { color: "bg-[var(--danger)]", label: "Simulated", ring: "ring-[var(--danger)]/30" },
    synthetic: { color: "bg-violet-500", label: "Synthetic", ring: "ring-violet-500/30" },
  };
  const c = config[q];
  const ariaLabel = `${c.label} data${conf ? `, ${conf} confidence` : ""}${src ? `, source: ${src}` : ""}${note ? `, note: ${note}` : ""}`;

  return (
    <span
      className="group relative inline-flex items-center gap-1.5"
      role="img"
      aria-label={ariaLabel}
      title={ariaLabel}
      tabIndex={0}
    >
      <span className={`w-2 h-2 rounded-full ${c.color} ring-2 ${c.ring}`} aria-hidden="true" />
      <span className="text-[10px] text-[var(--text-secondary)]">
        {c.label}{conf && ` · ${conf}`}
      </span>
      {(src || note) && (
        <span className="absolute bottom-full left-0 mb-1 hidden group-hover:block group-focus-within:block z-50 w-56 p-2 rounded-md bg-[var(--surface-3)] border border-white/[0.1] text-[10px] text-[var(--text-secondary)] shadow-lg">
          {src && <span className="block mb-0.5">Source: {src}</span>}
          {conf && <span className="block mb-0.5">Confidence: {conf}</span>}
          {provenance?.freshness && (
            <span className="block mb-0.5" suppressHydrationWarning>Updated: {new Date(provenance.freshness).toLocaleString()}</span>
          )}
          {note && <span className="block text-amber-400/80">Note: {note}</span>}
        </span>
      )}
    </span>
  );
}
