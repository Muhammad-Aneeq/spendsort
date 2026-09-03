# SpendSort — single-image demo build: the API serves the built SPA.

# --- stage 1: build the SPA -------------------------------------------------
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-fund --no-audit
COPY frontend/ ./
RUN npm run build

# --- stage 2: runtime -------------------------------------------------------
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/backend \
    PATH="/app/.venv/bin:$PATH"

# Dependencies first, so code changes do not invalidate the dependency layer.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY backend/ ./backend/
COPY evals/ ./evals/
COPY examples/ ./examples/
COPY --from=web /web/dist ./frontend/dist

# SQLite lives on the mounted volume (see docker-compose.yml).
RUN mkdir -p /data && \
    useradd --create-home --uid 10001 spendsort && \
    chown -R spendsort:spendsort /app /data
USER spendsort

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
