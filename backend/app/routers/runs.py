"""POST /api/runs — "categorize all pending" (spec 11 section 7)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Run
from app.schemas import RunOut
from app.services.runner import categorize_pending

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.post("", response_model=RunOut, status_code=status.HTTP_201_CREATED)
def create_run(db: Session = Depends(get_db)) -> Run:
    """Run the categorization graph over every pending transaction.

    Safe to call with nothing pending: it returns an empty run rather than an error, which
    keeps the UI simple and makes the run history honest about having been asked.
    """
    return categorize_pending(db)


@router.get("", response_model=list[RunOut])
def list_runs(db: Session = Depends(get_db)) -> list[Run]:
    """Oldest first — this series is the memory-bend chart (spec 11 section 4 F5)."""
    return list(db.scalars(select(Run).order_by(Run.id)))
