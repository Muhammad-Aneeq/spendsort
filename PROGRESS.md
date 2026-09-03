# PROGRESS.md · SpendSort

Append-only log. One entry per phase, written as the phase closes. Paired with PLAN.md (checkboxes) and
BLOCKERS.md (obstacles).

---

## P0 · Planning — DONE (2026-09-03)

**Done**
- Read both ground-truth specs end to end: `spec_00_shared_foundations.md`, `spec_11_spendsort.md`.
- Surveyed the working tree and toolchain; recorded every gap before writing a line of plan.
- Authored `PLAN.md`: five-line spec summary, complete file map, nine phases (P1–P9) mapped onto spec 11 §13's
  W1/W2 split with spec-quoted acceptance criteria, per-phase test plans and risk notes, external-dependency
  table with fallbacks, decisions log, and a constraint-traceability table linking each non-negotiable
  constraint to the phase and test that proves it.
- Authored `BLOCKERS.md` with five entries (B1–B5).
- Initialised version control (the repo was not previously a git repository) and committed Phase 0.

**Environment as found**
| Tool | Result |
|---|---|
| Python | 3.12.10 ✓ |
| uv | 0.11.23 ✓ |
| node / npm | 24.14.1 / 11.11.0 ✓ |
| git | 2.53.0 ✓ (repo was **not** initialised) |
| docker | present ✓ (daemon state unverified) |
| **make** | **MISSING** → B2 |
| **OPENAI_API_KEY** | **NOT SET** → B3 |

**Findings that changed the plan**
1. `backend_seed_ledgerfab/` **does not exist** — the repo held only the two spec files. Adaptation 1's fallback
   is now the active path: implement ledgerfab from spec 00 A3 (B1, PLAN D3).
2. The specs sat at the **repo root**, not `docs/` as the brief's ground-truth paths state. Moving them to
   `docs/` in P1 (PLAN D1).
3. `make` absent → shipping a `Makefile` *and* a `make.ps1` shim so the Definition of Done's `make dev` is
   demoable here without an install (B2).
4. No API key → mock mode is designed as a **first-class code path**, not a test shim, so the whole demo runs at
   zero spend; live behind the `live` marker (B3).

**Tests:** none — documentation phase. Self-check performed instead: every non-negotiable constraint from the
brief appears in PLAN.md §6 with a named phase and a named test.

**Deliberate scope calls** (full rationale in PLAN.md DECISIONS LOG): ledgerfab built only to the surface
SpendSort reads (D3); no LedgerLab MCP client, since spec 00 B forbids starting on an unbuilt upstream (D4);
`route` kept as a real 4th node with the memory bypass as a conditional *edge*, holding the count at exactly
four (D5); cost-cap exhaustion **queues** the remainder rather than silently skipping it (D7); the mock LLM
replays a deliberately imperfect fixture so the ≥95% gate can actually fail (D8).

**Next:** P1 · Scaffold & foundations.

---

## P1 · Scaffold & foundations — DONE (2026-09-03)

Re-read spec 00 A1 (repo skeleton, acceptance) and spec 00 F (stack lock) before writing anything.

**Done**
- Version control initialised; both specs moved into `docs/` (PLAN D1); `.gitignore` covering venvs, SQLite
  files, `node_modules`, build output and — deliberately — `.env`.
- **One** uv project at the repo root rather than under `backend/` (PLAN **D11**), because `evals/` sits at the
  top level per spec 00 A1 and must import both `app` and `ledgerfab`. One venv, one `pytest` invocation
  covering `backend/tests` and `evals`. Markers `live` and `eval` registered, `live` deselected by default.
- Backend foundation: `settings.py` (pydantic-settings; threshold, cost cap, model, temperature, mock flag all
  env-driven), `logging.py` (one JSON line per event), `db.py` (SQLAlchemy 2.0, SQLite with
  `foreign_keys=ON` + WAL), `GET /api/health`.
- Frontend: Vite 6 + React 19 + TS strict + **Tailwind v4** (PLAN **D12**). The aurora tokens of spec 00 A2 —
  navy `#0B1E3B`, emerald `#10B981`, frosted glass, Space Grotesk / Inter — live in a real `@theme` block in
  `components/aurora/tokens.css`, so v4 needs no `tailwind.config.js` or `postcss.config.js`.
- `Makefile` **and** `make.ps1` (B2), sixteen matching targets. `Dockerfile` (2-stage: build the SPA, then a
  Python runtime that serves it) plus `docker-compose.yml` — compose referenced a Dockerfile, so the Dockerfile
  had to exist rather than be implied.
- `ci.yml`: lint/typecheck/tests, a **separate eval-gate job**, and a frontend typecheck+build job.
- `.env.example` documenting every knob with the spec clause it comes from; MIT `LICENSE`.

