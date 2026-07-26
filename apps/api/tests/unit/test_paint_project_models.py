"""Contract tests for the Phase 1D-1B ORM metadata."""

import ast
import re
import subprocess
import sys
import uuid
from collections.abc import Iterable
from pathlib import Path
from types import MappingProxyType

import pytest
from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.schema import Table, UniqueConstraint

from creativedeploy_api.db import Base
from creativedeploy_api.db.models import (
    REGISTERED_MODELS,
    CommandIdempotencyRecord,
    PaintProject,
    StateTransitionEvent,
)
from creativedeploy_api.db.models.constants import (
    ACTOR_TYPES,
    IDEMPOTENCY_STATUS_COMPLETED,
    IDEMPOTENCY_STATUS_IN_PROGRESS,
    MACHINE_TOKEN_PATTERN,
    PAYLOAD_HASH_PATTERN,
    PHYSICAL_STRING_LENGTHS,
    PLANNING_MODE_DEMO,
    POSTGRESQL_MACHINE_TOKEN_PATTERN,
    TARGET_STYLE_CEL_SHADING,
    WORKFLOW_STATES,
)

EXPECTED_TABLES = frozenset(
    {
        "command_idempotency_records",
        "paint_projects",
        "state_transition_events",
    }
)
EXPECTED_CONSTRAINT_NAMES = frozenset(
    {
        "ck_command_idempotency_records_command_type_format",
        "ck_command_idempotency_records_execution_status_allowed",
        "ck_command_idempotency_records_execution_status_format",
        "ck_command_idempotency_records_expiry_after_creation",
        "ck_command_idempotency_records_http_status_valid",
        "ck_command_idempotency_records_payload_hash_format",
        "ck_command_idempotency_records_principal_id_normalized",
        "ck_command_idempotency_records_resource_type_format",
        "ck_command_idempotency_records_response_snapshot_is_object",
        "ck_command_idempotency_records_result_matches_execution_status",
        "ck_command_idempotency_records_scope_key_normalized",
        "ck_paint_projects_description_normalized",
        "ck_paint_projects_owner_principal_id_normalized",
        "ck_paint_projects_planning_mode_allowed",
        "ck_paint_projects_planning_mode_format",
        "ck_paint_projects_requested_target_style_allowed",
        "ck_paint_projects_requested_target_style_format",
        "ck_paint_projects_status_allowed",
        "ck_paint_projects_title_normalized",
        "ck_paint_projects_title_not_blank",
        "ck_paint_projects_updated_at_not_before_created_at",
        "ck_state_transition_events_actor_display_snapshot_normalized",
        "ck_state_transition_events_actor_principal_id_normalized",
        "ck_state_transition_events_actor_type_allowed",
        "ck_state_transition_events_actor_type_format",
        "ck_state_transition_events_create_project_reason",
        "ck_state_transition_events_event_format",
        "ck_state_transition_events_event_metadata_is_object",
        "ck_state_transition_events_from_state_allowed",
        "ck_state_transition_events_reason_format",
        "ck_state_transition_events_to_state_allowed",
        "ck_state_transition_events_user_display_name_required",
        "fk_state_transition_events_project_id_paint_projects",
        "pk_command_idempotency_records",
        "pk_paint_projects",
        "pk_state_transition_events",
        "uq_command_idempotency_records_scope_key_idempotency_key",
    }
)
EXPECTED_INDEX_NAMES = frozenset(
    {
        "ix_command_idempotency_records_expires_at",
        "ix_paint_projects_owner_updated_at_id",
        "ix_state_transition_events_project_created_at_id",
    }
)
EXPECTED_DATABASE_IDENTIFIERS = EXPECTED_TABLES | EXPECTED_CONSTRAINT_NAMES | EXPECTED_INDEX_NAMES
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
EXPECTED_PHYSICAL_STRING_LENGTHS = MappingProxyType(
    {
        "owner_principal_id": 128,
        "title": 80,
        "description": 500,
        "requested_target_style": 32,
        "planning_mode": 32,
        "status": 64,
        "from_state": 64,
        "to_state": 64,
        "event": 64,
        "actor_type": 32,
        "actor_principal_id": 128,
        "actor_display_name_snapshot": 200,
        "reason": 128,
        "scope_key": 512,
        "principal_id": 128,
        "command_type": 64,
        "payload_hash": 64,
        "execution_status": 32,
        "resource_type": 64,
    }
)
EXPECTED_ACTOR_TYPES = ("user", "api", "worker", "system")
EXPECTED_MACHINE_TOKEN_PATTERN = r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$"
EXPECTED_POSTGRESQL_MACHINE_TOKEN_PATTERN = r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$"
EXPECTED_PAYLOAD_HASH_PATTERN = r"^[0-9a-f]{64}$"
EXPECTED_TARGET_STYLE = "cel_shading"
EXPECTED_PLANNING_MODE = "planning_only_demo"
EXPECTED_IDEMPOTENCY_STATUSES = ("in_progress", "completed")
EXPECTED_CREATE_EVENT = "create_project"
EXPECTED_CREATE_REASON = "project_created"
EXPECTED_USER_ACTOR_TYPE = "user"
VALID_MACHINE_TOKENS = ("user", "create_project", "paint_project", "state2", "step_2")
INVALID_MACHINE_TOKENS = (
    "User",
    "create-project",
    "create project",
    "_create",
    "create_",
    "create__project",
    "2create",
    "",
)
EXPECTED_POSTGRESQL_MACHINE_TOKEN_CONSTRAINTS = MappingProxyType(
    {
        "ck_command_idempotency_records_command_type_format": ("command_idempotency_records"),
        "ck_command_idempotency_records_execution_status_format": ("command_idempotency_records"),
        "ck_command_idempotency_records_resource_type_format": ("command_idempotency_records"),
        "ck_paint_projects_planning_mode_format": "paint_projects",
        "ck_paint_projects_requested_target_style_format": "paint_projects",
        "ck_state_transition_events_actor_type_format": "state_transition_events",
        "ck_state_transition_events_event_format": "state_transition_events",
        "ck_state_transition_events_reason_format": "state_transition_events",
    }
)
POSTGRESQL_IDENTIFIER_LIMIT = 63
POSTGRESQL_IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9_]+$")
API_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = (
    API_ROOT / "migrations" / "versions" / "a10d3d8dab38_create_paintproject_persistence_.py"
)


