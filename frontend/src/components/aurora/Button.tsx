/**
 * Shared button. Not in the spec 00 A2 list, but every screen needs one and three
 * divergent hand-rolled buttons would undo the point of a design system.
 *
 * `primary` uses the deeper teal so white label text clears 4.5:1 (5.47:1 measured); the
 * lighter `accent` step is reserved for fills that carry no type.
 */
import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "ghost" | "danger";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  children: ReactNode;
};

const VARIANTS: Record<Variant, string> = {
  primary: "bg-accent-strong text-white shadow-sm hover:bg-accent-deep disabled:bg-accent-strong/40",
  ghost: "border border-hairline bg-card text-ink hover:bg-card-strong",
  danger: "border border-conf-low/40 bg-conf-low/10 text-conf-low hover:bg-conf-low/20",
};

export function Button({ variant = "primary", children, className = "", ...rest }: ButtonProps) {
  return (
    <button
      {...rest}
      className={`inline-flex items-center justify-center gap-2 rounded-lg px-3.5 py-2 text-sm font-semibold
        transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${VARIANTS[variant]} ${className}`}
    >
      {children}
    </button>
  );
}
