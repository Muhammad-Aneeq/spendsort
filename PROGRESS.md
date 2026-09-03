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
