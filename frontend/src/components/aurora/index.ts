/**
 * aurora-ui — the shared design system (spec 00 A2).
 *
 * Implemented locally rather than imported from a workspace package, because that package does
 * not exist in this repo (adaptation 2, BLOCKERS.md B5). The four components the brief names
 * are here — `Card`, `ConfidencePill`, `MetricTile`, `SyntheticDataBanner` — plus `EmptyState`
 * and `Button`, which every screen needed.
 *
 * Tokens live in `tokens.css` as a Tailwind v4 `@theme` block: dark navy #0B1E3B,
 * emerald #10B981, frosted glass, Space Grotesk / Inter.
 */

export { Button } from "./Button";
export { Card } from "./Card";
export { ConfidencePill } from "./ConfidencePill";
export { EmptyState } from "./EmptyState";
export { MetricTile } from "./MetricTile";
export { SyntheticDataBanner } from "./SyntheticDataBanner";
