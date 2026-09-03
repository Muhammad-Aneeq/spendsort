"""Vendor normalization — spec 11 section 14's headline risk.

    "Vendor normalization quality (messy descriptors) -> normalize aggressively,
     test on ledgerfab alias chaos"

`AMZN Mktp US*2K4LM7Y83`, `AMAZON.COM*MT4YH9 AMZN.COM/BILL WA` and `POS DEBIT AMZN MKTP US
SEATTLE WA` are the same shop. Normalization is what lets vendor_memory recognise a vendor it
has already been taught, which is what lets the agent skip the LLM.

**The line this module does not cross.** It cleans *descriptors*; it never decides *accounts*.
The abbreviation table below expands bank shorthand to a brand (`AMZN` -> `AMAZON`, `MSFT` ->
`MICROSOFT`) — the kind of descriptor-cleanup rule any bookkeeper keeps. It contains no mapping
from a vendor to an account code, so it cannot leak the answer the LLM or the human is there to
give. Categorization stays earned.

Normalization is deliberately imperfect. One vendor may still yield two keys (`AMAZON` and
`AMAZON MARKETPLACE`); memory simply learns both. Pretending a regex can perfectly resolve
vendor identity would be the dishonest version of this module.
"""

from __future__ import annotations

import re
import unicodedata

# --- processor / channel prefixes -------------------------------------------
# Payment rails bolt these onto the front of an otherwise clean descriptor.
_PREFIXES: tuple[str, ...] = (
    "POS DEBIT",
    "POS PURCHASE",
    "POS",
    "DEBIT CARD PURCHASE",
    "CHECKCARD",
    "RECURRING PAYMENT",
    "PREAUTHORIZED",
    "PURCHASE AUTHORIZED ON",
    "SQ *",
    "SQ*",
    "TST* ",
    "TST*",
    "PAYPAL *",
    "PAYPAL*",
    "PP*",
    "DD ",
    "APL* ",
    "APL*",
)

# --- noise tokens -----------------------------------------------------------
# Words that carry no identity: they say "this was a payment", which we knew.
_FILLER: frozenset[str] = frozenset(
    {
        "PMTS",
        "PMT",
        "PAYMENTS",
        "PAYMENT",
        "PAY",
        "BILLPAY",
        "AUTOPAY",
        "REBILL",
        "RECURRING",
        "PURCHASE",
        "DEBIT",
        "CREDIT",
        "TRANSACTION",
        "REF",
        "USA",
        "US",
        "INTL",
        "OF",
        "THE",
        "AND",
    }
)

# Corporate form. "Harbor & Vance LLP" and "HARBOR VANCE LLP" are one firm.
#
# "CO" is deliberately absent. It is both "Company" and Colorado, and in bank descriptors the
# state reading is at least as common ("SHELL ... DENVER CO"). Leaving it in the token stream
# lets the location-tail stripper handle it, which gives a good key either way:
# "DENVER CO" -> dropped as a location, "HISCOX INSURANCE CO" -> "HISCOX". Dropping it as a
# suffix instead would strand the city, leaving "... DENVER" as a separate memory key.
_LEGAL_SUFFIX: frozenset[str] = frozenset(
    {
        "INC",
        "INCORPORATED",
        "LLC",
        "LLP",
        "LP",
        "LTD",
        "LIMITED",
        "CORP",
        "CORPORATION",
        "COMPANY",
        "PLC",
        "GMBH",
        "SA",
        "NV",
        "BV",
    }
)

# US state codes, so a trailing "SEATTLE WA" location tail can be shed generically.
# fmt: off
_STATES: frozenset[str] = frozenset({
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA",
    "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT",
    "VA", "WA", "WV", "WI", "WY", "DC", "PR",
})
# fmt: on

