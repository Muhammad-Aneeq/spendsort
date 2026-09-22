/** aurora `MetricTile` — one number, its name, and what it means (spec 00 A2). */
import type { ReactNode } from "react";

type MetricTileProps = {
  label: string;
  value: ReactNode;
  /** Run-over-run change, e.g. "-40%". */
  delta?: string;
  /** Whether a *falling* value is the good direction (cost) or a rising one (memory-hit rate). */
  goodDirection?: "up" | "down";
  /** One line of context. Worth using: a metric without its meaning invites a wrong reading. */
  hint?: ReactNode;
  emphasis?: boolean;
};

export function MetricTile({
  label,
  value,
  delta,
  goodDirection = "up",
  hint,
  emphasis = false,
}: MetricTileProps) {
  const isDown = delta?.startsWith("-");
  const good = delta ? (goodDirection === "down" ? isDown : !isDown) : undefined;

  return (
    <div
      className={`rounded-card border p-4 shadow-sm ${
        emphasis ? "border-accent/30 bg-accent/5" : "border-hairline bg-card"
      }`}
    >
      <div className="text-[11px] font-semibold uppercase tracking-wider text-ink-faint">{label}</div>

      <div className="mt-2 flex items-baseline gap-2">
        <div className="tabular font-display text-2xl font-semibold text-ink">{value}</div>
        {delta && (
          <span
            className={`tabular text-xs font-medium ${good ? "text-conf-high" : "text-conf-mid"}`}
            title="change from the previous run"
          >
            {delta}
          </span>
        )}
      </div>

      {hint && <div className="mt-1.5 text-xs leading-snug text-ink-faint">{hint}</div>}
    </div>
  );
}
