"""Eval scoring — spec 11 section 10.

    "metrics: accuracy, auto-precision (accuracy of auto-applied only: must be >= 95%),
     queue-recall (wrong ones must land in queue, not auto)"

The three metrics answer three different questions, and only the last two really matter:

* **accuracy** — how often is the agent right? Interesting, but not a safety property.
* **auto-precision** — of the decisions it made *without a human*, how many were right? This is
  the number that decides whether the thing can be trusted, and the CI gate.
* **queue-recall** — of the decisions it got *wrong*, how many did it queue instead of posting?
  This is the honesty metric. An agent that is wrong but knows it is fine; an agent that is
  wrong and confident is the one that costs a bookkeeper their afternoon.

The eval runs the **whole system**, memory included, starting from an empty memory. That means
within-run promotion is in scope: if the first Amazon is confidently wrong and auto-applied,
later Amazons inherit it. That amplification is a genuine risk of the design, so it is measured
rather than excluded.
"""

from __future__ import annotations

import contextlib
import json
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

EVALS_DIR = Path(__file__).parent
CASES_PATH = EVALS_DIR / "cases.jsonl"
REPORT_PATH = EVALS_DIR / "report.json"

# spec 11 section 10: the CI gate.
AUTO_PRECISION_GATE = 0.95


@dataclass
class CaseResult:
    case_id: str
    vendor_raw: str
    vendor_norm: str
    expected: str
    predicted: str
    confidence: float
    status: str  # auto | queued
    source: str  # memory | llm
    coa_valid: bool
    ambiguous: bool
    cost_usd: float

    @property
    def correct(self) -> bool:
        return self.predicted == self.expected

    @property
    def auto(self) -> bool:
        return self.status == "auto"


@dataclass
class EvalReport:
    mode: str = "mock"
    model: str = ""
    auto_threshold: float = 0.0
    total: int = 0

    correct: int = 0
    auto_count: int = 0
    auto_correct: int = 0
    queued_count: int = 0
    wrong_total: int = 0
    wrong_queued: int = 0

    ambiguous_total: int = 0
    ambiguous_queued: int = 0

    out_of_coa: int = 0
    memory_hits: int = 0
    llm_calls: int = 0
    total_cost_usd: float = 0.0

    results: list[CaseResult] = field(default_factory=list)
    generated_at: str = ""

    # --- the three metrics ---------------------------------------------
    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0

    @property
    def auto_precision(self) -> float:
        """Accuracy of auto-applied decisions ONLY. The CI gate.

        With nothing auto-applied this is 1.0 by convention — vacuously true, and the reason
        the gate is paired with a minimum auto-rate check in the test module: an agent that
        queues everything would otherwise score a perfect 100%.
        """
        return self.auto_correct / self.auto_count if self.auto_count else 1.0

    @property
    def queue_recall(self) -> float:
        """Of the decisions that were WRONG, how many landed in the queue?

        1.0 when nothing was wrong. This is the metric that catches confident errors.
        """
        return self.wrong_queued / self.wrong_total if self.wrong_total else 1.0

    @property
    def auto_rate(self) -> float:
        return self.auto_count / self.total if self.total else 0.0

    @property
    def ambiguous_queued_rate(self) -> float:
        """spec 11 section 14: on genuinely ambiguous vendors, confidence must drop."""
        return self.ambiguous_queued / self.ambiguous_total if self.ambiguous_total else 1.0

    @property
    def passed(self) -> bool:
        return self.auto_precision >= AUTO_PRECISION_GATE

    def summary(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "model": self.model,
            "auto_threshold": self.auto_threshold,
            "total_cases": self.total,
            "accuracy": round(self.accuracy, 4),
            "auto_precision": round(self.auto_precision, 4),
            "auto_precision_gate": AUTO_PRECISION_GATE,
            "queue_recall": round(self.queue_recall, 4),
            "auto_rate": round(self.auto_rate, 4),
            "auto_count": self.auto_count,
            "queued_count": self.queued_count,
            "wrong_total": self.wrong_total,
            "wrong_queued": self.wrong_queued,
            "wrong_auto_applied": self.wrong_total - self.wrong_queued,
            "ambiguous_total": self.ambiguous_total,
            "ambiguous_queued_rate": round(self.ambiguous_queued_rate, 4),
            "out_of_coa_answers": self.out_of_coa,
            "memory_hits": self.memory_hits,
            "llm_calls": self.llm_calls,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "passed": self.passed,
            "generated_at": self.generated_at,
        }

    def write(self, path: Path = REPORT_PATH) -> Path:
        payload = {"summary": self.summary(), "cases": [asdict(r) for r in self.results]}
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def render(self) -> str:
        s = self.summary()
        gate = "PASS" if self.passed else "FAIL"
        lines = [
            "",
            f"  SpendSort eval — {self.total} ledgerfab cases, mode={self.mode}, model={self.model or 'n/a'}",
            f"  threshold={self.auto_threshold:.2f}",
            "  " + "-" * 62,
            f"  accuracy              {100 * self.accuracy:6.2f}%   (all decisions)",
            f"  auto-precision        {100 * self.auto_precision:6.2f}%   "
            f"GATE >= {100 * AUTO_PRECISION_GATE:.0f}%  [{gate}]",
            f"  queue-recall          {100 * self.queue_recall:6.2f}%   "
            f"({self.wrong_queued}/{self.wrong_total} wrong answers were queued)",
            f"  auto-rate             {100 * self.auto_rate:6.2f}%   "
            f"({self.auto_count} auto, {self.queued_count} queued)",
            "  " + "-" * 62,
            f"  wrong AND auto-applied     {s['wrong_auto_applied']}   <- the ones that hurt",
            f"  ambiguous cases queued     {self.ambiguous_queued}/{self.ambiguous_total}",
            f"  out-of-CoA answers caught  {self.out_of_coa}",
            f"  memory hits / llm calls    {self.memory_hits} / {self.llm_calls}",
            f"  total cost                 ${self.total_cost_usd:.6f}",
            "",
        ]
        return "\n".join(lines)


