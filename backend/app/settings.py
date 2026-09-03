"""Runtime configuration, env-driven (pydantic-settings, per spec 00 A1).

Every number that governs trust — the auto-apply threshold, the per-run cost cap — lives here
so it can be tuned without a code change and read back in the UI.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/settings.py -> backend/app -> backend -> <repo root>
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SPENDSORT_",
        env_file=(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- app -------------------------------------------------------------
    app_name: str = "SpendSort"
    env: str = "dev"
    log_level: str = "INFO"

    # --- persistence -----------------------------------------------------
    database_url: str = f"sqlite:///{(BACKEND_ROOT / 'spendsort.db').as_posix()}"

    # --- the confidence gate (spec 11 section 4 F2) ----------------------
    # Decisions at or above this auto-apply; everything else goes to the review queue.
    # Starting value per PLAN.md D10; re-derived from eval results in P5.
    auto_threshold: float = Field(default=0.85, ge=0.0, le=1.0)

    # --- cost control (spec 11 section 11: "cost cap per run (default $0.25)") ---
    cost_cap_usd_per_run: float = Field(default=0.25, gt=0.0)

    # Token prices in USD per 1M tokens. Set BOTH to override the table in app/costs.py
    # without a code change — prices move, and MODEL_COSTS.md must not go stale (D6, B4).
    price_input_per_1m: float | None = None
    price_output_per_1m: float | None = None

    # --- LLM (spec 00 F: OpenAI API on Track 1; spec 11 section 8: temperature 0.1) ---
    openai_api_key: str | None = None
    model: str = "gpt-4o-mini"
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    max_reason_words: int = 20  # spec 11 section 8: "Reason <= 20 words."

    # Mock mode is a first-class code path, not a test-only shim (BLOCKERS.md B3):
    # the entire demo runs end to end with zero spend and no API key.
    mock_llm: bool = False

    # --- intake hardening (spec 11 section 11: "CSV hardening") ----------
    max_upload_bytes: int = 5 * 1024 * 1024
    max_rows_per_upload: int = 5_000

    # --- chart of accounts ------------------------------------------------
    coa_path: Path = BACKEND_ROOT / "app" / "coa_default.yaml"

    @field_validator("log_level")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()

    @property
    def llm_available(self) -> bool:
        """True when a real LLM call is possible. Mock mode never needs a key."""
        return bool(self.openai_api_key) and not self.mock_llm

    @property
    def use_mock_llm(self) -> bool:
        """Mock when explicitly asked, or whenever no key exists (so the demo still runs)."""
        return self.mock_llm or not self.openai_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
