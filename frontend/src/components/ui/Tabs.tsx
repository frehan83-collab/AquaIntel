"use client";
import {
  createContext,
  useContext,
  useId,
  useRef,
  useCallback,
  type ReactNode,
  type ButtonHTMLAttributes,
  type HTMLAttributes,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";
import { cn } from "@/lib/utils";

/* ─────────────────────────────────────────────────────────────────
 * Tabs primitive — accessible tab system
 * Subcomponents: Tabs | TabList | Tab | TabPanels | TabPanel
 * Keyboard: Arrow keys, Home, End move between tabs
 * ARIA: role="tablist", role="tab", role="tabpanel", aria-selected, aria-controls
 * ───────────────────────────────────────────────────────────────── */

interface TabsContextValue {
  value: string;
  setValue: (v: string) => void;
  baseId: string;
}

const TabsContext = createContext<TabsContextValue | null>(null);

function useTabsContext(component: string): TabsContextValue {
  const ctx = useContext(TabsContext);
  if (!ctx) {
    throw new Error(`<${component}> must be used inside <Tabs>`);
  }
  return ctx;
}

// ── Tabs root ────────────────────────────────────────────────────

export interface TabsProps extends Omit<HTMLAttributes<HTMLDivElement>, "onChange"> {
  /** The active tab value (controlled) */
  value: string;
  /** Called when the active tab changes */
  onChange: (value: string) => void;
  children?: ReactNode;
  className?: string;
}

/**
 * Tabs — accessible tab system. Controlled via `value` + `onChange`.
 *
 * @example
 * const [tab, setTab] = useState("a");
 * <Tabs value={tab} onChange={setTab}>
 *   <TabList>
 *     <Tab value="a">One</Tab>
 *     <Tab value="b">Two</Tab>
 *   </TabList>
 *   <TabPanels>
 *     <TabPanel value="a">Panel A</TabPanel>
 *     <TabPanel value="b">Panel B</TabPanel>
 *   </TabPanels>
 * </Tabs>
 */
export function Tabs({ value, onChange, children, className, ...props }: TabsProps) {
  const baseId = useId();
  const ctx: TabsContextValue = {
    value,
    setValue: onChange,
    baseId,
  };
  return (
    <TabsContext.Provider value={ctx}>
      <div className={cn("flex flex-col gap-4", className)} {...props}>
        {children}
      </div>
    </TabsContext.Provider>
  );
}

// ── TabList ──────────────────────────────────────────────────────

export interface TabListProps extends HTMLAttributes<HTMLDivElement> {
  /** Accessible label for the tab list */
  "aria-label"?: string;
  children?: ReactNode;
  className?: string;
}

export function TabList({ className, children, ...props }: TabListProps) {
  const listRef = useRef<HTMLDivElement | null>(null);

  const handleKeyDown = useCallback((e: ReactKeyboardEvent<HTMLDivElement>) => {
    const list = listRef.current;
    if (!list) return;
    const tabs = Array.from(list.querySelectorAll<HTMLButtonElement>('[role="tab"]:not([disabled])'));
    if (tabs.length === 0) return;

    const currentIndex = tabs.findIndex((t) => t === document.activeElement);
    let nextIndex = currentIndex;

    switch (e.key) {
      case "ArrowRight":
      case "ArrowDown":
        e.preventDefault();
        nextIndex = currentIndex < 0 ? 0 : (currentIndex + 1) % tabs.length;
        break;
      case "ArrowLeft":
      case "ArrowUp":
        e.preventDefault();
        nextIndex = currentIndex < 0 ? tabs.length - 1 : (currentIndex - 1 + tabs.length) % tabs.length;
        break;
      case "Home":
        e.preventDefault();
        nextIndex = 0;
        break;
      case "End":
        e.preventDefault();
        nextIndex = tabs.length - 1;
        break;
      default:
        return;
    }

    const nextTab = tabs[nextIndex];
    if (nextTab) {
      nextTab.focus();
      nextTab.click();
    }
  }, []);

  return (
    <div
      ref={listRef}
      role="tablist"
      onKeyDown={handleKeyDown}
      className={cn(
        "inline-flex items-center gap-1 p-1",
        "bg-slate-100 dark:bg-white/[0.04]",
        "border border-slate-200 dark:border-white/[0.06]",
        "rounded-lg",
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}

// ── Tab ──────────────────────────────────────────────────────────

export interface TabProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "value"> {
  /** The unique value of this tab (matches value on TabPanel) */
  value: string;
  children?: ReactNode;
  className?: string;
}

export function Tab({ value, className, children, onClick, ...props }: TabProps) {
  const { value: active, setValue, baseId } = useTabsContext("Tab");
  const isActive = active === value;
  const tabId = `${baseId}-tab-${value}`;
  const panelId = `${baseId}-panel-${value}`;

  return (
    <button
      type="button"
      role="tab"
      id={tabId}
      aria-selected={isActive}
      aria-controls={panelId}
      tabIndex={isActive ? 0 : -1}
      onClick={(e) => {
        setValue(value);
        onClick?.(e);
      }}
      className={cn(
        "inline-flex items-center justify-center gap-1.5",
        "px-3 py-1.5 rounded-md",
        "text-sm font-medium",
        "transition-colors duration-150",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ocean-400/60",
        isActive
          ? "bg-white dark:bg-white/[0.08] text-[var(--text-primary)] shadow-sm"
          : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-white/50 dark:hover:bg-white/[0.04]",
        "disabled:opacity-40 disabled:cursor-not-allowed",
        className
      )}
      {...props}
    >
      {children}
    </button>
  );
}

// ── TabPanels ────────────────────────────────────────────────────

export interface TabPanelsProps extends HTMLAttributes<HTMLDivElement> {
  children?: ReactNode;
  className?: string;
}

export function TabPanels({ className, children, ...props }: TabPanelsProps) {
  return (
    <div className={cn("relative", className)} {...props}>
      {children}
    </div>
  );
}

// ── TabPanel ─────────────────────────────────────────────────────

export interface TabPanelProps extends HTMLAttributes<HTMLDivElement> {
  /** Matches the value on the corresponding Tab */
  value: string;
  children?: ReactNode;
  className?: string;
}

export function TabPanel({ value, className, children, ...props }: TabPanelProps) {
  const { value: active, baseId } = useTabsContext("TabPanel");
  const isActive = active === value;
  const tabId = `${baseId}-tab-${value}`;
  const panelId = `${baseId}-panel-${value}`;

  if (!isActive) return null;

  return (
    <div
      role="tabpanel"
      id={panelId}
      aria-labelledby={tabId}
      tabIndex={0}
      className={cn("focus-visible:outline-none", className)}
      {...props}
    >
      {children}
    </div>
  );
}

export default Tabs;
