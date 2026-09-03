"""The confidence gate, and the CoA gate that overrides it.

spec 11 section 4 F2: "route (auto >= threshold | queue)"
spec 11 section 8:    "account_code must be in the CoA (validated in code;
                       out-of-CoA = forced low confidence + queue)"

The comparison is the entire product, so the boundary is tested exactly — at, just below and
just above the threshold — rather than with comfortable round numbers.
"""

from __future__ import annotations

import pytest

from app.agent.graph import build_graph
from app.agent.llm import CategorySuggestion, LlmResult
from app.agent.nodes import route
from app.coa import get_coa

THRESHOLD = 0.85


class StubCategorizer:
    """Returns whatever the test dictates, so routing is tested in isolation."""

    name = "stub"

    def __init__(self, account_code: str, confidence: float, reason: str = "stub") -> None:
        self._suggestion = CategorySuggestion(account_code=account_code, confidence=confidence, reason=reason)

    def categorize(self, **kwargs):  # type: ignore[no-untyped-def]
        return LlmResult(suggestion=self._suggestion, prompt_tokens=1000, completion_tokens=60)


def run_one(db, account_code: str, confidence: float, *, threshold: float = THRESHOLD):  # type: ignore[no-untyped-def]
    graph = build_graph(db, categorizer=StubCategorizer(account_code, confidence))
    return graph.invoke(
        {
            "txn_id": 1,
            "vendor_raw": "A COMPLETELY UNSEEN VENDOR",
            "amount": 100.0,
            "currency": "USD",
            "date": "2026-01-15",
            "memo": None,
            "coa_block": get_coa().prompt_block(),
            "auto_threshold": threshold,
            "budget_remaining_usd": 1.0,
            "trace": [],
        }
    )


# --- the boundary ------------------------------------------------------------


@pytest.mark.parametrize(
    ("confidence", "expected"),
    [
        (1.00, "auto"),
        (0.9999, "auto"),
        (0.86, "auto"),
        (0.85, "auto"),  # ">= threshold" — the boundary itself auto-applies
        (0.8499, "queued"),
        (0.84, "queued"),
        (0.50, "queued"),
        (0.00, "queued"),
    ],
)
def test_the_threshold_boundary(db, confidence: float, expected: str) -> None:
    assert run_one(db, "6060", confidence)["status"] == expected


def test_the_threshold_is_inclusive(db) -> None:
    """The spec says "auto >= threshold". Exactly at the line must auto-apply, or the
    configured number does not mean what it says."""
    assert run_one(db, "6060", THRESHOLD)["status"] == "auto"


def test_raising_the_threshold_queues_more(db) -> None:
    """The threshold is the one dial a bookkeeper turns to buy precision with their time."""
    assert run_one(db, "6060", 0.90, threshold=0.85)["status"] == "auto"
    assert run_one(db, "6060", 0.90, threshold=0.95)["status"] == "queued"


# --- the CoA gate outranks confidence ----------------------------------------


@pytest.mark.parametrize("bad_code", ["9999", "6001", "", "Office Supplies", "6060-01"])
def test_an_out_of_coa_code_is_queued_however_confident(db, bad_code: str) -> None:
    """spec 11 section 8. A model claiming 0.99 on an account that does not exist is not
    evidence; it is the failure mode this gate exists for."""
    result = run_one(db, bad_code, 0.99)

    assert result["coa_valid"] is False
    assert result["confidence"] == 0.0, "confidence must be FORCED down, not merely noted"
    assert result["status"] == "queued"


def test_the_rejected_code_is_preserved_for_the_reviewer(db) -> None:
    """The reviewer should see what the model actually said — hiding it would make the queue
    harder to trust, not easier."""
    result = run_one(db, "9999", 0.99)

    assert result["account_code"] == "9999"
    assert "not in the chart of accounts" in result["reason"]


def test_a_valid_code_at_high_confidence_is_auto_applied(db) -> None:
    result = run_one(db, "6190", 0.96)
    assert (result["coa_valid"], result["status"]) == (True, "auto")


# --- the route node in isolation ---------------------------------------------


def test_route_refuses_to_auto_apply_an_invalid_account() -> None:
    """Belt and braces: even if some future caller sets a high confidence alongside
    coa_valid=False, route must still queue it."""
    out = route({"confidence": 0.99, "coa_valid": False, "auto_threshold": 0.85})
    assert out["status"] == "queued"


def test_route_defaults_to_queueing_when_it_knows_nothing() -> None:
    """Fail closed. An empty state must not produce an auto-applied entry."""
    assert route({})["status"] == "queued"


def test_route_explains_itself_in_the_trace() -> None:
    """Every decision carries its reasoning (spec 11 section 2 goals)."""
    out = route({"confidence": 0.91, "coa_valid": True, "auto_threshold": 0.85})
    assert "0.91" in out["trace"][0]
    assert "0.85" in out["trace"][0]
    assert "auto" in out["trace"][0]
