# BLOCKERS.md · SpendSort

Policy: never stop and wait. Each blocker is recorded with **what / tried / needed / workaround**, the affected
PLAN.md tasks are marked `[B]`, a stub or fallback goes in, and work continues.

Status legend: **OPEN** (workaround active, still needs the real thing) · **RESOLVED** · **ACCEPTED** (workaround is the permanent answer).

---

## B1 · `backend_seed_ledgerfab/` does not exist — OPEN (workaround active)

**What.** Adaptation 1 instructs: *"REUSE ledgerfab from `./backend_seed_ledgerfab/` (move to `backend/ledgerfab/`)."*
That directory is not present. At Phase 0 the repository contained exactly two files — `spec_00_shared_foundations.md`
and `spec_11_spendsort.md` — and no seed code of any kind.

**Tried.**
- Recursive listing of the whole working tree, including hidden/forced entries, to depth 3 → only the two spec files.
- Checked for version control that might hold the seed in history → `git` reports this is **not** a repository, so there is no prior commit to recover it from.
- Looked for the directory under any adjacent spelling (seed / backend / ledgerfab) → nothing.

**Needed.** Either the `backend_seed_ledgerfab/` source dropped into the repo root, or confirmation that
building ledgerfab from the spec is the intended path.

**Workaround (active).** Adaptation 1's own stated fallback: implement `backend/ledgerfab/` from **spec 00 A3**.
Scoped deliberately to what SpendSort actually consumes — chart of accounts, counterparties **with aliases**,
bank transactions, and the ground-truth emitter — with seeded reproducibility and the
`clean` / `realistic` / `nightmare` presets. Spec 00 A3 also lists invoices, POs, GL entries and recurring-accrual
schedules; SpendSort reads none of those, so they are **not** built (PLAN.md DECISIONS LOG **D3**).

**Consequence if the real seed arrives later.** The public surface is kept to spec 00 A3's contract
(`ledgerfab.generate(profile, seed) -> World`, `world.ground_truth`), so a drop-in replacement should not
require changes in `app/` or `evals/`.

**PLAN.md tasks affected.** P2 (all) — proceeding under the fallback, not blocked from progress.

---

## B2 · `make` is not installed on this machine — OPEN (workaround active)

**What.** The Definition of Done opens with `make dev`. `make` is absent from PATH
(`Get-Command make` → not found); the box is Windows 11 with PowerShell as the primary shell.

**Tried.** Checked PATH for `make`, and for a Git-Bash-bundled `make` — neither present.

**Needed.** A `make` binary on PATH.

**One-line fix.** `winget install ezwinports.make`  (alternatively `choco install make`).

**Workaround (active).** Ship **both**: a real `Makefile` (authoritative for CI, docker and Linux/macOS) and a
`make.ps1` PowerShell shim exposing the same targets, so `./make.ps1 dev` works here today with no install.
Targets stay in lockstep between the two files; FINAL_REPORT.md gives both invocations.

**PLAN.md tasks affected.** P1 (`Makefile` + shim) — mitigated, not blocking.

---

## B3 · No `OPENAI_API_KEY` in the environment — OPEN (expected; workaround active)

**What.** No `OPENAI_API_KEY` is set, so no live OpenAI call can be made from this machine. The categorization
graph, the live eval, and any real cost measurement all need it.

**Tried.** Checked the environment for `OPENAI_API_KEY` → not set. No `.env` file exists in the repo.

**Needed.** A funded OpenAI API key exported as `OPENAI_API_KEY` (Track 1 per spec 00 F).

**Workaround (active).** This is the case adaptation 3 anticipates: *"LLM mocked in default tests; live behind
pytest marker `live`."* Mock mode is built as a **first-class code path** (`SPENDSORT_MOCK_LLM=1`), not a
test-only shim, so the entire demo — upload, run, queue, override, learn, dashboard, export — runs end to end at
zero spend. The mock replays a fixed, deliberately **imperfect** fixture (including a wrong answer and an
out-of-CoA answer) so the ≥95% auto-precision gate and queue-recall are genuinely exercised and *can* fail
(PLAN.md DECISIONS LOG **D8**).

**Honesty note.** Any auto-precision figure produced in CI is therefore a **mock-mode** number and will be
labelled as such in README STATUS and in eval output. It demonstrates that the gate works; it does not measure
the real model. The live-eval command is handed to the reviewer in FINAL_REPORT.md so the real number can be
produced on a machine that has a key.

**PLAN.md tasks affected.** P5 (live eval verification) — the live path is implemented and marked, but its
result is **unverified here** by definition.

---

## B4 · Model pricing cannot be verified offline — ACCEPTED

**What.** `MODEL_COSTS.md` and the `$0.25` per-run cost cap need per-token prices. I cannot confirm current
OpenAI list prices from this environment.

**Needed.** Confirmation of current per-1M-token input/output pricing for the configured mini-class model.

**Workaround (accepted).** All pricing lives in a **single** env-overridable table in `app/costs.py`, is stamped
with the date it was written, and is labelled in MODEL_COSTS.md as requiring confirmation. Updating a price is a
config change, never a code change. Cost-cap enforcement logic is independent of the specific numbers, so it is
correct regardless (PLAN.md DECISIONS LOG **D6**).

---

## B5 · No upstream projects exist (LedgerLab MCP, `aurora-ui` package) — ACCEPTED

**What.** Spec 11 §4 F1 offers an *optional* LedgerLab MCP pull, and spec 00 A2 defines `aurora-ui` as a shared
workspace package. Neither exists: spec 00 B places Project 02 (Ledger MCP Server) upstream of this work, and its
rule is explicit — *"never start a project whose upstream isn't built."*

**Workaround (accepted).**
- **LedgerLab MCP:** out of scope. It is spec-optional, and building it would mean starting an unbuilt upstream.
  CSV intake satisfies every user story in spec 11 §3 (PLAN.md **D4**).
- **aurora-ui:** per adaptation 2, the four required components (`Card`, `ConfidencePill`, `MetricTile`,
  `SyntheticDataBanner`) are implemented locally in `frontend/src/components/aurora/` against spec 00 A2 tokens.

**PLAN.md tasks affected.** None blocked; both are deliberate scope decisions rather than obstacles.
