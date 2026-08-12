"""Isolated PostgreSQL round-trip tests for the first business migration."""

import asyncio
import os
import re
import secrets
import subprocess
import uuid
from collections.abc import Callable, Iterator
from concurrent.futures import Future
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event, Thread
from time import monotonic, sleep
from typing import Any
from urllib.parse import quote, quote_plus

import psycopg
import pytest
from psycopg import sql
from psycopg.types.json import Jsonb
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from creativedeploy_api.ai.constants import (
    FIXTURE_PROVIDER_ID,
    FIXTURE_STRUCTURED_CAPABILITY_ID,
    FIXTURE_TEXT_CAPABILITY_ID,
    FIXTURE_TEXT_MODEL_ID,
    FIXTURE_VISION_MODEL_ID,
)
from creativedeploy_api.ai.encryption import CredentialCipher, FixtureRootKeyProvider
from creativedeploy_api.ai.fixture_provider import FixtureProviderAdapter
from creativedeploy_api.core.config import POSTGRES_COMPONENT_NAMES, Settings
from creativedeploy_api.core.principal import (
    AuthenticationMode,
    PrincipalContext,
    PrincipalType,
)
from creativedeploy_api.schemas.ai_foundation import (
    CredentialCreateRequest,
    CredentialGrantRequest,
    CredentialMutationRequest,
    CredentialRead,
    CredentialReplaceRequest,
    FixtureInvocationPayload,
    InvocationCreateRequest,
    InvocationPreviewRequest,
    ProjectPolicyUpdate,
    UserPreferenceUpdate,
)
from creativedeploy_api.services.ai_foundation import (
    AdmissionRejectedError,
    AIAuthorizationError,
    AIConflictError,
    AIFoundationService,
    AIIdempotencyConflictError,
    AIResourceNotFoundError,
)
from creativedeploy_api.services.identity import ProjectMembershipService

pytestmark = pytest.mark.integration

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
ALEMBIC_COMMAND = (
    "uv",
    "run",
    "--project",
    "apps/api",
    "alembic",
    "-c",
    "apps/api/alembic.ini",
)
PHASE_3A_BUSINESS_TABLES = {
    "ai_audit_events",
    "ai_command_idempotency_records",
    "ai_cost_ledger",
    "ai_invocation_events",
    "ai_usage_ledger",
    "auth_sessions",
    "budget_reservations",
    "capability_definitions",
    "command_idempotency_records",
    "credential_project_grants",
    "credential_records",
    "external_identities",
    "image_assets",
    "image_set_readiness_reviews",
    "invocation_attempts",
    "invocation_requests",
    "model_capabilities",
    "model_definitions",
    "oidc_login_flows",
    "paint_projects",
    "project_memberships",
    "project_budget_counters",
    "project_budget_policies",
    "project_model_policies",
    "project_model_policy_capabilities",
    "project_model_policy_credentials",
    "project_model_policy_models",
    "project_model_policy_providers",
    "provider_capabilities",
    "provider_definitions",
    "region_set_reviews",
    "region_sets",
    "region_vertices",
    "regions",
    "state_transition_events",
    "user_accounts",
    "user_budget_counters",
    "user_budget_policies",
    "user_provider_preferences",
}
PHASE_3B_BUSINESS_TABLES = {
    "paint_plan_region_instructions",
    "paint_plan_review_events",
    "paint_plans",
    "prompt_template_definitions",
    "provider_pricing_snapshots",
}
ARCANA_BUSINESS_TABLES = {
    "tarot_card_definitions",
    "tarot_interpretation_revisions",
    "tarot_journal_entries",
    "tarot_reading_cards",
    "tarot_readings",
    "tarot_spread_definitions",
}
CURRENT_BUSINESS_TABLES = (
    PHASE_3A_BUSINESS_TABLES | PHASE_3B_BUSINESS_TABLES | ARCANA_BUSINESS_TABLES
)
EXPECTED_COLUMNS = {
    "user_accounts": (
        "id",
        "display_name",
        "email",
        "is_active",
        "created_at",
        "updated_at",
    ),
    "external_identities": (
        "id",
        "user_id",
        "issuer",
        "subject",
        "email_snapshot",
        "display_name_snapshot",
        "created_at",
        "last_authenticated_at",
    ),
    "project_memberships": (
        "id",
        "paint_project_id",
        "user_id",
        "role",
        "assigned_by_user_id",
        "created_at",
    ),
    "oidc_login_flows": (
        "id",
        "state_hash",
        "browser_binding_hash",
        "nonce",
        "code_verifier",
        "return_to",
        "created_at",
        "expires_at",
        "consumed_at",
    ),
    "auth_sessions": (
        "id",
        "user_id",
        "token_hash",
        "csrf_token_hash",
        "oidc_issuer",
        "created_at",
        "last_seen_at",
        "expires_at",
        "revoked_at",
    ),
    "paint_projects": (
        "id",
        "owner_principal_id",
        "title",
        "description",
        "requested_target_style",
        "planning_mode",
        "status",
        "created_at",
        "updated_at",
        "current_image_asset_id",
    ),
    "state_transition_events": (
        "id",
        "project_id",
        "from_state",
        "to_state",
        "event",
        "actor_type",
        "actor_principal_id",
        "actor_display_name_snapshot",
        "reason",
        "correlation_id",
        "event_metadata",
        "created_at",
    ),
    "command_idempotency_records": (
        "id",
        "scope_key",
        "principal_id",
        "command_type",
        "idempotency_key",
        "payload_hash",
        "execution_status",
        "resource_type",
        "resource_id",
        "http_status",
        "response_snapshot",
        "created_at",
        "expires_at",
    ),
    "image_assets": (
        "id",
        "paint_project_id",
        "owner_principal_id",
        "role",
        "version",
        "supersedes_image_asset_id",
        "is_current",
        "lifecycle_status",
        "storage_provider",
        "storage_key",
        "original_filename",
        "declared_content_type",
        "detected_format",
        "byte_size",
        "width",
        "height",
        "pixel_count",
        "color_mode",
        "has_alpha",
        "exif_orientation",
        "sha256",
        "upload_validation_result",
        "upload_validation_details",
        "source_type",
        "rights_attestation_status",
        "rights_attestation_version",
        "intended_usage",
        "rights_attested_by_principal_id",
        "rights_attested_at",
        "created_by_actor_type",
        "created_by_actor_id",
        "created_by_actor_display_name_snapshot",
        "created_at",
    ),
    "image_set_readiness_reviews": (
        "id",
        "owner_principal_id",
        "paint_project_id",
        "version",
        "verdict",
        "reason",
        "primary_front_image_asset_id",
        "primary_front_role",
        "reference_back_image_asset_id",
        "reference_back_role",
        "reference_angle_image_asset_id",
        "reference_angle_role",
        "reference_detail_image_asset_id",
        "reference_detail_role",
        "image_set_fingerprint",
        "actor_type",
        "actor_id",
        "actor_display_name_snapshot",
        "created_at",
    ),
}
EXPECTED_WORKFLOW_STATES = (
    "DRAFT",
    "IMAGE_UPLOADED",
    "IMAGE_REVIEW_REQUIRED",
    "IMAGE_VALIDATION_FAILED",
    "IMAGE_VALIDATED",
    "REGION_ANALYSIS_RUNNING",
    "REGION_REVIEW_REQUIRED",
    "REGIONS_CONFIRMED",
    "PLAN_GENERATION_RUNNING",
    "PLAN_REVIEW_REQUIRED",
    "PLAN_APPROVED",
    "COMPLETED",
    "BLOCKED_LOW_CONFIDENCE",
    "FAILED_RETRYABLE",
    "FAILED_FINAL",
    "ABANDONED",
)
ALEMBIC_TIMEOUT_SECONDS = 120
MAINTENANCE_DATABASE = "postgres"
DUPLICATE_DATABASE_SQLSTATE = "42P04"
DUPLICATE_OBJECT_SQLSTATE = "42710"
TEMPORARY_DATABASE_PATTERN = re.compile(r"^creativedeploy_migration_test_[0-9a-f]{16,32}$")
TEMPORARY_DATABASE_RESIDUAL_PATTERN = r"^creativedeploy_migration_test_"
TEMPORARY_OWNER_ROLE_PATTERN = re.compile(r"^creativedeploy_migration_owner_[0-9a-f]{16,32}$")
TEMPORARY_OWNER_ROLE_RESIDUAL_PATTERN = r"^creativedeploy_migration_owner_"
OWNERSHIP_TOKEN_PATTERN = re.compile(r"^[0-9a-f]{32}$")
OWNERSHIP_MARKER_PREFIX = "creativedeploy-fixture-owner:"


@dataclass(frozen=True)
class TemporaryDatabase:
    url: URL
    name: str
    owner_role: str

    def __repr__(self) -> str:
        return f"TemporaryDatabase(name={self.name!r}, owner_role={self.owner_role!r})"


@dataclass(frozen=True)
class TemporaryDatabaseOwnership:
    database_name: str
    owner_role: str
    ownership_token: str


class SyntheticCreateFailure(RuntimeError):
    """A test-only failure raised before a normal CREATE confirmation returns."""


class OwnershipNotProven(RuntimeError):
    """Destructive cleanup was refused because PostgreSQL ownership was not proven."""


CreateDatabaseOperation = Callable[
    [psycopg.Connection[tuple[Any, ...]], TemporaryDatabaseOwnership],
    None,
]
DropDatabaseOperation = Callable[
    [
        psycopg.Connection[tuple[Any, ...]],
        TemporaryDatabaseOwnership,
        str,
        bool,
    ],
    None,
]
BeforeCleanupOperation = Callable[
    [psycopg.Connection[tuple[Any, ...]], TemporaryDatabaseOwnership],
    None,
]


def _connection_kwargs(database_url: URL, database: str) -> dict[str, object]:
    return {
        "dbname": database,
        "user": database_url.username,
        "password": database_url.password,
        "host": database_url.host,
        "port": database_url.port,
    }


def _database_diagnostic_tokens(database_url: URL) -> tuple[str, ...]:
    tokens = {database_url.render_as_string(hide_password=False)}
    for component in (
        database_url.username,
        database_url.password,
        database_url.database,
    ):
        if component:
            tokens.update(
                {
                    component,
                    quote(component, safe=""),
                    quote_plus(component, safe=""),
                }
            )
    return tuple(sorted((token for token in tokens if token), key=len, reverse=True))


def _redact_database_diagnostics(text: str, database_url: URL) -> str:
    redacted = text
    for token in _database_diagnostic_tokens(database_url):
        redacted = re.sub(
            re.escape(token),
            "[REDACTED]",
            redacted,
            flags=re.IGNORECASE,
        )
    return redacted


def _subprocess_output_text(output: str | bytes | None) -> str:
    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return output


def _run_alembic(database_url: URL, *arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    rendered_database_url = database_url.render_as_string(hide_password=False)
    for component_name in POSTGRES_COMPONENT_NAMES:
        environment.pop(component_name, None)
    environment["CREATIVEDEPLOY_ENV_FILE"] = os.devnull
    environment["APP_ENV"] = "test"
    environment["DATABASE_URL"] = rendered_database_url
    try:
        result = subprocess.run(
            [*ALEMBIC_COMMAND, *arguments],
            cwd=REPOSITORY_ROOT,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=ALEMBIC_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        safe_stdout = _redact_database_diagnostics(
            _subprocess_output_text(error.stdout),
            database_url,
        )
        safe_stderr = _redact_database_diagnostics(
            _subprocess_output_text(error.stderr),
            database_url,
        )
        raise AssertionError(
            f"Alembic {' '.join(arguments)} timed out after "
            f"{ALEMBIC_TIMEOUT_SECONDS} seconds.\n"
            f"stdout:\n{safe_stdout}\nstderr:\n{safe_stderr}"
        ) from None
    if result.returncode != 0:
        safe_stdout = _redact_database_diagnostics(
            result.stdout,
            database_url,
        )
        safe_stderr = _redact_database_diagnostics(
            result.stderr,
            database_url,
        )
        raise AssertionError(
            f"Alembic {' '.join(arguments)} failed with exit code "
            f"{result.returncode}.\nstdout:\n{safe_stdout}\nstderr:\n{safe_stderr}"
        )
    return result


def _expect_rejection(
    connection: psycopg.Connection[tuple[Any, ...]],
    query: str,
    parameters: tuple[object, ...],
    *,
    case_label: str,
    expected_sqlstate: str,
    expected_constraint_name: str | None,
) -> None:
    try:
        with connection.transaction():
            connection.execute(query, parameters)
    except psycopg.Error as error:
        actual_sqlstate = error.sqlstate
        actual_constraint_name = error.diag.constraint_name
        assert actual_sqlstate == expected_sqlstate, (
            f"{case_label}: expected SQLSTATE {expected_sqlstate}, "
            f"got {actual_sqlstate}; expected constraint "
            f"{expected_constraint_name!r}, got {actual_constraint_name!r}"
        )
        assert actual_constraint_name == expected_constraint_name, (
            f"{case_label}: expected constraint {expected_constraint_name!r}, "
            f"got {actual_constraint_name!r}; SQLSTATE {actual_sqlstate}"
        )
    else:
        pytest.fail(
            f"{case_label}: database operation succeeded; expected SQLSTATE "
            f"{expected_sqlstate} and constraint {expected_constraint_name!r}"
        )

    with connection.transaction():
        assert connection.execute("SELECT 1").fetchone() == (1,)


def _validate_temporary_database_name(
    temporary_database: str,
    *,
    development_database: str,
    maintenance_database: str,
) -> None:
    assert TEMPORARY_DATABASE_PATTERN.fullmatch(temporary_database), (
        f"Unsafe temporary database name: {temporary_database!r}"
    )
    assert temporary_database != development_database
    assert temporary_database != maintenance_database


def _database_exists(
    connection: psycopg.Connection[tuple[Any, ...]],
    database_name: str,
) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (database_name,),
        ).fetchone()
        is not None
    )


def _validate_temporary_owner_role_name(owner_role: str) -> None:
    assert TEMPORARY_OWNER_ROLE_PATTERN.fullmatch(owner_role), "Unsafe temporary owner role name."


def _validate_ownership_token(ownership_token: str) -> None:
    assert OWNERSHIP_TOKEN_PATTERN.fullmatch(ownership_token), "Unsafe temporary ownership token."


def _ownership_marker(ownership_token: str) -> str:
    _validate_ownership_token(ownership_token)
    return f"{OWNERSHIP_MARKER_PREFIX}{ownership_token}"


def _validate_ownership_identity(
    ownership: TemporaryDatabaseOwnership,
    *,
    development_database: str,
) -> None:
    _validate_temporary_database_name(
        ownership.database_name,
        development_database=development_database,
        maintenance_database=MAINTENANCE_DATABASE,
    )
    _validate_temporary_owner_role_name(ownership.owner_role)
    _validate_ownership_token(ownership.ownership_token)


def _owner_role_state(
    connection: psycopg.Connection[tuple[Any, ...]],
    owner_role: str,
) -> tuple[bool, str | None] | None:
    row = connection.execute(
        """
        SELECT rolcanlogin, shobj_description(oid, 'pg_authid')
        FROM pg_roles
        WHERE rolname = %s
        """,
        (owner_role,),
    ).fetchone()
    if row is None:
        return None
    return bool(row[0]), row[1]


def _database_owner_state(
    connection: psycopg.Connection[tuple[Any, ...]],
    database_name: str,
) -> tuple[str, bool, str | None] | None:
    row = connection.execute(
        """
        SELECT owner_role.rolname,
               owner_role.rolcanlogin,
               shobj_description(owner_role.oid, 'pg_authid')
        FROM pg_database AS database
        JOIN pg_roles AS owner_role ON owner_role.oid = database.datdba
        WHERE database.datname = %s
        """,
        (database_name,),
    ).fetchone()
    if row is None:
        return None
    return str(row[0]), bool(row[1]), row[2]


def _set_owner_role_marker(
    connection: psycopg.Connection[tuple[Any, ...]],
    owner_role: str,
    marker: str | None,
) -> None:
    _validate_temporary_owner_role_name(owner_role)
    marker_sql = sql.SQL("NULL") if marker is None else sql.Literal(marker)
    connection.execute(
        sql.SQL("COMMENT ON ROLE {} IS {}").format(
            sql.Identifier(owner_role),
            marker_sql,
        )
    )


def _role_ownership_is_proven(
    connection: psycopg.Connection[tuple[Any, ...]],
    ownership: TemporaryDatabaseOwnership,
) -> bool:
    return _owner_role_state(connection, ownership.owner_role) == (
        False,
        _ownership_marker(ownership.ownership_token),
    )


def _claim_owner_role(
    connection: psycopg.Connection[tuple[Any, ...]],
    ownership: TemporaryDatabaseOwnership,
    *,
    development_database: str,
) -> None:
    assert connection.autocommit
    _validate_ownership_identity(
        ownership,
        development_database=development_database,
    )
    try:
        with connection.transaction():
            if _owner_role_state(connection, ownership.owner_role) is not None:
                raise OwnershipNotProven(
                    "OWNERSHIP_NOT_PROVEN: temporary owner role already exists."
                )
            connection.execute(
                sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(ownership.owner_role))
            )
            _set_owner_role_marker(
                connection,
                ownership.owner_role,
                _ownership_marker(ownership.ownership_token),
            )
            if not _role_ownership_is_proven(connection, ownership):
                raise OwnershipNotProven(
                    "OWNERSHIP_NOT_PROVEN: temporary owner role marker was not confirmed."
                )
    except psycopg.Error as error:
        if error.sqlstate == DUPLICATE_OBJECT_SQLSTATE:
            raise OwnershipNotProven(
                "OWNERSHIP_NOT_PROVEN: temporary owner role claim collided."
            ) from None
        raise

    if not _role_ownership_is_proven(connection, ownership):
        raise OwnershipNotProven("OWNERSHIP_NOT_PROVEN: temporary owner role changed after claim.")


def _create_database(
    connection: psycopg.Connection[tuple[Any, ...]],
    ownership: TemporaryDatabaseOwnership,
    development_database: str,
) -> None:
    assert connection.autocommit
    _validate_ownership_identity(
        ownership,
        development_database=development_database,
    )
    if not _role_ownership_is_proven(connection, ownership):
        raise OwnershipNotProven("OWNERSHIP_NOT_PROVEN: owner role changed before CREATE DATABASE.")
    connection.execute(
        sql.SQL("CREATE DATABASE {} OWNER {}").format(
            sql.Identifier(ownership.database_name),
            sql.Identifier(ownership.owner_role),
        )
    )


def _database_ownership_is_proven(
    connection: psycopg.Connection[tuple[Any, ...]],
    ownership: TemporaryDatabaseOwnership,
    *,
    development_database: str,
    create_returned_duplicate: bool,
) -> bool:
    _validate_ownership_identity(
        ownership,
        development_database=development_database,
    )
    if create_returned_duplicate:
        return False
    return _database_owner_state(connection, ownership.database_name) == (
        ownership.owner_role,
        False,
        _ownership_marker(ownership.ownership_token),
    )


def _drop_database(
    connection: psycopg.Connection[tuple[Any, ...]],
    ownership: TemporaryDatabaseOwnership,
    development_database: str,
    create_returned_duplicate: bool,
) -> None:
    assert connection.autocommit
    _validate_ownership_identity(
        ownership,
        development_database=development_database,
    )
    if not _database_ownership_is_proven(
        connection,
        ownership,
        development_database=development_database,
        create_returned_duplicate=create_returned_duplicate,
    ):
        raise OwnershipNotProven(
            "OWNERSHIP_NOT_PROVEN: refusing to terminate database connections."
        )

    expected_marker = _ownership_marker(ownership.ownership_token)
    connection.execute(
        """
        SELECT pg_terminate_backend(activity.pid)
        FROM pg_stat_activity AS activity
        JOIN pg_database AS database ON database.datname = activity.datname
        JOIN pg_roles AS owner_role ON owner_role.oid = database.datdba
        WHERE activity.datname = %s
          AND activity.pid <> pg_backend_pid()
          AND owner_role.rolname = %s
          AND owner_role.rolcanlogin IS FALSE
          AND shobj_description(owner_role.oid, 'pg_authid') = %s
        """,
        (
            ownership.database_name,
            ownership.owner_role,
            expected_marker,
        ),
    )

    if not _database_ownership_is_proven(
        connection,
        ownership,
        development_database=development_database,
        create_returned_duplicate=create_returned_duplicate,
    ):
        raise OwnershipNotProven("OWNERSHIP_NOT_PROVEN: database ownership changed before DROP.")

    connection.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(ownership.owner_role)))
    try:
        if not _database_ownership_is_proven(
            connection,
            ownership,
            development_database=development_database,
            create_returned_duplicate=create_returned_duplicate,
        ):
            raise OwnershipNotProven(
                "OWNERSHIP_NOT_PROVEN: database ownership changed before DROP."
            )
        connection.execute(
            sql.SQL("DROP DATABASE {}").format(sql.Identifier(ownership.database_name))
        )
    except psycopg.Error as error:
        if error.sqlstate == "42501":
            raise OwnershipNotProven(
                "OWNERSHIP_NOT_PROVEN: PostgreSQL refused owner-authorized DROP."
            ) from None
        raise
    finally:
        connection.execute("RESET ROLE")

    if _database_exists(connection, ownership.database_name):
        raise AssertionError("Temporary database still exists after owned DROP.")


