"""API contract tests for PaintProject route mapping and safe errors."""

import logging
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import (
    DataError,
    DBAPIError,
    IntegrityError,
    OperationalError,
    ProgrammingError,
    SQLAlchemyError,
)

from creativedeploy_api.api.dependencies import (
    get_current_principal,
    get_paint_project_service,
)
from creativedeploy_api.app_factory import create_app
from creativedeploy_api.core.config import Settings
from creativedeploy_api.core.principal import (
    AuthenticationMode,
    PrincipalContext,
    PrincipalType,
)
from creativedeploy_api.schemas.paint_projects import (
    CreatePaintProjectRequest,
    PaintProjectListResponse,
    PaintProjectRead,
)
from creativedeploy_api.services.paint_projects import (
    CreatePaintProjectResult,
    DatabaseWaitTimeoutError,
    IdempotencyKeyReusedError,
    PaintProjectNotFoundError,
)


class StubPaintProjectService:
    """Controllable application service used to prove route-only behavior."""

    def __init__(self, project: PaintProjectRead) -> None:
        self.project = project
        self.replayed = False
        self.error: BaseException | None = None
        self.create_arguments: dict[str, object] | None = None
        self.list_arguments: dict[str, object] | None = None
        self.detail_arguments: dict[str, object] | None = None

    async def create_project(self, **arguments: object) -> CreatePaintProjectResult:
        self.create_arguments = arguments
        if self.error is not None:
            raise self.error
        return CreatePaintProjectResult(
            project=self.project,
            replayed=self.replayed,
        )

    async def list_projects(self, **arguments: object) -> PaintProjectListResponse:
        self.list_arguments = arguments
        if self.error is not None:
            raise self.error
        return PaintProjectListResponse(
            items=[self.project],
            total=1,
            limit=int(arguments["limit"]),
            offset=int(arguments["offset"]),
        )

    async def get_project(self, **arguments: object) -> PaintProjectRead:
        self.detail_arguments = arguments
        if self.error is not None:
            raise self.error
        return self.project


def _project() -> PaintProjectRead:
    created = datetime(2026, 7, 26, 8, 0, tzinfo=UTC)
    return PaintProjectRead(
        id=uuid4(),
        owner_principal_id="owner",
        title="Project",
        description=None,
        requested_target_style="cel_shading",
        planning_mode="planning_only_demo",
        status="DRAFT",
        created_at=created,
        updated_at=created,
    )


def _principal() -> PrincipalContext:
    return PrincipalContext(
        principal_id="owner",
        principal_type=PrincipalType.HUMAN,
        display_name="Owner Display",
        authentication_mode=AuthenticationMode.CONFIGURED_DEMO_OPERATOR,
    )


def _client(
    service: StubPaintProjectService,
) -> AbstractContextManager[TestClient]:
    settings = Settings(
        app_env="test",
        database_url="postgresql+psycopg://test:test@127.0.0.1:1/test",
        paintpilot_demo_principal_id="test-owner",
        paintpilot_demo_principal_display_name="Test Owner",
        _env_file=None,
    )
    app = create_app(settings)
    app.dependency_overrides[get_paint_project_service] = lambda: service
    app.dependency_overrides[get_current_principal] = _principal
    return TestClient(app, raise_server_exceptions=False)


def test_post_returns_201_server_fields_and_request_correlation() -> None:
    service = StubPaintProjectService(_project())
    idempotency_key = uuid4()

    with _client(service) as client:
        response = client.post(
            "/api/v1/paint-projects",
            headers={"Idempotency-Key": str(idempotency_key)},
            json={"title": "  Project  ", "description": "   "},
        )

    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == service.project.model_dump(mode="json")
    assert response.headers.get("Idempotent-Replayed") is None
    assert service.create_arguments is not None
    payload = service.create_arguments["payload"]
    assert isinstance(payload, CreatePaintProjectRequest)
    assert payload.title == "Project"
    assert payload.description is None
    assert service.create_arguments["principal"] == _principal()
    assert service.create_arguments["idempotency_key"] == idempotency_key
    assert isinstance(service.create_arguments["correlation_id"], UUID)


