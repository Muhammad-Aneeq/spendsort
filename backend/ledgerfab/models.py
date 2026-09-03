"""Typed domain objects for the generated world (spec 00 A3: "returns a typed World").

Pydantic v2 throughout, so a World can be dumped to canonical JSON and hashed — which is how
the determinism guarantee ("same seed+profile = identical dataset, hash-verifiable") is proven.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Account(Frozen):
    """One line of the chart of accounts."""

    code: str
    name: str
    kind: str = "expense"
    description: str = ""


class Company(Frozen):
    name: str
    currency: str = "USD"
    country: str = "US"


class Counterparty(Frozen):
    """A vendor. `aliases` are the messy bank descriptors this vendor shows up as."""

    id: str
    canonical_name: str
    account_code: str
    aliases: tuple[str, ...] = ()
    # spec 11 section 14: "CoA ambiguity (two plausible accounts) -> confidence must drop".
    # A second genuinely defensible account for this vendor, or None.
    ambiguous_with: str | None = None
    typical_amount: tuple[float, float] = (10.0, 500.0)
    recurring: bool = False


class BankTxn(Frozen):
    """A bank/card transaction as it would actually land in a feed."""

    id: str
    # The date as the feed presents it — possibly in a chaotic format (date_format_chaos).
    date_raw: str
    # The same date, resolved. Ground truth for any date parsing.
    date: date
    amount: float
    currency: str = "USD"
    # The descriptor the bookkeeper actually sees. This is what must be normalized.
    vendor_raw: str
    counterparty_id: str
    memo: str | None = None
    # Set when this row is a duplicate of another (duplicate_rate).
    duplicate_of: str | None = None
    # Set when this row is one slice of a split charge (partial_payment_rate).
    partial_of: str | None = None


class GroundTruthEntry(Frozen):
    """The correct answer for one transaction (spec 00 A3: "ground-truth emitter")."""

    txn_id: str
    account_code: str
    counterparty_id: str
    counterparty_canonical: str
    # True when a second account is genuinely defensible: the agent is expected to be
    # UNCERTAIN here, so evals assert low confidence rather than a specific code.
    ambiguous: bool = False
    alternate_account_code: str | None = None


class GroundTruth(Frozen):
    entries: tuple[GroundTruthEntry, ...] = ()

    def by_txn(self) -> dict[str, GroundTruthEntry]:
        return {e.txn_id: e for e in self.entries}

    def account_for(self, txn_id: str) -> str | None:
        entry = self.by_txn().get(txn_id)
        return entry.account_code if entry else None


class World(Frozen):
    """Everything one generation produced, plus its labels."""

    profile: str
    seed: int
    company: Company
    chart_of_accounts: tuple[Account, ...]
    counterparties: tuple[Counterparty, ...]
    transactions: tuple[BankTxn, ...]
    ground_truth: GroundTruth = Field(default_factory=GroundTruth)

    # --- convenience ----------------------------------------------------
    def account_codes(self) -> set[str]:
        return {a.code for a in self.chart_of_accounts}

    def counterparty(self, cp_id: str) -> Counterparty | None:
        return next((c for c in self.counterparties if c.id == cp_id), None)

    def content_hash(self) -> str:
        """Stable SHA-256 over the canonical JSON form.

        This is the "hash-verifiable" half of spec 00 A3's determinism promise: two worlds
        built from the same seed+profile must produce the same string.
        """
        payload = self.model_dump(mode="json")
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