**Verified (not assumed)**
| Check | Result |
|---|---|
| `pytest -m "not live"` | 2 passed, 1 skipped |
| `pytest evals` | honest empty pass — skip, `cases.jsonl` arrives in P5 |
| `ruff check` + `ruff format --check` | clean |
| `mypy backend/app` | clean, 5 files |
| `npm run build` (`tsc --noEmit` + vite) | clean |
| aurora token utilities in compiled CSS | all 7 probed classes generated |
| uvicorn boot → `GET /api/health` | 200, reports threshold 0.85 / cap $0.25 / `llm_mode: mock` |
| built SPA served from `/` | 200, correct `<title>`, `#root` present |
| `./make.ps1 help` / `test` / `eval` | all work |

**Blocker found and fixed during the phase — B6.** `uvicorn --port 8000` never came up, and `--port 8011`
failed with `WinError 10013`. Port 8000 is held by `com.docker.backend` + `wslrelay.exe`; `netsh` also showed
reserved ranges explaining 8011. Rather than pick a different magic number, the port is now an override
everywhere (`PORT` in the Makefile, `-Port` in the shim, `VITE_API_PORT` for the Vite proxy so the SPA follows
the API), with a pre-flight check that prints the exact command to type instead of hanging. Verified on 8123.

**Honest gaps at P1 close**
- `mypy backend/ledgerfab` is wired into the Makefile and CI but that package does not exist until P2, so the
  full typecheck target has **not** been run yet — only `backend/app`.
- CI has never executed on a real runner: there is no git remote. The workflow is written but unproven.
- `frontend/dist` is gitignored, so the SPA mount is a no-op on a fresh clone until something builds it — this
  is why `make dev` uses Vite rather than the static mount.
- Recharts was bumped 2.x → 3.x after npm flagged the 2.x branch as no longer maintained.

**Next:** P2 · ledgerfab (spec 00 A3) — the fallback path from B1.

---

## P2 · ledgerfab — DONE (2026-09-03)

Re-read spec 00 A3 before starting. This is the **B1 fallback**: the seed directory the brief pointed at does
not exist, so the library is built from the spec, scoped to what SpendSort actually reads (PLAN D3).

**Done**
- `models.py` — typed `World`, `Company`, `Account`, `Counterparty`, `BankTxn`, `GroundTruth(Entry)` in
  Pydantic v2, frozen and `extra="forbid"`. `World.content_hash()` hashes canonical JSON, which is what makes
  spec 00 A3's "hash-verifiable" claim testable rather than rhetorical.
- `config.py` — all seven spec 00 A3 knobs plus the `clean` / `realistic` / `nightmare` presets. The period is
  a declared `period_start` + `period_days`, never `today()`.
- `coa.py` — a 20-account small-business expense CoA. **No "Uncategorized" account on purpose**: a catch-all is
  somewhere for the agent to hide a guess, and the whole design says an unconfident answer goes to a human.
- `vendors.py` — 51 counterparties with genuinely nasty descriptor aliases (`AMZN Mktp US*{ref}`,
  `POS DEBIT …`, `SQ *`, `TST*`, store numbers, city/state tails, inconsistent case and spacing). Seven vendors
  carry `ambiguous_with` — Amazon (supplies vs computer equipment), Uber (transport vs meals), Airbnb (lodging
  vs rent), and so on — so spec 11 §14's "confidence must drop" is testable on real ambiguity.
- `generate.py` — seeded generation. One `random.Random` seeded from `(profile, seed)`, no global `random`,
  explicit tuple iteration only, exact row counts even when splits and duplicates are injected.
- `ground_truth.py` — labels known **by construction** (vendor picked first, messy descriptor rendered after),
  and it refuses to emit a label outside the CoA.
- `export.py` — upload CSV (`date, amount, currency, vendor, memo`), a separate labels CSV, the three
  `examples/` files with published content hashes, and `backend/app/coa_default.yaml`.

**Ground truth never ships inside the upload CSVs.** The agent has to earn its answers from the descriptor;
labels live in `evals/`.

**Verified**
| Check | Result |
|---|---|
| `pytest` | **24 passed**, 1 skipped |
| determinism, all 3 presets | identical hash on repeat; different seed ⇒ different hash; profile part of the seed |
| clock independence | every date inside the declared period |
| `clean` really clean | no aliases, one date format, no dupes/splits/FX, every row has a reference |
| knobs bite | alias share: clean 0% → realistic >50% → nightmare higher |
| ground truth | every row labelled, every label in the CoA, label matches the generating vendor |
| ruff / ruff format / mypy | clean (13 source files) |
| `coa_default.yaml` | parses, 20 accounts |

