# SpendSort — task runner (spec 00 A1: "Makefile (dev, test, eval, up, down)").
#
# `make` is not installed on the primary dev box (BLOCKERS.md B2); `make.ps1` mirrors every
# target below for PowerShell. Keep the two files in lockstep.

.DEFAULT_GOAL := help
.PHONY: help install dev dev-api dev-web test test-live eval eval-live seed lint fmt typecheck up down clean

# Override when 8000 is taken (BLOCKERS.md B6):  make dev PORT=8123
PORT ?= 8000
export VITE_API_PORT = $(PORT)

help: ## Show available targets
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Install backend (uv) and frontend (npm) dependencies
	uv sync
	cd frontend && npm install

dev: ## Run API + SPA together (the demo entrypoint)
	@echo "API  -> http://127.0.0.1:$(PORT)/docs"
	@echo "SPA  -> http://127.0.0.1:5173"
	@$(MAKE) -j2 dev-api dev-web

dev-api: ## Run the FastAPI backend with reload
	uv run uvicorn app.main:app --app-dir backend --reload --port $(PORT)

dev-web: ## Run the Vite dev server
	cd frontend && npm run dev

test: ## Run the default test suite (LLM mocked; no spend, no key needed)
	uv run pytest -q -m "not live"

test-live: ## Run tests that hit the real OpenAI API (needs OPENAI_API_KEY; costs money)
	uv run pytest -q -m live

eval: ## Run the eval suite + auto-precision CI gate, mock mode
	uv run pytest evals -q -m "not live"

eval-live: ## Run the eval suite against the real model (needs OPENAI_API_KEY)
	uv run python evals/run_live.py

seed: ## Regenerate examples/ and evals/cases.jsonl from fixed ledgerfab seeds
	uv run python -m ledgerfab.export
	uv run python evals/build_cases.py

lint: ## ruff check
	uv run ruff check backend evals
	uv run ruff format --check backend evals

fmt: ## ruff format (writes)
	uv run ruff format backend evals
	uv run ruff check --fix backend evals

typecheck: ## mypy (backend) + tsc (frontend)
	uv run mypy backend/app backend/ledgerfab
	cd frontend && npm run typecheck

up: ## docker compose up
	docker compose up --build

down: ## docker compose down
	docker compose down -v

clean: ## Remove local DB, caches and build output
	rm -rf backend/spendsort.db backend/spendsort.db-wal backend/spendsort.db-shm
	rm -rf .pytest_cache .ruff_cache .mypy_cache frontend/dist
