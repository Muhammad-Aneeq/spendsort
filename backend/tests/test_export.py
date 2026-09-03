"""CSV export — spec 11 section 4 F6.

    "Export: categorized CSV with per-line {account, confidence, source, reason}."

Plus the hardening that matters because the reader is a bookkeeper in Excel: formula injection
neutralised on the way out, and a BOM so em-dash account names survive.
"""

from __future__ import annotations

import csv
import io
from datetime import date

from app.agent.llm import CategorySuggestion, LlmResult
from app.models import MemorySource, Transaction, TxnStatus
from app.services import memory as memory_service
from app.services.export import COLUMNS, export_bytes, export_csv, safe_text
from app.services.runner import categorize_pending


class Confident:
    name = "confident"

    def __init__(self, account_code: str = "6060", confidence: float = 0.95) -> None:
        self.account_code = account_code
        self.confidence = confidence

    def categorize(self, **kwargs):  # type: ignore[no-untyped-def]
        return LlmResult(
            suggestion=CategorySuggestion(
                account_code=self.account_code,
                confidence=self.confidence,
                reason="matched vendor name",
            ),
            prompt_tokens=1000,
            completion_tokens=60,
        )


def add_txn(db, vendor_raw: str, *, amount: float = 42.0, memo: str | None = "INV-1") -> Transaction:
    txn = Transaction(
        date=date(2026, 1, 15),
        amount=amount,
        currency="USD",
        vendor_raw=vendor_raw,
        vendor_norm="",
        status=TxnStatus.PENDING,
        memo=memo,
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


def parse(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text)))


# --- the four required fields ------------------------------------------------


def test_every_line_carries_account_confidence_source_and_reason(db) -> None:
    add_txn(db, "STAPLES #1234")
    categorize_pending(db, categorizer=Confident())

    rows = parse(export_csv(db))
    assert len(rows) == 1

    row = rows[0]
    # spec 11 section 4 F6, exactly.
    assert row["account"] == "6060"
    assert float(row["confidence"]) == 0.95
    assert row["source"] == "llm"
    assert row["reason"] == "matched vendor name"


def test_the_header_declares_every_column(db) -> None:
    add_txn(db, "STAPLES #1234")
    categorize_pending(db, categorizer=Confident())

    header = export_csv(db).splitlines()[0].split(",")
    assert header == list(COLUMNS)
    for required in ("account", "confidence", "source", "reason"):
        assert required in header


def test_the_account_name_is_included_for_readability(db) -> None:
    """A bookkeeper should not have to memorise the chart of accounts to read the export."""
    add_txn(db, "STAPLES #1234")
    categorize_pending(db, categorizer=Confident())

    assert parse(export_csv(db))[0]["account_name"] == "Office Supplies"


def test_a_learned_line_is_marked_learned(db) -> None:
    """spec 11 US3 — the export has to show which lines came from a human's correction."""
    memory_service.remember(db, vendor_norm="AMTRAK", account_code="6150", source=MemorySource.HUMAN)
    db.commit()

    add_txn(db, "AMTRAK TICKET 4672")
    # Different key, so this one is answered by the LLM rather than memory.
    add_txn(db, "Amtrak")
    categorize_pending(db, categorizer=Confident(account_code="6150"))

    rows = {r["vendor_norm"]: r for r in parse(export_csv(db))}
    assert rows["AMTRAK"]["learned"] == "yes"
    assert rows["AMTRAK"]["source"] == "memory"
    assert rows["AMTRAK TICKET"]["learned"] == "no"


def test_a_queued_line_still_appears_with_its_suggestion(db) -> None:
    """Queued rows belong in the export: leaving them out would make the file look complete
    when a fifth of the month is still unreviewed."""
    add_txn(db, "SOMETHING ODD")
    categorize_pending(db, categorizer=Confident(confidence=0.30))

    row = parse(export_csv(db))[0]
    assert row["status"] == "queued"
    assert row["account"] == "6060"  # the suggestion is shown
    assert float(row["confidence"]) == 0.30


def test_only_decided_excludes_the_queue(db) -> None:
    add_txn(db, "STAPLES #1")
    add_txn(db, "MYSTERY THING")
    categorize_pending(db, categorizer=Confident())
    # Force one into the queue.
    txn = db.query(Transaction).filter(Transaction.vendor_raw == "MYSTERY THING").one()
    txn.status = TxnStatus.QUEUED
    db.commit()

    assert len(parse(export_csv(db))) == 2
    assert len(parse(export_csv(db, only_decided=True))) == 1


