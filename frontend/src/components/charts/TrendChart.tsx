/**
 * A single-measure trend across runs.
 *
 * **Why this is one measure per chart.** The memory bend is naturally described as "memory-hit
 * rate up, cost per run down", which is the classic invitation to a dual-axis chart. Two
 * y-scales on one plot invent a correlation the data does not contain — the alignment of the
 * two axes is arbitrary, so the crossing point is a drawing artefact. So the bend is drawn as
 * two small multiples on one shared x-axis (run number) instead, and the story is read from
 * both panels rather than from a manufactured intersection.
 *
 * One series means no legend box: the card title names it. The endpoint is direct-labelled;
 * every other value lives in the tooltip and the table view.
 */
import {
  CartesianGrid,
  Label,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { ChartFrame, DataTable } from "./ChartFrame";
import {
  AXIS,
  DOT_SIZE,
  GRID,
  INK_FAINT,
  LINE_WIDTH,
  TOOLTIP_LABEL_STYLE,
  TOOLTIP_STYLE,
} from "./tokens";

export type TrendPoint = {
  /** X label, e.g. "run 1". */
  label: string;
  value: number;
};

type Props = {
  points: TrendPoint[];
  color: string;
  /** Renders a value for the axis, the tooltip and the endpoint label. */
  format: (value: number) => string;
  /** What the y-axis measures, e.g. "memory-hit rate". */
  measure: string;
  /** Domain override; percentages read better pinned to 0–1. */
  domain?: [number | "auto", number | "auto"];
  stale?: boolean;
  footnote?: React.ReactNode;
};

export function TrendChart({
  points,
  color,
  format,
  measure,
  domain = ["auto", "auto"],
  stale = false,
  footnote,
}: Props) {
  const last = points.at(-1);

  return (
    <ChartFrame
      stale={stale}
      height={220}
      footnote={footnote}
      table={
        <DataTable
          headers={["Run", measure]}
          rows={points.map((point) => [point.label, format(point.value)])}
        />
      }
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points} margin={{ top: 12, right: 44, left: 0, bottom: 4 }}>
          <CartesianGrid stroke={GRID} vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fill: INK_FAINT, fontSize: 11 }}
            stroke={AXIS}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: INK_FAINT, fontSize: 11 }}
            stroke={AXIS}
            tickLine={false}
            domain={domain}
            tickFormatter={format}
            width={62}
          />
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            labelStyle={TOOLTIP_LABEL_STYLE}
            formatter={(value) => [format(Number(value ?? 0)), measure]}
          />
          <Line
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={LINE_WIDTH}
            dot={{ r: DOT_SIZE, fill: color, stroke: "#0B1E3B", strokeWidth: 2 }}
            activeDot={{ r: DOT_SIZE + 2, fill: color, stroke: "#0B1E3B", strokeWidth: 2 }}
            isAnimationActive={false}
          >
            {/* Selective direct label: the endpoint only, never a number on every point. */}
            {last && (
              <Label
                value={format(last.value)}
                position="right"
                fill={color}
                fontSize={12}
                fontWeight={600}
              />
            )}
          </Line>
        </LineChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
