"""Chart of accounts: loading, validation, and the gate of spec 11 section 8.

    "account_code must be in the CoA (validated in code; out-of-CoA = forced low
     confidence + queue)"

Membership is decided here, in code. The half of that rule about forcing low confidence and
queueing is exercised in `test_coa_gate.py` once the graph exists (P4); this module proves the
decision itself is sound and cannot be talked out of by a model.
"""

from __future__ import annotations

import pytest

from app.coa import ChartOfAccounts, CoaAccount, load_coa, parse_coa
from app.settings import REPO_ROOT
from ledgerfab.coa import DEFAULT_COA

VALID_YAML = """
accounts:
  - code: "6000"
    name: "Advertising & Marketing"
    description: "Ads and campaigns"
  - code: "6060"
    name: "Office Supplies"
"""


# --- the gate ----------------------------------------------------------------


def test_membership_is_decided_in_code(coa: ChartOfAccounts) -> None:
    assert coa.is_valid("6000") is True
    assert coa.is_valid("6190") is True


@pytest.mark.parametrize(
    "hallucinated",
    [
        "9999",  # plausible shape, not in the CoA
        "6001",  # one digit off a real account
        "6000 ",  # trailing space
        " 6000",
        "Advertising",  # the name instead of the code
        "6000-01",  # sub-account that does not exist
        "",
        None,
    ],
)
def test_anything_not_in_the_chart_is_invalid(coa: ChartOfAccounts, hallucinated: str | None) -> None:
    """These are the shapes a model actually returns when it is guessing. Every one of them
    must fail closed, so the row is queued for a human instead of silently posted."""
    assert coa.is_valid(hallucinated) is False


def test_the_chart_has_no_catch_all_account(coa: ChartOfAccounts) -> None:
    """A "Miscellaneous" or "Uncategorized" account would give the agent somewhere to hide a
    guess, which defeats the entire confidence gate."""
    banned = {"uncategorized", "misc", "miscellaneous", "other", "suspense", "unknown", "general"}
    names = {a.name.strip().lower() for a in coa.accounts}
    assert not (names & banned), f"the CoA contains a dumping ground: {names & banned}"


# --- alignment with ledgerfab -------------------------------------------------


def test_the_shipped_coa_matches_ledgerfab(coa: ChartOfAccounts) -> None:
    """spec 11 section 10 requires eval ground truth to be "CoA-aligned". `coa_default.yaml`
    is generated from `ledgerfab/coa.py`, and this test is what stops the two drifting: if it
    fails, run `make seed`."""
    assert coa.codes == {a.code for a in DEFAULT_COA}
    assert [a.name for a in coa.accounts] == [a.name for a in DEFAULT_COA]


def test_em_dash_account_names_survive_the_round_trip(coa: ChartOfAccounts) -> None:
    """Measured, not assumed: this machine's locale default is cp1252, which silently renders
    "Travel — Airfare" as "Travel â€” Airfare". The loader must be explicit about UTF-8
    (PLAN.md D15)."""
    travel = [a.name for a in coa.accounts if a.name.startswith("Travel")]
    assert travel, "expected the Travel accounts"
    assert all("—" in name for name in travel)
    assert not any("â€" in name for name in travel)


def test_the_default_file_loads_from_disk() -> None:
    coa = load_coa(REPO_ROOT / "backend" / "app" / "coa_default.yaml")
    assert len(coa) == 20


# --- parsing ------------------------------------------------------------------


def test_a_minimal_valid_document_parses() -> None:
    coa = parse_coa(VALID_YAML)
    assert len(coa) == 2
    assert coa.name_for("6000") == "Advertising & Marketing"
    assert coa.get("6060") is not None
    assert coa.get("6060").description == ""  # type: ignore[union-attr]


def test_numeric_codes_are_read_as_strings() -> None:
    """YAML reads a bare `6000` as an int. If that reached the gate, no string answer from a
    model would ever match, and every single row would be queued."""
    coa = parse_coa("accounts:\n  - code: 6000\n    name: Advertising\n")
    assert coa.codes == {"6000"}
    assert coa.is_valid("6000") is True


@pytest.mark.parametrize(
    ("bad", "message"),
    [
        ("accounts: []", "empty"),
        ("[]", "mapping"),
        ("not yaml at all", "mapping"),
        ("accounts:\n  - name: No Code\n", "code"),
        ("accounts:\n  - code: '6000'\n", "name"),
        ("accounts:\n  - code: ''\n    name: Blank\n", "blank code"),
        ("accounts:\n  - code: '6000'\n    name: A\n  - code: '6000'\n    name: B\n", "duplicate"),
        ("accounts:\n  - just a string\n", "not a mapping"),
        ("accounts: 42", "must be a list"),
    ],
)
def test_invalid_documents_are_rejected_with_a_useful_message(bad: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        parse_coa(bad)


def test_prompt_block_lists_every_account_once(coa: ChartOfAccounts) -> None:
    """This block is what the model actually sees, so a missing account is an account the
    model can never choose."""
    block = coa.prompt_block()
    assert len(block.splitlines()) == len(coa)
    for account in coa.accounts:
        assert account.code in block
        assert account.name in block


def test_descriptions_reach_the_prompt() -> None:
    """Descriptions are what separate two near-neighbour accounts, so they must not be
    silently dropped from the prompt."""
    account = CoaAccount(code="6150", name="Travel — Ground", description="Taxis, rideshare, rail")
    assert "Taxis" in account.prompt_line()


# --- the API ------------------------------------------------------------------


def test_get_coa_returns_the_whole_chart(client) -> None:
    resp = client.get("/api/coa")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 20
    assert len(body["accounts"]) == 20
    assert {"code", "name", "kind", "description"} <= body["accounts"][0].keys()


def test_get_coa_yaml_returns_the_editable_source(client) -> None:
    resp = client.get("/api/coa/yaml")
    assert resp.status_code == 200
    assert "accounts:" in resp.json()["yaml"]


def test_put_coa_rejects_an_invalid_document_without_writing_it(client) -> None:
    """A bad edit must fail at the edit, not at the next categorization run."""
    before = client.get("/api/coa").json()["count"]

    resp = client.put("/api/coa", json={"yaml": "accounts: []"})
    assert resp.status_code == 422
    assert "invalid CoA" in resp.json()["detail"]

    assert client.get("/api/coa").json()["count"] == before


def test_put_coa_accepts_a_valid_document(client, tmp_path, monkeypatch) -> None:
    """Written to a temp path so the test cannot damage the shipped default CoA."""
    from app.coa import reload_coa
    from app.settings import get_settings

    target = tmp_path / "coa.yaml"
    monkeypatch.setattr(get_settings(), "coa_path", target)

    try:
        resp = client.put("/api/coa", json={"yaml": VALID_YAML})
        assert resp.status_code == 200, resp.text
        assert resp.json()["count"] == 2
        assert target.exists()
    finally:
        monkeypatch.undo()
        reload_coa()
