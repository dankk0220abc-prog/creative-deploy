SHELL := /bin/sh

PYTHON_PROJECT := apps/api
ALEMBIC_CONFIG := apps/api/alembic.ini
ALEMBIC_HEAD := 4c01a2b3c4d5
API_CHECK_PATHS := apps/api/src apps/api/tests apps/api/migrations
WEB_PACKAGE := @creativedeploy/web
ENV_FILE ?= .env
PNPM ?= pnpm
BACKEND_ENV_FILE := CREATIVEDEPLOY_ENV_FILE=$(abspath $(ENV_FILE))
INTEGRATION_DATABASE_ENV := env \
	-u DATABASE_URL_FILE \
	-u POSTGRES_HOST \
	-u POSTGRES_USER \
	-u POSTGRES_PASSWORD \
	-u POSTGRES_DB \
	-u POSTGRES_PORT \
	-u PHASE3A_FIXTURE_ENABLED \
	-u PHASE3B_PAINT_PLAN_ENABLED \
	-u VITE_PHASE3B_PAINT_PLAN_ENABLED \
	-u CREDENTIAL_FIXTURE_ROOT_KEY_FILE \
	-u STAGING_RUN_ID \
	CREATIVEDEPLOY_ENV_FILE=/dev/null
WEB_COMMAND_ENV := env \
	-u APP_ENV \
	-u APP_NAME \
	-u APP_VERSION \
	-u CREATIVEDEPLOY_ENV_FILE \
	-u DATABASE_URL \
	-u DATABASE_URL_FILE \
	-u DATABASE_HEALTH_TIMEOUT_SECONDS \
	-u DATABASE_LOCK_TIMEOUT_MS \
	-u DATABASE_STATEMENT_TIMEOUT_MS \
	-u IMAGE_STORAGE_PROVIDER \
	-u IMAGE_STORAGE_ROOT \
	-u IMAGE_UPLOAD_MAX_BYTES \
	-u IMAGE_MIN_SIDE_PX \
	-u IMAGE_MAX_SIDE_PX \
	-u IMAGE_MAX_PIXELS \
	-u IDENTITY_PROVIDER \
	-u OIDC_ISSUER \
	-u OIDC_DISCOVERY_URL \
	-u OIDC_BACKCHANNEL_BASE_URL \
	-u OIDC_CLIENT_ID \
	-u OIDC_CLIENT_SECRET \
	-u OIDC_CLIENT_SECRET_FILE \
	-u OIDC_REDIRECT_URI \
	-u OIDC_HTTP_TIMEOUT_SECONDS \
	-u OIDC_ID_TOKEN_MAX_AGE_SECONDS \
	-u OIDC_CLOCK_SKEW_SECONDS \
	-u OIDC_LOGIN_TTL_SECONDS \
	-u AUTH_SESSION_TTL_SECONDS \
	-u S3_ENDPOINT_URL \
	-u S3_REGION \
	-u S3_BUCKET \
	-u S3_ACCESS_KEY_ID \
	-u S3_ACCESS_KEY_ID_FILE \
	-u S3_SECRET_ACCESS_KEY \
	-u S3_SECRET_ACCESS_KEY_FILE \
	-u S3_FORCE_PATH_STYLE \
	-u S3_ALLOW_INSECURE_HTTP \
	-u S3_CREATE_BUCKET \
	-u S3_STAGING_ROOT \
	-u BACKUP_SIGNING_KEY_FILE \
	-u BACKUP_SIGNING_KEY_ID \
	-u PAINTPILOT_DEMO_PRINCIPAL_ID \
	-u PAINTPILOT_DEMO_PRINCIPAL_DISPLAY_NAME \
	-u POSTGRES_HOST \
	-u POSTGRES_USER \
	-u POSTGRES_PASSWORD \
	-u POSTGRES_DB \
	-u POSTGRES_PORT \
	-u TRUSTED_HOSTS \
	-u PUBLIC_ORIGIN \
	-u SECURE_COOKIES \
	-u REQUIRE_CSRF_ORIGIN \
	-u STRUCTURED_LOGS \
	-u PHASE3A_FIXTURE_ENABLED \
	-u PHASE3B_PAINT_PLAN_ENABLED \
	-u CREDENTIAL_FIXTURE_ROOT_KEY_FILE \
	-u STAGING_RUN_ID \
	-u VITE_PHASE3A_FIXTURE_ENABLED \
	-u VITE_PHASE3B_PAINT_PLAN_ENABLED
