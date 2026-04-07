"use client";

export default function DataAttribution() {
  return (
    <div className="w-full border-t border-white/[0.04] bg-fjord-abyss/30 px-6 py-2.5">
      <p className="text-[10px] text-[var(--text-secondary)] opacity-50 text-center tracking-wide">
        Data sources:{" "}
        <span className="text-[var(--text-secondary)]/70">BarentsWatch</span>{" "}
        <span className="opacity-30">(NLOD)</span>
        {" \u00B7 "}
        <span className="text-[var(--text-secondary)]/70">SSB</span>{" "}
        <span className="opacity-30">(CC BY 4.0)</span>
        {" \u00B7 "}
        <span className="text-[var(--text-secondary)]/70">Copernicus Marine</span>{" "}
        <span className="opacity-30">(EU)</span>
        {" \u00B7 "}
        <span className="text-[var(--text-secondary)]/70">MET.no</span>{" "}
        <span className="opacity-30">(CC BY 4.0)</span>
        {" \u00B7 "}
        <span className="text-[var(--text-secondary)]/70">Fiskeridirektoratet</span>{" "}
        <span className="opacity-30">(NLOD)</span>
        {" \u00B7 "}
        <span className="text-[var(--text-secondary)]/70">DFO Canada</span>{" "}
        <span className="opacity-30">(OGL)</span>
      </p>
    </div>
  );
}
