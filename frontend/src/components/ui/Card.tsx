import { forwardRef, type HTMLAttributes, type ReactNode } from "react";
import { cn } from "@/lib/utils";

/* ─────────────────────────────────────────────────────────────────
 * Card primitive — replaces GlassCard + inline card divs
 * 5 variants: default | glass | elevated | outlined | muted
 * Padding scale: none | sm | md | lg
 * ───────────────────────────────────────────────────────────────── */

export type CardVariant = "default" | "glass" | "elevated" | "outlined" | "muted";
export type CardPadding = "none" | "sm" | "md" | "lg";

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  /** Visual variant — default (surface-1 + border), glass (backdrop-blur), elevated (surface-2 + shadow), outlined (transparent + border), muted (surface-0) */
  variant?: CardVariant;
  /** Internal padding scale */
  padding?: CardPadding;
  className?: string;
  children?: ReactNode;
}

const VARIANT_CLASSES: Record<CardVariant, string> = {
  default: cn(
    "bg-surface-1",
    "border border-slate-200 dark:border-white/[0.08]",
    "rounded-2xl",
  ),
  glass: cn(
    "bg-white/60 dark:bg-white/[0.04]",
    "backdrop-blur-md",
    "border border-slate-200 dark:border-white/[0.08]",
    "rounded-2xl",
    "shadow-sm dark:shadow-[0_8px_32px_rgba(0,0,0,0.3),inset_0_1px_0_rgba(255,255,255,0.03)]",
  ),
  elevated: cn(
    "bg-surface-2",
    "border border-slate-200 dark:border-white/[0.08]",
    "rounded-2xl",
    "shadow-panel",
  ),
  outlined: cn(
    "bg-transparent",
    "border border-slate-200 dark:border-white/[0.08]",
    "rounded-2xl",
  ),
  muted: cn(
    "bg-surface-0",
    "border border-transparent",
    "rounded-2xl",
  ),
};

const PADDING_CLASSES: Record<CardPadding, string> = {
  none: "p-0",
  sm: "p-3",
  md: "p-4",
  lg: "p-6",
};

/**
 * Card — base container primitive. Use for panels, content grouping, and as a
 * replacement for inline `<div className="bg-surface-1 border ...">` patterns.
 *
 * @example
 * <Card variant="glass" padding="md">Panel content</Card>
 */
const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ variant = "default", padding = "md", className, children, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(VARIANT_CLASSES[variant], PADDING_CLASSES[padding], className)}
        {...props}
      >
        {children}
      </div>
    );
  }
);

Card.displayName = "Card";

export { Card };
export default Card;
