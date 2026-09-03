"""Overrides teach the agent — spec 11 US3 and section 4 F3/F4.

    US3: "same vendor next month -> auto-categorized from memory, marked 'learned'"
    F3:  "override writes to vendor_memory with the human as source"
    F4:  "memory hits bypass the LLM entirely"

This is the loop the whole product exists for, so it is tested end to end through the API:
upload -> run -> queue -> override -> re-upload -> re-run -> auto + learned + free.

The definition-of-done phrases it as "override learned and proven on re-run", and
`test_the_full_learning_loop_through_the_api` is that sentence as an executable test.
"""

from __future__ import annotations

from datetime import date

from app.agent.llm import CategorySuggestion, LlmResult
from app.models import (
    Categorization,
    MemorySource,
    Transaction,
    TxnStatus,
    VendorMemory,
)
from app.services import memory as memory_service
from app.services.runner import categorize_pending
from tests.conftest import csv_bytes


class UnsureCategorizer:
    """Answers below any sane threshold, so every row lands in the review queue."""

    name = "unsure"

    def __init__(self, account_code: str = "6060", confidence: float = 0.40) -> None:
        self.calls = 0
        self.account_code = account_code
        self.confidence = confidence

    def categorize(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls += 1
        return LlmResult(
            suggestion=CategorySuggestion(
                account_code=self.account_code, confidence=self.confidence, reason="not sure"
            ),
            prompt_tokens=1000,
            completion_tokens=60,
        )


def add_txn(db, vendor_raw: str, *, day: int = 1, amount: float = 50.0) -> Transaction:
    txn = Transaction(
        date=date(2026, 1, day),
        amount=amount,
        currency="USD",
        vendor_raw=vendor_raw,
        vendor_norm="",  # the graph fills this in
        status=TxnStatus.PENDING,
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


# --- the service-level loop --------------------------------------------------


def test_an_override_writes_memory_with_the_human_as_source(db, client) -> None:
    txn = add_txn(db, "AMTRAK 4K2J91")
    categorize_pending(db, categorizer=UnsureCategorizer())

    resp = client.post(f"/api/txns/{txn.id}/verdict", json={"action": "override", "final_account": "6150"})
    assert resp.status_code == 201, resp.text
    assert resp.json()["memory_written"] is True

    entry = db.get(VendorMemory, "AMTRAK")
    assert entry is not None
    assert entry.account_code == "6150"
    assert entry.source == MemorySource.HUMAN.value
    assert entry.learned_from_human is True


def test_the_next_occurrence_is_auto_categorized_from_memory_and_free(db, client) -> None:
    """The payoff. After one correction, the same vendor never costs money again."""
    first = add_txn(db, "AMTRAK 4K2J91", day=1)
    categorize_pending(db, categorizer=UnsureCategorizer())
    client.post(f"/api/txns/{first.id}/verdict", json={"action": "override", "final_account": "6150"})

    # Next month, same vendor, a different descriptor spelling.
    second = add_txn(db, "AMTRAK 9M2K40", day=15)
    unsure = UnsureCategorizer()
    run = categorize_pending(db, categorizer=unsure)

    db.refresh(second)
    assert unsure.calls == 0, "the LLM was called for a vendor a human had already taught us"
    assert second.status == TxnStatus.AUTO.value
    assert run.memory_hits == 1
    assert run.cost_usd == 0.0

    decision = db.query(Categorization).filter_by(txn_id=second.id).one()
    assert decision.source == "memory"
    assert decision.account_code == "6150"
    assert decision.cost_usd == 0.0
    assert "learned" in decision.reason.lower()


def test_a_human_mapping_is_not_overwritten_by_the_model(db) -> None:
    """Precedence matters: once a person has answered, no amount of model confidence
    outranks them."""
    memory_service.remember(db, vendor_norm="COSTCO", account_code="6050", source=MemorySource.HUMAN)
    db.commit()

    memory_service.remember(db, vendor_norm="COSTCO", account_code="6060", source=MemorySource.LLM_CONFIRMED)
    db.commit()

    entry = db.get(VendorMemory, "COSTCO")
    assert entry is not None
    assert (entry.account_code, entry.source) == ("6050", MemorySource.HUMAN.value)


def test_a_human_can_correct_their_own_earlier_correction(db) -> None:
    """People change their minds, and the newest human answer should win."""
    memory_service.remember(db, vendor_norm="UBER", account_code="6150", source=MemorySource.HUMAN)
    memory_service.remember(db, vendor_norm="UBER", account_code="6050", source=MemorySource.HUMAN)
    db.commit()

    entry = db.get(VendorMemory, "UBER")
    assert entry is not None
    assert entry.account_code == "6050"


def test_an_auto_applied_llm_answer_is_promoted_to_memory(db) -> None:
    """This is what actually bends the cost curve. If only overrides were remembered, memory
    would stay nearly empty and "gets cheaper every month" would be theatre."""

    class Confident(UnsureCategorizer):
        def __init__(self) -> None:
            super().__init__(account_code="6030", confidence=0.95)

    add_txn(db, "FIGMA INC")
    categorize_pending(db, categorizer=Confident())

    entry = db.get(VendorMemory, "FIGMA")
    assert entry is not None
    assert entry.source == MemorySource.LLM_CONFIRMED.value


def test_a_queued_guess_is_not_promoted_to_memory(db) -> None:
    """An answer the gate refused to trust has not earned a place in memory. Promoting it
    would launder a low-confidence guess into a permanent fact."""
    add_txn(db, "SOMETHING UNRECOGNISABLE")
    categorize_pending(db, categorizer=UnsureCategorizer(confidence=0.40))

    assert memory_service.count(db) == 0


def test_an_out_of_coa_answer_is_never_promoted(db) -> None:
    add_txn(db, "MYSTERY VENDOR")
    categorize_pending(db, categorizer=UnsureCategorizer(account_code="9999", confidence=0.99))

    assert memory_service.count(db) == 0


# --- the accept path ---------------------------------------------------------


def test_accepting_a_suggestion_resolves_it(db, client) -> None:
    txn = add_txn(db, "STAPLES #1234")
    categorize_pending(db, categorizer=UnsureCategorizer(account_code="6060", confidence=0.40))

    resp = client.post(f"/api/txns/{txn.id}/verdict", json={"action": "accept"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["final_account"] == "6060"
    assert body["final_account_name"] == "Office Supplies"

    db.refresh(txn)
    assert txn.status == TxnStatus.RESOLVED.value


def test_an_override_needs_an_account(db, client) -> None:
    txn = add_txn(db, "STAPLES #1234")
    categorize_pending(db, categorizer=UnsureCategorizer())

    resp = client.post(f"/api/txns/{txn.id}/verdict", json={"action": "override"})
    assert resp.status_code == 422
    assert "final_account" in resp.json()["detail"]


def test_an_override_to_a_nonexistent_account_is_refused(db, client) -> None:
    txn = add_txn(db, "STAPLES #1234")
    categorize_pending(db, categorizer=UnsureCategorizer())

    resp = client.post(f"/api/txns/{txn.id}/verdict", json={"action": "override", "final_account": "9999"})
    assert resp.status_code == 422
    assert db.get(VendorMemory, "STAPLES") is None, "a bad override must not be learned"


def test_accepting_an_out_of_coa_suggestion_is_refused(db, client) -> None:
    """The queue is the safety net. It must not become the one path a bad code slips through."""
    txn = add_txn(db, "MYSTERY VENDOR")
    categorize_pending(db, categorizer=UnsureCategorizer(account_code="9999", confidence=0.99))

    resp = client.post(f"/api/txns/{txn.id}/verdict", json={"action": "accept"})
    assert resp.status_code == 422
    assert "not in the chart of accounts" in resp.json()["detail"]


def test_a_verdict_on_an_unknown_transaction_is_404(client) -> None:
    resp = client.post("/api/txns/99999/verdict", json={"action": "accept"})
    assert resp.status_code == 404


# --- the definition of done, as a test ---------------------------------------


def test_the_full_learning_loop_through_the_api(db, client) -> None:
    """ "override learned and proven on re-run" — the Definition of Done, executable.

    Runs entirely through HTTP, in mock mode, so it also proves the demo path works.
    """
    # 1. Upload a month containing a vendor the mock is deliberately unsure about (Amazon:
    #    office supplies or computer equipment?).
    month_1 = csv_bytes(["2026-01-05,120.00,USD,AMZN Mktp US*Y7D8K6,INV-1"])
    assert client.post("/api/ingest/csv", files={"file": ("m1.csv", month_1, "text/csv")}).status_code == 201

    # 2. Run. The mock's confidence on Amazon is below the threshold, so it queues.
    run_1 = client.post("/api/runs").json()
    assert run_1["txn_count"] == 1
    assert run_1["memory_hit_rate"] == 0.0
    assert run_1["cost_usd"] > 0.0, "a cold run should cost something"

    txn = db.query(Transaction).one()
    assert txn.status == TxnStatus.QUEUED.value

    # 3. A human overrides it to Computer Equipment.
    verdict = client.post(f"/api/txns/{txn.id}/verdict", json={"action": "override", "final_account": "6020"}).json()
    assert verdict["memory_written"] is True

    # 4. Next month, the same vendor arrives under a different descriptor.
    month_2 = csv_bytes(["2026-02-07,88.40,USD,AMZN MKTP US SEATTLE WA,INV-2"])
    assert client.post("/api/ingest/csv", files={"file": ("m2.csv", month_2, "text/csv")}).status_code == 201

    run_2 = client.post("/api/runs").json()

    # 5. It is auto-applied from memory, correctly, marked learned, and for free.
    assert run_2["txn_count"] == 1
    assert run_2["memory_hit_rate"] == 1.0
    assert run_2["auto_rate"] == 1.0
    assert run_2["cost_usd"] == 0.0
    assert run_2["llm_calls"] == 0

    second = db.query(Transaction).order_by(Transaction.id.desc()).first()
    assert second is not None
    assert second.status == TxnStatus.AUTO.value

    decision = db.query(Categorization).filter_by(txn_id=second.id).one()
    assert (decision.account_code, decision.source) == ("6020", "memory")
    assert "learned" in decision.reason.lower()

    # 6. And the bend is visible in the run history: cost down, memory-hit rate up.
    assert run_2["cost_usd"] < run_1["cost_usd"]
    assert run_2["memory_hit_rate"] > run_1["memory_hit_rate"]
