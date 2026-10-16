"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { X, Sunrise, TrendingUp, BarChart3 } from "lucide-react";
import { cn } from "@/lib/utils";

export type DemoPersona = "farmer" | "trader" | "analyst";

const PERSONA_CONFIG: Record<DemoPersona, { label: string; icon: typeof Sunrise; color: string }> = {
  farmer:  { label: "Farmer",  icon: Sunrise,    color: "text-emerald-400" },
  trader:  { label: "Trader",  icon: TrendingUp, color: "text-amber-400" },
  analyst: { label: "Analyst", icon: BarChart3,   color: "text-ocean-400" },
};

export function getDemoState(): { active: boolean; persona: DemoPersona } {
  if (typeof window === "undefined") return { active: false, persona: "farmer" };
  try {
    const raw = localStorage.getItem("aquaintel_demo_mode");
    if (!raw) return { active: false, persona: "farmer" };
    const parsed = JSON.parse(raw);
    return { active: !!parsed.active, persona: parsed.persona || "farmer" };
  } catch {
    return { active: false, persona: "farmer" };
  }
}

export function setDemoState(active: boolean, persona?: DemoPersona) {
  if (typeof window === "undefined") return;
  if (!active) {
    localStorage.removeItem("aquaintel_demo_mode");
  } else {
    localStorage.setItem(
      "aquaintel_demo_mode",
      JSON.stringify({ active: true, persona: persona || "farmer" })
    );
  }
  window.dispatchEvent(new Event("aquaintel_demo_change"));
}

export default function DemoBanner() {
  const router = useRouter();
  const [demo, setDemo] = useState<{ active: boolean; persona: DemoPersona }>({
    active: false,
    persona: "farmer",
  });

  useEffect(() => {
    setDemo(getDemoState());
    const handler = () => setDemo(getDemoState());
    window.addEventListener("aquaintel_demo_change", handler);
    window.addEventListener("storage", handler);
    return () => {
      window.removeEventListener("aquaintel_demo_change", handler);
      window.removeEventListener("storage", handler);
    };
  }, []);

  if (!demo.active) return null;

  const current = PERSONA_CONFIG[demo.persona];
  const Icon = current.icon;

  const handleSwitch = (persona: DemoPersona) => {
    setDemoState(true, persona);
    setDemo({ active: true, persona });
  };

  const handleExit = () => {
    setDemoState(false);
    setDemo({ active: false, persona: "farmer" });
    router.push("/welcome");
  };

  return (
    <AnimatePresence>
      <motion.div
        initial={{ y: -40, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        exit={{ y: -40, opacity: 0 }}
        transition={{ duration: 0.3, ease: "easeOut" }}
        className={cn(
          "sticky top-0 z-50",
          "h-10 flex items-center justify-between px-5",
          "bg-gradient-to-r from-fjord-midwater/90 via-ocean-950/90 to-fjord-midwater/90",
          "backdrop-blur-xl",
          "border-b border-salmon/[0.15]",
          "shadow-[0_2px_16px_rgba(232,115,74,0.08)]"
        )}
      >
        {/* Left: Demo indicator */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <div className="w-1.5 h-1.5 rounded-full bg-salmon animate-pulse" />
            <span className="text-[10px] font-bold text-salmon uppercase tracking-[0.12em]">
              Demo Mode
            </span>
          </div>
          <span className="text-[11px] text-[var(--text-secondary)]">&mdash;</span>
          <div className="flex items-center gap-1.5">
            <Icon className={cn("w-3.5 h-3.5", current.color)} />
            <span className={cn("text-[11px] font-semibold", current.color)}>
              Exploring as {current.label}
            </span>
          </div>
        </div>

        {/* Center: Persona switcher */}
        <div className="flex items-center gap-1">
          {(Object.keys(PERSONA_CONFIG) as DemoPersona[]).map((p) => {
            const cfg = PERSONA_CONFIG[p];
            const PIcon = cfg.icon;
            const isActive = demo.persona === p;
            return (
              <button
                key={p}
                onClick={() => handleSwitch(p)}
                className={cn(
                  "flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-medium transition-all duration-200",
                  isActive
                    ? "bg-white/[0.08] text-[var(--text-primary)] shadow-[inset_0_0_0_1px_rgba(255,255,255,0.1)]"
                    : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-white/[0.04]"
                )}
              >
                <PIcon className={cn("w-3 h-3", isActive && cfg.color)} />
                {cfg.label}
              </button>
            );
          })}
        </div>

        {/* Right: Exit button */}
        <button
          onClick={handleExit}
          className={cn(
            "flex items-center gap-1.5 px-3 py-1 rounded-lg",
            "text-[11px] font-medium text-rose-400/80",
            "bg-rose-500/[0.08] hover:bg-rose-500/[0.15]",
            "border border-rose-500/[0.12] hover:border-rose-500/[0.2]",
            "transition-all duration-200"
          )}
        >
          <X className="w-3 h-3" />
          Exit Demo
        </button>
      </motion.div>
    </AnimatePresence>
  );
}
