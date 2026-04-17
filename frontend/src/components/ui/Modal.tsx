"use client";
import {
  useEffect,
  useId,
  useRef,
  useCallback,
  type ReactNode,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";

/* ─────────────────────────────────────────────────────────────────
 * Modal primitive — accessible dialog
 * Features: focus trap, ESC to close, scroll-lock, framer-motion transitions
 * role="dialog", aria-modal, aria-labelledby
 * Sizes: sm (max-w-sm) | md (max-w-lg) | lg (max-w-2xl) | xl (max-w-4xl)
 * ───────────────────────────────────────────────────────────────── */

export type ModalSize = "sm" | "md" | "lg" | "xl";

export interface ModalProps {
  /** Controls visibility */
  open: boolean;
  /** Called when user dismisses via backdrop click, ESC, or close button */
  onClose: () => void;
  /** Optional title rendered in the dialog header (also used for aria-labelledby) */
  title?: ReactNode;
  /** Max-width tier */
  size?: ModalSize;
  /** Dialog body content */
  children?: ReactNode;
  /** Optional className applied to the dialog panel */
  className?: string;
  /** Disable closing via backdrop click (ESC still works) */
  disableBackdropClose?: boolean;
}

const SIZE_CLASSES: Record<ModalSize, string> = {
  sm: "max-w-sm",
  md: "max-w-lg",
  lg: "max-w-2xl",
  xl: "max-w-4xl",
};

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  '[tabindex]:not([tabindex="-1"])',
].join(",");

/**
 * Modal — accessible dialog with focus trap, ESC-to-close, and body scroll lock.
 * Uses framer-motion for enter/exit. Restores focus to the previously-focused
 * element on close.
 *
 * @example
 * <Modal open={open} onClose={() => setOpen(false)} title="Confirm">
 *   <p>Are you sure?</p>
 * </Modal>
 */
export default function Modal({
  open,
  onClose,
  title,
  size = "md",
  children,
  className,
  disableBackdropClose = false,
}: ModalProps) {
  const panelRef = useRef<HTMLDivElement | null>(null);
  const lastFocusedRef = useRef<HTMLElement | null>(null);
  const reactId = useId();
  const titleId = title ? `modal-title-${reactId}` : undefined;

  // Scroll-lock the body while open and restore focus on close
  useEffect(() => {
    if (!open) return;

    // Save the element that had focus before the modal opened
    lastFocusedRef.current = (typeof document !== "undefined"
      ? (document.activeElement as HTMLElement | null)
      : null);

    const prevOverflow = typeof document !== "undefined" ? document.body.style.overflow : "";
    if (typeof document !== "undefined") {
      document.body.style.overflow = "hidden";
    }

    // Focus the first focusable element in the panel (or panel itself)
    const focusTimer = window.setTimeout(() => {
      const panel = panelRef.current;
      if (!panel) return;
      const focusables = panel.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
      if (focusables.length > 0) {
        focusables[0].focus();
      } else {
        panel.focus();
      }
    }, 0);

    return () => {
      window.clearTimeout(focusTimer);
      if (typeof document !== "undefined") {
        document.body.style.overflow = prevOverflow;
      }
      // Restore focus to the previously focused element
      if (lastFocusedRef.current && typeof lastFocusedRef.current.focus === "function") {
        lastFocusedRef.current.focus();
      }
    };
  }, [open]);

  // ESC to close + Tab focus trap
  const handleKeyDown = useCallback(
    (e: ReactKeyboardEvent<HTMLDivElement>) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
        return;
      }
      if (e.key !== "Tab") return;
      const panel = panelRef.current;
      if (!panel) return;

      const focusables = Array.from(
        panel.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)
      ).filter((el) => !el.hasAttribute("disabled"));

      if (focusables.length === 0) {
        e.preventDefault();
        panel.focus();
        return;
      }

      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const active = document.activeElement as HTMLElement | null;

      if (e.shiftKey) {
        if (active === first || !panel.contains(active)) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (active === last) {
          e.preventDefault();
          first.focus();
        }
      }
    },
    [onClose]
  );

  const handleBackdropClick = useCallback(() => {
    if (!disableBackdropClose) onClose();
  }, [disableBackdropClose, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <div
          className="fixed inset-0 z-[1000] flex items-center justify-center p-4"
          onKeyDown={handleKeyDown}
        >
          {/* Backdrop */}
          <motion.div
            key="backdrop"
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            onClick={handleBackdropClick}
            aria-hidden="true"
          />

          {/* Dialog panel */}
          <motion.div
            key="panel"
            ref={panelRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            tabIndex={-1}
            initial={{ opacity: 0, scale: 0.96, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 8 }}
            transition={{ duration: 0.18, ease: [0.25, 0.46, 0.45, 0.94] }}
            className={cn(
              "relative w-full",
              SIZE_CLASSES[size],
              "bg-white dark:bg-fjord-surface",
              "border border-slate-200 dark:border-white/[0.08]",
              "rounded-2xl",
              "shadow-2xl dark:shadow-[0_24px_80px_rgba(0,0,0,0.6)]",
              "outline-none",
              "max-h-[90vh] overflow-auto",
              className
            )}
          >
            {title && (
              <div className="flex items-center justify-between gap-4 px-6 py-4 border-b border-slate-200 dark:border-white/[0.08]">
                <h2
                  id={titleId}
                  className="text-lg font-semibold text-[var(--text-primary)]"
                >
                  {title}
                </h2>
                <button
                  type="button"
                  onClick={onClose}
                  aria-label="Close dialog"
                  className={cn(
                    "inline-flex items-center justify-center",
                    "h-8 w-8 rounded-lg",
                    "text-[var(--text-secondary)]",
                    "hover:bg-slate-100 dark:hover:bg-white/[0.06]",
                    "hover:text-[var(--text-primary)]",
                    "transition-colors",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ocean-400/60"
                  )}
                >
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden="true"
                  >
                    <line x1="18" y1="6" x2="6" y2="18" />
                    <line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                </button>
              </div>
            )}
            <div className={cn(title ? "px-6 py-4" : "p-6")}>{children}</div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}

export { Modal };
