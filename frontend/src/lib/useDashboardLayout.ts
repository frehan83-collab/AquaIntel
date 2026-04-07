"use client";
import { useState, useCallback, useEffect } from "react";

export interface WidgetConfig {
  id: string;
  label: string;
  visible: boolean;
}

const STORAGE_KEY = "oc_dashboard_layout";

const DEFAULT_WIDGETS: WidgetConfig[] = [
  { id: "hero-alert", label: "Hero Alert Zone", visible: true },
  { id: "kpi-strip", label: "Key Metrics", visible: true },
  { id: "intelligence", label: "Live Intelligence", visible: true },
  { id: "lice-chart", label: "Lice Chart & Export Volume", visible: true },
  { id: "signals", label: "Recent Signals", visible: true },
  { id: "detail-cards", label: "Regime / Pairs / AIS / Production", visible: true },
  { id: "disclaimer", label: "Data Disclaimer", visible: true },
];

function loadLayout(): WidgetConfig[] {
  if (typeof window === "undefined") return DEFAULT_WIDGETS;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_WIDGETS;
    const saved: WidgetConfig[] = JSON.parse(raw);
    // Merge: keep saved order/visibility, add any new default widgets not in saved
    const savedIds = new Set(saved.map((w) => w.id));
    const merged = saved.filter((w) => DEFAULT_WIDGETS.some((d) => d.id === w.id));
    for (const dw of DEFAULT_WIDGETS) {
      if (!savedIds.has(dw.id)) merged.push({ ...dw });
    }
    return merged;
  } catch {
    return DEFAULT_WIDGETS;
  }
}

function saveLayout(widgets: WidgetConfig[]) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(widgets));
  } catch {
    // quota exceeded — ignore
  }
}

export function useDashboardLayout() {
  const [widgets, setWidgets] = useState<WidgetConfig[]>(DEFAULT_WIDGETS);

  // Load from localStorage on mount (client only)
  useEffect(() => {
    setWidgets(loadLayout());
  }, []);

  const moveWidget = useCallback((id: string, direction: "up" | "down") => {
    setWidgets((prev) => {
      const idx = prev.findIndex((w) => w.id === id);
      if (idx < 0) return prev;
      const targetIdx = direction === "up" ? idx - 1 : idx + 1;
      if (targetIdx < 0 || targetIdx >= prev.length) return prev;
      const next = [...prev];
      [next[idx], next[targetIdx]] = [next[targetIdx], next[idx]];
      saveLayout(next);
      return next;
    });
  }, []);

  const toggleWidget = useCallback((id: string) => {
    setWidgets((prev) => {
      const next = prev.map((w) =>
        w.id === id ? { ...w, visible: !w.visible } : w
      );
      saveLayout(next);
      return next;
    });
  }, []);

  const resetLayout = useCallback(() => {
    const fresh = DEFAULT_WIDGETS.map((w) => ({ ...w }));
    setWidgets(fresh);
    saveLayout(fresh);
  }, []);

  return { widgets, moveWidget, toggleWidget, resetLayout };
}
