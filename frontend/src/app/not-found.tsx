import Link from "next/link";
import { Anchor, Home, Waves } from "lucide-react";
import GlassCard from "@/components/GlassCard";

export default function NotFound() {
  return (
    <div className="flex items-center justify-center min-h-[70vh] px-4">
      <GlassCard className="max-w-lg w-full text-center" accent="ocean">
        {/* Decorative wave SVG */}
        <div className="flex justify-center mb-6 opacity-30">
          <svg viewBox="0 0 200 40" className="w-48 h-10 text-ocean-400">
            <path
              d="M0 20 Q25 5 50 20 T100 20 T150 20 T200 20"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
            />
            <path
              d="M0 28 Q30 15 60 28 T120 28 T180 28 T200 28"
              fill="none"
              stroke="currentColor"
              strokeWidth="0.8"
              opacity="0.5"
            />
          </svg>
        </div>

        {/* Anchor icon */}
        <div className="flex justify-center mb-4">
          <div className="w-16 h-16 rounded-full bg-ocean-500/10 border border-ocean-500/20 flex items-center justify-center">
            <Anchor className="w-8 h-8 text-ocean-400" />
          </div>
        </div>

        {/* 404 heading */}
        <h1 className="text-5xl font-display text-[var(--text-primary)] mb-2">404</h1>
        <h2 className="text-lg font-display text-salmon/80 mb-3">Lost at Sea</h2>
        <p className="text-sm text-[var(--text-secondary)] mb-8 leading-relaxed max-w-sm mx-auto">
          The page you are looking for has drifted beyond our charts.
          It may have been moved, removed, or never existed in these waters.
        </p>

        {/* Navigation links */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
          <Link
            href="/"
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-salmon/10 border border-salmon/20 text-salmon hover:bg-salmon/20 transition-colors text-sm font-medium"
          >
            <Home className="w-4 h-4" />
            Back to Dashboard
          </Link>
          <Link
            href="/brief"
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-white/[0.04] border border-white/[0.08] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-white/[0.06] transition-colors text-sm font-medium"
          >
            <Waves className="w-4 h-4" />
            Morning Brief
          </Link>
        </div>

        {/* Bottom attribution */}
        <p className="mt-8 text-[10px] text-[var(--text-secondary)] opacity-40">
          FishIntel -- Aquaculture Intelligence
        </p>
      </GlassCard>
    </div>
  );
}