def test_an_overridden_line_exports_the_humans_account(db, client) -> None:
    """The ledger must reflect the human's decision, not the model's rejected guess."""
    txn = add_txn(db, "AMZN Mktp US*Y7D8K6")
    categorize_pending(db, categorizer=Confident(account_code="6060", confidence=0.40))

    client.post(f"/api/txns/{txn.id}/verdict", json={"action": "override", "final_account": "6020"})

    # The request committed through its own session, so this fixture session is holding a
    # stale copy. Production gives every request a fresh session; only the test needs this.
    db.expire_all()

    row = parse(export_csv(db))[0]
    assert row["account"] == "6020"
    assert row["status"] == "resolved"


# --- hardening ---------------------------------------------------------------


def test_formula_injection_is_neutralised_on_export(db) -> None:
    """spec 11 section 11. The descriptor is stored verbatim (it is the audit record); it is
    HERE, on the way into a spreadsheet, that it must stop being executable."""
    add_txn(db, "=cmd|' /C calc'!A0")
    categorize_pending(db, categorizer=Confident())

    text = export_csv(db)
    row = parse(text)[0]

    assert row["vendor_raw"].startswith("'="), "a formula reached the file unescaped"
    assert "cmd|" in row["vendor_raw"], "the original text must still be readable"


def test_every_dangerous_prefix_is_neutralised() -> None:
    for prefix in ("=", "+", "-", "@", "\t", "\r"):
        assert safe_text(f"{prefix}danger").startswith("'")


def test_ordinary_text_is_left_alone() -> None:
    assert safe_text("Amazon") == "Amazon"
    assert safe_text("") == ""
    assert safe_text(None) == ""


def test_a_negative_amount_is_not_treated_as_a_formula(db) -> None:
    """Amounts are formatted by us, so a refund must not acquire a stray apostrophe."""
    add_txn(db, "REFUND FROM STAPLES", amount=-45.50)
    categorize_pending(db, categorizer=Confident())

    row = parse(export_csv(db))[0]
    assert row["amount"] == "-45.50"
    assert float(row["amount"]) == -45.50


def test_the_download_carries_a_bom_for_excel(db) -> None:
    """Without the BOM, Excel on Windows reads the file as the local codepage and mangles
    "Travel — Airfare" (PLAN.md D15)."""
    add_txn(db, "UNITED AIRLINES 9K2M40")
    categorize_pending(db, categorizer=Confident(account_code="6130"))

    payload = export_bytes(db)
    assert payload.startswith(b"\xef\xbb\xbf")

    text = payload.decode("utf-8-sig")
    assert "Travel — Airfare" in text
    assert "â€”" not in text


def test_the_export_is_ordered_by_date(db) -> None:
    for day in (20, 5, 12):
        db.add(
            Transaction(
                date=date(2026, 1, day),
                amount=10.0,
                currency="USD",
                vendor_raw=f"VENDOR {day}",
                vendor_norm=f"VENDOR {day}",
                status=TxnStatus.PENDING,
            )
        )
    db.commit()
    categorize_pending(db, categorizer=Confident())

    dates = [r["date"] for r in parse(export_csv(db))]
    assert dates == sorted(dates)


def test_an_empty_ledger_exports_a_header_only(db) -> None:
    """The button should not error before the first upload."""
    text = export_csv(db)
    assert text.strip() == ",".join(COLUMNS)


# --- the endpoint ------------------------------------------------------------


def test_the_export_endpoint_serves_a_download(db, client) -> None:
    add_txn(db, "STAPLES #1234")
    categorize_pending(db, categorizer=Confident())

    resp = client.get("/api/export")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "attachment" in resp.headers["content-disposition"]
    assert "spendsort_categorized.csv" in resp.headers["content-disposition"]
    assert resp.content.startswith(b"\xef\xbb\xbf")

    rows = parse(resp.content.decode("utf-8-sig"))
    assert rows[0]["account"] == "6060"


def test_the_export_endpoint_honours_only_decided(db, client) -> None:
    add_txn(db, "STAPLES #1")
    categorize_pending(db, categorizer=Confident(confidence=0.20))

    assert len(parse(client.get("/api/export").content.decode("utf-8-sig"))) == 1
    only = client.get("/api/export", params={"only_decided": "true"})
    assert len(parse(only.content.decode("utf-8-sig"))) == 0