def _drop_owner_role(
    connection: psycopg.Connection[tuple[Any, ...]],
    ownership: TemporaryDatabaseOwnership,
    *,
    development_database: str,
) -> None:
    assert connection.autocommit
    _validate_ownership_identity(
        ownership,
        development_database=development_database,
    )
    if _owner_role_state(connection, ownership.owner_role) is None:
        return
    if not _role_ownership_is_proven(connection, ownership):
        raise OwnershipNotProven("OWNERSHIP_NOT_PROVEN: refusing to DROP temporary owner role.")
    if (
        connection.execute(
            """
            SELECT 1
            FROM pg_database AS database
            JOIN pg_roles AS owner_role ON owner_role.oid = database.datdba
            WHERE owner_role.rolname = %s
            LIMIT 1
            """,
            (ownership.owner_role,),
        ).fetchone()
        is not None
    ):
        raise OwnershipNotProven(
            "OWNERSHIP_NOT_PROVEN: temporary owner role still owns a database."
        )
    if not _role_ownership_is_proven(connection, ownership):
        raise OwnershipNotProven("OWNERSHIP_NOT_PROVEN: temporary owner role changed before DROP.")
    connection.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(ownership.owner_role)))
    if _owner_role_state(connection, ownership.owner_role) is not None:
        raise AssertionError("Temporary owner role still exists after owned DROP.")


def _temporary_database_name() -> str:
    return f"creativedeploy_migration_test_{secrets.token_hex(8)}"


def _temporary_database_ownership(
    database_name: str,
) -> TemporaryDatabaseOwnership:
    return TemporaryDatabaseOwnership(
        database_name=database_name,
        owner_role=f"creativedeploy_migration_owner_{secrets.token_hex(8)}",
        ownership_token=secrets.token_hex(16),
    )


def _safe_residual_names(
    names: tuple[str, ...],
    *,
    expected_pattern: re.Pattern[str],
) -> tuple[str, ...]:
    return tuple(
        name if expected_pattern.fullmatch(name) else "<redacted-unexpected-name-shape>"
        for name in names
    )


def _temporary_resource_residuals(
    connection: psycopg.Connection[tuple[Any, ...]],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    database_residuals = tuple(
        str(row[0])
        for row in connection.execute(
            "SELECT datname FROM pg_database WHERE datname ~ %s ORDER BY datname",
            (TEMPORARY_DATABASE_RESIDUAL_PATTERN,),
        ).fetchall()
    )
    role_residuals = tuple(
        str(row[0])
        for row in connection.execute(
            "SELECT rolname FROM pg_roles WHERE rolname ~ %s ORDER BY rolname",
            (TEMPORARY_OWNER_ROLE_RESIDUAL_PATTERN,),
        ).fetchall()
    )
    return database_residuals, role_residuals


def _assert_global_database_hygiene(
    connection: psycopg.Connection[tuple[Any, ...]],
    *,
    development_database: str,
) -> None:
    assert _database_exists(connection, development_database), (
        "GLOBAL_HYGIENE_AUDIT_FAILED: development database is missing."
    )
    assert _database_exists(connection, MAINTENANCE_DATABASE), (
        "GLOBAL_HYGIENE_AUDIT_FAILED: maintenance database is missing."
    )
    database_residuals, role_residuals = _temporary_resource_residuals(connection)
    if database_residuals or role_residuals:
        safe_database_names = _safe_residual_names(
            database_residuals,
            expected_pattern=TEMPORARY_DATABASE_PATTERN,
        )
        safe_role_names = _safe_residual_names(
            role_residuals,
            expected_pattern=TEMPORARY_OWNER_ROLE_PATTERN,
        )
        raise AssertionError(
            "GLOBAL_HYGIENE_AUDIT_FAILED: "
            f"database residual count={len(database_residuals)} "
            f"names={safe_database_names!r}; "
            f"role residual count={len(role_residuals)} "
            f"names={safe_role_names!r}"
        )


def _assert_exact_temporary_cleanup_state(
    connection: psycopg.Connection[tuple[Any, ...]],
    ownership: TemporaryDatabaseOwnership,
    *,
    development_database: str,
    expect_database_absent: bool,
) -> None:
    _validate_ownership_identity(
        ownership,
        development_database=development_database,
    )
    assert _database_exists(connection, development_database)
    assert _database_exists(connection, MAINTENANCE_DATABASE)
    assert _owner_role_state(connection, ownership.owner_role) is None, (
        "Fixture owner role still exists after exact cleanup."
    )
    assert connection.execute(
        """
        SELECT count(*)
        FROM pg_roles
        WHERE shobj_description(oid, 'pg_authid') = %s
        """,
        (_ownership_marker(ownership.ownership_token),),
    ).fetchone() == (0,), "Fixture ownership marker still exists after exact cleanup."
    if expect_database_absent:
        assert not _database_exists(connection, ownership.database_name), (
            "Fixture database still exists after exact cleanup."
        )
        assert connection.execute(
            "SELECT count(*) FROM pg_stat_activity WHERE datname = %s",
            (ownership.database_name,),
        ).fetchone() == (0,), "Fixture database connections remain after exact cleanup."


def _assert_global_database_hygiene_for_url(development_url: URL) -> None:
    development_database = development_url.database
    assert development_database is not None
    with psycopg.connect(
        **_connection_kwargs(development_url, MAINTENANCE_DATABASE),
        autocommit=True,
    ) as maintenance_connection:
        _assert_global_database_hygiene(
            maintenance_connection,
            development_database=development_database,
        )


def _assert_exact_temporary_resources_were_removed(
    development_url: URL,
    ownership: TemporaryDatabaseOwnership,
) -> None:
    development_database = development_url.database
    assert development_database is not None
    with psycopg.connect(
        **_connection_kwargs(development_url, MAINTENANCE_DATABASE),
        autocommit=True,
    ) as maintenance_connection:
        _assert_exact_temporary_cleanup_state(
            maintenance_connection,
            ownership,
            development_database=development_database,
            expect_database_absent=True,
        )


@contextmanager
def _temporary_database_resource(
    development_url: URL,
    temporary_database: str,
    *,
    ownership: TemporaryDatabaseOwnership | None = None,
    create_database: CreateDatabaseOperation | None = None,
    drop_database: DropDatabaseOperation = _drop_database,
    before_cleanup: BeforeCleanupOperation | None = None,
) -> Iterator[TemporaryDatabase]:
    development_database = development_url.database
    assert development_database is not None
    _validate_temporary_database_name(
        temporary_database,
        development_database=development_database,
        maintenance_database=MAINTENANCE_DATABASE,
    )
    if ownership is None:
        ownership = _temporary_database_ownership(temporary_database)
    assert ownership.database_name == temporary_database
    _validate_ownership_identity(
        ownership,
        development_database=development_database,
    )
    if create_database is None:

        def default_create_database(
            connection: psycopg.Connection[tuple[Any, ...]],
            identity: TemporaryDatabaseOwnership,
        ) -> None:
            _create_database(
                connection,
                identity,
                development_database,
            )

        create_database = default_create_database
    temporary_url = development_url.set(database=temporary_database)
    role_claimed = False
    create_returned_duplicate = False
    primary_error: BaseException | None = None

    try:
        with psycopg.connect(
            **_connection_kwargs(development_url, MAINTENANCE_DATABASE),
            autocommit=True,
        ) as maintenance_connection:
            assert _database_exists(maintenance_connection, development_database)
            assert _database_exists(maintenance_connection, MAINTENANCE_DATABASE)
            assert not _database_exists(maintenance_connection, temporary_database), (
                "Refusing to own or delete a temporary database that existed before "
                "this test's CREATE attempt."
            )
            _claim_owner_role(
                maintenance_connection,
                ownership,
                development_database=development_database,
            )
            role_claimed = True
            try:
                create_database(maintenance_connection, ownership)
            except psycopg.Error as error:
                if error.sqlstate == DUPLICATE_DATABASE_SQLSTATE:
                    create_returned_duplicate = True
                raise
        yield TemporaryDatabase(
            url=temporary_url,
            name=temporary_database,
            owner_role=ownership.owner_role,
        )
    except BaseException as error:
        primary_error = error

    cleanup_error: BaseException | None = None
    if role_claimed:
        try:
            with psycopg.connect(
                **_connection_kwargs(development_url, MAINTENANCE_DATABASE),
                autocommit=True,
            ) as maintenance_connection:
                if before_cleanup is not None:
                    before_cleanup(maintenance_connection, ownership)
                database_exists = _database_exists(
                    maintenance_connection,
                    ownership.database_name,
                )
                role_cleanup_allowed = not database_exists
                if database_exists:
                    if create_returned_duplicate:
                        role_cleanup_allowed = True
                    elif _database_ownership_is_proven(
                        maintenance_connection,
                        ownership,
                        development_database=development_database,
                        create_returned_duplicate=create_returned_duplicate,
                    ):
                        drop_database(
                            maintenance_connection,
                            ownership,
                            development_database,
                            create_returned_duplicate,
                        )
                        role_cleanup_allowed = not _database_exists(
                            maintenance_connection,
                            ownership.database_name,
                        )
                    else:
                        cleanup_error = OwnershipNotProven(
                            "OWNERSHIP_NOT_PROVEN: database cleanup was refused."
                        )
                if role_cleanup_allowed:
                    _drop_owner_role(
                        maintenance_connection,
                        ownership,
                        development_database=development_database,
                    )
                if cleanup_error is None:
                    _assert_exact_temporary_cleanup_state(
                        maintenance_connection,
                        ownership,
                        development_database=development_database,
                        expect_database_absent=not create_returned_duplicate,
                    )
        except BaseException as error:
            cleanup_error = error

    if primary_error is not None and cleanup_error is not None:
        raise BaseExceptionGroup(
            "Temporary database body and ownership-safe teardown both failed.",
            [primary_error, cleanup_error],
        )
    if primary_error is not None:
        raise primary_error.with_traceback(primary_error.__traceback__)
    if cleanup_error is not None:
        raise cleanup_error


@pytest.fixture(scope="module", autouse=True)
def global_database_hygiene_gate() -> Iterator[None]:
    development_url = make_url(Settings().database_url.get_secret_value())
    _assert_global_database_hygiene_for_url(development_url)
    yield
    _assert_global_database_hygiene_for_url(development_url)


@pytest.fixture
def temporary_database() -> Iterator[TemporaryDatabase]:
    development_url = make_url(Settings().database_url.get_secret_value())
    with _temporary_database_resource(
        development_url,
        _temporary_database_name(),
    ) as database:
        yield database


def test_temporary_database_name_validation_is_strict() -> None:
    safe_name = "creativedeploy_migration_test_0123456789abcdef"
    safe_owner_role = "creativedeploy_migration_owner_0123456789abcdef"
    safe_token = "0123456789abcdef0123456789abcdef"  # gitleaks:allow
    _validate_temporary_database_name(
        safe_name,
        development_database="creativedeploy",
        maintenance_database=MAINTENANCE_DATABASE,
    )
    _validate_temporary_owner_role_name(safe_owner_role)
    _validate_ownership_token(safe_token)

    for unsafe_name, development_database, maintenance_database in (
        ("creativedeploy_migration_test_short", "creativedeploy", MAINTENANCE_DATABASE),
        ("creativedeploy_migration_test_0123456789abcdeg", "creativedeploy", MAINTENANCE_DATABASE),
        (
            "creativedeploy_migration_test_0123456789ABCDEF",
            "creativedeploy",
            MAINTENANCE_DATABASE,
        ),
        (
            "creativedeploy_migration_test_0123456789abcdef0123456789abcdef0",
            "creativedeploy",
            MAINTENANCE_DATABASE,
        ),
        ("other_prefix_0123456789abcdef", "creativedeploy", MAINTENANCE_DATABASE),
        (safe_name, safe_name, MAINTENANCE_DATABASE),
        (safe_name, "creativedeploy", safe_name),
    ):
        with pytest.raises(AssertionError):
            _validate_temporary_database_name(
                unsafe_name,
                development_database=development_database,
                maintenance_database=maintenance_database,
            )

    for unsafe_owner_role in (
        "creativedeploy_migration_owner_short",
        "creativedeploy_migration_owner_0123456789abcdeg",
        "creativedeploy_migration_owner_0123456789ABCDEF",
        "other_owner_0123456789abcdef",
    ):
        with pytest.raises(AssertionError):
            _validate_temporary_owner_role_name(unsafe_owner_role)

    for unsafe_token in (
        "short",
        "0123456789abcdef0123456789abcdeg",
        "0123456789ABCDEF0123456789ABCDEF",
        "0123456789abcdef0123456789abcdef0",
    ):
        with pytest.raises(AssertionError):
            _validate_ownership_token(unsafe_token)


def test_temporary_database_normal_success_is_cleaned() -> None:
    development_url = make_url(Settings().database_url.get_secret_value())
    temporary_database = _temporary_database_name()
    ownership = _temporary_database_ownership(temporary_database)

    with _temporary_database_resource(
        development_url,
        temporary_database,
        ownership=ownership,
    ) as database:
        assert database.name == temporary_database
        assert database.owner_role == ownership.owner_role
        with psycopg.connect(
            **_connection_kwargs(development_url, MAINTENANCE_DATABASE),
            autocommit=True,
        ) as maintenance_connection:
            assert _database_exists(maintenance_connection, temporary_database)
            assert _role_ownership_is_proven(maintenance_connection, ownership)
            assert _database_ownership_is_proven(
                maintenance_connection,
                ownership,
                development_database=development_url.database or "",
                create_returned_duplicate=False,
            )

    _assert_exact_temporary_resources_were_removed(development_url, ownership)


def test_overlapping_temporary_database_resources_clean_up_independently() -> None:
    development_url = make_url(Settings().database_url.get_secret_value())
    development_database = development_url.database
    assert development_database is not None
    database_name_a = _temporary_database_name()
    database_name_b = _temporary_database_name()
    ownership_a = _temporary_database_ownership(database_name_a)
    ownership_b = _temporary_database_ownership(database_name_b)
    resource_a = _temporary_database_resource(
        development_url,
        database_name_a,
        ownership=ownership_a,
    )
    resource_b = _temporary_database_resource(
        development_url,
        database_name_b,
        ownership=ownership_b,
    )
    resource_a_entered = False
    resource_b_entered = False
    resource_a_teardown_succeeded = False
    resource_b_teardown_succeeded = False
    database_b_connection: psycopg.Connection[tuple[Any, ...]] | None = None

    try:
        database_a = resource_a.__enter__()
        resource_a_entered = True
        database_b = resource_b.__enter__()
        resource_b_entered = True
        assert database_a.name != database_b.name
        assert database_a.owner_role != database_b.owner_role
        assert ownership_a.ownership_token != ownership_b.ownership_token
        assert _ownership_marker(ownership_a.ownership_token) != _ownership_marker(
            ownership_b.ownership_token
        )

        with psycopg.connect(
            **_connection_kwargs(development_url, MAINTENANCE_DATABASE),
            autocommit=True,
        ) as maintenance_connection:
            assert _database_exists(maintenance_connection, database_a.name)
            assert _database_exists(maintenance_connection, database_b.name)
            assert _role_ownership_is_proven(maintenance_connection, ownership_a)
            assert _role_ownership_is_proven(maintenance_connection, ownership_b)
            assert _database_ownership_is_proven(
                maintenance_connection,
                ownership_a,
                development_database=development_database,
                create_returned_duplicate=False,
            )
            assert _database_ownership_is_proven(
                maintenance_connection,
                ownership_b,
                development_database=development_database,
                create_returned_duplicate=False,
            )

        database_b_connection = psycopg.connect(
            **_connection_kwargs(development_url, database_b.name),
            autocommit=True,
        )
        database_b_backend_pid = database_b_connection.execute("SELECT pg_backend_pid()").fetchone()
        assert database_b_backend_pid is not None

        resource_a_entered = False
        resource_a.__exit__(None, None, None)
        resource_a_teardown_succeeded = True

        with psycopg.connect(
            **_connection_kwargs(development_url, MAINTENANCE_DATABASE),
            autocommit=True,
        ) as maintenance_connection:
            assert not _database_exists(maintenance_connection, database_a.name)
            assert _owner_role_state(maintenance_connection, ownership_a.owner_role) is None
            assert _database_exists(maintenance_connection, database_b.name)
            assert _role_ownership_is_proven(maintenance_connection, ownership_b)
            assert _database_ownership_is_proven(
                maintenance_connection,
                ownership_b,
                development_database=development_database,
                create_returned_duplicate=False,
            )
        assert database_b_connection.execute("SELECT 1").fetchone() == (1,)
        assert database_b_connection.execute("SELECT pg_backend_pid()").fetchone() == (
            database_b_backend_pid
        )

        resource_b_entered = False
        resource_b.__exit__(None, None, None)
        resource_b_teardown_succeeded = True
    finally:
        if database_b_connection is not None:
            database_b_connection.close()
        if resource_b_entered:
            resource_b_entered = False
            resource_b.__exit__(None, None, None)
        if resource_a_entered:
            resource_a_entered = False
            resource_a.__exit__(None, None, None)

    assert resource_a_teardown_succeeded is True
    assert resource_b_teardown_succeeded is True
    _assert_exact_temporary_resources_were_removed(development_url, ownership_a)
    _assert_exact_temporary_resources_were_removed(development_url, ownership_b)
    with psycopg.connect(
        **_connection_kwargs(development_url, MAINTENANCE_DATABASE),
        autocommit=True,
    ) as maintenance_connection:
        _assert_global_database_hygiene(
            maintenance_connection,
            development_database=development_database,
        )
        assert _temporary_resource_residuals(maintenance_connection) == ((), ())


def test_global_hygiene_audit_detects_real_orphan_without_deleting_it() -> None:
    development_url = make_url(Settings().database_url.get_secret_value())
    development_database = development_url.database
    assert development_database is not None
    orphan_database = _temporary_database_name()
    orphan_ownership = _temporary_database_ownership(orphan_database)

    try:
        with psycopg.connect(
            **_connection_kwargs(development_url, MAINTENANCE_DATABASE),
            autocommit=True,
        ) as maintenance_connection:
            _assert_global_database_hygiene(
                maintenance_connection,
                development_database=development_database,
            )
            _claim_owner_role(
                maintenance_connection,
                orphan_ownership,
                development_database=development_database,
            )
            _create_database(
                maintenance_connection,
                orphan_ownership,
                development_database,
            )

            with pytest.raises(
                AssertionError,
                match="GLOBAL_HYGIENE_AUDIT_FAILED",
            ) as audit_error:
                _assert_global_database_hygiene(
                    maintenance_connection,
                    development_database=development_database,
                )

            audit_message = str(audit_error.value)
            assert "database residual count=1" in audit_message
            assert "role residual count=1" in audit_message
            assert orphan_database in audit_message
            assert orphan_ownership.owner_role in audit_message
            assert orphan_ownership.ownership_token not in audit_message
            assert development_url.render_as_string(hide_password=False) not in audit_message
            if development_url.password is not None:
                assert development_url.password not in audit_message
            assert _database_ownership_is_proven(
                maintenance_connection,
                orphan_ownership,
                development_database=development_database,
                create_returned_duplicate=False,
            )
            assert _role_ownership_is_proven(
                maintenance_connection,
                orphan_ownership,
            )
    finally:
        with psycopg.connect(
            **_connection_kwargs(development_url, MAINTENANCE_DATABASE),
            autocommit=True,
        ) as maintenance_connection:
            if _database_ownership_is_proven(
                maintenance_connection,
                orphan_ownership,
                development_database=development_database,
                create_returned_duplicate=False,
            ):
                _drop_database(
                    maintenance_connection,
                    orphan_ownership,
                    development_database,
                    False,
                )
            _drop_owner_role(
                maintenance_connection,
                orphan_ownership,
                development_database=development_database,
            )

    _assert_exact_temporary_resources_were_removed(development_url, orphan_ownership)
    with psycopg.connect(
        **_connection_kwargs(development_url, MAINTENANCE_DATABASE),
        autocommit=True,
    ) as maintenance_connection:
        _assert_global_database_hygiene(
            maintenance_connection,
            development_database=development_database,
        )
        assert _temporary_resource_residuals(maintenance_connection) == ((), ())


def test_temporary_database_definite_create_failure_is_idempotently_cleaned() -> None:
    development_url = make_url(Settings().database_url.get_secret_value())
    temporary_database = _temporary_database_name()
    ownership = _temporary_database_ownership(temporary_database)
    drop_attempted = False

    def fail_before_create(
        connection: psycopg.Connection[tuple[Any, ...]],
        identity: TemporaryDatabaseOwnership,
    ) -> None:
        assert identity == ownership
        assert _role_ownership_is_proven(connection, identity)
        assert not _database_exists(connection, identity.database_name)
        raise SyntheticCreateFailure("synthetic failure before CREATE")

    def reject_unnecessary_drop(
        connection: psycopg.Connection[tuple[Any, ...]],
        identity: TemporaryDatabaseOwnership,
        development_database: str,
        create_returned_duplicate: bool,
    ) -> None:
        nonlocal drop_attempted
        drop_attempted = True
        pytest.fail("DROP must not run for an absent database.")

    with (
        pytest.raises(SyntheticCreateFailure, match="before CREATE"),
        _temporary_database_resource(
            development_url,
            temporary_database,
            ownership=ownership,
            create_database=fail_before_create,
            drop_database=reject_unnecessary_drop,
        ),
    ):
        pytest.fail("A definite CREATE failure must not yield a database")

    assert drop_attempted is False
    _assert_exact_temporary_resources_were_removed(development_url, ownership)


def test_temporary_database_uncertain_create_success_is_cleaned() -> None:
    development_url = make_url(Settings().database_url.get_secret_value())
    development_database = development_url.database
    assert development_database is not None
    temporary_database = _temporary_database_name()
    ownership = _temporary_database_ownership(temporary_database)
    server_side_create_observed = False

    def create_then_lose_confirmation(
        connection: psycopg.Connection[tuple[Any, ...]],
        identity: TemporaryDatabaseOwnership,
    ) -> None:
        nonlocal server_side_create_observed
        _create_database(connection, identity, development_database)
        assert _database_ownership_is_proven(
            connection,
            identity,
            development_database=development_database,
            create_returned_duplicate=False,
        )
        server_side_create_observed = True
        raise SyntheticCreateFailure("synthetic confirmation loss after CREATE")

    with (
        pytest.raises(SyntheticCreateFailure, match="confirmation loss after CREATE"),
        _temporary_database_resource(
            development_url,
            temporary_database,
            ownership=ownership,
            create_database=create_then_lose_confirmation,
        ),
    ):
        pytest.fail("An uncertain CREATE result must not yield a database")

    assert server_side_create_observed is True
    _assert_exact_temporary_resources_were_removed(development_url, ownership)


def test_temporary_database_preexisting_name_is_not_owned_or_deleted() -> None:
    development_url = make_url(Settings().database_url.get_secret_value())
    development_database = development_url.database
    assert development_database is not None
    temporary_database = _temporary_database_name()
    _validate_temporary_database_name(
        temporary_database,
        development_database=development_database,
        maintenance_database=MAINTENANCE_DATABASE,
    )
    actor_ownership = _temporary_database_ownership(temporary_database)
    fixture_ownership = _temporary_database_ownership(temporary_database)
    actor_connection: psycopg.Connection[tuple[Any, ...]] | None = None

    with psycopg.connect(
        **_connection_kwargs(development_url, MAINTENANCE_DATABASE),
        autocommit=True,
    ) as maintenance_connection:
        assert not _database_exists(maintenance_connection, temporary_database)
        _claim_owner_role(
            maintenance_connection,
            actor_ownership,
            development_database=development_database,
        )
        _create_database(
            maintenance_connection,
            actor_ownership,
            development_database,
        )
        assert _database_exists(maintenance_connection, temporary_database)
    actor_connection = psycopg.connect(
        **_connection_kwargs(development_url, temporary_database),
        autocommit=True,
    )

    try:
        with (
            pytest.raises(
                AssertionError,
                match="existed before this test's CREATE attempt",
            ),
            _temporary_database_resource(
                development_url,
                temporary_database,
                ownership=fixture_ownership,
            ),
        ):
            pytest.fail("A pre-existing database must be rejected before fixture yield")

        assert actor_connection.execute("SELECT 1").fetchone() == (1,)
        with psycopg.connect(
            **_connection_kwargs(development_url, MAINTENANCE_DATABASE),
            autocommit=True,
        ) as maintenance_connection:
            assert _database_exists(maintenance_connection, temporary_database)
            assert _database_ownership_is_proven(
                maintenance_connection,
                actor_ownership,
                development_database=development_database,
                create_returned_duplicate=False,
            )
            assert (
                _owner_role_state(
                    maintenance_connection,
                    fixture_ownership.owner_role,
                )
                is None
            )
    finally:
        actor_connection.close()
        with psycopg.connect(
            **_connection_kwargs(development_url, MAINTENANCE_DATABASE),
            autocommit=True,
        ) as maintenance_connection:
            if _database_exists(maintenance_connection, temporary_database):
                _drop_database(
                    maintenance_connection,
                    actor_ownership,
                    development_database,
                    False,
                )
            _drop_owner_role(
                maintenance_connection,
                actor_ownership,
                development_database=development_database,
            )

    _assert_exact_temporary_resources_were_removed(development_url, actor_ownership)
    _assert_exact_temporary_resources_were_removed(development_url, fixture_ownership)


def test_temporary_database_toctou_duplicate_preserves_concurrent_actor() -> None:
    development_url = make_url(Settings().database_url.get_secret_value())
    development_database = development_url.database
    assert development_database is not None
    temporary_database = _temporary_database_name()
    fixture_ownership = _temporary_database_ownership(temporary_database)
    actor_ownership = _temporary_database_ownership(temporary_database)
    actor_connection: psycopg.Connection[tuple[Any, ...]] | None = None

    def concurrent_create_before_fixture_create(
        connection: psycopg.Connection[tuple[Any, ...]],
        identity: TemporaryDatabaseOwnership,
    ) -> None:
        nonlocal actor_connection
        assert identity == fixture_ownership
        assert not _database_exists(connection, identity.database_name)
        _claim_owner_role(
            connection,
            actor_ownership,
            development_database=development_database,
        )
        _create_database(connection, actor_ownership, development_database)
        actor_connection = psycopg.connect(
            **_connection_kwargs(development_url, temporary_database),
            autocommit=True,
        )
        _create_database(connection, identity, development_database)

    try:
        with (
            pytest.raises(psycopg.errors.DuplicateDatabase) as duplicate_error,
            _temporary_database_resource(
                development_url,
                temporary_database,
                ownership=fixture_ownership,
                create_database=concurrent_create_before_fixture_create,
            ),
        ):
            pytest.fail("A 42P04 CREATE result must not yield fixture ownership.")

        assert duplicate_error.value.sqlstate == DUPLICATE_DATABASE_SQLSTATE
        assert actor_connection is not None
        assert actor_connection.execute("SELECT 1").fetchone() == (1,)
        with psycopg.connect(
            **_connection_kwargs(development_url, MAINTENANCE_DATABASE),
            autocommit=True,
        ) as maintenance_connection:
            assert _database_ownership_is_proven(
                maintenance_connection,
                actor_ownership,
                development_database=development_database,
                create_returned_duplicate=False,
            )
            assert (
                _owner_role_state(
                    maintenance_connection,
                    fixture_ownership.owner_role,
                )
                is None
            )
    finally:
        if actor_connection is not None:
            actor_connection.close()
        with psycopg.connect(
            **_connection_kwargs(development_url, MAINTENANCE_DATABASE),
            autocommit=True,
        ) as maintenance_connection:
            if _database_ownership_is_proven(
                maintenance_connection,
                actor_ownership,
                development_database=development_database,
                create_returned_duplicate=False,
            ):
                _drop_database(
                    maintenance_connection,
                    actor_ownership,
                    development_database,
                    False,
                )
            _drop_owner_role(
                maintenance_connection,
                actor_ownership,
                development_database=development_database,
            )

    _assert_exact_temporary_resources_were_removed(development_url, actor_ownership)
    _assert_exact_temporary_resources_were_removed(development_url, fixture_ownership)


@pytest.mark.parametrize("marker_change", ["missing", "mismatched"])
def test_temporary_database_owner_marker_change_refuses_cleanup(
    marker_change: str,
) -> None:
    development_url = make_url(Settings().database_url.get_secret_value())
    development_database = development_url.database
    assert development_database is not None
    temporary_database = _temporary_database_name()
    ownership = _temporary_database_ownership(temporary_database)
    database_connection: psycopg.Connection[tuple[Any, ...]] | None = None

    def change_owner_marker(
        connection: psycopg.Connection[tuple[Any, ...]],
        identity: TemporaryDatabaseOwnership,
    ) -> None:
        if marker_change == "missing":
            changed_marker = None
        else:
            replacement_prefix = "0" if identity.ownership_token[0] != "0" else "1"
            changed_marker = _ownership_marker(
                f"{replacement_prefix}{identity.ownership_token[1:]}"
            )
        _set_owner_role_marker(
            connection,
            identity.owner_role,
            changed_marker,
        )

    try:
        with (
            pytest.raises(OwnershipNotProven, match="OWNERSHIP_NOT_PROVEN"),
            _temporary_database_resource(
                development_url,
                temporary_database,
                ownership=ownership,
                before_cleanup=change_owner_marker,
            ),
        ):
            database_connection = psycopg.connect(
                **_connection_kwargs(development_url, temporary_database),
                autocommit=True,
            )

        assert database_connection is not None
        assert database_connection.execute("SELECT 1").fetchone() == (1,)
        with psycopg.connect(
            **_connection_kwargs(development_url, MAINTENANCE_DATABASE),
            autocommit=True,
        ) as maintenance_connection:
            assert _database_exists(maintenance_connection, temporary_database)
            assert not _database_ownership_is_proven(
                maintenance_connection,
                ownership,
                development_database=development_database,
                create_returned_duplicate=False,
            )
            assert (
                _owner_role_state(
                    maintenance_connection,
                    ownership.owner_role,
                )
                is not None
            )
    finally:
        if database_connection is not None:
            database_connection.close()
        with psycopg.connect(
            **_connection_kwargs(development_url, MAINTENANCE_DATABASE),
            autocommit=True,
        ) as maintenance_connection:
            if _owner_role_state(maintenance_connection, ownership.owner_role) is not None:
                _set_owner_role_marker(
                    maintenance_connection,
                    ownership.owner_role,
                    _ownership_marker(ownership.ownership_token),
                )
            if _database_ownership_is_proven(
                maintenance_connection,
                ownership,
                development_database=development_database,
                create_returned_duplicate=False,
            ):
                _drop_database(
                    maintenance_connection,
                    ownership,
                    development_database,
                    False,
                )
            _drop_owner_role(
                maintenance_connection,
                ownership,
                development_database=development_database,
            )

    _assert_exact_temporary_resources_were_removed(development_url, ownership)


def test_temporary_database_owner_change_before_drop_refuses_cleanup() -> None:
    development_url = make_url(Settings().database_url.get_secret_value())
    development_database = development_url.database
    assert development_database is not None
    temporary_database = _temporary_database_name()
    fixture_ownership = _temporary_database_ownership(temporary_database)
    actor_ownership = _temporary_database_ownership(temporary_database)
    database_connection: psycopg.Connection[tuple[Any, ...]] | None = None

    def change_database_owner(
        connection: psycopg.Connection[tuple[Any, ...]],
        identity: TemporaryDatabaseOwnership,
    ) -> None:
        assert identity == fixture_ownership
        connection.execute(
            sql.SQL("ALTER DATABASE {} OWNER TO {}").format(
                sql.Identifier(identity.database_name),
                sql.Identifier(actor_ownership.owner_role),
            )
        )

    try:
        with (
            pytest.raises(OwnershipNotProven, match="OWNERSHIP_NOT_PROVEN"),
            _temporary_database_resource(
                development_url,
                temporary_database,
                ownership=fixture_ownership,
                before_cleanup=change_database_owner,
            ),
        ):
            with psycopg.connect(
                **_connection_kwargs(development_url, MAINTENANCE_DATABASE),
                autocommit=True,
            ) as maintenance_connection:
                _claim_owner_role(
                    maintenance_connection,
                    actor_ownership,
                    development_database=development_database,
                )
            database_connection = psycopg.connect(
                **_connection_kwargs(development_url, temporary_database),
                autocommit=True,
            )

        assert database_connection is not None
        assert database_connection.execute("SELECT 1").fetchone() == (1,)
        with psycopg.connect(
            **_connection_kwargs(development_url, MAINTENANCE_DATABASE),
            autocommit=True,
        ) as maintenance_connection:
            assert _database_ownership_is_proven(
                maintenance_connection,
                actor_ownership,
                development_database=development_database,
                create_returned_duplicate=False,
            )
            assert (
                _owner_role_state(
                    maintenance_connection,
                    fixture_ownership.owner_role,
                )
                is not None
            )
    finally:
        if database_connection is not None:
            database_connection.close()
        with psycopg.connect(
            **_connection_kwargs(development_url, MAINTENANCE_DATABASE),
            autocommit=True,
        ) as maintenance_connection:
            if _database_ownership_is_proven(
                maintenance_connection,
                actor_ownership,
                development_database=development_database,
                create_returned_duplicate=False,
            ):
                _drop_database(
                    maintenance_connection,
                    actor_ownership,
                    development_database,
                    False,
                )
            _drop_owner_role(
                maintenance_connection,
                actor_ownership,
                development_database=development_database,
            )
            _drop_owner_role(
                maintenance_connection,
                fixture_ownership,
                development_database=development_database,
            )

    _assert_exact_temporary_resources_were_removed(development_url, actor_ownership)
    _assert_exact_temporary_resources_were_removed(development_url, fixture_ownership)


def test_temporary_database_owner_role_collision_is_not_claimed_or_dropped() -> None:
    development_url = make_url(Settings().database_url.get_secret_value())
    development_database = development_url.database
    assert development_database is not None
    temporary_database = _temporary_database_name()
    actor_ownership = _temporary_database_ownership(temporary_database)
    fixture_ownership = TemporaryDatabaseOwnership(
        database_name=temporary_database,
        owner_role=actor_ownership.owner_role,
        ownership_token=secrets.token_hex(16),
    )
    database_create_attempted = False

    def reject_database_create(
        connection: psycopg.Connection[tuple[Any, ...]],
        identity: TemporaryDatabaseOwnership,
    ) -> None:
        nonlocal database_create_attempted
        database_create_attempted = True
        pytest.fail("Database CREATE must not run after an owner-role collision.")

    with psycopg.connect(
        **_connection_kwargs(development_url, MAINTENANCE_DATABASE),
        autocommit=True,
    ) as maintenance_connection:
        _claim_owner_role(
            maintenance_connection,
            actor_ownership,
            development_database=development_database,
        )

    try:
        with (
            pytest.raises(OwnershipNotProven, match="already exists"),
            _temporary_database_resource(
                development_url,
                temporary_database,
                ownership=fixture_ownership,
                create_database=reject_database_create,
            ),
        ):
            pytest.fail("An owner-role collision must prevent fixture yield.")

        assert database_create_attempted is False
        with psycopg.connect(
            **_connection_kwargs(development_url, MAINTENANCE_DATABASE),
            autocommit=True,
        ) as maintenance_connection:
            assert _role_ownership_is_proven(
                maintenance_connection,
                actor_ownership,
            )
            assert not _database_exists(
                maintenance_connection,
                temporary_database,
            )
    finally:
        with psycopg.connect(
            **_connection_kwargs(development_url, MAINTENANCE_DATABASE),
            autocommit=True,
        ) as maintenance_connection:
            _drop_owner_role(
                maintenance_connection,
                actor_ownership,
                development_database=development_database,
            )
            assert not _database_exists(
                maintenance_connection,
                temporary_database,
            )

    _assert_exact_temporary_resources_were_removed(development_url, actor_ownership)
    _assert_exact_temporary_resources_were_removed(development_url, fixture_ownership)


def test_alembic_subprocess_failure_redacts_all_database_identifiers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_url = URL.create(
        "postgresql+psycopg",
        username="review user",
        password="review/password",
        host="127.0.0.1",
        database="review_database",
    )
    rendered_url = test_url.render_as_string(hide_password=False)
    sensitive_values = (
        "review user",
        "review%20user",
        "review+user",
        "review/password",
        "review%2Fpassword",
        "review_database",
        rendered_url,
    )
    result = subprocess.CompletedProcess(
        args=ALEMBIC_COMMAND,
        returncode=7,
        stdout=(
            "connection refused; user=review user; encoded-user=review%20user; "
            "plus-user=review+user; password=review/password; "
            "encoded-password=review%2Fpassword; database=review_database"
        ),
        stderr=f"migration configuration rejected; url={rendered_url}",
    )
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: result)

    with pytest.raises(AssertionError) as error:
        _run_alembic(test_url, "current")

    message = str(error.value)
    assert "Alembic current failed with exit code 7." in message
    assert "connection refused" in message
    assert "migration configuration rejected" in message
    assert "[REDACTED]" in message
    for sensitive_value in sensitive_values:
        assert sensitive_value.lower() not in message.lower()


