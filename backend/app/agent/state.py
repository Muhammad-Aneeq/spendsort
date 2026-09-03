"""State carried through the categorization graph.

One transaction per invocation. Everything the four nodes need to read or write lives here,
including the audit trail (`trace`) and the run's remaining budget.
"""

from __future__ import annotations

from typing import Annotated, TypedDict


def _append(existing: list[str] | None, incoming: list[str] | None) -> list[str]:
    """Reducer so each node can append to the trace without clobbering earlier entries."""
    return (existing or []) + (incoming or [])


class CategorizeState(TypedDict, total=False):
    # --- input ---------------------------------------------------------
    txn_id: int
    vendor_raw: str
    amount: float
    currency: str
    date: str
    memo: str | None
    coa_block: str
    auto_threshold: float
    # Remaining run budget in USD. Checked before an LLM call, never after (spec 11 s11).
    budget_remaining_usd: float

    # --- set by normalize_vendor ---------------------------------------
    vendor_norm: str

    # --- set by check_memory -------------------------------------------
    memory_hit: bool
    # True when the mapping came from a human override — the UI labels this "learned".
    learned: bool

    # --- the decision --------------------------------------------------
    account_code: str
    confidence: float
    reason: str
    source: str  # memory | llm
    coa_valid: bool

    # --- cost ----------------------------------------------------------
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    # True when the cost cap stopped this transaction from reaching the LLM.
    cost_capped: bool

    # --- set by route --------------------------------------------------
    status: str  # auto | queued

    # --- audit ---------------------------------------------------------
    trace: Annotated[list[str], _append]
