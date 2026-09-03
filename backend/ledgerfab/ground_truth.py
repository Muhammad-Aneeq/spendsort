"""The ground-truth emitter (spec 00 A3).

    "Also ships: ground-truth emitter (for every generated world, the correct
     matches/exceptions/answers, so Projects 01/04/06/07 get labels for free)."

For SpendSort the correct answer is the account a transaction belongs in. Because the world was
built by choosing a counterparty first and only then rendering a messy descriptor, the label is
known by construction rather than inferred — which is exactly what makes it trustworthy as a gate.
"""

from __future__ import annotations

from ledgerfab.models import GroundTruth, GroundTruthEntry, World


def emit_ground_truth(world: World) -> GroundTruth:
    by_id = {cp.id: cp for cp in world.counterparties}
    valid_codes = world.account_codes()

    entries: list[GroundTruthEntry] = []
    for txn in world.transactions:
        cp = by_id.get(txn.counterparty_id)
        if cp is None:  # pragma: no cover - would mean a generator bug
            raise ValueError(f"transaction {txn.id} references unknown counterparty {txn.counterparty_id}")

        # A label outside the CoA would silently poison every downstream metric.
        if cp.account_code not in valid_codes:
            raise ValueError(f"counterparty {cp.id} maps to {cp.account_code}, which is not in the CoA")

        entries.append(
            GroundTruthEntry(
                txn_id=txn.id,
                account_code=cp.account_code,
                counterparty_id=cp.id,
                counterparty_canonical=cp.canonical_name,
                ambiguous=cp.ambiguous_with is not None,
                alternate_account_code=cp.ambiguous_with,
            )
        )

    return GroundTruth(entries=tuple(entries))
