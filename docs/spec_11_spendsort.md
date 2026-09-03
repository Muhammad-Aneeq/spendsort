# SPEC 11 · SPENDSORT — EXPENSE CATEGORIZATION WITH CONFIDENCE GATES
### Finance AI Lab episode project · Track 1 · 2 weeks · Python + LangChain/LangGraph + OpenAI + FastAPI + Vite/React
> **Prereq:** read `spec_00_shared_foundations.md` first (shared foundations, NDA & cost rules). Reuses ledgerfab + aurora components.

## 1. Overview & Positioning
Expense categorization is the lowest-risk, highest-volume finance AI workflow: the recommended FIRST agent per your own Day 15 carousel (Workflow #1). SpendSort is the reference implementation: an agent that categorizes transactions against a chart of accounts, attaches confidence + reasoning to every decision, auto-applies only above threshold, and routes the rest to a one-click review queue. Deliberately small: this is the Finance AI Lab series opener that demonstrates the whole trust pattern (confidence → gate → learn) in its simplest form.

## 2. Goals / Non-goals
GOALS: end-to-end demo in under 2 minutes of video; every categorization carries confidence + a one-line reason; corrections feed a learned vendor-mapping memory; the "trust pattern in miniature" is visible on one screen.
NON-GOALS: multi-entity; tax-code mapping; receipt OCR (transactions arrive as data); n8n variant (optional v2 content piece, not core).

## 3. Users & Stories
- Bookkeeper: "300 card transactions land monthly; I want 250 auto-categorized and 50 queued with the AI's best guess and reason."
- Finance AI Lab viewer: "show me the simplest honest version of an AI finance agent."
US1 upload transactions CSV (or pull from LedgerLab) → categorized run with confidence distribution. US2 review queue: accept/override in one click; overrides remembered. US3 same vendor next month → auto-categorized from memory, marked "learned". US4 export categorized ledger + audit note per line.

## 4. Feature Specification
### MVP
F1 Intake: CSV upload (date, amount, vendor/description, currency) + optional LedgerLab MCP pull; chart of accounts as editable YAML (ship a sensible default CoA).
F2 Categorization graph (LangGraph, ≤4 nodes): `normalize_vendor → check_memory (learned mappings first, zero LLM cost) → llm_categorize (structured output: {account_code, confidence, reason}) → route (auto ≥ threshold | queue)`.
F3 Review queue: sorted lowest-confidence-first; accept / override (account picker); override writes to vendor_memory with the human as source.
F4 Vendor memory: (vendor_normalized → account_code, source[human|llm-confirmed], hit_count); memory hits bypass the LLM entirely: the cost curve VISIBLY bends month over month (chart it).
F5 Dashboard: confidence histogram, auto-rate %, memory-hit rate, cost-per-run, category breakdown.
F6 Export: categorized CSV with per-line {account, confidence, source, reason}.
### v2
Rules layer (regex/amount rules evaluated before memory); n8n workflow variant as a content episode; multi-CoA profiles; anomaly flags (new vendor + unusual amount).

## 5. System Architecture
```
[SPA] ⇄ [FastAPI] ⇄ [SQLite]
              ├── LangGraph categorizer (OpenAI, structured output)
              ├── vendor_memory store
              └── optional MCP client → LedgerLab
```

## 6. Data Model
- transactions(id, date, amount, currency, vendor_raw, vendor_norm, status)
- categorizations(id, txn_id, account_code, confidence, reason, source[memory|llm], created_at)
- verdicts(id, txn_id, action[accept|override], final_account, at)
- vendor_memory(vendor_norm, account_code, source, hit_count, updated_at)
- runs(id, started, txn_count, auto_rate, memory_hit_rate, cost_usd)

## 7. API Surface
POST /api/ingest/csv · POST /api/runs (categorize all pending) · GET /api/queue · POST /api/txns/{id}/verdict · GET /api/memory · GET /api/metrics · GET /api/export.

## 8. Agent/LLM Design
Structured output enforced (Pydantic): account_code must be in the CoA (validated in code; out-of-CoA = forced low confidence + queue). Reason ≤ 20 words. Temperature 0.1. Memory-first is the signature design: the agent gets cheaper and faster every month, and the dashboard proves it: that chart IS the launch post.

## 9. Frontend Spec (aurora components)
Screens: (1) Import + CoA editor · (2) Run view (progress, confidence histogram) · (3) Review Queue (row: vendor, amount, suggested account, ConfidencePill, reason; one-click accept; override picker; keyboard flow) · (4) Memory (learned mappings table, hit counts) · (5) Metrics (auto-rate trend, cost trend, memory-bend chart).

## 10. Evals & Testing
evals/: 100 ledgerfab transactions with ground-truth categories (CoA-aligned); metrics: accuracy, auto-precision (accuracy of auto-applied only: must be ≥ 95%), queue-recall (wrong ones must land in queue, not auto). Memory tests: override → next occurrence auto + correct. CI gate on auto-precision.

## 11. Security & Privacy
Synthetic data banner; CSV hardening; cost cap per run (default $0.25); no PII assumptions.

## 12. Deployment & Costs
docker-compose; near-zero cost (memory-first + mini model). MODEL_COSTS.md shows the declining cost curve.

## 13. Milestones (2 weeks @10h)
W1 intake + CoA + graph + memory + routing + evals
W2 queue UI + dashboard + export + README + 90s demo video (the series opener)

## 14. Risks
Vendor normalization quality (messy descriptors) → normalize aggressively, test on ledgerfab alias chaos; CoA ambiguity (two plausible accounts) → confidence must drop, tested with deliberately ambiguous eval cases.

## 15. Launch Content Hooks
Finance AI Lab Episode 1: "The simplest honest finance agent: watch it earn trust" · the memory-bend chart post ("my agent gets cheaper every month") · "95% auto-precision or it stays in the queue: thresholds explained".
