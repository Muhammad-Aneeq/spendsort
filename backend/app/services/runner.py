"""Run orchestration — POST /api/runs, "categorize all pending" (spec 11 section 7).

Responsibilities:
  * drive the 4-node graph over every pending transaction
  * hold the per-run cost budget (spec 11 section 11, default $0.25)
  * promote confidently-auto answers into vendor memory, which is what bends the cost curve
  * roll the run up into `runs`, so the dashboard can chart the bend across runs

When the cap is reached, the remaining transactions are **queued, never dropped** (PLAN.md D7).
Silently leaving rows uncategorized would be a dishonest kind of success — and note that
memory hits keep working after the cap, because they cost nothing.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.graph import build_graph
from app.agent.llm import Categorizer
from app.coa import ChartOfAccounts, get_coa
from app.costs import budget_for_run
from app.logging import get_logger
from app.models import (
    Categorization,
    CategorizationSource,
    MemorySource,
    Run,
    Transaction,
    TxnStatus,
    utcnow,
)
from app.services import memory as memory_service
from app.settings import get_settings

log = get_logger("spendsort.runner")


def pending_transactions(db: Session) -> list[Transaction]:
    """Oldest first, so a run reads like the month it represents."""
    return list(
        db.scalars(
            select(Transaction)
            .where(Transaction.status == TxnStatus.PENDING)
            .order_by(Transaction.date, Transaction.id)
        )
    )


def categorize_pending(
    db: Session,
    *,
    categorizer: Categorizer | None = None,
    coa: ChartOfAccounts | None = None,
    cost_cap_usd: float | None = None,
    auto_threshold: float | None = None,
) -> Run:
    """Categorize every pending transaction and return the completed run."""
    settings = get_settings()
    resolved_coa = coa or get_coa()
    threshold = auto_threshold if auto_threshold is not None else settings.auto_threshold
    budget = budget_for_run(cost_cap_usd)

    run = Run(
        auto_threshold=threshold,
        cost_cap_usd=budget.cap_usd,
        model=settings.model,
        llm_mode="mock" if settings.use_mock_llm else "live",
    )
    db.add(run)
    db.flush()  # assigns run.id, needed on every categorization row

    graph = build_graph(db, categorizer=categorizer, coa=resolved_coa)
    coa_block = resolved_coa.prompt_block()

    txns = pending_transactions(db)
    auto_count = 0
    memory_hits = 0

    for txn in txns:
        result = graph.invoke(
            {
                "txn_id": txn.id,
                "vendor_raw": txn.vendor_raw,
                "amount": txn.amount,
                "currency": txn.currency,
                "date": txn.date.isoformat(),
                "memo": txn.memo,
                "coa_block": coa_block,
                "auto_threshold": threshold,
                "budget_remaining_usd": budget.remaining_usd,
                "trace": [],
            }
        )

        source = result.get("source", CategorizationSource.LLM.value)
        spent = float(result.get("cost_usd", 0.0) or 0.0)

        if source == CategorizationSource.MEMORY.value:
            memory_hits += 1
        elif result.get("cost_capped"):
            budget.block()
        else:
            budget.charge(
                int(result.get("prompt_tokens", 0) or 0),
                int(result.get("completion_tokens", 0) or 0),
            )

        status = result.get("status", TxnStatus.QUEUED.value)
        if status == TxnStatus.AUTO.value:
            auto_count += 1

        db.add(
            Categorization(
                txn_id=txn.id,
                run_id=run.id,
                account_code=result.get("account_code", "") or "",
                confidence=float(result.get("confidence", 0.0) or 0.0),
                reason=(result.get("reason", "") or "")[:512],
                source=source,
                coa_valid=bool(result.get("coa_valid", False)),
                prompt_tokens=int(result.get("prompt_tokens", 0) or 0),
                completion_tokens=int(result.get("completion_tokens", 0) or 0),
                cost_usd=spent,
            )
        )
        txn.status = status
        # `vendor_norm` is recomputed by the graph; keep the row in step in case the
        # normalizer has been improved since intake.
        txn.vendor_norm = result.get("vendor_norm", txn.vendor_norm)
        db.add(txn)

        # Promote a trusted answer into memory. This is the mechanism behind the bend: next
        # month this vendor costs nothing. Only auto-applied, CoA-valid, LLM-sourced answers
        # qualify — a queued guess has not earned it.
        if status == TxnStatus.AUTO.value and source == CategorizationSource.LLM.value and result.get("coa_valid"):
            memory_service.remember(
                db,
                vendor_norm=result.get("vendor_norm", ""),
                account_code=result.get("account_code", ""),
                source=MemorySource.LLM_CONFIRMED,
                example_vendor_raw=txn.vendor_raw,
            )

    total = len(txns)
    run.txn_count = total
    run.auto_rate = (auto_count / total) if total else 0.0
    run.memory_hit_rate = (memory_hits / total) if total else 0.0
    run.cost_usd = round(budget.spent_usd, 6)
    run.llm_calls = budget.llm_calls
    run.memory_hits = memory_hits
    run.cost_capped = budget.blocked > 0
    run.capped_txn_count = budget.blocked
    run.finished = utcnow()

    db.add(run)
    db.commit()
    db.refresh(run)

    log.info(
        "run complete",
        extra={
            "context": {
                "run_id": run.id,
                "txn_count": total,
                "auto_rate": round(run.auto_rate, 4),
                "memory_hit_rate": round(run.memory_hit_rate, 4),
                "cost_usd": run.cost_usd,
                "llm_calls": run.llm_calls,
                "cost_capped": run.cost_capped,
                "capped_txn_count": run.capped_txn_count,
            }
        },
    )
    return run
