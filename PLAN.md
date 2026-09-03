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
├── Makefile                             NEW  dev · test · eval · eval-live · seed · up · down · lint
├── make.ps1                             NEW  PowerShell shim — `make` absent on this box (BLOCKERS.md B2)
├── docker-compose.yml                   NEW  spec 11 §12
├── .env.example                         NEW  OPENAI_API_KEY, SPENDSORT_MODEL, thresholds, cost cap
├── .gitignore                           NEW
├── .github/workflows/ci.yml             NEW  ruff → mypy → pytest → eval gate (spec 00 A1)
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
│   ├── pyproject.toml                   NEW  uv-managed; pytest markers incl. `live`
│   ├── uv.lock                          NEW  generated
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
    ├── package.json · vite.config.ts · tsconfig.json          NEW
    ├── tailwind.config.js · postcss.config.js · index.html    NEW
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

### P1 · Scaffold & foundations — W1
- [ ] `git init` (repo is not currently under version control) + `.gitignore`
- [ ] `MOVE` both specs to `docs/`
- [ ] `backend/pyproject.toml` via uv: FastAPI, Pydantic v2, SQLAlchemy, langgraph, langchain-openai, pyyaml, pytest; register `live` marker
- [ ] `frontend/` Vite + React + TS + Tailwind bootstrap
- [ ] `Makefile` + `make.ps1` shim: `dev test eval eval-live seed lint up down`
- [ ] `.env.example`, `docker-compose.yml`, MIT `LICENSE`
- [ ] `.github/workflows/ci.yml`: ruff → mypy → pytest → eval gate
- [ ] `app/settings.py`, `app/logging.py`, health endpoint

**Acceptance (spec 00 A1):** *"`make up` runs a hello dashboard; `make eval` runs an empty pass; CI green on a fresh clone."* Stack exactly per spec 00 F: *"Python everywhere · FastAPI backends · Vite+React+TS frontends · LangChain + LangGraph for agent orchestration · no LangChain-classic chains (LCEL/LangGraph only)."*
**Test plan:** `test_api_smoke.py::test_health` green; `make test` and `make eval` both exit 0 on an empty suite; frontend dev server boots and renders a placeholder.
**Risk:** dependency resolution churn on Windows/Python 3.12. Mitigation: pin via `uv.lock`, committed.

### P2 · ledgerfab — W1
- [ ] Port/reimplement per spec 00 A3: `World`, chart of accounts, counterparties **with aliases**, bank transactions
- [ ] Knobs: `alias_rate`, `date_format_chaos`, `amount_noise`, `duplicate_rate`, `missing_reference_rate`; presets `clean` / `realistic` / `nightmare`
- [ ] Ground-truth emitter — correct category per transaction
- [ ] `World → CSV` export; generate the three `examples/` files with recorded seeds
- [ ] Determinism test

**Acceptance (spec 00 A3):** *"`ledgerfab.generate(profile, seed)` returns a typed World; `world.ground_truth` gives correct matches; determinism test passes"* and *"Seeded → reproducible (same seed+profile = identical dataset, hash-verifiable)."*
**Test plan:** `test_ledgerfab_determinism.py` — same seed+profile twice ⇒ identical content hash; different seed ⇒ different hash; every emitted transaction's ground-truth account is a member of the CoA.
**Risk:** scope creep into invoices/POs/GL that SpendSort never reads. Mitigation: build only the transaction + counterparty-alias + ground-truth surface SpendSort needs; leave the rest documented as out of scope in DECISIONS LOG D3.

### P3 · Data model, CoA, intake — W1
- [ ] ORM tables exactly per spec 11 §6: `transactions`, `categorizations`, `verdicts`, `vendor_memory`, `runs`
- [ ] `coa_default.yaml` + loader + **in-code** membership validation
- [ ] Aggressive vendor normalization (case, punctuation, store numbers, city/state tails, payment-processor prefixes)
- [ ] `POST /api/ingest/csv` with CSV hardening; `GET/PUT /api/coa`

