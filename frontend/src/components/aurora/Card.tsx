/**
 * aurora `Card` — frosted-glass surface (spec 00 A2).
 *
 * The one import that makes a screen look like the rest of the portfolio.
 */
import type { ReactNode } from "react";

type CardProps = {
  children: ReactNode;
  /** Section heading, rendered in the display face. */
  title?: ReactNode;
  /** One line under the title. Use it to say what the numbers mean. */
  subtitle?: ReactNode;
  /** Right-aligned controls in the header row. */
  actions?: ReactNode;
  className?: string;
  padded?: boolean;
};

export function Card({ children, title, subtitle, actions, className = "", padded = true }: CardProps) {
  return (
    <section
      className={`rounded-card border border-hairline bg-glass backdrop-blur-md ${className}`}
      style={{ boxShadow: "var(--shadow-glass)" }}
    >
      {(title || actions) && (
        <header className="flex items-start justify-between gap-4 border-b border-hairline px-5 py-4">
          <div>
            {title && <h2 className="font-display text-base font-semibold text-ink">{title}</h2>}
            {subtitle && <p className="mt-1 text-sm text-ink-faint">{subtitle}</p>}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={padded ? "p-5" : ""}>{children}</div>
    </section>
  );
}
