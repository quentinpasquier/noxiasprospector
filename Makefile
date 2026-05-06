.DEFAULT_GOAL := help
SHELL := /bin/bash

# Colours
GREEN := \033[0;32m
NC    := \033[0m

# ============================================================
#  Help
# ============================================================
.PHONY: help
help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-15s$(NC) %s\n", $$1, $$2}'

# ============================================================
#  Bootstrap
# ============================================================
.PHONY: setup
setup: setup-backend setup-frontend  ## Install all dependencies (back + front)

.PHONY: setup-backend
setup-backend:  ## Install backend deps with uv
	cd backend && uv sync --extra dev

.PHONY: setup-frontend
setup-frontend:  ## Install frontend deps with pnpm
	cd frontend && pnpm install

# ============================================================
#  Local dev
# ============================================================
.PHONY: dev
dev: infra-up  ## Start infra + back + front in parallel
	@echo "$(GREEN)Postgres:$(NC) localhost:5432  $(GREEN)Redis:$(NC) localhost:6379  $(GREEN)Adminer:$(NC) http://localhost:8080"
	@echo "$(GREEN)Backend:$(NC) http://localhost:8000/docs  $(GREEN)Frontend:$(NC) http://localhost:3000"
	@trap 'kill 0' EXIT; \
	  (cd backend && uv run uvicorn app.main:app --reload --port 8000) & \
	  (cd frontend && pnpm dev) & \
	  wait

.PHONY: infra-up
infra-up:  ## Start Postgres + Redis + Adminer via docker compose
	docker compose up -d

.PHONY: infra-down
infra-down:  ## Stop infra containers
	docker compose down

.PHONY: infra-reset
infra-reset:  ## Stop infra and wipe volumes (DESTRUCTIVE)
	docker compose down -v

# ============================================================
#  Quality gates
# ============================================================
.PHONY: lint
lint: lint-backend lint-frontend  ## Lint everything

.PHONY: lint-backend
lint-backend:  ## Ruff + mypy on backend
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app

.PHONY: lint-frontend
lint-frontend:  ## ESLint + tsc on frontend
	cd frontend && pnpm lint && pnpm typecheck

.PHONY: format
format:  ## Auto-format everything
	cd backend && uv run ruff check --fix . && uv run ruff format .
	cd frontend && pnpm format

.PHONY: test
test:  ## Run backend tests
	cd backend && uv run pytest

# ============================================================
#  Migrations
# ============================================================
.PHONY: migrate
migrate:  ## Apply Alembic migrations
	cd backend && uv run alembic upgrade head

.PHONY: migration
migration:  ## Generate a new auto-migration. Usage: make migration name="add users"
	cd backend && uv run alembic revision --autogenerate -m "$(name)"