**Acceptance (spec 11 §4 F1):** *"CSV upload (date, amount, vendor/description, currency) … chart of accounts as editable YAML (ship a sensible default CoA)."* Plus spec 11 §11: *"CSV hardening."*
**Test plan:** `test_normalize.py` over ledgerfab alias chaos (asserting aliases of one counterparty collapse to one `vendor_norm`); `test_coa_validation.py`; `test_ingest_csv.py` covering formula-injection cells, BOM, mixed date formats, negative/blank amounts, oversized upload.
**Risk (spec 11 §14):** *"Vendor normalization quality (messy descriptors) → normalize aggressively, test on ledgerfab alias chaos."* Mitigation: the normalizer is tested directly against generated alias sets, not hand-written strings.

### P4 · Categorization graph, memory, routing, cost cap — W1
- [ ] Graph with **exactly 4 nodes**: `normalize_vendor → check_memory → llm_categorize → route`
- [ ] Conditional edge: memory hit routes `check_memory → route`, **skipping the LLM**
- [ ] `llm_categorize`: Pydantic structured output `{account_code, confidence, reason}`, temperature 0.1, reason ≤20 words enforced
- [ ] Out-of-CoA `account_code` ⇒ forced low confidence + queue
- [ ] `route`: auto if `confidence ≥ threshold`, else queue; persist `categorizations.source` as `memory | llm`
- [ ] `vendor_memory` write on override with `source=human`; `hit_count` increments; re-run marks "learned"
- [ ] Per-run cost cap (default **$0.25**): on exhaustion, remaining transactions are **queued, never silently dropped**
- [ ] `POST /api/runs` orchestration + `runs` row rollup

**Acceptance (spec 11 §4 F2):** *"Categorization graph (LangGraph, ≤4 nodes): `normalize_vendor → check_memory (learned mappings first, zero LLM cost) → llm_categorize (structured output: {account_code, confidence, reason}) → route (auto ≥ threshold | queue)`."* Spec 11 §8: *"account_code must be in the CoA (validated in code; out-of-CoA = forced low confidence + queue). Reason ≤ 20 words. Temperature 0.1."* Spec 11 §4 F4: *"memory hits bypass the LLM entirely."* Spec 11 §11: *"cost cap per run (default $0.25)."*
**Test plan:** `test_graph_shape.py` asserts the compiled graph has exactly 4 nodes; `test_graph_memory_bypass.py` injects a FakeLLM that **fails the test if invoked** on a memory hit; `test_routing_threshold.py` boundary cases at, just below, and just above threshold; `test_coa_validation.py` hallucinated account code ⇒ queued; `test_memory_learning.py` override → re-run ⇒ auto + `source` learned-from-human; `test_cost_cap.py` cap reached mid-run ⇒ remainder queued and run row records the truncation.
**Risk (spec 11 §14):** *"CoA ambiguity (two plausible accounts) → confidence must drop, tested with deliberately ambiguous eval cases."* Mitigation: `examples/ambiguous_edge_cases.csv` and a matching eval slice assert confidence lands **below** threshold rather than asserting a specific account.

### P5 · Evals & CI gate — W1
- [ ] `build_cases.py` → `cases.jsonl`, **100** ledgerfab transactions with ground truth
- [ ] `harness.py`: accuracy, **auto-precision** (auto-applied lines only), **queue-recall**
- [ ] `test_eval_gate.py` fails CI below 95% auto-precision
- [ ] Deterministic mock-mode scorer (CI) + `run_live.py` behind the `live` marker
- [ ] Wire the gate into `ci.yml`

**Acceptance (spec 11 §10):** *"evals/: 100 ledgerfab transactions with ground-truth categories (CoA-aligned); metrics: accuracy, auto-precision (accuracy of auto-applied only: must be ≥ 95%), queue-recall (wrong ones must land in queue, not auto). Memory tests: override → next occurrence auto + correct. CI gate on auto-precision."*
**Test plan:** the eval suite is itself the test; additionally assert `cases.jsonl` has exactly 100 rows, every ground-truth account is CoA-aligned, and queue-recall is reported (not just accuracy) so a "confidently wrong" regression cannot pass.
**Risk:** a mock LLM that flatters the gate — 100% precision in CI proves nothing about the real model. Mitigation: the mock replays a **fixed, deliberately imperfect** response fixture including wrong and out-of-CoA answers, so queue-recall is genuinely exercised; README STATUS states plainly that the CI number is mock-mode, and the live command is handed to the reviewer in FINAL_REPORT.md.

