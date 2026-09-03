"""ledgerfab acceptance (spec 00 A3).

"ledgerfab.generate(profile, seed) returns a typed World; world.ground_truth gives
 correct matches; determinism test passes."
"Seeded -> reproducible (same seed+profile = identical dataset, hash-verifiable)."
"""

from __future__ import annotations

from datetime import date

import pytest

import ledgerfab
from ledgerfab.config import PRESETS
from ledgerfab.vendors import AMBIGUOUS_IDS

PROFILE_NAMES = ("clean", "realistic", "nightmare")


# --- determinism -------------------------------------------------------------


@pytest.mark.parametrize("profile", PROFILE_NAMES)
def test_same_seed_and_profile_gives_an_identical_world(profile: str) -> None:
    a = ledgerfab.generate(profile, seed=42)
    b = ledgerfab.generate(profile, seed=42)

    assert a.content_hash() == b.content_hash()
    # Hash equality could in principle hide a field the hash ignores, so compare the rows too.
    assert a.transactions == b.transactions
    assert a.ground_truth == b.ground_truth


@pytest.mark.parametrize("profile", PROFILE_NAMES)
def test_a_different_seed_gives_a_different_world(profile: str) -> None:
    assert ledgerfab.generate(profile, 42).content_hash() != ledgerfab.generate(profile, 43).content_hash()


def test_the_profile_is_part_of_the_seed() -> None:
    """Same integer seed, different preset, must not collide."""
    hashes = {p: ledgerfab.generate(p, 42).content_hash() for p in PROFILE_NAMES}
    assert len(set(hashes.values())) == len(PROFILE_NAMES)


def test_generation_never_reads_the_clock() -> None:
    """A generator that reads `today()` is not reproducible. The period is declared, not discovered."""
    world = ledgerfab.generate("realistic", 42)
    start = PRESETS["realistic"].period_start
    days = PRESETS["realistic"].period_days

    assert all(start <= txn.date < date.fromordinal(start.toordinal() + days) for txn in world.transactions)


# --- typed World -------------------------------------------------------------


def test_generate_returns_a_populated_typed_world() -> None:
    world = ledgerfab.generate("realistic", 42)

    assert isinstance(world, ledgerfab.World)
    assert world.profile == "realistic"
    assert world.seed == 42
    assert len(world.transactions) == PRESETS["realistic"].txn_count
    assert len(world.chart_of_accounts) == 20
    assert world.counterparties


def test_unknown_profile_is_rejected_loudly() -> None:
    with pytest.raises(ValueError, match="unknown profile"):
        ledgerfab.generate("mildly-annoying", 42)


# --- ground truth ------------------------------------------------------------


@pytest.mark.parametrize("profile", PROFILE_NAMES)
def test_every_transaction_has_a_coa_aligned_label(profile: str) -> None:
    """spec 11 section 10 requires eval ground truth to be "CoA-aligned"."""
    world = ledgerfab.generate(profile, 42)
    truth = world.ground_truth.by_txn()
    codes = world.account_codes()

    assert set(truth) == {txn.id for txn in world.transactions}
    assert all(entry.account_code in codes for entry in world.ground_truth.entries)


def test_the_label_matches_the_counterparty_that_produced_the_row() -> None:
    """Labels are known by construction — vendor chosen first, messy descriptor rendered after."""
    world = ledgerfab.generate("nightmare", 7)
    truth = world.ground_truth.by_txn()

    for txn in world.transactions:
        cp = world.counterparty(txn.counterparty_id)
        assert cp is not None
        assert truth[txn.id].account_code == cp.account_code
        assert truth[txn.id].counterparty_canonical == cp.canonical_name


def test_ambiguous_rows_are_flagged_with_their_alternative() -> None:
    """spec 11 section 14: two plausible accounts must be visible to the eval, so it can
    assert that confidence DROPS instead of asserting one code."""
    world = ledgerfab.generate("nightmare", 3)
    flagged = [e for e in world.ground_truth.entries if e.ambiguous]

    assert flagged, "the nightmare profile should surface ambiguous vendors"
    for entry in flagged:
        assert entry.counterparty_id in AMBIGUOUS_IDS
        assert entry.alternate_account_code in world.account_codes()
        assert entry.alternate_account_code != entry.account_code


