"""GET /api/export — the categorized ledger as CSV (spec 11 section 7)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.export import export_bytes

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("")
def export(
    only_decided: bool = Query(
        default=False,
        description="Exclude transactions still awaiting review",
    ),
    db: Session = Depends(get_db),
) -> Response:
    """Per-line {account, confidence, source, reason} (spec 11 section 4 F6).

    Served as a download with a BOM so Excel on Windows reads the em-dash account names
    correctly, and with formula-injection neutralised on text cells.
    """
    payload = export_bytes(db, only_decided=only_decided)
    return Response(
        content=payload,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="spendsort_categorized.csv"'},
    )
