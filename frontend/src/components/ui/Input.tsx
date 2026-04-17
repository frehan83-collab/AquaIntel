import { forwardRef, useId, type InputHTMLAttributes, type ReactNode } from "react";
import { cn } from "@/lib/utils";

/* ─────────────────────────────────────────────────────────────────
 * Input primitive — form input with label, hint, error, icon slots
 * States: default | hover | focus | error | disabled
 * Sizes: sm (h-8) | md (h-10)
 * ───────────────────────────────────────────────────────────────── */

export type InputSize = "sm" | "md";

export interface InputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "size"> {
  /** Visible label rendered above the input, linked via htmlFor */
  label?: ReactNode;
  /** Validation error message (red text below input); sets aria-invalid */
  error?: string;
  /** Helper text shown below input when no error */
  hint?: string;
  /** Size variant */
  size?: InputSize;
  /** Icon slot rendered inside the input, on the left */
  leftIcon?: ReactNode;
  /** Icon slot rendered inside the input, on the right */
  rightIcon?: ReactNode;
  className?: string;
  /** Optional class applied to the wrapper (label + input + hint block) */
  wrapperClassName?: string;
}

const SIZE_CLASSES: Record<InputSize, { input: string; text: string; iconPad: { left: string; right: string } }> = {
  sm: {
    input: "h-8 px-2.5 rounded-md",
    text: "text-xs",
    iconPad: { left: "pl-8", right: "pr-8" },
  },
  md: {
    input: "h-10 px-3 rounded-lg",
    text: "text-sm",
    iconPad: { left: "pl-10", right: "pr-10" },
  },
};

/**
 * Input — accessible form input primitive. Uses `<label htmlFor>` for a11y,
 * supports left/right icon slots, error/hint states, and sm/md sizing.
 *
 * @example
 * <Input label="Farm name" hint="Enter the locality ID" />
 * <Input label="Email" error="Invalid address" type="email" />
 */
const Input = forwardRef<HTMLInputElement, InputProps>(
  (
    {
      label,
      error,
      hint,
      size = "md",
      leftIcon,
      rightIcon,
      className,
      wrapperClassName,
      id,
      disabled,
      "aria-describedby": ariaDescribedBy,
      ...props
    },
    ref
  ) => {
    const reactId = useId();
    const inputId = id ?? `input-${reactId}`;
    const descId = `${inputId}-desc`;
    const sz = SIZE_CLASSES[size];
    const hasError = Boolean(error);

    const describedBy = [ariaDescribedBy, (error || hint) ? descId : null]
      .filter(Boolean)
      .join(" ") || undefined;

    return (
      <div className={cn("flex flex-col gap-1.5", wrapperClassName)}>
        {label && (
          <label
            htmlFor={inputId}
            className={cn(
              "font-medium text-[var(--text-primary)]",
              size === "sm" ? "text-xs" : "text-sm"
            )}
          >
            {label}
          </label>
        )}

        <div className="relative">
          {leftIcon && (
            <span
              aria-hidden="true"
              className={cn(
                "absolute inset-y-0 flex items-center pointer-events-none text-[var(--text-secondary)]",
                size === "sm" ? "left-2" : "left-3"
              )}
            >
              {leftIcon}
            </span>
          )}

          <input
            ref={ref}
            id={inputId}
            disabled={disabled}
            aria-invalid={hasError || undefined}
            aria-describedby={describedBy}
            className={cn(
              "w-full",
              sz.input,
              sz.text,
              "bg-white dark:bg-white/[0.04]",
              "border",
              "text-[var(--text-primary)] placeholder:text-[var(--text-secondary)]",
              "transition-colors duration-150",
              "outline-none",
              // Default border
              !hasError && "border-slate-200 dark:border-white/[0.08]",
              // Hover
              !hasError && !disabled && "hover:border-slate-300 dark:hover:border-white/[0.16]",
              // Focus
              !hasError && "focus:border-ocean-400 focus:ring-2 focus:ring-ocean-400/30",
              // Error
              hasError && "border-[var(--danger)] focus:ring-2 focus:ring-[var(--danger)]/30",
              // Disabled
              disabled && "opacity-50 cursor-not-allowed bg-slate-50 dark:bg-white/[0.02]",
              // Icon padding
              leftIcon && sz.iconPad.left,
              rightIcon && sz.iconPad.right,
              className
            )}
            {...props}
          />

          {rightIcon && (
            <span
              aria-hidden="true"
              className={cn(
                "absolute inset-y-0 flex items-center pointer-events-none text-[var(--text-secondary)]",
                size === "sm" ? "right-2" : "right-3"
              )}
            >
              {rightIcon}
            </span>
          )}
        </div>

        {(error || hint) && (
          <p
            id={descId}
            className={cn(
              "text-xs",
              hasError ? "text-[var(--danger)]" : "text-[var(--text-secondary)]"
            )}
          >
            {error || hint}
          </p>
        )}
      </div>
    );
  }
);

Input.displayName = "Input";

export { Input };
export default Input;
