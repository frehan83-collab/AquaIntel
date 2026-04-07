"use client";
import { useState, useEffect, useCallback } from "react";
import { useRouter, usePathname } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronRight, X, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { getDemoState, type DemoPersona } from "./DemoBanner";

interface TourStep {
  /** Route to navigate to before showing this step */
  route: string;
  /** Title of the tooltip */
  title: string;
  /** Description text */
  description: string;
  /** CSS selector or data attribute to anchor the tooltip near (informational — positioning is fixed) */
  anchor?: string;
  /** Position of the tooltip on the page */
  position: "top-left" | "top-center" | "center" | "bottom-center";
}

const TOUR_STEPS: Record<DemoPersona, TourStep[]> = {
  farmer: [
    {
      route: "/farmer-daily",
      title: "Daily Check",
      description:
        "Your morning starts here. One screen shows lice levels, sea temperature, and a clear decision — TREAT NOW, SCHEDULE, MONITOR, or NO ACTION — for each of your farms.",
      position: "center",
    },
    {
      route: "/treatment",
      title: "Treatment Optimizer",
      description:
        "Compare 5 treatment methods side-by-side with ROI calculations, timing recommendations, and coordination across your production area network.",
      position: "center",
    },
    {
      route: "/farmer-daily",
      title: "Log Treatment Outcome",
      description:
        "After treating, tap 'I Treated Today' to log results. This builds a crowdsourced efficacy dataset that makes recommendations smarter over time.",
      position: "bottom-center",
    },
    {
      route: "/disease",
      title: "Disease Intelligence",
      description:
        "Track ISA, PD, and resistance patterns across Norway and globally. See which companies are affected and what treatments are working.",
      position: "center",
    },
    {
      route: "/bio-risk",
      title: "Bio Risk Map",
      description:
        "Visualize lice pressure, disease outbreaks, and algal blooms across all farming regions. Zoom into your production area for local conditions.",
      position: "center",
    },
    {
      route: "/",
      title: "Your Dashboard",
      description:
        "This is your home base. Live KPIs, anomaly alerts, and intelligence summaries update throughout the day. You are all set!",
      position: "center",
    },
  ],
  trader: [
    {
      route: "/market",
      title: "Market Terminal",
      description:
        "Spot prices, forward curves, sentiment, and AIS vessel intelligence — everything a salmon trader needs in one view.",
      position: "center",
    },
    {
      route: "/trader",
      title: "Event Impact Simulator",
      description:
        "Model ISA outbreaks, traffic light changes, and feed price shocks. See per-company revenue impact, EBIT changes, and expected stock moves.",
      position: "center",
    },
    {
      route: "/trader",
      title: "Save Scenarios",
      description:
        "Save your simulations for later comparison. Build a library of what-if scenarios to inform your trading decisions.",
      position: "bottom-center",
    },
    {
      route: "/signals",
      title: "Trading Signals",
      description:
        "Pairs trading opportunities, regime shift alerts, and anomaly detection — quantitative signals derived from biological and market data.",
      position: "center",
    },
    {
      route: "/price-outlook",
      title: "Price Predictions",
      description:
        "Machine learning forecasts with confidence bands, track record, and the key drivers behind each prediction.",
      position: "center",
    },
    {
      route: "/",
      title: "Your Dashboard",
      description:
        "Live intelligence at a glance — regime alerts, pairs signals, and market mood. Start every trading day here. You are all set!",
      position: "center",
    },
  ],
  analyst: [
    {
      route: "/disease",
      title: "Disease Intelligence",
      description:
        "Comprehensive disease tracking across Norway, Canada, Chile, Scotland, Faroe Islands, and Iceland. Outbreaks, treatments, and resistance data.",
      position: "center",
    },
    {
      route: "/leaders",
      title: "Leaders & ESG",
      description:
        "Rank the top 50 Norwegian salmon companies by ESG score, lice performance, growth, and disease resilience. Click any row for deep-dive details.",
      position: "center",
    },
    {
      route: "/competitiveness",
      title: "Origin Competitiveness",
      description:
        "FX-adjusted production costs across 6 origins with tariff scenario modeling. See who wins on landed cost in each market.",
      position: "center",
    },
    {
      route: "/supply-forecast",
      title: "Supply Forecast",
      description:
        "Smolt-to-harvest cohort modeling with 18-month supply pipeline, demand balance indicators, and price pressure signals.",
      position: "center",
    },
    {
      route: "/causal",
      title: "Causal Engine",
      description:
        "Granger causality and transfer entropy reveal which variables actually drive salmon prices — and with what lag.",
      position: "center",
    },
    {
      route: "/",
      title: "Your Dashboard",
      description:
        "Your analytical home base — anomaly scores, production data, and live intelligence. Explore freely from here. You are all set!",
      position: "center",
    },
  ],
};

