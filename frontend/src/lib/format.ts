"use client";

/**
 * Locale-aware formatting utilities for AquaIntelligence.
 * Norwegian: 1 234,50 / 06.04.2026 / NOK 92,50
 * English:   1,234.50 / Apr 6, 2026 / NOK 92.50
 */

export type Locale = "en" | "no";

const localeMap: Record<Locale, string> = { en: "en-US", no: "nb-NO" };

/** Format a date in locale-appropriate style */
export function formatDate(date: Date | string, locale: Locale): string {
  const d = typeof date === "string" ? new Date(date) : date;
  if (isNaN(d.getTime())) return String(date);
  return d.toLocaleDateString(localeMap[locale], {
    day: "numeric", month: "short", year: "numeric",
  });
}

/** Format a number with locale-appropriate thousand separators and decimals */
export function formatNumber(n: number, locale: Locale, decimals = 0): string {
  if (n == null || !isFinite(n)) return "\u2014";
  return n.toLocaleString(localeMap[locale], {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

/** Format a currency value (NOK by default) */
export function formatCurrency(n: number, locale: Locale, currency = "NOK"): string {
  if (n == null || !isFinite(n)) return "\u2014";
  return n.toLocaleString(localeMap[locale], {
    style: "currency", currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}
