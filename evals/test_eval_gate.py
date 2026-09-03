"""The CI gate — spec 11 section 10.

    "metrics: accuracy, auto-precision (accuracy of auto-applied only: must be >= 95%),
     queue-recall (wrong ones must land in queue, not auto). CI gate on auto-precision."

⚠️ **What a passing gate here does and does not mean.** In CI this runs against
`MockCategorizer`, so the number measures the *harness* — that scoring, routing, the CoA gate
and memory promotion all behave — not the quality of a real model. The mock is a fixture with
deliberately planted defects; the gate's job is to prove those defects are detected and
correctly routed. The real quality number comes from `make eval-live` (BLOCKERS.md B3), and
README STATUS says so plainly.

The gate is deliberately more than one assertion, because auto-precision alone is gameable: an
agent that queues everything auto-applies nothing and scores a perfect 100%. So the minimum
auto-rate is checked too.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness import AUTO_PRECISION_GATE, CASES_PATH, load_cases, run_eval

pytestmark = pytest.mark.eval

# An agent that queues everything would score 100% auto-precision while being useless.
MIN_AUTO_RATE = 0.50

# Regression floor on queue-recall. Fixture-calibrated (measured at 0.40), not a spec number:
# it exists to catch a change that starts auto-applying errors it used to queue.
MIN_QUEUE_RECALL = 0.30

# The planted defects must actually be found, or the gate is measuring nothing.
MIN_WRONG_ANSWERS = 1
MIN_OUT_OF_COA_CAUGHT = 1


@pytest.fixture(scope="module")
def report():
    """One eval run shared by every assertion below, and written out as a CI artifact."""
    result = run_eval()
    result.write()
    print(result.render())
    return result


# --- the case file -----------------------------------------------------------


def test_there_are_exactly_one_hundred_cases() -> None:
    """spec 11 section 10: "100 ledgerfab transactions with ground-truth categories"."""
    assert CASES_PATH.exists(), "run `python evals/build_cases.py`"
    assert len(load_cases()) == 100


def test_every_expected_account_is_in_the_coa() -> None:
    """ "CoA-aligned" — a label outside the chart of accounts would make every metric
    meaningless, since the agent could never produce it."""
    from app.coa import get_coa

    coa = get_coa()
    for case in load_cases():
        assert coa.is_valid(str(case["expected_account_code"])), (
            f"{case['case_id']} expects {case['expected_account_code']}, which is not in the CoA"
        )


def test_the_cases_do_not_leak_the_account_code() -> None:
    """The agent sees the descriptor, never the label. An account *code* appearing in a field
    the agent reads would make the suite measure nothing.

    Only the code is checked, not the account name. A vendor legitimately named
    "Hiscox Insurance" whose account is "Insurance" is not a leak — that is exactly the signal
    a bookkeeper uses, and forbidding it would mean testing the agent on a world less
    informative than the real one.
    """
    for case in load_cases():
        visible = " ".join(str(case.get(field, "")) for field in ("vendor_raw", "memo", "date_raw", "currency"))
        assert str(case["expected_account_code"]) not in visible, f"{case['case_id']} leaks its own answer: {visible!r}"


def test_the_suite_includes_deliberately_ambiguous_cases() -> None:
    """spec 11 section 14: CoA ambiguity must be "tested with deliberately ambiguous eval
    cases"."""
    assert sum(1 for c in load_cases() if c["ambiguous"]) >= 10


def test_the_suite_covers_most_of_the_chart_of_accounts() -> None:
    """A suite concentrated in two accounts would say nothing about the other eighteen."""
    assert len({c["expected_account_code"] for c in load_cases()}) >= 15


# --- THE GATE ----------------------------------------------------------------


