"use client";

import { useState, useEffect, useCallback } from "react";

/**
 * Density mode for UI compactness.
 * - "comfortable" (default): full padding, 44px row height — farmer persona
 * - "compact": reduced padding, 32px row height — trader persona with multiple dashboards
 *
 * Wired to CSS vars via `data-density` on <html>:
 *   --density-padding-sm, --density-padding-md, --density-padding-lg, --density-row-height
 */
export type Density = "comfortable" | "compact";

const STORAGE_KEY = "oc_density";

function getInitialDensity(): Density {
  if (typeof window === "undefined") return "comfortable";
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "compact" || stored === "comfortable") return stored;
  return "comfortable";
}

function applyDensity(density: Density) {
  document.documentElement.setAttribute("data-density", density);
}

export function useDensity() {
  const [density, setDensity] = useState<Density>("comfortable");

  useEffect(() => {
    const initial = getInitialDensity();
    setDensity(initial);
    applyDensity(initial);
  }, []);

  const toggleDensity = useCallback(() => {
    setDensity((prev) => {
      const next: Density = prev === "comfortable" ? "compact" : "comfortable";
      localStorage.setItem(STORAGE_KEY, next);
      applyDensity(next);
      return next;
    });
  }, []);

  return { density, toggleDensity } as const;
}
