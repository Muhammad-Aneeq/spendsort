"""Shared test fixtures.

The LLM is mocked by default (adaptation 3) — no test in the default run spends money or
needs a key. Live tests carry the `live` marker and are deselected unless asked for.
"""

from __future__ import annotations

import os

import pytest

# Set before any app module is imported, so Settings picks it up.
os.environ.setdefault("SPENDSORT_MOCK_LLM", "1")
os.environ.setdefault("SPENDSORT_ENV", "test")
os.environ.setdefault("SPENDSORT_LOG_LEVEL", "WARNING")


@pytest.fixture
def client():
    """FastAPI TestClient against the app."""
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c
