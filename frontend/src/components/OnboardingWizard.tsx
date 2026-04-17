"use client";
import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Sunrise, TrendingUp, BarChart3, ShieldCheck,
  MapPin, Search, Bell, ChevronRight, ChevronLeft,
  Check, X, Star, Loader2, Globe,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { useTranslation, formatNumber } from "@/lib/i18n";

/* eslint-disable @typescript-eslint/no-explicit-any */

// ─── Types ───────────────────────────────────────────────────────────
type Role = "farmer" | "trader" | "analyst" | "admin";

interface Region {
  id: string;
  label: string;
  flag: string;
}

interface SavedFarm {
  locality_no: number;
  name: string;
}

interface AlertPrefs {
  lice: boolean;
  price: boolean;
  disease: boolean;
  temperature: boolean;
  lice_threshold: number;
  price_change_pct: number;
  temp_threshold: number;
}

// ─── Constants ───────────────────────────────────────────────────────
const ROLES: { id: Role; title: string; subtitle: string; icon: typeof Sunrise; color: string; gradient: string }[] = [
  {
    id: "farmer",
    title: "Farmer",
    subtitle: "Daily operations, treatment decisions, and farm monitoring",
    icon: Sunrise,
    color: "text-emerald-400",
    gradient: "from-emerald-500/20 to-emerald-400/5",
  },
  {
    id: "trader",
    title: "Trader / Investor",
    subtitle: "Market signals, event impact modeling, and price intelligence",
    icon: TrendingUp,
    color: "text-amber-400",
    gradient: "from-amber-500/20 to-amber-400/5",
  },
  {
    id: "analyst",
    title: "Analyst",
    subtitle: "Deep intelligence, competitive research, and ESG analysis",
    icon: BarChart3,
    color: "text-ocean-400",
    gradient: "from-ocean-500/20 to-ocean-400/5",
  },
  {
    id: "admin",
    title: "Admin",
    subtitle: "Platform management, data quality, and system health",
    icon: ShieldCheck,
    color: "text-violet-400",
    gradient: "from-violet-500/20 to-violet-400/5",
  },
];

const REGIONS: Region[] = [
  { id: "norway", label: "Norway", flag: "NO" },
  { id: "scotland", label: "Scotland", flag: "GB" },
  { id: "faroes", label: "Faroe Islands", flag: "FO" },
  { id: "iceland", label: "Iceland", flag: "IS" },
  { id: "canada", label: "Canada", flag: "CA" },
  { id: "chile", label: "Chile", flag: "CL" },
  { id: "global", label: "Global", flag: "GLOBE" },
];

const STEP_LABELS = ["Choose Your Role", "Select Your Region", "Save Your Farms", "Set Alert Preferences"];

// ─── localStorage helpers ────────────────────────────────────────────
export function isOnboarded(): boolean {
  if (typeof window === "undefined") return true;
  return localStorage.getItem("oc_onboarded") === "true";
}

export function resetOnboarding() {
  if (typeof window === "undefined") return;
  localStorage.removeItem("oc_onboarded");
  window.dispatchEvent(new Event("oc_onboarding_reset"));
}

function completeOnboarding() {
  localStorage.setItem("oc_onboarded", "true");
  window.dispatchEvent(new Event("oc_onboarding_complete"));
}

