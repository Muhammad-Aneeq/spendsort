/**
 * Chart colors — VALIDATED, not eyeballed.
 *
 * These two are status colors, not series identity: the histogram's split means
 * "auto-applied" vs "needs a human", which is a good/attention state. Status colors ship with
 * a label and a legend, never colour alone.
 *
 * Verified with the dataviz palette validator against the dark navy chart surface (#0B1E3B):
 *
 *   node scripts/validate_palette.js "#0E9A6C,#D97706" --mode dark --surface "#0B1E3B"
 *     [PASS] Lightness band       both inside L 0.48–0.67
 *     [PASS] Chroma floor         both >= 0.10
 *     [PASS] CVD separation       worst adjacent ΔE 8.3 (protan) · tritan 28.7
 *     [PASS] Normal-vision floor  worst adjacent ΔE 23.4
 *     [PASS] Contrast vs surface  both >= 3:1
 *
 * The brighter #10B981 / #F59E0B used elsewhere in the UI FAIL the dark-mode lightness band
 * (L 0.696 and 0.769, band is 0.48–0.67), so charts deliberately use the dimmer steps of the
 * same hues. Do not "brighten these to match the buttons" — re-run the validator first.
 */

/** Cleared the confidence gate: applied without a human. */
export const CHART_AUTO = "#0E9A6C";
/** Below the gate: waiting for a person. */
export const CHART_QUEUED = "#D97706";

/** Recessive chrome. Hairlines one shade off the surface — solid, never dashed. */
export const GRID = "rgba(255,255,255,0.08)";
export const AXIS = "rgba(255,255,255,0.14)";
export const INK_MUTED = "#94a3b8";
export const INK_FAINT = "#64748b";

/** Mark geometry, per the dataviz mark specs. */
export const BAR_RADIUS: [number, number, number, number] = [4, 4, 0, 0];
export const LINE_WIDTH = 2;
export const DOT_SIZE = 4; // radius; 8px diameter minimum

/** Shared tooltip chrome, so every chart's hover layer looks like one system. */
export const TOOLTIP_STYLE = {
  backgroundColor: "#12294b",
  border: "1px solid rgba(255,255,255,0.14)",
  borderRadius: "10px",
  fontSize: "12px",
  color: "#f8fafc",
  boxShadow: "0 8px 32px -8px rgb(0 0 0 / 0.6)",
} as const;

export const TOOLTIP_LABEL_STYLE = { color: INK_MUTED, marginBottom: 2 } as const;
