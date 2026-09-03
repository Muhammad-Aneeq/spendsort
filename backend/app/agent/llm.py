"""The LLM boundary: enforced structured output, and a mock that can fail.

spec 11 section 8: "Structured output enforced (Pydantic) ... Reason <= 20 words.
Temperature 0.1."

Two implementations sit behind one protocol:

* `OpenAICategorizer` — `langchain-openai` with `with_structured_output`, so the shape is
  enforced at the tool-call layer and the model retries rather than us parsing prose.
* `MockCategorizer` — a deterministic stand-in used by the whole default test run and by the
  zero-cost demo (BLOCKERS.md B3).

**The mock is deliberately imperfect** (PLAN.md D8). A mock that always answered correctly
would make the >=95% auto-precision gate and the queue-recall metric meaningless: they would
pass by construction and prove nothing. So it gets some vendors wrong, returns one out-of-CoA
code, and is genuinely unsure about genuinely ambiguous vendors. The gate has to be able to
fail, or it is decoration.
"""

from __future__ import annotations

import hashlib
from typing import Protocol

from pydantic import BaseModel, Field, field_validator

from app.agent.prompts import build_messages
from app.costs import ESTIMATED_COMPLETION_TOKENS, ESTIMATED_PROMPT_TOKENS
from app.settings import get_settings

MAX_REASON_WORDS = 20


class CategorySuggestion(BaseModel):
    """The enforced output shape (spec 11 section 4 F2)."""

    account_code: str = Field(description="A code copied exactly from the chart of accounts")
    confidence: float = Field(ge=0.0, le=1.0, description="Genuine probability this account is correct")
    reason: str = Field(description="At most 20 words, citing what in the descriptor decided it")

    @field_validator("account_code")
    @classmethod
    def _strip_code(cls, v: str) -> str:
        # Models like to pad codes. Membership is checked in app/coa.py, but the value has to
        # be comparable before it gets there.
        return v.strip()

    @field_validator("reason")
    @classmethod
    def _cap_reason(cls, v: str) -> str:
        """Enforce "Reason <= 20 words" by truncation rather than rejection.

        A model that rambles has still given a usable answer; failing the whole run over
        prose length would be the wrong trade.
        """
        words = v.strip().split()
        if len(words) <= MAX_REASON_WORDS:
            return " ".join(words)
        return " ".join(words[:MAX_REASON_WORDS]) + "…"


class LlmResult(BaseModel):
    suggestion: CategorySuggestion
    prompt_tokens: int = 0
    completion_tokens: int = 0


class Categorizer(Protocol):
    """What `llm_categorize` depends on. Narrow on purpose, so tests can inject anything."""

    name: str

    def categorize(
        self,
        *,
        coa_block: str,
        vendor_raw: str,
        vendor_norm: str,
        amount: float,
        currency: str,
        date: str,
        memo: str | None,
    ) -> LlmResult: ...


# --- the real thing ----------------------------------------------------------


