"""API DTOs (Pydantic v2).

Kept separate from the ORM so the wire format is a deliberate choice rather than whatever the
tables happen to look like. The LLM's structured-output model lives in `agent/llm.py`, next to
the prompt it constrains.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- chart of accounts -------------------------------------------------------


class AccountOut(ApiModel):
    code: str
    name: str
    kind: str = "expense"
    description: str = ""


class CoaOut(ApiModel):
    accounts: list[AccountOut]
    count: int


class CoaUpdate(BaseModel):
    """A full replacement of the editable CoA YAML (spec 11 section 4 F1)."""

    yaml: str = Field(min_length=1, description="The complete chart-of-accounts YAML document")


# --- intake ------------------------------------------------------------------


class RowErrorOut(ApiModel):
    line: int
    reason: str
    raw: str


class IngestResultOut(ApiModel):
    """Deliberately reports rejects as loudly as accepts: a silent partial import is a lie."""

    accepted: int
    rejected: int
    truncated: bool
    encoding: str
    source_file: str | None = None
    errors: list[RowErrorOut] = Field(default_factory=list)
    pending_total: int = Field(description="Transactions now awaiting categorization")


# --- transactions & decisions ------------------------------------------------


class CategorizationOut(ApiModel):
    account_code: str
    account_name: str = ""
    confidence: float
    reason: str
    source: str  # memory | llm
    coa_valid: bool = True
    cost_usd: float = 0.0
    created_at: datetime | None = None


class TransactionOut(ApiModel):
    id: int
    date: date
    amount: float
    currency: str
    vendor_raw: str
    vendor_norm: str
    status: str
    memo: str | None = None

    suggestion: CategorizationOut | None = None
    final_account: str | None = None
    final_account_name: str | None = None
    # True when this row was answered from a mapping a human taught us (spec 11 US3).
    learned: bool = False


class QueueOut(ApiModel):
    """The review queue — spec 11 section 4 F3: "sorted lowest-confidence-first"."""

    items: list[TransactionOut]
    total: int
    auto_threshold: float


# --- verdicts ----------------------------------------------------------------


class VerdictIn(BaseModel):
    action: str = Field(pattern="^(accept|override)$")
    # Required for an override; ignored for an accept.
    final_account: str | None = None


class VerdictOut(ApiModel):
    txn_id: int
    action: str
    final_account: str
    final_account_name: str = ""
    memory_written: bool = False
    at: datetime | None = None


# --- vendor memory -----------------------------------------------------------


class MemoryEntryOut(ApiModel):
    vendor_norm: str
    account_code: str
    account_name: str = ""
    source: str  # human | llm-confirmed
    hit_count: int
    updated_at: datetime | None = None
    example_vendor_raw: str | None = None


class MemoryOut(ApiModel):
    entries: list[MemoryEntryOut]
    total: int


# --- runs & metrics ----------------------------------------------------------


class RunOut(ApiModel):
    id: int
    started: datetime
    finished: datetime | None = None
    txn_count: int
    auto_rate: float
    memory_hit_rate: float
    cost_usd: float
    auto_threshold: float
    cost_cap_usd: float
    model: str
    llm_mode: str
    cost_capped: bool
    capped_txn_count: int
    llm_calls: int
    memory_hits: int


class HistogramBin(ApiModel):
    lower: float
    upper: float
    count: int
    auto: bool = Field(description="Whether decisions in this bin clear the auto-apply threshold")


class CategoryBreakdownItem(ApiModel):
    account_code: str
    account_name: str
    count: int
    total_amount: float


class MetricsOut(ApiModel):
    """Everything the dashboard needs (spec 11 section 4 F5), including the memory bend."""

    total_transactions: int
    pending: int
    auto: int
    queued: int
    resolved: int

    auto_rate: float
    memory_hit_rate: float
    total_cost_usd: float
    auto_threshold: float

    confidence_histogram: list[HistogramBin]
    category_breakdown: list[CategoryBreakdownItem]
    # The memory bend: one point per run, oldest first (spec 11 section 8).
    runs: list[RunOut]