API_UNIT_COMMAND_ENV := env \
	-u APP_ENV \
	-u APP_NAME \
	-u APP_VERSION \
	-u CREATIVEDEPLOY_ENV_FILE \
	-u DATABASE_URL \
	-u DATABASE_URL_FILE \
	-u DATABASE_HEALTH_TIMEOUT_SECONDS \
	-u DATABASE_LOCK_TIMEOUT_MS \
	-u DATABASE_STATEMENT_TIMEOUT_MS \
	-u IMAGE_STORAGE_PROVIDER \
	-u IMAGE_STORAGE_ROOT \
	-u IMAGE_UPLOAD_MAX_BYTES \
	-u IMAGE_MIN_SIDE_PX \
	-u IMAGE_MAX_SIDE_PX \
	-u IMAGE_MAX_PIXELS \
	-u IDENTITY_PROVIDER \
	-u OIDC_ISSUER \
	-u OIDC_DISCOVERY_URL \
	-u OIDC_BACKCHANNEL_BASE_URL \
	-u OIDC_CLIENT_ID \
	-u OIDC_CLIENT_SECRET \
	-u OIDC_CLIENT_SECRET_FILE \
	-u OIDC_REDIRECT_URI \
	-u OIDC_HTTP_TIMEOUT_SECONDS \
	-u OIDC_ID_TOKEN_MAX_AGE_SECONDS \
	-u OIDC_CLOCK_SKEW_SECONDS \
	-u OIDC_LOGIN_TTL_SECONDS \
	-u AUTH_SESSION_TTL_SECONDS \
	-u S3_ENDPOINT_URL \
	-u S3_REGION \
	-u S3_BUCKET \
	-u S3_ACCESS_KEY_ID \
	-u S3_ACCESS_KEY_ID_FILE \
	-u S3_SECRET_ACCESS_KEY \
	-u S3_SECRET_ACCESS_KEY_FILE \
	-u S3_FORCE_PATH_STYLE \
	-u S3_ALLOW_INSECURE_HTTP \
	-u S3_CREATE_BUCKET \
	-u S3_STAGING_ROOT \
	-u BACKUP_SIGNING_KEY_FILE \
	-u BACKUP_SIGNING_KEY_ID \
	-u PAINTPILOT_DEMO_PRINCIPAL_ID \
	-u PAINTPILOT_DEMO_PRINCIPAL_DISPLAY_NAME \
	-u POSTGRES_HOST \
	-u POSTGRES_USER \
	-u POSTGRES_PASSWORD \
	-u POSTGRES_DB \
	-u POSTGRES_PORT \
	-u TRUSTED_HOSTS \
	-u PUBLIC_ORIGIN \
	-u SECURE_COOKIES \
	-u REQUIRE_CSRF_ORIGIN \
	-u STRUCTURED_LOGS \
	-u PHASE3A_FIXTURE_ENABLED \
	-u PHASE3B_PAINT_PLAN_ENABLED \
	-u VITE_PHASE3B_PAINT_PLAN_ENABLED \
	-u CREDENTIAL_FIXTURE_ROOT_KEY_FILE \
	-u STAGING_RUN_ID

PHASE3B_UNIT_TESTS := \
	apps/api/tests/unit/test_ai_foundation_configuration_contract.py \
	apps/api/tests/unit/test_ai_foundation_security.py \
	apps/api/tests/unit/test_database_metadata.py \
	apps/api/tests/unit/test_paint_plan_models.py \
	apps/api/tests/unit/test_paint_plan_schema.py \
	apps/api/tests/unit/test_paint_project_models.py \
	apps/api/tests/unit/test_provider_transport.py \
	apps/api/tests/unit/test_region_geometry.py \
	apps/api/tests/unit/test_phase3b_validation_contract.py \
	apps/api/tests/unit/test_secret_scan_diff.py
PHASE3B_INTEGRATION_TEST := apps/api/tests/integration/test_phase3b_paint_plan_api.py

