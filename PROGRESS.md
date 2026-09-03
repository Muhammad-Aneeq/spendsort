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
