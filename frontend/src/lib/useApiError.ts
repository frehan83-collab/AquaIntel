"use client";

import { useCallback } from "react";
import { useToast } from "@/components/Toast";
import { useTranslation } from "@/lib/i18n";

/**
 * API Error Handler Hook
 * =======================
 * Replaces silent .catch(() => {}) patterns with structured error handling.
 *
 * Usage:
 *   const handleError = useApiError();
 *   api.liceSummary().then(setData).catch(handleError("lice_summary"));
 *
 * - Logs the error context + details for developers (structlog-style)
 * - Optionally shows a user-facing toast for critical data
 * - Returns undefined so useState stays null (shows empty/loading state)
 */
export function useApiError() {
  const { addToast } = useToast();
  const { t } = useTranslation();

  /**
   * Create an error handler for a specific API context.
   * @param context - descriptive label for the API call (for logging)
   * @param options.silent - if true, suppress user-facing toast (default: true for non-critical)
   * @param options.critical - if true, show toast to user (for primary data that users notice)
   */
  const handleError = useCallback(
    (context: string, options?: { silent?: boolean; critical?: boolean }) => {
      return (err: unknown) => {
        const message = err instanceof Error ? err.message : String(err);

        // Developer-visible structured log (not console.log — structured for observability)
        if (typeof window !== "undefined" && process.env.NODE_ENV === "development") {
          // eslint-disable-next-line no-console
          console.warn(`[API:${context}]`, message);
        }

        // Show toast for critical data failures
        if (options?.critical) {
          addToast({
            type: "alert",
            title: t("error.data_unavailable"),
            message: `${context}: ${t("error.api_error")}`,
            duration: 5000,
          });
        }

        // Return undefined — useState stays null, empty state shows
        return undefined;
      };
    },
    [addToast, t]
  );

  return handleError;
}