def _check_constraints(table: Table) -> dict[str, CheckConstraint]:
    return {
        str(constraint.name): constraint
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }


def _constraint_sql(constraint: CheckConstraint) -> str:
    return " ".join(str(constraint.sqltext).split())


def _quoted_sql_values(constraint: CheckConstraint) -> tuple[str, ...]:
    return tuple(re.findall(r"'([^']+)'", _constraint_sql(constraint)))


def _index_columns(index: Index) -> tuple[str, ...]:
    return tuple(column.name for column in index.columns)


def _assert_string_column(table: Table, name: str, length: int, *, nullable: bool) -> None:
    column = table.c[name]
    assert isinstance(column.type, String)
    assert column.type.length == length
    assert column.nullable is nullable


def _assert_timestamps(table: Table, names: Iterable[str]) -> None:
    for name in names:
        column = table.c[name]
        assert isinstance(column.type, DateTime)
        assert column.type.timezone is True


def _metadata_identifier_categories() -> tuple[
    frozenset[str],
    frozenset[str],
    frozenset[str],
]:
    table_names: set[str] = set()
    constraint_names: set[str] = set()
    index_names: set[str] = set()
    for table in Base.metadata.tables.values():
        table_names.add(table.name)
        for constraint in table.constraints:
            assert constraint.name is not None
            constraint_names.add(str(constraint.name))
        for index in table.indexes:
            assert index.name is not None
            index_names.add(index.name)
    return (
        frozenset(table_names),
        frozenset(constraint_names),
        frozenset(index_names),
    )


def _metadata_identifiers() -> frozenset[str]:
    tables, constraints, indexes = _metadata_identifier_categories()
    return tables | constraints | indexes


def _op_formatted_identifier(node: ast.expr) -> str | None:
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "op"
        and node.func.attr == "f"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    ):
        return node.args[0].value
    return None


