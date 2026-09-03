"""Vendor normalization, tested against real ledgerfab alias chaos (spec 11 section 14).

    "Vendor normalization quality (messy descriptors) -> normalize aggressively,
     test on ledgerfab alias chaos"

The properties asserted here are the ones that actually matter for the product:

  * **Purity** — no key may be shared by two different vendors. A collision teaches
    vendor_memory the wrong account, which is the one failure mode worse than a queued row.
  * **Idempotence** — normalizing twice must not move. Otherwise memory keys drift between
    runs and yesterday's learning silently stops matching.
  * **Collapse** — one vendor should yield few keys, since every extra key is one more
    LLM call before memory covers it.

Note what is NOT asserted: that every alias of a vendor collapses to exactly one key. It does
not, and pretending otherwise would be dishonest — `HISCOX INS` and `HISCOX PREMIUM` are
different descriptor families. Memory simply learns both.
"""

from __future__ import annotations

from collections import defaultdict

import pytest

import ledgerfab
from app.normalize import normalize_vendor
from ledgerfab.config import PRESETS

# A big nightmare-profile sample: maximum alias, date and reference chaos.
BIG_SAMPLE = PRESETS["nightmare"].model_copy(update={"txn_count": 2000})


@pytest.fixture(scope="module")
def chaos_world() -> ledgerfab.World:
    return ledgerfab.generate(BIG_SAMPLE, 9)


# --- the properties that matter ---------------------------------------------


def test_no_key_is_shared_by_two_vendors(chaos_world: ledgerfab.World) -> None:
    """The one unacceptable failure: memory learning the wrong account for a vendor."""
    vendors_by_key: dict[str, set[str]] = defaultdict(set)
    for txn in chaos_world.transactions:
        vendors_by_key[normalize_vendor(txn.vendor_raw)].add(txn.counterparty_id)

    collisions = {k: sorted(v) for k, v in vendors_by_key.items() if len(v) > 1}
    assert collisions == {}, f"normalized keys shared by several vendors: {collisions}"


def test_normalization_is_idempotent(chaos_world: ledgerfab.World) -> None:
    """If normalizing twice moves, memory keys drift and learning stops matching."""
    drifting = [
        (txn.vendor_raw, normalize_vendor(txn.vendor_raw), normalize_vendor(normalize_vendor(txn.vendor_raw)))
        for txn in chaos_world.transactions
        if normalize_vendor(normalize_vendor(txn.vendor_raw)) != normalize_vendor(txn.vendor_raw)
    ]
    assert drifting == [], f"normalization is not stable for: {drifting[:5]}"


def test_aliases_collapse_to_few_keys_per_vendor(chaos_world: ledgerfab.World) -> None:
    """Every extra key costs one more LLM call before memory covers the vendor."""
    keys_by_vendor: dict[str, set[str]] = defaultdict(set)
    for txn in chaos_world.transactions:
        keys_by_vendor[txn.counterparty_id].add(normalize_vendor(txn.vendor_raw))

    per_vendor = [len(keys) for keys in keys_by_vendor.values()]
    mean_keys = sum(per_vendor) / len(per_vendor)
    worst = max(per_vendor)
    worst_vendor = max(keys_by_vendor.items(), key=lambda kv: len(kv[1]))

    # Measured at 2.38 mean / 4 worst. The bounds leave headroom but would catch a real
    # regression: an earlier draft scored 14.90 mean / 46 worst.
    assert mean_keys < 4.0, f"mean keys per vendor {mean_keys:.2f} is too high"
    assert worst <= 8, f"{worst_vendor[0]} produced {worst} keys: {sorted(worst_vendor[1])}"


def test_every_row_gets_a_non_empty_key(chaos_world: ledgerfab.World) -> None:
    """A descriptor of pure noise still needs a key, so it can be queued and learned
    rather than silently dropped."""
    assert all(normalize_vendor(txn.vendor_raw).strip() for txn in chaos_world.transactions)