# --- the knobs ---------------------------------------------------------------


def test_clean_profile_is_actually_clean() -> None:
    world = ledgerfab.generate("clean", 42)
    canonical = {cp.canonical_name for cp in world.counterparties}

    # alias_rate 0 -> every descriptor is the plain vendor name.
    assert all(txn.vendor_raw in canonical for txn in world.transactions)
    # date_format_chaos 0 -> one ISO format throughout.
    assert all(txn.date_raw == txn.date.isoformat() for txn in world.transactions)
    # duplicate_rate / partial_payment_rate / fx_rate 0.
    assert all(txn.duplicate_of is None and txn.partial_of is None for txn in world.transactions)
    assert {txn.currency for txn in world.transactions} == {"USD"}
    # missing_reference_rate 0 -> every row carries a reference.
    assert all(txn.memo for txn in world.transactions)


def test_messier_profiles_produce_messier_descriptors() -> None:
    """The knobs have to actually bite, or the alias tests below prove nothing."""
    canonical = {cp.canonical_name for cp in ledgerfab.default_counterparties()}

    def alias_share(profile: str) -> float:
        world = ledgerfab.generate(profile, 42)
        aliased = sum(1 for t in world.transactions if t.vendor_raw not in canonical)
        return aliased / len(world.transactions)

    assert alias_share("clean") == 0.0
    assert alias_share("realistic") > 0.5
    assert alias_share("nightmare") > alias_share("realistic")


def test_nightmare_exercises_date_chaos_and_missing_references() -> None:
    world = ledgerfab.generate("nightmare", 42)

    chaotic_dates = sum(1 for t in world.transactions if t.date_raw != t.date.isoformat())
    missing_refs = sum(1 for t in world.transactions if not t.memo)

    assert chaotic_dates > 0
    assert missing_refs > 0
    # fx is flag-only in v1: rows are marked foreign, no conversion is modelled.
    assert all(t.currency == "USD" or t.currency in {"EUR", "GBP", "CAD"} for t in world.transactions)


def test_partial_payments_split_unevenly_and_still_reconcile() -> None:
    """A split charge must sum back to one charge, and must not look like a duplicated row —
    equal halves would be indistinguishable from a duplicate."""
    profile = PRESETS["nightmare"].model_copy(update={"txn_count": 400})
    world = ledgerfab.generate(profile, 5)
    by_id = {t.id: t for t in world.transactions}

    slices = [t for t in world.transactions if t.partial_of]
    assert slices, "the nightmare profile should produce partial payments"

    uneven = 0
    for second in slices:
        first = by_id[second.partial_of or ""]
        assert first.counterparty_id == second.counterparty_id
        assert second.date >= first.date
        if abs(first.amount - second.amount) > 0.01:
            uneven += 1

    # Not every split will be lopsided, but the great majority should be.
    assert uneven / len(slices) > 0.8


def test_duplicates_are_exact_copies_on_the_same_day() -> None:
    """A duplicated feed row is the same charge twice — that is what makes it a duplicate."""
    profile = PRESETS["nightmare"].model_copy(update={"txn_count": 400})
    world = ledgerfab.generate(profile, 5)
    by_id = {t.id: t for t in world.transactions}

    dupes = [t for t in world.transactions if t.duplicate_of]
    assert dupes, "the nightmare profile should produce duplicate rows"

    for dupe in dupes:
        original = by_id[dupe.duplicate_of or ""]
        assert (dupe.date, dupe.date_raw, dupe.amount, dupe.vendor_raw) == (
            original.date,
            original.date_raw,
            original.amount,
            original.vendor_raw,
        )


def test_row_count_is_exact_even_with_duplicates_and_splits() -> None:
    profile = PRESETS["nightmare"].model_copy(update={"txn_count": 57})
    assert len(ledgerfab.generate(profile, 11).transactions) == 57


def test_transactions_are_ordered_like_a_feed() -> None:
    world = ledgerfab.generate("realistic", 42)
    keys = [(t.date, t.id) for t in world.transactions]
    assert keys == sorted(keys)
