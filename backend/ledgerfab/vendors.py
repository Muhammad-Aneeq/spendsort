"""The counterparty catalog — "counterparties (with aliases)", spec 00 A3.

The aliases are the point. Real bank feeds do not say "Amazon"; they say
`AMZN Mktp US*2K4LM7Y83` or `AMAZON.COM*MT4YH9 AMZN.COM/BILL WA`. Vendor normalization
quality is the headline risk in spec 11 section 14, so the alias templates here are
deliberately nasty: processor prefixes (`SQ *`, `TST*`, `POS DEBIT`), store numbers,
city/state tails, reference noise, and inconsistent spacing and case.

Templates understand three placeholders, filled per transaction by `generate.py`:
    {ref}    a random alphanumeric reference    {store}  a store number    {city}  CITY ST

`ambiguous_with` names a second genuinely defensible account. Amazon really could be office
supplies or computer equipment; Uber really could be ground transport or a meal; Airbnb could
be lodging or rent. These exist so evals can assert that confidence DROPS on them, rather than
asserting one particular code (spec 11 section 14).
"""

from __future__ import annotations

from ledgerfab.models import Counterparty


def _cp(
    vendor_id: str,
    canonical: str,
    account: str,
    aliases: tuple[str, ...],
    amount: tuple[float, float],
    *,
    recurring: bool = False,
    ambiguous_with: str | None = None,
) -> Counterparty:
    return Counterparty(
        id=vendor_id,
        canonical_name=canonical,
        account_code=account,
        aliases=aliases,
        typical_amount=amount,
        recurring=recurring,
        ambiguous_with=ambiguous_with,
    )


