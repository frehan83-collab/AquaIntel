"use client";
import { useState, useEffect, useRef } from "react";

/**
 * Hook that animates a number from 0 to the target value.
 * Used on KPI cards for a premium "counting up" effect on load.
 *
 * @param target - The final number to count to
 * @param duration - Animation duration in ms (default 800)
 * @param decimals - Number of decimal places (default 0)
 * @returns The current animated value
 */
export function useCountUp(target: number, duration = 800, decimals = 0): number {
  const [value, setValue] = useState(0);
  const prevTarget = useRef(target);
  const frameRef = useRef<number>(0);

  useEffect(() => {
    if (target == null || !isFinite(target)) {
      setValue(target);
      return;
    }

    const startValue = prevTarget.current !== target ? value : 0;
    prevTarget.current = target;
    const startTime = performance.now();

    function animate(now: number) {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // Ease out cubic for smooth deceleration
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = startValue + (target - startValue) * eased;
      setValue(Number(current.toFixed(decimals)));

      if (progress < 1) {
        frameRef.current = requestAnimationFrame(animate);
      }
    }

    frameRef.current = requestAnimationFrame(animate);
    return () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
    };
  }, [target, duration, decimals]);

  return value;
}
