import { forwardRef, type HTMLAttributes, type ReactNode } from "react";
import { cn } from "@/lib/utils";

/* ─────────────────────────────────────────────────────────────────
 * Badge primitive — status chip
 * 6 variants: default | success | warning | danger | info | brand
 * 2 sizes: sm | md
 * Optional leading colored dot
 * ───────────────────────────────────────────────────────────────── */

export type BadgeVariant = "default" | "success" | "warning" | "danger" | "info" | "brand";
export type BadgeSize = "sm" | "md";

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  /** Visual variant (semantic color) */
  variant?: BadgeVariant;
  /** Size variant */
  size?: BadgeSize;
  /** Show a leading colored dot */
  dot?: boolean;
  className?: string;
  children?: ReactNode;
}

const VARIANT_CLASSES: Record<BadgeVariant, { bg: string; text: string; border: string; dot: string }> = {
  default: {
    bg: "bg-slate-500/10 dark:bg-white/[0.06]",
    text: "text-[var(--text-secondary)]",
    border: "border-[var(--border)]",
    dot: "bg-slate-400",
  },
  success: {
    bg: "bg-[var(--success)]/10",
    text: "text-[var(--success)]",
    border: "border-[var(--success)]/20",
    dot: "bg-[var(--success)]",
  },
  warning: {
    bg: "bg-[var(--warning)]/10",
    text: "text-[var(--warning)]",
    border: "border-[var(--warning)]/20",
    dot: "bg-[var(--warning)]",
  },
  danger: {
    bg: "bg-[var(--danger)]/10",
    text: "text-[var(--danger)]",
    border: "border-[var(--danger)]/20",
    dot: "bg-[var(--danger)]",
  },
  info: {
    bg: "bg-blue-500/10 dark:bg-blue-500/15",
    text: "text-blue-600 dark:text-blue-400",
    border: "border-blue-500/20",
    dot: "bg-blue-500",
  },
  brand: {
    bg: "bg-ocean-500/10",
    text: "text-ocean-600 dark:text-ocean-400",
    border: "border-ocean-500/20",
    dot: "bg-ocean-500",
  },
};

const SIZE_CLASSES: Record<BadgeSize, { padding: string; text: string; dot: string; gap: string }> = {
  sm: {
    padding: "px-2 py-0.5",
    text: "text-[10px]",
    dot: "w-1.5 h-1.5",
    gap: "gap-1",
  },
  md: {
    padding: "px-2.5 py-0.5",
    text: "text-xs",
    dot: "w-2 h-2",
    gap: "gap-1.5",
  },
};

/**
 * Badge — semantic status chip. Use for labels, statuses, tags.
 * Optional leading dot for live/status indicators.
 *
 * @example
 * <Badge variant="success">Live</Badge>
 * <Badge variant="danger" dot>Critical</Badge>
 * <Badge variant="brand" size="md">Pro</Badge>
 */
const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ variant = "default", size = "sm", dot = false, className, children, ...props }, ref) => {
    const v = VARIANT_CLASSES[variant];
    const sz = SIZE_CLASSES[size];

    return (
      <span
        ref={ref}
        className={cn(
          "inline-flex items-center rounded-full border font-medium whitespace-nowrap",
          v.bg,
          v.text,
          v.border,
          sz.padding,
          sz.text,
          sz.gap,
          className
        )}
        {...props}
      >
        {dot && (
          <span
            aria-hidden="true"
            className={cn("rounded-full", v.dot, sz.dot)}
          />
        )}
        {children}
      </span>
    );
  }
);

Badge.displayName = "Badge";

export { Badge };
export default Badge;
