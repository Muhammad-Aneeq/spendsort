"""Generation knobs and presets (spec 00 A3).

Config knobs: partial_payment_rate, missing_reference_rate, duplicate_rate,
date_format_chaos, amount_noise, alias_rate, fx_rate (flag-only in v1).
Presets: clean / realistic / nightmare.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class Profile(BaseModel):
    """How messy the generated world should be. Every rate is a probability in [0, 1]."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = "custom"

    # --- the spec 00 A3 knobs -------------------------------------------
    partial_payment_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    missing_reference_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    duplicate_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    date_format_chaos: float = Field(default=0.0, ge=0.0, le=1.0)
    amount_noise: float = Field(default=0.0, ge=0.0, le=1.0)
    # The knob SpendSort cares about most: how often a vendor appears as a messy
    # bank descriptor rather than its clean name (spec 11 section 14).
    alias_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    # "fx_rate (flag-only in v1)": some rows are marked as foreign currency, but no
    # conversion is modelled. SpendSort does not do FX (spec 11 section 2 non-goals).
    fx_rate: float = Field(default=0.0, ge=0.0, le=1.0)

    # --- volume / period -------------------------------------------------
    txn_count: int = Field(default=120, gt=0)
    # Explicit, never `today()`: a generator that reads the clock is not reproducible.
    period_start: date = date(2026, 1, 1)
    period_days: int = Field(default=31, gt=0)

    # How often a transaction is drawn from a genuinely ambiguous vendor
    # (two defensible accounts). Drives the "confidence must drop" eval cases.
    ambiguous_rate: float = Field(default=0.0, ge=0.0, le=1.0)


CLEAN = Profile(
    name="clean",
    txn_count=120,
    # Nothing messy: clean names, one date format, exact amounts.
)

REALISTIC = Profile(
    name="realistic",
    partial_payment_rate=0.03,
    missing_reference_rate=0.25,
    duplicate_rate=0.02,
    date_format_chaos=0.15,
    amount_noise=0.30,
    alias_rate=0.65,
    fx_rate=0.03,
    ambiguous_rate=0.12,
    txn_count=120,
)

NIGHTMARE = Profile(
    name="nightmare",
    partial_payment_rate=0.12,
    missing_reference_rate=0.60,
    duplicate_rate=0.08,
    date_format_chaos=0.55,
    amount_noise=0.70,
    alias_rate=0.95,
    fx_rate=0.10,
    ambiguous_rate=0.28,
    txn_count=120,
)

PRESETS: dict[str, Profile] = {p.name: p for p in (CLEAN, REALISTIC, NIGHTMARE)}


def resolve_profile(profile: str | Profile) -> Profile:
    """Accept a preset name or a Profile instance."""
    if isinstance(profile, Profile):
        return profile
    try:
        return PRESETS[profile]
    except KeyError:
        known = ", ".join(sorted(PRESETS))
        raise ValueError(f"unknown profile {profile!r}; known presets: {known}") from None