def test_auto_precision_meets_the_gate(report) -> None:
    """spec 11 section 10: auto-precision "must be >= 95%". This is the CI gate."""
    assert report.auto_precision >= AUTO_PRECISION_GATE, (
        f"auto-precision {100 * report.auto_precision:.2f}% is below the "
        f"{100 * AUTO_PRECISION_GATE:.0f}% gate. "
        f"{report.wrong_total - report.wrong_queued} wrong answers were auto-applied: "
        f"{[r.case_id for r in report.results if r.auto and not r.correct]}"
    )


def test_the_agent_actually_auto_applies_things(report) -> None:
    """Closes the loophole in the gate above: queue everything and auto-precision is a
    meaningless 100%."""
    assert report.auto_rate >= MIN_AUTO_RATE, (
        f"auto-rate {100 * report.auto_rate:.1f}% is too low for the auto-precision figure to mean anything"
    )


def test_wrong_answers_land_in_the_queue(report) -> None:
    """Queue-recall: of the decisions the agent got wrong, how many did it queue rather than
    post? This is the honesty metric — being wrong is survivable, being confidently wrong is
    what costs a bookkeeper their afternoon."""
    assert report.queue_recall >= MIN_QUEUE_RECALL, (
        f"queue-recall {100 * report.queue_recall:.1f}%: "
        f"{report.wrong_total - report.wrong_queued} of {report.wrong_total} wrong answers were auto-applied"
    )


def test_out_of_coa_answers_are_always_queued(report) -> None:
    """spec 11 section 8. Not one may be auto-applied, at any confidence."""
    leaked = [r for r in report.results if not r.coa_valid and r.auto]
    assert leaked == [], f"out-of-CoA answers were auto-applied: {[r.case_id for r in leaked]}"


# --- the gate must be capable of failing -------------------------------------


def test_the_fixture_actually_contains_errors(report) -> None:
    """The point of PLAN.md D8. If the mock were perfect, every metric above would pass by
    construction and prove nothing. This test fails if someone "improves" the mock into an
    oracle — which is exactly what happened in the first draft of this phase."""
    assert report.wrong_total >= MIN_WRONG_ANSWERS, (
        "the eval fixture produced zero wrong answers, so auto-precision and queue-recall "
        "are vacuous. See the calibration note in app/agent/llm.py."
    )
    assert report.out_of_coa >= MIN_OUT_OF_COA_CAUGHT, (
        "no out-of-CoA answer was produced, so the spec 11 section 8 gate is untested here"
    )


def test_a_deliberately_bad_agent_fails_the_gate() -> None:
    """Proves the gate has teeth by running an agent that is confidently wrong about
    everything. If this passed, the gate would be decoration."""
    from app.agent.llm import CategorySuggestion, LlmResult

    class ConfidentlyWrong:
        name = "confidently-wrong"

        def categorize(self, **kwargs):  # type: ignore[no-untyped-def]
            # A real account code, high confidence, applied to every transaction.
            return LlmResult(
                suggestion=CategorySuggestion(account_code="6000", confidence=0.99, reason="always ads"),
                prompt_tokens=1000,
                completion_tokens=60,
            )

    bad = run_eval(categorizer=ConfidentlyWrong(), mode="mock")

    assert bad.auto_precision < AUTO_PRECISION_GATE
    assert bad.passed is False
    assert bad.queue_recall < 0.5, "a confidently-wrong agent should queue almost nothing"


# --- the report --------------------------------------------------------------


def test_the_report_is_written_for_ci(report) -> None:
    path = Path(report.write())
    assert path.exists()

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["summary"]["total_cases"] == 100
    assert len(payload["cases"]) == 100
    # The mode must be recorded, so a mock-mode number can never be mistaken for a live one.
    assert payload["summary"]["mode"] in {"mock", "live"}


def test_the_report_records_which_cases_were_wrong(report) -> None:
    """A gate that only emits a percentage is not debuggable. The failing case ids have to be
    in the artifact."""
    payload = json.loads(Path(report.write()).read_text(encoding="utf-8"))
    wrong = [c for c in payload["cases"] if c["predicted"] != c["expected"]]
    assert len(wrong) == report.wrong_total
