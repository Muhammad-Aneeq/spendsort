"""The default chart of accounts — a small-business expense CoA.

This is the canonical definition. `backend/app/coa_default.yaml` is GENERATED from it
(`python -m ledgerfab.export`) so ledgerfab's ground truth and the app's CoA cannot drift apart;
spec 11 section 10 requires eval ground truth to be "CoA-aligned", and a test asserts the two match.

Deliberately absent: any "Uncategorized" / "Miscellaneous" dumping ground. A catch-all account
would give the agent somewhere to hide a guess, and the whole point of SpendSort is that an
unconfident answer goes to a human instead.
"""

from __future__ import annotations

from ledgerfab.models import Account

DEFAULT_COA: tuple[Account, ...] = (
    Account(code="6000", name="Advertising & Marketing", description="Ads, campaigns, sponsorships, design"),
    Account(code="6010", name="Bank & Merchant Fees", description="Bank charges, card processing fees, FX fees"),
    Account(code="6020", name="Computer Equipment", description="Laptops, monitors, peripherals, phones"),
    Account(code="6030", name="Dues & Subscriptions", description="Software SaaS subscriptions, memberships"),
    Account(code="6040", name="Insurance", description="Business, liability and equipment insurance premiums"),
    Account(code="6050", name="Meals & Entertainment", description="Client meals, team meals, coffee"),
    Account(code="6060", name="Office Supplies", description="Stationery, printer supplies, small consumables"),
    Account(code="6070", name="Postage & Shipping", description="Couriers, postage, freight"),
    Account(code="6080", name="Professional Fees", description="Legal, accounting, bookkeeping, consultants"),
    Account(code="6090", name="Rent", description="Office rent, coworking desks, storage"),
    Account(code="6100", name="Repairs & Maintenance", description="Equipment and premises repairs, cleaning"),
    Account(code="6110", name="Telephone & Internet", description="Mobile plans, broadband, VoIP"),
    Account(code="6120", name="Training & Education", description="Courses, certifications, books, conferences"),
    Account(code="6130", name="Travel — Airfare", description="Flights and airline fees"),
    Account(code="6140", name="Travel — Lodging", description="Hotels and short-stay accommodation"),
    Account(code="6150", name="Travel — Ground Transport", description="Taxis, rideshare, rail, car hire, parking"),
    Account(code="6160", name="Utilities", description="Electricity, water, gas for business premises"),
    Account(code="6170", name="Contractor & Payroll Services", description="Contractors, payroll platform fees"),
    Account(code="6180", name="Fuel & Vehicle", description="Fuel, tolls, vehicle servicing"),
    Account(code="6190", name="Cloud Hosting", description="IaaS/PaaS compute, storage, bandwidth, CDN"),
)

CODES: frozenset[str] = frozenset(a.code for a in DEFAULT_COA)


def account(code: str) -> Account:
    for a in DEFAULT_COA:
        if a.code == code:
            return a
    raise KeyError(f"{code} is not in the default chart of accounts")
