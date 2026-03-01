# ──────────────────────────────────────────────────────────────────────────────
# QueueFlow Makefile
# ──────────────────────────────────────────────────────────────────────────────
.DEFAULT_GOAL := help
COMPOSE        := docker compose
BACKEND        := $(COMPOSE) exec api
ALEMBIC        := $(BACKEND) alembic

.PHONY: help up down build logs shell db-shell \
        migrate migrate-gen seed \
        lint typecheck test test-unit test-integration \
        clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-20s\033[0m %s\n",$$1,$$2}'

# ── Docker ────────────────────────────────────────────────────────────────────
up:  ## Start all services (API, Postgres, Redis, worker, etc.)
	@cp -n .env.example .env 2>/dev/null || true
	$(COMPOSE) up --build -d
	@echo "API:      http://localhost:8000"
	@echo "Docs:     http://localhost:8000/docs"
	@echo "Frontend: http://localhost:3000"
	@echo "Keycloak: http://localhost:8080"
	@echo "Run 'make migrate' then 'make test' after first up"

down:  ## Stop all services
	$(COMPOSE) down

build:  ## Build images
	$(COMPOSE) build

logs:  ## Tail logs (all services)
	$(COMPOSE) logs -f

logs-api:  ## Tail API logs only
	$(COMPOSE) logs -f api

shell:  ## Open shell in api container
	$(BACKEND) bash

db-shell:  ## Open psql shell
	$(COMPOSE) exec db psql -U queueflow -d queueflow

redis-cli:  ## Open redis-cli
	$(COMPOSE) exec redis redis-cli

# ── Database / Migrations ─────────────────────────────────────────────────────
migrate:  ## Run pending migrations
	$(ALEMBIC) upgrade head

migrate-down:  ## Rollback one migration
	$(ALEMBIC) downgrade -1

migrate-gen:  ## Generate a new migration (MSG=<description>)
	$(ALEMBIC) revision --autogenerate -m "$(MSG)"

migrate-history:  ## Show migration history
	$(ALEMBIC) history --verbose

seed:  ## Seed demo data
	$(BACKEND) python scripts/seed.py

# ── Quality ───────────────────────────────────────────────────────────────────
lint:  ## Run ruff + black check
	$(BACKEND) ruff check app tests
	$(BACKEND) black --check app tests

format:  ## Auto-format with black + ruff
	$(BACKEND) black app tests scripts
	$(BACKEND) ruff check --fix app tests

typecheck:  ## Run mypy
	$(BACKEND) mypy app --ignore-missing-imports

# ── Tests ─────────────────────────────────────────────────────────────────────
test:  ## Run all tests
	$(BACKEND) pytest tests/ -v --tb=short

test-unit:  ## Run unit tests only
	$(BACKEND) pytest tests/unit/ -v

test-integration:  ## Run integration tests (requires running DB+Redis)
	$(BACKEND) pytest tests/integration/ -v --tb=short

test-cov:  ## Run tests with coverage report
	$(BACKEND) pytest tests/ --cov=app --cov-report=term-missing --cov-report=html

# ── Cleanup ───────────────────────────────────────────────────────────────────
clean:  ## Remove containers, volumes, and generated artifacts
	$(COMPOSE) down -v --remove-orphans
	find . -type d -name __pycache__ | xargs rm -rf
	find . -type d -name .pytest_cache | xargs rm -rf
	find . -name "*.pyc" -delete