def test_post_replay_preserves_201_and_adds_controlled_header() -> None:
    service = StubPaintProjectService(_project())
    service.replayed = True

    with _client(service) as client:
        response = client.post(
            "/api/v1/paint-projects",
            headers={"Idempotency-Key": str(uuid4())},
            json={"title": "Project"},
        )

    assert response.status_code == 201
    assert response.headers["Idempotent-Replayed"] == "true"
    assert response.json()["id"] == str(service.project.id)


def test_list_defaults_and_detail_delegate_without_sql_logic() -> None:
    service = StubPaintProjectService(_project())

    with _client(service) as client:
        list_response = client.get("/api/v1/paint-projects")
        detail_response = client.get(f"/api/v1/paint-projects/{service.project.id}")

    assert list_response.status_code == 200
    assert list_response.headers["cache-control"] == "no-store"
    assert list_response.json() == {
        "items": [service.project.model_dump(mode="json")],
        "total": 1,
        "limit": 20,
        "offset": 0,
    }
    assert service.list_arguments == {
        "principal": _principal(),
        "limit": 20,
        "offset": 0,
    }
    assert detail_response.status_code == 200
    assert service.detail_arguments == {
        "project_id": service.project.id,
        "principal": _principal(),
    }


@pytest.mark.parametrize(
    ("path", "headers", "json_body", "expected_field"),
    [
        (
            "/api/v1/paint-projects",
            {},
            {"title": "Project"},
            "header.Idempotency-Key",
        ),
        (
            "/api/v1/paint-projects",
            {"Idempotency-Key": "not-a-uuid"},
            {"title": "Project"},
            "header.Idempotency-Key",
        ),
        (
            "/api/v1/paint-projects",
            {"Idempotency-Key": "00000000-0000-4000-8000-000000000001"},
            {"title": "", "owner_principal_id": "attacker"},
            "title",
        ),
        (
            "/api/v1/paint-projects?limit=101",
            {},
            None,
            "query.limit",
        ),
        (
            "/api/v1/paint-projects/not-a-uuid",
            {},
            None,
            "path.project_id",
        ),
    ],
)
def test_validation_errors_use_safe_field_level_contract(
    path: str,
    headers: dict[str, str],
    json_body: dict[str, object] | None,
    expected_field: str,
) -> None:
    service = StubPaintProjectService(_project())

    with _client(service) as client:
        if json_body is None:
            response = client.get(path, headers=headers)
        else:
            response = client.post(path, headers=headers, json=json_body)

    body = response.json()
    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store"
    assert body["error_code"] == "REQUEST_VALIDATION_FAILED"
    assert body["category"] == "VALIDATION_ERROR"
    assert body["retryable"] is False
    assert UUID(body["request_id"])
    assert expected_field in {field["field"] for field in body["safe_details"]["fields"]}
    response_text = response.text.lower()
    assert "database_url" not in response_text
    assert "traceback" not in response_text


def test_typed_application_errors_map_to_404_and_409() -> None:
    service = StubPaintProjectService(_project())

    service.error = PaintProjectNotFoundError()
    with _client(service) as client:
        not_found = client.get(f"/api/v1/paint-projects/{uuid4()}")

    assert not_found.status_code == 404
    assert not_found.headers["cache-control"] == "no-store"
    assert not_found.json()["error_code"] == "PAINT_PROJECT_NOT_FOUND"
    assert not_found.json()["category"] == "NOT_FOUND"

    service.error = IdempotencyKeyReusedError()
    with _client(service) as client:
        conflict = client.post(
            "/api/v1/paint-projects",
            headers={"Idempotency-Key": str(uuid4())},
            json={"title": "Project"},
        )

    assert conflict.status_code == 409
    assert conflict.json()["error_code"] == "IDEMPOTENCY_KEY_REUSED"
    assert conflict.json()["retryable"] is False


class StructuredDriverError(Exception):
    """Synthetic DBAPI failure with structured state and sensitive text."""

    def __init__(self, sqlstate: str | None) -> None:
        super().__init__("synthetic-driver-secret")
        self.sqlstate = sqlstate


