/**
 * Screen 1 — Import + CoA editor (spec 11 section 9).
 *
 * spec 11 section 4 F1: "CSV upload (date, amount, vendor/description, currency) +
 * chart of accounts as editable YAML".
 *
 * The intake result deliberately reports rejected rows as loudly as accepted ones. A silent
 * partial import is the kind of thing a bookkeeper finds three weeks later.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button, Card, EmptyState } from "../components/aurora";
import { api, ApiError } from "../lib/api";
import type { IngestResult } from "../lib/types";

export default function Import() {
  const queryClient = useQueryClient();
  const [result, setResult] = useState<IngestResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const coa = useQuery({ queryKey: ["coa"], queryFn: api.coa });
  const coaYaml = useQuery({ queryKey: ["coa-yaml"], queryFn: api.coaYaml });

  const [draft, setDraft] = useState<string | null>(null);
  const [coaMessage, setCoaMessage] = useState<string | null>(null);

  const upload = useMutation({
    mutationFn: api.uploadCsv,
    onSuccess: (data) => {
      setResult(data);
      setError(null);
      void queryClient.invalidateQueries();
    },
    onError: (e: Error) => {
      setError(e instanceof ApiError ? e.message : String(e));
      setResult(null);
    },
  });

  const saveCoa = useMutation({
    mutationFn: api.saveCoa,
    onSuccess: (data) => {
      setCoaMessage(`Saved — ${data.count} accounts.`);
      void queryClient.invalidateQueries();
    },
    onError: (e: Error) => setCoaMessage(e instanceof ApiError ? e.message : String(e)),
  });

  const runCategorization = useMutation({
    mutationFn: api.startRun,
    onSuccess: () => void queryClient.invalidateQueries(),
  });

  return (
    <div className="space-y-6">
      <Card
        title="1 · Import transactions"
        subtitle="CSV with date, amount, currency, vendor/description and an optional memo."
      >
        <label
          className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg
            border border-dashed border-hairline bg-card/40 px-6 py-10 text-center transition-colors
            hover:border-accent/40 hover:bg-accent/5"
        >
          <span className="text-2xl" aria-hidden>
            ⬆
          </span>
          <span className="text-sm font-medium text-ink">Choose a CSV file</span>
          <span className="text-xs text-ink-faint">
            Try <code className="font-mono">examples/month_01_realistic_seed42.csv</code>
          </span>
          <input
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) upload.mutate(file);
              event.target.value = "";
            }}
          />
        </label>

        {upload.isPending && <p className="mt-4 text-sm text-ink-muted">Parsing…</p>}

        {error && (
          <div className="mt-4 rounded-lg border border-conf-low/40 bg-conf-low/10 p-3 text-sm text-conf-low">
            <strong className="font-semibold">Upload refused.</strong> {error}
          </div>
        )}

        {result && (
          <div className="mt-4 space-y-3">
            <div className="flex flex-wrap items-center gap-4 text-sm">
              <span className="text-conf-high">
                <strong className="tabular font-semibold">{result.accepted}</strong> accepted
              </span>
              <span className={result.rejected > 0 ? "text-conf-mid" : "text-ink-faint"}>
                <strong className="tabular font-semibold">{result.rejected}</strong> rejected
              </span>
              <span className="text-ink-faint">
                {result.pending_total} awaiting categorization · read as {result.encoding}
              </span>
            </div>

            {result.truncated && (
              <p className="text-sm text-conf-mid">
                Row limit reached — the rest of the file was not read.
              </p>
            )}

            {result.errors.length > 0 && (
              <details className="rounded-lg border border-hairline bg-card/40 p-3">
                <summary className="cursor-pointer text-sm font-medium text-ink-muted">
                  Rejected rows ({result.rejected}) — every one, with a reason
                </summary>
                <ul className="mt-2 space-y-1 text-xs text-ink-faint">
                  {result.errors.map((rowError) => (
                    <li key={rowError.line} className="font-mono">
                      line {rowError.line}: {rowError.reason}
                      {rowError.raw && <span className="opacity-60"> — {rowError.raw}</span>}
                    </li>
                  ))}
                </ul>
              </details>
            )}

            {result.pending_total > 0 && (
              <Button
                onClick={() => runCategorization.mutate()}
                disabled={runCategorization.isPending}
              >
                {runCategorization.isPending
                  ? "Categorizing…"
                  : `Categorize ${result.pending_total} transactions →`}
              </Button>
            )}
          </div>
        )}
      </Card>

      <Card
        title="2 · Chart of accounts"
        subtitle={
          coa.data
            ? `${coa.data.count} accounts. Editable YAML — validated before it is saved.`
            : "Loading…"
        }
        actions={
          draft !== null ? (
            <>
              <Button variant="ghost" onClick={() => { setDraft(null); setCoaMessage(null); }}>
                Cancel
              </Button>
              <Button onClick={() => saveCoa.mutate(draft)} disabled={saveCoa.isPending}>
                {saveCoa.isPending ? "Saving…" : "Save"}
              </Button>
            </>
          ) : (
            <Button variant="ghost" onClick={() => setDraft(coaYaml.data?.yaml ?? "")}>
              Edit YAML
            </Button>
          )
        }
      >
        {coaMessage && (
          <div
            className={`mb-4 rounded-lg border p-3 text-sm ${
              coaMessage.startsWith("Saved")
                ? "border-conf-high/40 bg-conf-high/10 text-conf-high"
                : "border-conf-low/40 bg-conf-low/10 text-conf-low"
            }`}
          >
            {coaMessage}
          </div>
        )}

        {draft !== null ? (
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            spellCheck={false}
            rows={20}
            className="w-full rounded-lg border border-hairline bg-paper-deep/60 p-3 font-mono text-xs
              text-ink outline-none focus:border-accent/50"
          />
        ) : coa.data && coa.data.accounts.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-hairline text-left text-[11px] uppercase tracking-wider text-ink-faint">
                  <th className="pb-2 pr-4 font-semibold">Code</th>
                  <th className="pb-2 pr-4 font-semibold">Account</th>
                  <th className="pb-2 font-semibold">What belongs here</th>
                </tr>
              </thead>
              <tbody>
                {coa.data.accounts.map((account) => (
                  <tr key={account.code} className="border-b border-hairline/40 last:border-0">
                    <td className="tabular py-2 pr-4 font-mono text-accent">{account.code}</td>
                    <td className="py-2 pr-4 whitespace-nowrap text-ink">{account.name}</td>
                    <td className="py-2 text-ink-faint">{account.description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No chart of accounts" icon="⚠">
            Expected one at <code className="font-mono">backend/app/coa_default.yaml</code>. Run{" "}
            <code className="font-mono">make seed</code> to regenerate it.
          </EmptyState>
        )}
      </Card>
    </div>
  );
}
