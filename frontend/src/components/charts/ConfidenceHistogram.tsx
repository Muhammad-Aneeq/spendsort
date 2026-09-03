/**
 * Confidence histogram (spec 11 section 4 F5, screen 2).
 *
 * The chart's argument is the **gate**: a vertical line at the threshold, bars to its right
 * applied without a human, bars to its left waiting for one. Colour follows that state, so it
 * is a status encoding — which is why it ships with a legend and a table view rather than
 * relying on the hue.
 *
 * Colours are validated (see `tokens.ts`); the reference line is deliberately dashed, because
 * it *is* a threshold — the grid stays solid so it cannot be mistaken for one.
 */
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { HistogramBin } from "../../lib/types";
import { ChartFrame, DataTable } from "./ChartFrame";
import {
  AXIS,
  BAR_RADIUS,
  CHART_AUTO,
  CHART_QUEUED,
  GRID,
  INK_FAINT,
  TOOLTIP_LABEL_STYLE,
  TOOLTIP_STYLE,
} from "./tokens";

type Props = {
  bins: HistogramBin[];
  threshold: number;
  stale?: boolean;
};

export function ConfidenceHistogram({ bins, threshold, stale = false }: Props) {
  const data = bins.map((bin) => ({
    ...bin,
    // Bucket label, e.g. "0.8–0.9".
    band: `${bin.lower.toFixed(1)}–${bin.upper.toFixed(1)}`,
  }));

  const autoTotal = bins.filter((b) => b.auto).reduce((sum, b) => sum + b.count, 0);
  const queuedTotal = bins.filter((b) => !b.auto).reduce((sum, b) => sum + b.count, 0);

  return (
    <ChartFrame
      stale={stale}
      height={280}
      legend={[
        { label: "Auto-applied", color: CHART_AUTO, hint: `≥ ${threshold.toFixed(2)} · ${autoTotal}` },
        { label: "Queued for review", color: CHART_QUEUED, hint: `below · ${queuedTotal}` },
      ]}
      footnote={
        <>
          Each bar is a confidence bucket. The dashed line is the auto-apply threshold: everything
          to its right was posted without a human, everything to its left is in the review queue.
          A tall bar just under the line is the interesting one — those are decisions the agent
          nearly trusted.
        </>
      }
      table={
        <DataTable
          headers={["Confidence", "Decisions", "Outcome"]}
          rows={data.map((bin) => [bin.band, bin.count, bin.auto ? "auto-applied" : "queued"])}
        />
      }
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 4 }} barCategoryGap={2}>
          <CartesianGrid stroke={GRID} vertical={false} />
          <XAxis
            dataKey="band"
            tick={{ fill: INK_FAINT, fontSize: 11 }}
            stroke={AXIS}
            tickLine={false}
            interval={0}
          />
          <YAxis
            tick={{ fill: INK_FAINT, fontSize: 11 }}
            stroke={AXIS}
            tickLine={false}
            allowDecimals={false}
            label={{
              value: "transactions",
              angle: -90,
              position: "insideLeft",
              fill: INK_FAINT,
              fontSize: 11,
              style: { textAnchor: "middle" },
            }}
          />
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            labelStyle={TOOLTIP_LABEL_STYLE}
            cursor={{ fill: "rgba(255,255,255,0.04)" }}
            // Recharts v3 types the value as possibly-undefined, so coerce rather than assert.
            formatter={(value, _name, entry) => [
              `${Number(value ?? 0)} transactions`,
              (entry?.payload as { auto?: boolean } | undefined)?.auto ? "auto-applied" : "queued",
            ]}
            labelFormatter={(label) => `confidence ${label}`}
          />
          <ReferenceLine
            // Bands are 0.1 wide, so the threshold sits at bin index threshold*10.
            x={data[Math.min(Math.floor(threshold * 10), data.length - 1)]?.band}
            stroke={INK_FAINT}
            strokeDasharray="4 4"
            label={{
              value: `gate ${threshold.toFixed(2)}`,
              position: "top",
              fill: INK_FAINT,
              fontSize: 10,
            }}
          />
          <Bar dataKey="count" radius={BAR_RADIUS} maxBarSize={54}>
            {data.map((bin) => (
              <Cell key={bin.band} fill={bin.auto ? CHART_AUTO : CHART_QUEUED} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