@pytest.mark.parametrize(
    "database_error",
    [
        OperationalError(
            "sensitive SQL",
            {"password": "synthetic-parameter-secret"},
            StructuredDriverError(None),
        ),
        OperationalError(
            "sensitive SQL",
            {"password": "synthetic-parameter-secret"},
            StructuredDriverError("08006"),
        ),
        DBAPIError(
            "sensitive SQL",
            {"password": "synthetic-parameter-secret"},
            StructuredDriverError("99999"),
            connection_invalidated=True,
        ),
    ],
)
def test_connection_and_invalidated_failures_are_safe_retryable_503(
    database_error: SQLAlchemyError,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING)
    service = StubPaintProjectService(_project())
    service.error = database_error

    with _client(service) as client:
        response = client.get("/api/v1/paint-projects")

    assert response.status_code == 503
    assert response.json()["error_code"] == "DATABASE_UNAVAILABLE"
    assert response.json()["retryable"] is True
    combined = f"{response.text}\n{caplog.text}".lower()
    assert "synthetic-driver-secret" not in combined
    assert "synthetic-parameter-secret" not in combined
    assert "sensitive sql" not in combined


@pytest.mark.parametrize("sqlstate", ["55P03", "57014"])
def test_tagged_database_wait_timeout_is_safe_retryable_503(
    sqlstate: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING)
    service = StubPaintProjectService(_project())
    service.error = DatabaseWaitTimeoutError(sqlstate=sqlstate)

    with _client(service) as client:
        response = client.post(
            "/api/v1/paint-projects",
            headers={"Idempotency-Key": str(uuid4())},
            json={"title": "Project"},
        )

    assert response.status_code == 503
    assert response.json()["error_code"] == "DATABASE_WAIT_TIMEOUT"
    assert response.json()["category"] == "DATABASE_UNAVAILABLE"
    assert response.json()["retryable"] is True
    assert sqlstate not in response.text


@pytest.mark.parametrize(
    "database_error",
    [
        IntegrityError(
            "sensitive SQL",
            {"password": "synthetic-parameter-secret"},
            StructuredDriverError("23505"),
        ),
        ProgrammingError(
            "sensitive SQL",
            {"password": "synthetic-parameter-secret"},
            StructuredDriverError("42P01"),
        ),
        DataError(
            "sensitive SQL",
            {"password": "synthetic-parameter-secret"},
            StructuredDriverError("22001"),
        ),
        OperationalError(
            "sensitive SQL",
            {"password": "synthetic-parameter-secret"},
            StructuredDriverError("57014"),
        ),
        SQLAlchemyError("synthetic-generic-secret"),
    ],
)
def test_non_retryable_sqlalchemy_failures_are_safe_500(
    database_error: SQLAlchemyError,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING)
    service = StubPaintProjectService(_project())
    service.error = database_error

    with _client(service) as client:
        response = client.get("/api/v1/paint-projects")

    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["error_code"] == "INTERNAL_ERROR"
    assert response.json()["retryable"] is False
    combined = f"{response.text}\n{caplog.text}".lower()
    assert "synthetic-driver-secret" not in combined
    assert "synthetic-parameter-secret" not in combined
    assert "sensitive sql" not in combined
    assert "synthetic-generic-secret" not in combined


def test_unexpected_error_is_safe_non_retryable_500(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.ERROR)
    service = StubPaintProjectService(_project())
    service.error = RuntimeError("synthetic-internal-detail")
    with _client(service) as client:
        internal_failure = client.get("/api/v1/paint-projects")

    assert internal_failure.status_code == 500
    assert internal_failure.headers["cache-control"] == "no-store"
    assert internal_failure.json()["error_code"] == "INTERNAL_ERROR"
    assert internal_failure.json()["retryable"] is False
    assert "synthetic-internal-detail" not in internal_failure.text
    assert "synthetic-internal-detail" not in caplog.text


def test_database_handler_registration_preserves_specific_error_classes() -> None:
    service = StubPaintProjectService(_project())

    with _client(service) as client:
        handlers = client.app.exception_handlers

    assert DatabaseWaitTimeoutError in handlers
    assert IntegrityError in handlers
    assert ProgrammingError in handlers
    assert DataError in handlers
    assert SQLAlchemyError in handlers
    assert handlers[IntegrityError] is not handlers[SQLAlchemyError]