### P6 · Remaining API surface — W1→W2
- [ ] `GET /api/queue` — lowest-confidence-first
- [ ] `POST /api/txns/{id}/verdict` — accept | override, writes `verdicts` + `vendor_memory`
- [ ] `GET /api/memory` · `GET /api/metrics` · `GET /api/export`
- [ ] Metrics payload carries **per-run series** for the memory-bend chart

**Acceptance (spec 11 §7):** *"POST /api/ingest/csv · POST /api/runs (categorize all pending) · GET /api/queue · POST /api/txns/{id}/verdict · GET /api/memory · GET /api/metrics · GET /api/export."*
**Test plan:** `test_api_smoke.py` exercises all eight endpoints; queue ordering asserted; `test_export.py` asserts the four required per-line fields.
**Risk:** metrics shaped for one screen, then reshaped for charts. Mitigation: design the metrics response from the P8 chart requirements first, then build the endpoint to it.

### P7 · Aurora components + frontend screens — W2
- [ ] `components/aurora/`: `Card` (frosted), `ConfidencePill` (0-1 → colour + label), `MetricTile`, `SyntheticDataBanner` — spec 00 A2 tokens
- [ ] Screens 1–4: Import + CoA editor · Run view · Review Queue · Memory
- [ ] Queue: one-click accept, override account picker, **keyboard flow**
- [ ] Typed API client; TanStack Query for fetch/invalidate

**Acceptance (spec 11 §9):** *"(3) Review Queue (row: vendor, amount, suggested account, ConfidencePill, reason; one-click accept; override picker; keyboard flow)."* Spec 00 A2 tokens: *"dark navy #0B1E3B, emerald #10B981, frosted-glass surfaces, Space Grotesk / Inter."*
**Test plan:** manual walkthrough against a real backend, driven end to end; `tsc --noEmit` clean; every screen renders both empty and populated states; accept and override both round-trip and disappear from the queue.
**Risk:** UI polish consuming the phase. Mitigation: the queue row and the memory-bend chart are the only two surfaces that get design attention; everything else is functional-plain.

### P8 · Dashboard, memory-bend, export — W2
- [ ] Confidence histogram
- [ ] Auto-rate %, memory-hit rate, cost-per-run tiles
- [ ] **Memory-bend chart**: memory-hit rate ↑ and cost-per-run ↓ across runs (Recharts)
- [ ] Category breakdown
- [ ] Export CSV download from the UI
- [ ] Two-run demo seed path so the bend is visible on a fresh clone

**Acceptance (spec 11 §4 F5):** *"Dashboard: confidence histogram, auto-rate %, memory-hit rate, cost-per-run, category breakdown."* Spec 11 §4 F4: *"the cost curve VISIBLY bends month over month (chart it)."* Spec 11 §4 F6: *"categorized CSV with per-line {account, confidence, source, reason}."*
**Test plan:** run `month_01` then `month_02`, assert the API series shows memory-hit rate strictly increasing and cost-per-run strictly decreasing between run 1 and run 2; verify the exported CSV opens cleanly and carries all four fields.
**Risk:** the bend fails to appear because month 2 shares too few vendors with month 1. Mitigation: `month_02` is generated from the **same counterparty catalog** by construction; the two-run assertion above is a real test, not a demo hope. I will use the `dataviz` skill before writing chart code.

### P9 · Docs, honesty pass, final report — W2
- [ ] README: screenshot slot → pitch → **mermaid** architecture → **"⚠️ All data synthetic"** banner → quickstart → honest STATUS → ex-accountant line
- [ ] `MODEL_COSTS.md` with the declining-cost story
- [ ] `docs/architecture.md`
- [ ] PLAN.md fully ticked or BLOCKED-marked; PROGRESS.md complete; BLOCKERS.md current
- [ ] `FINAL_REPORT.md`: demo script, exact commands **including the live-eval command**, blockers + one-line fixes, three next things

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