def _migration_identifier_categories() -> tuple[
    frozenset[str],
    frozenset[str],
    frozenset[str],
]:
    module = ast.parse(MIGRATION_PATH.read_text(encoding="utf-8"))
    table_names: set[str] = set()
    constraint_names: set[str] = set()
    index_names: set[str] = set()
    for node in ast.walk(module):
        if not isinstance(node, ast.Call):
            continue
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "op"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            if node.func.attr == "create_table":
                table_names.add(node.args[0].value)
            elif node.func.attr == "create_index":
                index_names.add(node.args[0].value)
            elif node.func.attr == "f":
                constraint_names.add(node.args[0].value)
        for keyword in node.keywords:
            if (
                keyword.arg == "name"
                and isinstance(keyword.value, ast.Constant)
                and isinstance(keyword.value.value, str)
            ):
                constraint_names.add(keyword.value.value)
    return (
        frozenset(table_names),
        frozenset(constraint_names),
        frozenset(index_names),
    )


def _migration_identifiers() -> frozenset[str]:
    tables, constraints, indexes = _migration_identifier_categories()
    return tables | constraints | indexes


def _migration_check_constraint_sql() -> dict[str, str]:
    module = ast.parse(MIGRATION_PATH.read_text(encoding="utf-8"))
    checks: dict[str, str] = {}
    for node in ast.walk(module):
        if (
            not isinstance(node, ast.Call)
            or not isinstance(node.func, ast.Attribute)
            or node.func.attr != "CheckConstraint"
            or not node.args
        ):
            continue
        sql_text = ast.literal_eval(node.args[0])
        assert isinstance(sql_text, str)
        name_keyword = next(keyword for keyword in node.keywords if keyword.arg == "name")
        constraint_name = _op_formatted_identifier(name_keyword.value)
        assert constraint_name is not None
        checks[constraint_name] = " ".join(sql_text.split())
    return checks


def test_registered_models_and_metadata_contain_exactly_three_business_tables() -> None:
    assert (
        PaintProject,
        StateTransitionEvent,
        CommandIdempotencyRecord,
    ) == REGISTERED_MODELS
    assert set(Base.metadata.tables) == EXPECTED_TABLES
    assert {model.__table__.name for model in REGISTERED_MODELS} == EXPECTED_TABLES
    assert not {
        "users",
        "workspaces",
        "tenants",
        "agent_runs",
    } & set(Base.metadata.tables)


def test_production_contract_constants_match_independent_expectations() -> None:
    assert WORKFLOW_STATES == EXPECTED_WORKFLOW_STATES
    assert len(WORKFLOW_STATES) == 16
    assert dict(PHYSICAL_STRING_LENGTHS) == dict(EXPECTED_PHYSICAL_STRING_LENGTHS)
    assert ACTOR_TYPES == EXPECTED_ACTOR_TYPES
    assert MACHINE_TOKEN_PATTERN == EXPECTED_MACHINE_TOKEN_PATTERN
    assert POSTGRESQL_MACHINE_TOKEN_PATTERN == EXPECTED_POSTGRESQL_MACHINE_TOKEN_PATTERN
    assert PAYLOAD_HASH_PATTERN == EXPECTED_PAYLOAD_HASH_PATTERN
    assert TARGET_STYLE_CEL_SHADING == EXPECTED_TARGET_STYLE
    assert PLANNING_MODE_DEMO == EXPECTED_PLANNING_MODE
    assert (
        IDEMPOTENCY_STATUS_IN_PROGRESS,
        IDEMPOTENCY_STATUS_COMPLETED,
    ) == EXPECTED_IDEMPOTENCY_STATUSES


@pytest.mark.parametrize("token", VALID_MACHINE_TOKENS)
def test_canonical_machine_token_contract_accepts_independent_valid_examples(
    token: str,
) -> None:
    assert re.fullmatch(EXPECTED_MACHINE_TOKEN_PATTERN, token)
    assert re.fullmatch(POSTGRESQL_MACHINE_TOKEN_PATTERN, token)


@pytest.mark.parametrize("token", INVALID_MACHINE_TOKENS)
def test_canonical_machine_token_contract_rejects_independent_invalid_examples(
    token: str,
) -> None:
    assert re.fullmatch(EXPECTED_MACHINE_TOKEN_PATTERN, token) is None
    assert re.fullmatch(POSTGRESQL_MACHINE_TOKEN_PATTERN, token) is None


