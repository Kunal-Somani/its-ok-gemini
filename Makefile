.PHONY: help dev down test lint format clean build push stop

# Default target
.DEFAULT_GOAL := help

# Project configuration
PROJECT_NAME := its-ok-gemini
DOCKER_REGISTRY ?= $(DOCKER_USER)
IMAGE_NAME := $(DOCKER_REGISTRY)/$(PROJECT_NAME)
IMAGE_TAG ?= latest

# Environment files
ENV_FILE := .env

# Colors for output
CYAN := \033[0;36m
GREEN := \033[0;32m
YELLOW := \033[0;33m
NC := \033[0m # No Color

help: ## Show this help message
	@echo '$(CYAN)$(PROJECT_NAME) - Docker Compose Makefile$(NC)'
	@echo ''
	@echo 'Usage:'
	@echo '  make $(GREEN)<target>$(NC)'
	@echo ''
	@echo 'Targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-15s$(NC) %s\n", $$1, $$2}'

dev: ## Start local development stack with Docker Compose
	@echo '$(CYAN)Starting development stack...$(NC)'
	@if [ ! -f $(ENV_FILE) ]; then \
		echo '$(YELLOW)Warning: $(ENV_FILE) not found. Creating default...$(NC)'; \
		cp .env.example $(ENV_FILE) 2>/dev/null || \
		echo 'ENVIRONMENT=development\nGITHUB_USERNAME=\nGITHUB_APP_ID=\nGITHUB_PRIVATE_KEY_B64=\nGEMINI_API_KEY=\nDB_USER=postgres\nDB_PASSWORD=postgres\nDB_NAME=its_ok_gemini\nDB_PORT=5432\nREDIS_PORT=6379\nAPI_PORT=8000\nPROMETHEUS_PORT=9090' > $(ENV_FILE); \
	fi
	docker-compose -f docker-compose.yml up -d
	@echo '$(GREEN)✓ Stack started successfully!$(NC)'
	@echo ''
	@echo 'Services:'
	@echo '  $(GREEN)API$(NC)         → http://localhost:8000'
	@echo '  $(GREEN)Prometheus$(NC)  → http://localhost:9090'
	@echo '  $(GREEN)PostgreSQL$(NC)  → localhost:5432'
	@echo '  $(GREEN)Redis$(NC)       → localhost:6379'
	@echo ''
	@echo 'View logs: $(CYAN)make logs$(NC)'
	@echo 'Stop: $(CYAN)make down$(NC)'

down: ## Stop and remove all containers
	@echo '$(CYAN)Stopping development stack...$(NC)'
	docker-compose -f docker-compose.yml down
	@echo '$(GREEN)✓ Stack stopped$(NC)'

stop: ## Stop containers without removing them
	@echo '$(CYAN)Stopping containers...$(NC)'
	docker-compose -f docker-compose.yml stop
	@echo '$(GREEN)✓ Containers stopped$(NC)'

logs: ## View logs from all services
	docker-compose -f docker-compose.yml logs -f

logs-api: ## View logs from API service only
	docker-compose -f docker-compose.yml logs -f api

logs-db: ## View logs from PostgreSQL service only
	docker-compose -f docker-compose.yml logs -f postgres

logs-redis: ## View logs from Redis service only
	docker-compose -f docker-compose.yml logs -f redis

test: ## Run pytest in the container
	@echo '$(CYAN)Running tests...$(NC)'
	@if [ ! -d tests ]; then \
		echo '$(YELLOW)No tests directory found$(NC)'; \
		exit 0; \
	fi
	docker-compose -f docker-compose.yml exec -T api pytest tests/ -v --tb=short
	@echo '$(GREEN)✓ Tests completed$(NC)'

test-unit: ## Run unit tests only
	@echo '$(CYAN)Running unit tests...$(NC)'
	docker-compose -f docker-compose.yml exec -T api pytest tests/unit/ -v --tb=short
	@echo '$(GREEN)✓ Unit tests completed$(NC)'

test-integration: ## Run integration tests only
	@echo '$(CYAN)Running integration tests...$(NC)'
	docker-compose -f docker-compose.yml exec -T api pytest tests/integration/ -v --tb=short
	@echo '$(GREEN)✓ Integration tests completed$(NC)'

test-coverage: ## Run tests with coverage report
	@echo '$(CYAN)Running tests with coverage...$(NC)'
	docker-compose -f docker-compose.yml exec -T api pytest tests/ --cov=app --cov-report=html --cov-report=term
	@echo '$(GREEN)✓ Coverage report generated in htmlcov/$(NC)'

lint: ## Run linting checks
	@echo '$(CYAN)Running linters...$(NC)'
	docker-compose -f docker-compose.yml exec -T api flake8 app/ --max-line-length=120 || true
	docker-compose -f docker-compose.yml exec -T api pylint app/ --disable=all --enable=E,F || true
	@echo '$(GREEN)✓ Linting completed$(NC)'

format: ## Format code with black and isort
	@echo '$(CYAN)Formatting code...$(NC)'
	docker-compose -f docker-compose.yml exec -T api black app/ tests/ || true
	docker-compose -f docker-compose.yml exec -T api isort app/ tests/ || true
	@echo '$(GREEN)✓ Code formatted$(NC)'

build: ## Build Docker image
	@echo '$(CYAN)Building Docker image...$(NC)'
	docker build -t $(IMAGE_NAME):$(IMAGE_TAG) .
	@echo '$(GREEN)✓ Image built: $(IMAGE_NAME):$(IMAGE_TAG)$(NC)'

rebuild: ## Rebuild and restart services
	@echo '$(CYAN)Rebuilding stack...$(NC)'
	docker-compose -f docker-compose.yml down
	docker-compose -f docker-compose.yml build --no-cache
	docker-compose -f docker-compose.yml up -d
	@echo '$(GREEN)✓ Stack rebuilt and started$(NC)'

push: ## Push Docker image to registry (requires DOCKER_REGISTRY and DOCKER_USER)
	@echo '$(CYAN)Pushing image to registry...$(NC)'
	@if [ -z "$(DOCKER_USER)" ]; then \
		echo '$(YELLOW)Error: DOCKER_USER not set. Use: make push DOCKER_USER=your_user DOCKER_REGISTRY=your_registry$(NC)'; \
		exit 1; \
	fi
	docker push $(IMAGE_NAME):$(IMAGE_TAG)
	@echo '$(GREEN)✓ Image pushed to $(IMAGE_NAME):$(IMAGE_TAG)$(NC)'

shell-api: ## Open shell in API container
	docker-compose -f docker-compose.yml exec api sh

shell-db: ## Open PostgreSQL shell
	docker-compose -f docker-compose.yml exec postgres psql -U postgres -d its_ok_gemini

ps: ## Show running containers
	docker-compose -f docker-compose.yml ps

clean: ## Clean up dangling images and volumes
	@echo '$(CYAN)Cleaning up Docker resources...$(NC)'
	docker system prune -f
	@echo '$(GREEN)✓ Cleanup completed$(NC)'

clean-volumes: ## Remove all volumes (WARNING: deletes data!)
	@echo '$(YELLOW)WARNING: This will delete all data in volumes!$(NC)'
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	docker-compose -f docker-compose.yml down -v
	@echo '$(GREEN)✓ Volumes removed$(NC)'

version: ## Show versions of key services
	@echo '$(CYAN)Service versions:$(NC)'
	docker --version
	docker-compose --version

migrate-up: ## Run database migrations (up)
	@echo '$(CYAN)Running database migrations...$(NC)'
	docker-compose -f docker-compose.yml exec api alembic upgrade head
	@echo '$(GREEN)✓ Migrations completed$(NC)'

migrate-down: ## Rollback latest migration
	@echo '$(CYAN)Rolling back migration...$(NC)'
	docker-compose -f docker-compose.yml exec api alembic downgrade -1
	@echo '$(GREEN)✓ Rollback completed$(NC)'
