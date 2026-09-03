/**
 * Screen 5 — Metrics (spec 11 section 9: "auto-rate trend, cost trend, memory-bend chart").
 *
 * spec 11 section 8: "the agent gets cheaper and faster every month, and the dashboard proves
 * it: that chart IS the launch post."
 *
 * The bend is drawn as two small multiples sharing one x-axis (run number) rather than one
 * dual-axis plot. Two y-scales on a single plot would put the "lines crossing" moment wherever
 * the axis alignment happened to fall — a drawing artefact, not a finding. Two panels make the
 * same point without inventing one.
 */
import { useQuery } from "@tanstack/react-query";

import { Button, Card, EmptyState, MetricTile } from "../components/aurora";
import { ConfidenceHistogram } from "../components/charts/ConfidenceHistogram";
import { TrendChart, type TrendPoint } from "../components/charts/TrendChart";
import { CHART_AUTO, CHART_QUEUED } from "../components/charts/tokens";
import { api } from "../lib/api";
import { delta, money, percent, usd } from "../lib/format";

export default function Metrics() {
  const metrics = useQuery({ queryKey: ["metrics"], queryFn: api.metrics });

  if (metrics.isLoading) return <Card>Loading metrics…</Card>;
  const data = metrics.data;

  if (!data || data.total_transactions === 0) {
    return (
      <Card>
        <EmptyState icon="◔" title="No data yet">
          Import a CSV and run the categorizer. Run it a second time on another month to see the
          memory bend — the chart this project exists to draw.
        </EmptyState>
      </Card>
    );
  }

  const runs = data.runs;
  const first = runs[0];
  const last = runs.at(-1);
  const hasTrend = runs.length >= 2;

  const memoryPoints: TrendPoint[] = runs.map((run) => ({
    label: `run ${run.id}`,
    value: run.memory_hit_rate,
  }));
  const costPoints: TrendPoint[] = runs.map((run) => ({
    label: `run ${run.id}`,
    value: run.txn_count ? run.cost_usd / run.txn_count : 0,
  }));
  const autoPoints: TrendPoint[] = runs.map((run) => ({
    label: `run ${run.id}`,
    value: run.auto_rate,
  }));

  return (
    <div className="space-y-6">
      {/* --- the headline numbers ------------------------------------- */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricTile
          label="Auto-applied"
          value={percent(data.auto_rate)}
          delta={hasTrend && first && last ? delta(first.auto_rate, last.auto_rate) : undefined}
          goodDirection="up"
          hint={`${data.auto} of ${data.total_transactions} needed no human`}
        />
        <MetricTile
          label="From memory"
          value={percent(data.memory_hit_rate)}
          delta={
            hasTrend && first && last ? delta(first.memory_hit_rate, last.memory_hit_rate) : undefined
          }
          goodDirection="up"
          emphasis
          hint="answered with no model call at all"
        />
        <MetricTile
          label="Total cost"
          value={usd(data.total_cost_usd)}
          hint={`${runs.length} run${runs.length === 1 ? "" : "s"} · cap ${usd(
            last?.cost_cap_usd ?? 0.25,
          )} each`}
        />
        <MetricTile
          label="In the queue"
          value={data.queued}
          goodDirection="down"
          hint={`${data.resolved} already reviewed`}
        />
      </div>

      {/* --- THE MEMORY BEND ------------------------------------------ */}
      <Card
        title="The memory bend"
        subtitle="Memory covers more of each run, so the model is called less and each run costs less."
      >
        {hasTrend ? (
          <div className="grid gap-6 lg:grid-cols-2">
            <div>
              <h3 className="mb-1 text-sm font-semibold text-ink">Memory-hit rate, per run</h3>
              <p className="mb-3 text-xs text-ink-faint">Share of transactions answered with no model call.</p>
              <TrendChart
                points={memoryPoints}
                color={CHART_AUTO}
                format={(v) => percent(v, 0)}
                measure="memory-hit rate"
                domain={[0, 1]}
                stale={metrics.isFetching}
              />
            </div>

            <div>
              <h3 className="mb-1 text-sm font-semibold text-ink">Cost per transaction, per run</h3>
              <p className="mb-3 text-xs text-ink-faint">
                Same work, less of it paid for. Normalised per transaction so months of different size compare.
              </p>
              <TrendChart
                points={costPoints}
                color={CHART_QUEUED}
                format={(v) => (v === 0 ? "$0" : `$${v.toFixed(5)}`)}
                measure="cost per transaction"
                domain={[0, "auto"]}
                stale={metrics.isFetching}
              />
            </div>
          </div>
        ) : (
          <EmptyState icon="↗" title="One run so far">
            The bend needs at least two runs. Import a second month — the same vendors reappear,
            memory covers them, and the cost drops. Try{" "}
            <code className="font-mono">examples/month_02_realistic_seed43.csv</code>.
          </EmptyState>
        )}

        {hasTrend && first && last && (
          <div className="mt-5 rounded-lg border border-emerald/25 bg-emerald/5 p-4 text-sm text-ink-muted">
            Between run #{first.id} and run #{last.id}: memory-hit rate{" "}
            <strong className="text-emerald">
              {percent(first.memory_hit_rate, 0)} → {percent(last.memory_hit_rate, 0)}
            </strong>
            , model calls{" "}
            <strong className="text-ink">
              {first.llm_calls} → {last.llm_calls}
            </strong>
            , cost per run{" "}
            <strong className="text-emerald">
              {usd(first.cost_usd)} → {usd(last.cost_usd)}
            </strong>
            {first.cost_usd > 0 && (
              <>
                {" "}
                ({(100 * (1 - last.cost_usd / first.cost_usd)).toFixed(0)}% cheaper)
              </>
            )}
            .
          </div>
        )}
      </Card>

      {/* --- auto-rate trend ------------------------------------------ */}
      {hasTrend && (
        <Card
          title="Auto-rate, per run"
          subtitle="How much of each month the agent handled unaided."
        >
          <TrendChart
            points={autoPoints}
            color={CHART_AUTO}
            format={(v) => percent(v, 0)}
            measure="auto-rate"
            domain={[0, 1]}
            stale={metrics.isFetching}
            footnote="Rising because memory answers with certainty where the model was merely confident."
          />
        </Card>
      )}

      {/* --- confidence distribution ---------------------------------- */}
      <Card title="Confidence distribution" subtitle="Every decision, and which side of the gate it fell on.">
        <ConfidenceHistogram
          bins={data.confidence_histogram}
          threshold={data.auto_threshold}
          stale={metrics.isFetching}
        />
      </Card>

      {/* --- category breakdown --------------------------------------- */}
      <Card
        title="Spend by account"
        subtitle="Decided lines only — a queued row has no agreed account yet."
        actions={
          <a href={api.exportUrl()} download>
            <Button variant="ghost">Export CSV ↓</Button>
          </a>
        }
        padded={false}
      >
        {data.category_breakdown.length === 0 ? (
          <EmptyState icon="▦" title="Nothing decided yet">
            Accounts appear here once transactions are auto-applied or reviewed.
          </EmptyState>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-hairline text-left text-[11px] uppercase tracking-wider text-ink-faint">
                  <th className="px-5 py-2 font-semibold">Account</th>
                  <th className="px-5 py-2 text-right font-semibold">Lines</th>
                  <th className="px-5 py-2 text-right font-semibold">Total</th>
                </tr>
              </thead>
              <tbody>
                {data.category_breakdown.map((item) => (
                  <tr key={item.account_code} className="border-b border-hairline/40 last:border-0">
                    <td className="px-5 py-2">
                      <span className="font-mono text-emerald">{item.account_code}</span>{" "}
                      <span className="text-ink">{item.account_name}</span>
                    </td>
                    <td className="tabular px-5 py-2 text-right text-ink-muted">{item.count}</td>
                    <td className="tabular px-5 py-2 text-right text-ink">{money(item.total_amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <p className="px-1 text-xs text-ink-faint">
        Cost figures come from the token counts of each run, priced by{" "}
        <code className="font-mono">backend/app/costs.py</code>. In mock mode no model is called, so
        the amounts are illustrative — see MODEL_COSTS.md.
      </p>
    </div>
  );
}