**Two real bugs the tests caught** — fixed in the generator, not by relaxing the test:
1. Descriptor case/spacing mangling ran regardless of `alias_rate`, so the `clean` preset still emitted 27.5%
   mangled descriptors. `clean` that isn't clean makes every alias comparison meaningless. Now gated on
   `alias_rate`, with the RNG draw taken either way so the stream stays aligned across branches.
2. Partial payments split into exact halves, which is indistinguishable from a duplicated feed row — the
   confusion a bookkeeper most cares about. Splits are now uneven (30–70%), asserted at >80% of cases.

**Encoding finding (PLAN D15/D16).** Three CoA names contain an em-dash (`Travel — Airfare`) and this box's
locale default is `cp1252`, which silently turns them into `Travel â€” Airfare`. Measured directly rather than
assumed. Consequence for later phases: every read/write passes `encoding="utf-8"` explicitly, and CSV export
will use `utf-8-sig` so an exported ledger opens correctly in Excel — which matters when the user is a
bookkeeper. Kept the em-dash rather than dodging it to a hyphen, so the fix is proven instead of avoided.

**Measured for P8.** 93.3% of `month_02` rows use a vendor already present in `month_01` (35 of 45 vendors
shared). That share is the ceiling on month 2's memory-hit rate, so the cost bend is designed in, not hoped
for. Hashes: `month_01 d50e0ab7…`, `month_02 5d9d4add…`, `ambiguous 6dfe9ae3…`.

**Honest gaps at P2 close**
- Ruff's line limit was raised 100 → 120 for the data tables, and the vendor catalog was rewritten from
  positional 7-tuples to keyword-labelled `_cp(...)` records after the formatter exploded them into a wall.
  Semantics unchanged (hashes identical); it reads as records now.
- `make seed` skips the eval-case builder with a printed notice until P5 creates it.
- Spec 00 A3's invoices, POs, GL entries and accrual schedules are **not** implemented (D3) — SpendSort reads
  none of them. Documented, not silent.

**Next:** P3 · data model, CoA loader, vendor normalization, CSV intake.

---

## P3 · Data model, CoA, normalization, intake — DONE (2026-09-03)

Re-read spec 11 §6, §4 F1, §11 and §14 first.

**Done**
- **ORM** exactly to spec 11 §6, plus two load-bearing additions: `categorizations.run_id`
  (the dashboard must chart auto-rate, memory-hit rate and cost *across* runs, which is
  impossible if a decision does not know its run) and run-level cost/cap audit fields, so the
  $0.25 cap can be *shown* to have been enforced. Status enums are `StrEnum` with matching DB
  `CHECK` constraints, so an invalid status cannot be written even by a direct SQL mistake.
- **CoA loader** (`app/coa.py`) with the spec 11 §8 gate in code. `str()` coercion on codes
  matters more than it looks: YAML reads a bare `6000` as an int, and an int in the lookup
  table would mean no string answer from a model ever matches — every row would queue forever.
- **Normalization** (`app/normalize.py`) — the headline risk of spec 11 §14.
- **CSV intake** (`app/services/ingest.py`) with the governing rule that **one bad row must
  not lose the other 119**: rows are parsed independently and the caller gets a per-row account
  of what was rejected and why.
- Routers: `POST /api/ingest/csv`, `GET/PUT /api/coa`, `GET /api/coa/yaml`. Tests redirect the
  database to a temp file *before* app import, so the suite can never write the dev DB.

**Normalization: measured, then fixed, then measured again.** I probed the normalizer against a
2 000-row nightmare-profile sample rather than trusting hand-written strings, and the probe
found four real defects:

| # | Defect | Fix |
|---|---|---|
| 1 | 29 distinct keys for Cloudflare alone — references were **glued onto vendor names** (`CLOUDFLARE0FDLSX`) | Fixed in **ledgerfab**: real bank feeds put a separator before a reference. This was a realism bug in the generator, not a normalizer weakness |
| 2 | `GOOGLE *ADS` and `GOOGLE *CLOUD` both collapsed to `GOOGLE` — a **collision across two different accounts** (6000 vs 6190) | Stop treating everything after `*` as a reference. In real descriptors `*` introduces the meaningful part as often as the noise |
| 3 | Non-idempotent: `E-ZPASS NY 7Z5544` → `EZPASS NY` → `EZPASS` | The location-tail strip ran before reference removal. Reordered; memory keys must settle in one pass or yesterday's learning stops matching |
| 4 | `SAN FRANCISCO CA` left a stray `SAN`; `CON ED OF NY` eroded to `CON` | Strip location tails as city+state **pairs**, require the city slot to look like a city (≥4 letters) |

Result: **mean 2.38 keys per vendor (was 14.90), worst 4 (was 46), zero collisions, fully
idempotent.** Month-over-month key overlap — the real ceiling on the memory-hit rate — rose
from 53.3% to **68.3%**. Note this is the honest number: P2's 93.3% was *counterparty* overlap,
while memory keys on `vendor_norm`, so 68.3% is what the dashboard can actually reach.

