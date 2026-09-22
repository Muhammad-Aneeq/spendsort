/**
 * Screen 3 — Review Queue (spec 11 section 9).
 *
 *   "row: vendor, amount, suggested account, ConfidencePill, reason; one-click accept;
 *    override picker; keyboard flow"
 *
 * spec 11 section 4 F3: sorted lowest-confidence-first, so a reviewer working top-down meets
 * the worst guesses first.
 *
 * The keyboard flow is the difference between a demo and a tool. The bookkeeper in spec 11
 * section 3 has fifty of these a month; making them reach for a mouse fifty times is how you
 * lose them. `j`/`k` move, `a` accepts, `o` opens the override picker, `Enter` confirms.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button, Card, ConfidencePill, EmptyState } from "../components/aurora";
import { api } from "../lib/api";
import { money, shortDate } from "../lib/format";
import type { Transaction } from "../lib/types";

export default function Queue() {
  const queryClient = useQueryClient();
  const queue = useQuery({ queryKey: ["queue"], queryFn: api.queue });
  const coa = useQuery({ queryKey: ["coa"], queryFn: api.coa });

  const [cursor, setCursor] = useState(0);
  const [overriding, setOverriding] = useState<number | null>(null);
  const [flash, setFlash] = useState<string | null>(null);
  const selectRef = useRef<HTMLSelectElement>(null);

  const items = queue.data?.items ?? [];
  const threshold = queue.data?.auto_threshold ?? 0.85;

  const verdict = useMutation({
    mutationFn: ({ id, action, account }: { id: number; action: "accept" | "override"; account?: string }) =>
      api.verdict(id, action, account),
    onSuccess: (data) => {
      setFlash(
        data.action === "override"
          ? `Learned: ${data.final_account} ${data.final_account_name}. This vendor will auto-categorize next time.`
          : `Accepted: ${data.final_account} ${data.final_account_name}.`,
      );
      setOverriding(null);
      void queryClient.invalidateQueries();
    },
    onError: (e: Error) => setFlash(e.message),
  });

  // Keep the cursor in range as rows leave the queue.
  useEffect(() => {
    if (cursor >= items.length) setCursor(Math.max(0, items.length - 1));
  }, [items.length, cursor]);

  useEffect(() => {
    if (overriding !== null) selectRef.current?.focus();
  }, [overriding]);

  const active: Transaction | undefined = items[cursor];

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      // Never hijack typing in the account picker or any other field.
      const target = event.target as HTMLElement | null;
      if (target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) return;
      if (!items.length) return;

      switch (event.key) {
        case "j":
        case "ArrowDown":
          event.preventDefault();
          setCursor((c) => Math.min(c + 1, items.length - 1));
          break;
        case "k":
        case "ArrowUp":
          event.preventDefault();
          setCursor((c) => Math.max(c - 1, 0));
          break;
        case "a":
          if (active?.suggestion?.coa_valid) {
            event.preventDefault();
            verdict.mutate({ id: active.id, action: "accept" });
          }
          break;
        case "o":
          if (active) {
            event.preventDefault();
            setOverriding(active.id);
          }
          break;
        case "Escape":
          setOverriding(null);
          break;
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [items, active, verdict]);

  const accounts = useMemo(() => coa.data?.accounts ?? [], [coa.data]);

  if (queue.isLoading) return <Card>Loading the queue…</Card>;

  return (
    <div className="space-y-4">
      {flash && (
        <div
          className={`rounded-lg border p-3 text-sm ${
            flash.startsWith("Learned")
              ? "border-accent/40 bg-accent/10 text-accent-strong"
              : flash.startsWith("Accepted")
                ? "border-conf-high/40 bg-conf-high/10 text-conf-high"
                : "border-conf-low/40 bg-conf-low/10 text-conf-low"
          }`}
        >
          {flash}
        </div>
      )}

      <Card
        title={`Review queue · ${queue.data?.total ?? 0} waiting`}
        subtitle={`Lowest confidence first. Anything at or above ${threshold.toFixed(2)} was applied without you.`}
        actions={
          <span className="hidden text-xs text-ink-faint sm:block">
            <kbd className="rounded bg-card-strong px-1.5 py-0.5 font-mono">j</kbd>/
            <kbd className="rounded bg-card-strong px-1.5 py-0.5 font-mono">k</kbd> move ·{" "}
            <kbd className="rounded bg-card-strong px-1.5 py-0.5 font-mono">a</kbd> accept ·{" "}
            <kbd className="rounded bg-card-strong px-1.5 py-0.5 font-mono">o</kbd> override
          </span>
        }
        padded={false}
      >
        {items.length === 0 ? (
          <EmptyState icon="✓" title="Nothing to review">
            Every transaction cleared the confidence gate, or nothing has been categorized yet.
            Import a CSV and run the categorizer to see the queue fill.
          </EmptyState>
        ) : (
          <ul className="divide-y divide-hairline/60">
            {items.map((txn, index) => {
              const selected = index === cursor;
              const suggestion = txn.suggestion;

              return (
                <li
                  key={txn.id}
                  onClick={() => setCursor(index)}
                  className={`px-5 py-3.5 transition-colors ${
                    selected ? "bg-accent/5 ring-1 ring-inset ring-accent/25" : "hover:bg-card/40"
                  }`}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="truncate font-medium text-ink" title={txn.vendor_raw}>
                          {txn.vendor_raw}
                        </span>
                        <span className="tabular shrink-0 text-sm text-ink-muted">
                          {money(txn.amount, txn.currency)}
                        </span>
                      </div>

                      <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-faint">
                        <span>{shortDate(txn.date)}</span>
                        <span className="font-mono opacity-70">→ {txn.vendor_norm}</span>
                        {txn.memo && <span className="opacity-70">{txn.memo}</span>}
                      </div>

                      {suggestion && (
                        <div className="mt-2 flex flex-wrap items-center gap-2">
                          <ConfidencePill
                            confidence={suggestion.confidence}
                            threshold={threshold}
                            coaValid={suggestion.coa_valid}
                            size="sm"
                          />
                          <span className="text-sm text-ink">
                            {suggestion.coa_valid ? (
                              <>
                                <span className="font-mono text-accent">{suggestion.account_code}</span>{" "}
                                {suggestion.account_name}
                              </>
                            ) : (
                              <span className="text-conf-low">
                                suggested {suggestion.account_code || "(blank)"} — not a real account
                              </span>
                            )}
                          </span>
                          <span className="text-xs italic text-ink-faint">“{suggestion.reason}”</span>
                        </div>
                      )}
                    </div>

                    <div className="flex shrink-0 items-center gap-2">
                      {overriding === txn.id ? (
                        <>
                          <select
                            ref={selectRef}
                            defaultValue=""
                            className="rounded-lg border border-hairline bg-paper-raised px-2 py-1.5 text-sm text-ink"
                            onChange={(event) => {
                              if (event.target.value) {
                                verdict.mutate({
                                  id: txn.id,
                                  action: "override",
                                  account: event.target.value,
                                });
                              }
                            }}
                          >
                            <option value="" disabled>
                              Pick the right account…
                            </option>
                            {accounts.map((account) => (
                              <option key={account.code} value={account.code}>
                                {account.code} · {account.name}
                              </option>
                            ))}
                          </select>
                          <Button variant="ghost" onClick={() => setOverriding(null)}>
                            Cancel
                          </Button>
                        </>
                      ) : (
                        <>
                          <Button
                            onClick={() => verdict.mutate({ id: txn.id, action: "accept" })}
                            disabled={verdict.isPending || !suggestion?.coa_valid}
                            title={
                              suggestion?.coa_valid
                                ? "Accept the suggestion"
                                : "The suggested account does not exist — override instead"
                            }
                          >
                            Accept
                          </Button>
                          <Button variant="ghost" onClick={() => setOverriding(txn.id)}>
                            Override
                          </Button>
                        </>
                      )}
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </Card>

      <p className="px-1 text-xs text-ink-faint">
        An override is remembered against the normalized vendor, with a human as the source. The next
        time that vendor appears it is categorized from memory — no model call, and marked “learned”.
      </p>
    </div>
  );
}
