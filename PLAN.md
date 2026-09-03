# PLAN.md · SpendSort

**Living document.** Ticked as work lands. Every phase re-reads its spec section before coding.
Status legend: `[ ]` todo · `[x]` done · `[~]` in progress · `[B]` BLOCKED (see BLOCKERS.md)

Ground truth: `docs/spec_00_shared_foundations.md`, `docs/spec_11_spendsort.md`.

---

## 1. FIVE-LINE SUMMARY (spec comprehension)

1. SpendSort categorizes synthetic card transactions against an editable chart of accounts using a **LangGraph graph of exactly 4 nodes** — `normalize_vendor → check_memory → llm_categorize → route` — where a vendor-memory hit **bypasses the LLM entirely** (spec 11 §4 F2/F4).
2. Every decision carries `{account_code, confidence, reason ≤20 words}` from **enforced Pydantic structured output at temperature 0.1**; `account_code` is validated against the CoA **in code**, and an out-of-CoA answer is **forced to low confidence and queued** rather than trusted (spec 11 §8).
3. The gate is the product: decisions at/above threshold auto-apply, everything else lands in a **lowest-confidence-first review queue** with one-click accept/override; an override writes `vendor_memory` with `source=human`, so the **next occurrence of that vendor auto-categorizes from memory and is marked "learned"** (spec 11 §4 F3, US3).
4. Because memory serves more traffic each run, the LLM is called less and **cost-per-run visibly bends downward** — the dashboard charts memory-hit rate and cost trend across runs, and per spec 11 §8 *"that chart IS the launch post"* (spec 11 §4 F5, §9 screen 5).
5. Honesty is enforced by evals: **100 ledgerfab transactions with ground truth**, gating CI on **auto-precision ≥ 95%** (accuracy of auto-applied lines only) plus **queue-recall** — wrong answers must land in the queue, not auto-apply — with a **$0.25 per-run cost cap** and a synthetic-data banner (spec 11 §10, §11).

**The one thing that must be true:** SpendSort is allowed to be wrong, but it is *not* allowed to be wrong *confidently*. Errors belong in the queue.

---

## 2. FILE MAP (complete)

Files marked `NEW` are authored here; `MOVE` is relocation of existing content.

