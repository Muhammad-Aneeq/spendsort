"""Chart of accounts: load, validate, and gate.

spec 11 section 4 F1: "chart of accounts as editable YAML (ship a sensible default CoA)".
spec 11 section 8: "account_code must be in the CoA (validated in code; out-of-CoA = forced
low confidence + queue)".

The validation lives here, in code, and is the single place that decides whether a model's
answer names a real account. Nothing downstream trusts the model's word for it.

Note the explicit `encoding="utf-8"`: three account names contain an em-dash, and this
machine's locale default (cp1252) silently corrupts them (PLAN.md D15).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from app.settings import get_settings


@dataclass(frozen=True, slots=True)
class CoaAccount:
    code: str
    name: str
    kind: str = "expense"
    description: str = ""

    def prompt_line(self) -> str:
        """One line for the LLM prompt. The description is what disambiguates two near-neighbours."""
        return f"{self.code} — {self.name}: {self.description}" if self.description else f"{self.code} — {self.name}"


class ChartOfAccounts:
    """An immutable, validated chart of accounts."""

    def __init__(self, accounts: list[CoaAccount]) -> None:
        if not accounts:
            raise ValueError("chart of accounts is empty — nothing could ever be categorized")

        seen: set[str] = set()
        for acct in accounts:
            if not acct.code.strip():
                raise ValueError(f"account {acct.name!r} has a blank code")
            if acct.code in seen:
                raise ValueError(f"duplicate account code {acct.code!r} in the chart of accounts")
            seen.add(acct.code)

        self._accounts = tuple(accounts)
        self._by_code = {a.code: a for a in accounts}

    # --- the gate --------------------------------------------------------
    def is_valid(self, code: str | None) -> bool:
        """The whole point of spec 11 section 8: membership is decided here, not by the model."""
        return bool(code) and code in self._by_code

    def get(self, code: str) -> CoaAccount | None:
        return self._by_code.get(code)

    # --- access ----------------------------------------------------------
    @property
    def accounts(self) -> tuple[CoaAccount, ...]:
        return self._accounts

    @property
    def codes(self) -> frozenset[str]:
        return frozenset(self._by_code)

    def name_for(self, code: str) -> str:
        acct = self._by_code.get(code)
        return acct.name if acct else code

    def prompt_block(self) -> str:
        """The CoA as the model sees it."""
        return "\n".join(a.prompt_line() for a in self._accounts)

    def __len__(self) -> int:
        return len(self._accounts)

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self._accounts)


def parse_coa(raw: str) -> ChartOfAccounts:
    """Parse the editable YAML. `safe_load` only — this file is user-editable."""
    data = yaml.safe_load(raw)
    if not isinstance(data, dict) or "accounts" not in data:
        raise ValueError("chart of accounts YAML must be a mapping with an 'accounts' key")

    rows = data["accounts"]
    if not isinstance(rows, list):
        raise ValueError("'accounts' must be a list")

    accounts: list[CoaAccount] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"account #{index + 1} is not a mapping")
        if "code" not in row or "name" not in row:
            raise ValueError(f"account #{index + 1} needs both 'code' and 'name'")
        accounts.append(
            CoaAccount(
                # str(): YAML would happily read a bare 6000 as an int, and then no lookup
                # against a model's string answer would ever match.
                code=str(row["code"]).strip(),
                name=str(row["name"]).strip(),
                kind=str(row.get("kind", "expense")).strip(),
                description=str(row.get("description", "")).strip(),
            )
        )
    return ChartOfAccounts(accounts)


def load_coa(path: Path | None = None) -> ChartOfAccounts:
    target = path or get_settings().coa_path
    if not target.exists():
        raise FileNotFoundError(f"chart of accounts not found at {target}")
    return parse_coa(target.read_text(encoding="utf-8"))


@lru_cache
def get_coa() -> ChartOfAccounts:
    """Cached accessor for request handlers. Cleared by `reload_coa()` after an edit."""
    return load_coa()


def reload_coa() -> ChartOfAccounts:
    get_coa.cache_clear()
    return get_coa()
