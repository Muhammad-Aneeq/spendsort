"""Smoke tests for the API surface (spec 11 section 7). Grows one endpoint per phase."""

from __future__ import annotations


def test_health_reports_the_trust_settings(client):
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


def test_openapi_schema_builds(client):
    """A broken route signature should fail here rather than at demo time."""
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    assert resp.json()["info"]["title"] == "SpendSort API"