# Words that commonly OPEN a multi-word US city name. Used only to finish removing a
# location tail whose state code has already been matched — never on its own.
_CITY_LEADERS: frozenset[str] = frozenset(
    {"SAN", "NEW", "LOS", "LAS", "FORT", "FT", "SAINT", "ST", "NORTH", "SOUTH", "EAST", "WEST", "PORT", "LAKE"}
)

# --- bank shorthand -> brand ------------------------------------------------
# Descriptor cleanup only. No account codes here, by design (see module docstring).
_ABBREVIATIONS: dict[str, str] = {
    "AMZN": "AMAZON",
    "MSFT": "MICROSOFT",
    "FACEBK": "META",
    "FB": "META",
    "LNKD": "LINKEDIN",
    "VZWRLSS": "VERIZON",
    "ZENPAYROLL": "GUSTO",
    "MKTP": "MARKETPLACE",
    "MKTPLACE": "MARKETPLACE",
    "WHSE": "WHOLESALE",
    "SVCS": "SERVICES",
    "SVC": "SERVICES",
    "SERVS": "SERVICES",
    "SERV": "SERVICES",
    "WRLS": "WIRELESS",
    "CLNG": "CLEANING",
    "ACCTG": "ACCOUNTING",
    "OFFIC": "OFFICE",
    "TECHNOLOGIES": "TECH",
    "TECHNOLOGY": "TECH",
}

# Web addresses and their trailing paths: `AMZN.COM/BILL`, `ZOOM.US`, `NOTION.SO`.
# The brand is kept; the TLD and any path are dropped.
_DOMAIN = re.compile(r"\b([A-Z0-9][A-Z0-9\-]*)\.(?:COM|NET|ORG|US|IO|SO|CO|AI|APP|DEV)\b(?:/[A-Z0-9/]*)?")
# A long brand with a reference glued straight onto it: `CLOUDFLARE0FDLSX`, `MICROSOFT365`.
# The head must be at least five letters. A shorter head (`KCT263`, `HM13S80`, `T4AB12`) is
# far more likely to be the front of a reference than a brand, so those are left whole and
# dropped by the reference test instead.
# The tail must START with a digit. Otherwise the greedy head would swallow the reference's
# leading letters too ("DELTA AIR LINESB9A1WJ" -> "LINESB"), inventing a brand that is neither.
_BRAND_WITH_REF = re.compile(r"^([A-Z]{5,})(\d[A-Z0-9]*)$")
# Everything that is not a letter, digit or ampersand is a token separator. Crucially this
# includes `*`, `#` and `-`: in real descriptors those introduce the MEANINGFUL part as often
# as a reference (`SQ *STARBUCKS`, `GOOGLE *ADS`, `E-ZPASS`), so they must not be used to
# decide what to throw away.
_SEPARATORS = re.compile(r"[^A-Z0-9&]+")
_WHITESPACE = re.compile(r"\s+")


def _looks_like_reference(token: str) -> bool:
    """Is this token a transaction reference rather than part of the vendor's identity?

    A reference carries digits — card and invoice references effectively always do, and
    ledgerfab guarantees it. That single signal is enough, and it is safer than any
    vowel/word-shape heuristic, which would happily eat a real brand.
    """
    if token.isdigit():
        return len(token) >= 3  # store numbers, flight codes, account fragments
    return len(token) >= 4 and any(c.isdigit() for c in token)


def _strip_location_tail(tokens: list[str]) -> list[str]:
    """Shed a trailing "SEATTLE WA" / "SAN FRANCISCO CA" location tail.

    A location tail is removed only as a **city + state pair**, and only when at least two
    tokens survive. Both conditions matter:

    * Pair-only, because a lone trailing state code is usually part of the payee's name —
      "CON ED OF NY" is a company, not a company in New York.
    * The city slot must look like a city: at least four letters. This is what separates
      "CLOUDFLARE SEATTLE WA" (strip, giving "CLOUDFLARE") from "CON ED NY" (leave alone —
      stripping would erode it to "CON").

    Together these make the function idempotent: when a strip is refused, the output still
    ends in a state code, and a second pass refuses it again rather than continuing to chew.
    """
    out = list(tokens)
    while len(out) >= 3 and out[-1] in _STATES:
        city = out[-2]
        if len(city) < 4 or city in _LEGAL_SUFFIX or _looks_like_reference(city) or city in _STATES:
            break
        out = out[:-2]
        # Two-word cities would otherwise leave their first word behind, turning
        # "SAN FRANCISCO CA" into a stray "SAN".
        if len(out) >= 2 and out[-1] in _CITY_LEADERS:
            out.pop()
    return out


