# FastAPI Cloud Workspaces - Backend Makefile
# Provides convenient commands for development, testing, and deployment

.PHONY: help install install-dev clean test test-unit test-integration test-coverage lint format type-check security run dev build docker-build docker-run docker-compose-up docker-compose-down migrate upgrade-db downgrade-db create-migration docs serve-docs pre-commit setup-hooks ci-test deploy-staging deploy-prod

# Default target
help: ## Show this help message
	@echo "FastAPI Cloud Workspaces - Backend"
	@echo "Available commands:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# Installation
install: ## Install production dependencies
	pip install -r requirements.txt

install-dev: ## Install development dependencies
	pip install -r requirements.txt -r requirements-dev.txt
	pre-commit install

# Cleanup
clean: ## Clean up temporary files and caches
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/
	rm -rf dist/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .tox/

# Testing
test: ## Run all tests
	pytest

test-unit: ## Run unit tests only
	pytest -m "unit" -v

test-integration: ## Run integration tests only
	pytest -m "integration" -v

test-coverage: ## Run tests with coverage report
	pytest --cov=app --cov-report=html --cov-report=term-missing --cov-fail-under=80

test-fast: ## Run tests excluding slow tests
	pytest -m "not slow" -x

# Code Quality
lint: ## Run linting checks
	flake8 app tests
	bandit -r app -f json -o bandit-report.json || true
	safety check --json --output safety-report.json || true

format: ## Format code with black and isort
	black app tests
	isort app tests

type-check: ## Run type checking with mypy
	mypy app

security: ## Run security checks
	bandit -r app
	safety check

# Development
run: ## Run the application in development mode
	python -m uvicorn main:app --reload --host 0.0.0.0 --port 8001

dev: ## Run the application with auto-reload and debug mode
	python -m uvicorn main:app --reload --host 0.0.0.0 --port 8001 --log-level debug

# Build
build: ## Build the application
	python -m build

# Docker
docker-build: ## Build Docker image
	docker build -t fastapi-cloud-workspaces-backend .

docker-run: ## Run Docker container
	docker run -p 8001:8001 --env-file .env fastapi-cloud-workspaces-backend

docker-compose-up: ## Start services with docker-compose
	docker-compose up -d

docker-compose-down: ## Stop services with docker-compose
	docker-compose down

# Database
migrate: ## Run database migrations
	alembic upgrade head

upgrade-db: ## Upgrade database to latest migration
	alembic upgrade head

downgrade-db: ## Downgrade database by one migration
	alembic downgrade -1

create-migration: ## Create a new migration (usage: make create-migration MESSAGE="description")
	alembic revision --autogenerate -m "$(MESSAGE)"

# Documentation
docs: ## Generate documentation
	sphinx-build -b html docs docs/_build/html

serve-docs: ## Serve documentation locally
	python -m http.server 8080 --directory docs/_build/html

# Pre-commit
pre-commit: ## Run pre-commit hooks on all files
	pre-commit run --all-files

setup-hooks: ## Setup pre-commit hooks
	pre-commit install
	pre-commit install --hook-type commit-msg

# CI/CD
ci-test: ## Run CI test suite
	pytest --cov=app --cov-report=xml --cov-report=term-missing --cov-fail-under=80 -v

ci-lint: ## Run CI linting checks
	flake8 app tests --format=json --output-file=flake8-report.json || true
	black --check app tests
	isort --check-only app tests
	mypy app
	bandit -r app -f json -o bandit-report.json || true
	safety check --json --output safety-report.json || true

# Performance
performance-test: ## Run performance tests with Locust
	locust -f tests/performance/locustfile.py --host=http://localhost:8001

# Deployment
deploy-staging: ## Deploy to staging environment
	@echo "Deploying to staging..."
	# Add staging deployment commands here

deploy-prod: ## Deploy to production environment
	@echo "Deploying to production..."
	# Add production deployment commands here

# Environment setup
setup: install-dev setup-hooks ## Complete development environment setup
	@echo "Development environment setup complete!"
	@echo "Run 'make run' to start the development server"

# Database seeding
seed-db: ## Seed database with sample data
	python -m app.scripts.seed_database

# Monitoring
logs: ## View application logs
	tail -f logs/app.log

health-check: ## Check application health
	curl -f http://localhost:8001/health || exit 1

# Backup
backup-db: ## Backup database
	@echo "Creating database backup..."
	# Add database backup commands here

# Version management
version: ## Show current version
	python -c "import app; print(app.__version__)"

bump-version: ## Bump version (usage: make bump-version TYPE=patch|minor|major)
	bump2version $(TYPE)

# Quick commands
quick-test: format lint test-fast ## Quick development test cycle
	@echo "Quick test cycle completed!"

full-check: clean install-dev format lint type-check security test-coverage ## Full code quality check
	@echo "Full quality check completed!"
