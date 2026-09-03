"""World generation (spec 00 A3).

    "Seeded -> reproducible (same seed+profile = identical dataset, hash-verifiable)."

Determinism rules obeyed here, because they are what make the guarantee real:
  * one `random.Random` instance, seeded from (profile name, seed) — never the global `random`
  * never reads the clock; the period comes from the profile
  * every iteration order is over an explicit tuple, never a set or dict
"""

from __future__ import annotations

import hashlib
import random
from datetime import date, timedelta

from ledgerfab.coa import DEFAULT_COA
from ledgerfab.config import Profile, resolve_profile
from ledgerfab.models import (
    BankTxn,
    Company,
    Counterparty,
    GroundTruth,
    World,
)
from ledgerfab.vendors import CITIES, default_counterparties

DEFAULT_COMPANY = Company(name="Northwind Studio LLC", currency="USD", country="US")

# Recurring vendors show up far more often than one-off purchases.
_RECURRING_WEIGHT = 4
_ONE_OFF_WEIGHT = 1

# "fx_rate (flag-only in v1)": the row is marked foreign, nothing is converted.
_FX_CURRENCIES: tuple[str, ...] = ("EUR", "GBP", "CAD")

_CHAOS_DATE_FORMATS: tuple[str, ...] = (
    "%m/%d/%Y",  # US
    "%d-%m-%Y",  # EU — genuinely ambiguous against the line above, which is the point
    "%d %b %Y",
    "%m/%d/%y",
    "%Y/%m/%d",
)


