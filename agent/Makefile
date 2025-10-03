.PHONY: help install dev test lint format type-check clean docker-build docker-run k8s-deploy

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install dependencies
	uv sync --all-extras

dev: ## Run development server
	uv run dev.py

test: ## Run all tests
	uv run pytest tests/ -v --cov=src --cov-report=term --cov-report=html

test-unit: ## Run unit tests only
	uv run pytest tests/test_utils.py -v

test-integration: ## Run integration tests only
	uv run pytest tests/test_api.py -v

lint: ## Run linting
	uv run ruff check src/ tests/

lint-fix: ## Run linting with auto-fix
	uv run ruff check --fix src/ tests/

format: ## Format code with black
	uv run black src/ tests/

format-check: ## Check code formatting
	uv run black --check src/ tests/

type-check: ## Run type checking
	uv run mypy src/ --ignore-missing-imports

check: lint type-check test ## Run all checks (lint, type-check, test)

clean: ## Clean up generated files
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage

docker-build: ## Build Docker image
	docker build -t sre-agent:latest .

docker-run: ## Run Docker container
	docker run -p 8000:8000 --env-file .env sre-agent:latest

docker-compose-up: ## Start all services with Docker Compose
	docker-compose up -d

docker-compose-down: ## Stop all services
	docker-compose down

docker-compose-logs: ## View logs from all services
	docker-compose logs -f

k8s-deploy: ## Deploy to Kubernetes
	kubectl apply -f k8s/deployment.yaml

k8s-delete: ## Delete from Kubernetes
	kubectl delete -f k8s/deployment.yaml

k8s-logs: ## View Kubernetes logs
	kubectl logs -f -n sre-system deployment/sre-agent

k8s-port-forward: ## Port forward to Kubernetes service
	kubectl port-forward -n sre-system svc/sre-agent 8000:80

health: ## Check application health
	curl http://localhost:8000/health

health-detailed: ## Check detailed application health
	curl http://localhost:8000/health/detailed | jq

cache-stats: ## View cache statistics
	curl http://localhost:8000/metrics/cache | jq

cache-clear: ## Clear caches
	curl -X POST http://localhost:8000/cache/clear

docs: ## Generate documentation
	@echo "API Documentation available at:"
	@echo "  http://localhost:8000/docs (Swagger UI)"
	@echo "  http://localhost:8000/redoc (ReDoc)"
	@echo ""
	@echo "Project Documentation:"
	@echo "  README.md - User guide"
	@echo "  ARCHITECTURE.md - Technical architecture"
	@echo "  DEPLOYMENT.md - Deployment guide"
	@echo "  CONTRIBUTING.md - Contributing guide"

version: ## Show version information
	@echo "SRE Agent v3.0.0"
	@python --version
	@uv --version
