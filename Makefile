SHELL := /bin/sh

PYTHON_PROJECT := apps/api
ALEMBIC_CONFIG := apps/api/alembic.ini
API_CHECK_PATHS := apps/api/src apps/api/tests apps/api/migrations
WEB_PACKAGE := @creativedeploy/web
ENV_FILE ?= .env
PNPM ?= pnpm
BACKEND_ENV_FILE := CREATIVEDEPLOY_ENV_FILE=$(abspath $(ENV_FILE))
WEB_COMMAND_ENV := env \
	-u APP_ENV \
	-u APP_NAME \
	-u APP_VERSION \
	-u CREATIVEDEPLOY_ENV_FILE \
	-u DATABASE_URL \
	-u DATABASE_HEALTH_TIMEOUT_SECONDS \
	-u DATABASE_LOCK_TIMEOUT_MS \
	-u DATABASE_STATEMENT_TIMEOUT_MS \
	-u IMAGE_STORAGE_PROVIDER \
	-u IMAGE_STORAGE_ROOT \
	-u IMAGE_UPLOAD_MAX_BYTES \
	-u IMAGE_MIN_SIDE_PX \
	-u IMAGE_MAX_SIDE_PX \
	-u IMAGE_MAX_PIXELS \
	-u PAINTPILOT_DEMO_PRINCIPAL_ID \
	-u PAINTPILOT_DEMO_PRINCIPAL_DISPLAY_NAME \
	-u POSTGRES_HOST \
	-u POSTGRES_USER \
	-u POSTGRES_PASSWORD \
	-u POSTGRES_DB \
	-u POSTGRES_PORT \
	-u TRUSTED_HOSTS
API_UNIT_COMMAND_ENV := env \
	-u APP_ENV \
	-u APP_NAME \
	-u APP_VERSION \
	-u CREATIVEDEPLOY_ENV_FILE \
	-u DATABASE_URL \
	-u DATABASE_HEALTH_TIMEOUT_SECONDS \
	-u DATABASE_LOCK_TIMEOUT_MS \
	-u DATABASE_STATEMENT_TIMEOUT_MS \
	-u IMAGE_STORAGE_PROVIDER \
	-u IMAGE_STORAGE_ROOT \
	-u IMAGE_UPLOAD_MAX_BYTES \
	-u IMAGE_MIN_SIDE_PX \
	-u IMAGE_MAX_SIDE_PX \
	-u IMAGE_MAX_PIXELS \
	-u PAINTPILOT_DEMO_PRINCIPAL_ID \
	-u PAINTPILOT_DEMO_PRINCIPAL_DISPLAY_NAME \
	-u POSTGRES_HOST \
	-u POSTGRES_USER \
	-u POSTGRES_PASSWORD \
	-u POSTGRES_DB \
	-u POSTGRES_PORT \
	-u TRUSTED_HOSTS

.PHONY: bootstrap bootstrap-env db-up db-down api web test-api test-api-integration test-web \
	lint-api format-check-api typecheck-api lint-web typecheck-web build-web \
	migration-current migration-heads migration-history migration-check \
	check require-env config-check ensure-db validate-run-id artifact-config artifact-build \
	artifact-test artifact-isolation-test \
	artifact-smoke-up artifact-smoke-down artifact-smoke secret-scan audit-api audit-web \
	immutable-reference-check supply-chain-check

ARTIFACT_COMPOSE := compose.artifact-smoke.yaml
ATTEMPT_ID ?=
RUN_ID ?= $(if $(strip $(ATTEMPT_ID)),$(ATTEMPT_ID),local_$(shell date -u +%Y%m%d%H%M%S)_$(shell uuidgen | tr '[:upper:]' '[:lower:]' | tr -d '-' | cut -c1-12))
ARTIFACT_PROJECT := creativedeploy-phase2a1-$(RUN_ID)
SMOKE_DATABASE_ID := phase2a1_$(RUN_ID)
ARTIFACT_COMPOSE_ENV := \
	SMOKE_RUN_ID=$(RUN_ID) \
	SMOKE_DATABASE_USER=$(SMOKE_DATABASE_ID) \
	SMOKE_DATABASE_PASSWORD=synthetic_$(RUN_ID)_password \
	SMOKE_DATABASE_NAME=$(SMOKE_DATABASE_ID)

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

config-check: require-env
	$(BACKEND_ENV_FILE) uv run --project $(PYTHON_PROJECT) \
		python -m creativedeploy_api.core.config_audit

ensure-db: config-check
	$(BACKEND_ENV_FILE) uv run --project $(PYTHON_PROJECT) \
		python -m creativedeploy_api.core.database_probe

bootstrap: bootstrap-env
	uv sync --project $(PYTHON_PROJECT) --all-groups --locked
	$(WEB_COMMAND_ENV) $(PNPM) install --frozen-lockfile

db-up: require-env
	docker compose --env-file "$(ENV_FILE)" up -d --wait postgres

