"use client";

import { useEffect } from "react";
import { Heart, RefreshCw } from "lucide-react";

export default function WelfareError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    if (process.env.NODE_ENV === "development") {
      // eslint-disable-next-line no-console
      console.warn("[welfare:error]", error.message);
    }
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <Heart className="w-12 h-12 text-rose-400/50 mb-4" />
      <h2 className="text-lg font-semibold text-[var(--text-primary)] mb-2">
        Welfare Dashboard Error
      </h2>
      <p className="text-sm text-[var(--text-secondary)] mb-6 max-w-md">
        Something went wrong loading the welfare dashboard. This may be a temporary issue with data sources.
      </p>
      <button
        onClick={reset}
        className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg bg-salmon/10 text-salmon hover:bg-salmon/20 transition-colors"
      >
        <RefreshCw className="w-4 h-4" />
        Try Again
      </button>
    </div>
  );
}
