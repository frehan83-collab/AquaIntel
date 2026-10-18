"use client";

/**
 * Source attribution, required by the licences of the data the platform displays.
 *
 * WS-31 (2026-10-18): added Norges Bank (the official FX source), FRED with the notice
 * its API terms require, and Mattilsynet (disease cases). Yahoo Finance is deliberately
 * absent: its terms forbid deriving income from the data, so the platform no longer
 * uses it for currency conversion; remaining Yahoo equity/commodity quotes are a known
 * open item (docs/HANDOVER.md WS-31) and not something to advertise.
 */
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
        <span className="opacity-30">(EU, attribution)</span>
        {" \u00B7 "}
        <span className="text-[var(--text-secondary)]/70">MET.no</span>{" "}
        <span className="opacity-30">(CC BY 4.0)</span>
        {" \u00B7 "}
        <span className="text-[var(--text-secondary)]/70">Fiskeridirektoratet</span>{" "}
        <span className="opacity-30">(NLOD)</span>
        {" \u00B7 "}
        <span className="text-[var(--text-secondary)]/70">Mattilsynet</span>
        {" \u00B7 "}
        <span className="text-[var(--text-secondary)]/70">Norges Bank</span>{" "}
        <span className="opacity-30">(official NOK rates)</span>
        {" \u00B7 "}
        <span className="text-[var(--text-secondary)]/70">DFO Canada</span>{" "}
        <span className="opacity-30">(OGL)</span>
      </p>
      <p className="text-[9px] text-[var(--text-secondary)] opacity-40 text-center mt-1">
        This product uses the FRED&reg; API but is not endorsed or certified by the
        Federal Reserve Bank of St. Louis. Copernicus data is used under its attribution
        terms; MET Norway data under CC BY 4.0; BarentsWatch and Fiskeridirektoratet
        under NLOD. Figures are dated where the source dates them.
      </p>
    </div>
  );
}
