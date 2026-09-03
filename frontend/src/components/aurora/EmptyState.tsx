/**
 * aurora `EmptyState` — spec 00 A2.
 *
 * Every screen has a first-run state, and an empty table with no explanation reads as a bug.
 * These say what to do next instead.
 */
import type { ReactNode } from "react";

type EmptyStateProps = {
  icon?: string;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
};

export function EmptyState({ icon = "◌", title, children, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-14 text-center">
      <div className="mb-3 text-3xl text-ink-faint/60" aria-hidden>
        {icon}
      </div>
      <h3 className="font-display text-base font-semibold text-ink">{title}</h3>
      {children && <p className="mt-2 max-w-md text-sm leading-relaxed text-ink-faint">{children}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