**A line I deliberately did not cross.** The normalizer expands bank shorthand to a brand
(`AMZN`→`AMAZON`, `MSFT`→`MICROSOFT`) — ordinary descriptor cleanup. It contains **no**
vendor→account mapping, so it cannot leak the answer the LLM or the human exists to give. A
lookup table that also knew accounts would make the whole agent a sham.

**A plan correction.** PLAN.md originally promised a test that "aliases of one counterparty
collapse to one `vendor_norm`". They don't, and asserting it would have been false: `HISCOX INS`
and `HISCOX PREMIUM` are different descriptor families. The tests assert the properties that
actually matter instead — purity, idempotence, collapse — and the module docstring states the
limitation rather than hiding it. Memory simply learns both keys.

**Verified**
| Check | Result |
|---|---|
| `pytest` | **154 passed**, 1 skipped |
| normalization purity / idempotence | zero collisions, zero drift over 2 000 chaotic rows |
| all three shipped example CSVs | import with **zero** rejected rows |
| CoA ↔ ledgerfab alignment | asserted, so drift fails CI |
| em-dash account names | survive the round trip (the cp1252 trap from D15) |
| date-format chaos | 10 formats parsed, incl. the slash-vs-hyphen convention |
| amount formats | thousands separators, `$`, accounting negatives `(123.45)`, European `1.234,56` |
| hardening | oversize, empty, BOM, NUL bytes, cp1252, 5 000-char descriptor, missing columns, semicolon delimiter |
| ruff / ruff format / mypy | clean (22 source files) |

**Two more bugs the tests caught:** `parse_currency` truncated to three characters *before*
validating, so `"dollars"` became a confident-looking `"DOL"`; and `&` was treated as a
mergeable initial, turning `HARBOR & VANCE` into `HARBOR &VANCE`.

**Deliberate choice on CSV formula injection.** The raw descriptor is stored **verbatim** — it
is the audit record. Neutralising `=cmd|...` happens on **export** (P6), which is where a
spreadsheet would actually evaluate it. Asserted in both directions so the intent is explicit.

**Next:** P4 · the categorization graph — exactly 4 nodes, memory bypass, cost cap.

---

## P4 · Categorization graph, memory, routing, cost cap — DONE (2026-09-03)

Re-read spec 11 §4 F2, §8 and §11 first. This is the phase the project exists for.

**Done**
- `agent/graph.py` — **exactly four nodes**, with the memory bypass as a conditional *edge*
  from `check_memory` (PLAN D5). Four is a hard constraint, so it gets a structural test.
- `agent/nodes.py` — the four nodes. `llm_categorize` holds two gates: the **cost check runs
  before the call** (afterwards the money is already spent) and the **CoA membership check
  runs in code** on the answer.
- `agent/llm.py` — `OpenAICategorizer` (`with_structured_output`, `include_raw=True` so real
  token counts are read rather than estimated) and `MockCategorizer`. Reason length is enforced
  by truncation, not rejection: a rambling model has still given a usable answer.
- `costs.py` — one env-overridable pricing table, plus `CostBudget`. An unknown model falls
  back to the priciest mini-class entry rather than zero, so a typo cannot silently make the
  cap unenforceable.
- `services/memory.py` — human mappings are never overwritten by the model. Once a person has
  answered, no amount of model confidence outranks them.
- `services/runner.py` — drives the graph, holds the budget, promotes trusted answers, rolls up
  the run.
- `routers/runs.py`, `routers/verdicts.py`. The verdict endpoint was pulled forward from P6
  because the learning loop cannot be *proven* without it.

**How the bypass is proven.** Asserting `source == "memory"` would only show what we *recorded*
— it would still pass if the LLM had been called and its answer thrown away, and we would have
paid for it. So the tests inject an `ExplodingCategorizer` that fails the test if invoked at
all, and separately assert `cost_usd == 0.0`. "Zero LLM cost" is a monetary claim, so it is
tested as one.

**Two design decisions worth stating plainly.**

1. **`llm-confirmed` promotion is what bends the curve.** Spec 11 §4 F4 allows memory sources
   of `human | llm-confirmed`. Only human overrides being remembered would leave memory nearly
   empty, and the headline claim would be theatre. So an answer that was *auto-applied* (i.e.
   the gate already trusted it without a human) is promoted. A queued guess is **not** — that
   would launder low confidence into permanent fact, and there is a test for it.
2. **"Learned" means a human taught us.** An `llm-confirmed` hit is a memory hit but is *not*
   labelled learned. Labelling the model's own recycled answer as "learned" would overstate
   what happened to whoever reads the queue.

