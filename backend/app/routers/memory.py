"""GET /api/memory — the learned vendor mappings (spec 11 section 7).

spec 11 section 9 screen 4: "Memory (learned mappings table, hit counts)".

`hit_count` is the interesting column: it is the evidence that a mapping is earning its keep,
and the sum of it across the table is the number of LLM calls that never had to happen.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.coa import get_coa
from app.db import get_db
from app.schemas import MemoryEntryOut, MemoryOut
from app.services import memory as memory_service

router = APIRouter(prefix="/api/memory", tags=["vendor memory"])


@router.get("", response_model=MemoryOut)
def read_memory(
    limit: int = Query(default=500, ge=1, le=5000),
    db: Session = Depends(get_db),
) -> MemoryOut:
    coa = get_coa()
    entries = memory_service.all_entries(db, limit=limit)

    return MemoryOut(
        entries=[
            MemoryEntryOut(
                vendor_norm=e.vendor_norm,
                account_code=e.account_code,
                account_name=coa.name_for(e.account_code),
                source=e.source,
                hit_count=e.hit_count,
                updated_at=e.updated_at,
                example_vendor_raw=e.example_vendor_raw,
            )
            for e in entries
        ],
        total=memory_service.count(db),
    )
