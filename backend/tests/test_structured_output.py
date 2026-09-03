"""The enforced output contract — spec 11 section 8.

    "Structured output enforced (Pydantic): account_code must be in the CoA (validated in
     code; out-of-CoA = forced low confidence + queue). Reason <= 20 words. Temperature 0.1."

Membership is covered by `test_coa_validation.py` and the queueing consequence by
`test_routing_threshold.py`. This module covers the two clauses that had no test at all until
an audit of PLAN.md's own traceability table found them missing: the **20-word cap** and
**temperature 0.1**.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.agent.llm import (
    MAX_REASON_WORDS,
    CategorySuggestion,
    MockCategorizer,
    OpenAICategorizer,
    build_categorizer,
)
from app.coa import get_coa
from app.settings import get_settings


def suggest(**kwargs) -> CategorySuggestion:  # type: ignore[no-untyped-def]
    return CategorySuggestion(**{"account_code": "6060", "confidence": 0.9, "reason": "ok", **kwargs})


# --- "Reason <= 20 words" ----------------------------------------------------


def test_the_cap_is_twenty_words() -> None:
    assert MAX_REASON_WORDS == 20


def test_a_long_reason_is_truncated_not_rejected() -> None:
    """Truncation, deliberately, not rejection. A model that rambles has still given a usable
    answer; failing the whole run over prose length would be the wrong trade."""
    long_reason = " ".join(f"word{i}" for i in range(50))
    result = suggest(reason=long_reason)

    words = result.reason.rstrip("…").split()
    assert len(words) == MAX_REASON_WORDS
    assert result.reason.endswith("…"), "a truncated reason should show that it was cut"
    # The beginning survives, so the reviewer still sees the model's actual argument.
    assert result.reason.startswith("word0 word1")


@pytest.mark.parametrize("count", [1, 5, 19, 20])
def test_a_reason_within_the_cap_is_untouched(count: int) -> None:
    reason = " ".join(f"w{i}" for i in range(count))
    assert suggest(reason=reason).reason == reason
    assert "…" not in suggest(reason=reason).reason


def test_reason_whitespace_is_collapsed() -> None:
    """Ragged whitespace would make the word count lie."""
    assert suggest(reason="  matched   the   vendor  ").reason == "matched the vendor"


def test_every_mock_reason_respects_the_cap() -> None:
    """The mock feeds the whole default test run and the demo, so its own output must obey the
    contract too."""
    coa_block = get_coa().prompt_block()
    mock = MockCategorizer()

    for vendor in ("AMAZON MARKETPLACE", "BRIGHTLINE CLEANING", "SLACK", "HARBOR & VANCE", "UNKNOWN THING"):
        result = mock.categorize(
            coa_block=coa_block,
            vendor_raw=vendor,
            vendor_norm=vendor,
            amount=10.0,
            currency="USD",
            date="2026-01-01",
            memo=None,
        )
        assert len(result.suggestion.reason.rstrip("…").split()) <= MAX_REASON_WORDS


# --- the rest of the shape ---------------------------------------------------


def test_account_code_is_stripped() -> None:
    """Models pad codes. An unstripped value would never match the CoA, so every row would
    queue forever."""
    assert suggest(account_code="  6060 ").account_code == "6060"


@pytest.mark.parametrize("confidence", [0.0, 0.5, 1.0])
def test_confidence_accepts_the_whole_valid_range(confidence: float) -> None:
    assert suggest(confidence=confidence).confidence == confidence


@pytest.mark.parametrize("confidence", [-0.1, 1.1, 2.0, -1.0])
def test_confidence_outside_zero_to_one_is_rejected(confidence: float) -> None:
    """A confidence of 1.4 is not a very sure answer; it is a broken one. Rejecting it at the
    boundary stops it reaching the gate, where it would auto-apply."""
    with pytest.raises(ValidationError):
        suggest(confidence=confidence)


def test_all_three_fields_are_required() -> None:
    """The graph reads all three unconditionally, so a missing one must fail loudly here."""
    for missing in ("account_code", "confidence", "reason"):
        payload = {"account_code": "6060", "confidence": 0.9, "reason": "ok"}
        del payload[missing]
        with pytest.raises(ValidationError):
            CategorySuggestion(**payload)  # type: ignore[arg-type]


# --- "Temperature 0.1" -------------------------------------------------------


def test_the_default_temperature_is_point_one() -> None:
    assert get_settings().temperature == 0.1


def test_the_openai_client_is_built_at_the_configured_temperature() -> None:
    """The setting has to actually reach the model, not just exist. Constructed without
    touching the network — no key needed, no call made."""
    categorizer = OpenAICategorizer()

    assert categorizer.temperature == get_settings().temperature == 0.1
    assert categorizer.model == get_settings().model
    assert "openai" in categorizer.name


def test_an_explicit_temperature_overrides_the_default() -> None:
    assert OpenAICategorizer(temperature=0.0).temperature == 0.0


# --- which implementation gets used ------------------------------------------


def test_the_default_test_run_uses_the_mock() -> None:
    """Adaptation 3: the LLM is mocked by default, so no test spends money or needs a key."""
    assert isinstance(build_categorizer(), MockCategorizer)
    assert get_settings().use_mock_llm is True


def test_mock_answers_are_deterministic() -> None:
    """Evals and tests are only reproducible if the same vendor always yields the same answer."""
    mock = MockCategorizer()
    args = {
        "coa_block": get_coa().prompt_block(),
        "vendor_raw": "AMZN Mktp US*Y7D8K6",
        "vendor_norm": "AMAZON MARKETPLACE",
        "amount": 120.0,
        "currency": "USD",
        "date": "2026-01-01",
        "memo": None,
    }
    first = mock.categorize(**args)
    second = MockCategorizer().categorize(**args)

    assert first.suggestion == second.suggestion
