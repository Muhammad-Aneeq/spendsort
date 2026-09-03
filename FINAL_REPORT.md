# FINAL_REPORT.md · SpendSort

**Built 2026-09-03.** Expense categorization with confidence gates and a learning vendor memory —
the Finance AI Lab series opener, per `docs/spec_11_spendsort.md` and `docs/spec_00_shared_foundations.md`.

**Bottom line:** the product is complete and tested end to end. 301 tests pass, the eval gate is
green, the memory bend is real and measured, and the whole demo runs with no API key and no
spend. Two things are genuinely unverified and neither is faked: **nobody has looked at the UI**
(no browser here), and **the eval number is mock-mode** (no API key here). Both have a one-line
fix below.

---

## 1. Demo it — exact commands

The whole demo runs in **mock mode**: no API key, no network calls, no spend.

### Setup

```bash
git clone <repo> && cd spendsort
make install
```

<details>
<summary><b>Windows</b> — <code>make</code> is absent and port 8000 is usually taken by Docker/WSL</summary>

```powershell
./make.ps1 install
./make.ps1 dev -Port 8123
```

Every `make X` below has a `./make.ps1 X` twin. This is how it was developed and verified.
</details>

### Run it

```bash
make dev              # API :8000 + SPA :5173
# Windows:  ./make.ps1 dev -Port 8123
```

Open **http://localhost:5173** — note `localhost`, not `127.0.0.1`: Vite 6 binds IPv6 `::1` only.

### The 90-second click path

| # | Do this | Watch for |
|---|---|---|
| 1 | **Import** → upload `examples/month_01_realistic_seed42.csv` | `120 accepted, 0 rejected`. Those rows carry deliberate date chaos (`04 Jan 2026`, `01/04/26`), FX flags and messy descriptors — all parsed |
| 2 | Click **Categorize 120 transactions →** | ~76% auto-applied, ~41% already from memory. Memory works *within* a run: the second Starbucks is free |
| 3 | **Run** screen | The confidence histogram. The dashed line is the gate at 0.85 — the tall bar just under it is what the agent nearly trusted |
| 4 | **Review queue** | Sorted lowest-confidence first. Rows show vendor, amount, suggested account, a ConfidencePill with the **number**, and the reason. Some read **"invalid account"** — the model named an account that does not exist and the CoA gate caught it. Accept is *disabled* on those |
| 5 | Press `j` `j` `a` | Keyboard flow: `j`/`k` move, `a` accepts, `o` overrides, `Esc` cancels |
| 6 | Find an **Amazon** row, press `o`, pick **6020 Computer Equipment** | *"Learned: 6020 Computer Equipment. This vendor will auto-categorize next time."* |
| 7 | **Memory** | The mapping, tagged **human**, with a hit count. "Model calls avoided" is the running total |
| 8 | **Import** → upload `examples/month_02_realistic_seed43.csv` → **Categorize** | Same volume, same vendors |
| 9 | **Metrics** — ***the money shot*** | **The memory bend**: hit rate 40.8% → 62.5%, cost $0.0132 → $0.0084, **36.6% cheaper**. Two panels, not one dual-axis plot — see §5 |
| 10 | **Metrics** → **Export CSV ↓** | Per line: `account, confidence, source, reason` |

Optional, worth showing: `examples/ambiguous_edge_cases.csv` — 24 rows of vendors with two
defensible accounts (Amazon, Uber, Airbnb). Correct behaviour is *low confidence and a queued
row*, not a lucky guess.

### Make the cost cap fire

At $0.000186 a call, the $0.25 cap is a circuit breaker, not a budget — it never triggers on
120 rows. To demo it:

```bash
SPENDSORT_COST_CAP_USD_PER_RUN=0.001 make dev    # ~5 calls, then everything queues
```

The Run screen then says *"Cost cap reached. N transactions were queued for review rather than
sent to the model. Nothing was dropped."*

### Everything else

```bash
make test        # 279 backend + 22 frontend tests. No key, no spend
make eval        # 100-case eval suite + the ≥95% auto-precision gate
make seed        # regenerate examples/ and evals/cases.jsonl from fixed seeds
make lint        # ruff check + format
make typecheck   # mypy + tsc
make up          # docker compose (image build + run verified, see §3)
```

---

## 2. ⭐ The live-eval command — for you

This is the one thing I could not do, and the number that actually matters.

```bash
export OPENAI_API_KEY=sk-...          # PowerShell: $env:OPENAI_API_KEY = "sk-..."
make eval-live
```

