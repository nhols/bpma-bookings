.PHONY: help check format test sync-dry-run sync eval report

MODELS ?= google:gemini-3.8-flash

help: ## Show these commands
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  make %-14s %s\n", $$1, $$2}'

check: ## Lint, type check and test (what CI runs)
	uv run ruff format --check .
	uv run ruff check .
	uv run ty check
	uv run pytest

format: ## Format and fix lint where possible
	uv run ruff format .
	uv run ruff check --fix .

test: ## Run the tests
	uv run pytest

sync-dry-run: ## Show what the sync would change in the calendar
	uv run --env-file .env bpma sync --dry-run

sync: ## Update the calendar
	uv run --env-file .env bpma sync

eval: ## Score models against the hand-checked sheets, e.g. make eval MODELS="google:gemini-3.8-flash google:gemini-3.5-flash"
	uv run --env-file .env evals/extraction.py --models $(MODELS)

report: ## Open the eval results
	uv run evals/report.py
