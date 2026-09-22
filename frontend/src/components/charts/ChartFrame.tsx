/**
 * Shared chart chrome: a legend row, and the **table-view twin** every chart is required to
 * have. A tooltip must never be the only way to read a value, so each chart ships a toggle to
 * the same numbers as text — which is also what makes the charts usable in a screen reader and
 * in forced-colors mode.
 */
import { useState, type ReactNode } from "react";

type LegendItem = {
  label: string;
  color: string;
  /** One line of meaning. Status colours must carry a label, never stand on colour alone. */
  hint?: string;
};

type ChartFrameProps = {
  children: ReactNode;
  /** Rendered instead of the chart when the reader asks for numbers. */
  table: ReactNode;
  legend?: LegendItem[];
  /** Chart height in px, chosen to include the x-axis band, not just the plot. */
  height?: number;
  /** True while refetching: hold the previous render faded rather than flashing a skeleton. */
  stale?: boolean;
  footnote?: ReactNode;
};

export function ChartFrame({
  children,
  table,
  legend,
  height = 260,
  stale = false,
  footnote,
}: ChartFrameProps) {
  const [showTable, setShowTable] = useState(false);

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        {legend && legend.length > 0 ? (
          <ul className="flex flex-wrap items-center gap-x-4 gap-y-1">
            {legend.map((item) => (
              <li key={item.label} className="flex items-center gap-2 text-xs text-ink-muted">
                <span
                  className="size-2.5 shrink-0 rounded-sm"
                  style={{ backgroundColor: item.color }}
                  aria-hidden
                />
                <span className="font-medium">{item.label}</span>
                {item.hint && <span className="text-ink-faint">{item.hint}</span>}
              </li>
            ))}
          </ul>
        ) : (
          <span />
        )}

        <button
          type="button"
          onClick={() => setShowTable((v) => !v)}
          className="rounded-md border border-hairline px-2 py-1 text-[11px] font-medium text-ink-faint
            transition-colors hover:bg-card-strong hover:text-ink"
          aria-pressed={showTable}
        >
          {showTable ? "Show chart" : "Show numbers"}
        </button>
      </div>

      {showTable ? (
        <div className="overflow-x-auto">{table}</div>
      ) : (
        <div
          style={{ height }}
          className={`transition-opacity ${stale ? "opacity-50" : "opacity-100"}`}
        >
          {children}
        </div>
      )}

      {footnote && <p className="mt-3 text-xs leading-relaxed text-ink-faint">{footnote}</p>}
    </div>
  );
}

/** Small helper so every table twin looks the same. */
export function DataTable({
  headers,
  rows,
}: {
  headers: string[];
  rows: (string | number)[][];
}) {
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-hairline text-left text-[11px] uppercase tracking-wider text-ink-faint">
          {headers.map((header, index) => (
            <th key={header} className={`py-2 font-semibold ${index === 0 ? "pr-4" : "px-3 text-right"}`}>
              {header}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, rowIndex) => (
          <tr key={rowIndex} className="border-b border-hairline/40 last:border-0">
            {row.map((cell, cellIndex) => (
              <td
                key={cellIndex}
                className={
                  cellIndex === 0
                    ? "py-1.5 pr-4 text-ink-muted"
                    : "tabular px-3 py-1.5 text-right text-ink"
                }
              >
                {cell}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
