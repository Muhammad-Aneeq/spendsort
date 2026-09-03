"""The four nodes, and nothing else.

spec 11 section 4 F2:

    normalize_vendor -> check_memory (learned mappings first, zero LLM cost)
    -> llm_categorize (structured output: {account_code, confidence, reason})
    -> route (auto >= threshold | queue)

Exactly four (PLAN.md D5). The memory bypass is a conditional **edge** out of `check_memory`,
not a fifth node, which is what keeps the count honest while still skipping the LLM entirely.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

from app.agent.llm import Categorizer
from app.agent.state import CategorizeState
from app.coa import ChartOfAccounts
from app.costs import cost_usd
from app.logging import get_logger
from app.models import CategorizationSource, MemorySource, TxnStatus
from app.normalize import normalize_vendor as normalize
from app.services import memory as memory_service

log = get_logger("spendsort.agent")

# Confidence forced onto any answer we refuse to trust, so `route` sends it to the queue.
# Not 0.0: the suggestion is still shown to the reviewer as a starting point, and a hard zero
# would misrepresent "we cannot verify this" as "this is definitely wrong".
FORCED_LOW_CONFIDENCE = 0.0


# --- node 1 ------------------------------------------------------------------


def normalize_vendor(state: CategorizeState) -> CategorizeState:
    """Collapse the bank descriptor to the key memory is stored under."""
    vendor_norm = normalize(state.get("vendor_raw", ""))
    return {
        "vendor_norm": vendor_norm,
        "trace": [f"normalize_vendor: {state.get('vendor_raw', '')!r} -> {vendor_norm!r}"],
    }


# --- node 2 ------------------------------------------------------------------


def make_check_memory(db: Session) -> Callable[[CategorizeState], CategorizeState]:
    """spec 11 section 4 F4: "memory hits bypass the LLM entirely"."""

    def check_memory(state: CategorizeState) -> CategorizeState:
        vendor_norm = state.get("vendor_norm", "")
        entry = memory_service.lookup(db, vendor_norm)

        if entry is None:
            return {"memory_hit": False, "trace": [f"check_memory: miss for {vendor_norm!r}"]}

        # A hit is worth recording as a hit: hit_count drives the Memory screen and is part of
        # the evidence that the agent is getting cheaper.
        memory_service.record_hit(db, entry)
        learned = entry.source == MemorySource.HUMAN

        return {
            "memory_hit": True,
            "learned": learned,
            "account_code": entry.account_code,
            "confidence": 1.0,  # a stored mapping is not a guess
            "reason": ("learned from a human correction" if learned else "previously confirmed mapping"),
            "source": CategorizationSource.MEMORY.value,
            "coa_valid": True,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "cost_usd": 0.0,
            "trace": [
                f"check_memory: HIT {vendor_norm!r} -> {entry.account_code} "
                f"({entry.source}, hits={entry.hit_count}); LLM skipped"
            ],
        }

    return check_memory


# --- node 3 ------------------------------------------------------------------


def make_llm_categorize(
    categorizer: Categorizer,
    coa: ChartOfAccounts,
) -> Callable[[CategorizeState], CategorizeState]:
    """spec 11 section 8: structured output, and the CoA gate applied in code."""

    def llm_categorize(state: CategorizeState) -> CategorizeState:
        from app.costs import estimated_call_cost_usd

        # The cost cap (spec 11 section 11) is checked BEFORE the call, because afterwards the
        # money is already spent. Note this only ever blocks the LLM: a memory hit never
        # reaches this node, so a capped run keeps categorizing known vendors for free.
        remaining = state.get("budget_remaining_usd", 0.0)
        if remaining < estimated_call_cost_usd():
            return {
                "account_code": "",
                "confidence": FORCED_LOW_CONFIDENCE,
                "reason": "cost cap reached for this run; queued for review",
                "source": CategorizationSource.LLM.value,
                "coa_valid": False,
                "cost_capped": True,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "cost_usd": 0.0,
                "trace": [f"llm_categorize: SKIPPED, cost cap reached (${remaining:.4f} left)"],
            }

        result = categorizer.categorize(
            coa_block=state.get("coa_block", ""),
            vendor_raw=state.get("vendor_raw", ""),
            vendor_norm=state.get("vendor_norm", ""),
            amount=state.get("amount", 0.0),
            currency=state.get("currency", "USD"),
            date=state.get("date", ""),
            memo=state.get("memo"),
        )

        suggestion = result.suggestion
        spent = cost_usd(result.prompt_tokens, result.completion_tokens)

        # THE GATE (spec 11 section 8): "account_code must be in the CoA (validated in code;
        # out-of-CoA = forced low confidence + queue)". The model's own confidence is not
        # evidence that the code exists, so membership is decided here and nowhere else.
        coa_valid = coa.is_valid(suggestion.account_code)
        if not coa_valid:
            return {
                "account_code": suggestion.account_code,
                "confidence": FORCED_LOW_CONFIDENCE,
                "reason": f"account {suggestion.account_code or '(blank)'} is not in the chart of accounts",
                "source": CategorizationSource.LLM.value,
                "coa_valid": False,
                "prompt_tokens": result.prompt_tokens,
                "completion_tokens": result.completion_tokens,
                "cost_usd": spent,
                "trace": [
                    f"llm_categorize: {suggestion.account_code!r} @ {suggestion.confidence:.2f} "
                    f"REJECTED — not in CoA; confidence forced to {FORCED_LOW_CONFIDENCE}"
                ],
            }

        return {
            "account_code": suggestion.account_code,
            "confidence": suggestion.confidence,
            "reason": suggestion.reason,
            "source": CategorizationSource.LLM.value,
            "coa_valid": True,
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "cost_usd": spent,
            "trace": [
                f"llm_categorize: {suggestion.account_code} @ {suggestion.confidence:.2f} "
                f"(${spent:.6f}) — {suggestion.reason}"
            ],
        }

    return llm_categorize


# --- node 4 ------------------------------------------------------------------


def route(state: CategorizeState) -> CategorizeState:
    """spec 11 section 4 F2: "route (auto >= threshold | queue)".

    The whole product is this comparison. Everything above the line is trusted without a
    human; everything else waits for one.
    """
    threshold = state.get("auto_threshold", 1.0)
    confidence = state.get("confidence", 0.0)
    coa_valid = state.get("coa_valid", False)

    auto = coa_valid and confidence >= threshold
    status = TxnStatus.AUTO.value if auto else TxnStatus.QUEUED.value

    return {
        "status": status,
        "trace": [
            f"route: confidence {confidence:.2f} vs threshold {threshold:.2f}"
            f"{'' if coa_valid else ' (invalid account)'} -> {status}"
        ],
    }


# --- the conditional edge ----------------------------------------------------


def memory_branch(state: CategorizeState) -> str:
    """Where to go after `check_memory`.

    A hit goes straight to `route`, skipping `llm_categorize` — this edge *is* the
    "zero LLM cost" promise of spec 11 section 4 F2, and the reason the cost curve bends.
    """
    return "route" if state.get("memory_hit") else "llm_categorize"
