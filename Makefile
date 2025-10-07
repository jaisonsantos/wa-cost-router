.PHONY: help dev build up down restart logs logs-api logs-db logs-redis logs-worker logs-web lint lint-fix frontend-dev install migrate seed seed-providers clean shell-api shell-db shell-worker psql stop worker-only makemigration postman-test postman-env

DC ?= docker-compose

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-18s %s\n", $$1, $$2}'

install: ## Install frontend dependencies (local npm)
	npm install

frontend-dev: ## Run the Vite dev server without Docker
	npm run dev

lint: ## Run frontend linting
	npm run lint

lint-fix: ## Run frontend linting with --fix
	npm run lint -- --fix

build: ## Build all Docker images
	$(DC) build

up: ## Start all services in detached mode
	$(DC) up -d

worker-only: ## Start only the async worker
	$(DC) up worker

dev: ## Bootstrap local stack (db/redis, migrations, seed, services) and tail API logs
	$(DC) build api worker web
	$(DC) up -d db redis
	@bash -c '\
	    echo "Waiting for Postgres to be ready..."; \
	    for i in $$(seq 1 30); do \
	        if $(DC) exec db pg_isready -U postgres >/dev/null 2>&1; then \
	            echo "Postgres is ready"; \
	            exit 0; \
	        fi; \
	        echo "  attempt $$i - waiting"; \
	        sleep 1; \
	    done; \
	    echo "Postgres did not become ready in time" >&2; \
	    exit 1; \
	'
	$(DC) run --rm api alembic upgrade head
	$(DC) run --rm api python scripts/seed.py
	$(DC) up -d web api worker
	$(DC) logs -f api

down: ## Stop and remove running services (including volumes)
	$(DC) down -v

stop: down ## Alias for down

restart: ## Restart all services
	$(MAKE) down
	$(MAKE) up

logs: ## Tail API logs with context
	$(DC) logs -f --tail=200 api

logs-api: ## Tail API logs
	$(DC) logs -f api

logs-worker: ## Tail worker logs
	$(DC) logs -f worker

logs-web: ## Tail web frontend logs
	$(DC) logs -f web

logs-db: ## Tail database logs
	$(DC) logs -f db

logs-redis: ## Tail Redis logs
	$(DC) logs -f redis

migrate: ## Run Alembic migrations
	$(DC) run --rm api alembic upgrade head

makemigration: ## Create a new Alembic revision (usage: make makemigration name=add-table)
	@if [ -z "$(name)" ]; then \
            echo "Missing migration name. Use: make makemigration name=<slug>"; \
            exit 1; \
        fi
	$(DC) run --rm api alembic revision -m "$(name)"

seed: ## Seed demo data (organizations, jobs)
	$(DC) run --rm api python scripts/seed.py

seed-providers: ## Seed default providers for the current org
	$(DC) run --rm api python scripts/seed_providers.py

postman-test: ## Run Newman collection tests against local stack
	npx --yes newman run docs/postman/wa-cost-router.postman_collection.json -e docs/postman/wa-cost-router.postman_environment.json --verbose

postman-env: ## Show Postman collection and environment paths
	@echo "Collection: docs/postman/wa-cost-router.postman_collection.json"
	@echo "Environment: docs/postman/wa-cost-router.postman_environment.json"

shell-api: ## Open a shell inside the API container
	$(DC) exec api bash

shell-worker: ## Open a shell inside the worker container
	$(DC) exec worker bash

shell-db: ## Open a psql shell in the database
	$(DC) exec db psql -U postgres -d wa_cost_router

psql: shell-db ## Alias for shell-db

clean: ## Remove all containers and volumes
	$(DC) down -v
