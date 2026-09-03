"""POST /api/ingest/csv — spec 11 section 7."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.logging import get_logger
from app.models import Transaction, TxnStatus
from app.schemas import IngestResultOut, RowErrorOut
from app.services.ingest import IngestError, parse_csv
from app.settings import get_settings

router = APIRouter(prefix="/api/ingest", tags=["intake"])
log = get_logger("spendsort.ingest")

# Only the first N row errors are returned, so a pathological file cannot produce a
# multi-megabyte response. The counts are always complete.
MAX_REPORTED_ERRORS = 50


@router.post("/csv", response_model=IngestResultOut, status_code=status.HTTP_201_CREATED)
async def ingest_csv(
    file: UploadFile = File(..., description="Transactions CSV: date, amount, currency, vendor, memo"),
    db: Session = Depends(get_db),
) -> IngestResultOut:
    settings = get_settings()

    data = await file.read()
    try:
        report = parse_csv(
            data,
            max_bytes=settings.max_upload_bytes,
            max_rows=settings.max_rows_per_upload,
        )
    except IngestError as exc:
        # A rejected file is a client error, and the message says exactly what to fix.
        # 422 as a literal: the Starlette constant was renamed and we support both versions.
        raise HTTPException(422, detail=str(exc)) from exc

    source = (file.filename or "upload.csv")[:256]

    db.add_all(
        [
            Transaction(
                date=row.date,
                amount=row.amount,
                currency=row.currency,
                vendor_raw=row.vendor_raw,
                vendor_norm=row.vendor_norm,
                status=TxnStatus.PENDING,
                memo=row.memo,
                source_file=source,
            )
            for row in report.rows
        ]
    )
    db.commit()

    pending_total = db.scalar(
        select(func.count()).select_from(Transaction).where(Transaction.status == TxnStatus.PENDING)
    )

    log.info(
        "csv ingested",
        extra={
            "context": {
                "file": source,
                "accepted": report.accepted,
                "rejected": report.rejected,
                "encoding": report.encoding,
                "truncated": report.truncated,
            }
        },
    )

    return IngestResultOut(
        accepted=report.accepted,
        rejected=report.rejected,
        truncated=report.truncated,
        encoding=report.encoding,
        source_file=source,
        errors=[RowErrorOut(line=e.line, reason=e.reason, raw=e.raw) for e in report.errors[:MAX_REPORTED_ERRORS]],
        pending_total=pending_total or 0,
    )
