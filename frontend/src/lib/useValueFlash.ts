"use client";

import { useRef, useState, useEffect } from "react";

/**
 * Hook that returns `true` for 600ms when the tracked value changes.
 * Used to trigger CSS flash animations on KPI cards when data refreshes.
 */
export function useValueFlash(value: number | string | null | undefined): boolean {
  const prevRef = useRef(value);
  const [flash, setFlash] = useState(false);

  useEffect(() => {
    if (prevRef.current !== value && prevRef.current != null && value != null) {
      setFlash(true);
      const timer = setTimeout(() => setFlash(false), 600);
      prevRef.current = value;
      return () => clearTimeout(timer);
    }
    prevRef.current = value;
  }, [value]);

  return flash;
}
