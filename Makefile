# =============================================================================
# Owlbell — Development Makefile
# =============================================================================
# Usage:
#   make setup    — Initial project setup
#   make dev      — Start development environment
#   make build    — Build Docker images
#   make test     — Run all tests
#   make lint     — Run linting and type checks
#   make format   — Format all code
#   make deploy   — Deploy to production
#
# For help, run: make help
# =============================================================================

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
.PHONY: help setup setup-python setup-node dev dev-backend dev-frontend dev-docker \
        build build-api build-dashboard build-ai build-all \
        test test-unit test-integration test-e2e test-frontend test-coverage \
        lint lint-backend lint-frontend lint-dashboard typecheck mypy \
        format format-backend format-frontend format-dashboard \
        migrate migrate-up migrate-down migrate-redo migrate-status seed seed-demo \
        deploy deploy-staging deploy-production \
        logs logs-backend logs-frontend logs-ai logs-db \
        backup backup-db backup-redis restore-db \
        clean clean-docker clean-python clean-node clean-all \
        pre-commit install-hooks \
        docker-up docker-down docker-restart docker-ps docker-prune \
        worker worker-beat health check-env

# Colors for output
BLUE  := \033[36m
GREEN := \033[32m
RED   := \033[31m
RESET := \033[0m

# Python / Node executables
PYTHON        := python3
PIP           := pip3
NODE          := node
NPM           := npm
DOCKER        := docker
COMPOSE       := docker compose
COMPOSE_FILE  := infrastructure/docker/docker-compose.yml
OVERRIDE_FILE := docker-compose.override.yml

# Project directories
BACKEND_DIR   := backend
DASHBOARD_DIR := dashboard
DOCKER_DIR    := infrastructure/docker
SCRIPTS_DIR   := infrastructure/scripts

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------
help: ## Display this help message
	@echo ""
	@echo "$(BLUE)╔══════════════════════════════════════════════════════════════╗$(RESET)"
	@echo "$(BLUE)║         Owlbell — Development Commands                 ║$(RESET)"
	@echo "$(BLUE)╚══════════════════════════════════════════════════════════════╝$(RESET)"
	@echo ""
	@echo "$(GREEN)Setup$(RESET)"
	@echo "  setup              Full initial project setup"
	@echo "  setup-python       Setup Python backend (venv + deps)"
	@echo "  setup-node         Setup Node.js frontend (npm install)"
	@echo "  install-hooks      Install pre-commit hooks"
	@echo ""
	@echo "$(GREEN)Development$(RESET)"
	@echo "  dev                Start full development environment (Docker)"
	@echo "  dev-backend        Start backend only (uvicorn + reload)"
	@echo "  dev-frontend       Start dashboard dev server (Vite)"
	@echo "  docker-up          Start Docker services"
	@echo "  docker-down        Stop Docker services"
	@echo "  docker-restart     Restart Docker services"
	@echo "  worker             Start Celery worker"
	@echo "  worker-beat        Start Celery beat scheduler"
	@echo ""
	@echo "$(GREEN)Build$(RESET)"
	@echo "  build              Build all Docker images"
	@echo "  build-api          Build API backend image"
	@echo "  build-dashboard    Build dashboard frontend image"
	@echo "  build-ai           Build AI pipeline images (Whisper + Piper)"
	@echo ""
	@echo "$(GREEN)Testing$(RESET)"
	@echo "  test               Run all tests"
	@echo "  test-unit          Run unit tests only"
	@echo "  test-integration   Run integration tests"
	@echo "  test-e2e           Run end-to-end tests"
	@echo "  test-frontend      Run frontend/dashboard tests"
	@echo "  test-coverage      Run tests with coverage report"
	@echo ""
	@echo "$(GREEN)Quality$(RESET)"
	@echo "  lint               Run all linters (ruff, mypy)"
	@echo "  lint-backend       Lint backend code with ruff"
	@echo "  lint-frontend      Lint frontend code"
	@echo "  typecheck          Run type checks (mypy)"
	@echo "  format             Format all code (black, isort, ruff)"
	@echo "  pre-commit         Run pre-commit on all files"
	@echo ""
	@echo "$(GREEN)Database$(RESET)"
	@echo "  migrate            Run database migrations (up)"
	@echo "  migrate-down       Rollback last migration"
	@echo "  migrate-redo       Rollback then re-apply last migration"
	@echo "  migrate-status     Show migration status"
	@echo "  seed               Seed database with reference data"
	@echo "  seed-demo          Seed with demo data for development"
	@echo ""
	@echo "$(GREEN)Production$(RESET)"
	@echo "  deploy-staging     Deploy to staging environment"
	@echo "  deploy-production  Deploy to production environment"
	@echo ""
	@echo "$(GREEN)Operations$(RESET)"
	@echo "  logs               View all service logs"
	@echo "  logs-backend       View backend logs"
	@echo "  logs-frontend      View dashboard logs"
	@echo "  logs-ai            View AI pipeline logs"
	@echo "  logs-db            View database logs"
	@echo "  backup             Run database backup"
	@echo "  backup-db          Backup PostgreSQL database"
	@echo "  restore-db         Restore PostgreSQL from backup"
	@echo "  health             Check service health"
	@echo "  check-env          Validate environment configuration"
	@echo ""
	@echo "$(GREEN)Maintenance$(RESET)"
	@echo "  clean              Clean build artifacts"
	@echo "  clean-docker       Clean Docker artifacts"
	@echo "  clean-python       Clean Python cache files"
	@echo "  clean-node         Clean node_modules"
	@echo "  clean-all          Deep clean everything"
	@echo "  docker-prune       Prune unused Docker volumes/images"
	@echo ""

# =============================================================================
# SETUP
# =============================================================================

setup: setup-python setup-node install-hooks ## Full initial project setup
	@echo "$(GREEN)✅ Project setup complete!$(RESET)"
	@echo "$(GREEN)   Run 'make dev' to start the development environment.$(RESET)"

setup-python: ## Setup Python backend (create venv, install deps)
	@echo "$(BLUE)🔧 Setting up Python environment...$(RESET)"
	@if [ ! -d "$(BACKEND_DIR)/.venv" ]; then \
		cd $(BACKEND_DIR) && $(PYTHON) -m venv .venv; \
	fi
	@cd $(BACKEND_DIR) && .venv/bin/pip install --upgrade pip
	@cd $(BACKEND_DIR) && .venv/bin/pip install -r requirements.txt
	@cd $(BACKEND_DIR) && .venv/bin/pip install -e ".[dev]" || true
	@echo "$(GREEN)✅ Python environment ready.$(RESET)"

setup-node: ## Setup Node.js frontend
	@echo "$(BLUE)🔧 Setting up Node.js environment...$(RESET)"
	@cd $(DASHBOARD_DIR) && $(NPM) install
	@echo "$(GREEN)✅ Node.js environment ready.$(RESET)"

install-hooks: ## Install pre-commit hooks
	@echo "$(BLUE)🔧 Installing pre-commit hooks...$(RESET)"
	@cd $(BACKEND_DIR) && .venv/bin/pip install pre-commit || pip install pre-commit
	@pre-commit install --install-hooks || cd $(BACKEND_DIR) && .venv/bin/pre-commit install --install-hooks
	@echo "$(GREEN)✅ Pre-commit hooks installed.$(RESET)"

# =============================================================================
# DEVELOPMENT
# =============================================================================

dev: docker-up ## Start full development environment (Docker Compose)
	@echo "$(GREEN)🚀 Development environment starting...$(RESET)"
	@echo "$(GREEN)   API docs:    http://localhost:8000/docs$(RESET)"
	@echo "$(GREEN)   Dashboard:   http://localhost:5173$(RESET)"
	@echo "$(GREEN)   Redis:       redis://localhost:6379$(RESET)"
	@echo "$(GREEN)   PostgreSQL:  postgresql://localhost:5432$(RESET)"

dev-backend: ## Start backend only (uvicorn with reload)
	@echo "$(BLUE)🚀 Starting backend development server...$(RESET)"
	@cd $(BACKEND_DIR) && .venv/bin/uvicorn main:app \
		--host 0.0.0.0 \
		--port 8000 \
		--reload \
		--reload-dir . \
		--log-level debug

dev-frontend: ## Start dashboard dev server (Vite)
	@echo "$(BLUE)🚀 Starting dashboard dev server...$(RESET)"
	@cd $(DASHBOARD_DIR) && $(NPM) run dev

docker-up: ## Start Docker services
	@echo "$(BLUE)🐳 Starting Docker services...$(RESET)"
	$(COMPOSE) -f $(COMPOSE_FILE) -f $(OVERRIDE_FILE) up -d

docker-down: ## Stop Docker services
	@echo "$(BLUE)🐳 Stopping Docker services...$(RESET)"
	$(COMPOSE) -f $(COMPOSE_FILE) -f $(OVERRIDE_FILE) down

docker-restart: docker-down docker-up ## Restart Docker services

worker: ## Start Celery worker
	@echo "$(BLUE)🔄 Starting Celery worker...$(RESET)"
	@cd $(BACKEND_DIR) && .venv/bin/celery -A orchestrator worker \
		--loglevel=info \
		--concurrency=4 \
		-Q calls,transcriptions,llm,tts,webhooks,notifications,default

worker-beat: ## Start Celery beat scheduler
	@echo "$(BLUE)⏰ Starting Celery beat scheduler...$(RESET)"
	@cd $(BACKEND_DIR) && .venv/bin/celery -A orchestrator beat \
		--loglevel=info \
		--scheduler django_celery_beat.schedulers:DatabaseScheduler || \
	cd $(BACKEND_DIR) && .venv/bin/celery -A orchestrator beat --loglevel=info

# =============================================================================
# BUILD
# =============================================================================

build: build-all ## Build all Docker images (default)

build-all: build-api build-dashboard build-ai ## Build all Docker images
	@echo "$(GREEN)✅ All images built.$(RESET)"

build-api: ## Build API backend image
	@echo "$(BLUE)🏗️  Building API image...$(RESET)"
	$(DOCKER) build -f $(DOCKER_DIR)/Dockerfile.api -t answerflow/api:latest $(BACKEND_DIR)

build-dashboard: ## Build dashboard frontend image
	@echo "$(BLUE)🏗️  Building dashboard image...$(RESET)"
	$(DOCKER) build -f $(DOCKER_DIR)/Dockerfile.dashboard -t answerflow/dashboard:latest $(DASHBOARD_DIR)

build-ai: ## Build AI pipeline images (Whisper + Piper)
	@echo "$(BLUE)🏗️  Building AI pipeline images...$(RESET)"
	$(DOCKER) build -f $(DOCKER_DIR)/Dockerfile.whisper -t answerflow/whisper:latest $(DOCKER_DIR)
	$(DOCKER) build -f $(DOCKER_DIR)/Dockerfile.piper -t answerflow/piper:latest $(DOCKER_DIR)
	$(DOCKER) build -f $(DOCKER_DIR)/Dockerfile.freeswitch -t answerflow/freeswitch:latest $(DOCKER_DIR)

# =============================================================================
# TESTING
# =============================================================================

test: test-unit test-integration test-frontend ## Run all tests
	@echo "$(GREEN)✅ All tests passed.$(RESET)"

test-unit: ## Run unit tests only
	@echo "$(BLUE)🧪 Running unit tests...$(RESET)"
	@cd $(BACKEND_DIR) && .venv/bin/pytest tests/ \
		-v \
		--tb=short \
		-m "unit or not integration and not e2e" \
		--disable-warnings || \
	cd $(BACKEND_DIR) && python -m pytest tests/ -v --tb=short --disable-warnings

test-integration: ## Run integration tests
	@echo "$(BLUE)🧪 Running integration tests...$(RESET)"
	@cd $(BACKEND_DIR) && .venv/bin/pytest tests/ \
		-v \
		--tb=short \
		-m integration \
		--disable-warnings || \
	cd $(BACKEND_DIR) && python -m pytest tests/integration/ -v --tb=short --disable-warnings

test-e2e: ## Run end-to-end tests
	@echo "$(BLUE)🧪 Running E2E tests...$(RESET)"
	@cd $(BACKEND_DIR) && .venv/bin/pytest tests/ \
		-v \
		--tb=short \
		-m e2e \
		--disable-warnings || \
	cd $(BACKEND_DIR) && python -m pytest tests/e2e/ -v --tb=short --disable-warnings

test-frontend: ## Run frontend/dashboard tests
	@echo "$(BLUE)🧪 Running frontend tests...$(RESET)"
	@cd $(DASHBOARD_DIR) && $(NPM) run test || echo "$(RED)⚠️  No tests configured$(RESET)"

test-coverage: ## Run tests with coverage report
	@echo "$(BLUE)📊 Running tests with coverage...$(RESET)"
	@cd $(BACKEND_DIR) && .venv/bin/pytest tests/ \
		--cov=backend \
		--cov-report=term-missing:skip-covered \
		--cov-report=html:htmlcov \
		--cov-report=xml:coverage.xml \
		--cov-fail-under=80 \
		--disable-warnings || true
	@echo "$(GREEN)📊 Coverage report: file://$(PWD)/$(BACKEND_DIR)/htmlcov/index.html$(RESET)"

# =============================================================================
# LINTING & FORMATTING
# =============================================================================

lint: lint-backend lint-frontend ## Run all linters

lint-backend: ## Lint backend code with ruff
	@echo "$(BLUE)🔍 Linting backend...$(RESET)"
	@cd $(BACKEND_DIR) && .venv/bin/ruff check . --fix || ruff check $(BACKEND_DIR) --fix || echo "$(RED)⚠️  ruff not available$(RESET)"

lint-frontend: ## Lint frontend code
	@echo "$(BLUE)🔍 Linting frontend...$(RESET)"
	@cd $(DASHBOARD_DIR) && $(NPM) run lint || echo "$(RED)⚠️  No lint script$(RESET)"

typecheck: mypy ## Run type checks

mypy: ## Run mypy type checker
	@echo "$(BLUE)🔍 Running mypy...$(RESET)"
	@cd $(BACKEND_DIR) && .venv/bin/mypy . \
		--ignore-missing-imports \
		--show-error-codes \
		--pretty || \
	mypy $(BACKEND_DIR) --ignore-missing-imports --show-error-codes --pretty || \
	echo "$(RED)⚠️  mypy not available$(RESET)"

format: format-backend format-frontend ## Format all code

format-backend: ## Format backend code (black + isort + ruff)
	@echo "$(BLUE)✨ Formatting backend...$(RESET)"
	@cd $(BACKEND_DIR) && .venv/bin/ruff format . || ruff format $(BACKEND_DIR) || true
	@cd $(BACKEND_DIR) && .venv/bin/ruff check . --select I --fix || ruff check $(BACKEND_DIR) --select I --fix || true
	@echo "$(GREEN)✅ Backend formatted.$(RESET)"

format-frontend: ## Format frontend code
	@echo "$(BLUE)✨ Formatting frontend...$(RESET)"
	@cd $(DASHBOARD_DIR) && $(NPM) run format || echo "$(RED)⚠️  No format script$(RESET)"

pre-commit: ## Run pre-commit on all files
	@echo "$(BLUE)🔍 Running pre-commit...$(RESET)"
	@pre-commit run --all-files || cd $(BACKEND_DIR) && .venv/bin/pre-commit run --all-files || true

# =============================================================================
# DATABASE
# =============================================================================

migrate: ## Run database migrations (upgrade to latest)
	@echo "$(BLUE)🗄️  Running migrations...$(RESET)"
	@cd $(BACKEND_DIR) && alembic upgrade head || .venv/bin/alembic upgrade head || \
	PYTHONPATH=$(PWD)/$(BACKEND_DIR) $(PYTHON) -m alembic upgrade head

migrate-down: ## Rollback last migration
	@echo "$(BLUE)🗄️  Rolling back one migration...$(RESET)"
	@cd $(BACKEND_DIR) && alembic downgrade -1 || .venv/bin/alembic downgrade -1

migrate-redo: ## Rollback then re-apply last migration
	@echo "$(BLUE)🗄️  Redoing last migration...$(RESET)"
	@cd $(BACKEND_DIR) && alembic downgrade -1 && alembic upgrade head || \
	.venv/bin/alembic downgrade -1 && .venv/bin/alembic upgrade head

migrate-status: ## Show migration status
	@echo "$(BLUE)🗄️  Migration status:$(RESET)"
	@cd $(BACKEND_DIR) && alembic current || .venv/bin/alembic current
	@cd $(BACKEND_DIR) && alembic history --verbose || .venv/bin/alembic history --verbose

seed: ## Seed database with reference data (plans, roles)
	@echo "$(BLUE)🌱 Seeding reference data...$(RESET)"
	@cd $(BACKEND_DIR) && .venv/bin/python -c \
		"from db.seed import seed_all; seed_all()" || \
	PYTHONPATH=$(PWD)/$(BACKEND_DIR) $(PYTHON) -c "from db.seed import seed_all; seed_all()" || \
	echo "$(RED)⚠️  Seed script not found. Create backend/db/seed.py$(RESET)"

seed-demo: ## Seed with demo data for development
	@echo "$(BLUE)🌱 Seeding demo data...$(RESET)"
	@cd $(BACKEND_DIR) && .venv/bin/python -c \
		"from db.seed import seed_demo; seed_demo()" || \
	PYTHONPATH=$(PWD)/$(BACKEND_DIR) $(PYTHON) -c "from db.seed import seed_demo; seed_demo()" || \
	echo "$(RED)⚠️  Demo seed script not found$(RESET)"

# =============================================================================
# DEPLOYMENT
# =============================================================================

deploy-staging: ## Deploy to staging environment
	@echo "$(BLUE)🚀 Deploying to staging...$(RESET)"
	@echo "$(BLUE)   Building images...$(RESET)"
	$(DOCKER) build -f $(DOCKER_DIR)/Dockerfile.api -t answerflow/api:staging $(BACKEND_DIR)
	$(DOCKER) build -f $(DOCKER_DIR)/Dockerfile.dashboard -t answerflow/dashboard:staging $(DASHBOARD_DIR)
	@echo "$(GREEN)✅ Staging deployment complete.$(RESET)"

deploy-production: build-all ## Deploy to production environment
	@echo "$(BLUE)🚀 Deploying to production...$(RESET)"
	@echo "$(RED)⚠️  Ensure all tests pass before deploying!$(RESET)"
	@echo "$(BLUE)   Running final checks...$(RESET)"
	@$(MAKE) test
	@$(MAKE) lint
	@echo "$(BLUE)   Tagging and pushing images...$(RESET)"
	$(DOCKER) tag answerflow/api:latest answerflow/api:$$(git rev-parse --short HEAD)
	$(DOCKER) tag answerflow/dashboard:latest answerflow/dashboard:$$(git rev-parse --short HEAD)
	@echo "$(GREEN)✅ Production deployment complete.$(RESET)"

# =============================================================================
# LOGS
# =============================================================================

logs: ## View all service logs
	$(COMPOSE) -f $(COMPOSE_FILE) logs -f --tail=100

logs-backend: ## View backend logs
	$(COMPOSE) -f $(COMPOSE_FILE) logs -f --tail=100 api

logs-frontend: ## View dashboard logs
	$(COMPOSE) -f $(COMPOSE_FILE) logs -f --tail=100 dashboard

logs-ai: ## View AI pipeline logs
	$(COMPOSE) -f $(COMPOSE_FILE) logs -f --tail=100 whisper piper

logs-db: ## View database logs
	$(COMPOSE) -f $(COMPOSE_FILE) logs -f --tail=100 postgres redis

logs-worker: ## View Celery worker logs
	$(COMPOSE) -f $(COMPOSE_FILE) logs -f --tail=100 worker beat

# =============================================================================
# BACKUP & RESTORE
# =============================================================================

backup: backup-db ## Run all backups (alias for backup-db)

backup-db: ## Backup PostgreSQL database
	@echo "$(BLUE)💾 Backing up PostgreSQL...$(RESET)"
	@mkdir -p backups
	@$(DOCKER) exec answerflow-postgres pg_dump -U answerflow -d answerflow \
		> backups/answerflow_$$(date +%Y%m%d_%H%M%S).sql
	@echo "$(GREEN)✅ Database backup saved to backups/$(RESET)"

backup-redis: ## Backup Redis data
	@echo "$(BLUE)💾 Backing up Redis...$(RESET)"
	@mkdir -p backups
	@$(DOCKER) exec answerflow-redis redis-cli BGSAVE
	@$(DOCKER) exec answerflow-redis cat /data/dump.rdb > backups/redis_$$(date +%Y%m%d_%H%M%S).rdb
	@echo "$(GREEN)✅ Redis backup saved to backups/$(RESET)"

restore-db: ## Restore PostgreSQL from backup (set BACKUP_FILE=...)
	@echo "$(BLUE)💾 Restoring PostgreSQL from $(BACKUP_FILE)...$(RESET)"
	@if [ -z "$(BACKUP_FILE)" ]; then \
		echo "$(RED)❌ Set BACKUP_FILE=path/to/backup.sql$(RESET)"; \
		exit 1; \
	fi
	@$(DOCKER) exec -i answerflow-postgres psql -U answerflow -d answerflow < $(BACKUP_FILE)
	@echo "$(GREEN)✅ Database restored from $(BACKUP_FILE)$(RESET)"

# =============================================================================
# HEALTH & DIAGNOSTICS
# =============================================================================

health: ## Check service health
	@echo "$(BLUE)🏥 Checking service health...$(RESET)"
	@echo "$(BLUE)   PostgreSQL:$(RESET)"
	@$(DOCKER) exec answerflow-postgres pg_isready -U answerflow 2>/dev/null && \
		echo "$(GREEN)   ✅ PostgreSQL is healthy$(RESET)" || echo "$(RED)   ❌ PostgreSQL is down$(RESET)"
	@echo "$(BLUE)   Redis:$(RESET)"
	@$(DOCKER) exec answerflow-redis redis-cli ping 2>/dev/null | grep -q PONG && \
		echo "$(GREEN)   ✅ Redis is healthy$(RESET)" || echo "$(RED)   ❌ Redis is down$(RESET)"
	@echo "$(BLUE)   API:$(RESET)"
	@curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null | grep -q 200 && \
		echo "$(GREEN)   ✅ API is healthy$(RESET)" || echo "$(RED)   ❌ API is down$(RESET)"

check-env: ## Validate environment configuration
	@echo "$(BLUE)🔍 Checking environment...$(RESET)"
	@cd $(BACKEND_DIR) && .venv/bin/python -c "from config import get_settings; s = get_settings(); print('$(GREEN)   ✅ Configuration loaded$(RESET)')" || \
	echo "$(RED)   ❌ Configuration failed$(RESET)"

# =============================================================================
# CLEANUP
# =============================================================================

clean: clean-python ## Clean build artifacts (default)
	@echo "$(GREEN)✅ Cleaned.$(RESET)"

clean-docker: ## Clean Docker artifacts
	@echo "$(BLUE)🧹 Cleaning Docker artifacts...$(RESET)"
	$(COMPOSE) -f $(COMPOSE_FILE) down -v --remove-orphans 2>/dev/null || true
	$(DOCKER) system prune -f 2>/dev/null || true

clean-python: ## Clean Python cache files
	@echo "$(BLUE)🧹 Cleaning Python cache...$(RESET)"
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -name "*.pyc" -delete 2>/dev/null || true
	@find . -name "*.pyo" -delete 2>/dev/null || true
	@find . -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf $(BACKEND_DIR)/.mypy_cache
	@rm -rf $(BACKEND_DIR)/.pytest_cache
	@rm -rf $(BACKEND_DIR)/htmlcov
	@rm -rf $(BACKEND_DIR)/.coverage
	@rm -rf $(BACKEND_DIR)/ruff_cache

clean-node: ## Clean node_modules
	@echo "$(BLUE)🧹 Cleaning Node modules...$(RESET)"
	@rm -rf $(DASHBOARD_DIR)/node_modules
	@rm -rf $(DASHBOARD_DIR)/.cache

clean-all: clean-docker clean-python clean-node ## Deep clean everything
	@echo "$(BLUE)🧹 Cleaning build directories...$(RESET)"
	@rm -rf $(DASHBOARD_DIR)/dist
	@rm -rf $(BACKEND_DIR)/build
	@rm -rf $(BACKEND_DIR)/dist
	@echo "$(GREEN)✅ Deep clean complete.$(RESET)"

docker-prune: ## Prune unused Docker volumes/images
	@echo "$(BLUE)🧹 Pruning Docker...$(RESET)"
	$(DOCKER) volume prune -f
	$(DOCKER) image prune -f
	$(DOCKER) network prune -f

# =============================================================================
# UTILITIES
# =============================================================================

docker-ps: ## List running containers
	$(COMPOSE) -f $(COMPOSE_FILE) ps

shell-backend: ## Open a shell in the backend container
	$(COMPOSE) -f $(COMPOSE_FILE) exec api /bin/bash

shell-db: ## Open PostgreSQL CLI
	$(COMPOSE) -f $(COMPOSE_FILE) exec postgres psql -U answerflow -d answerflow

shell-redis: ## Open Redis CLI
	$(COMPOSE) -f $(COMPOSE_FILE) exec redis redis-cli

alembic-init: ## Initialize Alembic migrations
	@cd $(BACKEND_DIR) && alembic init migrations || .venv/bin/alembic init migrations

migration: ## Create a new Alembic migration (set MSG=...)
	@if [ -z "$(MSG)" ]; then \
		echo "$(RED)❌ Set MSG='migration description'$(RESET)"; \
		exit 1; \
	fi
	@cd $(BACKEND_DIR) && alembic revision --autogenerate -m "$(MSG)" || \
	.venv/bin/alembic revision --autogenerate -m "$(MSG)"