export function isTourCompleted(): boolean {
  if (typeof window === "undefined") return false;
  return localStorage.getItem("openclaw_tour_completed") === "true";
}

export function resetTour() {
  if (typeof window === "undefined") return;
  localStorage.removeItem("openclaw_tour_completed");
}

export default function GuidedTour() {
  const router = useRouter();
  const pathname = usePathname();
  const [active, setActive] = useState(false);
  const [stepIndex, setStepIndex] = useState(0);
  const [persona, setPersona] = useState<DemoPersona>("farmer");

  // Listen for tour start event
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (detail?.persona) setPersona(detail.persona);
      setStepIndex(0);
      setActive(true);
    };
    window.addEventListener("openclaw_start_tour", handler);
    return () => window.removeEventListener("openclaw_start_tour", handler);
  }, []);

  const steps = TOUR_STEPS[persona];
  const currentStep = steps[stepIndex];

  // Navigate to the step's route when it changes
  useEffect(() => {
    if (!active || !currentStep) return;
    if (pathname !== currentStep.route) {
      router.push(currentStep.route);
    }
  }, [active, stepIndex, currentStep, pathname, router]);

  const handleNext = useCallback(() => {
    if (stepIndex < steps.length - 1) {
      setStepIndex((i) => i + 1);
    } else {
      // Tour complete
      localStorage.setItem("openclaw_tour_completed", "true");
      setActive(false);
    }
  }, [stepIndex, steps.length]);

  const handleSkip = useCallback(() => {
    localStorage.setItem("openclaw_tour_completed", "true");
    setActive(false);
  }, []);

  if (!active || !currentStep) return null;

  const positionClasses: Record<string, string> = {
    "top-left": "top-24 left-[260px]",
    "top-center": "top-24 left-1/2 -translate-x-1/2",
    center: "top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2",
    "bottom-center": "bottom-24 left-1/2 -translate-x-1/2",
  };

  return (
    <AnimatePresence>
      {/* Overlay */}
      <motion.div
        key="tour-overlay"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-[60] bg-black/40 backdrop-blur-[2px]"
        onClick={handleSkip}
      />

      {/* Tooltip */}
      <motion.div
        key={`tour-step-${stepIndex}`}
        initial={{ opacity: 0, y: 12, scale: 0.96 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: -8, scale: 0.96 }}
        transition={{ duration: 0.35, ease: [0.25, 0.46, 0.45, 0.94] }}
        className={cn(
          "fixed z-[61]",
          positionClasses[currentStep.position],
          "w-[400px] max-w-[90vw]",
          "rounded-2xl",
          "bg-gradient-to-br from-fjord-surface/80 to-fjord-midwater/70",
          "backdrop-blur-2xl",
          "border border-white/[0.1]",
          "shadow-[0_16px_64px_rgba(0,0,0,0.5),0_0_32px_rgba(232,115,74,0.08)]",
          "p-5"
        )}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Step counter */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-salmon" />
            <span className="text-[10px] font-bold text-salmon/70 uppercase tracking-[0.12em]">
              Step {stepIndex + 1} of {steps.length}
            </span>
          </div>
          <button
            onClick={handleSkip}
            className="text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
            aria-label="Skip tour"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Progress bar */}
        <div className="w-full h-1 rounded-full bg-white/[0.06] mb-4 overflow-hidden">
          <motion.div
            className="h-full rounded-full bg-gradient-to-r from-salmon to-salmon-600"
            initial={{ width: 0 }}
            animate={{ width: `${((stepIndex + 1) / steps.length) * 100}%` }}
            transition={{ duration: 0.4, ease: "easeOut" }}
          />
        </div>

        {/* Content */}
        <h3 className="text-lg font-display text-[var(--text-primary)] mb-2">
          {currentStep.title}
        </h3>
        <p className="text-[13px] text-[var(--text-secondary)] leading-relaxed mb-5">
          {currentStep.description}
        </p>

        {/* Actions */}
        <div className="flex items-center justify-between">
          <button
            onClick={handleSkip}
            className="text-[12px] font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
          >
            Skip Tour
          </button>
          <button
            onClick={handleNext}
            className={cn(
              "flex items-center gap-1.5 px-4 py-2 rounded-xl",
              "text-[12px] font-semibold text-white",
              "bg-gradient-to-r from-salmon to-salmon-600",
              "shadow-[0_4px_16px_rgba(232,115,74,0.3)]",
              "hover:shadow-[0_6px_24px_rgba(232,115,74,0.4)]",
              "hover:-translate-y-0.5",
              "transition-all duration-200"
            )}
          >
            {stepIndex < steps.length - 1 ? (
              <>
                Next <ChevronRight className="w-3.5 h-3.5" />
              </>
            ) : (
              "Finish Tour"
            )}
          </button>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
