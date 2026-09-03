"""World -> files.

Two jobs:
  1. Render a World as the transactions CSV a bookkeeper would upload
     (spec 11 section 4 F1: "date, amount, vendor/description, currency").
  2. Regenerate the committed artefacts — `examples/*.csv` and `backend/app/coa_default.yaml` —
     from fixed seeds, so the demo data and the app's default CoA are reproducible and aligned.

Run as:  python -m ledgerfab.export      (wired to `make seed`)

Ground truth is deliberately NOT written into the upload CSVs. The agent must earn its answers
from the descriptor alone; the labels go to `evals/` separately.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from io import StringIO
from pathlib import Path

from ledgerfab.coa import DEFAULT_COA
from ledgerfab.config import PRESETS, Profile
from ledgerfab.generate import generate
from ledgerfab.models import World

# backend/ledgerfab/export.py -> backend/ledgerfab -> backend -> <repo root>
REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_DIR = REPO_ROOT / "examples"
COA_YAML = REPO_ROOT / "backend" / "app" / "coa_default.yaml"

UPLOAD_COLUMNS: tuple[str, ...] = ("date", "amount", "currency", "vendor", "memo")


def transactions_csv(world: World) -> str:
    """The upload CSV: what the bank feed gives you, nothing more."""
    buffer = StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(UPLOAD_COLUMNS)
    for txn in world.transactions:
        writer.writerow(
            [
                txn.date_raw,  # possibly a chaotic format, on purpose
                f"{txn.amount:.2f}",
                txn.currency,
                txn.vendor_raw,
                txn.memo or "",
            ]
        )
    return buffer.getvalue()


def ground_truth_csv(world: World) -> str:
    """The labels, kept in a separate file so they can never leak into an upload."""
    buffer = StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["txn_id", "date", "vendor", "account_code", "counterparty", "ambiguous", "alternate"])
    truth = world.ground_truth.by_txn()
    for txn in world.transactions:
        entry = truth[txn.id]
        writer.writerow(
            [
                txn.id,
                txn.date.isoformat(),
                txn.vendor_raw,
                entry.account_code,
                entry.counterparty_canonical,
                "yes" if entry.ambiguous else "no",
                entry.alternate_account_code or "",
            ]
        )
    return buffer.getvalue()


def coa_yaml() -> str:
    """Render the canonical CoA as the app's editable YAML (spec 11 section 4 F1)."""
    lines = [
        "# SpendSort default chart of accounts.",
        "#",
        "# GENERATED from backend/ledgerfab/coa.py by `python -m ledgerfab.export` (`make seed`).",
        "# Edit ledgerfab/coa.py and regenerate, or edit here and accept that eval ground truth",
        "# will no longer be CoA-aligned — a test asserts the two stay in step.",
        "#",
        "# There is deliberately no 'Uncategorized' account: a catch-all gives the agent",
        "# somewhere to hide a guess, and unconfident answers belong with a human instead.",
        "accounts:",
    ]
    for acct in DEFAULT_COA:
        lines.append(f'  - code: "{acct.code}"')
        lines.append(f'    name: "{acct.name}"')
        lines.append(f'    kind: "{acct.kind}"')
        lines.append(f'    description: "{acct.description}"')
    return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class ExampleSpec:
    filename: str
    profile: Profile
    seed: int
    note: str


def _example_specs() -> tuple[ExampleSpec, ...]:
    realistic = PRESETS["realistic"]
    return (
        ExampleSpec(
            filename="month_01_realistic_seed42.csv",
            profile=realistic.model_copy(update={"period_start": date(2026, 1, 1), "period_days": 31}),
            seed=42,
            note="First run. Vendor memory is cold, so almost everything costs an LLM call.",
        ),
        ExampleSpec(
            filename="month_02_realistic_seed43.csv",
            profile=realistic.model_copy(update={"period_start": date(2026, 2, 1), "period_days": 28}),
            seed=43,
            note=(
                "Second run, same vendor catalogue. Memory now covers the repeat vendors, so the "
                "LLM is called less and cost-per-run bends downward — this is the launch-post chart."
            ),
        ),
        ExampleSpec(
            filename="ambiguous_edge_cases.csv",
            profile=realistic.model_copy(
                update={
                    "period_start": date(2026, 3, 1),
                    "period_days": 31,
                    "txn_count": 24,
                    "ambiguous_rate": 1.0,
                }
            ),
            seed=77,
            note=(
                "Every row is a vendor with two defensible accounts (Amazon, Uber, Airbnb, ...). "
                "Correct behaviour is LOW confidence and a queued row, not a lucky guess."
            ),
        ),
    )


def write_examples(out_dir: Path = EXAMPLES_DIR) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    readme = [
        "# examples/",
        "",
        "**⚠️ All data synthetic.** Generated by `ledgerfab` (spec 00 A3) from the seeds below.",
        "Regenerate with `make seed` (or `./make.ps1 seed`) — same seed + profile gives byte-identical output.",
        "",
        "Upload these on the Import screen. Columns: `date, amount, currency, vendor, memo`.",
        "Ground truth is **not** in these files; the labels live in `evals/`.",
        "",
        "| file | profile | seed | rows | period | what it is for |",
        "|---|---|---|---|---|---|",
    ]

    for spec in _example_specs():
        world = generate(spec.profile, spec.seed)
        path = out_dir / spec.filename
        path.write_text(transactions_csv(world), encoding="utf-8", newline="")
        written.append(path)

        readme.append(
            f"| `{spec.filename}` | {spec.profile.name} | {spec.seed} | "
            f"{len(world.transactions)} | {spec.profile.period_start.strftime('%b %Y')} | {spec.note} |"
        )

    readme += [
        "",
        "## Determinism",
        "",
        "Each world is hash-verifiable (spec 00 A3). Current content hashes:",
        "",
        "| file | sha256 (world) |",
        "|---|---|",
    ]
    for spec in _example_specs():
        world = generate(spec.profile, spec.seed)
        readme.append(f"| `{spec.filename}` | `{world.content_hash()[:32]}…` |")

    readme_path = out_dir / "README.md"
    readme_path.write_text("\n".join(readme) + "\n", encoding="utf-8")
    written.append(readme_path)
    return written


def write_coa_yaml(path: Path = COA_YAML) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(coa_yaml(), encoding="utf-8")
    return path


def main() -> None:
    coa = write_coa_yaml()
    print(f"wrote {coa.relative_to(REPO_ROOT)}  ({len(DEFAULT_COA)} accounts)")
    for path in write_examples():
        print(f"wrote {path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