```
spendsort/
├── PLAN.md                              NEW  this document (living)
├── PROGRESS.md                          NEW  per-phase log, appended as work lands
├── BLOCKERS.md                          NEW  what/tried/needed/workaround per blocker
├── FINAL_REPORT.md                      NEW  demo script, commands, blockers, next three
├── README.md                            NEW  pitch → architecture (mermaid) → synthetic banner → quickstart → STATUS
├── MODEL_COSTS.md                       NEW  declining-cost story + per-run math
├── LICENSE                              NEW  MIT (spec 00 A1)
├── Makefile                             NEW  install · dev · test · eval · eval-live · seed · lint · typecheck · up · down
├── make.ps1                             NEW  PowerShell shim — `make` absent on this box (BLOCKERS.md B2)
├── pyproject.toml                       NEW  single uv project for the whole repo (D11); pytest markers `live` + `eval`
├── uv.lock                              NEW  committed for reproducible resolution (D14)
├── Dockerfile                           NEW  2-stage: build SPA → python runtime serving it (referenced by compose)
├── docker-compose.yml                   NEW  spec 11 §12
├── .env.example                         NEW  OPENAI_API_KEY, SPENDSORT_MODEL, thresholds, cost cap
├── .gitignore                           NEW
├── .github/workflows/ci.yml             NEW  ruff → mypy → pytest → eval gate → frontend build (spec 00 A1)
├── docs/
│   ├── spec_00_shared_foundations.md    MOVE from repo root
│   ├── spec_11_spendsort.md             MOVE from repo root
│   └── architecture.md                  NEW  mermaid diagram + node-by-node walkthrough
├── examples/                            NEW  ledgerfab-generated, shipped so the demo needs no generation step
│   ├── month_01_realistic_seed42.csv         ~120 txns, first run (cold memory)
│   ├── month_02_realistic_seed43.csv         ~120 txns, repeat vendors → drives the memory bend
│   ├── ambiguous_edge_cases.csv              two-plausible-account cases (spec 11 §14)
│   └── README.md                             provenance: profile + seed + regeneration command
├── backend/
│   ├── ledgerfab/                       NEW  reimplemented from spec 00 A3 (seed dir absent — BLOCKERS.md B1)
│   │   ├── __init__.py                       public API: generate(profile, seed) -> World
│   │   ├── config.py                         knobs + presets clean | realistic | nightmare
│   │   ├── models.py                         World, Company, Account, Counterparty, BankTxn, GroundTruth
│   │   ├── coa.py                            default chart of accounts (CoA-aligned labels)
│   │   ├── vendors.py                        counterparty catalog + alias / descriptor chaos
│   │   ├── generate.py                       seeded, reproducible world generation
│   │   ├── ground_truth.py                   ground-truth emitter (labels for free, spec 00 A3)
│   │   └── export.py                         World → transactions CSV
│   ├── app/
│   │   ├── main.py                      NEW  FastAPI app, CORS, router wiring, static SPA mount
│   │   ├── settings.py                  NEW  pydantic-settings (threshold, cost cap, model, mock flag)
│   │   ├── logging.py                   NEW  structured logging (spec 00 A1)
│   │   ├── db.py                        NEW  SQLAlchemy engine/session, SQLite dev
│   │   ├── models.py                    NEW  ORM: transactions, categorizations, verdicts, vendor_memory, runs
│   │   ├── schemas.py                   NEW  Pydantic v2 DTOs incl. LLM structured-output model
│   │   ├── coa.py                       NEW  YAML CoA load + in-code account_code validation
│   │   ├── coa_default.yaml             NEW  shipped sensible default CoA (spec 11 §4 F1)
│   │   ├── normalize.py                 NEW  aggressive vendor normalization (spec 11 §14 risk)
│   │   ├── costs.py                     NEW  token→USD pricing table + per-run cost cap enforcement
│   │   ├── agent/
│   │   │   ├── state.py                 NEW  graph state (TypedDict)
│   │   │   ├── graph.py                 NEW  EXACTLY 4 nodes; conditional edge skips LLM on memory hit
│   │   │   ├── nodes.py                 NEW  normalize_vendor · check_memory · llm_categorize · route
│   │   │   ├── llm.py                   NEW  langchain-openai structured output; injectable fake for tests
│   │   │   └── prompts.py               NEW  categorization prompt (reason ≤20 words, temp 0.1)
│   │   ├── services/
│   │   │   ├── ingest.py                NEW  CSV parse + hardening (spec 11 §11)
│   │   │   ├── runner.py                NEW  run orchestration, cost cap, run-level metric rollup
│   │   │   ├── memory.py                NEW  vendor_memory read/write, hit_count, source precedence
│   │   │   ├── metrics.py               NEW  histogram, auto-rate, memory-hit trend, cost trend
│   │   │   └── export.py                NEW  CSV out: account, confidence, source, reason
│   │   └── routers/                     NEW  one module per spec 11 §7 endpoint
│   │       ├── ingest.py · runs.py · queue.py · verdicts.py
│   │       └── memory.py · metrics.py · export.py · coa.py
│   └── tests/                           NEW  LLM mocked by default (adaptation 3)
│       ├── conftest.py                       temp DB, TestClient, FakeLLM fixture
│       ├── test_ledgerfab_determinism.py     same seed+profile → identical dataset (spec 00 A3)
│       ├── test_normalize.py                 alias chaos → stable vendor_norm
│       ├── test_coa_validation.py            out-of-CoA → forced low confidence + queue
│       ├── test_graph_shape.py               node count == 4, exactly
│       ├── test_graph_memory_bypass.py       memory hit ⇒ LLM never invoked
│       ├── test_routing_threshold.py         auto ≥ threshold, else queue
│       ├── test_memory_learning.py           override → re-run auto + source "learned"
│       ├── test_cost_cap.py                  cap reached ⇒ remainder queued, never silently dropped
│       ├── test_ingest_csv.py                malformed/hostile CSV handling
│       ├── test_api_smoke.py                 every §7 endpoint
│       └── test_export.py                    per-line {account, confidence, source, reason}
├── evals/
│   ├── build_cases.py                   NEW  regenerate cases.jsonl from a fixed ledgerfab seed
│   ├── cases.jsonl                      NEW  100 transactions + ground-truth categories (spec 11 §10)
│   ├── harness.py                       NEW  accuracy · auto-precision · queue-recall
│   ├── test_eval_gate.py                NEW  CI gate: auto-precision ≥ 95%
│   ├── run_live.py                      NEW  same suite against the real API (`live` marker)
│   └── README.md                        NEW  what is measured and why each metric exists
└── frontend/
    ├── package.json · vite.config.ts · tsconfig.json          NEW  Tailwind v4 via plugin — no tailwind/postcss config (D12)
    ├── index.html                                             NEW  Space Grotesk + Inter
    └── src/
        ├── main.tsx · App.tsx · index.css                     NEW  routing + aurora tokens
        ├── lib/api.ts · lib/types.ts · lib/format.ts          NEW  typed API client
        ├── components/aurora/                                 NEW  spec 00 A2 tokens (adaptation 2)
        │   ├── tokens.css                                          navy #0B1E3B, emerald #10B981, frosted glass
        │   ├── Card.tsx · ConfidencePill.tsx                       ConfidencePill: 0-1 → colour + label
        │   ├── MetricTile.tsx · SyntheticDataBanner.tsx
        │   └── index.ts
        └── pages/                                             NEW  the five screens of spec 11 §9
            ├── Import.tsx      (1) CSV upload + CoA editor
            ├── Run.tsx         (2) run progress + confidence histogram
            ├── Queue.tsx       (3) lowest-confidence-first, accept/override, keyboard flow
            ├── Memory.tsx      (4) learned mappings + hit counts
            └── Metrics.tsx     (5) auto-rate trend, cost trend, memory-bend chart
```

---

## 3. PHASES

Phase grouping follows **spec 11 §13**: *"W1 intake + CoA + graph + memory + routing + evals · W2 queue UI + dashboard + export + README + 90s demo video (the series opener)"*.
**W1 = P1–P6 · W2 = P7–P9.** Each phase ends with tests green, PROGRESS.md updated, and one commit.

### P0 · Planning (this document) — W1 ✅ DONE
- [x] Read both specs fully, end to end
- [x] Survey environment and toolchain; record gaps
- [x] Author PLAN.md: summary, file map, phases, dependencies, decisions
- [x] Open BLOCKERS.md for the missing ledgerfab seed and absent `make` (B1–B5 recorded)
- [x] Initialise git (repo was not version-controlled) and commit Phase 0

**Acceptance:** *"PHASE 0: PLAN.md before any code"* — no application code until this document is complete.
**Test plan:** none (documentation phase); self-check that every non-negotiable constraint in the brief appears as at least one checkbox below.
**Risk:** a plan that drifts from reality. Mitigation: PLAN.md is re-ticked at the end of every phase, and phases re-read their spec section first.

### P1 · Scaffold & foundations — W1 ✅ DONE
- [x] `git init` (repo was not under version control) + `.gitignore`
- [x] `MOVE` both specs to `docs/`
- [x] `pyproject.toml` via uv: FastAPI, Pydantic v2, SQLAlchemy, langgraph, langchain-openai, pyyaml, pytest; `live` + `eval` markers registered. **At repo root, not `backend/`** — see D11
- [x] `frontend/` Vite + React 19 + TS + Tailwind **v4** bootstrap (D12); aurora tokens in `components/aurora/tokens.css`
- [x] `Makefile` + `make.ps1` shim: `install dev dev-api dev-web test test-live eval eval-live seed lint fmt typecheck up down clean`
- [x] `.env.example`, `docker-compose.yml`, `Dockerfile`, MIT `LICENSE`
- [x] `.github/workflows/ci.yml`: ruff → mypy → pytest → **eval gate** (separate job) → frontend build
- [x] `app/settings.py`, `app/logging.py` (structured JSON), `app/db.py`, `GET /api/health`
- [x] API port made overridable after finding 8000 occupied on this box (D13, BLOCKERS.md B6)

