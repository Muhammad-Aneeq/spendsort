"""Regenerate `evals/cases.jsonl` — spec 11 section 10.

    "evals/: 100 ledgerfab transactions with ground-truth categories (CoA-aligned)"

Run with `make seed` (or `python evals/build_cases.py`). The seed is fixed and the ledgerfab
world is hash-verifiable, so the suite is byte-reproducible: a change in the numbers means a
change in the *agent*, never a reshuffled dataset.

Ambiguous cases are labelled. Spec 11 section 14 requires that CoA ambiguity be "tested with
deliberately ambiguous eval cases", and for those the correct behaviour is low confidence and a
queued row — so the harness scores them on confidence, not on picking one particular code.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import ledgerfab
from ledgerfab.config import PRESETS

CASE_COUNT = 100
PROFILE = "realistic"
SEED = 2026

EVALS_DIR = Path(__file__).parent
CASES_PATH = EVALS_DIR / "cases.jsonl"


def build_world() -> ledgerfab.World:
    """The eval world: 100 realistic transactions from a fixed seed."""
    profile = PRESETS[PROFILE].model_copy(
        update={
            "txn_count": CASE_COUNT,
            "period_start": date(2026, 6, 1),
            "period_days": 30,
        }
    )
    return ledgerfab.generate(profile, SEED)


def build_cases() -> list[dict[str, object]]:
    world = build_world()
    truth = world.ground_truth.by_txn()
    names = {a.code: a.name for a in world.chart_of_accounts}

    cases: list[dict[str, object]] = []
    for txn in world.transactions:
        entry = truth[txn.id]
        cases.append(
            {
                "case_id": txn.id,
                # What the agent is allowed to see.
                "date_raw": txn.date_raw,
                "date": txn.date.isoformat(),
                "amount": txn.amount,
                "currency": txn.currency,
                "vendor_raw": txn.vendor_raw,
                "memo": txn.memo,
                # Ground truth. Never shown to the agent.
                "expected_account_code": entry.account_code,
                "expected_account_name": names.get(entry.account_code, ""),
                "counterparty": entry.counterparty_canonical,
                "ambiguous": entry.ambiguous,
                "alternate_account_code": entry.alternate_account_code,
            }
        )
    return cases


def main() -> None:
    cases = build_cases()
    world = build_world()

    with CASES_PATH.open("w", encoding="utf-8", newline="\n") as fh:
        for case in cases:
            fh.write(json.dumps(case, ensure_ascii=False, sort_keys=True) + "\n")

    ambiguous = sum(1 for c in cases if c["ambiguous"])
    accounts = len({c["expected_account_code"] for c in cases})
    print(f"wrote {CASES_PATH.relative_to(EVALS_DIR.parent)}  ({len(cases)} cases)")
    print(f"  profile={PROFILE} seed={SEED}  world hash={world.content_hash()[:16]}…")
    print(f"  ambiguous cases: {ambiguous}   distinct accounts covered: {accounts}/20")


if __name__ == "__main__":
    main()
