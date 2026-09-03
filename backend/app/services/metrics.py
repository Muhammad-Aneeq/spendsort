"""Dashboard metrics — spec 11 section 4 F5.

    "Dashboard: confidence histogram, auto-rate %, memory-hit rate, cost-per-run,
     category breakdown."

And the one that matters most, spec 11 section 8:

    "the agent gets cheaper and faster every month, and the dashboard proves it:
     that chart IS the launch post"

So the run series is a first-class part of this payload, not an afterthought — the memory-bend
chart is the whole reason the dashboard exists.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.coa import get_coa
from app.models import Categorization, Run, Transaction, TxnStatus, VendorMemory
from app.schemas import (
    CategoryBreakdownItem,
    HistogramBin,
    MetricsOut,
    RunOut,
)
from app.settings import get_settings

# Ten bins of 0.1. Fine enough to show the gate as a visible cliff, coarse enough to read.
HISTOGRAM_BINS = 10


def _latest_categorizations(db: Session) -> list[Categorization]:
    """The most recent decision per transaction.

    A transaction can be categorized more than once (a second run after an override), and
    counting all of them would double-count history into today's numbers.
    """
    newest = select(func.max(Categorization.id)).group_by(Categorization.txn_id).scalar_subquery()
    return list(db.scalars(select(Categorization).where(Categorization.id.in_(newest))))


def confidence_histogram(db: Session, threshold: float) -> list[HistogramBin]:
    """Distribution of confidence, with each bin marked auto or queued.

    The `auto` flag is what makes this chart readable at a glance: the gate becomes a visible
    line, and the bars to its right are the work no human touched.
    """
    decisions = _latest_categorizations(db)
    counts = [0] * HISTOGRAM_BINS

    for decision in decisions:
        # 1.0 belongs in the top bin, not an eleventh one.
        index = min(int(decision.confidence * HISTOGRAM_BINS), HISTOGRAM_BINS - 1)
        counts[index] += 1

    bins: list[HistogramBin] = []
    for i, count in enumerate(counts):
        lower = i / HISTOGRAM_BINS
        upper = (i + 1) / HISTOGRAM_BINS
        bins.append(
            HistogramBin(
                lower=round(lower, 2),
                upper=round(upper, 2),
                count=count,
                # A bin is "auto" when everything in it clears the threshold.
                auto=lower >= threshold,
            )
        )
    return bins


def category_breakdown(db: Session) -> list[CategoryBreakdownItem]:
    """Spend by account, largest first.

    Counts only **decided** lines — auto-applied or human-resolved. A queued row has no agreed
    account yet, and putting a suggestion into a spend breakdown would report a guess as fact.
    """
    coa = get_coa()
    totals: dict[str, tuple[int, float]] = {}

    txns = list(db.scalars(select(Transaction).where(Transaction.status.in_([TxnStatus.AUTO, TxnStatus.RESOLVED]))))
    for txn in txns:
        account = txn.final_account
        if not account:
            continue
        count, amount = totals.get(account, (0, 0.0))
        totals[account] = (count + 1, amount + txn.amount)

    items = [
        CategoryBreakdownItem(
            account_code=code,
            account_name=coa.name_for(code),
            count=count,
            total_amount=round(amount, 2),
        )
        for code, (count, amount) in totals.items()
    ]
    return sorted(items, key=lambda i: (-i.total_amount, i.account_code))


def status_counts(db: Session) -> dict[str, int]:
    rows = db.execute(select(Transaction.status, func.count()).group_by(Transaction.status)).all()
    counts = {status.value: 0 for status in TxnStatus}
    for status, count in rows:
        counts[str(status)] = int(count)
    return counts


def build_metrics(db: Session) -> MetricsOut:
    settings = get_settings()
    threshold = settings.auto_threshold

    counts = status_counts(db)
    total = sum(counts.values())

    decisions = _latest_categorizations(db)
    memory_hits = sum(1 for d in decisions if d.source == "memory")
    total_cost = sum(d.cost_usd for d in decisions)

    # Auto-rate counts what the agent handled unaided: auto-applied now, or auto-applied and
    # then confirmed by a human. Queued rows are the work it handed back.
    decided_without_a_human = counts.get(TxnStatus.AUTO.value, 0)

    runs = list(db.scalars(select(Run).order_by(Run.id)))

    return MetricsOut(
        total_transactions=total,
        pending=counts.get(TxnStatus.PENDING.value, 0),
        auto=counts.get(TxnStatus.AUTO.value, 0),
        queued=counts.get(TxnStatus.QUEUED.value, 0),
        resolved=counts.get(TxnStatus.RESOLVED.value, 0),
        auto_rate=(decided_without_a_human / total) if total else 0.0,
        memory_hit_rate=(memory_hits / len(decisions)) if decisions else 0.0,
        total_cost_usd=round(total_cost, 6),
        auto_threshold=threshold,
        confidence_histogram=confidence_histogram(db, threshold),
        category_breakdown=category_breakdown(db),
        runs=[RunOut.model_validate(r) for r in runs],
    )


def memory_size(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(VendorMemory)) or 0