**Measured, on the shipped example files, in mock mode:**

| run | txns | auto-rate | memory-hit | LLM calls | cost | $/txn |
|---|---|---|---|---|---|---|
| month 1 | 120 | 78.3% | 41.7% | 70 | $0.01302 | $0.000109 |
| month 2 | 120 | 85.0% | **65.0%** | 42 | **$0.00781** | $0.000065 |

**The bend: 40.0% cheaper, LLM calls 70 → 42, memory-hit rate +23 points, auto-rate +6.7
points.** 68 mappings learned, 6 out-of-CoA hallucinations queued by the gate, 0 transactions
lost. Month 1 already shows 41.7% memory hits because promotion works *within* a run too — the
second Starbucks of the month is free.

> **Superseded in P5.** These figures were measured before P5 deliberately made the mock
> fallible (it had been an accidental oracle). The current numbers are month 1 75.8% auto /
> 40.8% memory / $0.013206 and month 2 81.7% / 62.5% / $0.008370 — a 36.6% cost drop. The
> conclusion is unchanged; the arithmetic moved. Later phases quote the corrected numbers.

**Verified**
| Check | Result |
|---|---|
| `pytest` | **213 passed**, 1 skipped |
| node count | exactly 4; bypass present as an edge; LLM never upstream of memory |
| memory bypass | `ExplodingCategorizer` never called; cost and tokens all zero |
| threshold boundary | 0.8499 → queued, 0.85 → auto, 0.86 → auto (inclusive, per "≥") |
| CoA gate | 5 hallucination shapes queued even at confidence 0.99, with confidence forced to 0 |
| learning loop | full upload→run→override→re-upload→re-run cycle green through HTTP |
| cost cap | stops the LLM, queues the remainder, records the truncation, and **memory keeps working for free after the cap** |
| ruff / format / mypy | clean (33 source files) |

**A test of mine that was wrong, not the code.** I asserted a memory hit for `LYFT *RIDE 4K2J91`
against a mapping stored under `LYFT`. That descriptor normalizes to `LYFT RIDE` — a separate
key. Exactly the multi-key reality P3 documented; the test now names its descriptors explicitly
and says why.

**Honest notes**
- Two `type: ignore[arg-type]` on `add_node`: LangGraph 1.x types node arguments as
  `_Node[Never]`, which no explicitly-annotated callable can satisfy. Third-party generics
  friction, commented as such — the closures stay internally type-checked.
- The $0.25 cap is generous for a 120-row month (~$0.013 of real spend), so it does not trigger
  on the demo data. It is exercised by tests that shrink the cap deliberately.
- Auto-precision is **not** yet measured — that is P5, and it is the number that decides
  whether the threshold of 0.85 is the right default.

**Next:** P5 · evals, the 100-case suite and the ≥95% auto-precision CI gate.

---

## P5 · Evals & CI gate — DONE (2026-09-03)

Re-read spec 11 §10 first.

**Done**
- `build_cases.py` → `cases.jsonl`: exactly 100 transactions from a fixed ledgerfab seed
  (`realistic`, seed 2026, world hash `227a59d6…`), covering 18 of 20 accounts, 39 flagged
  ambiguous. Ground truth never appears in a field the agent reads.
- `harness.py`: accuracy, auto-precision, queue-recall, auto-rate, ambiguous-queued-rate. Runs
  the **whole system** from an empty vendor memory in a throwaway database.
- `test_eval_gate.py`: the gate, plus tests that the *fixture* is still capable of failing it.
- `run_live.py`: the same suite against the real model, with a clear refusal when no key is set
  (verified: exits 2 with the fix to type).
- `evals/README.md` explaining what each metric is *for*, not just what it is.

**Results at the shipped defaults**

| metric | value |
|---|---|
| accuracy | 95.00% |
| **auto-precision** | **96.10%** — gate ≥95% **PASS** |
| queue-recall | 40.00% (2 of 5 wrong answers queued) |
| auto-rate | 77.00% (77 auto, 23 queued) |
| wrong **and** auto-applied | 3 |
| out-of-CoA caught and queued | 2 |
| cost | $0.0125 for 100 cases (mock-priced) |

**The mistake this phase caught in itself.** The first mock scored **100% accuracy**. That made
the gate pass *vacuously*: queue-recall was 0/0, and the CoA gate never fired once. The cause was
structural — I had written the mock's rule table from the same vendor catalogue that generates the
data, so it was a lookup table pretending to be a model. This is precisely what DECISIONS LOG D8
was written to prevent, and I still walked into it. Two things changed:

1. The mock now has documented, deliberate defects: confident confusions between genuinely
   adjacent accounts (Gusto → Subscriptions instead of Payroll; a Starbucks run → Office Supplies;
   a water bill → Repairs), vendors it does not recognise at all, and a confident well-formed
   **non-existent** code (`6085`, which looks like it belongs beside 6080 Professional Fees).
