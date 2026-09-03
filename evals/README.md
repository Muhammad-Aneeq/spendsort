# evals/

**⚠️ All data synthetic.** 100 ledgerfab transactions with ground-truth categories
(spec 11 §10). Every repo in this portfolio ships an eval gate — it is the brand (spec 00 A1).

```bash
make eval        # mock mode, no key, no spend — this is what CI runs
make eval-live   # the REAL model; costs roughly $0.01–0.02
```

---

## What is measured, and why

| Metric | Question it answers | Gate |
|---|---|---|
| **accuracy** | How often is the agent right? | reported |
| **auto-precision** | Of the decisions it made *without a human*, how many were right? | **≥ 95% (CI gate)** |
| **queue-recall** | Of the decisions it got *wrong*, how many did it queue instead of posting? | regression floor |
| auto-rate | How much work did it actually take off a human? | ≥ 50% |
| ambiguous-queued | On vendors with two defensible accounts, did confidence drop? | reported |

Only the middle two really matter.

**Auto-precision** is the trust number. It ignores everything that went to the queue, because a
queued row already has a human on it. It asks the only question a bookkeeper cares about: *when
this thing acted on its own, was it right?*

**Queue-recall** is the honesty number. Being wrong is survivable — an agent that is wrong but
uncertain routes the row to a person and costs ten seconds. Being *confidently* wrong posts a
bad entry and costs a correcting journal, a reconciliation, and some credibility. Queue-recall
is the fraction of errors that ended up in the queue rather than in the ledger.

**Why auto-rate is also gated.** Auto-precision alone is gameable: an agent that queues
everything auto-applies nothing and scores a perfect 100%. The minimum auto-rate closes that
loophole.

---

## ⚠️ What a green CI gate does *not* mean

In CI this suite runs against `MockCategorizer`, not a real model. **A passing mock-mode gate
measures the harness** — that scoring, routing, the chart-of-accounts gate and memory promotion
all behave correctly. It says nothing about how good GPT-4o-mini is at bookkeeping.

This is not a hedge, it is a design constraint: the build environment has no API key
(BLOCKERS.md B3), and running paid calls in CI on every push would be both slow and wasteful.

The mock is a **fixture with deliberately planted defects** (PLAN.md D8):

- vendors it confuses between adjacent accounts, *confidently* — these are the auto-precision failures
- vendors it does not recognise at all — these should be queued
- a confident, well-formed, **non-existent** account code — this must be caught by the CoA gate

The first version of this mock had none of that and scored **100% accuracy**, which made the
gate pass vacuously: queue-recall was computed from 0/0 wrong answers and the CoA gate was never
exercised. `test_the_fixture_actually_contains_errors` now fails if anyone turns the mock back
into an oracle, and `test_a_deliberately_bad_agent_fails_the_gate` proves the gate has teeth by
running an agent that is confidently wrong about everything.

**For a real number, run `make eval-live`.**

---

## Current mock-mode results

At the shipped defaults (threshold 0.85, 100 cases):

```
accuracy               95.00%
auto-precision         96.10%   GATE >= 95%  [PASS]
queue-recall           40.00%   (2/5 wrong answers were queued)
auto-rate              77.00%   (77 auto, 23 queued)

wrong AND auto-applied     3    <- the ones that hurt
ambiguous cases queued     21/39
out-of-CoA answers caught  2
```

### A finding worth knowing: a higher threshold is not automatically safer

| threshold | auto-precision | auto-rate | gate |
|---|---|---|---|
| 0.75 | 96.10% | 77% | PASS |
| 0.80 | 96.10% | 77% | PASS |
| **0.85** | **96.10%** | **77%** | **PASS** |
| 0.90 | 94.23% | 52% | **FAIL** |

Raising the threshold to 0.90 makes auto-precision *worse*. The reason is instructive: the
fixture's mistakes are asserted at 0.92 confidence, so they survive a 0.90 cut, while a third
of the *correct* answers (0.86–0.90) get queued. Tightening the gate discarded good work and
kept the confident errors.

The lesson generalises beyond this fixture — **a threshold only buys safety when the model's
errors are less confident than its correct answers.** Checking that assumption is exactly what
this suite is for, and it is why the default stays at 0.85.

---

## Files

| file | what it is |
|---|---|
| `cases.jsonl` | the 100 cases. Regenerate with `make seed` |
| `build_cases.py` | generator, fixed seed (`realistic`, seed 2026), hash-verifiable |
| `harness.py` | scoring: accuracy, auto-precision, queue-recall |
| `test_eval_gate.py` | the CI gate |
| `run_live.py` | the same suite against the real model |
| `report.json` | last run's full output, per case (CI artifact; gitignored) |

## Reproducibility

The case file comes from a fixed ledgerfab seed, and the world is hash-verifiable (spec 00 A3),
so a change in the numbers means a change in the **agent** — never a reshuffled dataset. Each
case records its ground-truth account, its counterparty, and whether it is ambiguous. Ground
truth never appears in any field the agent reads; `test_the_cases_do_not_leak_the_account_code`
enforces that.

The eval always starts from an **empty** vendor memory. A warm memory would flatter the result.
Within-run promotion *is* in scope, though: if the first Amazon is confidently wrong and
auto-applied, later Amazons inherit the error. That amplification is a genuine risk of a
memory-first design, so it is measured rather than excluded.
