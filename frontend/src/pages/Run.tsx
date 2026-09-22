/**
 * Screen 2 — Run view (spec 11 section 9: "progress, confidence histogram").
 *
 * The histogram is the screen's argument: the confidence gate is a vertical line, and you can
 * see how much of the month fell on each side of it. The dashboard's *trend* charts are screen
 * 5; this one is about the run you just did.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button, Card, EmptyState, MetricTile } from "../components/aurora";
import { ConfidenceHistogram } from "../components/charts/ConfidenceHistogram";
import { api } from "../lib/api";
import { percent, usd } from "../lib/format";

export default function Run() {
  const queryClient = useQueryClient();
  const metrics = useQuery({ queryKey: ["metrics"], queryFn: api.metrics });
  const runs = useQuery({ queryKey: ["runs"], queryFn: api.runs });

  const start = useMutation({
    mutationFn: api.startRun,
    onSuccess: () => void queryClient.invalidateQueries(),
  });

  const latest = runs.data?.at(-1);
  const pending = metrics.data?.pending ?? 0;

  return (
    <div className="space-y-6">
      <Card
        title="Categorization run"
        subtitle={
          pending > 0
            ? `${pending} transactions are waiting to be categorized.`
            : "Nothing pending. Import a CSV to queue more work."
        }
        actions={
          <Button onClick={() => start.mutate()} disabled={start.isPending || pending === 0}>
            {start.isPending ? "Running…" : `Run on ${pending} pending`}
          </Button>
        }
      >
        {latest ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <MetricTile
              label="Transactions"
              value={latest.txn_count}
              hint={`run #${latest.id} · ${latest.llm_mode} model`}
            />
            <MetricTile
              label="Auto-applied"
              value={percent(latest.auto_rate)}
              hint={`at or above ${latest.auto_threshold.toFixed(2)} confidence`}
            />
            <MetricTile
              label="From memory"
              value={percent(latest.memory_hit_rate)}
              emphasis
              hint={`${latest.memory_hits} free · ${latest.llm_calls} model calls`}
            />
            <MetricTile
              label="Cost"
              value={usd(latest.cost_usd)}
              hint={`cap ${usd(latest.cost_cap_usd)} per run`}
            />
          </div>
        ) : (
          <EmptyState icon="▶" title="No runs yet">
            Import a CSV on the Import screen, then run the categorizer. Each run records its own
            auto-rate, memory-hit rate and cost, which is what makes the cost curve visible later.
          </EmptyState>
        )}

        {latest?.cost_capped && (
          <div className="mt-4 rounded-lg border border-conf-mid/40 bg-conf-mid/10 p-3 text-sm text-conf-mid">
            <strong className="font-semibold">Cost cap reached.</strong> {latest.capped_txn_count}{" "}
            transactions were queued for review rather than sent to the model. Nothing was dropped.
          </div>
        )}
      </Card>

      <Card
        title="Confidence distribution"
        subtitle={
          metrics.data
            ? `Every decision so far, bucketed. The gate sits at ${metrics.data.auto_threshold.toFixed(2)}.`
            : "Loading…"
        }
      >
        {metrics.data && metrics.data.total_transactions > 0 ? (
          <ConfidenceHistogram
            bins={metrics.data.confidence_histogram}
            threshold={metrics.data.auto_threshold}
          />
        ) : (
          <EmptyState icon="▤" title="Nothing categorized yet">
            The histogram appears after the first run.
          </EmptyState>
        )}
      </Card>

      {runs.data && runs.data.length > 0 && (
        <Card title="Run history" subtitle="Oldest first. The trend charts live on the Metrics screen." padded={false}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-hairline text-left text-[11px] uppercase tracking-wider text-ink-faint">
                  <th className="px-5 py-2 font-semibold">Run</th>
                  <th className="px-5 py-2 font-semibold">Txns</th>
                  <th className="px-5 py-2 font-semibold">Auto</th>
                  <th className="px-5 py-2 font-semibold">Memory</th>
                  <th className="px-5 py-2 font-semibold">Model calls</th>
                  <th className="px-5 py-2 font-semibold">Cost</th>
                  <th className="px-5 py-2 font-semibold">Cost / txn</th>
                </tr>
              </thead>
              <tbody>
                {runs.data.map((run) => (
                  <tr key={run.id} className="border-b border-hairline/40 last:border-0">
                    <td className="tabular px-5 py-2 font-mono text-accent">#{run.id}</td>
                    <td className="tabular px-5 py-2 text-ink">{run.txn_count}</td>
                    <td className="tabular px-5 py-2 text-ink">{percent(run.auto_rate)}</td>
                    <td className="tabular px-5 py-2 text-accent">{percent(run.memory_hit_rate)}</td>
                    <td className="tabular px-5 py-2 text-ink-muted">{run.llm_calls}</td>
                    <td className="tabular px-5 py-2 text-ink">{usd(run.cost_usd)}</td>
                    <td className="tabular px-5 py-2 text-ink-faint">
                      {run.txn_count ? usd(run.cost_usd / run.txn_count) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
