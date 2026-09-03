"""Run the eval suite against the REAL model. This spends money.

    make eval-live
    # or:  PYTHONPATH=backend uv run python evals/run_live.py

Why this exists as a separate entrypoint: everything in CI runs against `MockCategorizer`, so
the CI number measures the harness, not a model (BLOCKERS.md B3). This is the command that
produces the honest quality figure, and the one to run before quoting an auto-precision number
anywhere public.

Cost: 100 cases, minus memory hits, on a mini-class model — roughly $0.01-0.02 at the prices in
`app/costs.py`. The per-run cost cap does not apply here; evals measure decision quality, and
capping them would silently truncate the suite.

Exit code is 0 when the >=95% auto-precision gate passes, 1 when it does not, so this can be
wired into a release check.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Make `app` and `ledgerfab` importable when run as a bare script.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the SpendSort eval suite against the real model.")
    parser.add_argument("--threshold", type=float, default=None, help="Override the auto-apply threshold")
    parser.add_argument("--model", type=str, default=None, help="Override the model id")
    parser.add_argument(
        "--out", type=Path, default=Path(__file__).parent / "report_live.json", help="Where to write the report"
    )
    args = parser.parse_args()

    if args.model:
        os.environ["SPENDSORT_MODEL"] = args.model
    # Force the real client, whatever .env says.
    os.environ["SPENDSORT_MOCK_LLM"] = "0"

    from app.settings import get_settings

    get_settings.cache_clear()
    settings = get_settings()

    if not settings.openai_api_key:
        print(
            "OPENAI_API_KEY / SPENDSORT_OPENAI_API_KEY is not set.\n"
            "This command calls the real OpenAI API. Set the key and retry, or run\n"
            "`make eval` for the mock-mode gate.",
            file=sys.stderr,
        )
        return 2

    from app.agent.llm import OpenAICategorizer
    from harness import AUTO_PRECISION_GATE, load_cases, run_eval

    cases = load_cases()
    print(f"Running {len(cases)} cases against {settings.model} (temperature {settings.temperature}).")
    print("This spends real money. Ctrl+C to abort.\n")

    report = run_eval(
        categorizer=OpenAICategorizer(),
        auto_threshold=args.threshold,
        cases=cases,
        mode="live",
    )

    print(report.render())
    path = report.write(args.out)
    print(f"  report written to {path}")
    print(
        f"  NOTE: this is a LIVE measurement of {settings.model}. "
        "The number in CI is mock-mode and measures the harness only.\n"
    )

    if not report.passed:
        print(
            f"GATE FAILED: auto-precision {100 * report.auto_precision:.2f}% < {100 * AUTO_PRECISION_GATE:.0f}%",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