def test_alembic_subprocess_timeout_redacts_all_database_identifiers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_url = URL.create(
        "postgresql+psycopg",
        username="review user",
        password="review/password",
        host="127.0.0.1",
        database="review_database",
    )
    rendered_url = test_url.render_as_string(hide_password=False)
    sensitive_values = (
        "review user",
        "review%20user",
        "review+user",
        "review/password",
        "review%2Fpassword",
        "review_database",
        rendered_url,
    )

    def raise_timeout(*args: object, **kwargs: object) -> None:
        assert kwargs["timeout"] == ALEMBIC_TIMEOUT_SECONDS
        raise subprocess.TimeoutExpired(
            cmd=ALEMBIC_COMMAND,
            timeout=ALEMBIC_TIMEOUT_SECONDS,
            output=("connection timed out for review user via review%20user with review/password"),
            stderr=(
                f"database review_database unavailable; url={rendered_url}; "
                "encoded-password=review%2Fpassword; plus-user=review+user"
            ),
        )

    monkeypatch.setattr(subprocess, "run", raise_timeout)

    with pytest.raises(AssertionError) as error:
        _run_alembic(test_url, "current")

    message = str(error.value)
    assert "Alembic current timed out after 120 seconds." in message
    assert "connection timed out" in message
    assert "database" in message
    assert "[REDACTED]" in message
    for sensitive_value in sensitive_values:
        assert sensitive_value.lower() not in message.lower()


