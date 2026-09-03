"""Vendor memory — spec 11 section 4 F4.

    "(vendor_normalized -> account_code, source[human|llm-confirmed], hit_count);
     memory hits bypass the LLM entirely: the cost curve VISIBLY bends month over month"

Two ways a mapping gets written:

* **human** — a reviewer overrode a suggestion. The strongest signal available, and the one
  that makes spec 11 US3 work: the same vendor next month is auto-categorized and marked
  "learned".
* **llm-confirmed** — the model answered at or above the auto-apply threshold, so the answer
  was trusted enough to post without a human. Promoting those is what actually bends the cost
  curve; if only overrides were remembered, memory would stay nearly empty and the whole
  "gets cheaper every month" claim would be theatre.

A human mapping is never overwritten by the model. That precedence is the point: once a person
has told us the answer, no amount of model confidence outranks them.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.logging import get_logger
from app.models import MemorySource, VendorMemory, utcnow

log = get_logger("spendsort.memory")


def lookup(db: Session, vendor_norm: str) -> VendorMemory | None:
    if not vendor_norm:
        return None
    return db.get(VendorMemory, vendor_norm)


def record_hit(db: Session, entry: VendorMemory) -> VendorMemory:
    """Count a hit. Drives the Memory screen and the memory-hit-rate metric."""
    entry.hit_count += 1
    entry.updated_at = utcnow()
    db.add(entry)
    db.flush()
    return entry


def remember(
    db: Session,
    *,
    vendor_norm: str,
    account_code: str,
    source: MemorySource,
    example_vendor_raw: str | None = None,
) -> VendorMemory | None:
    """Write or update a mapping. Returns the entry, or None if nothing was written.

    Precedence: a human mapping wins. An `llm-confirmed` write will not overwrite one, because
    a person has already answered this question.
    """
    if not vendor_norm or not account_code:
        return None

    existing = db.get(VendorMemory, vendor_norm)

    if existing is None:
        entry = VendorMemory(
            vendor_norm=vendor_norm,
            account_code=account_code,
            source=source.value,
            hit_count=0,
            example_vendor_raw=example_vendor_raw,
        )
        db.add(entry)
        db.flush()
        log.info(
            "memory learned",
            extra={"context": {"vendor_norm": vendor_norm, "account": account_code, "source": source.value}},
        )
        return entry

    if existing.source == MemorySource.HUMAN and source != MemorySource.HUMAN:
        # A model does not get to overrule a person.
        return existing

    changed = existing.account_code != account_code or existing.source != source.value
    existing.account_code = account_code
    existing.source = source.value
    if example_vendor_raw:
        existing.example_vendor_raw = example_vendor_raw
    existing.updated_at = utcnow()
    db.add(existing)
    db.flush()

    if changed:
        log.info(
            "memory updated",
            extra={"context": {"vendor_norm": vendor_norm, "account": account_code, "source": source.value}},
        )
    return existing


def all_entries(db: Session, *, limit: int | None = None) -> list[VendorMemory]:
    """Most-used first: the Memory screen should open on what is carrying the load."""
    stmt = select(VendorMemory).order_by(VendorMemory.hit_count.desc(), VendorMemory.vendor_norm)
    if limit:
        stmt = stmt.limit(limit)
    return list(db.scalars(stmt))


def count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(VendorMemory)) or 0
