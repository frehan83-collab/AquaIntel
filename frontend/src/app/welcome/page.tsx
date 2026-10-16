"use client";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Sunrise, TrendingUp, BarChart3, ArrowRight, Waves } from "lucide-react";
import { cn } from "@/lib/utils";
import { useTranslation } from "@/lib/i18n";
import { setDemoState, type DemoPersona } from "@/components/DemoBanner";

interface PersonaCard {
  persona: DemoPersona;
  title: string;
  subtitle: string;
  icon: typeof Sunrise;
  color: string;
  gradient: string;
  glowColor: string;
  startRoute: string;
  bullets: string[];
}

const PERSONAS: PersonaCard[] = [
  {
    persona: "farmer",
    title: "Farmer",
    subtitle: "Daily operations & treatment decisions",
    icon: Sunrise,
    color: "text-emerald-400",
    gradient: "from-emerald-500/20 via-emerald-400/5 to-transparent",
    glowColor: "rgba(16,185,129,0.15)",
    startRoute: "/farmer-daily",
    bullets: [
      "One-screen daily lice check with clear TREAT / MONITOR decisions",
      "Treatment optimizer comparing 5 methods with ROI calculations",
      "Crowdsourced efficacy data that improves with every logged outcome",
      "Bio risk map with disease, bloom, and ocean condition overlays",
    ],
  },
  {
    persona: "trader",
    title: "Trader / Investor",
    subtitle: "Market signals & event impact modeling",
    icon: TrendingUp,
    color: "text-amber-400",
    gradient: "from-amber-500/20 via-amber-400/5 to-transparent",
    glowColor: "rgba(245,158,11,0.15)",
    startRoute: "/market",
    bullets: [
      "Market terminal with spot prices, forward curves, and sentiment",
      "Event simulator: model ISA outbreaks, traffic light changes, feed shocks",
      "Save and compare scenarios to build your trading thesis",
      "Quantitative signals from biological + market data fusion",
    ],
  },
  {
    persona: "analyst",
    title: "Analyst",
    subtitle: "Deep intelligence & competitive research",
    icon: BarChart3,
    color: "text-ocean-400",
    gradient: "from-ocean-500/20 via-ocean-400/5 to-transparent",
    glowColor: "rgba(0,212,200,0.15)",
    startRoute: "/disease",
    bullets: [
      "Disease intelligence across 6 countries with outbreak tracking",
      "ESG scoring and peer benchmarking for 50+ salmon companies",
      "FX-adjusted competitiveness index with tariff scenario modeling",
      "Smolt-to-harvest supply forecasting with 18-month pipeline view",
    ],
  },
];

export default function WelcomePage() {
  const { t } = useTranslation();
  const router = useRouter();

  const handleSelect = (card: PersonaCard) => {
    setDemoState(true, card.persona);
    // Dispatch tour start event
    window.dispatchEvent(
      new CustomEvent("aquaintel_start_tour", { detail: { persona: card.persona } })
    );
    router.push(card.startRoute);
  };

  const handleSkipDemo = () => {
    router.push("/");
  };

  return (
    <div className="min-h-[calc(100vh-4rem)] flex flex-col items-center justify-center px-6 py-12">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: [0.25, 0.46, 0.45, 0.94] }}
        className="text-center mb-12 max-w-2xl"
      >
        <div className="flex items-center justify-center gap-3 mb-4">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-salmon to-salmon-600 flex items-center justify-center shadow-[0_0_32px_rgba(232,115,74,0.2)]">
            <Waves className="w-6 h-6 text-white" />
          </div>
        </div>
        <h1 className="text-3xl md:text-4xl font-display text-[var(--text-primary)] mb-3">
          {t("page.welcome.title")}
        </h1>
        <p className="text-[15px] text-[var(--text-secondary)] leading-relaxed">
          The world&apos;s most advanced salmon aquaculture intelligence platform.
          Choose your perspective to get a guided tour of the features that matter most to you.
        </p>
      </motion.div>

      {/* Persona Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl w-full mb-10">
        {PERSONAS.map((card, i) => {
          const Icon = card.icon;
          return (
            <motion.button
              key={card.persona}
              initial={{ opacity: 0, y: 24 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{
                duration: 0.5,
                delay: 0.15 + i * 0.1,
                ease: [0.25, 0.46, 0.45, 0.94],
              }}
              onClick={() => handleSelect(card)}
              className={cn(
                "group relative text-left",
                "rounded-2xl overflow-hidden",
                "bg-gradient-to-br from-fjord-surface/60 to-fjord-midwater/40",
                "border border-white/[0.08]",
                "shadow-[0_8px_32px_rgba(0,0,0,0.3),inset_0_1px_0_rgba(255,255,255,0.03)]",
                "p-6",
                "transition-all duration-300",
                "hover:border-white/[0.15]",
                "hover:-translate-y-1",
                "hover:shadow-[0_16px_48px_rgba(0,0,0,0.4)]",
                "cursor-pointer"
              )}
              style={{
                // @ts-expect-error CSS custom property
                "--glow": card.glowColor,
              }}
            >
              {/* Left accent bar */}
              <div
                className={cn(
                  "absolute top-0 left-0 bottom-0 w-[2px] bg-gradient-to-b",
                  card.gradient
                )}
              />

              {/* Contour overlay */}
              <div className="absolute inset-0 contour-bg pointer-events-none opacity-40 rounded-[inherit]" />

              {/* Content */}
              <div className="relative z-10">
                {/* Icon */}
                <div
                  className={cn(
                    "w-12 h-12 rounded-xl flex items-center justify-center mb-4",
                    "bg-white/[0.04] border border-white/[0.06]",
                    "group-hover:border-white/[0.1] transition-colors"
                  )}
                >
                  <Icon className={cn("w-6 h-6", card.color)} />
                </div>

                {/* Title */}
                <h2 className="text-xl font-display text-[var(--text-primary)] mb-1">
                  {card.title}
                </h2>
                <p className="text-[12px] text-[var(--text-secondary)] mb-5">
                  {card.subtitle}
                </p>

                {/* Bullets */}
                <ul className="space-y-2.5 mb-6">
                  {card.bullets.map((bullet, bi) => (
                    <li key={bi} className="flex items-start gap-2.5">
                      <div
                        className={cn(
                          "w-1 h-1 rounded-full mt-1.5 flex-shrink-0",
                          card.color.replace("text-", "bg-")
                        )}
                      />
                      <span className="text-[12px] text-[var(--text-secondary)] leading-relaxed">
                        {bullet}
                      </span>
                    </li>
                  ))}
                </ul>

                {/* CTA */}
                <div
                  className={cn(
                    "flex items-center gap-2",
                    "text-[13px] font-semibold",
                    card.color,
                    "group-hover:gap-3 transition-all duration-200"
                  )}
                >
                  Start Tour
                  <ArrowRight className="w-4 h-4" />
                </div>
              </div>
            </motion.button>
          );
        })}
      </div>

      {/* Skip option */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.6 }}
      >
        <button
          onClick={handleSkipDemo}
          className="text-[12px] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
        >
          Skip — go straight to the dashboard
        </button>
      </motion.div>
    </div>
  );
}