def test_payload_hash_contract_uses_independent_examples() -> None:
    valid_hash = "0123456789abcdef" * 4

    assert re.fullmatch(EXPECTED_PAYLOAD_HASH_PATTERN, valid_hash)
    assert re.fullmatch(PAYLOAD_HASH_PATTERN, valid_hash)
    for invalid_hash in ("a" * 63, "a" * 65, "A" * 64, "g" * 64, ""):
        assert re.fullmatch(EXPECTED_PAYLOAD_HASH_PATTERN, invalid_hash) is None
        assert re.fullmatch(PAYLOAD_HASH_PATTERN, invalid_hash) is None


def test_all_database_identifiers_fit_postgresql_limit() -> None:
    identifiers = _metadata_identifiers()

    assert identifiers == EXPECTED_DATABASE_IDENTIFIERS
    assert len(identifiers) == 43
    assert all(
        len(identifier.encode("utf-8")) <= POSTGRESQL_IDENTIFIER_LIMIT for identifier in identifiers
    )
    assert all(POSTGRESQL_IDENTIFIER_PATTERN.fullmatch(identifier) for identifier in identifiers)
    assert "ck_state_transition_events_actor_display_snapshot_normalized" in identifiers
    assert "ck_state_transition_events_actor_display_name_snapshot_normalized" not in identifiers


def test_orm_and_migration_identifiers_each_match_independent_contract() -> None:
    metadata_tables, metadata_constraints, metadata_indexes = _metadata_identifier_categories()
    migration_tables, migration_constraints, migration_indexes = _migration_identifier_categories()

    assert metadata_tables == EXPECTED_TABLES
    assert metadata_constraints == EXPECTED_CONSTRAINT_NAMES
    assert metadata_indexes == EXPECTED_INDEX_NAMES
    assert migration_tables == EXPECTED_TABLES
    assert migration_constraints == EXPECTED_CONSTRAINT_NAMES
    assert migration_indexes == EXPECTED_INDEX_NAMES
    assert _metadata_identifiers() == EXPECTED_DATABASE_IDENTIFIERS
    assert _migration_identifiers() == EXPECTED_DATABASE_IDENTIFIERS
    assert _migration_identifiers() == _metadata_identifiers()
    assert all(
        len(identifier.encode("utf-8")) <= POSTGRESQL_IDENTIFIER_LIMIT
        for identifier in _migration_identifiers()
    )
    assert all(
        POSTGRESQL_IDENTIFIER_PATTERN.fullmatch(identifier)
        for identifier in _migration_identifiers()
    )
    assert not any("_8ef7" in identifier for identifier in _migration_identifiers())


def test_postgresql_machine_token_constraints_match_independent_contract() -> None:
    migration_checks = _migration_check_constraint_sql()

    for constraint_name, table_name in EXPECTED_POSTGRESQL_MACHINE_TOKEN_CONSTRAINTS.items():
        orm_checks = _check_constraints(Base.metadata.tables[table_name])
        assert EXPECTED_POSTGRESQL_MACHINE_TOKEN_PATTERN in _constraint_sql(
            orm_checks[constraint_name]
        )
        assert EXPECTED_POSTGRESQL_MACHINE_TOKEN_PATTERN in migration_checks[constraint_name]


def test_model_column_sets_are_exact() -> None:
    assert tuple(PaintProject.__table__.c.keys()) == (
        "id",
        "owner_principal_id",
        "title",
        "description",
        "requested_target_style",
        "planning_mode",
        "status",
        "created_at",
        "updated_at",
    )
    assert tuple(StateTransitionEvent.__table__.c.keys()) == (
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
    )
    assert tuple(CommandIdempotencyRecord.__table__.c.keys()) == (
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
    )
    all_columns = {
        column.name for table in Base.metadata.tables.values() for column in table.columns
    }
    assert (
        not {
            "current_image_asset_id",
            "current_region_version_id",
            "current_plan_id",
            "agent_run_id",
            "metadata",
        }
        & all_columns
    )