def _seed_int(profile_name: str, seed: int) -> int:
    """Stable seed from (profile, seed) so 'realistic'+42 and 'nightmare'+42 differ."""
    digest = hashlib.sha256(f"{profile_name}:{seed}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def _ref(rng: random.Random, length: int = 6) -> str:
    """A bank reference blob.

    Guaranteed to contain at least two digits, because real card references effectively always
    do. That is not a convenience for our normalizer — it is what makes "this token is a
    reference, not a brand" an honest inference downstream instead of a lucky guess.
    """
    letters = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    digits = "0123456789"
    chars = [rng.choice(digits), rng.choice(digits)]
    chars += [rng.choice(letters + digits) for _ in range(length - 2)]
    rng.shuffle(chars)
    return "".join(chars)


def _descriptor(rng: random.Random, cp: Counterparty, alias_rate: float) -> str:
    """Build the bank descriptor the bookkeeper will actually see."""
    use_alias = bool(cp.aliases) and rng.random() < alias_rate
    template = rng.choice(list(cp.aliases)) if use_alias else cp.canonical_name

    text = (
        template.replace("{ref}", _ref(rng))
        .replace("{store}", str(rng.randint(100, 9999)))
        .replace("{city}", rng.choice(list(CITIES)))
    )

    # Feeds also mangle case and spacing. This is descriptor chaos, so it is gated on
    # alias_rate as well: `clean` must mean clean, or the profile proves nothing.
    # The draw happens either way, so the RNG stream stays aligned across branches.
    roll = rng.random()
    if use_alias:
        if roll < 0.18:
            text = text.upper()
        elif roll < 0.24:
            text = f"POS DEBIT {text}"
        elif roll < 0.28:
            text = f"{text}  "
    return text


def _amount(rng: random.Random, cp: Counterparty, amount_noise: float) -> float:
    low, high = cp.typical_amount
    base = rng.uniform(low, high)
    if amount_noise > 0.0:
        # Up to +/-25% swing at full noise.
        base *= 1.0 + rng.uniform(-0.25, 0.25) * amount_noise
    return round(max(0.5, base), 2)


def _date_raw(rng: random.Random, when: date, chaos: float) -> str:
    if chaos > 0.0 and rng.random() < chaos:
        return when.strftime(rng.choice(list(_CHAOS_DATE_FORMATS)))
    return when.isoformat()


def _pick_counterparty(
    rng: random.Random,
    all_cps: tuple[Counterparty, ...],
    ambiguous: tuple[Counterparty, ...],
    weights: tuple[int, ...],
    ambiguous_rate: float,
) -> Counterparty:
    """Weighted pick, biased toward genuinely ambiguous vendors at `ambiguous_rate`."""
    if ambiguous and rng.random() < ambiguous_rate:
        return rng.choice(list(ambiguous))
    return rng.choices(list(all_cps), weights=list(weights), k=1)[0]


def generate(profile: str | Profile = "realistic", seed: int = 42) -> World:
    """Build a reproducible world.

    spec 00 A3 acceptance: "ledgerfab.generate(profile, seed) returns a typed World;
    world.ground_truth gives correct matches; determinism test passes."
    """
    prof = resolve_profile(profile)
    rng = random.Random(_seed_int(prof.name, seed))

    counterparties = default_counterparties()
    weights = tuple(_RECURRING_WEIGHT if cp.recurring else _ONE_OFF_WEIGHT for cp in counterparties)
    ambiguous = tuple(cp for cp in counterparties if cp.ambiguous_with is not None)

    rows: list[BankTxn] = []
    next_id = 0

    def new_id() -> str:
        nonlocal next_id
        next_id += 1
        return f"txn-{next_id:05d}"

    while len(rows) < prof.txn_count:
        cp = _pick_counterparty(rng, counterparties, ambiguous, weights, prof.ambiguous_rate)

        when = prof.period_start + timedelta(days=rng.randrange(prof.period_days))
        amount = _amount(rng, cp, prof.amount_noise)
        currency = (
            rng.choice(list(_FX_CURRENCIES))
            if prof.fx_rate > 0.0 and rng.random() < prof.fx_rate
            else DEFAULT_COMPANY.currency
        )
        memo = None if rng.random() < prof.missing_reference_rate else f"INV-{rng.randint(10000, 99999)}"

        # A charge split across two settlements (partial_payment_rate). The split is uneven:
        # equal halves would be indistinguishable from a duplicated feed row.
        split = prof.partial_payment_rate > 0.0 and rng.random() < prof.partial_payment_rate
        first_slice = round(amount * rng.uniform(0.3, 0.7), 2) if split else amount

        primary = BankTxn(
            id=new_id(),
            date_raw=_date_raw(rng, when, prof.date_format_chaos),
            date=when,
            amount=first_slice,
            currency=currency,
            vendor_raw=_descriptor(rng, cp, prof.alias_rate),
            counterparty_id=cp.id,
            memo=memo,
        )
        rows.append(primary)

        if split and len(rows) < prof.txn_count:
            second_when = when + timedelta(days=rng.randrange(1, 6))
            rows.append(
                BankTxn(
                    id=new_id(),
                    date_raw=_date_raw(rng, second_when, prof.date_format_chaos),
                    date=second_when,
                    amount=round(amount - first_slice, 2),
                    currency=currency,
                    vendor_raw=_descriptor(rng, cp, prof.alias_rate),
                    counterparty_id=cp.id,
                    memo=memo,
                    partial_of=primary.id,
                )
            )

        # A duplicated feed row (duplicate_rate) — same vendor, same amount, same day.
        if prof.duplicate_rate > 0.0 and rng.random() < prof.duplicate_rate and len(rows) < prof.txn_count:
            rows.append(
                BankTxn(
                    id=new_id(),
                    date_raw=primary.date_raw,
                    date=primary.date,
                    amount=primary.amount,
                    currency=primary.currency,
                    vendor_raw=primary.vendor_raw,
                    counterparty_id=cp.id,
                    memo=primary.memo,
                    duplicate_of=primary.id,
                )
            )

    # Exactly txn_count rows, presented like a feed: oldest first, stable tie-break on id.
    transactions = tuple(sorted(rows[: prof.txn_count], key=lambda t: (t.date, t.id)))

    from ledgerfab.ground_truth import emit_ground_truth

    world = World(
        profile=prof.name,
        seed=seed,
        company=DEFAULT_COMPANY,
        chart_of_accounts=DEFAULT_COA,
        counterparties=counterparties,
        transactions=transactions,
        ground_truth=GroundTruth(),
    )
    return world.model_copy(update={"ground_truth": emit_ground_truth(world)})