2. Two tests now guard the guard: `test_the_fixture_actually_contains_errors` fails if the mock
   is ever "improved" back into an oracle, and `test_a_deliberately_bad_agent_fails_the_gate` runs
   an agent that is confidently wrong about everything and asserts the gate rejects it.

**A finding worth the launch post: a higher threshold is not automatically safer.**

| threshold | auto-precision | auto-rate | gate |
|---|---|---|---|
| 0.75 | 96.10% | 77% | PASS |
| 0.80 | 96.10% | 77% | PASS |
| **0.85** | **96.10%** | **77%** | **PASS** |
| 0.90 | **94.23%** | 52% | **FAIL** |

Tightening to 0.90 makes auto-precision *worse*. The fixture's mistakes are asserted at 0.92, so
they sail through a 0.90 cut, while a third of the *correct* answers (0.86–0.90) get queued —
discarding good work and keeping the confident errors. The generalisable lesson: **a confidence
threshold only buys safety when the model's errors are less confident than its correct answers.**
That is an assumption, it is checkable, and this suite is what checks it. The 0.85 default (D10)
is now confirmed by measurement rather than chosen by feel.

**Honesty about what the CI number means.** In CI this runs against the mock, so a green gate
measures the **harness** — scoring, routing, the CoA gate, memory promotion — not the quality of
any real model. That is stated in the module docstring, in `evals/README.md`, and will be in
README STATUS. The real number needs `make eval-live`, which cannot run here (B3), so
FINAL_REPORT.md hands that command over.

**Deliberate scoring choice.** Within-run memory promotion is *in scope*: if the first Amazon is
confidently wrong and auto-applied, later Amazons inherit the error. That amplification is a real
risk of a memory-first design, so it is measured rather than excluded from the suite.

**Also fixed:** a Windows file-lock bug in the harness — the throwaway SQLite file could not be
deleted until the engine was disposed. And a test of mine was wrong rather than the code: I
asserted that no account *name* may appear in a visible field, which failed on the vendor "Hiscox
Insurance" whose account is "Insurance". A vendor name hinting at its category is legitimate
signal a bookkeeper uses, not an answer key; only the account **code** is now checked.

**Next:** P6 · the remaining API surface (queue, memory, metrics, export).

---

## P6 · Remaining API surface — DONE (2026-09-03)

Re-read spec 11 §7, §4 F3, F5 and F6 first. The backend is now feature-complete.

**Done**
- `GET /api/queue` — lowest-confidence-first, with rows that carry no decision at all sorting
  *first*: "we have no idea" deserves a human before "we are 84% sure". Plus
  `GET /api/queue/transactions` with a status filter, backing the run view and ledger table.
- `GET /api/memory` — learned mappings with hit counts, most-used first, and the account *name*
  resolved so the UI never has to look up a code.
- `GET /api/metrics` — status counts, auto-rate, memory-hit rate, total cost, a 10-bin
  confidence histogram where each bin is flagged auto/queued, spend by account, and the run
  series that draws the bend.
- `GET /api/export` — the categorized ledger.

**Design calls worth recording**

1. **The histogram bins carry their own `auto` flag.** The gate then renders as a visible
   cliff rather than something the frontend has to recompute and possibly disagree about.
2. **The category breakdown counts only *decided* lines.** A queued row has no agreed account,
   and putting a suggestion into a spend report would present a guess as fact.
3. **Metrics use the latest decision per transaction.** A row categorized twice (a second run
   after an override) would otherwise double-count history into today's numbers.
4. **Queued rows still appear in the export.** Omitting them would make the file look complete
   when a fifth of the month is unreviewed; each carries its `status` and its suggestion.
5. **Formula injection is neutralised on export, not intake.** The descriptor is stored
   verbatim because it is the audit record; the spreadsheet is where `=cmd|…` would actually
   execute. Numeric columns are formatted by us, so a `-45.50` refund never acquires a stray
   apostrophe — asserted in both directions.
6. **Export is UTF-8 *with BOM*.** Without it Excel on Windows reads the local codepage and
   mangles "Travel — Airfare" (the cp1252 trap from D15). Tested by decoding and asserting the
   em-dash survives and `â€”` does not appear.

**Verified**
| Check | Result |
|---|---|
| `pytest` | **257 passed** |
| every spec §7 endpoint registered | asserted against the **live OpenAPI schema**, not a comment |
| queue ordering | confidences come back sorted ascending |
| the memory bend | `test_the_run_series_shows_the_memory_bend` asserts hit-rate ↑, cost ↓, LLM calls ↓ across two real months |
| definition of done | one test walks upload → run → queue → override → re-run → learned → export |
| export | four required fields present; injection escaped; BOM present; negatives intact; empty ledger yields a header |
| ruff / format / mypy | clean (39 source files) |

