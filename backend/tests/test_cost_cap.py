"""The per-run cost cap — spec 11 section 11: "cost cap per run (default $0.25)".

Two things must be true, and the second is the one that is easy to get wrong:

1. The cap actually stops spending.
2. The transactions it stopped are **queued, not dropped** (PLAN.md D7). Silently leaving rows
   uncategorized would let a capped run report success while quietly losing work.
"""

from __future__ import annotations

from app.agent.llm import CategorySuggestion, LlmResult
from app.costs import CostBudget, budget_for_run, cost_usd, estimated_call_cost_usd
from app.models import Categorization, MemorySource, Transaction, TxnStatus
from app.services import memory as memory_service
from app.services.runner import categorize_pending
from app.settings import get_settings


class AlwaysConfident:
    name = "always-confident"

    def __init__(self) -> None:
        self.calls = 0

    def categorize(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls += 1
        return LlmResult(
            suggestion=CategorySuggestion(account_code="6060", confidence=0.95, reason="stub"),
            prompt_tokens=1000,
            completion_tokens=60,
        )


def add_txns(db, count: int, *, vendor_prefix: str = "UNIQUE VENDOR") -> None:
    from datetime import date

    for i in range(count):
        db.add(
            Transaction(
                date=date(2026, 1, 1 + (i % 28)),
                amount=10.0 + i,
                currency="USD",
                # Distinct vendors, so nothing is answered from memory and every row must pay.
                vendor_raw=f"{vendor_prefix} {chr(65 + i % 26)}{i}",
                vendor_norm=f"{vendor_prefix} {chr(65 + i % 26)}{i}",
                status=TxnStatus.PENDING,
            )
        )
    db.commit()


# --- the default -------------------------------------------------------------


def test_the_default_cap_is_25_cents() -> None:
    assert get_settings().cost_cap_usd_per_run == 0.25
    assert budget_for_run().cap_usd == 0.25


# --- the budget object -------------------------------------------------------


def test_a_budget_stops_affording_calls_once_spent() -> None:
    budget = CostBudget(cap_usd=estimated_call_cost_usd() * 2.5)

    assert budget.can_afford_a_call()
    budget.charge(1000, 60)
    assert budget.can_afford_a_call()
    budget.charge(1000, 60)
    assert not budget.can_afford_a_call()
    assert budget.exhausted


def test_spending_is_tracked_in_dollars() -> None:
    budget = CostBudget(cap_usd=1.0)
    spent = budget.charge(1000, 60)

    assert spent == cost_usd(1000, 60)
    assert budget.spent_usd == spent
    assert budget.llm_calls == 1
    assert budget.remaining_usd == 1.0 - spent


def test_an_unknown_model_does_not_become_free() -> None:
    """A model missing from the pricing table must not silently make the cap unenforceable."""
    assert cost_usd(1000, 60, "some-model-invented-next-year") > 0.0


# --- the cap inside a run ----------------------------------------------------


def test_the_cap_stops_the_llm_partway_through_a_run(db) -> None:
    add_txns(db, 30)
    per_call = estimated_call_cost_usd()
    cap = per_call * 5  # room for roughly five calls out of thirty

    categorizer = AlwaysConfident()
    run = categorize_pending(db, categorizer=categorizer, cost_cap_usd=cap)

    assert run.txn_count == 30
    assert categorizer.calls < 30, "the cap did not stop anything"
    assert run.cost_usd <= cap + 1e-9, f"spent {run.cost_usd} against a cap of {cap}"
    assert run.cost_capped is True
    assert run.capped_txn_count > 0


def test_capped_transactions_are_queued_not_dropped(db) -> None:
    """The important half. Every transaction must end up in a real state."""
    add_txns(db, 25)
    run = categorize_pending(db, categorizer=AlwaysConfident(), cost_cap_usd=estimated_call_cost_usd() * 3)

    statuses = [t.status for t in db.query(Transaction).all()]
    assert len(statuses) == 25
    assert TxnStatus.PENDING.value not in statuses, "capped rows were left pending — work was lost"
    assert all(s in {TxnStatus.AUTO.value, TxnStatus.QUEUED.value} for s in statuses)

    # Every transaction has a decision row, so the audit trail is complete even for the
    # ones that never reached the model.
    assert db.query(Categorization).count() == 25

    # The run's capped count must match the rows that actually say they were capped.
    capped_rows = [c for c in db.query(Categorization).all() if "cost cap" in c.reason]
    assert run.capped_txn_count == len(capped_rows)
    assert run.capped_txn_count + categorize_calls_that_succeeded(db) == 25


def categorize_calls_that_succeeded(db) -> int:
    """Rows that got a real answer, capped or not."""
    return len([c for c in db.query(Categorization).all() if "cost cap" not in c.reason])


def test_a_capped_transaction_says_why_it_was_queued(db) -> None:
    add_txns(db, 10)
    categorize_pending(db, categorizer=AlwaysConfident(), cost_cap_usd=estimated_call_cost_usd() * 2)

    capped = [c for c in db.query(Categorization).all() if "cost cap" in c.reason]
    assert capped, "no row explains the cap to the reviewer"
    for row in capped:
        assert row.confidence == 0.0
        assert row.cost_usd == 0.0
        assert row.coa_valid is False


def test_memory_hits_keep_working_after_the_cap(db) -> None:
    """The best consequence of memory-first: a capped run still categorizes every vendor it
    already knows, for free. Only genuinely new vendors are deferred."""
    from datetime import date

    memory_service.remember(db, vendor_norm="STAPLES", account_code="6060", source=MemorySource.HUMAN)
    for i in range(6):
        db.add(
            Transaction(
                date=date(2026, 1, 1 + i),
                amount=10.0,
                currency="USD",
                vendor_raw="STAPLES",
                vendor_norm="STAPLES",
                status=TxnStatus.PENDING,
            )
        )
    db.commit()

    # A cap of zero: no LLM call can be afforded at all.
    run = categorize_pending(db, categorizer=AlwaysConfident(), cost_cap_usd=1e-9)

    assert run.memory_hits == 6
    assert run.auto_rate == 1.0
    assert run.cost_usd == 0.0
    assert run.cost_capped is False, "nothing needed the LLM, so nothing was capped"
    assert all(t.status == TxnStatus.AUTO.value for t in db.query(Transaction).all())


def test_a_generous_cap_lets_the_whole_run_through(db) -> None:
    add_txns(db, 12)
    categorizer = AlwaysConfident()
    run = categorize_pending(db, categorizer=categorizer, cost_cap_usd=10.0)

    assert categorizer.calls == 12
    assert run.cost_capped is False
    assert run.capped_txn_count == 0


def test_the_run_records_the_cap_it_was_judged_under(db) -> None:
    """A historical run must stay readable after someone changes the setting."""
    add_txns(db, 3)
    run = categorize_pending(db, categorizer=AlwaysConfident(), cost_cap_usd=0.33)
    assert run.cost_cap_usd == 0.33
