# MODEL_COSTS.md

**The declining-cost story, with the arithmetic shown.**

SpendSort's design claim is that it gets cheaper every month. This file is where that claim
either survives contact with numbers or doesn't. Spec 00 D requires every repo in this portfolio
to publish one.

---

## ⚠️ Read this before quoting any number here

Two caveats, both load-bearing:

1. **Prices are unverified.** The per-token figures below were written on **2026-09-03** and
   could not be confirmed from the build environment (BLOCKERS.md **B4**). Confirm against
   OpenAI's current pricing page before repeating them anywhere that matters.
2. **The measurements are mock-mode.** This environment has no API key (BLOCKERS.md **B3**), so
   no real model was ever called. The token *counts* are realistic and the pricing arithmetic is
   real, which makes the figures **illustrative but internally consistent** — they show the
   shape of the cost curve correctly. They are not a measurement of GPT-4o-mini.

To get real numbers, run `make eval-live` (see [Getting the real numbers](#getting-the-real-numbers)).

---

## Pricing

Model: **gpt-4o-mini** — mini-class, per spec 00 D ("Small everything") and spec 11 §12.

| | USD per 1M tokens |
|---|---|
| input | $0.15 |
| output | $0.60 |

All prices live in **one** place, `backend/app/costs.py`, and are overridable by environment
variable so a price change never needs a code change:

```bash
SPENDSORT_PRICE_INPUT_PER_1M=0.15
SPENDSORT_PRICE_OUTPUT_PER_1M=0.60
```

A model missing from the table falls back to the *priciest* mini-class entry rather than to
zero — a typo in the model name must not silently make the cost cap unenforceable.

## Cost of one categorization

A prompt is the chart of accounts (20 accounts with descriptions) plus one transaction line.

| | tokens | cost |
|---|---|---|
| input | ~1,000 | $0.000150 |
| output | ~60 | $0.000036 |
| **one LLM call** | | **$0.000186** |
| **one memory hit** | 0 | **$0.000000** |

That second row is the whole product. A memory hit costs nothing because the model is never
called — the graph's conditional edge skips `llm_categorize` entirely, which is asserted by a
test that fails if the LLM is invoked at all.

---

## The bend, measured

Two months of the shipped example data (120 transactions each), run end to end over HTTP from a
cold vendor memory:

| run | transactions | memory-hit rate | LLM calls | cost | cost / transaction |
|---|---|---|---|---|---|
| month 1 | 120 | 40.8% | 71 | $0.013206 | $0.000110 |
| month 2 | 120 | **62.5%** | 45 | **$0.008370** | **$0.000070** |

**36.6% cheaper, on identical volume.** Nothing was optimised between the runs and no prompt
changed — the only difference is that memory had seen these vendors before.

Two details worth noticing:

- **Month 1 already shows 40.8% memory hits.** Promotion works *within* a run too: the second
  Starbucks of the month is free. The bend starts on day one, not in month two.
- **The ceiling is measurable, and it is not 100%.** Normalization collapses one vendor's
  descriptors to ~2.4 keys on average, so month 2 could reach at most **68.3%** memory hits
  against month 1's key set (measured in P3). It reached 62.5%. The remaining ~32% is genuinely
  new vendors and new descriptor families, and those will always cost a model call.

### What a real month looks like

The bookkeeper in spec 11 §3 has ~300 card transactions a month.

| | memory-hit rate | LLM calls | monthly cost |
|---|---|---|---|
| month 1 (cold) | 41% | ~177 | $0.033 |
| month 2 | 63% | ~111 | $0.021 |
| steady state *(projected)* | ~75% | ~75 | **~$0.014** |

The steady-state row is a **projection**, not a measurement — it assumes the memory-hit rate
keeps climbing toward the ~68–80% ceiling that normalization allows. The first two rows are
measured and scaled linearly from the 120-transaction runs.

**So: roughly two cents a month, falling.** Categorizing a small business's entire card feed
costs less than a stamp. That is the honest headline, and it is less exciting than "we cut costs
40%" — the 40% is real, but it is 40% of almost nothing.

### Why the cost cap almost never fires

Spec 11 §11 mandates a **$0.25 per-run cap** (default). At $0.000186 a call, that is ~1,340
transactions of brand-new vendors in a single run. A 300-row month costs about **$0.033**, or
13% of the cap.

So the cap is a **circuit breaker, not a budget**. It exists for the pathological case — a
10,000-row backfill, a misconfigured expensive model, a retry storm — and it is designed to fail
safely: when the cap is reached the remaining transactions are **queued for review, never
dropped**, and memory hits keep working for free because they cost nothing. There is a test for
each of those properties.

If you want the cap to actually bite during a demo, lower it:

```bash
SPENDSORT_COST_CAP_USD_PER_RUN=0.001   # ~5 calls, then everything queues
```

---

## Keeping it cheap

Ordered by how much they matter:

1. **Memory-first is the whole strategy.** Every mechanism that grows vendor memory reduces
   spend permanently: human overrides (spec 11 F3) and promotion of answers the gate already
   trusted (F4). One correction is paid for once and never again.
2. **Normalization quality is a cost lever, not just a correctness one.** Every extra key a
   vendor produces is one more LLM call before memory covers it. Improving the normalizer from
   14.9 keys per vendor to 2.4 (see P3 in PROGRESS.md) cut the long-run bill by roughly the same
   factor. This is the least obvious and highest-leverage tuning available.
3. **Stay mini-class.** `gpt-4o` would cost ~17× more input and ~17× more output for a task
   that is vendor-string pattern matching. The eval suite is how you check whether the cheaper
   model is good enough — run `make eval-live` on both and compare auto-precision.
4. **Keep the chart of accounts tight.** The CoA is in every prompt, so it is most of the input
   tokens. 20 accounts is ~1,000 tokens; 200 accounts would roughly 5× the per-call cost.
5. **Batch the month, don't stream the day.** One run over 300 transactions and one run over 10
   cost the same per transaction, but a monthly cadence gives memory a chance to accumulate
   before the next pass.
6. **Mock mode is free and complete.** `SPENDSORT_MOCK_LLM=1` runs the entire product — upload,
   run, queue, override, learn, dashboard, export — with no API calls at all. Use it for
   development, demos and CI; spend money only when measuring quality.

## Infrastructure

Nothing to add. SQLite on disk, a FastAPI process, a static SPA. No hosted database, no vector
store, no queue, no Azure resources — this is a Track-1 project and spec 00 D expects it to run
at ~$0. There is nothing to `azd down`.

---

## Getting the real numbers

```bash
export OPENAI_API_KEY=sk-...          # PowerShell: $env:OPENAI_API_KEY = "sk-..."
make eval-live                        # 100 cases against the real model
```

Expected spend: **$0.01–0.02** for the full suite (100 cases, minus memory hits). The command
prints accuracy, auto-precision and queue-recall, writes `evals/report_live.json`, and exits
non-zero if auto-precision falls below the 95% gate.

Then update this file with what you measured, and delete the caveat at the top.
