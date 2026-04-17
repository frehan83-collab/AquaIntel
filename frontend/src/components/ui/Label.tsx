import { forwardRef, type LabelHTMLAttributes, type ReactNode } from "react";
import { cn } from "@/lib/utils";

/* ─────────────────────────────────────────────────────────────────
 * Label primitive — form field label with optional required indicator
 * ───────────────────────────────────────────────────────────────── */

export interface LabelProps extends LabelHTMLAttributes<HTMLLabelElement> {
  /** The id of the form control this label is associated with (for a11y) */
  htmlFor?: string;
  /** When true, renders a red asterisk after the label text */
  required?: boolean;
  className?: string;
  children?: ReactNode;
}

/**
 * Label — accessible form label. Pair with form controls via `htmlFor`.
 * When `required` is true, a red asterisk is shown with aria-hidden so screen
 * readers rely on the underlying `required` attribute of the control.
 *
 * @example
 * <Label htmlFor="email" required>Email</Label>
 * <input id="email" required />
 */
const Label = forwardRef<HTMLLabelElement, LabelProps>(
  ({ htmlFor, required, className, children, ...props }, ref) => {
    return (
      <label
        ref={ref}
        htmlFor={htmlFor}
        className={cn(
          "inline-flex items-center gap-1",
          "text-sm font-medium",
          "text-[var(--text-primary)]",
          className
        )}
        {...props}
      >
        {children}
        {required && (
          <span
            aria-hidden="true"
            className="text-[var(--danger)]"
          >
            *
          </span>
        )}
      </label>
    );
  }
);

Label.displayName = "Label";

export { Label };
export default Label;
