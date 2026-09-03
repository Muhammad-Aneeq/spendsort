"""CSV intake and hardening.

spec 11 section 4 F1: "CSV upload (date, amount, vendor/description, currency)".
spec 11 section 11: "CSV hardening".

Design stance: **one bad row must not lose the other 119.** A finance tool that rejects a whole
upload because row 57 has a blank amount is a tool nobody uses. Every row is parsed
independently, and the caller gets back both the accepted transactions and a per-row account of
what was rejected and why.

Hardening covered here:
  * byte-size and row-count ceilings, checked before parsing (settings)
  * encoding: UTF-8 with BOM, then a declared fallback chain, never a silent mojibake
  * NUL bytes and control characters stripped — they break the csv module and downstream logs
  * field-length ceilings matching the DB columns, so a 10 MB descriptor cannot be stored
  * flexible header naming, because no two banks agree on column titles
  * date-format chaos and amount formatting resolved with documented, tested conventions

CSV **formula injection** (`=cmd|...`) is not neutralised on the way in: the raw descriptor is
kept verbatim for the audit trail. It is neutralised on the way OUT, in `services/export.py`,
which is where a spreadsheet would actually evaluate it.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime

from app.normalize import normalize_vendor

# --- limits mirroring the ORM columns ---------------------------------------
MAX_VENDOR_LEN = 512
MAX_MEMO_LEN = 256
MAX_CURRENCY_LEN = 3

# --- header aliases ---------------------------------------------------------
# No two banks name their columns the same way.
_HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "date": ("date", "transaction date", "txn date", "posted", "posted date", "post date", "trans date"),
    "amount": ("amount", "value", "debit", "charge", "transaction amount", "amt"),
    "vendor": ("vendor", "description", "merchant", "payee", "name", "details", "narrative", "memo/description"),
    "currency": ("currency", "curr", "ccy", "iso currency"),
    "memo": ("memo", "reference", "ref", "notes", "note", "invoice", "memo/notes"),
}

# --- date formats -----------------------------------------------------------
# Order is the disambiguation policy, and it is deliberate:
#   * ISO first, since `2026-01-04` is unambiguous.
#   * SLASHES are read US-style (month first): `01/04/26` -> 4 Jan 2026.
#   * HYPHENS are read EU-style (day first):   `04-01-2026` -> 4 Jan 2026.
# Those two conventions are genuinely ambiguous in the wild; picking by separator is a
# documented, tested convention rather than a guess re-made per row.
_DATE_FORMATS: tuple[str, ...] = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%m/%d/%Y",
    "%m/%d/%y",
    "%d-%m-%Y",
    "%d-%m-%y",
    "%d %b %Y",
    "%d %B %Y",
    "%b %d %Y",
    "%B %d %Y",
    "%d.%m.%Y",
)

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WHITESPACE = re.compile(r"\s+")
_AMOUNT_STRIP = re.compile(r"[^\d.,\-()]")
_CURRENCY_CODE = re.compile(r"^[A-Z]{3}$")


class IngestError(Exception):
    """The upload as a whole cannot be processed (too big, unreadable, no usable header)."""


@dataclass(frozen=True, slots=True)
class ParsedRow:
    line: int
    date: date
    amount: float
    currency: str
    vendor_raw: str
    vendor_norm: str
    memo: str | None


@dataclass(frozen=True, slots=True)
class RowError:
    line: int
    reason: str
    raw: str


@dataclass
class IngestReport:
    rows: list[ParsedRow] = field(default_factory=list)
    errors: list[RowError] = field(default_factory=list)
    encoding: str = "utf-8"
    truncated: bool = False  # row ceiling reached; the rest of the file was not read

    @property
    def accepted(self) -> int:
        return len(self.rows)

    @property
    def rejected(self) -> int:
        return len(self.errors)


# --- field parsing -----------------------------------------------------------


def _clean(value: str | None) -> str:
    if not value:
        return ""
    return _WHITESPACE.sub(" ", _CONTROL_CHARS.sub("", value)).strip()


def decode_csv(data: bytes) -> tuple[str, str]:
    """Decode upload bytes, returning (text, encoding-used).

    `utf-8-sig` first so a BOM is consumed rather than becoming part of the first header name.
    The fallbacks are declared and reported, so a mojibake upload is visible instead of silent
    (the em-dash problem measured in PLAN.md D15).
    """
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise IngestError("could not decode the file as UTF-8, CP1252 or Latin-1")


def parse_date(value: str) -> date:
    text = _clean(value).replace(",", " ")
    text = _WHITESPACE.sub(" ", text)
    if not text:
        raise ValueError("date is blank")

    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unrecognised date format: {value!r}")


def parse_amount(value: str) -> float:
    text = _clean(value)
    if not text:
        raise ValueError("amount is blank")

    negative = text.startswith("(") and text.endswith(")")
    text = _AMOUNT_STRIP.sub("", text).replace("(", "").replace(")", "")

    # European style: "1.234,56" -> comma is the decimal separator. Whichever separator comes
    # last is the decimal point.
    if "," in text and "." in text:
        european = text.rfind(",") > text.rfind(".")
        text = text.replace(".", "").replace(",", ".") if european else text.replace(",", "")
    elif "," in text:
        # A single comma is a thousands separator unless it looks like "123,45".
        whole, _, frac = text.rpartition(",")
        text = f"{whole}.{frac}" if len(frac) == 2 and whole.replace("-", "").isdigit() else text.replace(",", "")

    if not text or text in {"-", "."}:
        raise ValueError(f"not a number: {value!r}")

    try:
        amount = float(text)
    except ValueError:
        raise ValueError(f"not a number: {value!r}") from None

    if amount != amount or amount in (float("inf"), float("-inf")):  # NaN / inf
        raise ValueError(f"not a finite number: {value!r}")

    return -abs(amount) if negative else amount


def parse_currency(value: str, default: str = "USD") -> str:
    """Accept a 3-letter ISO code, else fall back to the default.

    Validate the whole token *before* trimming to width: truncating first would turn
    "dollars" into a confident-looking "DOL".
    """
    text = _clean(value).upper()
    return text if _CURRENCY_CODE.match(text) else default


def _map_headers(fieldnames: list[str]) -> dict[str, str]:
    """Map our canonical field names onto whatever this bank called its columns."""
    lookup = {_clean(name).lower(): name for name in fieldnames if name}
    mapping: dict[str, str] = {}
    for canonical, aliases in _HEADER_ALIASES.items():
        for alias in aliases:
            if alias in lookup:
                mapping[canonical] = lookup[alias]
                break
    return mapping


# --- the entry point ---------------------------------------------------------


def parse_csv(
    data: bytes,
    *,
    max_bytes: int,
    max_rows: int,
    default_currency: str = "USD",
) -> IngestReport:
    """Parse an uploaded transactions CSV. Never raises on a bad row — only on a bad file."""
    if not data:
        raise IngestError("the uploaded file is empty")
    if len(data) > max_bytes:
        raise IngestError(f"file is {len(data)} bytes; the limit is {max_bytes}")

    text, encoding = decode_csv(data)
    text = text.replace("\x00", "")

    try:
        # Sniffing lets a semicolon- or tab-delimited export work too.
        dialect: type[csv.Dialect] | csv.Dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel

    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        raise IngestError("no header row found")

    headers = _map_headers(list(reader.fieldnames))
    missing = [f for f in ("date", "amount", "vendor") if f not in headers]
    if missing:
        found = ", ".join(n for n in reader.fieldnames if n)
        raise IngestError(f"missing required column(s): {', '.join(missing)}. Columns found: {found}")

    report = IngestReport(encoding=encoding)

    for offset, raw_row in enumerate(reader):
        line = offset + 2  # +1 for the header, +1 for 1-based line numbers

        if report.accepted >= max_rows:
            report.truncated = True
            break

        # A short row leaves None values; a long row lands in the restkey. Both are tolerated.
        raw_preview = " | ".join(_clean(v) for v in raw_row.values() if isinstance(v, str))[:200]

        vendor_raw = _clean(raw_row.get(headers["vendor"]))[:MAX_VENDOR_LEN]
        if not vendor_raw:
            report.errors.append(RowError(line, "vendor/description is blank", raw_preview))
            continue

        try:
            txn_date = parse_date(_clean(raw_row.get(headers["date"])))
        except ValueError as exc:
            report.errors.append(RowError(line, str(exc), raw_preview))
            continue

        try:
            amount = parse_amount(_clean(raw_row.get(headers["amount"])))
        except ValueError as exc:
            report.errors.append(RowError(line, str(exc), raw_preview))
            continue

        if amount == 0.0:
            report.errors.append(RowError(line, "amount is zero", raw_preview))
            continue

        currency = parse_currency(_clean(raw_row.get(headers.get("currency", ""))), default_currency)
        memo = _clean(raw_row.get(headers.get("memo", "")))[:MAX_MEMO_LEN] or None

        report.rows.append(
            ParsedRow(
                line=line,
                date=txn_date,
                amount=amount,
                currency=currency,
                vendor_raw=vendor_raw,
                vendor_norm=normalize_vendor(vendor_raw),
                memo=memo,
            )
        )

    return report