@pytest.mark.parametrize(
    ("table", "column_name"),
    [
        (PaintProject.__table__, "id"),
        (StateTransitionEvent.__table__, "id"),
        (StateTransitionEvent.__table__, "project_id"),
        (StateTransitionEvent.__table__, "correlation_id"),
        (CommandIdempotencyRecord.__table__, "id"),
        (CommandIdempotencyRecord.__table__, "idempotency_key"),
        (CommandIdempotencyRecord.__table__, "resource_id"),
    ],
)
def test_uuid_columns_use_native_postgresql_uuid(table: Table, column_name: str) -> None:
    column = table.c[column_name]
    assert isinstance(column.type, PostgreSQLUUID)
    assert column.type.as_uuid is True


@pytest.mark.parametrize(
    "table",
    [
        PaintProject.__table__,
        StateTransitionEvent.__table__,
        CommandIdempotencyRecord.__table__,
    ],
)
def test_uuid_primary_keys_use_python_uuid4_without_server_default(table: Table) -> None:
    column = table.c.id
    assert column.primary_key is True
    assert column.nullable is False
    assert column.default is not None
    assert callable(column.default.arg)
    assert column.default.arg.__name__ == uuid.uuid4.__name__
    assert column.server_default is None


def test_paint_project_types_nullability_and_defaults() -> None:
    table = PaintProject.__table__
    for name in (
        "owner_principal_id",
        "title",
        "description",
        "requested_target_style",
        "planning_mode",
        "status",
    ):
        _assert_string_column(
            table,
            name,
            EXPECTED_PHYSICAL_STRING_LENGTHS[name],
            nullable=name == "description",
        )
    _assert_timestamps(table, ("created_at", "updated_at"))
    assert str(table.c.requested_target_style.server_default.arg) == (f"'{EXPECTED_TARGET_STYLE}'")
    assert str(table.c.planning_mode.server_default.arg) == f"'{EXPECTED_PLANNING_MODE}'"
    assert str(table.c.status.server_default.arg) == "'DRAFT'"
    assert str(table.c.created_at.server_default.arg) == "now()"
    assert str(table.c.updated_at.server_default.arg) == "now()"


def test_state_transition_types_and_conditional_audit_nullability() -> None:
    table = StateTransitionEvent.__table__
    for name in (
        "from_state",
        "to_state",
        "event",
        "actor_type",
        "actor_principal_id",
        "actor_display_name_snapshot",
        "reason",
    ):
        _assert_string_column(
            table,
            name,
            EXPECTED_PHYSICAL_STRING_LENGTHS[name],
            nullable=name in {"from_state", "actor_display_name_snapshot", "reason"},
        )
    assert table.c.actor_display_name_snapshot.nullable is True
    assert table.c.reason.nullable is True
    assert isinstance(table.c.event_metadata.type, JSONB)
    assert table.c.event_metadata.nullable is False
    assert str(table.c.event_metadata.server_default.arg) == "'{}'::jsonb"
    _assert_timestamps(table, ("created_at",))


def test_event_metadata_default_factory_returns_isolated_empty_objects() -> None:
    column_default = StateTransitionEvent.__table__.c.event_metadata.default

    assert column_default is not None
    assert column_default.is_callable
    factory = column_default.arg
    assert callable(factory)

    first = factory(None)
    second = factory(None)

    assert isinstance(first, dict)
    assert isinstance(second, dict)
    assert first == {}
    assert second == {}
    assert first is not second

    first["mutated"] = True

    assert first == {"mutated": True}
    assert second == {}


def test_idempotency_types_nullability_and_defaults() -> None:
    table = CommandIdempotencyRecord.__table__
    for name in (
        "scope_key",
        "principal_id",
        "command_type",
        "payload_hash",
        "execution_status",
        "resource_type",
    ):
        _assert_string_column(
            table,
            name,
            EXPECTED_PHYSICAL_STRING_LENGTHS[name],
            nullable=name == "resource_type",
        )
    assert table.c.resource_id.nullable is True
    assert table.c.http_status.nullable is True
    assert isinstance(table.c.response_snapshot.type, JSONB)
    assert table.c.response_snapshot.nullable is True
    _assert_timestamps(table, ("created_at", "expires_at"))


