"""Token pricing and the per-run cost cap.

spec 11 section 11: "cost cap per run (default $0.25)".

All pricing lives in **one** env-overridable place (PLAN.md D6) so that updating a price is a
config change, never a code change — and so MODEL_COSTS.md can never quietly go stale relative
to what the app actually charges.

⚠️ The figures below are list prices **as written on 2026-09-03** and could not be verified
from the build environment (BLOCKERS.md **B4**). Confirm before quoting them anywhere that
matters. The cap logic does not depend on them being right: it enforces whatever it is told.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.settings import get_settings

# USD per 1M tokens: model -> (input, output). Unverified; see the module docstring.
PRICING_PER_1M: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
}

# Used when the configured model is not in the table. Deliberately the priciest mini-class
# entry rather than zero: an unknown model must not silently make the cost cap unenforceable.
FALLBACK_PER_1M: tuple[float, float] = (0.40, 1.60)

# A categorization prompt is the CoA block plus one transaction line. Measured at roughly
# 700-900 prompt tokens and 30-50 completion tokens with the default 20-account CoA; the
# estimate is rounded up so the cap errs toward stopping early rather than overspending.
ESTIMATED_PROMPT_TOKENS = 1_000
ESTIMATED_COMPLETION_TOKENS = 60


def price_for(model: str) -> tuple[float, float]:
    """(input, output) USD per 1M tokens, honouring env overrides."""
    settings = get_settings()
    if settings.price_input_per_1m is not None and settings.price_output_per_1m is not None:
        return (settings.price_input_per_1m, settings.price_output_per_1m)
    return PRICING_PER_1M.get(model, FALLBACK_PER_1M)


def cost_usd(prompt_tokens: int, completion_tokens: int, model: str | None = None) -> float:
    """Actual cost of one completed call."""
    model = model or get_settings().model
    input_price, output_price = price_for(model)
    return (prompt_tokens / 1_000_000) * input_price + (completion_tokens / 1_000_000) * output_price


def estimated_call_cost_usd(model: str | None = None) -> float:
    """What the *next* call might cost, for a pre-flight cap check.

    The cap has to be decided before the call, since afterwards the money is already spent.
    """
    return cost_usd(ESTIMATED_PROMPT_TOKENS, ESTIMATED_COMPLETION_TOKENS, model)


@dataclass
class CostBudget:
    """A single run's spend, against the spec 11 section 11 cap.

    Memory hits are free, so they are never charged here and never blocked — which is the
    point of the whole design: once the cap is reached the agent keeps working from memory,
    and only new vendors are deferred to the queue.
    """

    cap_usd: float
    spent_usd: float = 0.0
    llm_calls: int = 0
    blocked: int = 0

    @property
    def remaining_usd(self) -> float:
        return max(0.0, self.cap_usd - self.spent_usd)

    def can_afford_a_call(self, model: str | None = None) -> bool:
        return self.remaining_usd >= estimated_call_cost_usd(model)

    def charge(self, prompt_tokens: int, completion_tokens: int, model: str | None = None) -> float:
        amount = cost_usd(prompt_tokens, completion_tokens, model)
        self.spent_usd += amount
        self.llm_calls += 1
        return amount

    def block(self) -> None:
        """Record that a transaction was deferred because the cap was reached."""
        self.blocked += 1

    @property
    def exhausted(self) -> bool:
        return not self.can_afford_a_call()


def budget_for_run(cap_usd: float | None = None) -> CostBudget:
    return CostBudget(cap_usd=cap_usd if cap_usd is not None else get_settings().cost_cap_usd_per_run)
