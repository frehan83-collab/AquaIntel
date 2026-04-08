"use client";
import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import { useTranslation, NAV_LABEL_KEYS, SECTION_KEYS } from "@/lib/i18n";
import {
  LayoutDashboard, Brain, TrendingUp, Anchor, Award,
  BarChart3, Map, FlaskConical, Settings, Newspaper,
  ChevronLeft, ChevronRight, Bot, Boxes, DollarSign, Trophy,
  Sigma, Wheat, Ship, Globe2, Shield, Scale, Radio, ShieldCheck, Satellite, FileText,
  Thermometer, Syringe, Factory, Timer, CreditCard, FileCheck, Sparkles, Sunrise, Layers,
  Menu, X, BookOpen, GitCompare, Bell, BriefcaseBusiness, Search, ScrollText, LineChart,
  Heart,
} from "lucide-react";

const CHANGELOG_LATEST_VERSION = "2.5.0";
const CHANGELOG_LS_KEY = "fishintel_last_viewed_changelog";

type NavItem = { href: string; label: string; icon: any };
type NavSection = { section: string; items: NavItem[] };

const NAV_SECTIONS: NavSection[] = [
  { section: "", items: [
    { href: "/", label: "Dashboard", icon: LayoutDashboard },
    { href: "/farmer-daily", label: "Daily Check", icon: Sunrise },
    { href: "/brief", label: "Morning Brief", icon: Newspaper },
    { href: "/notifications", label: "Notifications", icon: Bell },
  ]},
  { section: "Intelligence", items: [
    { href: "/leaders", label: "Leaders & ESG", icon: Trophy },
    { href: "/benchmark", label: "Peer Benchmark", icon: Award },
    { href: "/bio-risk", label: "Bio Risk Map", icon: Map },
    { href: "/disease", label: "Disease Intel", icon: Shield },
    { href: "/climate", label: "Climate Risk", icon: Thermometer },
    { href: "/traffic-light", label: "Traffic Light", icon: Thermometer },
    { href: "/lice-quota", label: "Lice Quotas", icon: Sigma },
    { href: "/compare", label: "Compare", icon: GitCompare },
  ]},
  { section: "Markets", items: [
    { href: "/feed-cost", label: "Production Costs", icon: Wheat },
    { href: "/global-supply", label: "Global Supply", icon: Ship },
    { href: "/competitiveness", label: "Competitiveness", icon: Scale },
    { href: "/supply-forecast", label: "Supply Forecast", icon: TrendingUp },
    { href: "/investor", label: "Investor Intel", icon: TrendingUp },
    { href: "/trader", label: "Trader Intel", icon: TrendingUp },
    { href: "/futures", label: "Salmon Futures", icon: LineChart },
    { href: "/market", label: "Market Terminal", icon: DollarSign },
    { href: "/price-outlook", label: "Price & Predictions", icon: Brain },
    { href: "/signals", label: "Signals", icon: BarChart3 },
  ]},
  { section: "Regions", items: [
    { href: "/canada", label: "Canada / BC", icon: Globe2 },
    { href: "/scotland", label: "Scotland", icon: Globe2 },
    { href: "/faroe", label: "Faroe Islands", icon: Globe2 },
    { href: "/iceland", label: "Iceland", icon: Globe2 },
    { href: "/china-demand", label: "China Demand", icon: Globe2 },
  ]},
  { section: "Operations", items: [
    { href: "/portfolio", label: "My Portfolio", icon: BriefcaseBusiness },
    { href: "/farmer", label: "Farm Advisory", icon: Anchor },
    { href: "/treatment", label: "Treatment Optimizer", icon: Syringe },
    { href: "/efficacy", label: "Efficacy Market", icon: FlaskConical },
    { href: "/welfare", label: "Fish Welfare", icon: Heart },
    { href: "/harvest", label: "Harvest Optimizer", icon: Timer },
    { href: "/twin", label: "Digital Twin", icon: Boxes },
    { href: "/satellite", label: "Satellite Intel", icon: Satellite },
    { href: "/feed-supply-chain", label: "Feed Supply Chain", icon: Wheat },
    { href: "/command-centre", label: "Command Centre", icon: Radio },
  ]},
  { section: "Advanced", items: [
    { href: "/scenarios-lab", label: "Scenario Lab", icon: Layers },
    { href: "/scenarios", label: "Scenarios", icon: FlaskConical },
    { href: "/causal", label: "Causal Engine", icon: Sigma },
    { href: "/chat", label: "AI Chat", icon: Bot },
    { href: "/ml-baselines", label: "ML Baselines", icon: Sparkles },
    { href: "/ras", label: "RAS Tracker", icon: Factory },
  ]},
  { section: "Compliance", items: [
    { href: "/asc-compliance", label: "ASC Compliance", icon: ShieldCheck },
    { href: "/regulatory-reports", label: "Regulatory Reports", icon: FileCheck },
    { href: "/traceability", label: "EU Traceability", icon: FileCheck },
    { href: "/contracts", label: "Contract Risk", icon: FileText },
    { href: "/insurance", label: "Insurance", icon: Shield },
    { href: "/compliance", label: "Compliance", icon: Shield },
  ]},
  { section: "System", items: [
    { href: "/admin", label: "Admin", icon: ShieldCheck },
    { href: "/api-docs", label: "API Docs", icon: BookOpen },
    { href: "/changelog", label: "Changelog", icon: ScrollText },
    { href: "/billing", label: "Billing", icon: CreditCard },
    { href: "/privacy", label: "Privacy", icon: Shield },
    { href: "/settings", label: "Settings", icon: Settings },
    { href: "/settings/webhooks", label: "Webhooks", icon: Radio },
    { href: "/design-system", label: "Design System", icon: Sparkles },
  ]},
];

