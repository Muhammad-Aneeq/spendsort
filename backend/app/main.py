"""FastAPI application entrypoint.

Architecture (spec 11 section 5):
    [SPA] <-> [FastAPI] <-> [SQLite]
                  |-- LangGraph categorizer (OpenAI, structured output)
                  |-- vendor_memory store
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.logging import configure_logging, get_logger
from app.settings import REPO_ROOT, get_settings

settings = get_settings()
configure_logging(settings.log_level)
log = get_logger("spendsort.app")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    log.info(
        "startup",
        extra={
            "context": {
                "version": __version__,
                "env": settings.env,
                "model": settings.model,
                "auto_threshold": settings.auto_threshold,
                "cost_cap_usd_per_run": settings.cost_cap_usd_per_run,
                "llm_mode": "mock" if settings.use_mock_llm else "live",
            }
        },
    )
    yield
    log.info("shutdown")


app = FastAPI(
    title="SpendSort API",
    version=__version__,
    summary="Expense categorization with confidence gates and a learning vendor memory.",
    description=(
        "Every categorization carries a confidence and a one-line reason. "
        "Only decisions at or above the threshold auto-apply; the rest are queued for review. "
        "\n\n**All data is synthetic.**"
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", tags=["meta"])
def health() -> dict[str, object]:
    """Liveness plus the settings that govern trust, so the UI can display them honestly."""
    return {
        "status": "ok",
        "version": __version__,
        "auto_threshold": settings.auto_threshold,
        "cost_cap_usd_per_run": settings.cost_cap_usd_per_run,
        "model": settings.model,
        "llm_mode": "mock" if settings.use_mock_llm else "live",
        "synthetic_data": True,
    }


def _mount_spa() -> None:
    """Serve the built SPA when it exists (docker/prod). In dev, Vite serves it instead."""
    from pathlib import Path

    from fastapi.staticfiles import StaticFiles

    dist = REPO_ROOT / "frontend" / "dist"
    if (dist / "index.html").exists():
        # html=True makes unknown paths fall back to index.html for client-side routing.
        app.mount("/", StaticFiles(directory=Path(dist), html=True), name="spa")
        log.info("spa mounted", extra={"context": {"dist": str(dist)}})


_mount_spa()
