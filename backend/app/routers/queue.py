"""GET /api/queue — the review queue (spec 11 section 7).

spec 11 section 4 F3: "Review queue: sorted lowest-confidence-first".

The ordering is the feature. A bookkeeper working top-down meets the agent's worst guesses
first, which is where their attention is actually worth something.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.coa import ChartOfAccounts, get_coa
from app.db import get_db
from app.models import Categorization, MemorySource, Transaction, TxnStatus, VendorMemory
from app.schemas import CategorizationOut, QueueOut, TransactionOut
from app.settings import get_settings

router = APIRouter(prefix="/api/queue", tags=["review queue"])


def to_transaction_out(
    txn: Transaction,
    *,
    coa: ChartOfAccounts | None = None,
    memory: dict[str, VendorMemory] | None = None,
) -> TransactionOut:
    """Shape one row for the UI, including whether it was learned from a human."""
    coa = coa or get_coa()
    decision: Categorization | None = txn.latest_categorization

    learned = False
    if decision and decision.source == "memory" and memory is not None:
        entry = memory.get(txn.vendor_norm)
        learned = entry is not None and entry.source == MemorySource.HUMAN.value

    suggestion = None
    if decision:
        suggestion = CategorizationOut(
            account_code=decision.account_code,
            account_name=coa.name_for(decision.account_code) if decision.account_code else "",
            confidence=decision.confidence,
            reason=decision.reason,
            source=decision.source,
            coa_valid=decision.coa_valid,
            cost_usd=decision.cost_usd,
            created_at=decision.created_at,
        )

    final = txn.final_account
    return TransactionOut(
        id=txn.id,
        date=txn.date,
        amount=txn.amount,
        currency=txn.currency,
        vendor_raw=txn.vendor_raw,
        vendor_norm=txn.vendor_norm,
        status=txn.status,
        memo=txn.memo,
        suggestion=suggestion,
        final_account=final,
        final_account_name=coa.name_for(final) if final else None,
        learned=learned,
    )


@router.get("", response_model=QueueOut)
def read_queue(
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> QueueOut:
    """Queued transactions, least-confident first."""
    coa = get_coa()
    memory = {m.vendor_norm: m for m in db.scalars(select(VendorMemory))}

    txns = list(
        db.scalars(
            select(Transaction)
            .options(selectinload(Transaction.categorizations), selectinload(Transaction.verdicts))
            .where(Transaction.status == TxnStatus.QUEUED)
        )
    )

    def sort_key(txn: Transaction) -> tuple[float, int]:
        # Rows with no decision at all sort first: "we have no idea" deserves a human's
        # attention before "we are 84% sure".
        decision = txn.latest_categorization
        return (decision.confidence if decision else -1.0, txn.id)

    txns.sort(key=sort_key)
    total = len(txns)
    page = txns[offset : offset + limit]

    return QueueOut(
        items=[to_transaction_out(t, coa=coa, memory=memory) for t in page],
        total=total,
        auto_threshold=get_settings().auto_threshold,
    )


@router.get("/transactions", response_model=QueueOut)
def read_transactions(
    status: str | None = Query(default=None, description="pending | auto | queued | resolved"),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> QueueOut:
    """All transactions, optionally filtered by status. Backs the run view and the ledger table."""
    coa = get_coa()
    memory = {m.vendor_norm: m for m in db.scalars(select(VendorMemory))}

    stmt = select(Transaction).options(selectinload(Transaction.categorizations), selectinload(Transaction.verdicts))
    if status:
        stmt = stmt.where(Transaction.status == status)

    txns = list(db.scalars(stmt.order_by(Transaction.date, Transaction.id)))
    total = len(txns)
    page = txns[offset : offset + limit]

    return QueueOut(
        items=[to_transaction_out(t, coa=coa, memory=memory) for t in page],
        total=total,
        auto_threshold=get_settings().auto_threshold,
    )
