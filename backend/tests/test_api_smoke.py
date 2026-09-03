"""Every endpoint of spec 11 section 7, exercised through HTTP.

    "POST /api/ingest/csv · POST /api/runs (categorize all pending) · GET /api/queue ·
     POST /api/txns/{id}/verdict · GET /api/memory · GET /api/metrics · GET /api/export."

The last test walks the whole Definition of Done in one pass, so a break anywhere in the demo
path fails here rather than in front of an audience.
"""

from __future__ import annotations

from app.settings import REPO_ROOT
from tests.conftest import csv_bytes

EXAMPLE = REPO_ROOT / "examples" / "month_01_realistic_seed42.csv"


def upload(client, rows: list[str], name: str = "m.csv"):  # type: ignore[no-untyped-def]
    return client.post("/api/ingest/csv", files={"file": (name, csv_bytes(rows), "text/csv")})


# --- meta --------------------------------------------------------------------


def test_health_reports_the_trust_settings(client) -> None:
    """Health is not just liveness: it publishes the gate settings the UI must show honestly."""
    resp = client.get("/api/health")
    assert resp.status_code == 200

    body = resp.json()
    assert body["status"] == "ok"
    assert 0.0 <= body["auto_threshold"] <= 1.0
    # spec 11 section 11: "cost cap per run (default $0.25)"
    assert body["cost_cap_usd_per_run"] == 0.25
    assert body["llm_mode"] == "mock"  # default test run never calls OpenAI
    assert body["synthetic_data"] is True


def test_openapi_schema_builds(client) -> None:
    """A broken route signature should fail here rather than at demo time."""
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    assert resp.json()["info"]["title"] == "SpendSort API"


def test_every_spec_endpoint_is_registered(client) -> None:
    """spec 11 section 7, checked against the live schema rather than a comment."""
    paths = client.get("/openapi.json").json()["paths"]

    assert "post" in paths["/api/ingest/csv"]
    assert "post" in paths["/api/runs"]
    assert "get" in paths["/api/queue"]
    assert "post" in paths["/api/txns/{txn_id}/verdict"]
    assert "get" in paths["/api/memory"]
    assert "get" in paths["/api/metrics"]
    assert "get" in paths["/api/export"]
    # Plus the editable chart of accounts (spec 11 section 4 F1).
    assert "get" in paths["/api/coa"] and "put" in paths["/api/coa"]


# --- queue -------------------------------------------------------------------


def test_the_queue_is_empty_before_anything_is_uploaded(client) -> None:
    body = client.get("/api/queue").json()
    assert body["total"] == 0
    assert body["items"] == []
    assert 0.0 < body["auto_threshold"] <= 1.0


def test_the_queue_is_sorted_lowest_confidence_first(client) -> None:
    """spec 11 section 4 F3. The ordering is the feature: a bookkeeper working top-down meets
    the worst guesses first, where their attention is worth most."""
    upload(
        client,
        [
            "2026-01-01,10.00,USD,AMZN Mktp US*Y7D8K6,",  # mock is unsure -> queued
            "2026-01-02,20.00,USD,UBER *TRIP 4K2J91,",  # unsure -> queued
            "2026-01-03,30.00,USD,BRIGHTLINE CLEANING,",  # unrecognised -> very low
            "2026-01-04,40.00,USD,Slack.com,",  # confident -> auto
        ],
    )
    client.post("/api/runs")

    items = client.get("/api/queue").json()["items"]
    assert len(items) >= 3

    confidences = [i["suggestion"]["confidence"] for i in items]
    assert confidences == sorted(confidences), f"queue is not lowest-confidence-first: {confidences}"


def test_a_queued_row_carries_everything_the_reviewer_needs(client) -> None:
    """spec 11 section 9 screen 3: "row: vendor, amount, suggested account, ConfidencePill,
    reason"."""
    upload(client, ["2026-01-01,120.00,USD,AMZN Mktp US*Y7D8K6,INV-9"])
    client.post("/api/runs")

    item = client.get("/api/queue").json()["items"][0]
    assert item["vendor_raw"] == "AMZN Mktp US*Y7D8K6"
    assert item["vendor_norm"] == "AMAZON MARKETPLACE"
    assert item["amount"] == 120.0
    assert item["status"] == "queued"
    assert item["suggestion"]["account_code"]
    assert item["suggestion"]["reason"]
    assert 0.0 <= item["suggestion"]["confidence"] <= 1.0