**Acceptance (spec 00 A1):** *"`make up` runs a hello dashboard; `make eval` runs an empty pass; CI green on a fresh clone."* Stack exactly per spec 00 F: *"Python everywhere · FastAPI backends · Vite+React+TS frontends · LangChain + LangGraph for agent orchestration · no LangChain-classic chains (LCEL/LangGraph only)."*
**Test plan:** `test_api_smoke.py::test_health` green; `make test` and `make eval` both exit 0 on an empty suite; frontend dev server boots and renders a placeholder.
**Verified:** `pytest` → 2 passed, 1 skipped · `pytest evals` → honest empty pass (skip, cases.jsonl arrives P5) · `ruff check` + `ruff format --check` clean · `mypy backend/app` clean · `npm run build` → `tsc --noEmit` clean + bundle built · uvicorn boots, `/api/health` returns 200 with the trust settings, and the built SPA is served from `/` · all seven aurora token utilities confirmed present in the compiled CSS · `./make.ps1 help|test|eval` all work.
**Not yet verified:** `mypy` on `backend/ledgerfab` (the target is in the Makefile and CI; the package lands in P2) and CI on a real runner (no git remote yet).
**Risk:** dependency resolution churn on Windows/Python 3.12. Mitigation: pin via `uv.lock`, committed. *Outcome: resolved clean; uv picked LangGraph 1.2.11 / langchain-openai 1.6.0 — the 1.x line, newer than the floors in the spec era. Noted in D14.*

**Acceptance (spec 00 A1):** *"`make up` runs a hello dashboard; `make eval` runs an empty pass; CI green on a fresh clone."* Stack exactly per spec 00 F: *"Python everywhere · FastAPI backends · Vite+React+TS frontends · LangChain + LangGraph for agent orchestration · no LangChain-classic chains (LCEL/LangGraph only)."*
**Test plan:** `test_api_smoke.py::test_health` green; `make test` and `make eval` both exit 0 on an empty suite; frontend dev server boots and renders a placeholder.
**Risk:** dependency resolution churn on Windows/Python 3.12. Mitigation: pin via `uv.lock`, committed.

### P2 · ledgerfab — W1 ✅ DONE
- [x] Reimplement per spec 00 A3 (B1 fallback): typed `World`, 20-account CoA, 51 counterparties **with aliases**, bank transactions
- [x] Knobs: `alias_rate`, `date_format_chaos`, `amount_noise`, `duplicate_rate`, `missing_reference_rate`, `partial_payment_rate`, `fx_rate` (flag-only); presets `clean` / `realistic` / `nightmare`
- [x] Ground-truth emitter — correct account per transaction, known **by construction**, with ambiguous rows flagged and their alternate account named
- [x] `World → CSV` export; the three `examples/` files generated with recorded seeds + published content hashes
- [x] Determinism test (+ 21 more): same seed+profile ⇒ identical hash; profile is part of the seed; generator never reads the clock
- [x] `backend/app/coa_default.yaml` **generated** from `ledgerfab/coa.py`, so eval ground truth cannot drift out of CoA alignment

**Acceptance (spec 00 A3):** *"`ledgerfab.generate(profile, seed)` returns a typed World; `world.ground_truth` gives correct matches; determinism test passes"* and *"Seeded → reproducible (same seed+profile = identical dataset, hash-verifiable)."*
**Test plan:** `test_ledgerfab_determinism.py` — same seed+profile twice ⇒ identical content hash; different seed ⇒ different hash; every emitted transaction's ground-truth account is a member of the CoA.
**Verified:** 24 tests pass. Determinism holds across all three presets; `clean` is genuinely clean on every knob; alias share rises `clean` 0% → `realistic` >50% → `nightmare` higher still; splits reconcile and are uneven >80% of the time; duplicates are exact same-day copies; row count is exact even with splits/duplicates; ruff + mypy clean.
**Two bugs the tests caught (fixed in the generator, not the test):** descriptor case/spacing mangling ignored `alias_rate`, so `clean` produced 27.5% mangled descriptors; and partial payments split into exact halves, making them indistinguishable from duplicated rows.
**Measured for P8:** 93.3% of `month_02` rows use a vendor already seen in `month_01` — that is the ceiling on the memory-hit rate, so the cost bend will be clearly visible rather than hoped for.
**Risk:** scope creep into invoices/POs/GL that SpendSort never reads. Mitigation: build only the transaction + counterparty-alias + ground-truth surface SpendSort needs; leave the rest documented as out of scope in DECISIONS LOG D3. *Outcome: held — no invoice/PO/GL/accrual code was written.*

### P3 · Data model, CoA, intake — W1 ✅ DONE
- [x] ORM tables exactly per spec 11 §6: `transactions`, `categorizations`, `verdicts`, `vendor_memory`, `runs` (+ `categorizations.run_id`, needed for the cross-run memory-bend chart, and run-level audit of the cost cap)
- [x] `coa_default.yaml` + loader + **in-code** membership validation, fail-closed on every hallucination shape
- [x] Aggressive vendor normalization (case, punctuation, processor prefixes, references, store numbers, domains, city/state tails, legal suffixes, bank shorthand)
- [x] `POST /api/ingest/csv` with CSV hardening; `GET/PUT /api/coa` + `GET /api/coa/yaml`