// ─── Component ───────────────────────────────────────────────────────
export default function OnboardingWizard() {
  const [visible, setVisible] = useState(false);
  const [step, setStep] = useState(0);

  // Step 1: Role
  const [role, setRole] = useState<Role | null>(null);

  // Step 2: Region
  const [region, setRegion] = useState<string | null>(null);

  // Step 3: Farms
  const [farmSearch, setFarmSearch] = useState("");
  const [farmResults, setFarmResults] = useState<SavedFarm[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [savedFarms, setSavedFarms] = useState<SavedFarm[]>([]);

  // Step 4: Alerts
  const [alertPrefs, setAlertPrefs] = useState<AlertPrefs>({
    lice: true,
    price: true,
    disease: true,
    temperature: false,
    lice_threshold: 0.5,
    price_change_pct: 5,
    temp_threshold: 18,
  });

  // Check if should show
  useEffect(() => {
    if (!isOnboarded()) setVisible(true);
    const handler = () => setVisible(true);
    window.addEventListener("oc_onboarding_reset", handler);
    return () => window.removeEventListener("oc_onboarding_reset", handler);
  }, []);

  // Farm search debounce
  useEffect(() => {
    if (!farmSearch || farmSearch.length < 2) {
      setFarmResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      setSearchLoading(true);
      try {
        const data = await api.searchLocalities(farmSearch);
        const results = Array.isArray(data) ? data : data?.results || [];
        setFarmResults(results.slice(0, 20));
      } catch {
        setFarmResults([]);
      } finally {
        setSearchLoading(false);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [farmSearch]);

  const addFarm = useCallback((farm: SavedFarm) => {
    setSavedFarms((prev) => {
      if (prev.length >= 10) return prev;
      if (prev.some((f) => f.locality_no === farm.locality_no)) return prev;
      return [...prev, farm];
    });
  }, []);

  const removeFarm = useCallback((locNo: number) => {
    setSavedFarms((prev) => prev.filter((f) => f.locality_no !== locNo));
  }, []);

  const handleComplete = useCallback(() => {
    // Persist role
    if (role) {
      localStorage.setItem("oc_persona", role);
    }
    // Persist region
    if (region) {
      localStorage.setItem("oc_default_region", region);
    }
    // Persist saved farms
    if (savedFarms.length > 0) {
      localStorage.setItem("oc_saved_farms", JSON.stringify(savedFarms));
    }
    // Persist alert preferences
    localStorage.setItem("oc_alert_prefs", JSON.stringify(alertPrefs));
    // Mark onboarded
    completeOnboarding();
    setVisible(false);
  }, [role, region, savedFarms, alertPrefs]);

  const canProceed = useCallback(() => {
    switch (step) {
      case 0: return !!role;
      case 1: return !!region;
      case 2: return true; // optional
      case 3: return true;
      default: return false;
    }
  }, [step, role, region]);

  const handleNext = useCallback(() => {
    if (step < 3) setStep((s) => s + 1);
    else handleComplete();
  }, [step, handleComplete]);

  const handleBack = useCallback(() => {
    if (step > 0) setStep((s) => s - 1);
  }, [step]);

  const handleSkipStep = useCallback(() => {
    if (step < 3) setStep((s) => s + 1);
    else handleComplete();
  }, [step, handleComplete]);

  if (!visible) return null;

  const progress = ((step + 1) / 4) * 100;

  return (
    <AnimatePresence>
      {/* Glassmorphic full-screen overlay */}
      <motion.div
        key="onboarding-overlay"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.4 }}
        className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60 backdrop-blur-md"
      >
        {/* Wizard Card */}
        <motion.div
          key={`wizard-step-${step}`}
          initial={{ opacity: 0, y: 20, scale: 0.97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -10, scale: 0.97 }}
          transition={{ duration: 0.35, ease: [0.25, 0.46, 0.45, 0.94] }}
          className={cn(
            "relative w-[640px] max-w-[94vw] max-h-[90vh] overflow-y-auto",
            "rounded-3xl",
            "bg-gradient-to-br from-fjord-surface/90 to-fjord-midwater/80",
            "backdrop-blur-2xl",
            "border border-white/[0.1]",
            "shadow-[0_24px_80px_rgba(0,0,0,0.6),0_0_40px_rgba(232,115,74,0.06)]",
            "p-8"
          )}
        >
          {/* Close button */}
          <button
            onClick={handleComplete}
            className="absolute top-4 right-4 text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
            aria-label="Skip onboarding"
          >
            <X className="w-5 h-5" />
          </button>

          {/* Header */}
          <div className="mb-6">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-salmon to-salmon-600 flex items-center justify-center">
                <Star className="w-4 h-4 text-white" />
              </div>
              <span className="text-[10px] font-bold text-salmon/70 uppercase tracking-[0.12em]">
                Step {step + 1} of 4
              </span>
            </div>
            <h2 className="text-2xl font-display text-[var(--text-primary)]">
              {STEP_LABELS[step]}
            </h2>
          </div>

          {/* Progress bar */}
          <div className="w-full h-1.5 rounded-full bg-white/[0.06] mb-8 overflow-hidden">
            <motion.div
              className="h-full rounded-full bg-gradient-to-r from-salmon to-salmon-600"
              initial={{ width: 0 }}
              animate={{ width: `${progress}%` }}
              transition={{ duration: 0.5, ease: "easeOut" }}
            />
          </div>

          {/* Step Content */}
          <div className="min-h-[280px]">
            {step === 0 && (
              <StepRole selected={role} onSelect={setRole} />
            )}
            {step === 1 && (
              <StepRegion selected={region} onSelect={setRegion} />
            )}
            {step === 2 && (
              <StepFarms
                role={role}
                farmSearch={farmSearch}
                setFarmSearch={setFarmSearch}
                farmResults={farmResults}
                searchLoading={searchLoading}
                savedFarms={savedFarms}
                addFarm={addFarm}
                removeFarm={removeFarm}
              />
            )}
            {step === 3 && (
              <StepAlerts prefs={alertPrefs} setPrefs={setAlertPrefs} />
            )}
          </div>

          {/* Navigation */}
          <div className="flex items-center justify-between mt-8 pt-6 border-t border-white/[0.06]">
            <div>
              {step > 0 ? (
                <button
                  onClick={handleBack}
                  className="flex items-center gap-1.5 text-[13px] font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
                >
                  <ChevronLeft className="w-4 h-4" />
                  Back
                </button>
              ) : (
                <button
                  onClick={handleComplete}
                  className="text-[12px] font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
                >
                  Skip Setup
                </button>
              )}
            </div>

            <div className="flex items-center gap-3">
              {(step === 2 || step === 3) && (
                <button
                  onClick={handleSkipStep}
                  className="text-[12px] font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
                >
                  Skip
                </button>
              )}
              <button
                onClick={handleNext}
                disabled={!canProceed()}
                className={cn(
                  "flex items-center gap-1.5 px-5 py-2.5 rounded-xl",
                  "text-[13px] font-semibold text-white",
                  "bg-gradient-to-r from-salmon to-salmon-600",
                  "shadow-[0_4px_16px_rgba(232,115,74,0.3)]",
                  "hover:shadow-[0_6px_24px_rgba(232,115,74,0.4)]",
                  "hover:-translate-y-0.5",
                  "transition-all duration-200",
                  "disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:translate-y-0 disabled:hover:shadow-[0_4px_16px_rgba(232,115,74,0.3)]"
                )}
              >
                {step < 3 ? (
                  <>
                    Next <ChevronRight className="w-4 h-4" />
                  </>
                ) : (
                  <>
                    <Check className="w-4 h-4" />
                    Complete Setup
                  </>
                )}
              </button>
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

// ─── Step 1: Choose Your Role ────────────────────────────────────────
function StepRole({ selected, onSelect }: { selected: Role | null; onSelect: (r: Role) => void }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
      {ROLES.map((r) => {
        const Icon = r.icon;
        const isSelected = selected === r.id;
        return (
          <button
            key={r.id}
            onClick={() => onSelect(r.id)}
            className={cn(
              "relative text-left rounded-2xl p-5 transition-all duration-200",
              "border",
              isSelected
                ? "border-salmon/40 bg-salmon/[0.08] shadow-[0_0_24px_rgba(232,115,74,0.1)]"
                : "border-white/[0.06] bg-white/[0.02] hover:border-white/[0.12] hover:bg-white/[0.04]"
            )}
          >
            {/* Selection indicator */}
            {isSelected && (
              <div className="absolute top-3 right-3 w-5 h-5 rounded-full bg-salmon flex items-center justify-center">
                <Check className="w-3 h-3 text-white" />
              </div>
            )}
            <div className={cn("w-10 h-10 rounded-xl flex items-center justify-center mb-3", "bg-white/[0.04] border border-white/[0.06]")}>
              <Icon className={cn("w-5 h-5", r.color)} />
            </div>
            <h3 className="text-[15px] font-semibold text-[var(--text-primary)] mb-1">
              {r.title}
            </h3>
            <p className="text-[12px] text-[var(--text-secondary)] leading-relaxed">
              {r.subtitle}
            </p>
          </button>
        );
      })}
    </div>
  );
}

// ─── Step 2: Select Your Region ──────────────────────────────────────
function StepRegion({ selected, onSelect }: { selected: string | null; onSelect: (r: string) => void }) {
  return (
    <div>
      <p className="text-[13px] text-[var(--text-secondary)] mb-5">
        Choose your primary region to set default filters across the platform.
      </p>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        {REGIONS.map((r) => {
          const isSelected = selected === r.id;
          return (
            <button
              key={r.id}
              onClick={() => onSelect(r.id)}
              className={cn(
                "relative flex flex-col items-center gap-2 rounded-2xl p-5 transition-all duration-200",
                "border",
                isSelected
                  ? "border-salmon/40 bg-salmon/[0.08] shadow-[0_0_24px_rgba(232,115,74,0.1)]"
                  : "border-white/[0.06] bg-white/[0.02] hover:border-white/[0.12] hover:bg-white/[0.04]"
              )}
            >
              {isSelected && (
                <div className="absolute top-2 right-2 w-4 h-4 rounded-full bg-salmon flex items-center justify-center">
                  <Check className="w-2.5 h-2.5 text-white" />
                </div>
              )}
              <div className={cn(
                "w-10 h-10 rounded-full flex items-center justify-center",
                "bg-white/[0.04] border border-white/[0.06]"
              )}>
                {r.flag === "GLOBE" ? (
                  <Globe className="w-5 h-5 text-ocean-400" />
                ) : (
                  <MapPin className={cn("w-5 h-5", isSelected ? "text-salmon" : "text-[var(--text-secondary)]")} />
                )}
              </div>
              <span className={cn(
                "text-[13px] font-medium",
                isSelected ? "text-[var(--text-primary)]" : "text-[var(--text-secondary)]"
              )}>
                {r.label}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ─── Step 3: Save Your Farms ─────────────────────────────────────────
function StepFarms({
  role,
  farmSearch,
  setFarmSearch,
  farmResults,
  searchLoading,
  savedFarms,
  addFarm,
  removeFarm,
}: {
  role: Role | null;
  farmSearch: string;
  setFarmSearch: (s: string) => void;
  farmResults: SavedFarm[];
  searchLoading: boolean;
  savedFarms: SavedFarm[];
  addFarm: (f: SavedFarm) => void;
  removeFarm: (n: number) => void;
}) {
  const isOptional = role !== "farmer";

  return (
    <div>
      {isOptional && (
        <div className="flex items-center gap-2 px-3 py-2 mb-4 rounded-xl bg-ocean-500/[0.08] border border-ocean-500/[0.15]">
          <span className="text-[12px] text-ocean-400">
            This step is optional for {role === "trader" ? "traders" : role === "analyst" ? "analysts" : "admins"}. Skip if you don&apos;t manage specific farms.
          </span>
        </div>
      )}

      <p className="text-[13px] text-[var(--text-secondary)] mb-4">
        Search for farms by name or locality number. Save up to 10 farms for quick access.
      </p>

      {/* Search input */}
      <div className="relative mb-4">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-secondary)]" />
        <input
          type="text"
          value={farmSearch}
          onChange={(e) => setFarmSearch(e.target.value)}
          placeholder="Search farms by name..."
          className={cn(
            "w-full pl-10 pr-4 py-2.5 rounded-xl",
            "bg-white/[0.04] border border-white/[0.08]",
            "text-[13px] text-[var(--text-primary)] placeholder:text-[var(--text-secondary)]",
            "focus:outline-none focus:border-salmon/40 focus:ring-1 focus:ring-salmon/20",
            "transition-all"
          )}
        />
        {searchLoading && (
          <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-salmon animate-spin" />
        )}
      </div>

      {/* Search results */}
      {farmResults.length > 0 && (
        <div className="mb-4 max-h-[160px] overflow-y-auto rounded-xl border border-white/[0.06] bg-white/[0.02]">
          {farmResults.map((farm) => {
            const isSaved = savedFarms.some((f) => f.locality_no === farm.locality_no);
            return (
              <button
                key={farm.locality_no}
                onClick={() => !isSaved && addFarm(farm)}
                disabled={isSaved || savedFarms.length >= 10}
                className={cn(
                  "w-full flex items-center justify-between px-4 py-2.5 text-left",
                  "border-b border-white/[0.04] last:border-b-0",
                  "transition-colors",
                  isSaved
                    ? "opacity-50 cursor-default"
                    : "hover:bg-white/[0.04] cursor-pointer"
                )}
              >
                <div>
                  <span className="text-[13px] text-[var(--text-primary)]">{farm.name}</span>
                  <span className="text-[11px] text-[var(--text-secondary)] ml-2">#{farm.locality_no}</span>
                </div>
                {isSaved ? (
                  <Check className="w-4 h-4 text-emerald-400" />
                ) : (
                  <span className="text-[11px] text-salmon">+ Add</span>
                )}
              </button>
            );
          })}
        </div>
      )}

      {/* Saved farms */}
      {savedFarms.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-[12px] font-semibold text-[var(--text-secondary)] uppercase tracking-wider">
              My Farms ({savedFarms.length}/10)
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            {savedFarms.map((farm) => (
              <div
                key={farm.locality_no}
                className={cn(
                  "flex items-center gap-2 px-3 py-1.5 rounded-lg",
                  "bg-emerald-500/[0.08] border border-emerald-500/[0.15]",
                  "text-[12px] text-emerald-400"
                )}
              >
                <span>{farm.name}</span>
                <button
                  onClick={() => removeFarm(farm.locality_no)}
                  className="hover:text-rose-400 transition-colors"
                  aria-label={`Remove ${farm.name}`}
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {savedFarms.length === 0 && farmResults.length === 0 && !farmSearch && (
        <div className="text-center py-8 text-[var(--text-secondary)]">
          <MapPin className="w-8 h-8 mx-auto mb-2 opacity-40" />
          <p className="text-[13px]">Start typing to search for farms</p>
        </div>
      )}
    </div>
  );
}

// ─── Step 4: Set Alert Preferences ───────────────────────────────────
function StepAlerts({
  prefs,
  setPrefs,
}: {
  prefs: AlertPrefs;
  setPrefs: React.Dispatch<React.SetStateAction<AlertPrefs>>;
}) {
  const { locale } = useTranslation();
  const toggles: { key: keyof Pick<AlertPrefs, "lice" | "price" | "disease" | "temperature">; label: string; desc: string; icon: typeof Bell; color: string }[] = [
    { key: "lice", label: "Lice Alerts", desc: "When adult female lice exceed your threshold", icon: Bell, color: "text-rose-400" },
    { key: "price", label: "Price Alerts", desc: "When spot price changes by your specified percentage", icon: TrendingUp, color: "text-amber-400" },
    { key: "disease", label: "Disease Alerts", desc: "New ISA, PD, or resistance reports in your region", icon: ShieldCheck, color: "text-violet-400" },
    { key: "temperature", label: "Temperature Alerts", desc: "When sea temperature exceeds safe thresholds", icon: Globe, color: "text-ocean-400" },
  ];

  return (
    <div>
      <p className="text-[13px] text-[var(--text-secondary)] mb-5">
        Choose which alerts you want to receive. You can adjust these anytime in Settings.
      </p>

      {/* Toggle cards */}
      <div className="space-y-3 mb-6">
        {toggles.map((t) => {
          const isOn = prefs[t.key];
          const Icon = t.icon;
          return (
            <button
              key={t.key}
              onClick={() => setPrefs((p) => ({ ...p, [t.key]: !p[t.key] }))}
              className={cn(
                "w-full flex items-center gap-4 px-4 py-3.5 rounded-xl text-left transition-all duration-200",
                "border",
                isOn
                  ? "border-white/[0.1] bg-white/[0.04]"
                  : "border-white/[0.04] bg-white/[0.01] opacity-60"
              )}
            >
              <div className={cn("w-8 h-8 rounded-lg flex items-center justify-center", "bg-white/[0.04]")}>
                <Icon className={cn("w-4 h-4", isOn ? t.color : "text-[var(--text-secondary)]")} />
              </div>
              <div className="flex-1">
                <span className="text-[13px] font-medium text-[var(--text-primary)] block">
                  {t.label}
                </span>
                <span className="text-[11px] text-[var(--text-secondary)]">
                  {t.desc}
                </span>
              </div>
              {/* Toggle switch */}
              <div
                className={cn(
                  "w-10 h-5.5 rounded-full relative transition-colors duration-200",
                  isOn ? "bg-salmon" : "bg-white/[0.1]"
                )}
                style={{ height: "22px" }}
              >
                <div
                  className={cn(
                    "absolute top-[2px] w-[18px] h-[18px] rounded-full bg-white shadow-sm transition-transform duration-200",
                    isOn ? "translate-x-[20px]" : "translate-x-[2px]"
                  )}
                />
              </div>
            </button>
          );
        })}
      </div>

      {/* Threshold sliders */}
      {prefs.lice && (
        <ThresholdSlider
          label="Lice threshold (adult female per fish)"
          value={prefs.lice_threshold}
          min={0.1}
          max={2.0}
          step={0.1}
          format={(v) => formatNumber(v, locale, 1)}
          onChange={(v) => setPrefs((p) => ({ ...p, lice_threshold: v }))}
        />
      )}
      {prefs.price && (
        <ThresholdSlider
          label="Price change alert (%)"
          value={prefs.price_change_pct}
          min={1}
          max={20}
          step={1}
          format={(v) => `${v}%`}
          onChange={(v) => setPrefs((p) => ({ ...p, price_change_pct: v }))}
        />
      )}
      {prefs.temperature && (
        <ThresholdSlider
          label="Temperature threshold (C)"
          value={prefs.temp_threshold}
          min={10}
          max={25}
          step={0.5}
          format={(v) => `${v}C`}
          onChange={(v) => setPrefs((p) => ({ ...p, temp_threshold: v }))}
        />
      )}
    </div>
  );
}

// ─── Reusable threshold slider ───────────────────────────────────────
function ThresholdSlider({
  label,
  value,
  min,
  max,
  step,
  format,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  format: (v: number) => string;
  onChange: (v: number) => void;
}) {
  return (
    <div className="mb-4">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[12px] text-[var(--text-secondary)]">{label}</span>
        <span className="text-[12px] font-mono text-salmon">{format(value)}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full h-1.5 rounded-full appearance-none bg-white/[0.08] accent-salmon cursor-pointer"
      />
    </div>
  );
}

