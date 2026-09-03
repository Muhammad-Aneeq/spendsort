"""The categorization prompt.

spec 11 section 8: "Structured output enforced (Pydantic): account_code must be in the CoA
(validated in code; out-of-CoA = forced low confidence + queue). Reason <= 20 words.
Temperature 0.1."

The prompt asks for calibrated confidence and *invites* the model to be uncertain. That is the
opposite of most prompt advice, and it is deliberate: a queued row costs a bookkeeper ten
seconds, while a confidently-wrong auto-posted row costs a correcting journal entry and a
credibility hit. The gate can only work if low confidence is a respectable answer.
"""

from __future__ import annotations

SYSTEM_PROMPT = """You are a bookkeeping assistant that assigns card and bank transactions to \
a chart of accounts.

You will be given one transaction and the complete chart of accounts. Choose the single best \
account.

Rules:
1. `account_code` MUST be copied exactly from the chart of accounts below. Never invent a code, \
and never return a code that is not listed.
2. `confidence` is your genuine probability, from 0.0 to 1.0, that your chosen account is the \
one a careful bookkeeper would pick.
   - Use 0.90+ only when the vendor is unmistakable (a named airline, a known SaaS subscription).
   - Use 0.50-0.75 when two accounts are genuinely defensible. Amazon could be office supplies \
or computer equipment; Uber could be ground transport or a meal; Airbnb could be lodging or rent.
   - Use below 0.50 when the descriptor is too vague to identify the vendor at all.
   A low score is a correct and useful answer: those transactions go to a human for review, \
which is much cheaper than a wrong entry posted automatically. Do not inflate confidence.
3. `reason` must be at most 20 words, and must cite what in the descriptor drove the decision.

Chart of accounts:
{coa_block}
"""

USER_PROMPT = """Transaction:
- Bank descriptor: {vendor_raw}
- Normalized vendor: {vendor_norm}
- Amount: {amount:.2f} {currency}
- Date: {date}
- Reference/memo: {memo}

Assign the account."""


def build_messages(
    *,
    coa_block: str,
    vendor_raw: str,
    vendor_norm: str,
    amount: float,
    currency: str,
    date: str,
    memo: str | None,
) -> list[tuple[str, str]]:
    """Messages for the structured-output call, as (role, content) pairs."""
    return [
        ("system", SYSTEM_PROMPT.format(coa_block=coa_block)),
        (
            "user",
            USER_PROMPT.format(
                vendor_raw=vendor_raw,
                vendor_norm=vendor_norm,
                amount=amount,
                currency=currency,
                date=date,
                memo=memo or "(none)",
            ),
        ),
    ]
