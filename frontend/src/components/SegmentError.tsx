"use client";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { useTranslation } from "@/lib/i18n";

interface Props {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function SegmentError({ error, reset }: Props) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4">
      <div className="w-16 h-16 rounded-2xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center mb-4">
        <AlertTriangle className="w-8 h-8 text-rose-400" />
      </div>
      <h3 className="text-lg font-semibold text-[var(--text-primary)] mb-2">
        {t("error.segment_title")}
      </h3>
      <p className="text-sm text-[var(--text-secondary)] mb-4 text-center max-w-md">
        {t("error.segment_message")}
      </p>
      {process.env.NODE_ENV === "development" && (
        <p className="text-xs text-rose-400/60 mb-4 font-mono max-w-lg text-center break-all">
          {error.message}
        </p>
      )}
      <button
        onClick={reset}
        className="flex items-center gap-2 px-4 py-2 rounded-xl bg-ocean-500/10 border border-ocean-500/20 text-ocean-400 text-sm hover:bg-ocean-500/20 transition-colors"
      >
        <RefreshCw className="w-4 h-4" /> {t("error.try_again")}
      </button>
    </div>
  );
}
