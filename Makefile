# Canonical task runner (Linux/macOS/CI). On Windows without `make`, use the
# console script instead, e.g. `filing-reconciler run` / `filing-reconciler eval`,
# or the `uv run` commands shown under each target. See README "Running on Windows".

UV ?= uv

.PHONY: help install up down logs run serve eval test lint typecheck check fmt clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Create venv and install (dev + anthropic extras)
	$(UV) sync --extra dev --extra anthropic

up: ## Start Postgres + pgvector
	docker compose up -d
	@echo "Postgres up. Set CHECKPOINTER=postgres in .env to use durable checkpoints."

down: ## Stop Postgres
	docker compose down

logs: ## Tail db logs
	docker compose logs -f db

run: ## Run a full analysis over the sample data (pauses at the HITL gate)
	$(UV) run filing-reconciler run --sample set_a

serve: ## Start the FastAPI server
	$(UV) run uvicorn app.main:app --reload --port 8000

eval: ## Run the offline evaluation harness and print metrics
	$(UV) run filing-reconciler eval

test: ## Run the test suite
	$(UV) run pytest

lint: ## Lint with ruff
	$(UV) run ruff check .

fmt: ## Auto-format / fix with ruff
	$(UV) run ruff check --fix . && $(UV) run ruff format .

typecheck: ## Static type check with mypy
	$(UV) run mypy filing_reconciler app

check: lint typecheck test ## Lint + types + tests (what CI runs)

clean: ## Remove caches and local artifacts
	rm -rf .pytest_cache .mypy_cache .ruff_cache artifacts output