class OpenAICategorizer:
    """langchain-openai with structured output. Track 1 per spec 00 F."""

    def __init__(self, model: str | None = None, temperature: float | None = None) -> None:
        settings = get_settings()
        self.model = model or settings.model
        self.temperature = temperature if temperature is not None else settings.temperature
        self.name = f"openai:{self.model}"
        self._client = None

    def _structured(self):  # type: ignore[no-untyped-def]
        if self._client is None:
            # Imported lazily so the app boots (and the whole mock-mode demo runs) without
            # langchain-openai ever being constructed or a key being present.
            from langchain_openai import ChatOpenAI

            settings = get_settings()
            self._client = ChatOpenAI(
                model=self.model,
                temperature=self.temperature,
                api_key=settings.openai_api_key,
                timeout=30,
                max_retries=2,
            ).with_structured_output(CategorySuggestion, include_raw=True)
        return self._client

    def categorize(
        self,
        *,
        coa_block: str,
        vendor_raw: str,
        vendor_norm: str,
        amount: float,
        currency: str,
        date: str,
        memo: str | None,
    ) -> LlmResult:
        messages = build_messages(
            coa_block=coa_block,
            vendor_raw=vendor_raw,
            vendor_norm=vendor_norm,
            amount=amount,
            currency=currency,
            date=date,
            memo=memo,
        )
        raw = self._structured().invoke(messages)

        # include_raw=True gives {"raw": AIMessage, "parsed": CategorySuggestion, ...} so real
        # token counts can be read instead of estimated.
        suggestion = raw["parsed"] if isinstance(raw, dict) else raw
        prompt_tokens, completion_tokens = ESTIMATED_PROMPT_TOKENS, ESTIMATED_COMPLETION_TOKENS
        if isinstance(raw, dict) and raw.get("raw") is not None:
            usage = getattr(raw["raw"], "usage_metadata", None) or {}
            prompt_tokens = int(usage.get("input_tokens", prompt_tokens))
            completion_tokens = int(usage.get("output_tokens", completion_tokens))

        if suggestion is None:
            # Structured output failed after retries. Fail closed: no answer, no confidence,
            # so `route` queues it for a human.
            return LlmResult(
                suggestion=CategorySuggestion(
                    account_code="", confidence=0.0, reason="model returned no parseable answer"
                ),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )

        return LlmResult(suggestion=suggestion, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)


# --- the mock ----------------------------------------------------------------

# Vendor-key substring -> account code. Covers the ledgerfab catalogue well but not perfectly,
# which is the intent: this stands in for a competent-but-fallible model.
_MOCK_RULES: tuple[tuple[str, str], ...] = (
    ("GOOGLE ADS", "6000"),
    ("META", "6000"),
    ("LINKEDIN", "6000"),
    ("STRIPE", "6010"),
    ("SERVICE CHARGE", "6010"),
    ("ANALYSIS FEE", "6010"),
    ("WIRE FEE", "6010"),
    ("NORTHWEST BANK", "6010"),
    ("APPLE", "6020"),
    ("ITUNES", "6020"),
    ("DELL", "6020"),
    ("BEST BUY", "6020"),
    ("BESTBUY", "6020"),
    ("SLACK", "6030"),
    ("NOTION", "6030"),
    ("ADOBE", "6030"),
    ("FIGMA", "6030"),
    ("GITHUB", "6030"),
    ("ZOOM", "6030"),
    ("MICROSOFT", "6030"),
    ("HISCOX", "6040"),
    ("STARBUCKS", "6050"),
    ("CHIPOTLE", "6050"),
    ("DOORDASH", "6050"),
    ("BLUE BOTTLE", "6050"),
    ("AMAZON MARKETPLACE", "6060"),
    ("AMAZON", "6060"),
    ("STAPLES", "6060"),
    ("COSTCO", "6060"),
    ("FEDEX", "6070"),
    ("UPS", "6070"),
    ("HARBOR", "6080"),
    ("QUILL", "6080"),
    ("WEWORK", "6090"),
    ("WE WORK", "6090"),
    ("PUBLIC STORAGE", "6090"),
    ("PUBLICSTORAGE", "6090"),
    ("BRIGHTLINE", "6100"),
    ("ACME", "6100"),
    ("VERIZON", "6110"),
    ("COMCAST", "6110"),
    ("CABLE COMM", "6110"),
    ("UDEMY", "6120"),
    ("OREILLY", "6120"),
    ("UNITED", "6130"),
    ("DELTA", "6130"),
    ("MARRIOTT", "6140"),
    ("AIRBNB", "6140"),
    ("UBER", "6150"),
    ("LYFT", "6150"),
    ("AMTRAK", "6150"),
    ("CON ED", "6160"),
    ("CONED", "6160"),
    ("CONSOLIDATED EDISON", "6160"),
    ("WATER", "6160"),
    ("GUSTO", "6170"),
    ("UPWORK", "6170"),
    ("SHELL", "6180"),
    ("EZPASS", "6180"),
    ("AMAZON WEB SERVICES", "6190"),
    ("AWS", "6190"),
    ("GOOGLE CLOUD", "6190"),
    ("VERCEL", "6190"),
    ("CLOUDFLARE", "6190"),
)

