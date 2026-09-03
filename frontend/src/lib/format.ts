/** Formatting helpers. Money and percentages appear on every screen, so they format once. */

export const money = (value: number, currency = "USD"): string =>
  new Intl.NumberFormat("en-US", { style: "currency", currency, maximumFractionDigits: 2 }).format(value);

/** Sub-cent costs are the whole point of the cost story, so they need real precision. */
export const usd = (value: number): string => {
  if (value === 0) return "$0.00";
  if (value < 0.01) return `$${value.toFixed(5)}`;
  return `$${value.toFixed(2)}`;
};

export const percent = (value: number, digits = 1): string => `${(value * 100).toFixed(digits)}%`;

export const shortDate = (iso: string): string => {
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return iso;
  return parsed.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
};

export const dateTime = (iso: string | null): string => {
  if (!iso) return "—";
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return iso;
  return parsed.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

/** Change between two values, as a signed percentage. Used for the run-over-run deltas. */
export const delta = (from: number, to: number): string => {
  if (from === 0) return to === 0 ? "0%" : "new";
  const change = ((to - from) / Math.abs(from)) * 100;
  return `${change > 0 ? "+" : ""}${change.toFixed(0)}%`;
};