def test_transactions_can_be_filtered_by_status(client) -> None:
    upload(client, ["2026-01-01,10.00,USD,Slack.com,", "2026-01-02,20.00,USD,BRIGHTLINE CLEANING,"])
    client.post("/api/runs")

    auto = client.get("/api/queue/transactions", params={"status": "auto"}).json()
    queued = client.get("/api/queue/transactions", params={"status": "queued"}).json()
    every = client.get("/api/queue/transactions").json()

    assert auto["total"] >= 1
    assert queued["total"] >= 1
    assert every["total"] == auto["total"] + queued["total"]


# --- runs --------------------------------------------------------------------


def test_a_run_with_nothing_pending_is_not_an_error(client) -> None:
    """The UI should not have to guard the button, and the run history should be honest about
    having been asked."""
    resp = client.post("/api/runs")
    assert resp.status_code == 201
    assert resp.json()["txn_count"] == 0


def test_the_run_list_is_oldest_first(client) -> None:
    """This series is the memory-bend chart, so its order is load-bearing."""
    upload(client, ["2026-01-01,10.00,USD,Slack.com,"])
    client.post("/api/runs")
    upload(client, ["2026-02-01,10.00,USD,Slack.com,"], name="m2.csv")
    client.post("/api/runs")

    ids = [r["id"] for r in client.get("/api/runs").json()]
    assert ids == sorted(ids)
    assert len(ids) == 2


def test_a_run_records_the_settings_it_was_judged_under(client) -> None:
    upload(client, ["2026-01-01,10.00,USD,Slack.com,"])
    run = client.post("/api/runs").json()

    assert run["auto_threshold"] == 0.85
    assert run["cost_cap_usd"] == 0.25
    assert run["llm_mode"] == "mock"
    assert run["model"]


# --- memory ------------------------------------------------------------------


def test_memory_starts_empty(client) -> None:
    body = client.get("/api/memory").json()
    assert body["total"] == 0
    assert body["entries"] == []


def test_memory_lists_learned_mappings_with_hit_counts(client) -> None:
    """spec 11 section 9 screen 4: "learned mappings table, hit counts"."""
    upload(client, ["2026-01-01,10.00,USD,Slack.com,", "2026-01-02,12.00,USD,SLACK TECHNOLOGIES,"])
    client.post("/api/runs")

    body = client.get("/api/memory").json()
    assert body["total"] >= 1

    entry = body["entries"][0]
    assert entry["vendor_norm"]
    assert entry["account_name"], "the UI should not have to look up the code"
    assert entry["source"] in {"human", "llm-confirmed"}
    assert entry["hit_count"] >= 0


def test_an_override_appears_in_memory_as_human(client) -> None:
    upload(client, ["2026-01-01,120.00,USD,AMZN Mktp US*Y7D8K6,"])
    client.post("/api/runs")
    txn_id = client.get("/api/queue").json()["items"][0]["id"]

    client.post(f"/api/txns/{txn_id}/verdict", json={"action": "override", "final_account": "6020"})

    entries = {e["vendor_norm"]: e for e in client.get("/api/memory").json()["entries"]}
    assert entries["AMAZON MARKETPLACE"]["source"] == "human"
    assert entries["AMAZON MARKETPLACE"]["account_code"] == "6020"


# --- metrics -----------------------------------------------------------------


def test_metrics_are_safe_to_read_before_any_data(client) -> None:
    body = client.get("/api/metrics").json()
    assert body["total_transactions"] == 0
    assert body["auto_rate"] == 0.0
    assert len(body["confidence_histogram"]) == 10
    assert body["runs"] == []


