"""CSV intake and hardening — spec 11 section 4 F1 and section 11.

The governing rule: **one bad row must not lose the other 119.** A finance tool that rejects a
whole upload over a single blank amount is a tool nobody uses. So the tests below check both
halves: good rows land, bad rows are reported with a line number and a reason.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from app.services.ingest import (
    IngestError,
    parse_amount,
    parse_csv,
    parse_currency,
    parse_date,
)
from app.settings import REPO_ROOT
from tests.conftest import csv_bytes

LIMITS = {"max_bytes": 5 * 1024 * 1024, "max_rows": 5000}


def run(rows: list[str], header: str = "date,amount,currency,vendor,memo", **kw):
    return parse_csv(csv_bytes(rows, header), **{**LIMITS, **kw})


# --- dates: ledgerfab deliberately emits format chaos ------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026-01-04", date(2026, 1, 4)),
        ("2026/01/04", date(2026, 1, 4)),
        ("04 Jan 2026", date(2026, 1, 4)),
        ("4 January 2026", date(2026, 1, 4)),
        ("Jan 4, 2026", date(2026, 1, 4)),
        ("04.01.2026", date(2026, 1, 4)),
        # Slashes are read US-style (month first)...
        ("01/04/2026", date(2026, 1, 4)),
        ("01/04/26", date(2026, 1, 4)),
        # ...and hyphens EU-style (day first). Both are genuinely ambiguous in the wild;
        # picking by separator is a documented convention, and it is exactly the inverse of
        # how ledgerfab generates the chaos, so round-tripping is verified end to end.
        ("04-01-2026", date(2026, 1, 4)),
    ],
)
def test_date_format_chaos_is_parsed(raw: str, expected: date) -> None:
    assert parse_date(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "not a date", "2026-13-45", "99/99/9999"])
def test_unparseable_dates_are_rejected(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_date(raw)


# --- amounts -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("123.45", 123.45),
        ("1,234.56", 1234.56),
        ("$1,234.56", 1234.56),
        ("  42 ", 42.0),
        ("-99.99", -99.99),
        ("(123.45)", -123.45),  # accounting-style negative
        ("1.234,56", 1234.56),  # European
        ("123,45", 123.45),  # European, no thousands
        ("USD 500.00", 500.0),
    ],
)
def test_amount_formats(raw: str, expected: float) -> None:
    assert parse_amount(raw) == pytest.approx(expected)


@pytest.mark.parametrize("raw", ["", "   ", "abc", "-", ".", "$"])
def test_unparseable_amounts_are_rejected(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_amount(raw)


@pytest.mark.parametrize(("raw", "expected"), [("USD", "USD"), ("gbp", "GBP"), ("", "USD"), ("dollars", "USD")])
def test_currency_falls_back_to_the_default(raw: str, expected: str) -> None:
    assert parse_currency(raw) == expected


# --- hardening ---------------------------------------------------------------


def test_a_bad_row_does_not_lose_the_good_ones() -> None:
    report = run(
        [
            "2026-01-01,10.00,USD,Staples,INV-1",
            "not-a-date,20.00,USD,Amazon,INV-2",
            "2026-01-03,,USD,Figma,INV-3",
            "2026-01-04,40.00,USD,,INV-4",
            "2026-01-05,50.00,USD,Slack,INV-5",
        ]
    )
    assert report.accepted == 2
    assert report.rejected == 3
    assert [e.line for e in report.errors] == [3, 4, 5]
    assert "date" in report.errors[0].reason
    assert "amount" in report.errors[1].reason
    assert "vendor" in report.errors[2].reason


def test_oversized_upload_is_refused() -> None:
    with pytest.raises(IngestError, match="limit"):
        parse_csv(csv_bytes(["2026-01-01,1,USD,X,"]), max_bytes=10, max_rows=100)


def test_row_ceiling_truncates_and_says_so() -> None:
    report = run([f"2026-01-01,{i + 1}.00,USD,Vendor{i}," for i in range(20)], max_rows=5)
    assert report.accepted == 5
    assert report.truncated is True


def test_empty_file_is_refused() -> None:
    with pytest.raises(IngestError, match="empty"):
        parse_csv(b"", **LIMITS)


def test_missing_required_column_is_refused_with_a_useful_message() -> None:
    with pytest.raises(IngestError, match="missing required column"):
        parse_csv(csv_bytes(["2026-01-01,10.00"], header="date,amount"), **LIMITS)


def test_a_utf8_bom_does_not_corrupt_the_first_header() -> None:
    payload = b"\xef\xbb\xbf" + csv_bytes(["2026-01-01,10.00,USD,Staples,INV-1"])
    report = parse_csv(payload, **LIMITS)
    assert report.accepted == 1
    assert report.encoding == "utf-8-sig"


def test_nul_bytes_and_control_characters_are_stripped() -> None:
    payload = b"date,amount,currency,vendor,memo\n2026-01-01,10.00,USD,Sta\x00ples\x07,INV-1\n"
    report = parse_csv(payload, **LIMITS)
    assert report.accepted == 1
    assert report.rows[0].vendor_raw == "Staples"


def test_cp1252_input_is_decoded_rather_than_rejected() -> None:
    payload = "date,amount,currency,vendor,memo\n2026-01-01,10.00,USD,Café Nero,INV-1\n".encode("cp1252")
    report = parse_csv(payload, **LIMITS)
    assert report.accepted == 1
    assert report.encoding in {"cp1252", "latin-1"}


def test_an_overlong_descriptor_is_truncated_to_the_column_width() -> None:
    report = run([f"2026-01-01,10.00,USD,{'A' * 5000},INV-1"])
    assert report.accepted == 1
    assert len(report.rows[0].vendor_raw) == 512


def test_formula_injection_is_preserved_on_input_not_silently_altered() -> None:
    """The raw descriptor is the audit record, so it is stored verbatim. Neutralising it
    belongs on export, where a spreadsheet would actually evaluate it."""
    report = run(["2026-01-01,10.00,USD,=cmd|' /C calc'!A0,INV-1"])
    assert report.accepted == 1
    assert report.rows[0].vendor_raw.startswith("=cmd")


def test_zero_amount_rows_are_queued_as_errors_not_stored() -> None:
    report = run(["2026-01-01,0.00,USD,Staples,INV-1"])
    assert report.accepted == 0
    assert "zero" in report.errors[0].reason


def test_alternative_header_names_are_understood() -> None:
    report = parse_csv(
        csv_bytes(
            ["01/04/2026,19.99,Starbucks #123,GBP,ref-9"],
            header="Posted Date,Transaction Amount,Description,Currency,Reference",
        ),
        **LIMITS,
    )
    assert report.accepted == 1
    row = report.rows[0]
    assert (row.date, row.amount, row.currency, row.memo) == (date(2026, 1, 4), 19.99, "GBP", "ref-9")


def test_semicolon_delimited_export_is_handled() -> None:
    payload = b"date;amount;currency;vendor;memo\n2026-01-01;10,50;EUR;Figma;INV-1\n"
    report = parse_csv(payload, **LIMITS)
    assert report.accepted == 1
    assert report.rows[0].amount == pytest.approx(10.5)


def test_vendor_is_normalized_at_intake() -> None:
    report = run(["2026-01-01,10.00,USD,AMZN Mktp US*Y7D8K6,"])
    assert report.rows[0].vendor_norm == "AMAZON MARKETPLACE"


# --- the shipped example files -----------------------------------------------


@pytest.mark.parametrize(
    "filename",
    ["month_01_realistic_seed42.csv", "month_02_realistic_seed43.csv", "ambiguous_edge_cases.csv"],
)
def test_every_shipped_example_file_imports_cleanly(filename: str) -> None:
    """The demo must not open with a parse error. These files carry deliberate date-format
    chaos and FX flags, so this is a real end-to-end check of the hardening above."""
    path = REPO_ROOT / "examples" / filename
    assert path.exists(), f"{filename} is missing — run `make seed`"

    report = parse_csv(path.read_bytes(), **LIMITS)
    assert report.rejected == 0, f"{filename} had rejected rows: {report.errors[:3]}"
    assert report.accepted > 0
    assert all(r.vendor_norm for r in report.rows)


def test_examples_directory_is_not_empty() -> None:
    files = list((REPO_ROOT / "examples").glob("*.csv"))
    assert len(files) >= 3, f"expected the shipped example CSVs, found {[f.name for f in files]}"


# --- the API endpoint ---------------------------------------------------------


def test_upload_endpoint_stores_transactions_as_pending(client) -> None:
    payload = csv_bytes(
        [
            "2026-01-01,10.00,USD,AMZN Mktp US*Y7D8K6,INV-1",
            "2026-01-02,20.00,USD,Starbucks #123,",
        ]
    )
    resp = client.post(
        "/api/ingest/csv",
        files={"file": ("month.csv", payload, "text/csv")},
    )
    assert resp.status_code == 201, resp.text

    body = resp.json()
    assert body["accepted"] == 2
    assert body["rejected"] == 0
    assert body["pending_total"] == 2
    assert body["source_file"] == "month.csv"


def test_upload_endpoint_reports_rejected_rows(client) -> None:
    payload = csv_bytes(["2026-01-01,10.00,USD,Staples,", "oops,20.00,USD,Amazon,"])
    resp = client.post("/api/ingest/csv", files={"file": ("m.csv", payload, "text/csv")})

    body = resp.json()
    assert body["accepted"] == 1
    assert body["rejected"] == 1
    assert body["errors"][0]["line"] == 3


def test_upload_endpoint_rejects_a_file_with_no_usable_header(client) -> None:
    resp = client.post(
        "/api/ingest/csv",
        files={"file": ("m.csv", b"foo,bar\n1,2\n", "text/csv")},
    )
    assert resp.status_code == 422
    assert "missing required column" in resp.json()["detail"]


def test_a_real_example_file_uploads_through_the_api(client) -> None:
    path: Path = REPO_ROOT / "examples" / "month_01_realistic_seed42.csv"
    resp = client.post(
        "/api/ingest/csv",
        files={"file": (path.name, path.read_bytes(), "text/csv")},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["accepted"] == 120
