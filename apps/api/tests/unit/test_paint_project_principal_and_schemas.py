"""Contract tests for PaintProject boundary schemas and the demo Principal adapter."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from creativedeploy_api.app_factory import create_app
from creativedeploy_api.core.config import (
    MAX_DATABASE_TRANSACTION_TIMEOUT_MS,
    Settings,
)
from creativedeploy_api.core.principal import (
    AuthenticationMode,
    ConfiguredDemoPrincipalAdapter,
    PrincipalContext,
    PrincipalType,
)
from creativedeploy_api.schemas.errors import ErrorResponse
from creativedeploy_api.schemas.paint_projects import (
    CreatePaintProjectRequest,
    PaintProjectListResponse,
    PaintProjectRead,
)


def test_configured_demo_principal_is_trimmed_human_and_non_persistent() -> None:
    settings = Settings(
        app_env="development",
        database_url="postgresql+psycopg://test:test@127.0.0.1:1/test",
        paintpilot_demo_principal_id="  local-demo-owner  ",
        paintpilot_demo_principal_display_name="  Local Demo Owner  ",
        _env_file=None,
    )

    principal = ConfiguredDemoPrincipalAdapter.from_settings(settings).resolve()

    assert principal == PrincipalContext(
        principal_id="local-demo-owner",
        principal_type=PrincipalType.HUMAN,
        display_name="Local Demo Owner",
        authentication_mode=AuthenticationMode.CONFIGURED_DEMO_OPERATOR,
    )
    assert "principal_contexts" not in {
        "paint_projects",
        "state_transition_events",
        "command_idempotency_records",
    }


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("paintpilot_demo_principal_id", " "),
        ("paintpilot_demo_principal_id", "p" * 129),
        ("paintpilot_demo_principal_display_name", " "),
        ("paintpilot_demo_principal_display_name", "界" * 201),
    ],
)
def test_configured_demo_principal_boundaries_are_validated(
    field_name: str,
    field_value: str,
) -> None:
    values = {
        "app_env": "test",
        "database_url": "postgresql+psycopg://test:test@127.0.0.1:1/test",
        "paintpilot_demo_principal_id": "test-owner",
        "paintpilot_demo_principal_display_name": "Test Owner",
        field_name: field_value,
        "_env_file": None,
    }

    with pytest.raises(ValidationError):
        Settings(**values)


def _explicit_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "test",
        "database_url": "postgresql+psycopg://test:test@127.0.0.1:1/test",
        "paintpilot_demo_principal_id": "test-owner",
        "paintpilot_demo_principal_display_name": "Test Owner",
        "_env_file": None,
    }
    values.update(overrides)
    return Settings(**values)


def test_missing_runtime_identity_has_no_silent_demo_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "APP_ENV",
        "PAINTPILOT_DEMO_PRINCIPAL_ID",
        "PAINTPILOT_DEMO_PRINCIPAL_DISPLAY_NAME",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = Settings(
        database_url="postgresql+psycopg://test:test@127.0.0.1:1/test",
        _env_file=None,
    )

    assert settings.app_env is None
    assert settings.paintpilot_demo_principal_id is None
    assert settings.paintpilot_demo_principal_display_name is None
    with pytest.raises(ValueError, match="APP_ENV must be explicitly configured"):
        create_app(settings)


def test_shared_test_settings_are_explicit_and_start_health_capable_app(
    test_settings: Settings,
) -> None:
    app = create_app(test_settings)

    assert test_settings.app_env == "test"
    assert test_settings.paintpilot_demo_principal_id == "test-demo-owner"
    assert test_settings.paintpilot_demo_principal_display_name == "Test Demo Owner"
    assert app.state.principal_adapter.resolve().principal_id == "test-demo-owner"


@pytest.mark.parametrize("app_env", ["", " ", "unknown", "Production"])
def test_blank_or_unknown_app_env_is_rejected(app_env: str) -> None:
    with pytest.raises(ValidationError):
        _explicit_settings(app_env=app_env)


def test_production_rejects_demo_adapter_even_when_demo_values_are_present() -> None:
    settings = _explicit_settings(app_env="production")

    with pytest.raises(ValueError, match="unavailable in production"):
        create_app(settings)


@pytest.mark.parametrize(
    ("missing_field", "expected_message"),
    [
        (
            "paintpilot_demo_principal_id",
            "PAINTPILOT_DEMO_PRINCIPAL_ID must be explicitly configured",
        ),
        (
            "paintpilot_demo_principal_display_name",
            "PAINTPILOT_DEMO_PRINCIPAL_DISPLAY_NAME must be explicitly configured",
        ),
    ],
)
def test_non_production_startup_requires_both_demo_principal_fields(
    missing_field: str,
    expected_message: str,
) -> None:
    settings = _explicit_settings(**{missing_field: None})

    with pytest.raises(ValueError, match=expected_message):
        create_app(settings)


@pytest.mark.parametrize("app_env", ["development", "test"])
def test_explicit_non_production_runtime_configuration_starts(
    app_env: str,
) -> None:
    settings = _explicit_settings(app_env=app_env)

    app = create_app(settings)

    assert app.state.settings is settings
    assert app.state.principal_adapter.resolve().principal_id == "test-owner"


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("database_lock_timeout_ms", 0),
        ("database_lock_timeout_ms", -1),
        ("database_lock_timeout_ms", MAX_DATABASE_TRANSACTION_TIMEOUT_MS + 1),
        ("database_statement_timeout_ms", 0),
        ("database_statement_timeout_ms", -1),
        ("database_statement_timeout_ms", MAX_DATABASE_TRANSACTION_TIMEOUT_MS + 1),
    ],
)
def test_database_transaction_timeouts_are_positive_and_bounded(
    field_name: str,
    value: int,
) -> None:
    with pytest.raises(ValidationError):
        _explicit_settings(**{field_name: value})


def test_create_request_normalizes_only_client_owned_text() -> None:
    request = CreatePaintProjectRequest(
        title="  计划项目  ",
        description="  仅用于规划  ",
    )
    empty_description = CreatePaintProjectRequest(
        title="Project",
        description="   ",
    )

    assert request.model_dump() == {
        "title": "计划项目",
        "description": "仅用于规划",
    }
    assert empty_description.description is None


@pytest.mark.parametrize(
    "payload",
    [
        {"title": ""},
        {"title": "   "},
        {"title": "界" * 81},
        {"title": "Project", "description": "界" * 501},
        {"title": 123},
        {"title": "Project", "owner_principal_id": "attacker"},
        {"title": "Project", "requested_target_style": "other_style"},
        {"title": "Project", "planning_mode": "other_mode"},
        {"title": "Project", "status": "COMPLETED"},
        {"title": "Project", "id": str(uuid4())},
    ],
)
def test_create_request_rejects_invalid_or_server_owned_fields(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        CreatePaintProjectRequest.model_validate(payload)


def test_create_request_accepts_exact_unicode_limits() -> None:
    request = CreatePaintProjectRequest(
        title="界" * 80,
        description="说" * 500,
    )

    assert len(request.title) == 80
    assert request.description is not None
    assert len(request.description) == 500


def _read_payload() -> dict[str, object]:
    created_at = datetime(2026, 7, 26, 8, 0, tzinfo=UTC)
    return {
        "id": uuid4(),
        "owner_principal_id": "owner",
        "title": "Project",
        "description": None,
        "requested_target_style": "cel_shading",
        "planning_mode": "planning_only_demo",
        "status": "DRAFT",
        "created_at": created_at,
        "updated_at": created_at,
    }


def test_read_schema_accepts_the_exact_nine_field_contract() -> None:
    payload = _read_payload()

    project = PaintProjectRead.model_validate(payload)

    assert set(project.model_dump()) == {
        "id",
        "owner_principal_id",
        "title",
        "description",
        "requested_target_style",
        "planning_mode",
        "status",
        "created_at",
        "updated_at",
    }
    assert not {
        "current_image_asset_id",
        "current_region_version_id",
        "current_plan_id",
    } & set(project.model_dump())


@pytest.mark.parametrize(
    "overrides",
    [
        {"owner_principal_id": " owner"},
        {"title": "Project "},
        {"description": ""},
        {"requested_target_style": "other_style"},
        {"planning_mode": "other_mode"},
        {"status": "UNKNOWN"},
        {"created_at": datetime(2026, 7, 26, 8, 0)},
        {
            "updated_at": datetime(2026, 7, 26, 7, 59, tzinfo=UTC),
        },
    ],
)
def test_read_schema_rejects_invalid_stored_or_replay_values(
    overrides: dict[str, object],
) -> None:
    payload = _read_payload()
    payload.update(overrides)

    with pytest.raises(ValidationError):
        PaintProjectRead.model_validate(payload)


def test_list_and_error_envelopes_are_strict_and_bounded() -> None:
    project = PaintProjectRead.model_validate(_read_payload())
    response = PaintProjectListResponse(
        items=[project],
        total=1,
        limit=20,
        offset=0,
    )
    error = ErrorResponse(
        error_code="REQUEST_VALIDATION_FAILED",
        category="VALIDATION_ERROR",
        message="One or more request fields are invalid.",
        retryable=False,
        request_id=uuid4(),
        current_state=None,
        allowed_actions=["correct_request"],
        safe_details={"fields": [{"field": "title", "message": "Value is too short."}]},
    )

    assert response.total == 1
    assert error.safe_details["fields"]
    with pytest.raises(ValidationError):
        PaintProjectListResponse(
            items=[],
            total=0,
            limit=101,
            offset=0,
        )
    with pytest.raises(ValidationError):
        ErrorResponse.model_validate(
            {
                **error.model_dump(),
                "database_url": "must-not-be-accepted",
            }
        )


def test_read_schema_accepts_updated_at_after_created_at() -> None:
    payload = _read_payload()
    payload["updated_at"] = payload["created_at"] + timedelta(seconds=1)  # type: ignore[operator]

    project = PaintProjectRead.model_validate(payload)

    assert project.updated_at > project.created_at
