"use client";
import { useSearchParams, useRouter, usePathname } from "next/navigation";
import { useCallback, useMemo, useRef } from "react";

/**
 * Syncs React state with URL query parameters, making filtered views bookmarkable.
 *
 * Reads initial values from URL search params on mount.
 * Updates URL params (via router.replace, shallow) when state changes.
 * Supports string, number, and boolean value types (inferred from defaults).
 *
 * Usage:
 *   const [filters, setFilters] = useQueryParams({ search: "", sort: "rank", pa: 0, active: true });
 *   setFilters({ search: "mowi" }); // partial updates OK
 */
export function useQueryParams<T extends Record<string, string | number | boolean>>(
  defaults: T,
): [T, (updates: Partial<T>) => void] {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  // Keep a stable reference to defaults to avoid re-renders
  const defaultsRef = useRef(defaults);

  // Parse current URL params into typed values based on defaults
  const currentValues = useMemo(() => {
    const result = { ...defaultsRef.current };
    for (const key of Object.keys(defaultsRef.current)) {
      const raw = searchParams.get(key);
      if (raw === null) continue;

      const defaultVal = defaultsRef.current[key];
      if (typeof defaultVal === "number") {
        const parsed = Number(raw);
        if (!isNaN(parsed)) {
          (result as Record<string, string | number | boolean>)[key] = parsed;
        }
      } else if (typeof defaultVal === "boolean") {
        (result as Record<string, string | number | boolean>)[key] = raw === "true";
      } else {
        (result as Record<string, string | number | boolean>)[key] = raw;
      }
    }
    return result;
  }, [searchParams]);

  // Update URL params; only includes non-default values to keep URLs clean
  const setValues = useCallback(
    (updates: Partial<T>) => {
      const merged = { ...currentValues, ...updates };
      const params = new URLSearchParams();

      for (const key of Object.keys(defaultsRef.current)) {
        const val = merged[key];
        const def = defaultsRef.current[key];
        // Only serialize non-default values to keep URLs clean
        if (val !== def) {
          params.set(key, String(val));
        }
      }

      const qs = params.toString();
      const url = qs ? `${pathname}?${qs}` : pathname;
      router.replace(url, { scroll: false });
    },
    [currentValues, pathname, router],
  );

  return [currentValues as T, setValues];
}
