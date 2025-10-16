.PHONY: help dev build up down restart logs logs-api logs-db logs-redis logs-worker logs-web \
        lint lint-fix lint-backend frontend-dev install migrate seed seed-providers clean \
        shell-api shell-db shell-worker psql stop worker-only makemigration postman-test postman-env \
        ci ci-backend ci-frontend ci-e2e ci-pipeline test-backend test-backend-multichannel \
        test-frontend test-e2e

export RATE_LIMIT_MESSAGES_PER_MIN ?= 120
export RATE_LIMIT_LOGIN_PER_MIN ?= 20

# Prefer the standalone docker-compose binary when available and fall back to
# the Docker CLI plugin (`docker compose`). This mirrors the default GitHub
# Actions environment which only ships the plugin.
ifeq ($(shell command -v docker-compose >/dev/null 2>&1 && echo found),found)
DC ?= docker-compose
else
DC ?= docker compose
endif

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-18s %s\n", $$1, $$2}'
	@echo ""
	@echo "Sandbox:"
	@echo "  SANDBOX_PROVIDERS=true (default) evita chamadas HTTP externas nos conectores."
	@echo "  Ajuste SANDBOX_LATENCY_MS e SANDBOX_FAILURE_RATE para simular cenários específicos."

install: ## Install frontend dependencies (local npm)
	npm install

frontend-dev: ## Run the Vite dev server without Docker
	npm run dev

lint: ## Run frontend linting
	npm run lint

lint-fix: ## Run frontend linting with --fix
	npm run lint -- --fix

lint-backend: ## Run backend linting (ruff)
	python -m ruff check backend/app backend/scripts

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

# Monolithic CI pipeline kept as a separate target (no more name collision with `ci`)
ci-pipeline: ## Run CI workflow (build, migrations, health check, Postman tests, collect logs)
	@bash -c '\
		set -euo pipefail; \
		cleanup() { \
			status=$$?; \
			mkdir -p artifacts; \
			$(DC) logs api > artifacts/api.log 2>&1 || true; \
			$(DC) logs worker > artifacts/worker.log 2>&1 || true; \
			$(DC) logs web > artifacts/web.log 2>&1 || true; \
			$(DC) logs db > artifacts/db.log 2>&1 || true; \
			$(DC) logs redis > artifacts/redis.log 2>&1 || true; \
			$(DC) down -v; \
			exit $${status}; \
		}; \
		trap cleanup EXIT; \
		mkdir -p artifacts; \
		$(DC) build api worker web; \
		$(DC) up -d db redis; \
		echo "Waiting for Postgres to be ready..."; \
		pg_ready=0; \
		for i in $$(seq 1 30); do \
			if $(DC) exec db pg_isready -U postgres >/dev/null 2>&1; then \
				echo "Postgres is ready"; \
				pg_ready=1; \
				break; \
			fi; \
			echo "  attempt $$i - waiting"; \
			sleep 1; \
		done; \
		if [ $$pg_ready -ne 1 ]; then \
			echo "Postgres did not become ready in time" >&2; \
			exit 1; \
		fi; \
		$(DC) run --rm api alembic upgrade head; \
		$(DC) run --rm api python scripts/seed.py; \
		$(DC) up -d api worker web; \
		echo "Waiting for API health endpoint..."; \
		api_ready=0; \
		for i in $$(seq 1 30); do \
			status_code=$$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/admin/health || true); \
			if [ "$${status_code}" = "200" ]; then \
				echo "API health endpoint ready"; \
				api_ready=1; \
				break; \
			fi; \
			echo "  attempt $$i - status $${status_code:-N/A}"; \
			sleep 2; \
		done; \
		if [ $$api_ready -ne 1 ]; then \
			echo "API did not become healthy in time" >&2; \
			exit 1; \
		fi; \
		npx --yes newman run docs/postman/wa-cost-router.postman_collection.json -e docs/postman/wa-cost-router.postman_environment.json --verbose; \
	'

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

test-backend: ## Run backend test suite (pytest)
	pytest backend/tests --cov=backend/app --cov=backend/scripts --cov-report=term --cov-report=xml:backend/coverage.xml

test-backend-multichannel: ## Run targeted multi-channel backend tests (email/SMS sandbox flows)
	scripts/test-backend-multichannel.sh

postman-test: ## Run Newman collection tests against local stack
	npx --yes newman run docs/postman/wa-cost-router.postman_collection.json -e docs/postman/wa-cost-router.postman_environment.json --verbose
	npx --yes newman run docs/postman/wa-cost-router.postman_collection.json -e docs/postman/wa-cost-router.postman_environment.json --folder "Multi-Channel Regression" --iteration-data docs/postman/multi_channel_regression.json --verbose