**A test-fixture trap worth noting.** `test_an_overridden_line_exports_the_humans_account`
failed at first with a stale `status`: the verdict was committed by the *request's* session
while the long-lived test fixture session held a cached copy. Production gives every request a
fresh session, so this was a test artifact, not a bug — fixed with an explicit `expire_all()`
and a comment saying why, rather than by weakening the assertion.

**Next:** P7 · aurora components and the frontend screens.

---

## P7 + P8 · Frontend: aurora components, five screens, the memory bend — DONE (2026-09-03)

Re-read spec 11 §9 and spec 00 A2 first. Taken together because the Run screen needs the
histogram, so the chart work could not wait for P8.

**Done**
- **aurora** (`components/aurora/`): `Card`, `ConfidencePill`, `MetricTile`,
  `SyntheticDataBanner` — the four the brief names — plus `EmptyState` and `Button`, which
  every screen needed. Tokens stay in the Tailwind v4 `@theme` block from P1.
- **Five screens** per spec 11 §9, a typed API client, TanStack Query for fetch/invalidate.
- **Charts**: confidence histogram with the gate as a reference line; the memory bend; an
  auto-rate trend; a spend breakdown; CSV export.
- **22 render tests** (vitest + jsdom) across every screen, wired into CI and `make test`.

**`ConfidencePill` is the component that carries the product.** It shows the **number**, not
just a colour — "high" hides whether it was 0.86 or 0.99 — says which side of the gate the row
fell on, and never renders green below the threshold. An out-of-CoA answer reads
"invalid account" rather than "low confidence", because those are different failures and a
reviewer needs to know which one they are looking at.

**The dataviz skill changed the design, which is why it was loaded first.**

1. **No dual-axis (PLAN D17).** The bend is naturally described as "memory-hit rate up, cost
   down" — the classic invitation to two y-scales on one plot. That would put the dramatic
   "lines crossing" moment wherever the axis alignment happened to fall: an artefact of drawing,
   presented as a finding. It is now **two small multiples** on a shared x-axis. Less
   theatrical, and it doesn't lie.
2. **Colours validated by script (PLAN D18).** The UI's bright emerald and amber **fail** the
   dark-mode lightness band (L 0.696 and 0.769 against 0.48–0.67). The charts use the dimmer
   steps of the same hues — `#0E9A6C` / `#D97706` — which pass all six checks (CVD ΔE 8.3,
   normal-vision 23.4, contrast ≥3:1). The exact command is recorded in `charts/tokens.ts` so
   the next person re-runs it instead of guessing.
3. **A table view on every chart.** A tooltip must never be the only way to read a value, so
   each chart has a "Show numbers" toggle.
4. Solid hairline gridlines (dashing is reserved for the threshold line, which *is* a
   threshold); 2px lines; 8px markers; 4px rounded bar tops; the endpoint direct-labelled and
   nothing else; containers sized to include the x-axis band.

**Verified end to end over HTTP** (API on 8123, both example months uploaded and run):

| run | txns | auto-rate | memory-hit | LLM calls | cost |
|---|---|---|---|---|---|
| month 1 | 120 | 75.8% | 40.8% | 71 | $0.013206 |
| month 2 | 120 | 81.7% | **62.5%** | 45 | **$0.008370** |

**36.6% cheaper, calls 71 → 45, memory-hit +21.7 points.** P3 predicted the ceiling at 68.3%
key overlap; month 2 reached 62.5%, so the design behaved as measured rather than as hoped.

**⚠️ The manual walkthrough did not happen, and that matters.** The Chrome extension is not
connected (BLOCKERS.md **B7**), so **nobody has looked at these screens**. The dataviz method's
last step is "render it and look at it" precisely because a validator checks colour, not
layout. Substituted automated rendering, which is stronger for correctness and weaker for
appearance:
- 22 tests assert every screen mounts, in both empty and populated states, and that the
  product's claims are actually on screen (the gate, the "learned" marker, the bend in words).
- Still unverified: layout, label collisions, chart overflow, and the browser keyboard flow.
- **The README screenshot slot stays empty on purpose.** No screenshot is claimed that was not
  produced.

**Three things that went wrong, all mine**
1. **A stale server served a stale app for ten minutes.** A uvicorn process left over from my
   P1 verification still held port 8123, and it only knew `/api/health` — so uploads returned
   405 and I briefly suspected the routers. The diagnostic that settled it was asking the
   *running* server for its OpenAPI paths. Lesson applied: kill by verified PID, and check
   `openapi.json` before debugging routing.
