/**
 * Chart colors — VALIDATED, not eyeballed.
 *
 * These two are status colors, not series identity: the histogram's split means
 * "auto-applied" vs "needs a human", which is a good/attention state. Status colors ship with
 * a label and a legend, never colour alone.
 *
 * Re-validated for the **light** theme against the card surface (#FFFFFF):
 *
 *   node scripts/validate_palette.js "#0D9488,#EA580C" --mode light --surface "#FFFFFF"
 *     [PASS] Lightness band       both inside L 0.43–0.77
 *     [PASS] Chroma floor         both >= 0.10
 *     [PASS] CVD separation       worst adjacent ΔE 13.8 (protan) · tritan 34.5
 *     [PASS] Normal-vision floor  worst adjacent ΔE 28.8
 *     [PASS] Contrast vs surface  both >= 3:1
 *
 * Two things this check caught, both of which would have shipped otherwise:
 *   • The previous dark-theme steps (#0E9A6C / #D97706) are wrong here — a palette is only
 *     valid for the surface it was measured against.
 *   • The deeper teals that read better as *text* (#0F766E, #115E59) FAIL the chroma floor as
 *     fills — at that lightness the hue desaturates and the bar reads gray.
 *
 * So fills and text deliberately use different steps of the same hue. Do not "unify them" —
 * re-run the validator first.
 */

/** Cleared the confidence gate: applied without a human. */
export const CHART_AUTO = "#0D9488";
/** Below the gate: waiting for a person. */
export const CHART_QUEUED = "#EA580C";

/** The surface charts are drawn on; marks ring against it to stay separate. */
export const CHART_SURFACE = "#FFFFFF";

/** Recessive chrome. Hairlines one shade off the surface — solid, never dashed. */
export const GRID = "rgba(26,22,20,0.09)";
export const AXIS = "rgba(26,22,20,0.18)";
export const INK_MUTED = "#5C5349";
export const INK_FAINT = "#8A7F72";

/** Mark geometry, per the dataviz mark specs. */
export const BAR_RADIUS: [number, number, number, number] = [4, 4, 0, 0];
export const LINE_WIDTH = 2;
export const DOT_SIZE = 4; // radius; 8px diameter minimum

/** Shared tooltip chrome, so every chart's hover layer looks like one system. */
export const TOOLTIP_STYLE = {
  backgroundColor: "#FFFFFF",
  border: "1px solid rgba(26,22,20,0.14)",
  borderRadius: "10px",
  fontSize: "12px",
  color: "#1A1614",
  boxShadow: "0 8px 24px -12px rgb(80 60 40 / 0.35)",
} as const;

export const TOOLTIP_LABEL_STYLE = { color: INK_MUTED, marginBottom: 2 } as const;