<details>
<summary>Without <code>make</code></summary>

```powershell
$env:OPENAI_API_KEY = "sk-..."
$env:PYTHONPATH = "backend"
uv run python evals/run_live.py
```

Options: `--threshold 0.90` to sweep the gate, `--model gpt-4.1-mini` to compare models.
</details>

**Expected spend: $0.01–0.02** (100 cases, minus memory hits, on a mini-class model).

It prints accuracy, auto-precision and queue-recall, writes `evals/report_live.json`, and
**exits non-zero if auto-precision is below 95%** — so it can gate a release. It refuses to run
without a key rather than silently falling back to the mock (verified: exits 2 with the fix to
type).

**Why this matters.** CI runs the same suite against `MockCategorizer`, so the **96.10%
auto-precision in the README measures the harness, not GPT-4o-mini.** It proves scoring,
routing, the CoA gate and memory promotion all behave. Only `make eval-live` measures the model.

Also worth running once you have a key:

```bash
make test-live      # tests marked `live` (none are required for the product to work)
```

---

## 3. What is verified, and how

| Claim | How it was checked |
|---|---|
| Graph has **exactly 4 nodes** | Structural test on the compiled graph; fails if a fifth is added |
| Memory hits **bypass the LLM** | A categorizer that **raises if called**, plus `cost_usd == 0.0`. Asserting `source == "memory"` would have passed even if the call had been made and discarded |
| Out-of-CoA codes are queued | 5 hallucination shapes, all queued at confidence **0.99**, confidence forced to 0 |
| Threshold is inclusive | Boundary tested at 0.8499 / 0.85 / 0.86 |
| The learning loop | Full upload → run → override → re-upload → re-run → *learned* over HTTP |
| Cost cap | Stops the LLM, queues the remainder, records the truncation — **and memory keeps working free after the cap** |
| The memory bend | A test asserts hit-rate ↑, cost ↓ and LLM calls ↓ across two real months |
| All 8 spec §7 endpoints | Asserted against the **live OpenAPI schema**, not a comment |
| ledgerfab determinism | Same seed+profile ⇒ identical content hash, across all three presets |
| Normalization | Zero key collisions and full idempotence over a 2,000-row nightmare sample |
| Every example CSV imports | Zero rejected rows across all three shipped files |
| Chart colours | `validate_palette.js` — all six checks pass on the dark surface |
| Mermaid diagrams | All 4 blocks parsed with the real mermaid parser |
| **Docker** | Image builds; container serves `/api/health` + the SPA, and an upload+run inside it produced **identical numbers** to the native run (75.8% auto, 40.8% memory, $0.013206). `docker compose config` valid |

**301 tests** (279 backend, 22 frontend). ruff, ruff-format, mypy and tsc all clean.

### Measured results

```
accuracy               95.00%
auto-precision         96.10%   GATE >= 95%  [PASS]
queue-recall           40.00%   (2 of 5 wrong answers were queued)
auto-rate              77.00%   (77 auto, 23 queued)
```

| run | txns | memory-hit | LLM calls | cost |
|---|---|---|---|---|
| month 1 | 120 | 40.8% | 71 | $0.013206 |
| month 2 | 120 | **62.5%** | 45 | **$0.008370** |

---

## 4. Blockers, with one-line fixes

Full detail — what/tried/needed/workaround — in `BLOCKERS.md`.

| # | Blocker | State | One-line fix |
|---|---|---|---|
| **B1** | `backend_seed_ledgerfab/` does not exist | **Worked around** | Drop the real seed in; the public surface matches spec 00 A3 (`generate(profile, seed) -> World`), so `app/` and `evals/` shouldn't change |
| **B2** | `make` not installed | Mitigated | `winget install ezwinports.make` — or keep using `./make.ps1`, which mirrors every target |
| **B3** | No `OPENAI_API_KEY` | **Open — affects a headline number** | `export OPENAI_API_KEY=sk-... && make eval-live` |
| **B4** | Prices unverified | Accepted | Check OpenAI's pricing page, then set `SPENDSORT_PRICE_INPUT_PER_1M` / `..._OUTPUT_PER_1M` — no code change |
| **B5** | No `aurora-ui` package, no LedgerLab MCP | Accepted | Out of scope by spec 00 B (unbuilt upstream); the four aurora components are local |
| **B6** | Port 8000 taken by Docker/WSL | **Resolved** | `make dev PORT=8123` / `./make.ps1 dev -Port 8123` |
| **B7** | No browser — UI never seen | **Open — affects the screenshot** | Open http://localhost:5173, walk §1, capture the Metrics screen |

