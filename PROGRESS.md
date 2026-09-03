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
