"""POST /api/txns/{id}/verdict — accept or override (spec 11 section 7).

spec 11 section 4 F3: "accept / override (account picker); override writes to vendor_memory
with the human as source."

This endpoint closes the learning loop, and it is where the product earns its keep: the
correction a bookkeeper makes once should never need making again.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.coa import get_coa
from app.db import get_db
from app.logging import get_logger
from app.models import (
    MemorySource,
    Transaction,
    TxnStatus,
    Verdict,
    VerdictAction,
)
from app.schemas import VerdictIn, VerdictOut
from app.services import memory as memory_service

router = APIRouter(prefix="/api/txns", tags=["review queue"])
log = get_logger("spendsort.verdicts")


@router.post("/{txn_id}/verdict", response_model=VerdictOut, status_code=status.HTTP_201_CREATED)
def record_verdict(
    txn_id: int,
    payload: VerdictIn,
    db: Session = Depends(get_db),
) -> VerdictOut:
    txn = db.get(Transaction, txn_id)
    if txn is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"transaction {txn_id} not found")

    coa = get_coa()
    suggestion = txn.latest_categorization

    if payload.action == VerdictAction.ACCEPT.value:
        if suggestion is None:
            raise HTTPException(422, detail="nothing to accept: this transaction has no suggestion yet")
        if not coa.is_valid(suggestion.account_code):
            # Accepting an out-of-CoA suggestion would smuggle a bad code into the ledger via
            # the one path that is supposed to be the safety net.
            raise HTTPException(
                422,
                detail=(
                    f"cannot accept {suggestion.account_code!r}: it is not in the chart of accounts. "
                    "Override with a real account instead."
                ),
            )
        final_account = suggestion.account_code
    else:
        if not payload.final_account:
            raise HTTPException(422, detail="an override needs final_account")
        if not coa.is_valid(payload.final_account):
            raise HTTPException(422, detail=f"{payload.final_account!r} is not in the chart of accounts")
        final_account = payload.final_account

    verdict = Verdict(txn_id=txn.id, action=payload.action, final_account=final_account)
    db.add(verdict)

    txn.status = TxnStatus.RESOLVED
    db.add(txn)

    # An override is a human teaching us the answer, so it is written to memory with the
    # human as source (spec 11 section 4 F3). An accept is only agreement with what the model
    # already said, and that answer was promoted to memory when it auto-applied — so an
    # accept does not need to write, and writing it as "human" would overstate the evidence.
    memory_written = False
    if payload.action == VerdictAction.OVERRIDE.value:
        entry = memory_service.remember(
            db,
            vendor_norm=txn.vendor_norm,
            account_code=final_account,
            source=MemorySource.HUMAN,
            example_vendor_raw=txn.vendor_raw,
        )
        memory_written = entry is not None

    db.commit()
    db.refresh(verdict)

    log.info(
        "verdict recorded",
        extra={
            "context": {
                "txn_id": txn.id,
                "action": payload.action,
                "final_account": final_account,
                "vendor_norm": txn.vendor_norm,
                "memory_written": memory_written,
            }
        },
    )

    return VerdictOut(
        txn_id=txn.id,
        action=verdict.action,
        final_account=final_account,
        final_account_name=coa.name_for(final_account),
        memory_written=memory_written,
        at=verdict.at,
    )