# Vendors the mock is genuinely unsure about — it still answers, but below any sane threshold,
# so the row is queued. This is what makes queue-recall a real measurement.
_MOCK_UNSURE: frozenset[str] = frozenset(
    {"AMAZON", "UBER", "AIRBNB", "BEST BUY", "BESTBUY", "COSTCO", "APPLE", "UDEMY", "AMTRAK", "UPWORK"}
)

# Deliberate defects, so the gate can fail (PLAN.md D8):
#   * one confidently WRONG answer  -> auto-precision cannot be 100%
#   * one OUT-OF-CoA code           -> exercises the spec 11 section 8 gate
_MOCK_CONFIDENTLY_WRONG: dict[str, str] = {"BLUE BOTTLE COFFEE": "6060", "BLUE BOTTLE": "6060"}
_MOCK_OUT_OF_COA: frozenset[str] = frozenset({"FIRST NORTHWEST BANK"})


class MockCategorizer:
    """Deterministic, offline, and imperfect on purpose.

    Same vendor key always yields the same answer, so evals and tests are reproducible.
    """

    name = "mock"

    def categorize(
        self,
        *,
        coa_block: str,
        vendor_raw: str,
        vendor_norm: str,
        amount: float,
        currency: str,
        date: str,
        memo: str | None,
    ) -> LlmResult:
        key = vendor_norm.upper()

        if key in _MOCK_OUT_OF_COA:
            # A hallucinated account code, stated with confidence. The CoA gate must catch
            # this in code — the model's own confidence is no defence.
            return self._result("9999", 0.94, f"mock: hallucinated code for {key[:24]}")

        if key in _MOCK_CONFIDENTLY_WRONG:
            return self._result(_MOCK_CONFIDENTLY_WRONG[key], 0.93, f"mock: confidently wrong on {key[:20]}")

        code = self._match(key)
        if code is None:
            return self._result("", 0.10, "mock: descriptor not recognised")

        unsure = any(token in _MOCK_UNSURE for token in (key, key.split(" ")[0]))
        confidence = self._jitter(key, 0.42, 0.72) if unsure else self._jitter(key, 0.86, 0.97)
        return self._result(code, confidence, f"mock: matched {key[:24]}")

    # --- helpers -------------------------------------------------------
    @staticmethod
    def _match(key: str) -> str | None:
        # Longest rule first, so "AMAZON WEB SERVICES" beats "AMAZON".
        for needle, code in sorted(_MOCK_RULES, key=lambda r: -len(r[0])):
            if needle in key:
                return code
        return None

    @staticmethod
    def _jitter(key: str, low: float, high: float) -> float:
        """Stable pseudo-random confidence in [low, high], derived from the vendor key."""
        digest = hashlib.sha256(key.encode()).digest()
        fraction = int.from_bytes(digest[:4], "big") / 0xFFFFFFFF
        return round(low + fraction * (high - low), 3)

    @staticmethod
    def _result(code: str, confidence: float, reason: str) -> LlmResult:
        return LlmResult(
            suggestion=CategorySuggestion(account_code=code, confidence=confidence, reason=reason),
            # Realistic token counts, so mock-mode cost figures are illustrative rather than zero.
            prompt_tokens=ESTIMATED_PROMPT_TOKENS,
            completion_tokens=ESTIMATED_COMPLETION_TOKENS,
        )


def build_categorizer() -> Categorizer:
    """Pick an implementation. Mock whenever asked, or whenever there is no API key."""
    return MockCategorizer() if get_settings().use_mock_llm else OpenAICategorizer()