def load_cases(path: Path = CASES_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"{path} not found — run `python evals/build_cases.py`")
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _isolated_session():  # type: ignore[no-untyped-def]
    """A throwaway database, so an eval never touches the dev DB and always starts from an
    empty vendor memory. A warm memory would flatter the result."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import app.models  # noqa: F401  (registers mappers)
    from app.db import Base

    path = Path(tempfile.gettempdir()) / f"spendsort_eval_{uuid.uuid4().hex[:8]}.db"
    engine = create_engine(f"sqlite:///{path.as_posix()}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    # The engine is returned too: on Windows the file stays locked until it is disposed.
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine, path


def run_eval(
    *,
    categorizer: Any | None = None,
    auto_threshold: float | None = None,
    cases: list[dict[str, Any]] | None = None,
    mode: str | None = None,
) -> EvalReport:
    """Score the whole system over the case file."""
    from app.agent.graph import build_graph
    from app.agent.llm import build_categorizer
    from app.coa import get_coa
    from app.models import MemorySource, TxnStatus
    from app.services import memory as memory_service
    from app.settings import get_settings

    settings = get_settings()
    coa = get_coa()
    threshold = auto_threshold if auto_threshold is not None else settings.auto_threshold
    resolved = categorizer or build_categorizer()
    rows = cases if cases is not None else load_cases()

    session, engine, db_path = _isolated_session()
    report = EvalReport(
        mode=mode or ("mock" if settings.use_mock_llm else "live"),
        model=getattr(resolved, "name", "unknown"),
        auto_threshold=threshold,
        total=len(rows),
        generated_at=datetime.now().astimezone().isoformat(timespec="seconds"),
    )

    try:
        graph = build_graph(session, categorizer=resolved, coa=coa)
        coa_block = coa.prompt_block()

        for index, case in enumerate(rows):
            state = graph.invoke(
                {
                    "txn_id": index,
                    "vendor_raw": case["vendor_raw"],
                    "amount": float(case["amount"]),
                    "currency": case.get("currency", "USD"),
                    "date": case.get("date", date(2026, 1, 1).isoformat()),
                    "memo": case.get("memo"),
                    "coa_block": coa_block,
                    "auto_threshold": threshold,
                    # Evals measure decision quality, not the cost cap (which has its own
                    # tests), so the budget is deliberately not binding here.
                    "budget_remaining_usd": 1_000.0,
                    "trace": [],
                }
            )

            result = CaseResult(
                case_id=str(case["case_id"]),
                vendor_raw=case["vendor_raw"],
                vendor_norm=state.get("vendor_norm", ""),
                expected=str(case["expected_account_code"]),
                predicted=str(state.get("account_code", "") or ""),
                confidence=float(state.get("confidence", 0.0) or 0.0),
                status=str(state.get("status", TxnStatus.QUEUED.value)),
                source=str(state.get("source", "llm")),
                coa_valid=bool(state.get("coa_valid", False)),
                ambiguous=bool(case.get("ambiguous", False)),
                cost_usd=float(state.get("cost_usd", 0.0) or 0.0),
            )
            report.results.append(result)

            # --- tally -------------------------------------------------
            if result.correct:
                report.correct += 1
            else:
                report.wrong_total += 1
                if not result.auto:
                    report.wrong_queued += 1

            if result.auto:
                report.auto_count += 1
                if result.correct:
                    report.auto_correct += 1
            else:
                report.queued_count += 1

            if result.ambiguous:
                report.ambiguous_total += 1
                if not result.auto:
                    report.ambiguous_queued += 1

            if not result.coa_valid:
                report.out_of_coa += 1

            if result.source == "memory":
                report.memory_hits += 1
            else:
                report.llm_calls += 1
            report.total_cost_usd += result.cost_usd

            # Mirror production: a trusted answer is promoted to memory, so within-run
            # error amplification is part of what gets measured.
            if result.auto and result.source == "llm" and result.coa_valid:
                memory_service.remember(
                    session,
                    vendor_norm=state.get("vendor_norm", ""),
                    account_code=result.predicted,
                    source=MemorySource.LLM_CONFIRMED,
                    example_vendor_raw=result.vendor_raw,
                )
        session.commit()
    finally:
        session.close()
        engine.dispose()  # on Windows the file stays locked until this happens
        with contextlib.suppress(OSError):
            # A leftover temp file is not worth failing an eval run over.
            db_path.unlink(missing_ok=True)

    return report