**Acceptance (spec 11 §4 F1):** *"CSV upload (date, amount, vendor/description, currency) … chart of accounts as editable YAML (ship a sensible default CoA)."* Plus spec 11 §11: *"CSV hardening."*
**Test plan:** `test_normalize.py` over ledgerfab alias chaos (asserting aliases of one counterparty collapse to one `vendor_norm`); `test_coa_validation.py`; `test_ingest_csv.py` covering formula-injection cells, BOM, mixed date formats, negative/blank amounts, oversized upload.
**Verified:** 154 tests pass; ruff, ruff format, mypy all clean. Normalization measured on a 2 000-row nightmare-profile sample: **zero key collisions**, **fully idempotent**, mean **2.38** keys per vendor (worst 4) — down from 14.90 / 46 in the first draft. All three shipped example CSVs import with **zero rejected rows**. CoA↔ledgerfab alignment asserted, so drift fails CI.
**Plan correction:** the original test plan said aliases of one counterparty collapse to *one* `vendor_norm`. They do not, and asserting it would have been false. `HISCOX INS` and `HISCOX PREMIUM` are genuinely different descriptor families. The tests instead assert the three properties that actually matter — **purity** (no key shared by two vendors, the only failure that would teach memory a wrong account), **idempotence**, and **collapse** to few keys — and the module documents the limit rather than hiding it.
**Bugs the tests caught:** `parse_currency` truncated to three characters *before* validating, so `"dollars"` became a confident-looking `"DOL"`; and `&` was treated as a mergeable initial, turning `HARBOR & VANCE` into `HARBOR &VANCE`.
**Risk (spec 11 §14):** *"Vendor normalization quality (messy descriptors) → normalize aggressively, test on ledgerfab alias chaos."* Mitigation: the normalizer is tested directly against generated alias sets, not hand-written strings. *Outcome: the probe found four real defects — two of them in ledgerfab's own realism (references glued onto vendor names, which real feeds do not do) — see PROGRESS.md.*

**Acceptance (spec 11 §4 F1):** *"CSV upload (date, amount, vendor/description, currency) … chart of accounts as editable YAML (ship a sensible default CoA)."* Plus spec 11 §11: *"CSV hardening."*
**Test plan:** `test_normalize.py` over ledgerfab alias chaos (asserting aliases of one counterparty collapse to one `vendor_norm`); `test_coa_validation.py`; `test_ingest_csv.py` covering formula-injection cells, BOM, mixed date formats, negative/blank amounts, oversized upload.
**Risk (spec 11 §14):** *"Vendor normalization quality (messy descriptors) → normalize aggressively, test on ledgerfab alias chaos."* Mitigation: the normalizer is tested directly against generated alias sets, not hand-written strings.

### P4 · Categorization graph, memory, routing, cost cap — W1 ✅ DONE
- [x] Graph with **exactly 4 nodes**: `normalize_vendor → check_memory → llm_categorize → route`
- [x] Conditional edge: memory hit routes `check_memory → route`, **skipping the LLM**
- [x] `llm_categorize`: Pydantic structured output `{account_code, confidence, reason}`, temperature 0.1, reason ≤20 words enforced by truncation
- [x] Out-of-CoA `account_code` ⇒ forced low confidence + queue (the rejected code is still shown to the reviewer)
- [x] `route`: auto if `confidence ≥ threshold`, else queue; persists `categorizations.source` as `memory | llm`
- [x] `vendor_memory` write on override with `source=human`; `hit_count` increments; re-run marks "learned"
- [x] Per-run cost cap (default **$0.25**): on exhaustion, remaining transactions are **queued, never silently dropped**
- [x] `POST /api/runs` + `GET /api/runs` orchestration + `runs` row rollup
- [x] `POST /api/txns/{id}/verdict` — pulled forward from P6, because the learning loop cannot be proven without it
- [x] `llm-confirmed` promotion: an auto-applied, CoA-valid LLM answer enters memory. **This is the mechanism behind the bend** — if only human overrides were remembered, memory would stay nearly empty and "gets cheaper every month" would be theatre

