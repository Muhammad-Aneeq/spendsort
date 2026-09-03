"""The CI gate (spec 11 section 10).

    "metrics: accuracy, auto-precision (accuracy of auto-applied only: must be >= 95%),
     queue-recall (wrong ones must land in queue, not auto). CI gate on auto-precision."

P1 status: placeholder so `make eval` is an honest empty pass (spec 00 A1 acceptance).
The real suite — 100 ledgerfab transactions with ground truth — lands in P5.
"""

from __future__ import annotations

from pathlib import Path

import pytest

CASES = Path(__file__).parent / "cases.jsonl"

pytestmark = pytest.mark.eval


@pytest.mark.skipif(not CASES.exists(), reason="evals/cases.jsonl lands in P5 (see PLAN.md)")
def test_auto_precision_gate() -> None:
    raise AssertionError("replaced in P5")