def test_every_check_constraint_has_a_stable_explicit_name() -> None:
    for table in Base.metadata.tables.values():
        checks = [
            constraint
            for constraint in table.constraints
            if isinstance(constraint, CheckConstraint)
        ]
        assert checks
        assert all(
            constraint.name is not None and str(constraint.name).startswith(f"ck_{table.name}_")
            for constraint in checks
        )
        assert len({str(constraint.name) for constraint in checks}) == len(checks)


def test_paint_project_constraints_match_contract() -> None:
    checks = _check_constraints(PaintProject.__table__)
    expected = {
        "ck_paint_projects_owner_principal_id_normalized",
        "ck_paint_projects_title_not_blank",
        "ck_paint_projects_title_normalized",
        "ck_paint_projects_description_normalized",
        "ck_paint_projects_requested_target_style_format",
        "ck_paint_projects_requested_target_style_allowed",
        "ck_paint_projects_planning_mode_format",
        "ck_paint_projects_planning_mode_allowed",
        "ck_paint_projects_status_allowed",
        "ck_paint_projects_updated_at_not_before_created_at",
    }
    assert set(checks) == expected
    assert EXPECTED_POSTGRESQL_MACHINE_TOKEN_PATTERN in _constraint_sql(
        checks["ck_paint_projects_requested_target_style_format"]
    )
    assert _quoted_sql_values(checks["ck_paint_projects_requested_target_style_allowed"]) == (
        EXPECTED_TARGET_STYLE,
    )
    assert _quoted_sql_values(checks["ck_paint_projects_planning_mode_allowed"]) == (
        EXPECTED_PLANNING_MODE,
    )
    status_constraint = checks["ck_paint_projects_status_allowed"]
    status_sql = _constraint_sql(status_constraint)
    assert _quoted_sql_values(status_constraint) == EXPECTED_WORKFLOW_STATES
    assert MACHINE_TOKEN_PATTERN not in status_sql
    assert "btrim" in _constraint_sql(checks["ck_paint_projects_owner_principal_id_normalized"])
    assert "updated_at >= created_at" in _constraint_sql(
        checks["ck_paint_projects_updated_at_not_before_created_at"]
    )


def test_state_transition_constraints_match_conditional_contract() -> None:
    checks = _check_constraints(StateTransitionEvent.__table__)
    expected = {
        "ck_state_transition_events_from_state_allowed",
        "ck_state_transition_events_to_state_allowed",
        "ck_state_transition_events_event_format",
        "ck_state_transition_events_actor_type_format",
        "ck_state_transition_events_actor_type_allowed",
        "ck_state_transition_events_actor_principal_id_normalized",
        "ck_state_transition_events_actor_display_snapshot_normalized",
        "ck_state_transition_events_user_display_name_required",
        "ck_state_transition_events_reason_format",
        "ck_state_transition_events_create_project_reason",
        "ck_state_transition_events_event_metadata_is_object",
    }
    assert set(checks) == expected
    assert "actor_display_name_snapshot IS NULL" in _constraint_sql(
        checks["ck_state_transition_events_actor_display_snapshot_normalized"]
    )
    assert f"actor_type <> '{EXPECTED_USER_ACTOR_TYPE}'" in _constraint_sql(
        checks["ck_state_transition_events_user_display_name_required"]
    )
    assert "reason IS NULL" in _constraint_sql(checks["ck_state_transition_events_reason_format"])
    assert EXPECTED_POSTGRESQL_MACHINE_TOKEN_PATTERN in _constraint_sql(
        checks["ck_state_transition_events_reason_format"]
    )
    assert f"event <> '{EXPECTED_CREATE_EVENT}'" in _constraint_sql(
        checks["ck_state_transition_events_create_project_reason"]
    )
    assert "reason IS NOT NULL" in _constraint_sql(
        checks["ck_state_transition_events_create_project_reason"]
    )
    assert f"reason = '{EXPECTED_CREATE_REASON}'" in _constraint_sql(
        checks["ck_state_transition_events_create_project_reason"]
    )
    assert "jsonb_typeof(event_metadata) = 'object'" in _constraint_sql(
        checks["ck_state_transition_events_event_metadata_is_object"]
    )
    actor_constraint = checks["ck_state_transition_events_actor_type_allowed"]
    assert _quoted_sql_values(actor_constraint) == EXPECTED_ACTOR_TYPES
    assert "agent" not in EXPECTED_ACTOR_TYPES