2. **`Set-Content -Encoding UTF8` writes a BOM on PowerShell 5.1**, which broke
   `package.json` and made Vite fail to parse the PostCSS config. Swept the whole tree for
   BOMs, found three files, and rewrote them with `UTF8Encoding($false)`.
3. Three of my own render tests were wrong rather than the code: two waited on content that
   renders before the data arrives, and one asserted a single "All data synthetic" when the
   banner *and* the footer both say it. Fixed the queries, not the UI.

**Honest gaps**
- Bundle is 703 kB (212 kB gzipped), mostly Recharts. Above Vite's 500 kB advisory; not
  code-split. Fine for a local dashboard, noted rather than hidden.
- `.gitignore` was missing the SQLite `-wal`/`-shm` sidecars; added.
- P4's originally-reported bend numbers were superseded by the P5 mock recalibration; both
  PLAN.md and the P4 entry above now carry the correction.

**Next:** P9 · README, MODEL_COSTS.md, architecture diagram, and the final report.

---

## P9 · Docs, honesty pass, final report — DONE (2026-09-03)

**Done**
- **README** in spec 00 A1's mandatory order, with a STATUS section split into *works and is
  tested* / *real gaps* / *not built on purpose*.
- **MODEL_COSTS.md** — the declining-cost story with the arithmetic shown, including the part
  that undercuts the headline: 36.6% cheaper is 36.6% of about **two cents a month**. Also
  explains why the $0.25 cap is a circuit breaker rather than a budget (a 300-row month costs
  ~$0.033, or 13% of it), and how to make it fire for a demo.
- **docs/architecture.md** — the system, the 4-node graph, the two gates, the learning loop, and
  a "deliberately absent" section.
- **FINAL_REPORT.md** — the 10-step click path, the live-eval command, B1–B7 with one-line
  fixes, three judgement calls, and three next things.
- PLAN.md fully ticked: **10/10 phases, zero unticked items, zero BLOCKED markers.**

**Two things verified in this phase that had only been assumed**

1. **Docker actually works.** The image had never been built. It builds, the container serves
   `/api/health` and the SPA, and an upload + run *inside the container* produced numbers
   **identical** to the native run (75.8% auto, 40.8% memory, $0.013206). `docker compose config`
   validates. Cleaned up after.
2. **All four mermaid diagrams parse.** Ran them through the real mermaid parser under jsdom
   rather than trusting them by eye — a broken diagram renders as an error box on GitHub, right
   at the top of the README. Needed one fix along the way: Node 24 makes `globalThis.navigator`
   getter-only, so it has to be redefined rather than assigned.

**A stale-number correction.** P4's reported bend figures (78.3%/41.7% → 85.0%/65.0%) were
measured *before* P5 deliberately made the mock fallible, so they no longer matched anything
shipping. Corrected to 75.8%/40.8% → 81.7%/62.5% in PLAN.md, and the P4 entry above now carries
a "superseded" note pointing at the current values. The conclusion never changed; the arithmetic
did, and leaving two sets of numbers in the repo would have been worse than either.

**Final state**
| Check | Result |
|---|---|
| backend tests | **279 passed** |
| eval gate | **13 passed** — auto-precision 96.10% ≥ 95% |
| frontend render tests | **22 passed** |
| ruff / ruff-format / mypy / tsc | all clean |
| production build | clean |
| Docker image | builds, serves, and categorizes correctly |
| mermaid | 4/4 blocks parse |
| PLAN.md | 10/10 phases ticked |

**What remains genuinely undone, and is labelled everywhere it matters:**
- **No live eval number** (B3) — the 96.10% measures the harness, not GPT-4o-mini. One command
  fixes it, handed over in FINAL_REPORT.md §2.
- **Nobody has looked at the UI** (B7) — 22 render tests cover mounting and content; layout is
  unverified. The screenshot and demo-video slots are empty rather than faked.
- **CI has never run on a real runner** — no git remote exists.

That is the whole gap list. It is repeated in README STATUS, `evals/README.md`, MODEL_COSTS.md
and FINAL_REPORT.md, so a green number cannot be quoted out of context.

**A coverage gap the final audit caught in my own plan.** Reading PLAN.md's traceability table
back against the tree, one row pointed at `test_graph_nodes` — **a file that does not exist**. Two
explicit spec 11 §8 clauses were implemented but never asserted: *"Reason ≤ 20 words"* (the
truncation validator) and *"Temperature 0.1"*. Both were true in the code and unproven by the
suite, which is exactly the kind of claim a traceability table exists to catch. Added
`test_structured_output.py` — **22 tests** covering the word cap (truncated, not rejected;
whitespace collapsed; the mock's own reasons obey it), the required fields, confidence rejected
outside 0–1, that temperature 0.1 both defaults *and reaches the client*, and that mock answers
are deterministic. Table corrected to name the real file.

Backend total is now **279 tests**; **301** including the frontend.
