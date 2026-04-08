"use client";
import { useEffect } from "react";

/**
 * Catches unhandled promise rejections and global errors.
 * Logs structured context in dev, suppresses noise in prod.
 */
export default function GlobalErrorHandler() {
  useEffect(() => {
    const onUnhandledRejection = (e: PromiseRejectionEvent) => {
      if (process.env.NODE_ENV === "development") {
        console.warn("[GlobalErrorHandler] Unhandled rejection:", e.reason);
      }
      // Prevent default browser error logging for known API errors
      if (e.reason instanceof Error && e.reason.message.startsWith("API ")) {
        e.preventDefault();
      }
    };

    const onError = (e: ErrorEvent) => {
      if (process.env.NODE_ENV === "development") {
        console.warn("[GlobalErrorHandler] Uncaught error:", e.message);
      }
    };

    window.addEventListener("unhandledrejection", onUnhandledRejection);
    window.addEventListener("error", onError);
    return () => {
      window.removeEventListener("unhandledrejection", onUnhandledRejection);
      window.removeEventListener("error", onError);
    };
  }, []);

  return null;
}
