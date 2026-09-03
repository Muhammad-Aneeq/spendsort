"""Memory hits must bypass the LLM entirely (spec 11 section 4 F4).

    "memory hits bypass the LLM entirely: the cost curve VISIBLY bends month over month"

The proof technique matters here. Asserting `source == "memory"` would only show what we
*recorded*; it would still pass if the LLM had been called and its answer thrown away — and
we would have paid for it. So these tests inject a categorizer that **fails the test if it is
invoked at all**. That is the only way to demonstrate money was not spent.
"""

from __future__ import annotations

import pytest

from app.agent.graph import build_graph
from app.agent.llm import CategorySuggestion, LlmResult
from app.coa import get_coa
from app.models import MemorySource
from app.services import memory as memory_service


class ExplodingCategorizer:
    """Any call is a test failure: a memory hit must never reach the LLM."""

    name = "exploding"

    def __init__(self) -> None:
        self.calls = 0

    def categorize(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls += 1
        raise AssertionError(
            "llm_categorize was invoked on a memory hit — the bypass is broken and this run cost money"
        )


class CountingCategorizer:
    """Answers, but counts how often it was asked."""

    name = "counting"

    def __init__(self, account_code: str = "6060", confidence: float = 0.95) -> None:
        self.calls = 0
        self.account_code = account_code
        self.confidence = confidence

    def categorize(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls += 1
        return LlmResult(
            suggestion=CategorySuggestion(
                account_code=self.account_code, confidence=self.confidence, reason="counted stub"
            ),
            prompt_tokens=1000,
            completion_tokens=60,
        )


def invoke(graph, vendor_raw: str, *, threshold: float = 0.85, budget: float = 1.0):  # type: ignore[no-untyped-def]
    return graph.invoke(
        {
            "txn_id": 1,
            "vendor_raw": vendor_raw,
            "amount": 42.0,
            "currency": "USD",
            "date": "2026-01-15",
            "memo": None,
            "coa_block": get_coa().prompt_block(),
            "auto_threshold": threshold,
            "budget_remaining_usd": budget,
            "trace": [],
        }
    )


# --- the bypass --------------------------------------------------------------


def test_a_memory_hit_never_calls_the_llm(db) -> None:
    memory_service.remember(db, vendor_norm="STAPLES", account_code="6060", source=MemorySource.LLM_CONFIRMED)
    db.commit()

    exploding = ExplodingCategorizer()
    result = invoke(build_graph(db, categorizer=exploding), "STAPLES #1234")

    assert exploding.calls == 0
    assert result["memory_hit"] is True
    assert result["source"] == "memory"
    assert result["account_code"] == "6060"


def test_a_memory_hit_costs_nothing(db) -> None:
    """ "zero LLM cost" is a monetary claim, so assert on the money."""
    memory_service.remember(db, vendor_norm="FIGMA", account_code="6030", source=MemorySource.HUMAN)
    db.commit()

    result = invoke(build_graph(db, categorizer=ExplodingCategorizer()), "FIGMA INC")

    assert result["cost_usd"] == 0.0
    assert result["prompt_tokens"] == 0
    assert result["completion_tokens"] == 0


def test_a_memory_hit_is_auto_applied(db) -> None:
    """A stored mapping is not a guess, so it should clear any sane threshold."""
    memory_service.remember(db, vendor_norm="SLACK", account_code="6030", source=MemorySource.HUMAN)
    db.commit()

    result = invoke(build_graph(db, categorizer=ExplodingCategorizer()), "Slack.com", threshold=0.99)

    assert result["confidence"] == 1.0
    assert result["status"] == "auto"


def test_a_human_taught_mapping_is_marked_learned(db) -> None:
    """spec 11 US3: "same vendor next month -> auto-categorized from memory, marked 'learned'"."""
    memory_service.remember(db, vendor_norm="AMTRAK", account_code="6130", source=MemorySource.HUMAN)
    db.commit()

    result = invoke(build_graph(db, categorizer=ExplodingCategorizer()), "AMTRAK 4K2J91")

    assert result["learned"] is True
    assert "learned" in result["reason"].lower()


def test_an_llm_confirmed_mapping_is_not_labelled_learned(db) -> None:
    """ "Learned" should mean a person taught us. Labelling the model's own recycled answer
    as learned would overstate what happened."""
    memory_service.remember(db, vendor_norm="VERCEL", account_code="6190", source=MemorySource.LLM_CONFIRMED)
    db.commit()

    result = invoke(build_graph(db, categorizer=ExplodingCategorizer()), "VERCEL.COM")

    assert result["memory_hit"] is True
    assert result["learned"] is False


def test_a_memory_miss_does_call_the_llm(db) -> None:
    counting = CountingCategorizer()
    result = invoke(build_graph(db, categorizer=counting), "SOME BRAND NEW VENDOR")

    assert counting.calls == 1
    assert result["memory_hit"] is False
    assert result["source"] == "llm"
    assert result["cost_usd"] > 0.0


def test_a_hit_increments_the_hit_count(db) -> None:
    """hit_count is the evidence on the Memory screen that a mapping is earning its keep."""
    memory_service.remember(db, vendor_norm="LYFT", account_code="6150", source=MemorySource.HUMAN)
    db.commit()

    graph = build_graph(db, categorizer=ExplodingCategorizer())
    # All three descriptors normalize to the single key "LYFT". Note that "LYFT *RIDE …"
    # would NOT: it normalizes to "LYFT RIDE", a separate key that memory learns separately
    # (documented in app/normalize.py, and the reason this test names its descriptors
    # explicitly rather than assuming one vendor means one key).
    for descriptor in ("Lyft", "LYFT", "LYFT SEATTLE WA"):
        invoke(graph, descriptor)
    db.commit()

    entry = memory_service.lookup(db, "LYFT")
    assert entry is not None
    assert entry.hit_count == 3


def test_the_bypass_still_works_after_the_cost_cap_is_exhausted(db) -> None:
    """The most useful consequence of memory-first: with the budget at zero the agent keeps
    categorizing every vendor it already knows, for free. Only new vendors get deferred."""
    memory_service.remember(db, vendor_norm="GUSTO", account_code="6170", source=MemorySource.HUMAN)
    db.commit()

    result = invoke(build_graph(db, categorizer=ExplodingCategorizer()), "GUSTO 4K2J91", budget=0.0)

    assert result["status"] == "auto"
    assert result["source"] == "memory"
    assert not result.get("cost_capped")


# --- normalization is what makes the hit possible ----------------------------


@pytest.mark.parametrize(
    "descriptor",
    [
        "AMZN Mktp US*Y7D8K6",
        "AMZN MKTP US SEATTLE WA",
        "POS DEBIT AMZN Mktp US*3K9F21",
    ],
)
def test_memory_matches_across_different_descriptors_of_one_vendor(db, descriptor: str) -> None:
    """Memory is keyed on the normalized vendor, so a mapping learned from one descriptor
    has to fire for the vendor's other spellings. This is the whole reason P3 existed."""
    memory_service.remember(db, vendor_norm="AMAZON MARKETPLACE", account_code="6060", source=MemorySource.HUMAN)
    db.commit()

    exploding = ExplodingCategorizer()
    result = invoke(build_graph(db, categorizer=exploding), descriptor)

    assert exploding.calls == 0
    assert result["account_code"] == "6060"