def test_the_clean_profile_normalizes_to_the_vendor_name(chaos_world: ledgerfab.World) -> None:
    """With no alias chaos, the key should just be the vendor, uppercased."""
    world = ledgerfab.generate("clean", 42)
    for txn in world.transactions:
        cp = world.counterparty(txn.counterparty_id)
        assert cp is not None
        # Legal suffixes and punctuation are stripped, so compare on the leading word.
        assert normalize_vendor(txn.vendor_raw).startswith(normalize_vendor(cp.canonical_name).split(" ")[0])


# --- specific mechanics ------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # Case and whitespace.
        ("Amazon", "AMAZON"),
        ("  amazon  ", "AMAZON"),
        ("AMAZON", "AMAZON"),
        # Processor and channel prefixes.
        ("POS DEBIT STAPLES", "STAPLES"),
        ("SQ *BLUE BOTTLE", "BLUE BOTTLE"),
        ("TST* CHIPOTLE", "CHIPOTLE"),
        ("PAYPAL *FIGMA", "FIGMA"),
        # `*` introduces the meaningful part as often as a reference, so it must not be
        # used to decide what to discard.
        ("GOOGLE *ADS #4423", "GOOGLE ADS"),
        ("UBER *TRIP", "UBER TRIP"),
        ("UBER *EATS KCT263", "UBER EATS"),
        # References and store numbers.
        ("ADOBE  *5HJH31", "ADOBE"),
        ("BEST BUY #1234", "BEST BUY"),
        ("DELL 1234", "DELL"),
        ("UNITED  0162 9K2M40", "UNITED"),
        ("UNITED AIRLINES 9K2M40", "UNITED AIRLINES"),
        # A reference glued straight onto a long brand.
        ("CLOUDFLARE0FDLSX", "CLOUDFLARE"),
        ("Microsoft 365", "MICROSOFT"),
        # Domains: keep the brand, drop the TLD and path.
        ("Slack.com", "SLACK"),
        ("APPLE.COM/BILL", "APPLE"),
        ("NOTION.SO", "NOTION"),
        ("AMAZON.COM*MT4YH9 AMZN.COM/BILL WA", "AMAZON"),
        # Location tails.
        ("COURTYARD BY MARRIOTT SEATTLE WA", "COURTYARD BY MARRIOTT"),
        ("SHELL SERVICE STATION SAN FRANCISCO CA", "SHELL SERVICE STATION"),
        ("CLOUDFLARE DENVER CO", "CLOUDFLARE"),
        # Corporate form.
        ("FIGMA INC", "FIGMA"),
        ("Notion Labs Inc", "NOTION LABS"),
        ("HARBOR & VANCE  LLP 4K2J91", "HARBOR & VANCE"),
        # Bank shorthand expanded to the brand.
        ("AMZN Mktp US*Y7D8K6", "AMAZON MARKETPLACE"),
        ("AMZN MKTP US SEATTLE WA", "AMAZON MARKETPLACE"),
        ("MSFT *GITHUB", "MICROSOFT GITHUB"),
        ("VZWRLSS*APOCC VISB", "VERIZON APOCC VISB"),
        ("ZENPAYROLL INC", "GUSTO"),
        # A stray initial belongs to the word after it.
        ("E-ZPass", "EZPASS"),
        ("EZPASS", "EZPASS"),
    ],
)
def test_specific_descriptors(raw: str, expected: str) -> None:
    assert normalize_vendor(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "\t\n"])
def test_blank_input_gives_a_blank_key(raw: str) -> None:
    assert normalize_vendor(raw) == ""


def test_a_state_code_inside_a_name_survives() -> None:
    """ "CON ED OF NY" is a company, not a company in New York. Eroding it to "CON" would
    make the key useless."""
    assert normalize_vendor("CON ED OF NY 4K2J91") == "CON ED NY"


def test_pure_noise_still_produces_a_key() -> None:
    assert normalize_vendor("**** 1234 ****").strip() != ""


def test_two_google_products_do_not_collapse_together() -> None:
    """Google Ads is advertising; Google Cloud is hosting. One key for both would teach
    memory the wrong account for whichever came second."""
    assert normalize_vendor("GOOGLE *ADS #4423") != normalize_vendor("GOOGLE *CLOUD 8M2K10")
