"""GET /api/metrics — everything the dashboard needs (spec 11 section 7)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import MetricsOut
from app.services.metrics import build_metrics

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("", response_model=MetricsOut)
def read_metrics(db: Session = Depends(get_db)) -> MetricsOut:
    """Confidence histogram, auto-rate, memory-hit rate, category breakdown, and the run
    series that draws the memory bend (spec 11 section 4 F5 and section 8)."""
    return build_metrics(db)
