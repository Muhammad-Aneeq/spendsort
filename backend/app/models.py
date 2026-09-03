"""ORM tables, following spec 11 section 6 exactly.

    transactions(id, date, amount, currency, vendor_raw, vendor_norm, status)
    categorizations(id, txn_id, account_code, confidence, reason, source[memory|llm], created_at)
    verdicts(id, txn_id, action[accept|override], final_account, at)
    vendor_memory(vendor_norm, account_code, source, hit_count, updated_at)
    runs(id, started, txn_count, auto_rate, memory_hit_rate, cost_usd)

Two additions beyond the listed columns, both load-bearing rather than decorative:
  * `categorizations.run_id` — the dashboard has to chart auto-rate, memory-hit rate and cost
    ACROSS runs (spec 11 section 4 F5), which is impossible if a decision does not know its run.
  * a few audit/cost fields on `runs`, so the cost cap of spec 11 section 11 can be shown to
    have been enforced rather than merely claimed.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class TxnStatus(StrEnum):
    """Where a transaction sits in the trust pipeline."""

    PENDING = "pending"  # uploaded, not yet categorized
    AUTO = "auto"  # confidence >= threshold: applied without a human
    QUEUED = "queued"  # below threshold, or invalid/capped: waiting for a human
    RESOLVED = "resolved"  # a human accepted or overrode it


class CategorizationSource(StrEnum):
    """spec 11 section 6: source[memory|llm]."""

    MEMORY = "memory"  # answered from vendor_memory — zero LLM cost
    LLM = "llm"


class MemorySource(StrEnum):
    """spec 11 section 4 F4: source[human|llm-confirmed]."""

    HUMAN = "human"  # written by an override; the strongest signal there is
    LLM_CONFIRMED = "llm-confirmed"  # a high-confidence LLM answer, promoted to memory


class VerdictAction(StrEnum):
    """spec 11 section 6: action[accept|override]."""

    ACCEPT = "accept"
    OVERRIDE = "override"


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    # The descriptor as uploaded — never overwritten, so an audit can always see the original.
    vendor_raw: Mapped[str] = mapped_column(String(512), nullable=False)
    # The normalized form the agent and vendor_memory both key on.
    vendor_norm: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=TxnStatus.PENDING, index=True)

    memo: Mapped[str | None] = mapped_column(String(256), nullable=True)
    # Kept so a re-upload of the same file can be recognised rather than silently doubled.
    source_file: Mapped[str | None] = mapped_column(String(256), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    categorizations: Mapped[list[Categorization]] = relationship(
        back_populates="transaction", cascade="all, delete-orphan", order_by="Categorization.id"
    )
    verdicts: Mapped[list[Verdict]] = relationship(
        back_populates="transaction", cascade="all, delete-orphan", order_by="Verdict.id"
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','auto','queued','resolved')",
            name="ck_transactions_status",
        ),
        Index("ix_transactions_status_date", "status", "date"),
    )

    @property
    def latest_categorization(self) -> Categorization | None:
        return self.categorizations[-1] if self.categorizations else None

    @property
    def final_account(self) -> str | None:
        """What the ledger should say: a human verdict beats the agent's suggestion."""
        if self.verdicts:
            return self.verdicts[-1].final_account
        latest = self.latest_categorization
        return latest.account_code if latest and self.status == TxnStatus.AUTO else None


class Categorization(Base):
    __tablename__ = "categorizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    txn_id: Mapped[int] = mapped_column(ForeignKey("transactions.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("runs.id", ondelete="SET NULL"), index=True)

    account_code: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    source: Mapped[str] = mapped_column(String(16), nullable=False)

    # True when the account_code the model returned was not in the CoA. The decision is kept
    # for the audit trail, but it is forced to low confidence and queued (spec 11 section 8).
    coa_valid: Mapped[bool] = mapped_column(default=True, nullable=False)
    # Cost attribution, so cost-per-run is measured rather than estimated.
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    transaction: Mapped[Transaction] = relationship(back_populates="categorizations")

    __table_args__ = (
        CheckConstraint("source IN ('memory','llm')", name="ck_categorizations_source"),
        CheckConstraint("confidence >= 0.0 AND confidence <= 1.0", name="ck_categorizations_confidence"),
    )


class Verdict(Base):
    __tablename__ = "verdicts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    txn_id: Mapped[int] = mapped_column(ForeignKey("transactions.id", ondelete="CASCADE"), index=True)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    final_account: Mapped[str] = mapped_column(String(16), nullable=False)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    transaction: Mapped[Transaction] = relationship(back_populates="verdicts")

    __table_args__ = (CheckConstraint("action IN ('accept','override')", name="ck_verdicts_action"),)


class VendorMemory(Base):
    """The learned vendor mapping — the reason the agent gets cheaper every month."""

    __tablename__ = "vendor_memory"

    vendor_norm: Mapped[str] = mapped_column(String(256), primary_key=True)
    account_code: Mapped[str] = mapped_column(String(16), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    hit_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    # Kept for the Memory screen: which vendor the mapping was first learned from.
    example_vendor_raw: Mapped[str | None] = mapped_column(String(512), nullable=True)

    __table_args__ = (CheckConstraint("source IN ('human','llm-confirmed')", name="ck_vendor_memory_source"),)

    @property
    def learned_from_human(self) -> bool:
        """A mapping a person taught us. This is what the UI labels "learned"."""
        return self.source == MemorySource.HUMAN


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False
    )
    finished: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    txn_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    auto_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    memory_hit_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # The settings this run was actually judged under, recorded so a historical run can be
    # read honestly even after someone changes the threshold.
    auto_threshold: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    cost_cap_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    model: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    llm_mode: Mapped[str] = mapped_column(String(16), default="mock", nullable=False)

    # Set when the cost cap stopped the run early. The remainder is queued, never dropped
    # (PLAN.md D7), and this is how the UI can say so out loud.
    cost_capped: Mapped[bool] = mapped_column(default=False, nullable=False)
    capped_txn_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    llm_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    memory_hits: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