# fmt: off
_CATALOG: tuple[Counterparty, ...] = (
    # --- 6000 Advertising & Marketing -------------------------------------------------
    _cp("google_ads", "Google Ads", "6000",
        ("GOOGLE ADS{ref}", "GOOGLE *ADS{store}", "google ads {city}"), (150.0, 2400.0), recurring=True),
    _cp("meta_ads", "Meta Platforms", "6000",
        ("FACEBK *{ref}", "META PLATFORMS INC{ref}", "FB ADS {city}"), (80.0, 1800.0), recurring=True),
    _cp("linkedin_ads", "LinkedIn", "6000",
        ("LINKEDIN{ref}", "LNKD *ADS {city}", "LINKEDIN-{store}"), (120.0, 900.0)),

    # --- 6010 Bank & Merchant Fees ----------------------------------------------------
    _cp("stripe_fees", "Stripe", "6010",
        ("STRIPE FEE{ref}", "STRIPE  MONTHLY FEE", "Stripe Payments Fee"), (12.0, 340.0), recurring=True),
    _cp("bank_charge", "First Northwest Bank", "6010",
        ("MONTHLY SERVICE CHARGE", "ACCT ANALYSIS FEE", "WIRE FEE OUTGOING"), (8.0, 45.0), recurring=True),

    # --- 6020 Computer Equipment ------------------------------------------------------
    _cp("apple", "Apple", "6020",
        ("APPLE.COM/BILL", "APPLE STORE #{store}", "APL*ITUNES.COM/BILL", "APPLE STORE {city}"),
        (29.0, 2900.0), ambiguous_with="6030"),
    _cp("dell", "Dell Technologies", "6020",
        ("DELL {store}", "DELL MARKETING LP", "DELL*ORDER {ref}"), (240.0, 3200.0)),
    _cp("best_buy", "Best Buy", "6020",
        ("BEST BUY #{store}", "BESTBUY.COM {ref}", "BEST BUY {city}"), (35.0, 1600.0), ambiguous_with="6060"),

    # --- 6030 Dues & Subscriptions ----------------------------------------------------
    _cp("slack", "Slack", "6030",
        ("SLACK T{ref}", "SLACK TECHNOLOGIES", "Slack.com"), (8.0, 210.0), recurring=True),
    _cp("notion", "Notion Labs", "6030",
        ("NOTION LABS{ref}", "NOTION.SO", "Notion Labs Inc"), (10.0, 180.0), recurring=True),
    _cp("adobe", "Adobe", "6030",
        ("ADOBE  *{ref}", "ADOBE CREATIVE CLOUD", "ADOBE INC {city}"), (22.0, 660.0), recurring=True),
    _cp("figma", "Figma", "6030",
        ("FIGMA MONTHLY{ref}", "FIGMA.COM", "FIGMA INC"), (12.0, 450.0), recurring=True),
    _cp("github", "GitHub", "6030",
        ("GITHUB.COM{ref}", "GITHUB *TEAM", "MSFT *GITHUB"), (4.0, 320.0), recurring=True, ambiguous_with="6190"),
    _cp("zoom", "Zoom", "6030",
        ("ZOOM.US{ref}", "ZOOM VIDEO COMM", "ZOOM *{store}"), (15.0, 240.0), recurring=True, ambiguous_with="6110"),
    _cp("microsoft365", "Microsoft 365", "6030",
        ("MSFT * E{ref}", "MICROSOFT*365", "MICROSOFT #G{ref}"), (12.0, 520.0), recurring=True),

    # --- 6040 Insurance ---------------------------------------------------------------
    _cp("hiscox", "Hiscox Insurance", "6040",
        ("HISCOX INS{ref}", "HISCOX INSURANCE CO", "HISCOX PREMIUM"), (95.0, 780.0), recurring=True),

    # --- 6050 Meals & Entertainment ---------------------------------------------------
    _cp("starbucks", "Starbucks", "6050",
        ("STARBUCKS #{store}", "SQ *STARBUCKS {city}", "STARBUCKS STORE {store}"), (4.0, 68.0)),
    _cp("chipotle", "Chipotle", "6050",
        ("CHIPOTLE {store}", "CHIPOTLE ONLINE{ref}", "CHIPOTLE MEXICAN GRILL {city}"), (11.0, 240.0)),
    _cp("doordash", "DoorDash", "6050",
        ("DD DOORDASH {ref}", "DOORDASH*{ref}", "DOORDASH {city}"), (18.0, 190.0)),
    _cp("blue_bottle", "Blue Bottle Coffee", "6050",
        ("TST* BLUE BOTTLE {city}", "SQ *BLUE BOTTLE", "BLUE BOTTLE #{store}"), (6.0, 95.0)),

    # --- 6060 Office Supplies ---------------------------------------------------------
    _cp("amazon", "Amazon", "6060",
        ("AMZN Mktp US*{ref}", "AMAZON.COM*{ref} AMZN.COM/BILL WA", "AMZN MKTP US {city}",
         "Amazon.com*{ref}", "AMAZON MKTPLACE PMTS"),
        (9.0, 1400.0), ambiguous_with="6020"),
    _cp("staples", "Staples", "6060",
        ("STAPLES #{store}", "STAPLES.COM {ref}", "STAPLES {city}"), (14.0, 420.0)),
    _cp("costco", "Costco", "6060",
        ("COSTCO WHSE #{store}", "COSTCO WHOLESALE {city}", "COSTCO #{store}"), (48.0, 890.0),
        ambiguous_with="6050"),

    # --- 6070 Postage & Shipping ------------------------------------------------------
    _cp("fedex", "FedEx", "6070",
        ("FEDEX {ref}", "FEDEX OFFIC{store}", "FEDEXOFFICE {city}"), (12.0, 380.0)),
    _cp("ups", "UPS", "6070",
        ("UPS*{ref}", "THE UPS STORE {store}", "UPS SHIPPING {city}"), (9.0, 290.0)),

    # --- 6080 Professional Fees -------------------------------------------------------
    _cp("harbor_legal", "Harbor & Vance LLP", "6080",
        ("HARBOR VANCE LLP", "HARBOR & VANCE  LLP {ref}", "HARBORVANCE RETAINER"), (450.0, 6500.0)),
    _cp("quill_accounting", "Quill Accounting", "6080",
        ("QUILL ACCOUNTING{ref}", "QUILL ACCTG SVCS", "QUILL ACCOUNTING {city}"), (280.0, 2400.0), recurring=True),

    # --- 6090 Rent --------------------------------------------------------------------
    _cp("wework", "WeWork", "6090",
        ("WEWORK {city}", "WEWORK*{ref}", "WE WORK MGMT LLC"), (320.0, 2800.0), recurring=True),
    _cp("public_storage", "Public Storage", "6090",
        ("PUBLIC STORAGE {store}", "PUBLIC STORAGE  #{store}", "PUBLICSTORAGE {city}"), (85.0, 340.0),
        recurring=True),

    # --- 6100 Repairs & Maintenance ---------------------------------------------------
    _cp("brightline_clean", "Brightline Cleaning", "6100",
        ("BRIGHTLINE CLEANING", "SQ *BRIGHTLINE CLEAN", "BRIGHTLINE CLNG {city}"), (120.0, 640.0), recurring=True),
    _cp("acme_hvac", "Acme HVAC Services", "6100",
        ("ACME HVAC SVC{ref}", "ACME HVAC {city}", "ACME HEATING & AIR"), (180.0, 2100.0)),

    # --- 6110 Telephone & Internet ----------------------------------------------------
    _cp("verizon", "Verizon", "6110",
        ("VERIZON WRLS {ref}", "VZWRLSS*APOCC VISB", "VERIZON *{store}"), (65.0, 620.0), recurring=True),
    _cp("comcast", "Comcast Business", "6110",
        ("COMCAST {ref}", "COMCAST BUSINESS {city}", "CABLE COMM {store}"), (89.0, 480.0), recurring=True),

    # --- 6120 Training & Education ----------------------------------------------------
    _cp("udemy", "Udemy", "6120",
        ("UDEMY {ref}", "UDEMY.COM", "UDEMY ONLINE COURSES"), (14.0, 320.0), ambiguous_with="6030"),
    _cp("oreilly", "O'Reilly Media", "6120",
        ("OREILLY MEDIA{ref}", "O'REILLY MEDIA INC", "OREILLY  *SAFARI"), (39.0, 620.0), recurring=True),

    # --- 6130 Travel — Airfare --------------------------------------------------------
    _cp("united", "United Airlines", "6130",
        ("UNITED AIRLINES {ref}", "UNITED  0162{ref}", "UNITED AIR {city}"), (180.0, 1850.0)),
    _cp("delta", "Delta Air Lines", "6130",
        ("DELTA AIR LINES{ref}", "DELTA  0062{ref}", "DELTA AIR {city}"), (160.0, 2100.0)),

    # --- 6140 Travel — Lodging --------------------------------------------------------
    _cp("marriott", "Marriott", "6140",
        ("MARRIOTT {city}", "MARRIOTT HOTELS {store}", "COURTYARD BY MARRIOTT {city}"), (140.0, 1400.0)),
    _cp("airbnb", "Airbnb", "6140",
        ("AIRBNB * HM{ref}", "AIRBNB {ref}", "AIRBNB PAYMENTS"), (110.0, 1900.0), ambiguous_with="6090"),

    # --- 6150 Travel — Ground Transport -----------------------------------------------
    _cp("uber", "Uber", "6150",
        ("UBER *TRIP {city}", "UBER   *TRIP", "UBER *EATS {ref}", "UBER TRIP {ref}"), (7.0, 145.0),
        ambiguous_with="6050"),
    _cp("lyft", "Lyft", "6150",
        ("LYFT *RIDE {ref}", "LYFT   *RIDE", "LYFT {city}"), (6.0, 120.0)),
    _cp("amtrak", "Amtrak", "6150",
        ("AMTRAK {ref}", "AMTRAK .COM {city}", "AMTRAK TICKET {store}"), (28.0, 380.0), ambiguous_with="6130"),

    # --- 6160 Utilities ---------------------------------------------------------------
    _cp("coned", "Consolidated Edison", "6160",
        ("CON EDISON {ref}", "CONED BILL PAY", "CON ED OF NY {city}"), (95.0, 890.0), recurring=True),
    _cp("city_water", "City Water Dept", "6160",
        ("CITY WATER DEPT", "CITY OF {city} WATER", "WATER DEPT {ref}"), (40.0, 260.0), recurring=True),

    # --- 6170 Contractor & Payroll Services -------------------------------------------
    _cp("gusto", "Gusto", "6170",
        ("GUSTO {ref}", "GUSTO PAYROLL FEE", "ZENPAYROLL INC"), (45.0, 480.0), recurring=True),
    _cp("upwork", "Upwork", "6170",
        ("UPWORK -{ref}", "UPWORK ESCROW", "UPWORK.COM {city}"), (120.0, 3400.0), ambiguous_with="6080"),

    # --- 6180 Fuel & Vehicle ----------------------------------------------------------
    _cp("shell", "Shell", "6180",
        ("SHELL OIL {store}", "SHELL SERVICE STATION {city}", "SHELL {store}"), (32.0, 140.0)),
    _cp("ezpass", "E-ZPass", "6180",
        ("EZPASS REBILL{ref}", "E-ZPASS NY {ref}", "EZPASS {city}"), (25.0, 120.0), recurring=True),

    # --- 6190 Cloud Hosting -----------------------------------------------------------
    _cp("aws", "Amazon Web Services", "6190",
        ("AMAZON WEB SERVICES{ref}", "AWS EMEA {ref}", "AMAZON WEB SERV AWS.AM"), (85.0, 4200.0),
        recurring=True, ambiguous_with="6060"),
    _cp("gcp", "Google Cloud", "6190",
        ("GOOGLE *CLOUD {ref}", "GOOGLE CLOUD {city}", "GOOGLE*SVCS {ref}"), (60.0, 3100.0), recurring=True),
    _cp("vercel", "Vercel", "6190",
        ("VERCEL INC{ref}", "VERCEL.COM", "VERCEL *PRO"), (20.0, 640.0), recurring=True, ambiguous_with="6030"),
    _cp("cloudflare", "Cloudflare", "6190",
        ("CLOUDFLARE{ref}", "CLOUDFLARE INC {city}", "CLOUDFLARE *PRO"), (20.0, 480.0),
        recurring=True, ambiguous_with="6030"),
)
# fmt: on

CITIES: tuple[str, ...] = (
    "SEATTLE WA",
    "SAN FRANCISCO CA",
    "NEW YORK NY",
    "AUSTIN TX",
    "DENVER CO",
    "CHICAGO IL",
    "PORTLAND OR",
    "BOSTON MA",
    "ATLANTA GA",
    "SAN JOSE CA",
)


def default_counterparties() -> tuple[Counterparty, ...]:
    return _CATALOG


AMBIGUOUS_IDS: frozenset[str] = frozenset(cp.id for cp in _CATALOG if cp.ambiguous_with is not None)