postman-env: ## Show Postman collection and environment paths
	@echo "Collection: docs/postman/wa-cost-router.postman_collection.json"
	@echo "Environment: docs/postman/wa-cost-router.postman_environment.json"

# Aggregator CI target (no recipe) → runs modular steps
ci: ci-backend test-backend-multichannel ci-frontend test-frontend ci-e2e ## Run backend, frontend and E2E checks sequentially

ci-lite: ## Run local CI fallback (sem Docker) e gerar relatório em artifacts/ci-lite
	scripts/ci_lite.py

ci-lite-publish: ## Publicar resultado manual do CI Lite no GitHub (repo=<owner/name> [pr=123] [comment=1])
	@if [ -z "$(repo)" ]; then echo "Missing repo=owner/name (use repo=org/proj)"; exit 1; fi
	@sha_value="$(if $(sha),$(sha),$(shell git rev-parse HEAD))"; \
	cmd="scripts/ci_lite_publish.py --repo \"$(repo)\" --sha \"$$sha_value\""; \
	if [ -n "$(summary)" ]; then cmd="$$cmd --summary \"$(summary)\""; fi; \
	if [ -n "$(details_url)" ]; then cmd="$$cmd --details-url \"$(details_url)\""; fi; \
	if [ -n "$(pr)" ]; then cmd="$$cmd --pr $(pr)"; fi; \
	if [ -n "$(comment)" ]; then cmd="$$cmd --comment"; fi; \
	if [ -n "$(token)" ]; then cmd="GITHUB_TOKEN=$(token) $$cmd"; fi; \
	echo $$cmd; \
	eval $$cmd

ci-backend: ## Build backend images and verify migrations
	$(DC) build api worker
	$(DC) run --rm api alembic upgrade head

ci-frontend: ## Lint and build the frontend
	npm ci
	npm run lint
	npm run build

test-frontend: ## Execute frontend unit tests (Vitest)
	scripts/test-frontend.sh

ci-e2e: ## Spin up stack and execute Newman + Playwright tests
	@bash -c '\
	set -euo pipefail; \
	trap "$(DC) down -v" EXIT; \
	$(DC) down -v >/dev/null 2>&1 || true; \
	$(DC) up -d db redis; \
	echo "Waiting for Postgres to be ready..."; \
	ready=0; \
	for i in $$(seq 1 30); do \
	if $(DC) exec db pg_isready -U postgres >/dev/null 2>&1; then \
	echo "Postgres is ready"; \
	ready=1; \
	break; \
	fi; \
	printf "  attempt %s - waiting\n" "$$i"; \
	sleep 2; \
	done; \
	if [ "$$ready" -ne 1 ]; then \
	echo "Postgres did not become ready in time" >&2; \
	exit 1; \
	fi; \
	$(DC) run --rm api alembic upgrade head; \
	$(DC) run --rm api python scripts/seed.py; \
	$(DC) up -d api worker; \
	echo "Waiting for API to respond..."; \
	ready=0; \
	for i in $$(seq 1 30); do \
	if curl -sSf http://localhost:8000/admin/health >/dev/null; then \
	echo "API is ready"; \
	ready=1; \
	break; \
	fi; \
	printf "  attempt %s - waiting\n" "$$i"; \
	sleep 2; \
	done; \
	if [ "$$ready" -ne 1 ]; then \
	echo "API did not become ready in time" >&2; \
	exit 1; \
	fi; \
	npx --yes newman run docs/postman/wa-cost-router.postman_collection.json -e docs/postman/wa-cost-router.postman_environment.json --reporters cli,junit --reporter-junit-export newman-report.xml; \
	npx --yes newman run docs/postman/wa-cost-router.postman_collection.json -e docs/postman/wa-cost-router.postman_environment.json --folder "Multi-Channel Regression" --iteration-data docs/postman/multi_channel_regression.json --reporters cli; \
	E2E_API_BASE_URL=http://localhost:8000 PLAYWRIGHT_INSTALL_ARGS="--with-deps" scripts/test-e2e.sh; \
	'

test-e2e: ## Run Playwright end-to-end UI regression (requires API stack running)
	scripts/test-e2e.sh

shell-api: ## Open a shell inside the API container
	$(DC) exec api bash

shell-worker: ## Open a shell inside the worker container
	$(DC) exec worker bash

shell-db: ## Open a psql shell in the database
	$(DC) exec db psql -U postgres -d wa_cost_router

psql: shell-db ## Alias for shell-db

clean: ## Remove all containers and volumes
	$(DC) down -v