def _strip_prefixes(text: str) -> str:
    """Peel channel prefixes off the front, repeatedly — feeds stack them."""
    changed = True
    while changed:
        changed = False
        for prefix in _PREFIXES:
            if text.startswith(prefix):
                text = text[len(prefix) :].lstrip(" *-")
                changed = True
    return text


def normalize_vendor(raw: str) -> str:
    """Collapse a bank descriptor to a stable vendor key.

    Idempotent: `normalize_vendor(normalize_vendor(x)) == normalize_vendor(x)`.
    Never returns an empty string for non-empty input — an unrecognisable descriptor still
    needs a key, so it can be queued and learned rather than dropped.
    """
    if not raw or not raw.strip():
        return ""

    # Unicode punctuation (em-dash, curly quotes) folded to ASCII before anything else.
    text = unicodedata.normalize("NFKD", raw)
    # The non-ASCII characters here are the point: they are what we are folding away.
    text = text.replace("—", " ").replace("–", " ").replace("’", "").replace("‘", "")  # noqa: RUF001
    text = text.upper().strip()

    text = _strip_prefixes(text)
    text = _DOMAIN.sub(r"\1", text)

    # Split on separators, then peel a reference off any long brand it was glued to.
    # Order matters: classify the WHOLE chunk as a reference first. Splitting letter/digit
    # boundaries up front would shatter `Y7D8K6` into six harmless-looking fragments.
    chunks: list[str] = []
    for chunk in _SEPARATORS.split(text):
        if not chunk:
            continue
        glued = _BRAND_WITH_REF.match(chunk)
        chunks.append(glued.group(1) if glued else chunk)

    # Drop the noise, expand shorthand, and reattach stray initials.
    kept: list[str] = []
    for chunk in chunks:
        token = _ABBREVIATIONS.get(chunk, chunk)
        if token in _FILLER or token in _LEGAL_SUFFIX or _looks_like_reference(token):
            continue
        if kept and len(kept[-1]) == 1 and kept[-1].isalpha():
            # A stray initial belongs to the word after it: "E ZPASS" is one brand, E-ZPass.
            # Merging beats dropping, which would make "E-ZPASS" and "EZPASS" different keys.
            # `isalpha` keeps "&" out of it — "HARBOR & VANCE" is not "HARBOR &VANCE".
            kept[-1] = kept[-1] + token
        else:
            kept.append(token)

    # A trailing lone initial has nothing left to attach to.
    if kept and len(kept[-1]) == 1 and kept[-1].isalpha():
        kept.pop()

    # Only now shed a trailing location tail. Doing this before reference removal would leave
    # "EZPASS NY 7Z5544" as "EZPASS NY" on the first pass and "EZPASS" on the second — the
    # normalizer must reach its answer in one pass or memory keys drift.
    kept = _strip_location_tail(kept)

    # De-duplicate while preserving order: "AMAZON ... AMAZON" is one brand, said twice.
    unique = list(dict.fromkeys(kept))

    result = " ".join(unique).strip()

    # Never lose the row entirely. A descriptor of pure noise still deserves a key, so it can
    # be queued and learned rather than silently dropped. The fallback keeps only the parts
    # that survive tokenization, so it is itself stable under a second pass.
    if not result:
        return " ".join(t for t in _SEPARATORS.split(text) if t) or raw.strip().upper()
    return result
