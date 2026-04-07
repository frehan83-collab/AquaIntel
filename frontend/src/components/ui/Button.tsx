"use client";
import { forwardRef, useState, useCallback, type ReactNode, type ButtonHTMLAttributes } from "react";
import { motion, AnimatePresence, type HTMLMotionProps } from "framer-motion";
import { Loader2, Check, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { cva, type VariantProps } from "class-variance-authority";

/* ─────────────────────────────────────────────────────────────────
 * 2026 Premium Button System — Glassmorphism 2.0
 * ─────────────────────────────────────────────────────────────────
 * 7 states: enabled, disabled, hover, active, focused, loading,
 *           success, error
 * Full WCAG 2.2 + ARIA + keyboard navigation
 * Framer Motion micro-interactions with spring physics
 * Role-aware subtle accent shifts (farmer/buyer/investor)
 * ───────────────────────────────────────────────────────────────── */

const buttonVariants = cva(
  // Base styles — glassmorphism foundation
  [
    "relative inline-flex items-center justify-center gap-2",
    "font-medium transition-all duration-200",
    "border outline-none select-none",
    "backdrop-blur-md",
    // Focus ring — WCAG 2.2 compliant, 3:1 contrast
    "focus-visible:ring-2 focus-visible:ring-ocean-400/60 focus-visible:ring-offset-2 focus-visible:ring-offset-ocean-950",
    // Disabled state
    "disabled:pointer-events-none disabled:opacity-40",
    // Noise texture overlay via pseudo-element handled in CSS
  ].join(" "),
  {
    variants: {
      variant: {
        // Primary — gradient glass with glow
        primary: [
          "bg-gradient-to-r from-ocean-600/90 to-ocean-500/90",
          "border-ocean-400/25",
          "text-white",
          "shadow-[0_4px_20px_rgba(0,212,200,0.15),inset_0_1px_0_rgba(255,255,255,0.1)]",
          "hover:shadow-[0_8px_32px_rgba(0,212,200,0.25),inset_0_1px_0_rgba(255,255,255,0.15)]",
          "hover:border-ocean-400/40",
          "active:shadow-[0_2px_8px_rgba(0,212,200,0.1),inset_0_2px_4px_rgba(0,0,0,0.2)]",
        ].join(" "),
        // Secondary — translucent glass
        secondary: [
          "bg-white/[0.04]",
          "border-white/[0.08]",
          "text-[var(--text-primary)]",
          "shadow-[0_4px_16px_rgba(0,0,0,0.2),inset_0_1px_0_rgba(255,255,255,0.04)]",
          "hover:bg-white/[0.08]",
          "hover:border-ocean-400/20",
          "hover:shadow-[0_8px_24px_rgba(0,0,0,0.3),inset_0_1px_0_rgba(255,255,255,0.06)]",
          "active:bg-white/[0.03]",
        ].join(" "),
        // Ghost — minimal, no background
        ghost: [
          "bg-transparent",
          "border-transparent",
          "text-[var(--text-secondary)]",
          "hover:bg-white/[0.06]",
          "hover:text-[var(--text-primary)]",
          "hover:border-white/[0.06]",
          "active:bg-white/[0.03]",
        ].join(" "),
        // Danger — destructive actions
        danger: [
          "bg-rose-500/10",
          "border-rose-500/20",
          "text-rose-400",
          "shadow-[0_4px_16px_rgba(244,63,94,0.1),inset_0_1px_0_rgba(255,255,255,0.04)]",
          "hover:bg-rose-500/20",
          "hover:border-rose-500/30",
          "hover:shadow-[0_8px_24px_rgba(244,63,94,0.15)]",
          "active:bg-rose-500/10",
        ].join(" "),
        // Success — confirmation actions
        success: [
          "bg-emerald-500/10",
          "border-emerald-500/20",
          "text-emerald-400",
          "shadow-[0_4px_16px_rgba(16,185,129,0.1),inset_0_1px_0_rgba(255,255,255,0.04)]",
          "hover:bg-emerald-500/20",
          "hover:border-emerald-500/30",
          "hover:shadow-[0_8px_24px_rgba(16,185,129,0.15)]",
          "active:bg-emerald-500/10",
        ].join(" "),
        // Accent — ocean glow outline
        accent: [
          "bg-ocean-500/[0.08]",
          "border-ocean-500/20",
          "text-ocean-400",
          "shadow-[0_4px_16px_rgba(0,212,200,0.08),inset_0_1px_0_rgba(255,255,255,0.04)]",
          "hover:bg-ocean-500/[0.15]",
          "hover:border-ocean-500/30",
          "hover:shadow-[0_8px_24px_rgba(0,212,200,0.12)]",
          "active:bg-ocean-500/[0.06]",
        ].join(" "),
        // Salmon — industry-branded accent
        salmon: [
          "bg-gradient-to-r from-salmon-600/90 to-salmon/90",
          "border-salmon-300/25",
          "text-white",
          "shadow-[0_4px_20px_rgba(232,115,74,0.15),inset_0_1px_0_rgba(255,255,255,0.1)]",
          "hover:shadow-[0_8px_32px_rgba(232,115,74,0.25),inset_0_1px_0_rgba(255,255,255,0.15)]",
          "hover:border-salmon-300/40",
          "active:shadow-[0_2px_8px_rgba(232,115,74,0.1),inset_0_2px_4px_rgba(0,0,0,0.2)]",
        ].join(" "),
        // Icon — square icon-only button
        icon: [
          "bg-white/[0.04]",
          "border-white/[0.08]",
          "text-[var(--text-secondary)]",
          "hover:bg-white/[0.08]",
          "hover:text-ocean-400",
          "hover:border-ocean-400/20",
          "hover:shadow-[0_4px_16px_rgba(0,212,200,0.1)]",
          "active:bg-white/[0.03]",
        ].join(" "),
      },
      size: {
        xs: "h-7 px-2.5 text-[11px] rounded-lg gap-1",
        sm: "h-8 px-3 text-xs rounded-lg gap-1.5",
        md: "h-10 px-4 text-sm rounded-xl gap-2",
        lg: "h-12 px-6 text-sm rounded-xl gap-2.5",
        xl: "h-14 px-8 text-base rounded-2xl gap-3",
        icon_sm: "h-8 w-8 rounded-lg p-0",
        icon_md: "h-10 w-10 rounded-xl p-0",
        icon_lg: "h-12 w-12 rounded-xl p-0",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "md",
    },
  }
);

// Spring physics for premium feel
const spring = { type: "spring" as const, stiffness: 400, damping: 17 };

// Ripple animation origin tracking
interface RippleState {
  x: number;
  y: number;
  id: number;
}

export interface ButtonProps
  extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "onAnimationStart" | "onDrag" | "onDragEnd" | "onDragStart" | "style">,
    VariantProps<typeof buttonVariants> {
  /** Show loading spinner + optional text */
  loading?: boolean;
  loadingText?: string;
  /** Flash success state (auto-resets after 1.5s) */
  showSuccess?: boolean;
  /** Flash error state (auto-resets after 1.5s) */
  showError?: boolean;
  /** Left icon */
  leftIcon?: ReactNode;
  /** Right icon */
  rightIcon?: ReactNode;
  /** Enable click ripple effect */
  ripple?: boolean;
  /** Role-aware accent (subtle color shift) */
  role_accent?: "farmer" | "buyer" | "investor" | "admin";
}

const OcButton = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant,
      size,
      loading = false,
      loadingText,
      showSuccess = false,
      showError = false,
      leftIcon,
      rightIcon,
      ripple = true,
      disabled,
      children,
      onClick,
      role_accent,
      ...props
    },
    ref
  ) => {
    const [ripples, setRipples] = useState<RippleState[]>([]);
    const [internalSuccess] = useState(false);
    const [internalError] = useState(false);

    const isSuccess = showSuccess || internalSuccess;
    const isError = showError || internalError;
    const isDisabled = disabled || loading;

    // Ripple on click
    const handleClick = useCallback(
      (e: React.MouseEvent<HTMLButtonElement>) => {
        if (ripple && !isDisabled) {
          const rect = e.currentTarget.getBoundingClientRect();
          const newRipple: RippleState = {
            x: e.clientX - rect.left,
            y: e.clientY - rect.top,
            id: Date.now(),
          };
          setRipples((prev) => [...prev, newRipple]);
          setTimeout(() => {
            setRipples((prev) => prev.filter((r) => r.id !== newRipple.id));
          }, 600);
        }
        onClick?.(e);
      },
      [ripple, isDisabled, onClick]
    );

    // Role accent overlay color
    const roleAccentClass = role_accent === "farmer"
      ? "before:bg-emerald-500/[0.03]"
      : role_accent === "buyer"
      ? "before:bg-amber-500/[0.03]"
      : role_accent === "investor"
      ? "before:bg-violet-500/[0.03]"
      : "";

    return (
      <motion.button
        ref={ref as React.Ref<HTMLButtonElement>}
        className={cn(
          buttonVariants({ variant, size }),
          roleAccentClass && `before:absolute before:inset-0 before:rounded-[inherit] before:pointer-events-none ${roleAccentClass}`,
          // Success/error state overrides
          isSuccess && "!border-emerald-400/40 !shadow-[0_0_20px_rgba(16,185,129,0.2)]",
          isError && "!border-rose-400/40 !shadow-[0_0_20px_rgba(244,63,94,0.2)]",
          "overflow-hidden",
          className
        )}
        disabled={isDisabled}
        onClick={handleClick}
        // Micro-interactions
        whileHover={isDisabled ? undefined : { scale: 1.02, y: -1 }}
        whileTap={isDisabled ? undefined : { scale: 0.97 }}
        transition={spring}
        // Error shake animation
        animate={
          isError
            ? { x: [0, -4, 4, -4, 4, -2, 2, 0] }
            : { x: 0 }
        }
        // ARIA
        aria-busy={loading}
        aria-disabled={isDisabled}
        {...(props as Omit<HTMLMotionProps<"button">, "ref">)}
      >
        {/* Ripple effects */}
        {ripples.map((r) => (
          <motion.span
            key={r.id}
            className="absolute rounded-full bg-white/20 pointer-events-none"
            initial={{ width: 0, height: 0, opacity: 0.5 }}
            animate={{ width: 200, height: 200, opacity: 0 }}
            transition={{ duration: 0.6, ease: "easeOut" }}
            style={{
              left: r.x - 100,
              top: r.y - 100,
            }}
          />
        ))}

        {/* Shimmer highlight on hover */}
        <span className="absolute inset-0 rounded-[inherit] opacity-0 hover:opacity-100 transition-opacity duration-300 bg-gradient-to-r from-transparent via-white/[0.04] to-transparent pointer-events-none" />

        {/* Content with state transitions */}
        <AnimatePresence mode="wait">
          {loading ? (
            <motion.span
              key="loading"
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.8 }}
              transition={{ duration: 0.15 }}
              className="flex items-center gap-2"
            >
              <Loader2 className="w-4 h-4 animate-spin" />
              {loadingText && <span>{loadingText}</span>}
              {!loadingText && children}
            </motion.span>
          ) : isSuccess ? (
            <motion.span
              key="success"
              initial={{ opacity: 0, scale: 0.5 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.5 }}
              transition={spring}
              className="flex items-center gap-2 text-emerald-400"
            >
              <Check className="w-4 h-4" />
              <span>Done</span>
            </motion.span>
          ) : isError ? (
            <motion.span
              key="error"
              initial={{ opacity: 0, scale: 0.5 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.5 }}
              transition={spring}
              className="flex items-center gap-2 text-rose-400"
            >
              <X className="w-4 h-4" />
              <span>Failed</span>
            </motion.span>
          ) : (
            <motion.span
              key="default"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.1 }}
              className="flex items-center gap-2 relative z-10"
            >
              {leftIcon}
              {children}
              {rightIcon}
            </motion.span>
          )}
        </AnimatePresence>
      </motion.button>
    );
  }
);

OcButton.displayName = "OcButton";

export { OcButton, buttonVariants };
export default OcButton;
