/**
 * Screen 4 — Memory (spec 11 section 9: "learned mappings table, hit counts").
 *
 * `hit_count` is the column that matters. Summed across the table it is the number of model
 * calls that never had to happen — which is the same number, seen from the other side, as the
 * cost bend on the Metrics screen.
 */
import { useQuery } from "@tanstack/react-query";

import { Card, EmptyState, MetricTile } from "../components/aurora";
import { api } from "../lib/api";
import { dateTime } from "../lib/format";

export default function Memory() {
  const memory = useQuery({ queryKey: ["memory"], queryFn: api.memory });

  const entries = memory.data?.entries ?? [];
  const humanTaught = entries.filter((e) => e.source === "human").length;
  const savedCalls = entries.reduce((total, e) => total + e.hit_count, 0);

  return (
    <div className="space-y-6">
      <div className="grid gap-3 sm:grid-cols-3">
        <MetricTile
          label="Mappings learned"
          value={memory.data?.total ?? 0}
          hint="one per normalized vendor"
        />
        <MetricTile
          label="Taught by a human"
          value={humanTaught}
          hint="from overrides — these outrank the model"
        />
        <MetricTile
          label="Model calls avoided"
          value={savedCalls}
          emphasis
          hint="total memory hits: work the LLM never had to do"
        />
      </div>

      <Card
        title="Vendor memory"
        subtitle="Most-used first. A human mapping is never overwritten by the model."
        padded={false}
      >
        {entries.length === 0 ? (
          <EmptyState icon="◇" title="Memory is empty">
            Nothing has been learned yet. Memory fills in two ways: the agent promotes an answer it
            was confident enough to apply on its own, and a human override is remembered
            permanently. Either way, that vendor is free next month.
          </EmptyState>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-hairline text-left text-[11px] uppercase tracking-wider text-ink-faint">
                  <th className="px-5 py-2 font-semibold">Vendor (normalized)</th>
                  <th className="px-5 py-2 font-semibold">Account</th>
                  <th className="px-5 py-2 font-semibold">Learned from</th>
                  <th className="px-5 py-2 text-right font-semibold">Hits</th>
                  <th className="px-5 py-2 font-semibold">Updated</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry) => (
                  <tr key={entry.vendor_norm} className="border-b border-hairline/40 last:border-0">
                    <td className="px-5 py-2">
                      <div className="font-mono text-ink">{entry.vendor_norm}</div>
                      {entry.example_vendor_raw && (
                        <div className="mt-0.5 truncate text-xs text-ink-faint" title={entry.example_vendor_raw}>
                          first seen as “{entry.example_vendor_raw}”
                        </div>
                      )}
                    </td>
                    <td className="px-5 py-2 whitespace-nowrap">
                      <span className="font-mono text-accent">{entry.account_code}</span>{" "}
                      <span className="text-ink-muted">{entry.account_name}</span>
                    </td>
                    <td className="px-5 py-2">
                      {entry.source === "human" ? (
                        <span className="inline-flex items-center gap-1.5 rounded-full border border-accent/40 bg-accent/15 px-2 py-0.5 text-[11px] font-medium text-accent-strong">
                          <span className="size-1.5 rounded-full bg-accent-strong" aria-hidden />
                          human
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 rounded-full border border-hairline bg-card px-2 py-0.5 text-[11px] font-medium text-ink-muted">
                          <span className="size-1.5 rounded-full bg-ink-faint" aria-hidden />
                          llm-confirmed
                        </span>
                      )}
                    </td>
                    <td className="tabular px-5 py-2 text-right text-ink">{entry.hit_count}</td>
                    <td className="px-5 py-2 whitespace-nowrap text-xs text-ink-faint">
                      {dateTime(entry.updated_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
