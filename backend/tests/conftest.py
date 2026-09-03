"""Shared test fixtures.

The LLM is mocked by default (adaptation 3) — no test in the default run spends money or
needs a key. Live tests carry the `live` marker and are deselected unless asked for.

The database is redirected to a throwaway file **before any app module is imported**, because
`app.db` builds its engine at import time from the settings. Without this, running the suite
would write into the developer's `backend/spendsort.db`.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

_TMP_DB = Path(tempfile.gettempdir()) / "spendsort_test.db"

os.environ.setdefault("SPENDSORT_MOCK_LLM", "1")
os.environ.setdefault("SPENDSORT_ENV", "test")
os.environ.setdefault("SPENDSORT_LOG_LEVEL", "WARNING")
os.environ.setdefault("SPENDSORT_DATABASE_URL", f"sqlite:///{_TMP_DB.as_posix()}")


@pytest.fixture(autouse=True)
def clean_db():
    """Every test starts from empty tables, so ordering can never create a false pass."""
    import app.models  # noqa: F401  (registers mappers)
    from app.db import Base, engine

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    """A session for tests that talk to the ORM directly."""
    from app.db import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    """FastAPI TestClient against the app."""
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def coa():
    """The default chart of accounts, freshly loaded."""
    from app.coa import reload_coa

    return reload_coa()


def csv_bytes(rows: list[str], header: str = "date,amount,currency,vendor,memo") -> bytes:
    """Build an upload payload from literal CSV lines."""
    return ("\n".join([header, *rows]) + "\n").encode("utf-8")
