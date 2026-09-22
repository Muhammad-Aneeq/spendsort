/**
 * aurora `ConfidencePill` — spec 00 A2: "0-1 → color+label".
 *
 * This is the most important component in the product. It is where a number the model produced
 * becomes a claim a human has to judge, so it does three things deliberately:
 *
 *  * shows the **number**, not just a colour — "high" hides whether it was 0.86 or 0.99
 *  * says which side of the **gate** it fell on, because that is the consequence
 *  * never renders green below the threshold, whatever the raw score
 *
 * Colour alone is not the signal (accessibility, and colour-blind reviewers): the label and the
 * number carry the meaning too.
 */

type ConfidencePillProps = {
  confidence: number;
  /** The auto-apply threshold in force. Drives the label, not just the tint. */
  threshold?: number;
  /** False when the model named an account outside the chart of accounts. */
  coaValid?: boolean;
  /** True when this came from a mapping a human taught us. */
  learned?: boolean;
  size?: "sm" | "md";
};

type Tone = {
  label: string;
  className: string;
  dot: string;
};

function tone(confidence: number, threshold: number, coaValid: boolean, learned: boolean): Tone {
  if (learned) {
    return {
      label: "learned",
      className: "border-accent/40 bg-accent/15 text-accent-strong",
      dot: "bg-accent-strong",
    };
  }
  if (!coaValid) {
    // An invalid account is not a low-confidence answer — it is a rejected one. Saying so is
    // more useful to the reviewer than a number.
    return {
      label: "invalid account",
      className: "border-conf-low/40 bg-conf-low/15 text-conf-low",
      dot: "bg-conf-low",
    };
  }
  if (confidence >= threshold) {
    return {
      label: "auto-applied",
      className: "border-conf-high/40 bg-conf-high/15 text-conf-high",
      dot: "bg-conf-high",
    };
  }
  if (confidence >= threshold * 0.6) {
    return {
      label: "needs review",
      className: "border-conf-mid/40 bg-conf-mid/15 text-conf-mid",
      dot: "bg-conf-mid",
    };
  }
  return {
    label: "low confidence",
    className: "border-conf-low/40 bg-conf-low/15 text-conf-low",
    dot: "bg-conf-low",
  };
}

export function ConfidencePill({
  confidence,
  threshold = 0.85,
  coaValid = true,
  learned = false,
  size = "md",
}: ConfidencePillProps) {
  const t = tone(confidence, threshold, coaValid, learned);
  const padding = size === "sm" ? "px-2 py-0.5 text-[11px]" : "px-2.5 py-1 text-xs";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border font-medium ${padding} ${t.className}`}
      title={`confidence ${confidence.toFixed(3)} · threshold ${threshold.toFixed(2)}`}
    >
      <span className={`size-1.5 rounded-full ${t.dot}`} aria-hidden />
      <span className="tabular">{learned ? "1.00" : confidence.toFixed(2)}</span>
      <span className="opacity-80">{t.label}</span>
    </span>
  );
}