db-down: require-env
	docker compose --env-file "$(ENV_FILE)" down

migration-current: require-env
	$(BACKEND_ENV_FILE) uv run --project $(PYTHON_PROJECT) \
		alembic -c $(ALEMBIC_CONFIG) current

migration-heads: require-env
	$(BACKEND_ENV_FILE) uv run --project $(PYTHON_PROJECT) \
		alembic -c $(ALEMBIC_CONFIG) heads

migration-history: require-env
	$(BACKEND_ENV_FILE) uv run --project $(PYTHON_PROJECT) \
		alembic -c $(ALEMBIC_CONFIG) history

migration-check: require-env
	$(BACKEND_ENV_FILE) uv run --project $(PYTHON_PROJECT) \
		alembic -c $(ALEMBIC_CONFIG) check

api: require-env
	$(BACKEND_ENV_FILE) uv run --project $(PYTHON_PROJECT) \
		uvicorn creativedeploy_api.main:app \
		--host 127.0.0.1 --port 8000

web:
	$(WEB_COMMAND_ENV) $(PNPM) --filter $(WEB_PACKAGE) dev --host 127.0.0.1 --port 5173

test-api:
	$(API_UNIT_COMMAND_ENV) uv run --project $(PYTHON_PROJECT) pytest apps/api/tests/unit \
		--cov=creativedeploy_api --cov-report=term-missing

test-api-integration: ensure-db
	@integration_database_url="$$($(BACKEND_ENV_FILE) uv run --project $(PYTHON_PROJECT) python -c \
		'from creativedeploy_api.core.config import Settings; print(Settings().require_database_url().get_secret_value())')"; \
	env -u POSTGRES_HOST -u POSTGRES_USER -u POSTGRES_PASSWORD -u POSTGRES_DB \
		-u POSTGRES_PORT CREATIVEDEPLOY_ENV_FILE=/dev/null \
		DATABASE_URL="$$integration_database_url" uv run --project $(PYTHON_PROJECT) \
		pytest apps/api/tests/integration -m integration

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

validate-run-id:
	@printf '%s\n' "$(RUN_ID)" | grep -Eq '^[a-z0-9][a-z0-9_]{0,39}$$' || \
		(echo "RUN_ID must match ^[a-z0-9][a-z0-9_]{0,39}$$"; exit 1)

artifact-config: validate-run-id
	$(ARTIFACT_COMPOSE_ENV) docker compose --project-name $(ARTIFACT_PROJECT) \
		--file $(ARTIFACT_COMPOSE) \
		config --format json | uv run --project $(PYTHON_PROJECT) \
		python scripts/validate_artifact_config.py

artifact-build: artifact-config
	$(ARTIFACT_COMPOSE_ENV) docker compose --project-name $(ARTIFACT_PROJECT) \
		--file $(ARTIFACT_COMPOSE) \
		build migrate api web

artifact-test: artifact-config
	$(WEB_COMMAND_ENV) VITE_RUNTIME_PROFILE=artifact-smoke \
		$(PNPM) --filter $(WEB_PACKAGE) build

artifact-smoke-up: artifact-config
	$(ARTIFACT_COMPOSE_ENV) docker compose --project-name $(ARTIFACT_PROJECT) \
		--file $(ARTIFACT_COMPOSE) \
		up --detach --build --wait
	@$(ARTIFACT_COMPOSE_ENV) docker compose --project-name $(ARTIFACT_PROJECT) \
		--file $(ARTIFACT_COMPOSE) port web 8080

artifact-smoke-down: validate-run-id
	$(ARTIFACT_COMPOSE_ENV) docker compose --project-name $(ARTIFACT_PROJECT) \
		--file $(ARTIFACT_COMPOSE) \
		down --volumes --remove-orphans --rmi local

artifact-smoke: artifact-config
	RUN_ID=$(RUN_ID) ./scripts/verify_artifact_smoke.sh

artifact-isolation-test: validate-run-id
	RUN_ID=$(RUN_ID) ./scripts/verify_attempt_isolation.sh

secret-scan: validate-run-id
	RUN_ID=$(RUN_ID) ./scripts/secret_scan.sh

audit-api:
	uv run --project $(PYTHON_PROJECT) pip-audit --timeout 60

audit-web:
	$(WEB_COMMAND_ENV) $(PNPM) --filter $(WEB_PACKAGE) audit --prod --audit-level high

immutable-reference-check:
	uv run --project $(PYTHON_PROJECT) python scripts/verify_immutable_references.py

supply-chain-check: secret-scan audit-api audit-web immutable-reference-check

check: ensure-db
	$(MAKE) config-check
	$(MAKE) lint-api
	$(MAKE) format-check-api
	$(MAKE) typecheck-api
	$(MAKE) test-api
	$(MAKE) test-api-integration
	$(MAKE) lint-web
	$(MAKE) typecheck-web
	$(MAKE) test-web
	$(MAKE) build-web