def test_idempotency_constraints_match_contract() -> None:
    checks = _check_constraints(CommandIdempotencyRecord.__table__)
    expected = {
        "ck_command_idempotency_records_scope_key_normalized",
        "ck_command_idempotency_records_principal_id_normalized",
        "ck_command_idempotency_records_command_type_format",
        "ck_command_idempotency_records_payload_hash_format",
        "ck_command_idempotency_records_execution_status_format",
        "ck_command_idempotency_records_execution_status_allowed",
        "ck_command_idempotency_records_resource_type_format",
        "ck_command_idempotency_records_http_status_valid",
        "ck_command_idempotency_records_response_snapshot_is_object",
        "ck_command_idempotency_records_result_matches_execution_status",
        "ck_command_idempotency_records_expiry_after_creation",
    }
    assert set(checks) == expected
    assert EXPECTED_PAYLOAD_HASH_PATTERN in _constraint_sql(
        checks["ck_command_idempotency_records_payload_hash_format"]
    )
    assert (
        EXPECTED_PAYLOAD_HASH_PATTERN
        in _migration_check_constraint_sql()["ck_command_idempotency_records_payload_hash_format"]
    )
    assert (
        _quoted_sql_values(checks["ck_command_idempotency_records_execution_status_allowed"])
        == EXPECTED_IDEMPOTENCY_STATUSES
    )
    assert "jsonb_typeof(response_snapshot) = 'object'" in _constraint_sql(
        checks["ck_command_idempotency_records_response_snapshot_is_object"]
    )
    assert "execution_status <> 'completed'" in _constraint_sql(
        checks["ck_command_idempotency_records_result_matches_execution_status"]
    )
    assert "expires_at > created_at" in _constraint_sql(
        checks["ck_command_idempotency_records_expiry_after_creation"]
    )


def test_required_indexes_have_exact_names_and_column_order() -> None:
    expected = {
        "paint_projects": {
            "ix_paint_projects_owner_updated_at_id": (
                "owner_principal_id",
                "updated_at",
                "id",
            )
        },
        "state_transition_events": {
            "ix_state_transition_events_project_created_at_id": (
                "project_id",
                "created_at",
                "id",
            )
        },
        "command_idempotency_records": {
            "ix_command_idempotency_records_expires_at": ("expires_at",)
        },
    }
    for table_name, expected_indexes in expected.items():
        table = Base.metadata.tables[table_name]
        actual = {index.name: _index_columns(index) for index in table.indexes}
        assert actual == expected_indexes


def test_state_transition_foreign_key_is_restrict_without_orm_cascade() -> None:
    table = StateTransitionEvent.__table__
    constraints = [
        constraint
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    ]
    assert len(constraints) == 1
    constraint = constraints[0]
    assert tuple(element.parent.name for element in constraint.elements) == ("project_id",)
    assert tuple(element.target_fullname for element in constraint.elements) == (
        "paint_projects.id",
    )
    assert constraint.ondelete == "RESTRICT"
    assert not StateTransitionEvent.__mapper__.relationships


def test_idempotency_unique_constraint_has_exact_scope_and_name() -> None:
    constraints = [
        constraint
        for constraint in CommandIdempotencyRecord.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    ]
    assert len(constraints) == 1
    constraint = constraints[0]
    assert str(constraint.name) == ("uq_command_idempotency_records_scope_key_idempotency_key")
    assert tuple(column.name for column in constraint.columns) == (
        "scope_key",
        "idempotency_key",
    )


def test_importing_all_models_has_no_runtime_or_output_side_effect() -> None:
    source = """
import sqlalchemy.ext.asyncio

def fail(*args, **kwargs):
    raise AssertionError("Model import attempted to create an engine")

sqlalchemy.ext.asyncio.create_async_engine = fail
from creativedeploy_api.db.models import REGISTERED_MODELS
assert len(REGISTERED_MODELS) == 3
"""
    result = subprocess.run(
        [sys.executable, "-c", source],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert result.stderr == ""
