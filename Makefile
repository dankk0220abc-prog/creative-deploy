SHELL := /bin/sh

PYTHON_PROJECT := apps/api
ALEMBIC_CONFIG := apps/api/alembic.ini
API_CHECK_PATHS := apps/api/src apps/api/tests apps/api/migrations
WEB_PACKAGE := @creativedeploy/web
ENV_FILE ?= .env
PNPM ?= pnpm
WEB_COMMAND_ENV := env \
	-u APP_ENV \
	-u APP_NAME \
	-u APP_VERSION \
	-u DATABASE_URL \
	-u DATABASE_HEALTH_TIMEOUT_SECONDS \
	-u IMAGE_STORAGE_PROVIDER \
	-u IMAGE_STORAGE_ROOT \
	-u IMAGE_UPLOAD_MAX_BYTES \
	-u IMAGE_MIN_SIDE_PX \
	-u IMAGE_MAX_SIDE_PX \
	-u IMAGE_MAX_PIXELS \
	-u POSTGRES_USER \
	-u POSTGRES_PASSWORD \
	-u POSTGRES_DB \
	-u POSTGRES_PORT

.PHONY: bootstrap bootstrap-env db-up db-down api web test-api test-api-integration test-web \
	lint-api format-check-api typecheck-api lint-web typecheck-web build-web \
	migration-current migration-heads migration-history migration-check \
	check require-env ensure-db

bootstrap-env:
	@if [ -e "$(ENV_FILE)" ]; then \
		echo "$(ENV_FILE) already exists; keeping existing file."; \
	else \
		cp .env.example "$(ENV_FILE)"; \
		echo "Created $(ENV_FILE) from .env.example."; \
	fi

require-env:
	@test -f "$(ENV_FILE)" || \
		(echo "Missing $(ENV_FILE). Run 'make bootstrap' before continuing."; exit 1)

ensure-db: require-env
	@docker compose --env-file "$(ENV_FILE)" ps --status running --services | grep -qx postgres || \
		(echo "PostgreSQL is not running. Start it with 'make db-up'."; exit 1)

bootstrap: bootstrap-env
	uv sync --project $(PYTHON_PROJECT) --all-groups --locked
	$(WEB_COMMAND_ENV) $(PNPM) install --frozen-lockfile

db-up: require-env
	docker compose --env-file "$(ENV_FILE)" up -d --wait postgres

db-down: require-env
	docker compose --env-file "$(ENV_FILE)" down

migration-current: require-env
	uv run --project $(PYTHON_PROJECT) alembic -c $(ALEMBIC_CONFIG) current

migration-heads: require-env
	uv run --project $(PYTHON_PROJECT) alembic -c $(ALEMBIC_CONFIG) heads

migration-history: require-env
	uv run --project $(PYTHON_PROJECT) alembic -c $(ALEMBIC_CONFIG) history

migration-check: require-env
	uv run --project $(PYTHON_PROJECT) alembic -c $(ALEMBIC_CONFIG) check

api: require-env
	uv run --project $(PYTHON_PROJECT) uvicorn creativedeploy_api.main:app \
		--host 127.0.0.1 --port 8000

web:
	$(WEB_COMMAND_ENV) $(PNPM) --filter $(WEB_PACKAGE) dev --host 127.0.0.1 --port 5173

test-api:
	uv run --project $(PYTHON_PROJECT) pytest apps/api/tests/unit \
		--cov=creativedeploy_api --cov-report=term-missing

test-api-integration: ensure-db
	uv run --project $(PYTHON_PROJECT) pytest apps/api/tests/integration -m integration

test-web:
	$(WEB_COMMAND_ENV) $(PNPM) --filter $(WEB_PACKAGE) test --run

lint-api:
	uv run --project $(PYTHON_PROJECT) ruff check $(API_CHECK_PATHS)

format-check-api:
	uv run --project $(PYTHON_PROJECT) ruff format --check $(API_CHECK_PATHS)

typecheck-api:
	uv run --project $(PYTHON_PROJECT) mypy apps/api/src

lint-web:
	$(WEB_COMMAND_ENV) $(PNPM) --filter $(WEB_PACKAGE) lint

typecheck-web:
	$(WEB_COMMAND_ENV) $(PNPM) --filter $(WEB_PACKAGE) typecheck

build-web:
	$(WEB_COMMAND_ENV) $(PNPM) --filter $(WEB_PACKAGE) build

check: ensure-db
	$(MAKE) lint-api
	$(MAKE) format-check-api
	$(MAKE) typecheck-api
	$(MAKE) test-api
	$(MAKE) test-api-integration
	$(MAKE) lint-web
	$(MAKE) typecheck-web
	$(MAKE) test-web
	$(MAKE) build-web