def _insert_project(
    connection: psycopg.Connection[tuple[Any, ...]],
    *,
    owner: str = "owner",
    title: str = "Project",
    description: str | None = None,
    target_style: str = "cel_shading",
    planning_mode: str = "planning_only_demo",
    status: str = "DRAFT",
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> uuid.UUID:
    project_id = uuid.uuid4()
    created = created_at or datetime.now(UTC)
    updated = updated_at or created
    with connection.transaction():
        connection.execute(
            """
            INSERT INTO paint_projects (
                id, owner_principal_id, title, description,
                requested_target_style, planning_mode, status,
                created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                project_id,
                owner,
                title,
                description,
                target_style,
                planning_mode,
                status,
                created,
                updated,
            ),
        )
    return project_id


def _project_parameters(**overrides: object) -> tuple[object, ...]:
    created = datetime.now(UTC)
    values: dict[str, object] = {
        "id": uuid.uuid4(),
        "owner": "owner",
        "title": "Project",
        "description": None,
        "target_style": "cel_shading",
        "planning_mode": "planning_only_demo",
        "status": "DRAFT",
        "created_at": created,
        "updated_at": created,
    }
    values.update(overrides)
    return tuple(values[key] for key in values)


PROJECT_INSERT = """
    INSERT INTO paint_projects (
        id, owner_principal_id, title, description,
        requested_target_style, planning_mode, status,
        created_at, updated_at
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


def _event_parameters(
    default_project_id: uuid.UUID,
    **overrides: object,
) -> tuple[object, ...]:
    values: dict[str, object] = {
        "id": uuid.uuid4(),
        "project_id": default_project_id,
        "from_state": None,
        "to_state": "DRAFT",
        "event": "background_event",
        "actor_type": "system",
        "actor_principal_id": "system",
        "actor_display_name_snapshot": None,
        "reason": None,
        "correlation_id": uuid.uuid4(),
        "event_metadata": Jsonb({}),
    }
    values.update(overrides)
    return tuple(values[key] for key in values)


EVENT_INSERT = """
    INSERT INTO state_transition_events (
        id, project_id, from_state, to_state, event, actor_type,
        actor_principal_id, actor_display_name_snapshot, reason,
        correlation_id, event_metadata
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


def _idempotency_parameters(**overrides: object) -> tuple[object, ...]:
    created = datetime.now(UTC)
    values: dict[str, object] = {
        "id": uuid.uuid4(),
        "scope_key": "principal:owner:command:create_paint_project",
        "principal_id": "owner",
        "command_type": "create_paint_project",
        "idempotency_key": uuid.uuid4(),
        "payload_hash": "a" * 64,
        "execution_status": "completed",
        "resource_type": "paint_project",
        "resource_id": uuid.uuid4(),
        "http_status": 201,
        "response_snapshot": Jsonb({"status": "DRAFT"}),
        "created_at": created,
        "expires_at": created + timedelta(hours=24),
    }
    values.update(overrides)
    return tuple(values[key] for key in values)


IDEMPOTENCY_INSERT = """
    INSERT INTO command_idempotency_records (
        id, scope_key, principal_id, command_type, idempotency_key,
        payload_hash, execution_status, resource_type, resource_id,
        http_status, response_snapshot, created_at, expires_at
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


def _assert_schema(connection: psycopg.Connection[tuple[Any, ...]]) -> None:
    tables = {
        row[0]
        for row in connection.execute(
            """
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'public'
            """
        ).fetchall()
    }
    assert tables == CURRENT_BUSINESS_TABLES | {"alembic_version"}

    for table, expected_columns in EXPECTED_COLUMNS.items():
        columns = tuple(
            row[0]
            for row in connection.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s
                ORDER BY ordinal_position
                """,
                (table,),
            ).fetchall()
        )
        assert columns == expected_columns

    state_nullability = dict(
        connection.execute(
            """
            SELECT column_name, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'state_transition_events'
            """
        ).fetchall()
    )
    assert state_nullability["actor_display_name_snapshot"] == "YES"
    assert state_nullability["reason"] == "YES"
    assert "agent_run_id" not in state_nullability

    index_definitions = [
        row[0]
        for row in connection.execute(
            """
            SELECT indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
            """
        ).fetchall()
    ]
    assert not any("event_metadata" in definition for definition in index_definitions)


def _assert_paint_project_constraints(
    connection: psycopg.Connection[tuple[Any, ...]],
) -> uuid.UUID:
    valid_project_id = _insert_project(
        connection,
        owner="o" * 128,
        title="T" * 80,
        description="D" * 500,
        status="DRAFT",
    )

    for status in EXPECTED_WORKFLOW_STATES:
        _insert_project(connection, status=status)

    rejection_cases = (
        (
            "blank title",
            {"title": ""},
            "23514",
            "ck_paint_projects_title_not_blank",
        ),
        (
            "whitespace title",
            {"title": "   "},
            "23514",
            "ck_paint_projects_title_normalized",
        ),
        ("title over 80 characters", {"title": "T" * 81}, "22001", None),
        (
            "untrimmed title",
            {"title": " title"},
            "23514",
            "ck_paint_projects_title_normalized",
        ),
        (
            "empty description",
            {"description": ""},
            "23514",
            "ck_paint_projects_description_normalized",
        ),
        (
            "whitespace description",
            {"description": "   "},
            "23514",
            "ck_paint_projects_description_normalized",
        ),
        ("description over 500 characters", {"description": "D" * 501}, "22001", None),
        (
            "untrimmed description",
            {"description": "description "},
            "23514",
            "ck_paint_projects_description_normalized",
        ),
        (
            "blank owner",
            {"owner": ""},
            "23514",
            "ck_paint_projects_owner_principal_id_normalized",
        ),
        (
            "whitespace owner",
            {"owner": "   "},
            "23514",
            "ck_paint_projects_owner_principal_id_normalized",
        ),
        (
            "untrimmed owner",
            {"owner": "owner "},
            "23514",
            "ck_paint_projects_owner_principal_id_normalized",
        ),
        ("owner over 128 characters", {"owner": "o" * 129}, "22001", None),
        (
            "unapproved target style",
            {"target_style": "other_style"},
            "23514",
            "ck_paint_projects_requested_target_style_allowed",
        ),
        (
            "unapproved planning mode",
            {"planning_mode": "other_mode"},
            "23514",
            "ck_paint_projects_planning_mode_allowed",
        ),
        (
            "unknown workflow state",
            {"status": "UNKNOWN"},
            "23514",
            "ck_paint_projects_status_allowed",
        ),
    )
    for rejection_cases_item in rejection_cases:
        case_label, overrides, expected_sqlstate, expected_constraint_name = rejection_cases_item
        _expect_rejection(
            connection,
            PROJECT_INSERT,
            _project_parameters(**overrides),
            case_label=case_label,
            expected_sqlstate=expected_sqlstate,
            expected_constraint_name=expected_constraint_name,
        )

    created = datetime.now(UTC)
    _expect_rejection(
        connection,
        PROJECT_INSERT,
        _project_parameters(
            created_at=created,
            updated_at=created - timedelta(seconds=1),
        ),
        case_label="updated_at before created_at",
        expected_sqlstate="23514",
        expected_constraint_name="ck_paint_projects_updated_at_not_before_created_at",
    )
    return valid_project_id


def _assert_event_constraints(
    connection: psycopg.Connection[tuple[Any, ...]],
    project_id: uuid.UUID,
) -> None:
    with connection.transaction():
        connection.execute(
            EVENT_INSERT,
            _event_parameters(
                project_id,
                event="create_project",
                actor_type="user",
                actor_principal_id="human-owner",
                actor_display_name_snapshot="界" * 200,
                reason="project_created",
            ),
        )
        connection.execute(
            EVENT_INSERT,
            _event_parameters(
                project_id,
                event="a" * 64,
                reason="r" * 128,
                event_metadata=Jsonb({"kind": "object"}),
            ),
        )
        connection.execute(
            EVENT_INSERT,
            _event_parameters(
                project_id,
                actor_type="worker",
                actor_display_name_snapshot=None,
                reason=None,
            ),
        )

    for metadata in ([], "text", 1, True, None):
        _expect_rejection(
            connection,
            EVENT_INSERT,
            _event_parameters(project_id, event_metadata=Jsonb(metadata)),
            case_label=f"event_metadata rejects {type(metadata).__name__}",
            expected_sqlstate="23514",
            expected_constraint_name="ck_state_transition_events_event_metadata_is_object",
        )

    rejection_cases = (
        (
            "event references missing project",
            {"project_id": uuid.uuid4()},
            "23503",
            "fk_state_transition_events_project_id_paint_projects",
        ),
        (
            "unknown from_state",
            {"from_state": "UNKNOWN"},
            "23514",
            "ck_state_transition_events_from_state_allowed",
        ),
        (
            "unknown to_state",
            {"to_state": "UNKNOWN"},
            "23514",
            "ck_state_transition_events_to_state_allowed",
        ),
        (
            "event token contains space",
            {"event": "invalid event"},
            "23514",
            "ck_state_transition_events_event_format",
        ),
        (
            "event token contains hyphen",
            {"event": "invalid-event"},
            "23514",
            "ck_state_transition_events_event_format",
        ),
        ("event over 64 characters", {"event": "e" * 65}, "22001", None),
        (
            "actor type contains space",
            {"actor_type": "invalid actor"},
            "23514",
            "ck_state_transition_events_actor_type_allowed",
        ),
        (
            "unapproved actor type",
            {"actor_type": "agent"},
            "23514",
            "ck_state_transition_events_actor_type_allowed",
        ),
        (
            "blank actor principal",
            {"actor_principal_id": ""},
            "23514",
            "ck_state_transition_events_actor_principal_id_normalized",
        ),
        (
            "whitespace actor principal",
            {"actor_principal_id": "   "},
            "23514",
            "ck_state_transition_events_actor_principal_id_normalized",
        ),
        (
            "untrimmed actor principal",
            {"actor_principal_id": "system "},
            "23514",
            "ck_state_transition_events_actor_principal_id_normalized",
        ),
        (
            "empty display snapshot",
            {"actor_display_name_snapshot": ""},
            "23514",
            "ck_state_transition_events_actor_display_snapshot_normalized",
        ),
        (
            "whitespace display snapshot",
            {"actor_display_name_snapshot": "   "},
            "23514",
            "ck_state_transition_events_actor_display_snapshot_normalized",
        ),
        (
            "untrimmed display snapshot",
            {"actor_display_name_snapshot": "Display "},
            "23514",
            "ck_state_transition_events_actor_display_snapshot_normalized",
        ),
        (
            "display snapshot over 200 Unicode characters",
            {"actor_display_name_snapshot": "界" * 201},
            "22001",
            None,
        ),
        (
            "user actor without display snapshot",
            {"actor_type": "user", "actor_display_name_snapshot": None},
            "23514",
            "ck_state_transition_events_user_display_name_required",
        ),
        (
            "empty reason token",
            {"reason": ""},
            "23514",
            "ck_state_transition_events_reason_format",
        ),
        (
            "reason token contains space",
            {"reason": "invalid reason"},
            "23514",
            "ck_state_transition_events_reason_format",
        ),
        (
            "reason token contains uppercase",
            {"reason": "Invalid"},
            "23514",
            "ck_state_transition_events_reason_format",
        ),
        (
            "reason token contains hyphen",
            {"reason": "invalid-reason"},
            "23514",
            "ck_state_transition_events_reason_format",
        ),
        ("reason over 128 characters", {"reason": "r" * 129}, "22001", None),
        (
            "create_project without reason",
            {
                "event": "create_project",
                "actor_type": "user",
                "actor_display_name_snapshot": "Human Owner",
                "reason": None,
            },
            "23514",
            "ck_state_transition_events_create_project_reason",
        ),
        (
            "create_project with wrong reason",
            {
                "event": "create_project",
                "actor_type": "user",
                "actor_display_name_snapshot": "Human Owner",
                "reason": "other_reason",
            },
            "23514",
            "ck_state_transition_events_create_project_reason",
        ),
    )
    for rejection_cases_item in rejection_cases:
        case_label, overrides, expected_sqlstate, expected_constraint_name = rejection_cases_item
        _expect_rejection(
            connection,
            EVENT_INSERT,
            _event_parameters(project_id, **overrides),
            case_label=case_label,
            expected_sqlstate=expected_sqlstate,
            expected_constraint_name=expected_constraint_name,
        )


def _assert_idempotency_constraints(
    connection: psycopg.Connection[tuple[Any, ...]],
) -> None:
    duplicate_key = uuid.uuid4()
    with connection.transaction():
        connection.execute(
            IDEMPOTENCY_INSERT,
            _idempotency_parameters(
                scope_key="s" * 512,
                principal_id="p" * 128,
                command_type="c" * 64,
                resource_type="r" * 64,
                idempotency_key=duplicate_key,
            ),
        )
        connection.execute(
            IDEMPOTENCY_INSERT,
            _idempotency_parameters(
                scope_key="different_scope",
                idempotency_key=duplicate_key,
            ),
        )
        connection.execute(
            IDEMPOTENCY_INSERT,
            _idempotency_parameters(
                execution_status="in_progress",
                resource_type=None,
                resource_id=None,
                http_status=None,
                response_snapshot=None,
            ),
        )
        connection.execute(
            IDEMPOTENCY_INSERT,
            _idempotency_parameters(http_status=100),
        )
        connection.execute(
            IDEMPOTENCY_INSERT,
            _idempotency_parameters(http_status=599),
        )

    _expect_rejection(
        connection,
        IDEMPOTENCY_INSERT,
        _idempotency_parameters(
            scope_key="s" * 512,
            idempotency_key=duplicate_key,
        ),
        case_label="duplicate scope and idempotency key",
        expected_sqlstate="23505",
        expected_constraint_name=("uq_command_idempotency_records_scope_key_idempotency_key"),
    )

    rejection_cases = (
        (
            "blank scope key",
            {"scope_key": ""},
            "23514",
            "ck_command_idempotency_records_scope_key_normalized",
        ),
        (
            "whitespace scope key",
            {"scope_key": "   "},
            "23514",
            "ck_command_idempotency_records_scope_key_normalized",
        ),
        (
            "untrimmed scope key",
            {"scope_key": "scope "},
            "23514",
            "ck_command_idempotency_records_scope_key_normalized",
        ),
        ("scope key over 512 characters", {"scope_key": "s" * 513}, "22001", None),
        (
            "blank principal id",
            {"principal_id": ""},
            "23514",
            "ck_command_idempotency_records_principal_id_normalized",
        ),
        (
            "whitespace principal id",
            {"principal_id": "   "},
            "23514",
            "ck_command_idempotency_records_principal_id_normalized",
        ),
        (
            "untrimmed principal id",
            {"principal_id": "owner "},
            "23514",
            "ck_command_idempotency_records_principal_id_normalized",
        ),
        ("principal id over 128 characters", {"principal_id": "p" * 129}, "22001", None),
        (
            "command token contains space",
            {"command_type": "invalid command"},
            "23514",
            "ck_command_idempotency_records_command_type_format",
        ),
        (
            "command token contains uppercase",
            {"command_type": "Invalid"},
            "23514",
            "ck_command_idempotency_records_command_type_format",
        ),
        (
            "command token contains hyphen",
            {"command_type": "invalid-command"},
            "23514",
            "ck_command_idempotency_records_command_type_format",
        ),
        ("command token over 64 characters", {"command_type": "c" * 65}, "22001", None),
        (
            "payload hash contains uppercase",
            {"payload_hash": "A" * 64},
            "23514",
            "ck_command_idempotency_records_payload_hash_format",
        ),
        (
            "payload hash has 63 characters",
            {"payload_hash": "a" * 63},
            "23514",
            "ck_command_idempotency_records_payload_hash_format",
        ),
        (
            "payload hash contains non-hex",
            {"payload_hash": "g" * 64},
            "23514",
            "ck_command_idempotency_records_payload_hash_format",
        ),
        ("payload hash has 65 characters", {"payload_hash": "a" * 65}, "22001", None),
        (
            "unapproved execution status",
            {"execution_status": "unknown"},
            "23514",
            "ck_command_idempotency_records_execution_status_allowed",
        ),
        (
            "resource token contains space",
            {"resource_type": "invalid resource"},
            "23514",
            "ck_command_idempotency_records_resource_type_format",
        ),
        ("resource token over 64 characters", {"resource_type": "r" * 65}, "22001", None),
        (
            "HTTP status below lower bound",
            {"http_status": 99},
            "23514",
            "ck_command_idempotency_records_http_status_valid",
        ),
        (
            "HTTP status above upper bound",
            {"http_status": 600},
            "23514",
            "ck_command_idempotency_records_http_status_valid",
        ),
        (
            "response snapshot array",
            {"response_snapshot": Jsonb([])},
            "23514",
            "ck_command_idempotency_records_response_snapshot_is_object",
        ),
        (
            "response snapshot string",
            {"response_snapshot": Jsonb("text")},
            "23514",
            "ck_command_idempotency_records_response_snapshot_is_object",
        ),
        (
            "response snapshot number",
            {"response_snapshot": Jsonb(1)},
            "23514",
            "ck_command_idempotency_records_response_snapshot_is_object",
        ),
        (
            "response snapshot boolean",
            {"response_snapshot": Jsonb(True)},
            "23514",
            "ck_command_idempotency_records_response_snapshot_is_object",
        ),
        (
            "response snapshot JSON null",
            {"response_snapshot": Jsonb(None)},
            "23514",
            "ck_command_idempotency_records_response_snapshot_is_object",
        ),
    )
    for rejection_cases_item in rejection_cases:
        case_label, overrides, expected_sqlstate, expected_constraint_name = rejection_cases_item
        _expect_rejection(
            connection,
            IDEMPOTENCY_INSERT,
            _idempotency_parameters(**overrides),
            case_label=case_label,
            expected_sqlstate=expected_sqlstate,
            expected_constraint_name=expected_constraint_name,
        )

    for field_name, missing_result in (
        ("resource_type", {"resource_type": None}),
        ("resource_id", {"resource_id": None}),
        ("http_status", {"http_status": None}),
        ("response_snapshot", {"response_snapshot": None}),
    ):
        _expect_rejection(
            connection,
            IDEMPOTENCY_INSERT,
            _idempotency_parameters(**missing_result),
            case_label=f"completed result without {field_name}",
            expected_sqlstate="23514",
            expected_constraint_name=(
                "ck_command_idempotency_records_result_matches_execution_status"
            ),
        )

    created = datetime.now(UTC)
    for case_label, expires_at in (
        ("expires_at equals created_at", created),
        ("expires_at before created_at", created - timedelta(seconds=1)),
    ):
        _expect_rejection(
            connection,
            IDEMPOTENCY_INSERT,
            _idempotency_parameters(
                created_at=created,
                expires_at=expires_at,
            ),
            case_label=case_label,
            expected_sqlstate="23514",
            expected_constraint_name=("ck_command_idempotency_records_expiry_after_creation"),
        )


IMAGE_ASSET_INSERT = """
    INSERT INTO image_assets (
        id, paint_project_id, owner_principal_id, role, version,
        supersedes_image_asset_id, is_current, lifecycle_status,
        storage_provider, storage_key, original_filename,
        declared_content_type, detected_format, byte_size, width, height,
        pixel_count, color_mode, has_alpha, exif_orientation, sha256,
        upload_validation_result, upload_validation_details, source_type,
        rights_attestation_status, rights_attestation_version, intended_usage,
        rights_attested_by_principal_id, rights_attested_at,
        created_by_actor_type, created_by_actor_id,
        created_by_actor_display_name_snapshot, created_at
    )
    VALUES (
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
    )
"""


def _image_asset_parameters(
    project_id: uuid.UUID,
    owner_principal_id: str,
    **overrides: object,
) -> tuple[object, ...]:
    created_at = datetime.now(UTC)
    identifier = uuid.uuid4()
    values: dict[str, object] = {
        "id": identifier,
        "paint_project_id": project_id,
        "owner_principal_id": owner_principal_id,
        "role": "primary_front",
        "version": 1,
        "supersedes_image_asset_id": None,
        "is_current": True,
        "lifecycle_status": "current",
        "storage_provider": "local_filesystem",
        "storage_key": f"objects/{identifier.hex[:2]}/{identifier.hex}.jpg",
        "original_filename": "primary.jpg",
        "declared_content_type": "image/jpeg",
        "detected_format": "jpeg",
        "byte_size": 1024,
        "width": 768,
        "height": 768,
        "pixel_count": 768 * 768,
        "color_mode": "RGB",
        "has_alpha": False,
        "exif_orientation": 1,
        "sha256": "a" * 64,
        "upload_validation_result": "accepted",
        "upload_validation_details": Jsonb({"decoder_verified": True}),
        "source_type": "user_photographed",
        "rights_attestation_status": "confirmed",
        "rights_attestation_version": 1,
        "intended_usage": Jsonb(["private_project"]),
        "rights_attested_by_principal_id": owner_principal_id,
        "rights_attested_at": created_at,
        "created_by_actor_type": "user",
        "created_by_actor_id": owner_principal_id,
        "created_by_actor_display_name_snapshot": "Owner",
        "created_at": created_at,
    }
    values.update(overrides)
    return tuple(values[key] for key in values)


def _assert_image_asset_constraints(
    connection: psycopg.Connection[tuple[Any, ...]],
    project_id: uuid.UUID,
) -> None:
    owner = "o" * 128
    first_parameters = _image_asset_parameters(project_id, owner)
    first_asset_id = first_parameters[0]
    with connection.transaction():
        connection.execute(IMAGE_ASSET_INSERT, first_parameters)
        connection.execute(
            "UPDATE paint_projects SET current_image_asset_id = %s WHERE id = %s",
            (first_asset_id, project_id),
        )

    _expect_rejection(
        connection,
        IMAGE_ASSET_INSERT,
        _image_asset_parameters(
            project_id,
            "other-owner",
            version=2,
            is_current=False,
            lifecycle_status="superseded",
            storage_key=f"objects/dd/{uuid.uuid4().hex}.jpg",
        ),
        case_label="image owner does not match project owner",
        expected_sqlstate="23503",
        expected_constraint_name="fk_image_assets_project_owner_paint_projects",
    )
    _expect_rejection(
        connection,
        IMAGE_ASSET_INSERT,
        _image_asset_parameters(
            project_id,
            owner,
            version=2,
            storage_key=f"objects/bb/{'b' * 32}.jpg",
        ),
        case_label="two current assets for one project role",
        expected_sqlstate="23505",
        expected_constraint_name="uq_image_assets_project_role_current",
    )
    for case_label, overrides, expected_constraint in (
        (
            "unsupported role",
            {"role": "arbitrary_role"},
            "ck_image_assets_role_allowed",
        ),
        (
            "unsafe storage key",
            {"storage_key": "../private.jpg"},
            "ck_image_assets_storage_key_format",
        ),
        (
            "invalid sha",
            {"sha256": "A" * 64},
            "ck_image_assets_sha256_format",
        ),
        (
            "pixel count mismatch",
            {"pixel_count": 1},
            "ck_image_assets_pixel_count_allowed",
        ),
        (
            "quality details array",
            {"upload_validation_details": Jsonb([])},
            "ck_image_assets_upload_validation_details_is_object",
        ),
        (
            "unknown intended usage",
            {"intended_usage": Jsonb(["unknown"])},
            "ck_image_assets_intended_usage_allowed",
        ),
    ):
        candidate_overrides = {
            "version": 2,
            "is_current": False,
            "lifecycle_status": "superseded",
            "storage_key": f"objects/cc/{uuid.uuid4().hex}.jpg",
        }
        candidate_overrides.update(overrides)
        _expect_rejection(
            connection,
            IMAGE_ASSET_INSERT,
            _image_asset_parameters(
                project_id,
                owner,
                **candidate_overrides,
            ),
            case_label=case_label,
            expected_sqlstate="23514",
            expected_constraint_name=expected_constraint,
        )

    second_project_id = _insert_project(connection, owner=owner)
    _expect_rejection(
        connection,
        IMAGE_ASSET_INSERT,
        _image_asset_parameters(
            second_project_id,
            owner,
            supersedes_image_asset_id=first_asset_id,
        ),
        case_label="supersedes cannot cross projects",
        expected_sqlstate="23503",
        expected_constraint_name="fk_image_assets_supersedes_same_owner_project_role",
    )
    try:
        with connection.transaction():
            connection.execute(
                "UPDATE paint_projects SET current_image_asset_id = %s WHERE id = %s",
                (first_asset_id, second_project_id),
            )
    except psycopg.Error as error:
        assert error.sqlstate == "23503"
        assert (
            error.diag.constraint_name == "fk_paint_projects_current_image_asset_same_owner_project"
        )
    else:
        pytest.fail("A cross-project current image reference was accepted.")


def test_initial_paint_project_migration_round_trip_and_constraints(
    temporary_database: TemporaryDatabase,
) -> None:
    temporary_database_url = temporary_database.url
    temporary_database_name = temporary_database.name

    assert len(PHASE_3A_BUSINESS_TABLES) == 39
    assert len(PHASE_3B_BUSINESS_TABLES) == 5
    assert len(ARCANA_BUSINESS_TABLES) == 6
    assert CURRENT_BUSINESS_TABLES - PHASE_3A_BUSINESS_TABLES == (
        PHASE_3B_BUSINESS_TABLES | ARCANA_BUSINESS_TABLES
    )
    assert len(CURRENT_BUSINESS_TABLES) == 50

    _run_alembic(temporary_database_url, "upgrade", "3a04fab2e7a5")
    with psycopg.connect(
        **_connection_kwargs(temporary_database_url, temporary_database_name)
    ) as connection:
        phase3a_tables = {
            row[0]
            for row in connection.execute(
                """
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
                """
            ).fetchall()
        }
        assert phase3a_tables == PHASE_3A_BUSINESS_TABLES | {"alembic_version"}

    _run_alembic(temporary_database_url, "upgrade", "head")
    current_result = _run_alembic(temporary_database_url, "current")
    assert "4c01a2b3c4d5 (head)" in current_result.stdout
    check_result = _run_alembic(temporary_database_url, "check")
    assert "No new upgrade operations detected." in check_result.stdout

    with psycopg.connect(
        **_connection_kwargs(temporary_database_url, temporary_database_name)
    ) as connection:
        _assert_schema(connection)
        project_id = _assert_paint_project_constraints(connection)
        _assert_event_constraints(connection, project_id)
        _assert_idempotency_constraints(connection)
        _assert_image_asset_constraints(connection, project_id)

    _run_alembic(temporary_database_url, "downgrade", "base")
    with psycopg.connect(
        **_connection_kwargs(temporary_database_url, temporary_database_name)
    ) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                """
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
                """
            ).fetchall()
        }
        assert tables == {"alembic_version"}
        assert connection.execute("SELECT count(*) FROM alembic_version").fetchone() == (0,)

    _run_alembic(temporary_database_url, "upgrade", "head")
    with psycopg.connect(
        **_connection_kwargs(temporary_database_url, temporary_database_name)
    ) as connection:
        _assert_schema(connection)
        current_seed_counts = {
            "provider_definitions": 2,
            "model_definitions": 3,
            "capability_definitions": 3,
            "provider_capabilities": 6,
            "model_capabilities": 8,
            "provider_pricing_snapshots": 1,
            "prompt_template_definitions": 1,
            "tarot_card_definitions": 78,
            "tarot_spread_definitions": 1,
        }
        for table in CURRENT_BUSINESS_TABLES:
            query = sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table))
            assert connection.execute(query).fetchone() == (current_seed_counts.get(table, 0),)


def test_phase3a_downgrade_refuses_governed_facts_without_deleting_them(
    temporary_database: TemporaryDatabase,
) -> None:
    temporary_database_url = temporary_database.url
    temporary_database_name = temporary_database.name
    user_id = uuid.uuid4()
    _run_alembic(temporary_database_url, "upgrade", "head")
    with (
        psycopg.connect(
            **_connection_kwargs(temporary_database_url, temporary_database_name)
        ) as connection,
        connection.transaction(),
    ):
        connection.execute(
            """
            INSERT INTO user_accounts (id, display_name, email)
            VALUES (%s, %s, %s)
            """,
            (user_id, "Synthetic Downgrade Guard", "downgrade@example.test"),
        )

    with pytest.raises(AssertionError, match="governed facts exist"):
        _run_alembic(temporary_database_url, "downgrade", "7f3a2b9c4d1e")

    current_result = _run_alembic(temporary_database_url, "current")
    assert "4c01a2b3c4d5 (head)" in current_result.stdout
    with psycopg.connect(
        **_connection_kwargs(temporary_database_url, temporary_database_name)
    ) as connection:
        assert connection.execute(
            "SELECT display_name FROM user_accounts WHERE id = %s",
            (user_id,),
        ).fetchone() == ("Synthetic Downgrade Guard",)
        with connection.transaction():
            connection.execute("DELETE FROM user_accounts WHERE id = %s", (user_id,))

    _run_alembic(temporary_database_url, "downgrade", "7f3a2b9c4d1e")
    downgraded_result = _run_alembic(temporary_database_url, "current")
    assert "7f3a2b9c4d1e" in downgraded_result.stdout


def _phase3a_principal(user_id: uuid.UUID, principal_id: str) -> PrincipalContext:
    return PrincipalContext(
        principal_id=principal_id,
        principal_type=PrincipalType.HUMAN,
        display_name=f"Fixture actor {user_id}",
        authentication_mode=AuthenticationMode.OIDC_AUTHORIZATION_CODE,
        user_id=user_id,
    )


def _seed_phase3a_user_and_project(
    connection: psycopg.Connection[Any],
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    principal_id: str,
) -> None:
    now = datetime.now(UTC)
    connection.execute(
        """
        INSERT INTO user_accounts (
            id, display_name, email, is_active, created_at, updated_at
        ) VALUES (%s, %s, %s, true, %s, %s)
        """,
        (user_id, f"Fixture actor {user_id}", None, now, now),
    )
    connection.execute(
        """
        INSERT INTO paint_projects (
            id, owner_principal_id, title, description,
            requested_target_style, planning_mode, status, created_at, updated_at
        ) VALUES (%s, %s, %s, NULL, 'cel_shading', 'planning_only_demo', 'DRAFT', %s, %s)
        """,
        (project_id, principal_id, f"Fixture project {project_id}", now, now),
    )


def _phase3a_service(
    session: Any,
    *,
    adapter: FixtureProviderAdapter | None = None,
) -> AIFoundationService:
    return AIFoundationService(
        session,
        CredentialCipher(FixtureRootKeyProvider(bytes(range(32)))),
        adapter or FixtureProviderAdapter(),
    )


async def _configure_phase3a_owner(
    service: AIFoundationService,
    *,
    principal: PrincipalContext,
    project_id: uuid.UUID,
    cumulative_limit_minor_units: int = 10_000,
) -> tuple[CredentialRead, InvocationCreateRequest]:
    credential = await service.create_credential(
        payload=CredentialCreateRequest(
            provider_key="fixture_local",
            alias="Security concurrency fixture",
            credential=SecretStr(f"fixture-sk-{uuid.uuid4().hex}"),
            confirm_save=True,
        ),
        principal=principal,
        idempotency_key=uuid.uuid4(),
        request_id=uuid.uuid4(),
    )
    await service.create_grant(
        credential_id=credential.id,
        payload=CredentialGrantRequest(
            project_id=project_id,
            expected_credential_revision=credential.revision,
        ),
        principal=principal,
        idempotency_key=uuid.uuid4(),
        request_id=uuid.uuid4(),
    )
    await service.update_user_preference(
        payload=UserPreferenceUpdate(
            enabled=True,
            default_provider_definition_id=FIXTURE_PROVIDER_ID,
            default_model_definition_id=FIXTURE_TEXT_MODEL_ID,
            default_credential_id=credential.id,
            timeout_ms=30_000,
            streaming_enabled=False,
            cost_warning_minor_units=800,
            budget_per_invocation_minor_units=1_000,
            budget_cumulative_minor_units=cumulative_limit_minor_units,
            budget_window_seconds=86_400,
            expected_revision=0,
        ),
        principal=principal,
        idempotency_key=uuid.uuid4(),
        request_id=uuid.uuid4(),
    )
    await service.update_project_policy(
        project_id=project_id,
        payload=ProjectPolicyUpdate(
            enabled=True,
            default_provider_definition_id=FIXTURE_PROVIDER_ID,
            default_model_definition_id=FIXTURE_TEXT_MODEL_ID,
            default_credential_id=credential.id,
            provider_allowlist=[FIXTURE_PROVIDER_ID],
            model_allowlist=[FIXTURE_TEXT_MODEL_ID],
            capability_allowlist=[FIXTURE_TEXT_CAPABILITY_ID],
            credential_allowlist=[credential.id],
            per_invocation_limit_minor_units=1_000,
            cumulative_limit_minor_units=cumulative_limit_minor_units,
            budget_window_seconds=86_400,
            allow_unknown_cost=False,
            allow_manual_model_id=False,
            allow_fallback=False,
            require_paid_call_confirmation=True,
            expected_revision=0,
        ),
        principal=principal,
        idempotency_key=uuid.uuid4(),
        request_id=uuid.uuid4(),
    )
    return credential, InvocationCreateRequest(
        product_space="paintpilot",
        project_id=project_id,
        invocation_family="fixture_invocation",
        provider_definition_id=FIXTURE_PROVIDER_ID,
        model_definition_id=FIXTURE_TEXT_MODEL_ID,
        credential_id=credential.id,
        temporary_credential=None,
        requested_capabilities=["text_generation"],
        artifacts=[],
        payload=FixtureInvocationPayload(
            prompt_label="security concurrency",
            fixture_input="deterministic local evidence",
            scenario="success",
        ),
        confirm_fixture_use=True,
        max_attempts=2,
        total_elapsed_time_limit_ms=30_000,
    )


def test_phase3a_fixture_service_round_trip_and_rejection_has_no_adapter_effect(
    temporary_database: TemporaryDatabase,
) -> None:
    temporary_database_url = temporary_database.url
    temporary_database_name = temporary_database.name
    user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    principal_id = "phase3a-fixture-owner"
    now = datetime.now(UTC)
    _run_alembic(temporary_database_url, "upgrade", "head")
    with (
        psycopg.connect(
            **_connection_kwargs(temporary_database_url, temporary_database_name)
        ) as connection,
        connection.transaction(),
    ):
        connection.execute(
            """
            INSERT INTO user_accounts (
                id, display_name, email, is_active, created_at, updated_at
            ) VALUES (%s, %s, %s, true, %s, %s)
            """,
            (user_id, "Phase 3A Fixture Owner", "phase3a@example.test", now, now),
        )
        connection.execute(
            """
            INSERT INTO paint_projects (
                id, owner_principal_id, title, description,
                requested_target_style, planning_mode, status, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, 'cel_shading', 'planning_only_demo', 'DRAFT', %s, %s)
            """,
            (project_id, principal_id, "Fixture policy project", None, now, now),
        )

    async def exercise() -> tuple[uuid.UUID, int, uuid.UUID, uuid.UUID]:
        engine = create_async_engine(
            temporary_database_url.render_as_string(hide_password=False),
            pool_pre_ping=True,
        )
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        adapter = FixtureProviderAdapter()
        original_invoke = adapter.invoke
        adapter_calls = 0

        def counted_invoke(*args: Any, **kwargs: Any) -> Any:
            nonlocal adapter_calls
            adapter_calls += 1
            return original_invoke(*args, **kwargs)

        adapter.invoke = counted_invoke  # type: ignore[method-assign]
        principal = PrincipalContext(
            principal_id=principal_id,
            principal_type=PrincipalType.HUMAN,
            display_name="Phase 3A Fixture Owner",
            authentication_mode=AuthenticationMode.OIDC_AUTHORIZATION_CODE,
            user_id=user_id,
        )
        try:
            async with session_factory() as session:
                service = AIFoundationService(
                    session,
                    CredentialCipher(FixtureRootKeyProvider(bytes(range(32)))),
                    adapter,
                )
                credential = await service.create_credential(
                    payload=CredentialCreateRequest(
                        provider_key="fixture_local",
                        alias="Local fixture key",
                        credential=SecretStr("fixture-sk-0123456789abcdef"),
                        confirm_save=True,
                    ),
                    principal=principal,
                    idempotency_key=uuid.uuid4(),
                    request_id=uuid.uuid4(),
                )
                assert "fixture-sk" not in credential.model_dump_json()
                await service.create_grant(
                    credential_id=credential.id,
                    payload=CredentialGrantRequest(
                        project_id=project_id,
                        expected_credential_revision=credential.revision,
                    ),
                    principal=principal,
                    idempotency_key=uuid.uuid4(),
                    request_id=uuid.uuid4(),
                )
                await service.update_user_preference(
                    payload=UserPreferenceUpdate(
                        enabled=True,
                        default_provider_definition_id=FIXTURE_PROVIDER_ID,
                        default_model_definition_id=FIXTURE_TEXT_MODEL_ID,
                        default_credential_id=credential.id,
                        timeout_ms=30_000,
                        streaming_enabled=False,
                        cost_warning_minor_units=800,
                        budget_per_invocation_minor_units=1_000,
                        budget_cumulative_minor_units=10_000,
                        budget_window_seconds=86_400,
                        expected_revision=0,
                    ),
                    principal=principal,
                    idempotency_key=uuid.uuid4(),
                    request_id=uuid.uuid4(),
                )
                temporary_invocation = await service.create_invocation(
                    payload=InvocationCreateRequest(
                        product_space="paintpilot",
                        project_id=None,
                        invocation_family="fixture_invocation",
                        provider_definition_id=FIXTURE_PROVIDER_ID,
                        model_definition_id=FIXTURE_TEXT_MODEL_ID,
                        credential_id=None,
                        temporary_credential=SecretStr("fixture-sk-projectless-0123456789"),
                        requested_capabilities=["text_generation"],
                        artifacts=[],
                        payload=FixtureInvocationPayload(
                            prompt_label="temporary local integration",
                            fixture_input="request-local fixture only",
                            scenario="success",
                        ),
                        confirm_fixture_use=True,
                        max_attempts=1,
                        total_elapsed_time_limit_ms=30_000,
                    ),
                    principal=principal,
                    idempotency_key=uuid.uuid4(),
                    request_id=uuid.uuid4(),
                )
                assert temporary_invocation.status == "succeeded"
                assert temporary_invocation.attempts[0].safe_provider_metadata["fixture"] is True
                await service.update_project_policy(
                    project_id=project_id,
                    payload=ProjectPolicyUpdate(
                        enabled=True,
                        default_provider_definition_id=FIXTURE_PROVIDER_ID,
                        default_model_definition_id=FIXTURE_TEXT_MODEL_ID,
                        default_credential_id=credential.id,
                        provider_allowlist=[FIXTURE_PROVIDER_ID],
                        model_allowlist=[FIXTURE_TEXT_MODEL_ID],
                        capability_allowlist=[
                            FIXTURE_TEXT_CAPABILITY_ID,
                            FIXTURE_STRUCTURED_CAPABILITY_ID,
                        ],
                        credential_allowlist=[credential.id],
                        per_invocation_limit_minor_units=1_000,
                        cumulative_limit_minor_units=5_000,
                        budget_window_seconds=86_400,
                        allow_unknown_cost=False,
                        allow_manual_model_id=False,
                        allow_fallback=False,
                        require_paid_call_confirmation=True,
                        expected_revision=0,
                    ),
                    principal=principal,
                    idempotency_key=uuid.uuid4(),
                    request_id=uuid.uuid4(),
                )
                fixture_payload = FixtureInvocationPayload(
                    prompt_label="local integration",
                    fixture_input="deterministic paint planning fixture",
                    scenario="success",
                )
                preview_request = InvocationPreviewRequest(
                    product_space="paintpilot",
                    project_id=project_id,
                    invocation_family="fixture_invocation",
                    provider_definition_id=FIXTURE_PROVIDER_ID,
                    model_definition_id=FIXTURE_TEXT_MODEL_ID,
                    credential_id=credential.id,
                    requested_capabilities=["text_generation"],
                    payload=fixture_payload,
                    confirm_fixture_use=True,
                )
                preview = await service.preview_invocation(
                    payload=preview_request, principal=principal
                )
                assert preview.admissible is True
                assert preview.local_only is True
                invocation_key = uuid.uuid4()
                invocation_request = InvocationCreateRequest(
                    **preview_request.model_dump(),
                    max_attempts=1,
                    total_elapsed_time_limit_ms=30_000,
                )
                invocation = await service.create_invocation(
                    payload=invocation_request,
                    principal=principal,
                    idempotency_key=invocation_key,
                    request_id=uuid.uuid4(),
                )
                assert invocation.status == "succeeded"
                assert invocation.output == {
                    "fixture": True,
                    "local_only": True,
                    "result_id": invocation.output["result_id"],
                    "summary": "Deterministic local fixture response",
                }
                replay = await service.create_invocation(
                    payload=invocation_request,
                    principal=principal,
                    idempotency_key=invocation_key,
                    request_id=uuid.uuid4(),
                )
                assert replay.id == invocation.id
                assert replay.replayed is True
                assert adapter_calls == 2

                failed_request = InvocationCreateRequest(
                    **{
                        **preview_request.model_dump(),
                        "payload": FixtureInvocationPayload(
                            prompt_label="terminal failure",
                            fixture_input="deterministic invalid request",
                            scenario="invalid_request",
                        ),
                    },
                    max_attempts=1,
                    total_elapsed_time_limit_ms=30_000,
                )
                failed = await service.create_invocation(
                    payload=failed_request,
                    principal=principal,
                    idempotency_key=uuid.uuid4(),
                    request_id=uuid.uuid4(),
                )
                assert failed.status == "failed"
                assert failed.final_attempt_id is None
                assert failed.attempts[0].status == "failed"

                unknown_request = InvocationCreateRequest(
                    **{
                        **preview_request.model_dump(),
                        "payload": FixtureInvocationPayload(
                            prompt_label="unknown outcome",
                            fixture_input="deterministic reconciliation",
                            scenario="outcome_unknown",
                        ),
                    },
                    max_attempts=2,
                    total_elapsed_time_limit_ms=30_000,
                )
                unknown = await service.create_invocation(
                    payload=unknown_request,
                    principal=principal,
                    idempotency_key=uuid.uuid4(),
                    request_id=uuid.uuid4(),
                )
                assert unknown.status == "outcome_unknown"
                assert len(unknown.attempts) == 1
                assert unknown.final_attempt_id is None

                retry_request = InvocationCreateRequest(
                    **{
                        **preview_request.model_dump(),
                        "payload": FixtureInvocationPayload(
                            prompt_label="bounded retry",
                            fixture_input="deterministic provider unavailable",
                            scenario="provider_unavailable",
                        ),
                    },
                    max_attempts=2,
                    total_elapsed_time_limit_ms=30_000,
                )
                retried = await service.create_invocation(
                    payload=retry_request,
                    principal=principal,
                    idempotency_key=uuid.uuid4(),
                    request_id=uuid.uuid4(),
                )
                assert retried.status == "failed"
                assert [attempt.attempt_number for attempt in retried.attempts] == [1, 2]
                assert [attempt.status for attempt in retried.attempts] == ["failed", "failed"]
                assert retried.final_attempt_id is None
                async with session.begin():
                    retry_transition = (
                        await session.execute(
                            text(
                                """
                                SELECT from_status, to_status
                                FROM ai_invocation_events
                                WHERE invocation_id = :invocation_id
                                  AND attempt_id = :attempt_id
                                  AND event_type = 'attempt_admitted'
                                """
                            ),
                            {
                                "invocation_id": retried.id,
                                "attempt_id": retried.attempts[1].id,
                            },
                        )
                    ).one()
                assert retry_transition == ("running", "admitted")
                assert adapter_calls == 6

                rejected_request = InvocationCreateRequest(
                    **{
                        **preview_request.model_dump(),
                        "requested_capabilities": ["vision_understanding"],
                    },
                    max_attempts=1,
                    total_elapsed_time_limit_ms=30_000,
                )
                with pytest.raises(AdmissionRejectedError):
                    await service.create_invocation(
                        payload=rejected_request,
                        principal=principal,
                        idempotency_key=uuid.uuid4(),
                        request_id=uuid.uuid4(),
                    )
                assert adapter_calls == 6
                audit = await service.list_audit(
                    principal=principal,
                    project_id=project_id,
                    limit=100,
                    offset=0,
                )
                assert audit.total >= 3
                revoked = await service.revoke_credential(
                    credential_id=credential.id,
                    payload=CredentialMutationRequest(
                        expected_revision=credential.revision,
                        confirm=True,
                    ),
                    principal=principal,
                    idempotency_key=uuid.uuid4(),
                    request_id=uuid.uuid4(),
                )
                assert revoked.status == "revoked"
                return credential.id, adapter_calls, failed.id, failed.attempts[0].id
        finally:
            await engine.dispose()

    credential_id, adapter_calls, failed_invocation_id, failed_attempt_id = asyncio.run(exercise())
    assert adapter_calls == 6
    with psycopg.connect(
        **_connection_kwargs(temporary_database_url, temporary_database_name)
    ) as connection:
        erased = connection.execute(
            """
            SELECT status, ciphertext, wrapped_dek, data_nonce, wrap_nonce,
                   data_authentication_tag, wrap_authentication_tag
            FROM credential_records WHERE id = %s
            """,
            (credential_id,),
        ).fetchone()
        assert erased == ("revoked", None, None, None, None, None, None)
        assert connection.execute("SELECT count(*) FROM ai_usage_ledger").fetchone() == (2,)
        assert connection.execute("SELECT count(*) FROM ai_cost_ledger").fetchone() == (2,)
        assert connection.execute(
            """
            SELECT count(*) FROM invocation_requests
            WHERE project_id IS NULL AND requested_credential_id IS NULL
              AND safe_payload->>'temporary_credential' = 'true'
              AND safe_payload::text NOT LIKE '%%fixture-sk%%'
            """
        ).fetchone() == (1,)
        assert connection.execute("SELECT count(*) FROM credential_records").fetchone() == (1,)
        with (
            pytest.raises(psycopg.Error) as invalid_final_attempt,
            connection.transaction(),
        ):
            connection.execute(
                "UPDATE invocation_requests SET final_attempt_id = %s WHERE id = %s",
                (failed_attempt_id, failed_invocation_id),
            )
        assert invalid_final_attempt.value.sqlstate == "23514"
        assert connection.execute(
            "SELECT final_attempt_id FROM invocation_requests WHERE id = %s",
            (failed_invocation_id,),
        ).fetchone() == (None,)
        for append_only_table in (
            "ai_invocation_events",
            "ai_usage_ledger",
            "ai_cost_ledger",
            "ai_audit_events",
        ):
            statement = sql.SQL("UPDATE {} SET created_at = created_at").format(
                sql.Identifier(append_only_table)
            )
            with (
                pytest.raises(psycopg.Error) as append_only_error,
                connection.transaction(),
            ):
                connection.execute(statement)
            assert append_only_error.value.sqlstate == "55000"


def test_phase3a_reference_authorization_precedes_pending_side_effects(
    temporary_database: TemporaryDatabase,
) -> None:
    temporary_database_url = temporary_database.url
    temporary_database_name = temporary_database.name
    owner_user_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    unauthorized_project_id = uuid.uuid4()
    no_grant_project_id = uuid.uuid4()
    owner_principal_id = "phase3a-reference-owner"
    other_principal_id = "phase3a-reference-other"
    _run_alembic(temporary_database_url, "upgrade", "head")
    with (
        psycopg.connect(
            **_connection_kwargs(temporary_database_url, temporary_database_name)
        ) as connection,
        connection.transaction(),
    ):
        _seed_phase3a_user_and_project(
            connection,
            user_id=owner_user_id,
            project_id=project_id,
            principal_id=owner_principal_id,
        )
        _seed_phase3a_user_and_project(
            connection,
            user_id=other_user_id,
            project_id=unauthorized_project_id,
            principal_id=other_principal_id,
        )
        now = datetime.now(UTC)
        connection.execute(
            """
            INSERT INTO paint_projects (
                id, owner_principal_id, title, requested_target_style,
                planning_mode, status, created_at, updated_at
            ) VALUES (%s, %s, %s, 'cel_shading', 'planning_only_demo', 'DRAFT', %s, %s)
            """,
            (no_grant_project_id, owner_principal_id, "No grant project", now, now),
        )

    async def exercise() -> None:
        engine = create_async_engine(
            temporary_database_url.render_as_string(hide_password=False),
            pool_pre_ping=True,
        )
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        adapter = FixtureProviderAdapter()
        original_invoke = adapter.invoke
        adapter_calls = 0

        def counted_invoke(*args: Any, **kwargs: Any) -> Any:
            nonlocal adapter_calls
            adapter_calls += 1
            return original_invoke(*args, **kwargs)

        adapter.invoke = counted_invoke  # type: ignore[method-assign]
        owner = _phase3a_principal(owner_user_id, owner_principal_id)
        other = _phase3a_principal(other_user_id, other_principal_id)
        try:
            async with session_factory() as session:
                owner_service = _phase3a_service(session, adapter=adapter)
                owner_credential, valid_request = await _configure_phase3a_owner(
                    owner_service,
                    principal=owner,
                    project_id=project_id,
                )
            async with session_factory() as session:
                other_service = _phase3a_service(session)
                other_credential = await other_service.create_credential(
                    payload=CredentialCreateRequest(
                        provider_key="fixture_local",
                        alias="Other user fixture",
                        credential=SecretStr(f"fixture-sk-{uuid.uuid4().hex}"),
                        confirm_save=True,
                    ),
                    principal=other,
                    idempotency_key=uuid.uuid4(),
                    request_id=uuid.uuid4(),
                )
            async with session_factory() as session:
                baseline_values = []
                for table in (
                    "invocation_requests",
                    "invocation_attempts",
                    "budget_reservations",
                    "ai_audit_events",
                ):
                    baseline_values.append(
                        (await session.execute(text(f"SELECT count(*) FROM {table}"))).scalar_one()
                    )
                baseline = tuple(baseline_values)
                await session.rollback()
            cases = (
                valid_request.model_copy(update={"project_id": uuid.uuid4()}),
                valid_request.model_copy(update={"project_id": unauthorized_project_id}),
                valid_request.model_copy(
                    update={"project_id": None, "credential_id": uuid.uuid4()}
                ),
                valid_request.model_copy(
                    update={"project_id": None, "credential_id": other_credential.id}
                ),
                valid_request.model_copy(update={"project_id": no_grant_project_id}),
            )
            for request in cases:
                async with session_factory() as session:
                    service = _phase3a_service(session, adapter=adapter)
                    with pytest.raises(AIResourceNotFoundError):
                        await service.create_invocation(
                            payload=request,
                            principal=owner,
                            idempotency_key=uuid.uuid4(),
                            request_id=uuid.uuid4(),
                        )
            async with session_factory() as session:
                after_values = []
                for table in (
                    "invocation_requests",
                    "invocation_attempts",
                    "budget_reservations",
                    "ai_audit_events",
                ):
                    after_values.append(
                        (await session.execute(text(f"SELECT count(*) FROM {table}"))).scalar_one()
                    )
                after = tuple(after_values)
            assert after == baseline
            assert owner_credential.id == valid_request.credential_id
            async with session_factory() as session:
                service = _phase3a_service(session, adapter=adapter)
                replacement = await service.replace_credential(
                    credential_id=owner_credential.id,
                    payload=CredentialReplaceRequest(
                        alias="Replacement fixture",
                        credential=SecretStr(f"fixture-sk-{uuid.uuid4().hex}"),
                        expected_revision=owner_credential.revision,
                        confirm_replace=True,
                    ),
                    principal=owner,
                    idempotency_key=uuid.uuid4(),
                    request_id=uuid.uuid4(),
                )
                assert replacement.id != owner_credential.id
            async with session_factory() as session:
                service = _phase3a_service(session, adapter=adapter)
                with pytest.raises(AIResourceNotFoundError):
                    await service.create_invocation(
                        payload=valid_request,
                        principal=owner,
                        idempotency_key=uuid.uuid4(),
                        request_id=uuid.uuid4(),
                    )
            async with session_factory() as session:
                lifecycle = (
                    await session.execute(
                        text(
                            """
                            SELECT status, ciphertext, wrapped_dek, data_nonce, wrap_nonce
                            FROM credential_records WHERE id = :id
                            """
                        ),
                        {"id": owner_credential.id},
                    )
                ).one()
                assert lifecycle == ("replaced", None, None, None, None)
                assert (
                    await session.execute(
                        text(
                            """
                            SELECT count(*) FROM credential_project_grants
                            WHERE credential_id = :id AND revoked_at IS NULL
                            """
                        ),
                        {"id": owner_credential.id},
                    )
                ).scalar_one() == 0
                assert (
                    await session.execute(
                        text(
                            "SELECT count(*) FROM credential_project_grants "
                            "WHERE credential_id = :id"
                        ),
                        {"id": replacement.id},
                    )
                ).scalar_one() == 0
            assert adapter_calls == 0
        finally:
            await engine.dispose()

    asyncio.run(exercise())


def test_phase3a_membership_revoke_and_admission_linearize_on_postgresql(
    temporary_database: TemporaryDatabase,
) -> None:
    temporary_database_url = temporary_database.url
    temporary_database_name = temporary_database.name
    owner_user_id = uuid.uuid4()
    reviewer_user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    owner_principal_id = "phase3a-linearization-owner"
    reviewer_principal_id = "phase3a-linearization-reviewer"
    _run_alembic(temporary_database_url, "upgrade", "head")
    with (
        psycopg.connect(
            **_connection_kwargs(temporary_database_url, temporary_database_name)
        ) as connection,
        connection.transaction(),
    ):
        _seed_phase3a_user_and_project(
            connection,
            user_id=reviewer_user_id,
            project_id=project_id,
            principal_id=reviewer_principal_id,
        )
        now = datetime.now(UTC)
        connection.execute(
            """
            INSERT INTO user_accounts (id, display_name, is_active, created_at, updated_at)
            VALUES (%s, %s, true, %s, %s)
            """,
            (owner_user_id, "Linearization owner", now, now),
        )

    async def exercise() -> None:
        engine = create_async_engine(
            temporary_database_url.render_as_string(hide_password=False),
            pool_pre_ping=True,
        )
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        adapter = FixtureProviderAdapter()
        adapter_calls = 0
        original_invoke = adapter.invoke

        def counted_invoke(*args: Any, **kwargs: Any) -> Any:
            nonlocal adapter_calls
            adapter_calls += 1
            return original_invoke(*args, **kwargs)

        adapter.invoke = counted_invoke  # type: ignore[method-assign]
        reviewer = _phase3a_principal(reviewer_user_id, reviewer_principal_id)
        owner = _phase3a_principal(owner_user_id, owner_principal_id)
        try:
            async with session_factory() as session:
                setup_service = _phase3a_service(session, adapter=adapter)
                _, request = await _configure_phase3a_owner(
                    setup_service,
                    principal=reviewer,
                    project_id=project_id,
                )
            async with session_factory() as session, session.begin():
                await session.execute(
                    text(
                        """
                            UPDATE paint_projects SET owner_principal_id = :owner
                            WHERE id = :project_id
                            """
                    ),
                    {"owner": owner_principal_id, "project_id": project_id},
                )
                await session.execute(
                    text(
                        """
                            INSERT INTO project_memberships (
                                id, paint_project_id, user_id, role,
                                assigned_by_user_id, created_at
                            ) VALUES (
                                :id, :project_id, :user_id, 'reviewer',
                                :assigned_by_user_id, now()
                            )
                            """
                    ),
                    {
                        "id": uuid.uuid4(),
                        "project_id": project_id,
                        "user_id": reviewer_user_id,
                        "assigned_by_user_id": owner_user_id,
                    },
                )

            async with session_factory() as session:
                pending_service = _phase3a_service(session, adapter=adapter)
                pending_a, replayed = await pending_service._create_pending_invocation(
                    payload=request,
                    principal=reviewer,
                    idempotency_key=uuid.uuid4(),
                    request_id=uuid.uuid4(),
                )
                assert replayed is False

            revoke_locked = asyncio.Event()
            allow_revoke_commit = asyncio.Event()

            async def revoke_first() -> None:
                async with session_factory() as session, session.begin():
                    await session.execute(
                        text(
                            """
                                SELECT id FROM user_accounts
                                WHERE id IN (:owner_id, :reviewer_id)
                                ORDER BY id FOR UPDATE
                                """
                        ),
                        {"owner_id": owner_user_id, "reviewer_id": reviewer_user_id},
                    )
                    await session.execute(
                        text("SELECT id FROM paint_projects WHERE id = :id FOR UPDATE"),
                        {"id": project_id},
                    )
                    await session.execute(
                        text(
                            """
                                SELECT id FROM project_memberships
                                WHERE paint_project_id = :project_id AND user_id = :user_id
                                FOR UPDATE
                                """
                        ),
                        {"project_id": project_id, "user_id": reviewer_user_id},
                    )
                    await session.execute(
                        text(
                            """
                                DELETE FROM project_memberships
                                WHERE paint_project_id = :project_id AND user_id = :user_id
                                """
                        ),
                        {"project_id": project_id, "user_id": reviewer_user_id},
                    )
                    revoke_locked.set()
                    await allow_revoke_commit.wait()

            async def blocked_admission() -> None:
                async with session_factory() as session:
                    service = _phase3a_service(session, adapter=adapter)
                    await service._admit_attempt(
                        invocation_id=pending_a.id,
                        payload=request,
                        principal=reviewer,
                        attempt_number=1,
                        retry_of_attempt_id=None,
                    )

            revoke_task = asyncio.create_task(revoke_first())
            await revoke_locked.wait()
            admission_task = asyncio.create_task(blocked_admission())
            await asyncio.sleep(0.05)
            assert admission_task.done() is False
            allow_revoke_commit.set()
            await revoke_task
            with pytest.raises(AIAuthorizationError):
                await admission_task

            async with session_factory() as session:
                assert (
                    await session.execute(
                        text("SELECT count(*) FROM invocation_attempts WHERE invocation_id = :id"),
                        {"id": pending_a.id},
                    )
                ).scalar_one() == 0

            async with session_factory() as session, session.begin():
                await session.execute(
                    text(
                        """
                            INSERT INTO project_memberships (
                                id, paint_project_id, user_id, role,
                                assigned_by_user_id, created_at
                            ) VALUES (
                                :id, :project_id, :user_id, 'reviewer',
                                :assigned_by_user_id, now()
                            )
                            """
                    ),
                    {
                        "id": uuid.uuid4(),
                        "project_id": project_id,
                        "user_id": reviewer_user_id,
                        "assigned_by_user_id": owner_user_id,
                    },
                )
            async with session_factory() as session:
                service = _phase3a_service(session, adapter=adapter)
                pending_b, _ = await service._create_pending_invocation(
                    payload=request,
                    principal=reviewer,
                    idempotency_key=uuid.uuid4(),
                    request_id=uuid.uuid4(),
                )

            admission_paused = asyncio.Event()
            allow_admission_commit = asyncio.Event()

            async def admission_first() -> tuple[uuid.UUID, uuid.UUID]:
                async with session_factory() as session:
                    service = _phase3a_service(session, adapter=adapter)
                    original_flush = service._repository.flush
                    flush_calls = 0

                    async def controlled_flush() -> None:
                        nonlocal flush_calls
                        flush_calls += 1
                        await original_flush()
                        if flush_calls == 3:
                            admission_paused.set()
                            await allow_admission_commit.wait()

                    service._repository.flush = controlled_flush  # type: ignore[method-assign]
                    attempt_id, reservation_id, _, _ = await service._admit_attempt(
                        invocation_id=pending_b.id,
                        payload=request,
                        principal=reviewer,
                        attempt_number=1,
                        retry_of_attempt_id=None,
                    )
                    return attempt_id, reservation_id

            async def revoke_after_admission() -> None:
                async with session_factory() as session:
                    membership_service = ProjectMembershipService(session)
                    await membership_service.remove(
                        project_id=project_id,
                        reviewer_user_id=reviewer_user_id,
                        principal=owner,
                    )

            admission_first_task = asyncio.create_task(admission_first())
            await admission_paused.wait()
            revoke_after_task = asyncio.create_task(revoke_after_admission())
            await asyncio.sleep(0.05)
            assert revoke_after_task.done() is False
            allow_admission_commit.set()
            attempt_id, reservation_id = await admission_first_task
            await revoke_after_task

            async with session_factory() as session:
                service = _phase3a_service(session, adapter=adapter)
                assert await service._commit_dispatch(
                    invocation_id=pending_b.id,
                    attempt_id=attempt_id,
                    reservation_id=reservation_id,
                )
            async with session_factory() as session:
                service = _phase3a_service(session, adapter=adapter)
                with pytest.raises(AIAuthorizationError):
                    await service._admit_attempt(
                        invocation_id=pending_b.id,
                        payload=request,
                        principal=reviewer,
                        attempt_number=2,
                        retry_of_attempt_id=attempt_id,
                    )
            assert adapter_calls == 0
        finally:
            await engine.dispose()

    asyncio.run(exercise())


def test_phase3a_policy_lock_order_and_tightened_budget_are_authoritative(
    temporary_database: TemporaryDatabase,
) -> None:
    temporary_database_url = temporary_database.url
    temporary_database_name = temporary_database.name
    user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    principal_id = "phase3a-budget-owner"
    _run_alembic(temporary_database_url, "upgrade", "head")
    with (
        psycopg.connect(
            **_connection_kwargs(temporary_database_url, temporary_database_name)
        ) as connection,
        connection.transaction(),
    ):
        _seed_phase3a_user_and_project(
            connection,
            user_id=user_id,
            project_id=project_id,
            principal_id=principal_id,
        )

    async def exercise() -> None:
        engine = create_async_engine(
            temporary_database_url.render_as_string(hide_password=False),
            pool_pre_ping=True,
        )
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        principal = _phase3a_principal(user_id, principal_id)
        try:
            async with session_factory() as session:
                service = _phase3a_service(session)
                credential, request = await _configure_phase3a_owner(
                    service,
                    principal=principal,
                    project_id=project_id,
                )
            async with session_factory() as session, session.begin():
                await session.execute(
                    text(
                        """
                            UPDATE user_budget_counters
                            SET committed_minor_units = 4990, limit_minor_units = 10000
                            WHERE user_id = :user_id
                            """
                    ),
                    {"user_id": user_id},
                )
            async with session_factory() as session:
                service = _phase3a_service(session)
                order: list[str] = []
                original_credential = service._repository.get_owned_credential
                original_preference = service._repository.get_preference
                original_budget = service._repository.get_user_budget_policy
                original_counter = service._repository.get_user_counter

                async def tracked_credential(*args: Any, **kwargs: Any) -> Any:
                    order.append("credential")
                    return await original_credential(*args, **kwargs)

                async def tracked_preference(*args: Any, **kwargs: Any) -> Any:
                    order.append("preference")
                    return await original_preference(*args, **kwargs)

                async def tracked_budget(*args: Any, **kwargs: Any) -> Any:
                    order.append("user_budget_policy")
                    return await original_budget(*args, **kwargs)

                async def tracked_counter(*args: Any, **kwargs: Any) -> Any:
                    order.append("user_counter")
                    return await original_counter(*args, **kwargs)

                service._repository.get_owned_credential = tracked_credential  # type: ignore[method-assign]
                service._repository.get_preference = tracked_preference  # type: ignore[method-assign]
                service._repository.get_user_budget_policy = tracked_budget  # type: ignore[method-assign]
                service._repository.get_user_counter = tracked_counter  # type: ignore[method-assign]
                await service.update_user_preference(
                    payload=UserPreferenceUpdate(
                        enabled=True,
                        default_provider_definition_id=FIXTURE_PROVIDER_ID,
                        default_model_definition_id=FIXTURE_TEXT_MODEL_ID,
                        default_credential_id=credential.id,
                        timeout_ms=30_000,
                        streaming_enabled=False,
                        cost_warning_minor_units=800,
                        budget_per_invocation_minor_units=1_000,
                        budget_cumulative_minor_units=5_000,
                        budget_window_seconds=86_400,
                        expected_revision=1,
                    ),
                    principal=principal,
                    idempotency_key=uuid.uuid4(),
                    request_id=uuid.uuid4(),
                )
                assert order.index("credential") < order.index("preference")
                assert order.index("preference") < order.index("user_budget_policy")
                assert order.index("user_budget_policy") < order.index("user_counter")
            async with session_factory() as session:
                service = _phase3a_service(session)
                pending, _ = await service._create_pending_invocation(
                    payload=request,
                    principal=principal,
                    idempotency_key=uuid.uuid4(),
                    request_id=uuid.uuid4(),
                )
                with pytest.raises(AdmissionRejectedError):
                    await service._admit_attempt(
                        invocation_id=pending.id,
                        payload=request,
                        principal=principal,
                        attempt_number=1,
                        retry_of_attempt_id=None,
                    )
            async with session_factory() as session:
                service = _phase3a_service(session)
                await service.update_user_preference(
                    payload=UserPreferenceUpdate(
                        enabled=True,
                        default_provider_definition_id=FIXTURE_PROVIDER_ID,
                        default_model_definition_id=FIXTURE_TEXT_MODEL_ID,
                        default_credential_id=credential.id,
                        timeout_ms=30_000,
                        streaming_enabled=False,
                        cost_warning_minor_units=800,
                        budget_per_invocation_minor_units=1_000,
                        budget_cumulative_minor_units=10_000,
                        budget_window_seconds=86_400,
                        expected_revision=2,
                    ),
                    principal=principal,
                    idempotency_key=uuid.uuid4(),
                    request_id=uuid.uuid4(),
                )
            async with session_factory() as session, session.begin():
                await session.execute(
                    text(
                        """
                            UPDATE user_budget_counters
                            SET committed_minor_units = 0, limit_minor_units = 10000
                            WHERE user_id = :user_id
                            """
                    ),
                    {"user_id": user_id},
                )
                await session.execute(
                    text(
                        """
                            UPDATE project_budget_counters
                            SET committed_minor_units = 4990, limit_minor_units = 10000
                            WHERE project_id = :project_id
                            """
                    ),
                    {"project_id": project_id},
                )
            async with session_factory() as session:
                service = _phase3a_service(session)
                second = await service.create_credential(
                    payload=CredentialCreateRequest(
                        provider_key="fixture_local",
                        alias="Second ordered credential",
                        credential=SecretStr(f"fixture-sk-{uuid.uuid4().hex}"),
                        confirm_save=True,
                    ),
                    principal=principal,
                    idempotency_key=uuid.uuid4(),
                    request_id=uuid.uuid4(),
                )
                await service.create_grant(
                    credential_id=second.id,
                    payload=CredentialGrantRequest(
                        project_id=project_id,
                        expected_credential_revision=second.revision,
                    ),
                    principal=principal,
                    idempotency_key=uuid.uuid4(),
                    request_id=uuid.uuid4(),
                )
                order = []
                original_credentials = service._repository.lock_owned_credentials
                original_grants = service._repository.lock_active_grants_for_credentials
                original_policy = service._repository.get_project_policy
                original_budget = service._repository.get_project_budget_policy
                original_counter = service._repository.get_project_counter

                async def tracked_credentials(*args: Any, **kwargs: Any) -> Any:
                    order.append("credentials")
                    return await original_credentials(*args, **kwargs)

                async def tracked_grants(*args: Any, **kwargs: Any) -> Any:
                    order.append("grants")
                    return await original_grants(*args, **kwargs)

                async def tracked_policy(*args: Any, **kwargs: Any) -> Any:
                    order.append("project_policy")
                    return await original_policy(*args, **kwargs)

                async def tracked_project_budget(*args: Any, **kwargs: Any) -> Any:
                    order.append("project_budget_policy")
                    return await original_budget(*args, **kwargs)

                async def tracked_project_counter(*args: Any, **kwargs: Any) -> Any:
                    order.append("project_counter")
                    return await original_counter(*args, **kwargs)

                service._repository.lock_owned_credentials = tracked_credentials  # type: ignore[method-assign]
                service._repository.lock_active_grants_for_credentials = tracked_grants  # type: ignore[method-assign]
                service._repository.get_project_policy = tracked_policy  # type: ignore[method-assign]
                service._repository.get_project_budget_policy = tracked_project_budget  # type: ignore[method-assign]
                service._repository.get_project_counter = tracked_project_counter  # type: ignore[method-assign]
                await service.update_project_policy(
                    project_id=project_id,
                    payload=ProjectPolicyUpdate(
                        enabled=True,
                        default_provider_definition_id=FIXTURE_PROVIDER_ID,
                        default_model_definition_id=FIXTURE_TEXT_MODEL_ID,
                        default_credential_id=credential.id,
                        provider_allowlist=[FIXTURE_PROVIDER_ID],
                        model_allowlist=[FIXTURE_TEXT_MODEL_ID],
                        capability_allowlist=[FIXTURE_TEXT_CAPABILITY_ID],
                        credential_allowlist=[credential.id, second.id],
                        per_invocation_limit_minor_units=1_000,
                        cumulative_limit_minor_units=5_000,
                        budget_window_seconds=86_400,
                        allow_unknown_cost=False,
                        allow_manual_model_id=False,
                        allow_fallback=False,
                        require_paid_call_confirmation=True,
                        expected_revision=1,
                    ),
                    principal=principal,
                    idempotency_key=uuid.uuid4(),
                    request_id=uuid.uuid4(),
                )
                assert order.index("credentials") < order.index("grants")
                assert order.index("grants") < order.index("project_policy")
                assert order.index("project_policy") < order.index("project_budget_policy")
                assert order.index("project_budget_policy") < order.index("project_counter")
            async with session_factory() as session:
                service = _phase3a_service(session)
                pending, _ = await service._create_pending_invocation(
                    payload=request,
                    principal=principal,
                    idempotency_key=uuid.uuid4(),
                    request_id=uuid.uuid4(),
                )
                with pytest.raises(AdmissionRejectedError):
                    await service._admit_attempt(
                        invocation_id=pending.id,
                        payload=request,
                        principal=principal,
                        attempt_number=1,
                        retry_of_attempt_id=None,
                    )
            async with session_factory() as session:
                limits = (
                    await session.execute(
                        text(
                            """
                            SELECT
                                (SELECT limit_minor_units FROM user_budget_counters
                                 WHERE user_id = :user_id ORDER BY window_start DESC LIMIT 1),
                                (SELECT limit_minor_units FROM project_budget_counters
                                 WHERE project_id = :project_id ORDER BY window_start DESC LIMIT 1)
                            """
                        ),
                        {"user_id": user_id, "project_id": project_id},
                    )
                ).one()
                assert limits == (10_000, 5_000)
        finally:
            await engine.dispose()

    asyncio.run(exercise())


def test_phase3a_idempotency_and_active_attempt_concurrency_are_database_arbitrated(
    temporary_database: TemporaryDatabase,
) -> None:
    temporary_database_url = temporary_database.url
    temporary_database_name = temporary_database.name
    user_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    second_project_id = uuid.uuid4()
    principal_id = "phase3a-concurrency-owner"
    _run_alembic(temporary_database_url, "upgrade", "head")
    with (
        psycopg.connect(
            **_connection_kwargs(temporary_database_url, temporary_database_name)
        ) as connection,
        connection.transaction(),
    ):
        _seed_phase3a_user_and_project(
            connection,
            user_id=user_id,
            project_id=project_id,
            principal_id=principal_id,
        )
        now = datetime.now(UTC)
        connection.execute(
            """
            INSERT INTO user_accounts (id, display_name, is_active, created_at, updated_at)
            VALUES (%s, %s, true, %s, %s)
            """,
            (other_user_id, "Other idempotency user", now, now),
        )
        connection.execute(
            """
            INSERT INTO paint_projects (
                id, owner_principal_id, title, requested_target_style,
                planning_mode, status, created_at, updated_at
            ) VALUES (%s, %s, %s, 'cel_shading', 'planning_only_demo', 'DRAFT', %s, %s)
            """,
            (second_project_id, principal_id, "Second scope project", now, now),
        )

    async def exercise() -> None:
        engine = create_async_engine(
            temporary_database_url.render_as_string(hide_password=False),
            pool_pre_ping=True,
        )
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        principal = _phase3a_principal(user_id, principal_id)
        other_principal = _phase3a_principal(other_user_id, "phase3a-other-idempotency")
        try:
            async with session_factory() as session:
                service = _phase3a_service(session)
                credential, request = await _configure_phase3a_owner(
                    service,
                    principal=principal,
                    project_id=project_id,
                )
                preview = await service.preview_invocation(
                    payload=InvocationPreviewRequest.model_validate(
                        request.model_dump(exclude={"max_attempts", "total_elapsed_time_limit_ms"})
                    ),
                    principal=principal,
                )
                await service.create_grant(
                    credential_id=credential.id,
                    payload=CredentialGrantRequest(
                        project_id=second_project_id,
                        expected_credential_revision=credential.revision,
                    ),
                    principal=principal,
                    idempotency_key=uuid.uuid4(),
                    request_id=uuid.uuid4(),
                )
            estimate = preview.estimated_cost_minor_units
            async with session_factory() as session, session.begin():
                for table, subject_column, subject_id in (
                    ("user_budget_policies", "user_id", user_id),
                    ("project_budget_policies", "project_id", project_id),
                ):
                    await session.execute(
                        text(
                            f"UPDATE {table} SET cumulative_limit_minor_units = :limit "
                            f"WHERE {subject_column} = :subject_id"
                        ),
                        {"limit": estimate, "subject_id": subject_id},
                    )
                for table, subject_column, subject_id in (
                    ("user_budget_counters", "user_id", user_id),
                    ("project_budget_counters", "project_id", project_id),
                ):
                    await session.execute(
                        text(
                            f"UPDATE {table} SET limit_minor_units = :limit, "
                            "committed_minor_units = 0, reserved_minor_units = 0 "
                            f"WHERE {subject_column} = :subject_id"
                        ),
                        {"limit": estimate, "subject_id": subject_id},
                    )
            pending_ids = []
            for _ in range(2):
                async with session_factory() as session:
                    service = _phase3a_service(session)
                    pending, _ = await service._create_pending_invocation(
                        payload=request,
                        principal=principal,
                        idempotency_key=uuid.uuid4(),
                        request_id=uuid.uuid4(),
                    )
                    pending_ids.append(pending.id)

            async def admit(invocation_id: uuid.UUID, attempt_number: int = 1) -> Any:
                async with session_factory() as session:
                    service = _phase3a_service(session)
                    return await service._admit_attempt(
                        invocation_id=invocation_id,
                        payload=request,
                        principal=principal,
                        attempt_number=attempt_number,
                        retry_of_attempt_id=None,
                    )

            reservation_results = await asyncio.gather(
                *(admit(invocation_id) for invocation_id in pending_ids),
                return_exceptions=True,
            )
            assert sum(isinstance(result, tuple) for result in reservation_results) == 1
            assert (
                sum(isinstance(result, AdmissionRejectedError) for result in reservation_results)
                == 1
            )
            async with session_factory() as session, session.begin():
                await session.execute(
                    text(
                        """
                            UPDATE budget_reservations
                            SET state = 'released', released_at = now(), revision = revision + 1
                            WHERE state = 'reserved'
                            """
                    )
                )
                await session.execute(
                    text(
                        """
                            UPDATE user_budget_counters
                            SET limit_minor_units = 10000, reserved_minor_units = 0
                            WHERE user_id = :user_id
                            """
                    ),
                    {"user_id": user_id},
                )
                await session.execute(
                    text(
                        """
                            UPDATE project_budget_counters
                            SET limit_minor_units = 10000, reserved_minor_units = 0
                            WHERE project_id = :project_id
                            """
                    ),
                    {"project_id": project_id},
                )
                await session.execute(
                    text(
                        "UPDATE user_budget_policies SET cumulative_limit_minor_units = 10000 "
                        "WHERE user_id = :user_id"
                    ),
                    {"user_id": user_id},
                )
                await session.execute(
                    text(
                        "UPDATE project_budget_policies "
                        "SET cumulative_limit_minor_units = 10000 "
                        "WHERE project_id = :project_id"
                    ),
                    {"project_id": project_id},
                )
            async with session_factory() as session:
                service = _phase3a_service(session)
                active_pending, _ = await service._create_pending_invocation(
                    payload=request,
                    principal=principal,
                    idempotency_key=uuid.uuid4(),
                    request_id=uuid.uuid4(),
                )
            active_results = await asyncio.gather(
                admit(active_pending.id, 1),
                admit(active_pending.id, 2),
                return_exceptions=True,
            )
            assert sum(isinstance(result, tuple) for result in active_results) == 1
            assert sum(isinstance(result, AIConflictError) for result in active_results) == 1
            async with session_factory() as session:
                assert (
                    await session.execute(
                        text("SELECT count(*) FROM invocation_attempts WHERE invocation_id = :id"),
                        {"id": active_pending.id},
                    )
                ).scalar_one() == 1

            projectless_request = request.model_copy(
                update={
                    "project_id": None,
                    "credential_id": None,
                    "temporary_credential": SecretStr(f"fixture-sk-{uuid.uuid4().hex}"),
                }
            )
            duplicate_key = uuid.uuid4()

            async def create_pending(
                actor: PrincipalContext,
                payload: InvocationCreateRequest,
                key: uuid.UUID,
            ) -> tuple[uuid.UUID, bool]:
                async with session_factory() as session:
                    service = _phase3a_service(session)
                    invocation, replayed = await service._create_pending_invocation(
                        payload=payload,
                        principal=actor,
                        idempotency_key=key,
                        request_id=uuid.uuid4(),
                    )
                    return invocation.id, replayed

            duplicate_results = await asyncio.gather(
                create_pending(principal, projectless_request, duplicate_key),
                create_pending(principal, projectless_request, duplicate_key),
            )
            assert duplicate_results[0][0] == duplicate_results[1][0]
            assert {result[1] for result in duplicate_results} == {False, True}
            conflicting_request = projectless_request.model_copy(
                update={
                    "payload": projectless_request.payload.model_copy(
                        update={"fixture_input": "different canonical payload"}
                    )
                }
            )
            with pytest.raises(AIIdempotencyConflictError):
                await create_pending(principal, conflicting_request, duplicate_key)
            other_id, other_replayed = await create_pending(
                other_principal,
                projectless_request,
                duplicate_key,
            )
            assert other_replayed is False
            assert other_id != duplicate_results[0][0]
            cross_project_key = uuid.uuid4()
            first_project_id, _ = await create_pending(principal, request, cross_project_key)
            second_project_request = request.model_copy(update={"project_id": second_project_id})
            second_scope_id, _ = await create_pending(
                principal,
                second_project_request,
                cross_project_key,
            )
            assert first_project_id != second_scope_id
        finally:
            await engine.dispose()

    asyncio.run(exercise())


def test_phase3a_cancel_and_completion_commit_order_selects_one_terminal_winner(
    temporary_database: TemporaryDatabase,
) -> None:
    temporary_database_url = temporary_database.url
    temporary_database_name = temporary_database.name
    user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    principal_id = "phase3a-cancel-owner"
    _run_alembic(temporary_database_url, "upgrade", "head")
    with (
        psycopg.connect(
            **_connection_kwargs(temporary_database_url, temporary_database_name)
        ) as connection,
        connection.transaction(),
    ):
        _seed_phase3a_user_and_project(
            connection,
            user_id=user_id,
            project_id=project_id,
            principal_id=principal_id,
        )

    async def exercise() -> None:
        engine = create_async_engine(
            temporary_database_url.render_as_string(hide_password=False),
            pool_pre_ping=True,
        )
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        adapter = FixtureProviderAdapter()
        principal = _phase3a_principal(user_id, principal_id)
        try:
            async with session_factory() as session:
                service = _phase3a_service(session, adapter=adapter)
                _, request = await _configure_phase3a_owner(
                    service,
                    principal=principal,
                    project_id=project_id,
                )

            async def prepare_running() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, Any]:
                async with session_factory() as session:
                    service = _phase3a_service(session, adapter=adapter)
                    invocation, _ = await service._create_pending_invocation(
                        payload=request,
                        principal=principal,
                        idempotency_key=uuid.uuid4(),
                        request_id=uuid.uuid4(),
                    )
                    attempt_id, reservation_id, secret, _ = await service._admit_attempt(
                        invocation_id=invocation.id,
                        payload=request,
                        principal=principal,
                        attempt_number=1,
                        retry_of_attempt_id=None,
                    )
                    assert await service._commit_dispatch(
                        invocation_id=invocation.id,
                        attempt_id=attempt_id,
                        reservation_id=reservation_id,
                    )
                    result = adapter.invoke(
                        request.payload.model_dump(mode="json"),
                        secret,
                        scenario=request.payload.scenario,
                    )
                    return invocation.id, attempt_id, reservation_id, result

            cancel_first = await prepare_running()
            async with session_factory() as session:
                service = _phase3a_service(session, adapter=adapter)
                cancel_response = await service.cancel_invocation(
                    invocation_id=cancel_first[0],
                    principal=principal,
                    request_id=uuid.uuid4(),
                    idempotency_key=uuid.uuid4(),
                )
                assert cancel_response.status == "running"
            async with session_factory() as session:
                service = _phase3a_service(session, adapter=adapter)
                assert (
                    await service._terminalize_attempt(
                        invocation_id=cancel_first[0],
                        attempt_id=cancel_first[1],
                        reservation_id=cancel_first[2],
                        principal=principal,
                        request_id=uuid.uuid4(),
                        result=cancel_first[3],
                        error=None,
                        can_retry=False,
                    )
                    is False
                )
            async with session_factory() as session:
                cancel_winner = (
                    await session.execute(
                        text(
                            """
                            SELECT status, final_attempt_id, output_reference
                            FROM invocation_requests WHERE id = :id
                            """
                        ),
                        {"id": cancel_first[0]},
                    )
                ).one()
                assert cancel_winner == ("cancelled", None, None)
                assert (
                    await session.execute(
                        text(
                            """
                            SELECT count(*) FROM ai_invocation_events
                            WHERE invocation_id = :id AND event_type = 'late_result_received'
                            """
                        ),
                        {"id": cancel_first[0]},
                    )
                ).scalar_one() == 1
                assert (
                    await session.execute(
                        text(
                            """
                            SELECT count(*) FROM ai_cost_ledger
                            WHERE invocation_id = :id AND source = 'late_fixture_reconciliation'
                            """
                        ),
                        {"id": cancel_first[0]},
                    )
                ).scalar_one() == 1

            completion_first = await prepare_running()
            async with session_factory() as session:
                service = _phase3a_service(session, adapter=adapter)
                assert (
                    await service._terminalize_attempt(
                        invocation_id=completion_first[0],
                        attempt_id=completion_first[1],
                        reservation_id=completion_first[2],
                        principal=principal,
                        request_id=uuid.uuid4(),
                        result=completion_first[3],
                        error=None,
                        can_retry=False,
                    )
                    is False
                )
            async with session_factory() as session:
                service = _phase3a_service(session, adapter=adapter)
                completion_winner = await service.cancel_invocation(
                    invocation_id=completion_first[0],
                    principal=principal,
                    request_id=uuid.uuid4(),
                    idempotency_key=uuid.uuid4(),
                )
                assert completion_winner.status == "succeeded"
                assert completion_winner.final_attempt_id == completion_first[1]
        finally:
            await engine.dispose()

    asyncio.run(exercise())


@pytest.mark.parametrize("winning_change", ("release", "dispatch_evidence"))
def test_phase3a_recovery_refreshes_locked_current_state_after_lock_wait(
    temporary_database: TemporaryDatabase,
    winning_change: str,
) -> None:
    temporary_database_url = temporary_database.url
    temporary_database_name = temporary_database.name
    connection_kwargs = _connection_kwargs(temporary_database_url, temporary_database_name)
    user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    principal_id = f"phase3a-locked-recovery-{winning_change}"
    _run_alembic(temporary_database_url, "upgrade", "head")
    with (
        psycopg.connect(**connection_kwargs) as connection,
        connection.transaction(),
    ):
        _seed_phase3a_user_and_project(
            connection,
            user_id=user_id,
            project_id=project_id,
            principal_id=principal_id,
        )

    adapter = FixtureProviderAdapter()
    original_invoke = adapter.invoke
    adapter_calls = 0

    def counted_invoke(*args: Any, **kwargs: Any) -> Any:
        nonlocal adapter_calls
        adapter_calls += 1
        return original_invoke(*args, **kwargs)

    adapter.invoke = counted_invoke  # type: ignore[method-assign]
    principal = _phase3a_principal(user_id, principal_id)

    async def prepare_admission() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
        engine = create_async_engine(
            temporary_database_url.render_as_string(hide_password=False),
            pool_pre_ping=True,
        )
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with session_factory() as session:
                service = _phase3a_service(session, adapter=adapter)
                _, request = await _configure_phase3a_owner(
                    service,
                    principal=principal,
                    project_id=project_id,
                )
                invocation, _ = await service._create_pending_invocation(
                    payload=request,
                    principal=principal,
                    idempotency_key=uuid.uuid4(),
                    request_id=uuid.uuid4(),
                )
                attempt_id, reservation_id, _, _ = await service._admit_attempt(
                    invocation_id=invocation.id,
                    payload=request,
                    principal=principal,
                    attempt_number=1,
                    retry_of_attempt_id=None,
                )
                return invocation.id, attempt_id, reservation_id
        finally:
            await engine.dispose()

    invocation_id, attempt_id, reservation_id = asyncio.run(prepare_admission())
    with (
        psycopg.connect(**connection_kwargs) as connection,
        connection.transaction(),
    ):
        connection.execute(
            """
            UPDATE budget_reservations
            SET admission_expires_at = now() - interval '1 second'
            WHERE id = %s
            """,
            (reservation_id,),
        )
        reservation_context = connection.execute(
            """
            SELECT user_counter_id, project_counter_id, reserved_amount
            FROM budget_reservations WHERE id = %s
            """,
            (reservation_id,),
        ).fetchone()
        assert reservation_context is not None
        user_counter_id, project_counter_id, reserved_amount = reservation_context
        assert project_counter_id is not None
        counters_before = connection.execute(
            """
            SELECT u.reserved_minor_units, p.reserved_minor_units
            FROM user_budget_counters u
            JOIN project_budget_counters p ON p.id = %s
            WHERE u.id = %s
            """,
            (project_counter_id, user_counter_id),
        ).fetchone()
        assert counters_before is not None

    recovery_ready = Event()
    lock_wait_observed = Event()
    recovery_result: Future[int] = Future()
    recovery_backend_pid: dict[str, int] = {}

    def recovery_worker() -> None:
        async def run_recovery() -> int:
            engine = create_async_engine(
                temporary_database_url.render_as_string(hide_password=False),
                pool_pre_ping=True,
            )
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            try:
                async with session_factory() as session:
                    backend_pid = (
                        await session.execute(text("SELECT pg_backend_pid()"))
                    ).scalar_one()
                    await session.rollback()
                    recovery_backend_pid["value"] = backend_pid
                    recovery_ready.set()
                    service = _phase3a_service(session, adapter=adapter)
                    return await service.recover_expired_admissions(limit=20)
            finally:
                await engine.dispose()

        try:
            recovery_result.set_result(asyncio.run(run_recovery()))
        except BaseException as error:
            recovery_ready.set()
            recovery_result.set_exception(error)

    worker = Thread(target=recovery_worker, name=f"phase3a-recovery-{winning_change}")
    blocker_error: BaseException | None = None
    blocker_pid = -1
    worker_started = False
    try:
        with (
            psycopg.connect(**connection_kwargs) as blocker_connection,
            blocker_connection.transaction(),
        ):
            blocker_pid = blocker_connection.execute("SELECT pg_backend_pid()").fetchone()[0]
            blocker_connection.execute(
                "SELECT id FROM user_accounts WHERE id = %s FOR UPDATE",
                (user_id,),
            )
            blocker_connection.execute(
                "SELECT id FROM paint_projects WHERE id = %s FOR UPDATE",
                (project_id,),
            )
            blocker_connection.execute(
                "SELECT id FROM user_budget_counters WHERE id = %s FOR UPDATE",
                (user_counter_id,),
            )
            blocker_connection.execute(
                "SELECT id FROM project_budget_counters WHERE id = %s FOR UPDATE",
                (project_counter_id,),
            )
            blocker_connection.execute(
                "SELECT id FROM invocation_requests WHERE id = %s FOR UPDATE",
                (invocation_id,),
            )
            blocker_connection.execute(
                "SELECT id FROM invocation_attempts WHERE id = %s FOR UPDATE",
                (attempt_id,),
            )
            blocker_connection.execute(
                "SELECT id FROM budget_reservations WHERE id = %s FOR UPDATE",
                (reservation_id,),
            )
            if winning_change == "release":
                blocker_connection.execute(
                    """
                        UPDATE user_budget_counters
                        SET reserved_minor_units = reserved_minor_units - %s,
                            revision = revision + 1
                        WHERE id = %s
                        """,
                    (reserved_amount, user_counter_id),
                )
                blocker_connection.execute(
                    """
                        UPDATE project_budget_counters
                        SET reserved_minor_units = reserved_minor_units - %s,
                            revision = revision + 1
                        WHERE id = %s
                        """,
                    (reserved_amount, project_counter_id),
                )
                blocker_connection.execute(
                    """
                        UPDATE budget_reservations
                        SET state = 'released', released_at = now(), revision = revision + 1
                        WHERE id = %s
                        """,
                    (reservation_id,),
                )
                blocker_connection.execute(
                    """
                        UPDATE invocation_attempts
                        SET status = 'failed', final_error_category = 'dispatch_not_started',
                            terminal_at = now(), revision = revision + 1
                        WHERE id = %s
                        """,
                    (attempt_id,),
                )
                blocker_connection.execute(
                    """
                        UPDATE invocation_requests
                        SET status = 'failed', final_attempt_id = NULL,
                            final_error_category = 'dispatch_not_started',
                            terminal_at = now(), updated_at = now(), revision = revision + 1
                        WHERE id = %s
                        """,
                    (invocation_id,),
                )
                blocker_connection.execute(
                    """
                        INSERT INTO ai_invocation_events (
                            id, invocation_id, attempt_id, event_type,
                            from_status, to_status, safe_metadata, created_at
                        ) VALUES (
                            %s, %s, %s, 'admission_recovered',
                            'admitted', 'failed', '{}'::jsonb, now()
                        )
                        """,
                    (uuid.uuid4(), invocation_id, attempt_id),
                )
            else:
                blocker_connection.execute(
                    """
                        UPDATE budget_reservations
                        SET dispatch_committed_at = now(), revision = revision + 1
                        WHERE id = %s
                        """,
                    (reservation_id,),
                )

            worker.start()
            worker_started = True
            assert recovery_ready.wait(timeout=10), "recovery worker did not expose its PID"
            if recovery_result.done():
                recovery_result.result()
            waiter_pid = recovery_backend_pid["value"]
            assert waiter_pid != blocker_pid
            deadline = monotonic() + 10
            with psycopg.connect(**connection_kwargs, autocommit=True) as observer_connection:
                while monotonic() < deadline:
                    wait_state = observer_connection.execute(
                        """
                            SELECT wait_event_type, pg_blocking_pids(pid), query
                            FROM pg_stat_activity WHERE pid = %s
                            """,
                        (waiter_pid,),
                    ).fetchone()
                    if (
                        wait_state is not None
                        and wait_state[0] == "Lock"
                        and blocker_pid in wait_state[1]
                        and "user_accounts" in wait_state[2]
                        and "FOR UPDATE" in wait_state[2]
                    ):
                        lock_wait_observed.set()
                        break
                    if recovery_result.done():
                        recovery_result.result()
                        raise AssertionError("recovery completed before the locked handoff")
                    sleep(0.01)
            assert lock_wait_observed.is_set(), "PostgreSQL row-lock wait was not observed"
            assert not recovery_result.done()
    except BaseException as error:
        blocker_error = error

    worker_result: int | None = None
    worker_error: BaseException | None = None
    if worker_started:
        try:
            worker_result = recovery_result.result(timeout=10)
        except BaseException as error:
            worker_error = error
        finally:
            worker.join(timeout=10)
    if blocker_error is not None and worker_error is not None:
        raise BaseExceptionGroup(
            "lock-holder proof and recovery worker both failed",
            [blocker_error, worker_error],
        )
    if blocker_error is not None:
        raise blocker_error
    if worker_error is not None:
        raise worker_error
    assert not worker.is_alive()
    assert worker_result == 0
    assert adapter_calls == 0

    async def recover_again() -> int:
        engine = create_async_engine(
            temporary_database_url.render_as_string(hide_password=False),
            pool_pre_ping=True,
        )
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with session_factory() as session:
                service = _phase3a_service(session, adapter=adapter)
                return await service.recover_expired_admissions(limit=20)
        finally:
            await engine.dispose()

    assert asyncio.run(recover_again()) == 0
    assert adapter_calls == 0
    with psycopg.connect(**connection_kwargs) as connection:
        final_state = connection.execute(
            """
            SELECT r.state, r.released_at, r.dispatch_committed_at,
                   a.status, a.final_error_category, a.dispatched_at,
                   i.status, i.final_error_category,
                   u.reserved_minor_units, p.reserved_minor_units
            FROM budget_reservations r
            JOIN invocation_attempts a ON a.id = r.attempt_id
            JOIN invocation_requests i ON i.id = r.invocation_id
            JOIN user_budget_counters u ON u.id = r.user_counter_id
            JOIN project_budget_counters p ON p.id = r.project_counter_id
            WHERE r.id = %s
            """,
            (reservation_id,),
        ).fetchone()
        assert final_state is not None
        event_counts = dict(
            connection.execute(
                """
                SELECT event_type, count(*)
                FROM ai_invocation_events
                WHERE invocation_id = %s
                  AND event_type IN ('admission_recovered', 'recovery_reconciliation_required')
                GROUP BY event_type
                """,
                (invocation_id,),
            ).fetchall()
        )
        ledger_counts = connection.execute(
            """
            SELECT
                (SELECT count(*) FROM ai_usage_ledger WHERE attempt_id = %s),
                (SELECT count(*) FROM ai_cost_ledger WHERE attempt_id = %s)
            """,
            (attempt_id, attempt_id),
        ).fetchone()
        assert ledger_counts == (0, 0)
        if winning_change == "release":
            assert final_state[:8] == (
                "released",
                final_state[1],
                None,
                "failed",
                "dispatch_not_started",
                None,
                "failed",
                "dispatch_not_started",
            )
            assert final_state[1] is not None
            assert final_state[8:] == (
                counters_before[0] - reserved_amount,
                counters_before[1] - reserved_amount,
            )
            assert event_counts == {"admission_recovered": 1}
        else:
            assert final_state[:8] == (
                "reconciliation_required",
                None,
                final_state[2],
                "outcome_unknown",
                "dispatch_evidence_present",
                None,
                "outcome_unknown",
                "dispatch_evidence_present",
            )
            assert final_state[2] is not None
            assert final_state[8:] == counters_before
            assert event_counts == {"recovery_reconciliation_required": 1}


def test_phase3a_orphan_recovery_requires_proof_dispatch_never_started(
    temporary_database: TemporaryDatabase,
) -> None:
    temporary_database_url = temporary_database.url
    temporary_database_name = temporary_database.name
    user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    principal_id = "phase3a-recovery-owner"
    _run_alembic(temporary_database_url, "upgrade", "head")
    with (
        psycopg.connect(
            **_connection_kwargs(temporary_database_url, temporary_database_name)
        ) as connection,
        connection.transaction(),
    ):
        _seed_phase3a_user_and_project(
            connection,
            user_id=user_id,
            project_id=project_id,
            principal_id=principal_id,
        )

    async def exercise() -> None:
        engine = create_async_engine(
            temporary_database_url.render_as_string(hide_password=False),
            pool_pre_ping=True,
        )
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        adapter = FixtureProviderAdapter()
        original_invoke = adapter.invoke
        adapter_calls = 0

        def counted_invoke(*args: Any, **kwargs: Any) -> Any:
            nonlocal adapter_calls
            adapter_calls += 1
            return original_invoke(*args, **kwargs)

        adapter.invoke = counted_invoke  # type: ignore[method-assign]
        principal = _phase3a_principal(user_id, principal_id)
        try:
            async with session_factory() as session:
                service = _phase3a_service(session, adapter=adapter)
                _, request = await _configure_phase3a_owner(
                    service,
                    principal=principal,
                    project_id=project_id,
                    cumulative_limit_minor_units=100_000,
                )
            rows: list[tuple[uuid.UUID, uuid.UUID, uuid.UUID]] = []
            for _ in range(8):
                async with session_factory() as session:
                    service = _phase3a_service(session, adapter=adapter)
                    invocation, _ = await service._create_pending_invocation(
                        payload=request,
                        principal=principal,
                        idempotency_key=uuid.uuid4(),
                        request_id=uuid.uuid4(),
                    )
                    attempt_id, reservation_id, _, _ = await service._admit_attempt(
                        invocation_id=invocation.id,
                        payload=request,
                        principal=principal,
                        attempt_number=1,
                        retry_of_attempt_id=None,
                    )
                    rows.append((invocation.id, attempt_id, reservation_id))
            async with session_factory() as session, session.begin():
                await session.execute(
                    text(
                        """
                            UPDATE budget_reservations
                            SET admission_expires_at = now() - interval '1 second'
                            WHERE id = ANY(:ids)
                            """
                    ),
                    {"ids": [row[2] for row in rows]},
                )
                await session.execute(
                    text(
                        """
                            UPDATE budget_reservations
                            SET dispatch_committed_at = now()
                            WHERE id = :id
                            """
                    ),
                    {"id": rows[1][2]},
                )
                await session.execute(
                    text(
                        """
                            UPDATE invocation_attempts
                            SET safe_provider_metadata = safe_provider_metadata ||
                                '{"provider_request_id":"fixture-request-evidence"}'::jsonb
                            WHERE id = :id
                            """
                    ),
                    {"id": rows[2][1]},
                )
                await session.execute(
                    text(
                        """
                            INSERT INTO ai_usage_ledger (
                                id, invocation_id, attempt_id, provider_definition_id,
                                model_definition_id, source, canonical_sequence,
                                input_units, output_units, safe_metadata, created_at
                            ) VALUES (
                                :id, :invocation_id, :attempt_id, :provider_id,
                                :model_id, 'recovery_test', 1, 1, 1, '{}'::jsonb, now()
                            )
                            """
                    ),
                    {
                        "id": uuid.uuid4(),
                        "invocation_id": rows[3][0],
                        "attempt_id": rows[3][1],
                        "provider_id": FIXTURE_PROVIDER_ID,
                        "model_id": FIXTURE_TEXT_MODEL_ID,
                    },
                )
                await session.execute(
                    text(
                        """
                            INSERT INTO ai_cost_ledger (
                                id, invocation_id, attempt_id, provider_definition_id,
                                model_definition_id, source, canonical_sequence,
                                amount_minor_units, currency, created_at
                            ) VALUES (
                                :id, :invocation_id, :attempt_id, :provider_id,
                                :model_id, 'recovery_test', 1, 1, 'FIXTURE_CREDITS', now()
                            )
                            """
                    ),
                    {
                        "id": uuid.uuid4(),
                        "invocation_id": rows[4][0],
                        "attempt_id": rows[4][1],
                        "provider_id": FIXTURE_PROVIDER_ID,
                        "model_id": FIXTURE_TEXT_MODEL_ID,
                    },
                )
                await session.execute(
                    text(
                        """
                            INSERT INTO ai_invocation_events (
                                id, invocation_id, attempt_id, event_type,
                                from_status, to_status, safe_metadata, created_at
                            ) VALUES (
                                :id, :invocation_id, :attempt_id, 'dispatch_committed',
                                'admitted', 'running', '{}'::jsonb, now()
                            )
                            """
                    ),
                    {
                        "id": uuid.uuid4(),
                        "invocation_id": rows[5][0],
                        "attempt_id": rows[5][1],
                    },
                )
                await session.execute(
                    text(
                        """
                            UPDATE invocation_attempts
                            SET dispatched_at = now()
                            WHERE id = :id
                            """
                    ),
                    {"id": rows[6][1]},
                )
                await session.execute(
                    text(
                        """
                            UPDATE budget_reservations
                            SET invocation_id = :other_invocation_id
                            WHERE id = :id
                            """
                    ),
                    {"other_invocation_id": rows[0][0], "id": rows[7][2]},
                )
            async with session_factory() as session:
                reserved_before = (
                    await session.execute(
                        text(
                            """
                            SELECT reserved_minor_units
                            FROM user_budget_counters
                            WHERE user_id = :user_id
                            """
                        ),
                        {"user_id": user_id},
                    )
                ).scalar_one()
                project_reserved_before = (
                    await session.execute(
                        text(
                            """
                            SELECT reserved_minor_units
                            FROM project_budget_counters
                            WHERE project_id = :project_id
                            """
                        ),
                        {"project_id": project_id},
                    )
                ).scalar_one()
                clean_reserved_amount = (
                    await session.execute(
                        text("SELECT reserved_amount FROM budget_reservations WHERE id = :id"),
                        {"id": rows[0][2]},
                    )
                ).scalar_one()
                service = _phase3a_service(session, adapter=adapter)
                assert await service.recover_expired_admissions(limit=20) == 1
                assert adapter_calls == 0
            async with session_factory() as session:
                reserved_after_first_recovery = (
                    await session.execute(
                        text(
                            """
                            SELECT reserved_minor_units
                            FROM user_budget_counters
                            WHERE user_id = :user_id
                            """
                        ),
                        {"user_id": user_id},
                    )
                ).scalar_one()
                assert reserved_after_first_recovery == reserved_before - clean_reserved_amount
                project_reserved_after_first_recovery = (
                    await session.execute(
                        text(
                            """
                            SELECT reserved_minor_units
                            FROM project_budget_counters
                            WHERE project_id = :project_id
                            """
                        ),
                        {"project_id": project_id},
                    )
                ).scalar_one()
                assert (
                    project_reserved_after_first_recovery
                    == project_reserved_before - clean_reserved_amount
                )
                service = _phase3a_service(session, adapter=adapter)
                assert await service.recover_expired_admissions(limit=20) == 0
                assert adapter_calls == 0
            async with session_factory() as session:
                clean = (
                    await session.execute(
                        text(
                            """
                            SELECT r.state, a.status, a.final_error_category,
                                   i.status, i.final_attempt_id
                            FROM budget_reservations r
                            JOIN invocation_attempts a ON a.id = r.attempt_id
                            JOIN invocation_requests i ON i.id = a.invocation_id
                            WHERE r.id = :id
                            """
                        ),
                        {"id": rows[0][2]},
                    )
                ).one()
                assert clean == ("released", "failed", "dispatch_not_started", "failed", None)
                protected_states = (
                    await session.execute(
                        text(
                            """
                            SELECT id, state FROM budget_reservations
                            WHERE id = ANY(:ids) ORDER BY id
                            """
                        ),
                        {"ids": [row[2] for row in rows[1:7]]},
                    )
                ).all()
                assert {state for _, state in protected_states} == {"reconciliation_required"}
                dispatched_at_case = (
                    await session.execute(
                        text(
                            """
                            SELECT r.state, r.released_at, a.status,
                                   a.final_error_category, a.dispatched_at
                            FROM budget_reservations r
                            JOIN invocation_attempts a ON a.id = r.attempt_id
                            WHERE r.id = :id
                            """
                        ),
                        {"id": rows[6][2]},
                    )
                ).one()
                assert dispatched_at_case[:4] == (
                    "reconciliation_required",
                    None,
                    "outcome_unknown",
                    "dispatch_evidence_present",
                )
                assert dispatched_at_case.dispatched_at is not None
                mismatch_state = (
                    await session.execute(
                        text("SELECT state FROM budget_reservations WHERE id = :id"),
                        {"id": rows[7][2]},
                    )
                ).scalar_one()
                assert mismatch_state == "reserved"
                reserved_after_second_recovery = (
                    await session.execute(
                        text(
                            """
                            SELECT reserved_minor_units
                            FROM user_budget_counters
                            WHERE user_id = :user_id
                            """
                        ),
                        {"user_id": user_id},
                    )
                ).scalar_one()
                assert reserved_after_second_recovery == reserved_after_first_recovery
                project_reserved_after_second_recovery = (
                    await session.execute(
                        text(
                            """
                            SELECT reserved_minor_units
                            FROM project_budget_counters
                            WHERE project_id = :project_id
                            """
                        ),
                        {"project_id": project_id},
                    )
                ).scalar_one()
                assert (
                    project_reserved_after_second_recovery == project_reserved_after_first_recovery
                )
        finally:
            await engine.dispose()

    asyncio.run(exercise())


def test_phase3a_fixture_seed_downgrade_refuses_references_then_deletes_exact_seed(
    temporary_database: TemporaryDatabase,
) -> None:
    temporary_database_url = temporary_database.url
    temporary_database_name = temporary_database.name
    user_id = uuid.uuid4()
    preference_id = uuid.uuid4()
    project_id = uuid.uuid4()
    policy_id = uuid.uuid4()
    _run_alembic(temporary_database_url, "upgrade", "head")
    with (
        psycopg.connect(
            **_connection_kwargs(temporary_database_url, temporary_database_name)
        ) as connection,
        connection.transaction(),
    ):
        connection.execute(
            "INSERT INTO user_accounts (id, display_name) VALUES (%s, %s)",
            (user_id, "Fixture downgrade guard"),
        )
        connection.execute(
            """
            INSERT INTO user_provider_preferences (
                id, user_id, enabled, default_provider_definition_id,
                timeout_ms, streaming_enabled, revision, updated_at
            ) VALUES (%s, %s, false, %s, 30000, false, 1, now())
            """,
            (preference_id, user_id, FIXTURE_PROVIDER_ID),
        )

    with pytest.raises(AssertionError, match="fixture Registry identities are referenced"):
        _run_alembic(temporary_database_url, "downgrade", "3a03e9a1d6f4")
    assert "4c01a2b3c4d5 (head)" in _run_alembic(temporary_database_url, "current").stdout
    with (
        psycopg.connect(
            **_connection_kwargs(temporary_database_url, temporary_database_name)
        ) as connection,
        connection.transaction(),
    ):
        assert connection.execute(
            "SELECT default_provider_definition_id FROM user_provider_preferences WHERE id = %s",
            (preference_id,),
        ).fetchone() == (FIXTURE_PROVIDER_ID,)
        connection.execute("DELETE FROM user_provider_preferences WHERE id = %s", (preference_id,))

    with (
        psycopg.connect(
            **_connection_kwargs(temporary_database_url, temporary_database_name)
        ) as connection,
        connection.transaction(),
    ):
        connection.execute(
            """
            INSERT INTO user_provider_preferences (
                id, user_id, enabled, default_model_definition_id,
                timeout_ms, streaming_enabled, revision, updated_at
            ) VALUES (%s, %s, false, %s, 30000, false, 1, now())
            """,
            (preference_id, user_id, FIXTURE_TEXT_MODEL_ID),
        )
    with pytest.raises(AssertionError, match="fixture Registry identities are referenced"):
        _run_alembic(temporary_database_url, "downgrade", "3a03e9a1d6f4")
    with (
        psycopg.connect(
            **_connection_kwargs(temporary_database_url, temporary_database_name)
        ) as connection,
        connection.transaction(),
    ):
        connection.execute("DELETE FROM user_provider_preferences WHERE id = %s", (preference_id,))
        now = datetime.now(UTC)
        connection.execute(
            """
            INSERT INTO paint_projects (
                id, owner_principal_id, title, requested_target_style,
                planning_mode, status, created_at, updated_at
            ) VALUES (%s, 'fixture-downgrade-owner', 'Capability guard',
                      'cel_shading', 'planning_only_demo', 'DRAFT', %s, %s)
            """,
            (project_id, now, now),
        )
        connection.execute(
            """
            INSERT INTO project_model_policies (
                id, project_id, enabled, per_invocation_limit_minor_units,
                currency, allow_unknown_cost, unknown_cost_reservation_minor_units,
                allow_manual_model_id, allow_fallback, require_paid_call_confirmation,
                updated_by_user_id, revision, updated_at
            ) VALUES (%s, %s, false, 1, 'FIXTURE_CREDITS', false, 0,
                      false, false, true, %s, 1, now())
            """,
            (policy_id, project_id, user_id),
        )
        connection.execute(
            """
            INSERT INTO project_model_policy_capabilities (
                id, project_model_policy_id, capability_definition_id, created_at
            ) VALUES (%s, %s, %s, now())
            """,
            (uuid.uuid4(), policy_id, FIXTURE_TEXT_CAPABILITY_ID),
        )
    with pytest.raises(AssertionError, match="fixture Registry identities are referenced"):
        _run_alembic(temporary_database_url, "downgrade", "3a03e9a1d6f4")
    with (
        psycopg.connect(
            **_connection_kwargs(temporary_database_url, temporary_database_name)
        ) as connection,
        connection.transaction(),
    ):
        connection.execute(
            "DELETE FROM project_model_policy_capabilities WHERE project_model_policy_id = %s",
            (policy_id,),
        )
        connection.execute("DELETE FROM project_model_policies WHERE id = %s", (policy_id,))
        connection.execute("DELETE FROM paint_projects WHERE id = %s", (project_id,))

    _run_alembic(temporary_database_url, "downgrade", "3a03e9a1d6f4")
    assert "3a03e9a1d6f4" in _run_alembic(temporary_database_url, "current").stdout
    with psycopg.connect(
        **_connection_kwargs(temporary_database_url, temporary_database_name)
    ) as connection:
        assert connection.execute("SELECT count(*) FROM provider_definitions").fetchone() == (0,)
        assert connection.execute("SELECT count(*) FROM model_definitions").fetchone() == (0,)
        assert connection.execute("SELECT count(*) FROM capability_definitions").fetchone() == (0,)


def test_phase3a_fixture_seed_downgrade_refuses_non_seed_model_before_delete(
    temporary_database: TemporaryDatabase,
) -> None:
    temporary_database_url = temporary_database.url
    temporary_database_name = temporary_database.name
    extra_model_id = uuid.uuid4()
    _run_alembic(temporary_database_url, "upgrade", "head")
    with (
        psycopg.connect(
            **_connection_kwargs(temporary_database_url, temporary_database_name)
        ) as connection,
        connection.transaction(),
    ):
        connection.execute(
            """
            INSERT INTO model_definitions (
                id, provider_definition_id, provider_key, model_id, display_name,
                catalog_source, catalog_fresh_at, catalog_status, status,
                context_window, supports_structured_output, supports_vision,
                pricing_minor_units, pricing_currency, revision, created_at, updated_at
            ) VALUES (
                %s, %s, 'fixture_local', %s, 'Synthetic non-seed fixture model',
                'synthetic_test', now(), 'bundled', 'active', 1024,
                false, false, 1, 'FIXTURE_CREDITS', 1, now(), now()
            )
            """,
            (extra_model_id, FIXTURE_PROVIDER_ID, f"fixture-extra-{extra_model_id.hex}"),
        )

    with pytest.raises(
        AssertionError,
        match="fixture provider still has non-seed model references",
    ) as downgrade_error:
        _run_alembic(temporary_database_url, "downgrade", "3a03e9a1d6f4")
    assert "ForeignKeyViolation" not in str(downgrade_error.value)
    assert "4c01a2b3c4d5 (head)" in _run_alembic(temporary_database_url, "current").stdout
    with psycopg.connect(
        **_connection_kwargs(temporary_database_url, temporary_database_name)
    ) as connection:
        assert connection.execute(
            """
            SELECT provider_definition_id FROM model_definitions WHERE id = %s
            """,
            (extra_model_id,),
        ).fetchone() == (FIXTURE_PROVIDER_ID,)
        assert {
            row[0]
            for row in connection.execute(
                """
                SELECT id FROM model_definitions
                WHERE id = ANY(%s)
                """,
                ([FIXTURE_TEXT_MODEL_ID, FIXTURE_VISION_MODEL_ID],),
            ).fetchall()
        } == {
            FIXTURE_TEXT_MODEL_ID,
            FIXTURE_VISION_MODEL_ID,
        }
        assert connection.execute(
            "SELECT count(*) FROM provider_definitions WHERE id = %s",
            (FIXTURE_PROVIDER_ID,),
        ).fetchone() == (1,)
        assert connection.execute(
            "SELECT count(*) FROM provider_capabilities WHERE provider_definition_id = %s",
            (FIXTURE_PROVIDER_ID,),
        ).fetchone() == (3,)
        assert connection.execute(
            """
            SELECT count(*) FROM model_capabilities
            WHERE model_definition_id = ANY(%s)
            """,
            ([FIXTURE_TEXT_MODEL_ID, FIXTURE_VISION_MODEL_ID],),
        ).fetchone() == (5,)