def test_metrics_carry_everything_the_dashboard_needs(client) -> None:
    """spec 11 section 4 F5: confidence histogram, auto-rate, memory-hit rate, cost-per-run,
    category breakdown."""
    resp = client.post(
        "/api/ingest/csv",
        files={"file": (EXAMPLE.name, EXAMPLE.read_bytes(), "text/csv")},
    )
    assert resp.status_code == 201
    client.post("/api/runs")

    body = client.get("/api/metrics").json()

    assert body["total_transactions"] == 120
    assert 0.0 < body["auto_rate"] <= 1.0
    assert 0.0 <= body["memory_hit_rate"] <= 1.0
    assert body["total_cost_usd"] > 0.0
    assert body["auto_threshold"] == 0.85

    # Histogram: ten bins, marked either side of the gate, summing to the decisions made.
    histogram = body["confidence_histogram"]
    assert len(histogram) == 10
    assert sum(b["count"] for b in histogram) == 120
    # The gate shows up as a boundary in the bins: the top bin is auto, the bottom is not.
    assert histogram[-1]["auto"] is True
    assert histogram[0]["auto"] is False

    assert body["category_breakdown"], "no spend breakdown"
    assert all(item["account_name"] for item in body["category_breakdown"])
    assert len(body["runs"]) == 1


def test_the_run_series_shows_the_memory_bend(client) -> None:
    """spec 11 section 8: "the dashboard proves it: that chart IS the launch post".

    This is the assertion the launch claim rests on, so it is a real test rather than a hope:
    across two months of the same vendor catalogue, the memory-hit rate must RISE and the
    cost per run must FALL.
    """
    month_1 = REPO_ROOT / "examples" / "month_01_realistic_seed42.csv"
    month_2 = REPO_ROOT / "examples" / "month_02_realistic_seed43.csv"

    for path in (month_1, month_2):
        assert (
            client.post("/api/ingest/csv", files={"file": (path.name, path.read_bytes(), "text/csv")}).status_code
            == 201
        )
        client.post("/api/runs")

    runs = client.get("/api/metrics").json()["runs"]
    assert len(runs) == 2
    first, second = runs

    assert second["memory_hit_rate"] > first["memory_hit_rate"], "memory-hit rate did not rise"
    assert second["cost_usd"] < first["cost_usd"], "cost per run did not fall"
    assert second["llm_calls"] < first["llm_calls"], "the LLM was not called less"


# --- the whole demo path -----------------------------------------------------


def test_the_definition_of_done_end_to_end(client) -> None:
    """upload CSV → run → review queue → override → re-run → learned → export.

    One test for the whole demo, so the path cannot rot silently between phases.
    """
    # 1. upload
    first = client.post(
        "/api/ingest/csv",
        files={"file": (EXAMPLE.name, EXAMPLE.read_bytes(), "text/csv")},
    ).json()
    assert first["accepted"] == 120
    assert first["rejected"] == 0

    # 2. run
    run_1 = client.post("/api/runs").json()
    assert run_1["txn_count"] == 120

    # 3. review queue, lowest confidence first
    queue = client.get("/api/queue").json()
    assert queue["total"] > 0
    target = queue["items"][0]

    # 4. override -> memory
    verdict = client.post(
        f"/api/txns/{target['id']}/verdict",
        json={"action": "override", "final_account": "6020"},
    ).json()
    assert verdict["memory_written"] is True
    assert verdict["final_account_name"] == "Computer Equipment"

    # 5. the same vendor next month is answered from memory, and marked learned
    month_2 = REPO_ROOT / "examples" / "month_02_realistic_seed43.csv"
    client.post("/api/ingest/csv", files={"file": (month_2.name, month_2.read_bytes(), "text/csv")})
    run_2 = client.post("/api/runs").json()

    assert run_2["memory_hit_rate"] > run_1["memory_hit_rate"]
    assert run_2["cost_usd"] < run_1["cost_usd"]

    learned = [
        t for t in client.get("/api/queue/transactions", params={"status": "auto"}).json()["items"] if t["learned"]
    ]
    assert learned, "no line was marked learned after an override"

    # 6. dashboard
    metrics = client.get("/api/metrics").json()
    assert metrics["total_transactions"] == 240
    assert len(metrics["runs"]) == 2

    # 7. export, with the four required per-line fields
    export = client.get("/api/export")
    assert export.status_code == 200
    text = export.content.decode("utf-8-sig")
    header = text.splitlines()[0]
    for field in ("account", "confidence", "source", "reason"):
        assert field in header
    assert len(text.strip().splitlines()) == 241  # header + 240 lines