### The two that are really open

**B3 — the eval number is mock-mode.** One command fixes it (§2). The mock is *deliberately*
imperfect so the gate can fail: it confuses adjacent accounts confidently, draws a blank on some
vendors, and hallucinates a well-formed non-existent code. An earlier version of it scored 100%
and made the gate meaningless — two tests now fail if anyone turns it back into an oracle.

**B7 — nobody has looked at the UI.** 22 render tests assert every screen mounts, in empty and
populated states, and that the product's claims are on screen. They **cannot judge layout**:
label collisions, chart overflow and spacing are unverified, as is the keyboard flow against real
browser key events. The README screenshot slot and the demo-video link are empty on purpose.

---

## 5. Three judgement calls worth knowing about

**1. The memory bend is two charts, not one.** "Memory-hit rate up, cost down" invites a
dual-axis plot, but two y-scales put the dramatic crossing point wherever the axis alignment
happens to fall — an artefact of drawing, presented as a finding. It ships as two small
multiples on a shared x-axis. Less theatrical, and it doesn't lie.

**2. `llm-confirmed` promotion is what actually bends the curve.** Spec 11 §4 F4 allows memory
sources of `human | llm-confirmed`. If only human overrides were remembered, memory would stay
nearly empty and "gets cheaper every month" would be theatre. So an answer the gate *already*
trusted enough to apply unsupervised gets promoted. A **queued** guess never is — that would
launder low confidence into permanent fact. And only `human` mappings are labelled "learned",
because calling the model's own recycled answer "learned" would overstate it.

**3. A higher threshold is not automatically safer** — and the eval proved it. At 0.90,
auto-precision gets **worse** (96.10% → 94.23%): the fixture's errors sit at 0.92 and survive the
cut, while a third of the *correct* answers (0.86–0.90) get queued. Tightening the gate discarded
good work and kept the confident mistakes. **A confidence threshold only buys safety when the
model's errors are less confident than its correct answers.** That is an assumption, it is
checkable, and this suite is what checks it — it is also the best launch-post material here after
the bend itself.

---

## 6. Three next things

**1. Run `make eval-live` and publish the real number.** *(~10 minutes, needs a key.)*
Everything else here is honest but provisional until this exists. Do it at 0.80 / 0.85 / 0.90 and
publish the threshold sweep — if the real model's errors turn out to be *less* confident than its
correct answers (the opposite of the mock fixture), then a higher threshold *does* buy safety, and
that reversal is a better post than either number alone. Then delete the mock-mode caveats from
README STATUS and MODEL_COSTS.md.

**2. Capture the screenshot and record the 90-second demo.** *(~1 hour.)* Spec 00 A1 puts the
screenshot first and spec 00 E makes the video part of "launch-ready"; the Metrics screen with two
months loaded is the shot. Do the visual pass at the same time — the charts have never been seen,
so budget for layout fixes. This is the last thing standing between the repo and launch-ready.

**3. Make normalization measurable, then improve it.** *(~half a day, highest leverage.)*
Normalization quality *is* cost: taking one vendor from 14.9 keys to 2.4 cut the long-run bill by
roughly the same factor, and the current 68% memory ceiling is set entirely by residual key
fragmentation (`HISCOX INS` vs `HISCOX PREMIUM` are still two keys). Add the key-count and
collision probe from P3 as a permanent eval metric, then attack the biggest offenders. Raising the
ceiling from 68% to 85% is a further ~50% cost cut and needs no model change at all — and it makes
"my agent gets cheaper every month" a curve with a second act.

---

## 7. Where things are

| | |
|---|---|
| `PLAN.md` | The plan, fully ticked, with 19 logged decisions |
| `PROGRESS.md` | Phase-by-phase log, including every bug the tests caught |
| `BLOCKERS.md` | B1–B7, each with what/tried/needed/workaround |
| `MODEL_COSTS.md` | The declining-cost story with the arithmetic shown |
| `docs/architecture.md` | The graph, the two gates, the learning loop |
| `evals/README.md` | What each metric is *for*, and why a green mock gate proves less than it looks |
| `examples/README.md` | Provenance and content hashes for the shipped CSVs |

**Definition of done:** met, except the screenshot and demo video (B7) and a live eval number
(B3) — both called out here and in README STATUS rather than papered over.