/** Flatten all nav items for search indexing */
function flattenNavItems(): (NavItem & { section: string })[] {
  return NAV_SECTIONS.flatMap((group) =>
    group.items.map((item) => ({ ...item, section: group.section }))
  );
}

/** Simple fuzzy match: checks if all characters of query appear in order within text */
function fuzzyMatch(text: string, query: string): { matches: boolean; score: number; indices: number[] } {
  const lower = text.toLowerCase();
  const q = query.toLowerCase();
  const indices: number[] = [];
  let qi = 0;
  for (let i = 0; i < lower.length && qi < q.length; i++) {
    if (lower[i] === q[qi]) {
      indices.push(i);
      qi++;
    }
  }
  if (qi < q.length) return { matches: false, score: 0, indices: [] };
  // Score: prefer consecutive matches and earlier matches
  let score = 100;
  for (let k = 1; k < indices.length; k++) {
    score -= (indices[k] - indices[k - 1] - 1) * 2;
  }
  score -= indices[0] * 3; // penalize late starts
  // Bonus for exact substring
  if (lower.includes(q)) score += 50;
  return { matches: true, score, indices };
}

/** Highlight matched characters in label */
function HighlightedLabel({ label, indices }: { label: string; indices: number[] }) {
  const indexSet = new Set(indices);
  return (
    <span className="truncate">
      {label.split("").map((ch, i) =>
        indexSet.has(i) ? (
          <span key={i} className="text-salmon font-semibold">{ch}</span>
        ) : (
          <span key={i}>{ch}</span>
        )
      )}
    </span>
  );
}

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [hasNewChangelog, setHasNewChangelog] = useState(false);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const pathname = usePathname();
  const router = useRouter();
  const { t } = useTranslation();

  // Check if user has seen the latest changelog
  useEffect(() => {
    try {
      const viewed = localStorage.getItem(CHANGELOG_LS_KEY);
      setHasNewChangelog(viewed !== CHANGELOG_LATEST_VERSION);
    } catch {
      setHasNewChangelog(false);
    }
  }, [pathname]);

  const allItems = useMemo(() => flattenNavItems(), []);

  // Filter and score items based on search query
  const filteredResults = useMemo(() => {
    if (!searchQuery.trim()) return null;
    const results: (NavItem & { section: string; score: number; indices: number[] })[] = [];
    for (const item of allItems) {
      const labelMatch = fuzzyMatch(item.label, searchQuery);
      const sectionMatch = fuzzyMatch(item.section || "Home", searchQuery);
      if (labelMatch.matches) {
        results.push({ ...item, score: labelMatch.score, indices: labelMatch.indices });
      } else if (sectionMatch.matches) {
        results.push({ ...item, score: sectionMatch.score - 20, indices: [] });
      }
    }
    results.sort((a, b) => b.score - a.score);
    return results;
  }, [searchQuery, allItems]);

  // Sections that have matching items (for filtered view)
  const filteredSections = useMemo(() => {
    if (!filteredResults) return null;
    const hrefSet = new Set(filteredResults.map((r) => r.href));
    return NAV_SECTIONS.map((group) => ({
      ...group,
      items: group.items.filter((item) => hrefSet.has(item.href)),
    })).filter((group) => group.items.length > 0);
  }, [filteredResults]);

  // Map href to match indices for highlighting
  const matchIndicesMap = useMemo((): Record<string, number[]> => {
    if (!filteredResults) return {};
    const map: Record<string, number[]> = {};
    for (const r of filteredResults) {
      if (r.indices.length > 0) map[r.href] = r.indices;
    }
    return map;
  }, [filteredResults]);

  // Reset selected index when results change
  useEffect(() => {
    setSelectedIndex(0);
  }, [filteredResults?.length]);

  // Close mobile sidebar on navigation
  useEffect(() => {
    setMobileOpen(false);
    setSearchQuery("");
  }, [pathname]);

  // Listen for focus-sidebar-search custom event (from useKeyboardShortcuts)
  useEffect(() => {
    function handleFocusSearch() {
      if (collapsed) setCollapsed(false);
      setTimeout(() => searchInputRef.current?.focus(), 50);
    }
    window.addEventListener("focus-sidebar-search", handleFocusSearch);
    return () => window.removeEventListener("focus-sidebar-search", handleFocusSearch);
  }, [collapsed]);

  const clearSearch = useCallback(() => {
    setSearchQuery("");
    setSelectedIndex(0);
    searchInputRef.current?.blur();
  }, []);

  // Handle keyboard navigation within search results
  const handleSearchKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        clearSearch();
        return;
      }
      if (!filteredResults || filteredResults.length === 0) return;

      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => Math.min(prev + 1, filteredResults.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) => Math.max(prev - 1, 0));
      } else if (e.key === "Enter") {
        e.preventDefault();
        const target = filteredResults[selectedIndex];
        if (target) {
          router.push(target.href);
          clearSearch();
        }
      }
    },
    [filteredResults, selectedIndex, router, clearSearch]
  );

  const isSearchActive = searchQuery.trim().length > 0;
  const sectionsToRender = filteredSections ?? NAV_SECTIONS;

  return (
    <>
      {/* Mobile hamburger button */}
      <button
        onClick={() => setMobileOpen(true)}
        className="fixed top-4 left-4 z-50 md:hidden p-2 rounded-lg bg-white/90 dark:bg-fjord-midwater/90 border border-slate-200 dark:border-white/[0.08] text-[var(--text-secondary)] hover:text-salmon transition-colors"
        aria-label="Toggle menu"
        aria-expanded={mobileOpen}
      >
        <Menu className="w-5 h-5" />
      </button>

      {/* Mobile overlay backdrop */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setMobileOpen(false)}
            className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm md:hidden"
          />
        )}
      </AnimatePresence>

      <motion.aside
        animate={{ width: collapsed ? 72 : 240 }}
        transition={{ duration: 0.3, ease: "easeInOut" }}
        className={cn(
          "fixed left-0 top-0 h-screen z-50",
          "bg-[var(--sidebar-bg)] dark:bg-gradient-to-b dark:from-fjord-midwater/95 dark:to-fjord-abyss/98 backdrop-blur-xl",
          "border-r border-slate-200 dark:border-white/[0.06]",
          "flex flex-col",
          "shadow-[4px_0_24px_rgba(0,0,0,0.06)] dark:shadow-[4px_0_24px_rgba(0,0,0,0.3)]",
          // Hidden on mobile by default, shown when mobileOpen
          mobileOpen ? "translate-x-0" : "-translate-x-full",
          "md:translate-x-0",
          "transition-transform duration-300 ease-in-out",
        )}
      >
      {/* Mobile close button */}
      <button
        onClick={() => setMobileOpen(false)}
        className="absolute top-4 right-3 z-10 p-1.5 rounded-lg text-[var(--text-secondary)] hover:text-salmon transition-colors md:hidden"
        aria-label="Close navigation"
      >
        <X className="w-4 h-4" />
      </button>

      {/* Logo */}
      <div className="h-16 flex items-center px-5 border-b border-slate-200 dark:border-white/[0.06]">
        <motion.div className="flex items-center gap-3 overflow-hidden">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-salmon to-salmon-600 flex items-center justify-center flex-shrink-0 shadow-[0_0_16px_rgba(232,115,74,0.2)]">
            <span className="text-white font-bold text-sm">FI</span>
          </div>
          <AnimatePresence>
            {!collapsed && (
              <motion.div
                initial={{ opacity: 0, width: 0 }}
                animate={{ opacity: 1, width: "auto" }}
                exit={{ opacity: 0, width: 0 }}
                className="overflow-hidden whitespace-nowrap"
              >
                <h1 className="text-lg font-display text-[var(--text-primary)] tracking-tight">FishIntel</h1>
                <p className="text-[10px] text-salmon/70 -mt-1 font-medium tracking-wide">Aquaculture Intelligence</p>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      </div>

      {/* Search input */}
      <AnimatePresence>
        {!collapsed && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="px-3 pt-3 pb-1"
          >
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400 dark:text-slate-500 pointer-events-none" />
              <input
                ref={searchInputRef}
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={handleSearchKeyDown}
                placeholder={`${t("search.pages")} (\u2318K)`}
                aria-label={t("search.pages")}
                className={cn(
                  "w-full h-8 pl-8 pr-7 text-[12px] rounded-lg outline-none transition-all",
                  "bg-slate-100 dark:bg-slate-800/50",
                  "border border-slate-300 dark:border-slate-700/50",
                  "text-slate-600 dark:text-slate-300",
                  "placeholder:text-slate-400 dark:placeholder:text-slate-500",
                  "focus:border-salmon/40 focus:ring-1 focus:ring-salmon/20",
                )}
              />
              {searchQuery && (
                <button
                  onClick={clearSearch}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-0.5 rounded text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors"
                  aria-label="Clear search"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
            {isSearchActive && filteredResults && (
              <div className="mt-1 text-[10px] text-slate-400 dark:text-slate-500 px-1">
                {filteredResults.length} {filteredResults.length !== 1 ? t("table.results") : t("table.result")}
                {filteredResults.length === 1 && <span className="ml-1 text-slate-300 dark:text-slate-600">&mdash; {t("table.enter_to_go")}</span>}
              </div>
            )}
            {isSearchActive && filteredResults?.length === 0 && (
              <div className="mt-1 text-[10px] text-slate-400 dark:text-slate-500 px-1">
                {t("table.no_results")}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Navigation — grouped sections */}
      <nav className="flex-1 py-3 px-3 overflow-y-auto" role="navigation" aria-label="Main navigation">
        {sectionsToRender.map((group, gi) => (
          <div key={gi} className={cn(group.section && "mt-4 first:mt-0")}>
            {/* Section label */}
            {group.section && !collapsed && (
              <div className="px-3 pb-1.5 pt-1">
                <span className="text-[9px] font-display italic text-salmon/40 uppercase tracking-[0.15em]">
                  {SECTION_KEYS[group.section] ? t(SECTION_KEYS[group.section]) : group.section}
                </span>
              </div>
            )}
            {group.section && collapsed && <div className="mx-3 my-2 border-t border-slate-200 dark:border-white/[0.04]" />}
            <div className="space-y-0.5">
              {group.items.map((item) => {
                const isActive = pathname === item.href;
                const matchIndices = matchIndicesMap[item.href];
                // Track index for keyboard selection in search mode
                const flatIdx = isSearchActive && filteredResults
                  ? filteredResults.findIndex((r) => r.href === item.href)
                  : -1;
                const isSelected = isSearchActive && flatIdx === selectedIndex;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => { if (isSearchActive) clearSearch(); }}
                    aria-current={isActive ? "page" : undefined}
                    className={cn(
                      "relative flex items-center gap-3 px-3 py-2 rounded-lg transition-all duration-200",
                      "text-[13px] font-medium",
                      isActive
                        ? "bg-salmon/[0.08] text-salmon-700 dark:text-salmon-100 shadow-[inset_0_0_0_1px_rgba(232,115,74,0.12),0_2px_8px_rgba(232,115,74,0.06)]"
                        : isSelected
                          ? "bg-slate-200/70 dark:bg-white/[0.08] text-[var(--text-primary)]"
                          : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-slate-100 dark:hover:bg-white/[0.04]",
                    )}
                  >
                    <item.icon className={cn("w-[16px] h-[16px] flex-shrink-0", isActive && "text-salmon")} />
                    <AnimatePresence>
                      {!collapsed && (
                        <motion.span
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          exit={{ opacity: 0 }}
                          className="truncate"
                        >
                          {isSearchActive && matchIndices ? (
                            <HighlightedLabel label={item.label} indices={matchIndices} />
                          ) : (
                            NAV_LABEL_KEYS[item.label] ? t(NAV_LABEL_KEYS[item.label]) : item.label
                          )}
                        </motion.span>
                      )}
                    </AnimatePresence>
                    {/* "What's New" dot for Changelog */}
                    {item.href === "/changelog" && hasNewChangelog && (
                      <span className="ml-auto flex-shrink-0 w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.6)] animate-pulse" title="New updates available" />
                    )}
                    {isActive && (
                      <motion.div
                        layoutId="nav-indicator"
                        className="absolute left-0 w-[3px] h-5 rounded-r-full bg-salmon shadow-[0_0_8px_rgba(232,115,74,0.4)]"
                      />
                    )}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Collapse toggle */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="h-12 flex items-center justify-center border-t border-slate-200 dark:border-white/[0.06] text-[var(--text-secondary)] hover:text-salmon transition-colors"
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
      </button>

      {/* Attribution */}
      {!collapsed && (
        <>
          <div className="px-5 pb-1 opacity-20">
            <svg viewBox="0 0 180 20" className="w-full h-4 text-salmon/30">
              <path d="M0 15 Q30 5 60 12 T120 8 T180 14" fill="none" stroke="currentColor" strokeWidth="0.5" />
              <path d="M0 18 Q40 10 80 16 T160 11 T180 17" fill="none" stroke="currentColor" strokeWidth="0.3" opacity="0.5" />
            </svg>
          </div>
          <div className="px-5 py-3 border-t border-slate-200 dark:border-white/[0.06]">
            <p className="text-[9px] text-[var(--text-secondary)] leading-relaxed opacity-60">
              Data: BarentsWatch / NLOD 2.0
            </p>
          </div>
        </>
      )}
    </motion.aside>
    </>
  );
}