**Verified:** 213 tests pass; ruff, format, mypy clean. The graph has exactly 4 nodes with the bypass as an edge. The bypass is proven with an `ExplodingCategorizer` that raises if called at all — asserting `source == "memory"` would still have passed if the LLM had been called and its answer discarded, i.e. if money had been spent. Threshold tested at 0.8499 / 0.85 / 0.86, inclusive as the spec's "≥" requires. Out-of-CoA codes queue at **every** confidence, including 0.99.
**Measured end to end on the shipped example files, mock mode.** *(Figures below are the P8 re-measurement. P4's original numbers — 78.3%/41.7%/$0.01302 and 85.0%/65.0%/$0.00781 — were taken before P5 deliberately made the mock fallible, which changed them. The current numbers are the ones quoted everywhere else.)*

| run | txns | auto-rate | memory-hit | LLM calls | cost |
|---|---|---|---|---|---|
| month 1 | 120 | 75.8% | 40.8% | 71 | $0.013206 |
| month 2 | 120 | 81.7% | **62.5%** | 45 | **$0.008370** |

**The bend is real: 36.6% cheaper per run, LLM calls 71 → 45, memory-hit rate up 21.7 points.** Out-of-CoA hallucinations correctly queued; 0 transactions lost.

**Acceptance (spec 11 §4 F2):** *"Categorization graph (LangGraph, ≤4 nodes): `normalize_vendor → check_memory (learned mappings first, zero LLM cost) → llm_categorize (structured output: {account_code, confidence, reason}) → route (auto ≥ threshold | queue)`."* Spec 11 §8: *"account_code must be in the CoA (validated in code; out-of-CoA = forced low confidence + queue). Reason ≤ 20 words. Temperature 0.1."* Spec 11 §4 F4: *"memory hits bypass the LLM entirely."* Spec 11 §11: *"cost cap per run (default $0.25)."*
**Test plan:** `test_graph_shape.py` asserts the compiled graph has exactly 4 nodes; `test_graph_memory_bypass.py` injects a FakeLLM that **fails the test if invoked** on a memory hit; `test_routing_threshold.py` boundary cases at, just below, and just above threshold; `test_coa_validation.py` hallucinated account code ⇒ queued; `test_memory_learning.py` override → re-run ⇒ auto + `source` learned-from-human; `test_cost_cap.py` cap reached mid-run ⇒ remainder queued and run row records the truncation.
**Risk (spec 11 §14):** *"CoA ambiguity (two plausible accounts) → confidence must drop, tested with deliberately ambiguous eval cases."* Mitigation: `examples/ambiguous_edge_cases.csv` and a matching eval slice assert confidence lands **below** threshold rather than asserting a specific account.

### P5 · Evals & CI gate — W1 ✅ DONE
- [x] `build_cases.py` → `cases.jsonl`, **exactly 100** ledgerfab transactions with ground truth (fixed seed, hash-verifiable, 18/20 accounts, 39 ambiguous)
- [x] `harness.py`: accuracy, **auto-precision** (auto-applied lines only), **queue-recall**, plus auto-rate and ambiguous-queued-rate
- [x] `test_eval_gate.py` fails CI below 95% auto-precision
- [x] Deterministic mock-mode scorer (CI) + `run_live.py` for the real model
- [x] Gate wired into `ci.yml` as its own job, with `report.json` uploaded as an artifact
- [x] Ground truth proven not to leak into any field the agent reads
- [x] `test_a_deliberately_bad_agent_fails_the_gate` — the gate is shown to have teeth

**Verified:** 226 tests pass (no skips); ruff, format, mypy clean.

| metric | value | gate |
|---|---|---|
| accuracy | 95.00% | reported |
| **auto-precision** | **96.10%** | **≥95% → PASS** |
| queue-recall | 40.00% (2/5) | ≥30% floor |
| auto-rate | 77.00% (77 auto / 23 queued) | ≥50% |
| wrong **and** auto-applied | 3 | the ones that hurt |
| out-of-CoA caught & queued | 2 | must be 0 auto-applied |

**The bug this phase found in itself — and it was the important one.** The first mock scored
**100% accuracy**, which made the gate pass *vacuously*: queue-recall was computed from 0/0 wrong
answers and the CoA gate was never exercised. The cause was structural, not a tuning slip — the
mock's rule table had been written from the *same vendor catalogue that generates the data*, so it
was a lookup table, not a model. Exactly the failure D8 was written to prevent, and it still
happened. The mock now carries planted, documented defects (confident confusions between adjacent
accounts, unrecognised vendors, a well-formed non-existent code), and
`test_the_fixture_actually_contains_errors` fails if anyone turns it back into an oracle.

**A finding worth the launch post: a higher threshold is not automatically safer.**

| threshold | auto-precision | auto-rate | gate |
|---|---|---|---|
| 0.75 / 0.80 / **0.85** | 96.10% | 77% | PASS |
| 0.90 | **94.23%** | 52% | **FAIL** |

Raising the threshold to 0.90 makes auto-precision *worse*: the fixture's errors are asserted at
0.92 and survive the cut, while a third of the *correct* answers (0.86–0.90) get queued. Tightening
discarded good work and kept the confident mistakes. A threshold only buys safety when the model's
errors are less confident than its correct answers — and checking that assumption is what this
suite is for. **Default stays at 0.85** (D10 confirmed by measurement, not assumption).

**Acceptance (spec 11 §10):** *"evals/: 100 ledgerfab transactions with ground-truth categories (CoA-aligned); metrics: accuracy, auto-precision (accuracy of auto-applied only: must be ≥ 95%), queue-recall (wrong ones must land in queue, not auto). Memory tests: override → next occurrence auto + correct. CI gate on auto-precision."*
**Test plan:** the eval suite is itself the test; additionally assert `cases.jsonl` has exactly 100 rows, every ground-truth account is CoA-aligned, and queue-recall is reported (not just accuracy) so a "confidently wrong" regression cannot pass.
**Risk:** a mock LLM that flatters the gate — 100% precision in CI proves nothing about the real model. Mitigation: the mock replays a **fixed, deliberately imperfect** response fixture including wrong and out-of-CoA answers, so queue-recall is genuinely exercised; README STATUS states plainly that the CI number is mock-mode, and the live command is handed to the reviewer in FINAL_REPORT.md.

### P6 · Remaining API surface — W1→W2 ✅ DONE
- [x] `GET /api/queue` — lowest-confidence-first (+ `GET /api/queue/transactions` with a status filter, for the run view and ledger table)
- [x] `POST /api/txns/{id}/verdict` — accept | override, writes `verdicts` + `vendor_memory` *(landed in P4)*
- [x] `GET /api/memory` · `GET /api/metrics` · `GET /api/export`
- [x] Metrics payload carries the **per-run series** for the memory-bend chart
- [x] Export neutralises CSV formula injection and ships a BOM so Excel reads the em-dash accounts

**Acceptance (spec 11 §7):** *"POST /api/ingest/csv · POST /api/runs (categorize all pending) · GET /api/queue · POST /api/txns/{id}/verdict · GET /api/memory · GET /api/metrics · GET /api/export."*
**Test plan:** `test_api_smoke.py` exercises all eight endpoints; queue ordering asserted; `test_export.py` asserts the four required per-line fields.
**Verified:** 257 tests pass; ruff, format, mypy clean. Endpoint registration is asserted **against the live OpenAPI schema**, not a comment. `test_the_run_series_shows_the_memory_bend` asserts memory-hit rate rises and cost falls across two real months — the launch claim is a test, not a hope. `test_the_definition_of_done_end_to_end` walks upload → run → queue → override → re-run → learned → export in one pass.
**Risk:** metrics shaped for one screen, then reshaped for charts. Mitigation: design the metrics response from the P8 chart requirements first, then build the endpoint to it. *Outcome: held — the run series and the histogram's per-bin `auto` flag were both designed for the charts before the endpoint was written.*

**Acceptance (spec 11 §7):** *"POST /api/ingest/csv · POST /api/runs (categorize all pending) · GET /api/queue · POST /api/txns/{id}/verdict · GET /api/memory · GET /api/metrics · GET /api/export."*
**Test plan:** `test_api_smoke.py` exercises all eight endpoints; queue ordering asserted; `test_export.py` asserts the four required per-line fields.
**Risk:** metrics shaped for one screen, then reshaped for charts. Mitigation: design the metrics response from the P8 chart requirements first, then build the endpoint to it.

### P7 · Aurora components + frontend screens — W2 ✅ DONE
- [x] `components/aurora/`: `Card` (frosted), `ConfidencePill` (0-1 → colour + label), `MetricTile`, `SyntheticDataBanner`, plus `EmptyState` and `Button` — spec 00 A2 tokens
- [x] Screens 1–4: Import + CoA editor · Run view · Review Queue · Memory
- [x] Queue: one-click accept, override account picker, **keyboard flow** (`j`/`k` move, `a` accept, `o` override, `Esc` cancel)
- [x] Typed API client; TanStack Query for fetch/invalidate
- [x] **22 render tests** across all five screens (vitest + jsdom), wired into CI — substituting for the visual walkthrough this environment cannot do (B7)

**Acceptance (spec 11 §9):** *"(3) Review Queue (row: vendor, amount, suggested account, ConfidencePill, reason; one-click accept; override picker; keyboard flow)."* Spec 00 A2 tokens: *"dark navy #0B1E3B, emerald #10B981, frosted-glass surfaces, Space Grotesk / Inter."*
**Test plan:** manual walkthrough against a real backend, driven end to end; `tsc --noEmit` clean; every screen renders both empty and populated states; accept and override both round-trip and disappear from the queue.
**Verified:** `tsc --noEmit` clean · `npm run build` clean · **22/22 render tests pass**, covering every screen in both empty and populated states, the row contract of §9, the disabled accept on an invalid account, and the em-dash account name surviving to the DOM. The API was separately driven end to end over HTTP: 11 routes registered, both example months uploaded and run, the Vite proxy verified with `curl`.
**⚠️ NOT verified — the manual walkthrough did not happen.** The Chrome extension is not connected (BLOCKERS.md **B7**), so **no one has looked at these screens**. Layout, label collisions and chart overflow are unconfirmed, and the browser keyboard flow is untested against real key events. Recorded as a gap rather than quietly dropped from the plan.
**Risk:** UI polish consuming the phase. Mitigation: the queue row and the memory-bend chart are the only two surfaces that get design attention; everything else is functional-plain. *Outcome: held.*

**Acceptance (spec 11 §9):** *"(3) Review Queue (row: vendor, amount, suggested account, ConfidencePill, reason; one-click accept; override picker; keyboard flow)."* Spec 00 A2 tokens: *"dark navy #0B1E3B, emerald #10B981, frosted-glass surfaces, Space Grotesk / Inter."*
**Test plan:** manual walkthrough against a real backend, driven end to end; `tsc --noEmit` clean; every screen renders both empty and populated states; accept and override both round-trip and disappear from the queue.
**Risk:** UI polish consuming the phase. Mitigation: the queue row and the memory-bend chart are the only two surfaces that get design attention; everything else is functional-plain.

### P8 · Dashboard, memory-bend, export — W2 ✅ DONE
- [x] Confidence histogram, with the gate drawn as a reference line and each bar coloured by which side it fell on
- [x] Auto-rate %, memory-hit rate, cost-per-run tiles, with run-over-run deltas
- [x] **Memory-bend chart**: memory-hit rate ↑ and cost-per-transaction ↓ across runs (Recharts) — as **two small multiples, not a dual-axis plot** (D17)
- [x] Category breakdown
- [x] Export CSV download from the UI
- [x] Two-run demo path verified end to end over HTTP
- [x] Chart palette **computationally validated**, not eyeballed
- [x] A "Show numbers" table view on every chart, so a tooltip is never the only way to read a value

**Acceptance (spec 11 §4 F5):** *"Dashboard: confidence histogram, auto-rate %, memory-hit rate, cost-per-run, category breakdown."* Spec 11 §4 F4: *"the cost curve VISIBLY bends month over month (chart it)."* Spec 11 §4 F6: *"categorized CSV with per-line {account, confidence, source, reason}."*
**Verified — the real two-month run, over HTTP:**

| run | txns | auto-rate | memory-hit | LLM calls | cost |
|---|---|---|---|---|---|
| month 1 | 120 | 75.8% | 40.8% | 71 | $0.013206 |
| month 2 | 120 | 81.7% | **62.5%** | 45 | **$0.008370** |

**36.6% cheaper per run, LLM calls 71 → 45, memory-hit rate +21.7 points.** The backend assertion `test_the_run_series_shows_the_memory_bend` locks this in, and the frontend test asserts the bend is stated in words on screen as well as drawn.
**Risk:** the bend fails to appear because month 2 shares too few vendors with month 1. Mitigation: `month_02` is generated from the **same counterparty catalogue** by construction; the two-run assertion is a real test, not a demo hope. I will use the `dataviz` skill before writing chart code. *Outcome: skill loaded before the first line of chart code, and it changed the design — see D17. The bend appeared as predicted (P3 measured the key-overlap ceiling at 68.3%; month 2 reached 62.5%).*

**Acceptance (spec 11 §4 F5):** *"Dashboard: confidence histogram, auto-rate %, memory-hit rate, cost-per-run, category breakdown."* Spec 11 §4 F4: *"the cost curve VISIBLY bends month over month (chart it)."* Spec 11 §4 F6: *"categorized CSV with per-line {account, confidence, source, reason}."*
**Test plan:** run `month_01` then `month_02`, assert the API series shows memory-hit rate strictly increasing and cost-per-run strictly decreasing between run 1 and run 2; verify the exported CSV opens cleanly and carries all four fields.
**Risk:** the bend fails to appear because month 2 shares too few vendors with month 1. Mitigation: `month_02` is generated from the **same counterparty catalog** by construction; the two-run assertion above is a real test, not a demo hope. I will use the `dataviz` skill before writing chart code.

### P9 · Docs, honesty pass, final report — W2 ✅ DONE
- [x] README in spec 00 A1's mandatory order: screenshot slot → pitch → **mermaid** architecture → demo-video slot → **"⚠️ All data synthetic"** banner → quickstart → honest STATUS → ex-accountant line
- [x] `MODEL_COSTS.md` with the declining-cost story and the arithmetic shown
- [x] `docs/architecture.md` — the graph, the two gates, the learning loop, and what is deliberately absent
- [x] PLAN.md fully ticked; PROGRESS.md complete; BLOCKERS.md current (B1–B7)
- [x] `FINAL_REPORT.md`: demo script, exact commands **including the live-eval command**, blockers + one-line fixes, three next things
- [x] **Docker verified** — image builds, container serves health + SPA, and an upload+run inside it produced numbers identical to the native run
- [x] **All 4 mermaid blocks parsed** with the real mermaid parser, so no diagram renders as an error box

**Acceptance (spec 00 A1):** *"README skeleton sections (mandatory order): screenshot → one-line pitch → architecture diagram → demo video link → '⚠️ All data synthetic' banner → quickstart → 'Built by an ex-accountant turned AI engineer' line."* Spec 00 D: *"Every repo publishes MODEL_COSTS.md."*
**Test plan:** fresh-clone rehearsal — `make dev`, upload `examples/month_01…`, run, review queue, override, re-run `month_02`, confirm "learned", read the dashboard, export CSV. Any step that does not work verbatim gets fixed or documented in STATUS, not quietly omitted.
**Verified:** the full path was exercised **over HTTP** end to end (uploads, runs, verdict, memory, metrics, export) and again **inside the Docker container**; `test_the_definition_of_done_end_to_end` runs the same sequence as a test. 279 tests pass; ruff, format, mypy, tsc clean.
**Not verified, and stated as such in README STATUS:** the *visual* rehearsal — no browser (B7). Screenshot and demo-video slots are deliberately empty rather than faked.
**Risk:** a README that overclaims. Mitigation: STATUS states mock-vs-live eval mode, the demo-video slot is marked not-recorded rather than faked, and no screenshot is claimed that I have not produced. *Outcome: held — STATUS carries a "Real gaps" section listing all six, and the mock-mode caveat is repeated in `evals/README.md`, `MODEL_COSTS.md` and `FINAL_REPORT.md` so it cannot be read out of context.*

**Acceptance (spec 00 A1):** *"README skeleton sections (mandatory order): screenshot → one-line pitch → architecture diagram → demo video link → '⚠️ All data synthetic' banner → quickstart → 'Built by an ex-accountant turned AI engineer' line."* Spec 00 D: *"Every repo publishes MODEL_COSTS.md."*
**Test plan:** fresh-clone rehearsal — `make dev`, upload `examples/month_01…`, run, review queue, override, re-run `month_02`, confirm "learned", read the dashboard, export CSV. Any step that does not work verbatim gets fixed or documented in STATUS, not quietly omitted.
**Risk:** a README that overclaims. Mitigation: STATUS states mock-vs-live eval mode, the demo-video slot is marked not-recorded rather than faked, and no screenshot is claimed that I have not produced.

---

## 4. EXTERNAL DEPENDENCIES & FALLBACKS

| # | Dependency | Status here | Fallback if unavailable |
|---|---|---|---|
| 1 | `backend_seed_ledgerfab/` | **ABSENT** (repo has only the two specs) | **Active fallback:** implement `backend/ledgerfab/` from spec 00 A3, scoped to SpendSort's needs. BLOCKERS.md **B1** |
| 2 | `make` | **NOT INSTALLED** | **Active fallback:** ship both `Makefile` (CI/docker/Linux) and `make.ps1` (this box). One-line fix: `winget install ezwinports.make`. BLOCKERS.md **B2** |
| 3 | `OPENAI_API_KEY` | **NOT SET** | **Active fallback:** LLM mocked in default tests per adaptation 3; live path behind pytest marker `live`. Live-eval command handed over in FINAL_REPORT.md. BLOCKERS.md **B3** |
| 4 | OpenAI API / `langchain-openai` | Package installable; no key to call it | Mock mode is a first-class code path (`SPENDSORT_MOCK_LLM=1`), not a test-only hack, so the full demo runs with zero spend |
| 5 | `aurora-ui` workspace package | Does not exist as a package | Per adaptation 2, implement the four components locally in `frontend/src/components/aurora/` against spec 00 A2 tokens |
| 6 | LedgerLab MCP pull (spec 11 §4 F1, "optional") | Project 02 not built; out of dependency order (spec 00 B) | Explicitly out of scope — CSV intake only. Recorded in DECISIONS LOG D4 |
| 7 | Model pricing figures | Cannot verify pricing offline | Pricing lives in one table in `app/costs.py`, env-overridable, dated in MODEL_COSTS.md and labelled as needing confirmation. DECISIONS LOG D6 |
| 8 | `docker` / compose | Installed (daemon state unverified) | `make dev` runs backend+frontend natively; docker-compose is the packaging deliverable, not the demo path |
| 9 | Node 24 / npm 11 | Present | — |
| 10 | Python 3.12.10 + uv 0.11 | Present | — |
| 11 | TCP port 8000 | **OCCUPIED** by Docker/WSL on this box | **Resolved:** port is an override end to end (`PORT` / `-Port` / `VITE_API_PORT`). Verified on 8123. BLOCKERS.md **B6** |

---

## 5. DECISIONS LOG

| # | Decision | Rationale |
|---|---|---|
| D1 | Specs **moved** from repo root to `docs/` | The brief names `docs/spec_00…` / `docs/spec_11…` as ground truth; aligning the tree to the stated paths. Content unchanged. |
| D2 | ledgerfab lands at `backend/ledgerfab/` as a package inside the backend project | Matches adaptation 1's stated destination; importable by both `app/` and `evals/` without a second install step. |
| D3 | ledgerfab implements **only** CoA, counterparties+aliases, bank transactions, ground truth | Spec 00 A3 lists invoices/POs/GL/accruals, but SpendSort reads none of them. Building unread generators would be waste; the omission is documented rather than silent. |
| D4 | No LedgerLab MCP client | Spec 11 §4 F1 marks it optional; spec 00 B forbids starting on an unbuilt upstream (Project 02). CSV intake covers every user story. |
| D5 | `route` is a real 4th graph node, not just a conditional edge | Spec 11 §4 F2 names four nodes and the brief says *"≤4 nodes exactly"*; the memory bypass is expressed as a conditional **edge** from `check_memory`, keeping the node count at exactly 4. |
| D6 | Cost/pricing table centralised and env-overridable in `app/costs.py` | Pricing changes; the cost cap and MODEL_COSTS.md must not require code edits to stay honest. Figures dated and flagged for confirmation. |
| D7 | Cost-cap exhaustion **queues** the remainder | Silently leaving transactions uncategorized would be a dishonest success. Queuing is the spec's own answer for anything not confidently auto-applied. |
| D8 | Mock LLM replays a deliberately **imperfect** fixture (incl. a wrong and an out-of-CoA answer) | A perfect mock would make the ≥95% auto-precision gate and queue-recall meaningless. The gate must be able to fail. |
| D9 | `git init` performed at P0 close (not P1) | Repo was not version-controlled, and the work loop requires a commit per phase — including Phase 0 itself. |
| D10 | Default threshold **0.85**, cost cap **$0.25**/run, model mini-class, temp **0.1** | Cap and temperature are spec-mandated (§11, §8). Threshold is a starting value chosen to make the ≥95% auto-precision gate achievable; it is env-tunable and will be re-derived from eval results in P5 — any change gets logged here. |
| D11 | **One `pyproject.toml` at the repo root**, not `backend/pyproject.toml` as first mapped | Spec 00 A1 puts `evals/` at the top level, and the eval harness must import both `app` and `ledgerfab`. A single root project gives one venv and one `uv run pytest` that covers `backend/tests` *and* `evals`, instead of a second install step or path hacks. Declared `package = false` (this is a monorepo, not a distributable); imports resolve via pytest `pythonpath` and uvicorn `--app-dir backend`. |
| D12 | **Tailwind v4** (`@tailwindcss/vite`), so no `tailwind.config.js` / `postcss.config.js` | v4 is the current line and is CSS-first: the aurora tokens of spec 00 A2 live in a real `@theme` block in `components/aurora/tokens.css`, which is a better home for a design system than a JS config object. The two config files in the original file map are therefore not needed and were dropped. |
| D13 | API port is an override (`PORT` / `-Port` / `VITE_API_PORT`), not a hardcoded 8000 | Port 8000 is occupied by Docker/WSL on the dev box (BLOCKERS.md B6). A demo that only works when one specific port is free is a demo that breaks on someone else's laptop. |
| D17 | **The memory bend is two small-multiple charts, not one dual-axis plot** | Memory-hit rate (%) and cost per run ($) are different scales, and putting them on one plot with two y-axes would place the "lines crossing" moment wherever the axis alignment happened to fall — a drawing artefact presented as a finding. The `dataviz` skill names this the single most common charting mistake. Two panels on a shared x-axis (run number) make the same point without inventing one. |
| D18 | **Chart colours validated by script, not by eye** | Ran the palette validator against the dark navy chart surface. The UI's bright `#10B981` / `#F59E0B` **fail** the dark-mode lightness band (L 0.696 / 0.769 against a 0.48–0.67 band), so the charts use the dimmer steps of the same hues — `#0E9A6C` / `#D97706` — which pass all six checks (CVD ΔE 8.3, normal-vision 23.4, contrast ≥3:1). Recorded in `charts/tokens.ts` with the command, so the next person re-runs it instead of guessing. |
| D19 | **Frontend render tests instead of a manual walkthrough** | No browser is available (B7), so "look at it" is impossible. 22 vitest+jsdom tests assert every screen mounts and shows the product's claims. They cannot judge layout, and that gap is stated in README STATUS rather than glossed. |
| D15 | **Every file read/write passes `encoding="utf-8"` explicitly; CSV export uses `utf-8-sig`** | Measured, not assumed: three CoA account names contain an em-dash (`Travel — Airfare`), and this box's locale default is `cp1252`, which silently renders them `Travel â€” Airfare`. Any reader that omits the encoding corrupts the chart of accounts. The BOM on export is what makes Excel open an exported ledger correctly — which matters, since a bookkeeper is the user. Asserted by test rather than left to convention. |
| D16 | Keep the em-dash in account names rather than downgrading to a hyphen | Sidestepping the character would hide the encoding bug instead of fixing it, and the CSV hardening that spec 11 §11 asks for has to survive real-world text anyway. |
| D14 | Accept the **1.x** LangGraph / langchain-openai line that uv resolved | `langgraph 1.2.11`, `langchain-core 1.6.1`, `langchain-openai 1.6.0` — newer than the `>=0.2` floors written for the spec era. The APIs used (`StateGraph`, `add_conditional_edges`, `with_structured_output`) are stable across the bump, and `uv.lock` is committed so the resolution is reproducible. |

---

## 6. NON-NEGOTIABLE CONSTRAINT TRACEABILITY

Each brief constraint mapped to the phase and test that proves it.

| Constraint | Phase | Proof |
|---|---|---|
| Graph ≤4 nodes exactly, per spec 11 §8 order | P4 | `test_graph_shape.py` |
| Memory hits bypass the LLM | P4 | `test_graph_memory_bypass.py` (FakeLLM fails on invocation) |
| Structured output `{account_code, confidence, reason ≤20 words}` | P4 | `test_graph_nodes` / schema validation |
| `account_code` validated against CoA in code; out-of-CoA ⇒ forced low confidence + queue | P3, P4 | `test_coa_validation.py` |
| Overrides write `vendor_memory`; next occurrence auto + "learned" | P4 | `test_memory_learning.py` |
| Dashboard charts the memory-bend (hit rate + cost trend across runs) | P6, P8 | two-run API series assertion + Metrics screen |
| 100 ledgerfab txns with ground truth | P5 | `cases.jsonl` row-count + CoA-alignment test |
| Auto-precision ≥95% is the CI gate | P5 | `test_eval_gate.py` in `ci.yml` |
| Wrong answers land in the queue (queue-recall) | P5 | `harness.py` queue-recall metric |
| Cost cap per run (default $0.25) enforced | P4 | `test_cost_cap.py` |
| LLM mocked by default; live behind `live` marker | P1, P5 | `pyproject.toml` markers + `run_live.py` |
