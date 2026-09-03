"""ledgerfab — the synthetic finance data engine (spec 00 A3).

Reimplemented from the spec because `backend_seed_ledgerfab/` was not present in this repo
(BLOCKERS.md **B1**). The public surface is kept to the contract spec 00 A3 states, so the
original seed could replace this module without touching `app/` or `evals/`:

    world = ledgerfab.generate("realistic", seed=42)
    world.ground_truth          # correct answers, for free
    world.content_hash()        # same seed + profile => same hash

Scope note (PLAN.md D3): spec 00 A3 also lists invoices, POs, GL entries and recurring-accrual
schedules. SpendSort reads none of them, so they are not built — the omission is documented
rather than silent.

⚠️ Everything this module produces is synthetic.
"""

from ledgerfab.coa import CODES, DEFAULT_COA, account
from ledgerfab.config import CLEAN, NIGHTMARE, PRESETS, REALISTIC, Profile, resolve_profile
from ledgerfab.generate import generate
from ledgerfab.ground_truth import emit_ground_truth
from ledgerfab.models import (
    Account,
    BankTxn,
    Company,
    Counterparty,
    GroundTruth,
    GroundTruthEntry,
    World,
)
from ledgerfab.vendors import default_counterparties

__version__ = "0.1.0"

__all__ = [
    "CLEAN",
    "CODES",
    "DEFAULT_COA",
    "NIGHTMARE",
    "PRESETS",
    "REALISTIC",
    "Account",
    "BankTxn",
    "Company",
    "Counterparty",
    "GroundTruth",
    "GroundTruthEntry",
    "Profile",
    "World",
    "account",
    "default_counterparties",
    "emit_ground_truth",
    "generate",
    "resolve_profile",
]
