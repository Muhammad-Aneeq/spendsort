"""CSV export — spec 11 section 4 F6.

    "Export: categorized CSV with per-line {account, confidence, source, reason}."

Two hardening decisions, both because the reader of this file is a bookkeeper opening it in
Excel:

1. **Formula injection is neutralised here**, not at intake (spec 11 section 11). A descriptor
   like `=cmd|' /C calc'!A0` is stored verbatim on the way in because it is the audit record;
   it is on the way *out* that a spreadsheet would evaluate it. Text cells beginning with
   `= + - @` or a control character are prefixed with an apostrophe. Numeric columns are
   formatted by us, so a negative amount is never mistaken for a formula.
2. **UTF-8 with BOM** (`utf-8-sig`). Without it Excel on Windows reads the file as the local
   codepage and mangles the em-dash in account names like "Travel — Airfare" (PLAN.md D15).
"""

from __future__ import annotations

import csv
from io import StringIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.coa import get_coa
from app.models import MemorySource, Transaction, TxnStatus, VendorMemory

# The four fields spec 11 section 4 F6 requires, plus the context that makes a line auditable
# on its own: what was uploaded, what state it is in, and what it cost.
COLUMNS: tuple[str, ...] = (
    "date",
    "vendor_raw",
    "vendor_norm",
    "amount",
    "currency",
    "account",  # F6
    "account_name",
    "confidence",  # F6
    "source",  # F6
    "reason",  # F6
    "status",
    "learned",
    "coa_valid",
    "cost_usd",
    "memo",
)

_DANGEROUS_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")


def safe_text(value: str | None) -> str:
    """Neutralise a spreadsheet formula without losing the original text.

    The apostrophe prefix is what Excel and LibreOffice both treat as "this is literal text",
    so the reader still sees the descriptor exactly as the bank sent it.
    """
    if value is None:
        return ""
    text = str(value)
    if text.startswith(_DANGEROUS_PREFIXES):
        return "'" + text
    return text


def _rows(db: Session) -> list[dict[str, object]]:
    coa = get_coa()
    memory = {m.vendor_norm: m for m in db.scalars(select(VendorMemory))}

    txns = list(db.scalars(select(Transaction).order_by(Transaction.date, Transaction.id)))
    out: list[dict[str, object]] = []

    for txn in txns:
        decision = txn.latest_categorization
        account = txn.final_account or (decision.account_code if decision else "")

        entry: VendorMemory | None = memory.get(txn.vendor_norm)
        learned = bool(
            decision and decision.source == "memory" and entry is not None and entry.source == MemorySource.HUMAN.value
        )

        out.append(
            {
                "date": txn.date.isoformat(),
                "vendor_raw": safe_text(txn.vendor_raw),
                "vendor_norm": safe_text(txn.vendor_norm),
                # Numbers are formatted by us, so "-12.34" is never read as a formula.
                "amount": f"{txn.amount:.2f}",
                "currency": txn.currency,
                "account": account,
                "account_name": safe_text(coa.name_for(account) if account else ""),
                "confidence": f"{decision.confidence:.3f}" if decision else "",
                "source": decision.source if decision else "",
                "reason": safe_text(decision.reason if decision else ""),
                "status": txn.status,
                "learned": "yes" if learned else "no",
                "coa_valid": ("yes" if decision.coa_valid else "no") if decision else "",
                "cost_usd": f"{decision.cost_usd:.6f}" if decision else "",
                "memo": safe_text(txn.memo),
            }
        )
    return out


def export_csv(db: Session, *, only_decided: bool = False) -> str:
    """Render the categorized ledger.

    `only_decided` drops rows still awaiting a human — useful when the file is going somewhere
    that would treat every line as posted.
    """
    rows = _rows(db)
    if only_decided:
        decided = {TxnStatus.AUTO.value, TxnStatus.RESOLVED.value}
        rows = [r for r in rows if r["status"] in decided]

    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(COLUMNS), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def export_bytes(db: Session, *, only_decided: bool = False) -> bytes:
    """UTF-8 **with BOM**, so Excel on Windows renders the em-dash accounts correctly."""
    return export_csv(db, only_decided=only_decided).encode("utf-8-sig")
