import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatNOK(value: number): string {
  if (Math.abs(value) >= 1_000_000_000) return `${(value / 1e9).toFixed(1)}B`;
  if (Math.abs(value) >= 1_000_000) return `${(value / 1e6).toFixed(0)}M`;
  if (Math.abs(value) >= 1_000) return `${(value / 1e3).toFixed(0)}K`;
  return value.toFixed(0);
}