.PHONY: bootstrap bootstrap-env db-up db-down api web test-api test-api-integration \
	test-api-phase3b test-web \
	lint-api format-check-api typecheck-api lint-web typecheck-web build-web \
	migration-current migration-heads migration-history migration-check \
	check require-env config-check ensure-db validate-run-id artifact-config artifact-build \
	artifact-test artifact-isolation-test \
	artifact-smoke-up artifact-smoke-down artifact-smoke database-role-provision \
	image-storage-migrate secret-scan audit-api audit-web \
	immutable-reference-check supply-chain-check staging-secrets staging-config staging-build \
	staging-up staging-down staging-backup staging-restore staging-drill \
	demo-up demo-status demo-down demo-reset

ARTIFACT_COMPOSE := compose.artifact-smoke.yaml
STAGING_COMPOSE := compose.staging.yaml
DEMO_COMPOSE := compose.demo.yaml
DEMO_PROJECT := creativedeploy-phase2e-demo
DEMO_LIFECYCLE := python3 scripts/demo_lifecycle.py
ATTEMPT_ID ?=
RUN_ID ?= $(if $(strip $(ATTEMPT_ID)),$(ATTEMPT_ID),local_$(shell date -u +%Y%m%d%H%M%S)_$(shell uuidgen | tr '[:upper:]' '[:lower:]' | tr -d '-' | cut -c1-12))
ARTIFACT_PROJECT := creativedeploy-phase2b1-$(RUN_ID)
STAGING_PROJECT := creativedeploy-phase2b2-$(RUN_ID)
SMOKE_DATABASE_ID := phase2b1_$(RUN_ID)
STAGING_DATABASE_PREFIX ?= p2b2s
STAGING_DATABASE_ID := $(STAGING_DATABASE_PREFIX)_$(RUN_ID)
STAGING_DATABASE_NAME ?= $(STAGING_DATABASE_ID)
STAGING_DATABASE_ADMIN_USER ?= $(STAGING_DATABASE_ID)_admin
STAGING_DATABASE_MIGRATOR_USER ?= $(STAGING_DATABASE_ID)_migrator
STAGING_DATABASE_RUNTIME_USER ?= $(STAGING_DATABASE_ID)_runtime
STAGING_HOST ?= localhost
STAGING_HTTP_PORT ?= 18081
STAGING_HTTPS_PORT ?= 18443
STAGING_SECRET_ROOT ?= /tmp/creativedeploy-phase2b2-$(RUN_ID)-secrets
STAGING_BACKUP_ROOT ?= /tmp/creativedeploy-phase2b2-$(RUN_ID)-backups
STAGING_OPERATIONS_UID ?= $(shell id -u)
STAGING_OPERATIONS_GID ?= $(shell id -g)
STAGING_BACKUP_READ_ONLY ?= $(if $(filter p2b2r,$(STAGING_DATABASE_PREFIX)),true,false)
STAGING_BACKUP_SIGNING_KEY_FILE ?= $(STAGING_SECRET_ROOT)/backup_signing_key
STAGING_BACKUP_SIGNING_KEY_ID ?= p2b2-$(RUN_ID)-v1
STAGING_OIDC_CLIENT_ID ?= phase2b2-staging-client
STAGING_OIDC_USERS_JSON ?= [{"subject":"owner-a","name":"Phase 2B-2 Owner A","email":"owner-a@example.test"},{"subject":"owner-b","name":"Phase 2B-2 Owner B","email":"owner-b@example.test"},{"subject":"reviewer-c","name":"Phase 2B-2 Reviewer","email":"reviewer-c@example.test"}]
STAGING_S3_BUCKET ?= p2b2-private-$(subst _,-,$(RUN_ID))
SOURCE_GIT_COMMIT ?= $(shell git rev-parse HEAD)
ifeq ($(origin ARTIFACT_SMOKE_PORT), undefined)
ARTIFACT_SMOKE_PORT := $(shell /usr/bin/python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')
endif
ARTIFACT_COMPOSE_ENV := \
	SMOKE_RUN_ID=$(RUN_ID) \
	ARTIFACT_SMOKE_PORT=$(ARTIFACT_SMOKE_PORT) \
	SMOKE_DATABASE_ADMIN_USER=$(SMOKE_DATABASE_ID)_admin \
	SMOKE_DATABASE_ADMIN_PASSWORD=synthetic_admin_$(RUN_ID)_password \
	SMOKE_DATABASE_MIGRATOR_USER=$(SMOKE_DATABASE_ID)_migrator \
	SMOKE_DATABASE_MIGRATOR_PASSWORD=synthetic_migrator_$(RUN_ID)_password \
	SMOKE_DATABASE_RUNTIME_USER=$(SMOKE_DATABASE_ID)_runtime \
	SMOKE_DATABASE_RUNTIME_PASSWORD=synthetic_runtime_$(RUN_ID)_password \
	SMOKE_DATABASE_NAME=$(SMOKE_DATABASE_ID) \
	SMOKE_OIDC_CLIENT_ID=phase2b1-smoke-client \
	SMOKE_OIDC_CLIENT_SECRET=synthetic_oidc_$(RUN_ID)_secret \
	SMOKE_OIDC_USERS_JSON='[{"subject":"owner-a","name":"Phase 2B-1 Owner A","email":"owner-a@example.test"},{"subject":"owner-b","name":"Phase 2B-1 Owner B","email":"owner-b@example.test"},{"subject":"reviewer-c","name":"Phase 2B-1 Reviewer","email":"reviewer-c@example.test"}]' \
	SMOKE_S3_BUCKET=phase2b1-private-images \
	SMOKE_S3_ACCESS_KEY_ID=phase2b1minio \
	SMOKE_S3_SECRET_ACCESS_KEY=synthetic_minio_$(RUN_ID)_secret
STAGING_COMPOSE_ENV := \
	STAGING_RUN_ID=$(RUN_ID) \
	STAGING_HOST=$(STAGING_HOST) \
	STAGING_HTTP_PORT=$(STAGING_HTTP_PORT) \
	STAGING_HTTPS_PORT=$(STAGING_HTTPS_PORT) \
	STAGING_SECRET_ROOT=$(STAGING_SECRET_ROOT) \
	STAGING_BACKUP_ROOT=$(STAGING_BACKUP_ROOT) \
	STAGING_OPERATIONS_UID=$(STAGING_OPERATIONS_UID) \
	STAGING_OPERATIONS_GID=$(STAGING_OPERATIONS_GID) \
	STAGING_BACKUP_READ_ONLY=$(STAGING_BACKUP_READ_ONLY) \
	STAGING_BACKUP_SIGNING_KEY_FILE=$(STAGING_BACKUP_SIGNING_KEY_FILE) \
	STAGING_BACKUP_SIGNING_KEY_ID=$(STAGING_BACKUP_SIGNING_KEY_ID) \
	STAGING_DATABASE_NAME=$(STAGING_DATABASE_NAME) \
	STAGING_DATABASE_ADMIN_USER=$(STAGING_DATABASE_ADMIN_USER) \
	STAGING_DATABASE_MIGRATOR_USER=$(STAGING_DATABASE_MIGRATOR_USER) \
	STAGING_DATABASE_RUNTIME_USER=$(STAGING_DATABASE_RUNTIME_USER) \
	STAGING_OIDC_CLIENT_ID=$(STAGING_OIDC_CLIENT_ID) \
	STAGING_OIDC_USERS_JSON='$(STAGING_OIDC_USERS_JSON)' \
	STAGING_S3_BUCKET=$(STAGING_S3_BUCKET) \
	SOURCE_GIT_COMMIT=$(SOURCE_GIT_COMMIT)

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

demo-up:
	$(DEMO_LIFECYCLE) up

demo-status:
	$(DEMO_LIFECYCLE) status

demo-down:
	$(DEMO_LIFECYCLE) down

demo-reset:
	$(DEMO_LIFECYCLE) reset

test-api:
	$(API_UNIT_COMMAND_ENV) uv run --project $(PYTHON_PROJECT) pytest apps/api/tests/unit \
		--cov=creativedeploy_api --cov-report=term-missing

test-api-integration: ensure-db
	@integration_database_url="$$($(BACKEND_ENV_FILE) uv run --project $(PYTHON_PROJECT) python -c \
		'from creativedeploy_api.core.config import Settings; print(Settings().require_database_url().get_secret_value())')"; \
	$(INTEGRATION_DATABASE_ENV) DATABASE_URL="$$integration_database_url" \
		uv run --project $(PYTHON_PROJECT) alembic -c $(ALEMBIC_CONFIG) upgrade head; \
	current_revision="$$($(INTEGRATION_DATABASE_ENV) DATABASE_URL="$$integration_database_url" \
		uv run --project $(PYTHON_PROJECT) alembic -c $(ALEMBIC_CONFIG) current)"; \
	printf '%s\n' "$$current_revision"; \
	test "$$current_revision" = "$(ALEMBIC_HEAD) (head)" || \
		(echo "Integration database is not at the expected unique Alembic head $(ALEMBIC_HEAD)." >&2; exit 1); \
	$(INTEGRATION_DATABASE_ENV) \
		DATABASE_URL="$$integration_database_url" uv run --project $(PYTHON_PROJECT) \
		pytest apps/api/tests/integration -m integration

test-api-phase3b: ensure-db
	@set -eu; \
	integration_database_url="$$($(BACKEND_ENV_FILE) uv run --project $(PYTHON_PROJECT) python -c \
		'from creativedeploy_api.core.config import Settings; print(Settings().require_database_url().get_secret_value())')"; \
	$(INTEGRATION_DATABASE_ENV) DATABASE_URL="$$integration_database_url" \
		uv run --project $(PYTHON_PROJECT) alembic -c $(ALEMBIC_CONFIG) upgrade head; \
	current_revision="$$($(INTEGRATION_DATABASE_ENV) DATABASE_URL="$$integration_database_url" \
		uv run --project $(PYTHON_PROJECT) alembic -c $(ALEMBIC_CONFIG) current)"; \
	printf '%s\n' "$$current_revision"; \
	test "$$current_revision" = "$(ALEMBIC_HEAD) (head)" || \
		(echo "Phase 3B database is not at the expected unique Alembic head $(ALEMBIC_HEAD)." >&2; exit 1); \
	$(API_UNIT_COMMAND_ENV) uv run --project $(PYTHON_PROJECT) pytest -q $(PHASE3B_UNIT_TESTS); \
	$(INTEGRATION_DATABASE_ENV) DATABASE_URL="$$integration_database_url" \
		uv run --project $(PYTHON_PROJECT) pytest -q "$(PHASE3B_INTEGRATION_TEST)" -m integration

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
	@$(ARTIFACT_COMPOSE_ENV) docker compose --project-name $(ARTIFACT_PROJECT) \
		--file $(ARTIFACT_COMPOSE) \
		config --format json | uv run --project $(PYTHON_PROJECT) \
		python scripts/validate_artifact_config.py

artifact-build: artifact-config
	@$(ARTIFACT_COMPOSE_ENV) docker compose --project-name $(ARTIFACT_PROJECT) \
		--file $(ARTIFACT_COMPOSE) \
		build migrate api web

artifact-test: artifact-config
	$(WEB_COMMAND_ENV) VITE_RUNTIME_PROFILE=artifact-smoke \
		$(PNPM) --filter $(WEB_PACKAGE) build

artifact-smoke-up: artifact-config
	@$(ARTIFACT_COMPOSE_ENV) docker compose --project-name $(ARTIFACT_PROJECT) \
		--file $(ARTIFACT_COMPOSE) \
		up --detach --build --wait
	@$(ARTIFACT_COMPOSE_ENV) docker compose --project-name $(ARTIFACT_PROJECT) \
		--file $(ARTIFACT_COMPOSE) port web 8080

artifact-smoke-down: validate-run-id
	@$(ARTIFACT_COMPOSE_ENV) docker compose --project-name $(ARTIFACT_PROJECT) \
		--file $(ARTIFACT_COMPOSE) \
		down --volumes --remove-orphans --rmi local

artifact-smoke: artifact-config
	RUN_ID=$(RUN_ID) ARTIFACT_SMOKE_PORT=$(ARTIFACT_SMOKE_PORT) ./scripts/verify_artifact_smoke.sh

database-role-provision: require-env
	$(BACKEND_ENV_FILE) uv run --project $(PYTHON_PROJECT) \
		python -m creativedeploy_api.tools.provision_database_roles

image-storage-migrate: require-env
	$(BACKEND_ENV_FILE) uv run --project $(PYTHON_PROJECT) \
		python -m creativedeploy_api.tools.migrate_image_storage

artifact-isolation-test: validate-run-id
	RUN_ID=$(RUN_ID) ./scripts/verify_attempt_isolation.sh

staging-secrets: validate-run-id
	uv run --project $(PYTHON_PROJECT) python scripts/prepare_staging_attempt.py \
		--run-id "$(RUN_ID)" \
		--secret-root "$(STAGING_SECRET_ROOT)" \
		--backup-root "$(STAGING_BACKUP_ROOT)" \
		--host "$(STAGING_HOST)" \
		--database-name "$(STAGING_DATABASE_NAME)" \
		--admin-user "$(STAGING_DATABASE_ADMIN_USER)" \
		--migrator-user "$(STAGING_DATABASE_MIGRATOR_USER)" \
		--runtime-user "$(STAGING_DATABASE_RUNTIME_USER)"

staging-config: validate-run-id
	$(STAGING_COMPOSE_ENV) docker compose --project-name $(STAGING_PROJECT) \
		--file $(STAGING_COMPOSE) --profile operations config --format json | \
		uv run --project $(PYTHON_PROJECT) python scripts/validate_staging_config.py

staging-build: staging-config
	$(STAGING_COMPOSE_ENV) docker compose --project-name $(STAGING_PROJECT) \
		--file $(STAGING_COMPOSE) --profile operations \
		build migrate api operations web tls_proxy

staging-up: staging-config
	$(STAGING_COMPOSE_ENV) docker compose --project-name $(STAGING_PROJECT) \
		--file $(STAGING_COMPOSE) up --detach --build --wait

staging-down: validate-run-id
	$(STAGING_COMPOSE_ENV) docker compose --project-name $(STAGING_PROJECT) \
		--file $(STAGING_COMPOSE) down --volumes --remove-orphans --rmi local

staging-backup: staging-config
	@test -n "$(BACKUP_ID)" || (echo "BACKUP_ID is required."; exit 1)
	@set -eu; \
		$(STAGING_COMPOSE_ENV) docker compose --project-name $(STAGING_PROJECT) \
			--file $(STAGING_COMPOSE) stop api; \
		trap 'docker start $(STAGING_PROJECT)-api-1 >/dev/null 2>&1 || true' EXIT HUP INT TERM; \
		$(STAGING_COMPOSE_ENV) OPERATIONS_QUIESCED=true docker compose \
			--project-name $(STAGING_PROJECT) --file $(STAGING_COMPOSE) --profile operations \
			run --rm --env OPERATIONS_QUIESCED=true operations \
			backup --backup-id "$(BACKUP_ID)" --dry-run; \
		$(STAGING_COMPOSE_ENV) OPERATIONS_QUIESCED=true docker compose \
			--project-name $(STAGING_PROJECT) --file $(STAGING_COMPOSE) --profile operations \
			run --rm --env OPERATIONS_QUIESCED=true operations \
			backup --backup-id "$(BACKUP_ID)"; \
		$(STAGING_COMPOSE_ENV) docker compose --project-name $(STAGING_PROJECT) \
			--file $(STAGING_COMPOSE) start api; \
		trap - EXIT HUP INT TERM

staging-restore: staging-config
	@test -n "$(BACKUP_ID)" || (echo "BACKUP_ID is required."; exit 1)
	@test "$(STAGING_DATABASE_PREFIX)" = "p2b2r" || \
		(echo "Restore requires STAGING_DATABASE_PREFIX=p2b2r."; exit 1)
	@set -eu; \
		$(STAGING_COMPOSE_ENV) docker compose --project-name $(STAGING_PROJECT) \
			--file $(STAGING_COMPOSE) stop api; \
		trap 'docker start $(STAGING_PROJECT)-api-1 >/dev/null 2>&1 || true' EXIT HUP INT TERM; \
		$(STAGING_COMPOSE_ENV) OPERATIONS_QUIESCED=true RESTORE_TEMPORARY=true docker compose \
			--project-name $(STAGING_PROJECT) --file $(STAGING_COMPOSE) --profile operations \
			run --rm --env OPERATIONS_QUIESCED=true --env RESTORE_TEMPORARY=true operations \
			restore --backup-id "$(BACKUP_ID)" --dry-run; \
		$(STAGING_COMPOSE_ENV) OPERATIONS_QUIESCED=true RESTORE_TEMPORARY=true docker compose \
			--project-name $(STAGING_PROJECT) --file $(STAGING_COMPOSE) --profile operations \
			run --rm --env OPERATIONS_QUIESCED=true --env RESTORE_TEMPORARY=true operations \
			restore --backup-id "$(BACKUP_ID)"; \
		$(STAGING_COMPOSE_ENV) docker compose --project-name $(STAGING_PROJECT) \
			--file $(STAGING_COMPOSE) start api; \
		trap - EXIT HUP INT TERM

staging-drill: validate-run-id
	RUN_ID=$(RUN_ID) ./scripts/verify_staging_drill.sh

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
