"""Unit tests for PaintProject service transactions and idempotency orchestration."""

import asyncio
import hashlib
import logging
import uuid
from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import cast

import pytest
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from creativedeploy_api.core.principal import (
    AuthenticationMode,
    PrincipalContext,
    PrincipalType,
)
from creativedeploy_api.db.models import (
    CommandIdempotencyRecord,
    PaintProject,
    StateTransitionEvent,
)
from creativedeploy_api.repositories.paint_projects import IdempotencyClaim
from creativedeploy_api.schemas.paint_projects import (
    CreatePaintProjectRequest,
    PaintProjectRead,
)
from creativedeploy_api.services.paint_projects import (
    CREATE_PAYLOAD_VERSION,
    IDEMPOTENCY_RETENTION,
    DatabaseWaitTimeoutError,
    IdempotencyKeyReusedError,
    PaintProjectNotFoundError,
    PaintProjectRepositoryPort,
    PaintProjectService,
    PrincipalTypeNotAllowedError,
    StoredIdempotencyResultInvalidError,
    canonical_create_payload,
    create_payload_hash,
    create_scope_key,
)


class FakeTransaction:
    """Track transaction outcome without hiding service exceptions."""

    def __init__(self, session: "FakeSession") -> None:
        self._session = session

    async def __aenter__(self) -> None:
        self._session.begun += 1

    async def __aexit__(
        self,
        exception_type: type[BaseException] | None,
        _exception: BaseException | None,
        _traceback: TracebackType | None,
    ) -> bool:
        if exception_type is None:
            self._session.committed += 1
        else:
            self._session.rolled_back += 1
        return False


class FakeSession:
    """The transaction surface used by the application service."""

    def __init__(self) -> None:
        self.begun = 0
        self.committed = 0
        self.rolled_back = 0

    def begin(self) -> FakeTransaction:
        return FakeTransaction(self)


class FakeRepository:
    """In-memory call recorder implementing the narrow repository port."""

    def __init__(self, claim: IdempotencyClaim) -> None:
        self.claim = claim
        self.claim_arguments: dict[str, object] | None = None
        self.timeout_arguments: dict[str, object] | None = None
        self.projects: list[PaintProject] = []
        self.events: list[StateTransitionEvent] = []
        self.flush_calls = 0
        self.complete_arguments: dict[str, object] | None = None
        self.flush_error: BaseException | None = None
        self.list_result: tuple[list[PaintProject], int] = ([], 0)
        self.list_arguments: dict[str, object] | None = None
        self.detail_result: PaintProject | None = None
        self.detail_arguments: dict[str, object] | None = None
        self.claim_error: BaseException | None = None
        self.call_order: list[str] = []

    async def configure_create_transaction_timeouts(
        self,
        **arguments: object,
    ) -> None:
        self.call_order.append("configure_timeouts")
        self.timeout_arguments = arguments

    async def claim_create_command(self, **arguments: object) -> IdempotencyClaim:
        self.call_order.append("claim")
        self.claim_arguments = arguments
        if self.claim_error is not None:
            raise self.claim_error
        return self.claim

    def add_project(self, project: PaintProject) -> None:
        self.projects.append(project)

    def add_initial_event(self, event: StateTransitionEvent) -> None:
        self.events.append(event)

    async def flush(self) -> None:
        self.flush_calls += 1
        if self.flush_error is not None:
            raise self.flush_error

    async def complete_create_command(self, **arguments: object) -> None:
        self.complete_arguments = arguments

    async def list_owned_projects(
        self,
        **arguments: object,
    ) -> tuple[list[PaintProject], int]:
        self.list_arguments = arguments
        return self.list_result

    async def get_owned_project(self, **arguments: object) -> PaintProject | None:
        self.detail_arguments = arguments
        return self.detail_result


def _principal(
    principal_id: str = "owner",
    *,
    principal_type: PrincipalType = PrincipalType.HUMAN,
) -> PrincipalContext:
    return PrincipalContext(
        principal_id=principal_id,
        principal_type=principal_type,
        display_name="Owner Display",
        authentication_mode=AuthenticationMode.CONFIGURED_DEMO_OPERATOR,
    )


def _project(
    *,
    project_id: uuid.UUID | None = None,
    owner: str = "owner",
    title: str = "Project",
    updated_at: datetime | None = None,
) -> PaintProject:
    created = datetime(2026, 7, 26, 8, 0, tzinfo=UTC)
    return PaintProject(
        id=project_id or uuid.uuid4(),
        owner_principal_id=owner,
        title=title,
        description=None,
        requested_target_style="cel_shading",
        planning_mode="planning_only_demo",
        status="DRAFT",
        created_at=created,
        updated_at=updated_at or created,
    )


def _snapshot(project: PaintProject) -> dict[str, object]:
    return PaintProjectRead.model_validate(project).model_dump(mode="json")


def _completed_record(
    payload_hash: str,
    *,
    project: PaintProject | None = None,
) -> CommandIdempotencyRecord:
    stored_project = project or _project()
    created = datetime(2026, 7, 26, 8, 0, tzinfo=UTC)
    return CommandIdempotencyRecord(
        id=uuid.uuid4(),
        scope_key=create_scope_key(stored_project.owner_principal_id),
        principal_id=stored_project.owner_principal_id,
        command_type="create_paint_project",
        idempotency_key=uuid.uuid4(),
        payload_hash=payload_hash,
        execution_status="completed",
        resource_type="paint_project",
        resource_id=stored_project.id,
        http_status=201,
        response_snapshot=_snapshot(stored_project),
        created_at=created,
        expires_at=created + timedelta(hours=24),
    )


def _service(
    repository: FakeRepository,
    *,
    lock_timeout_ms: int = 2_000,
    statement_timeout_ms: int = 5_000,
) -> tuple[PaintProjectService, FakeSession]:
    session = FakeSession()
    service = PaintProjectService(
        cast(AsyncSession, session),
        cast(PaintProjectRepositoryPort, repository),
        database_lock_timeout_ms=lock_timeout_ms,
        database_statement_timeout_ms=statement_timeout_ms,
    )
    return service, session


def test_canonical_payload_and_scope_are_frozen_and_normalized() -> None:
    payload = CreatePaintProjectRequest(title="  项目  ", description="   ")
    expected_bytes = (
        '{"description":null,"title":"项目","version":"create_paint_project.v1"}'.encode()
    )

    assert CREATE_PAYLOAD_VERSION == "create_paint_project.v1"
    assert canonical_create_payload(payload) == expected_bytes
    assert create_payload_hash(payload) == hashlib.sha256(expected_bytes).hexdigest()
    assert create_scope_key("principal-1") == ("principal:principal-1:command:create_paint_project")


def test_create_writes_project_event_and_completed_result_in_one_transaction(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="creativedeploy_api.services.paint_projects")
    acquired_id = uuid.uuid4()
    repository = FakeRepository(
        IdempotencyClaim(acquired_record_id=acquired_id, existing_record=None)
    )
    service, session = _service(repository)
    idempotency_key = uuid.uuid4()
    correlation_id = uuid.uuid4()
    payload = CreatePaintProjectRequest(
        title="  Project  ",
        description="  Planning only  ",
    )

    result = asyncio.run(
        service.create_project(
            payload=payload,
            principal=_principal(),
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
        )
    )

    assert result.replayed is False
    assert result.http_status == 201
    assert result.project.owner_principal_id == "owner"
    assert result.project.title == "Project"
    assert result.project.description == "Planning only"
    assert result.project.requested_target_style == "cel_shading"
    assert result.project.planning_mode == "planning_only_demo"
    assert result.project.status == "DRAFT"
    assert result.project.id != idempotency_key
    assert session.begun == 1
    assert session.committed == 1
    assert session.rolled_back == 0
    assert repository.call_order[:2] == ["configure_timeouts", "claim"]
    assert repository.timeout_arguments == {
        "lock_timeout_ms": 2_000,
        "statement_timeout_ms": 5_000,
    }
    assert repository.flush_calls == 1
    assert len(repository.projects) == 1
    assert len(repository.events) == 1

    event = repository.events[0]
    assert event.project_id == result.project.id
    assert event.from_state is None
    assert event.to_state == "DRAFT"
    assert event.event == "create_project"
    assert event.actor_type == "user"
    assert event.actor_principal_id == "owner"
    assert event.actor_display_name_snapshot == "Owner Display"
    assert event.reason == "project_created"
    assert event.correlation_id == correlation_id
    assert event.event_metadata == {}
    assert event.created_at == result.project.created_at

    assert repository.claim_arguments is not None
    assert repository.claim_arguments["scope_key"] == create_scope_key("owner")
    assert repository.claim_arguments["idempotency_key"] == idempotency_key
    created_at = cast(datetime, repository.claim_arguments["created_at"])
    expires_at = cast(datetime, repository.claim_arguments["expires_at"])
    assert expires_at - created_at == IDEMPOTENCY_RETENTION
    assert repository.complete_arguments is not None
    assert repository.complete_arguments["record_id"] == acquired_id
    assert repository.complete_arguments["project_id"] == result.project.id
    assert repository.complete_arguments["response_snapshot"] == result.project.model_dump(
        mode="json"
    )

    assert "PaintProject create command completed" in caplog.text
    assert str(correlation_id) not in caplog.text
    assert str(idempotency_key) not in caplog.text
    assert "Planning only" not in caplog.text
    assert "Owner Display" not in caplog.text


def test_same_key_and_payload_replays_stored_201_without_new_writes() -> None:
    payload = CreatePaintProjectRequest(title="Project", description=None)
    stored_project = _project()
    existing = _completed_record(
        create_payload_hash(payload),
        project=stored_project,
    )
    repository = FakeRepository(IdempotencyClaim(acquired_record_id=None, existing_record=existing))
    service, session = _service(repository)

    result = asyncio.run(
        service.create_project(
            payload=payload,
            principal=_principal(),
            idempotency_key=existing.idempotency_key,
            correlation_id=uuid.uuid4(),
        )
    )

    assert result.replayed is True
    assert result.http_status == 201
    assert result.project.id == stored_project.id
    assert repository.projects == []
    assert repository.events == []
    assert repository.complete_arguments is None
    assert session.committed == 1
    assert session.rolled_back == 0


def test_same_key_and_different_payload_rolls_back_and_rejects_conflict() -> None:
    payload = CreatePaintProjectRequest(title="Changed", description=None)
    existing = _completed_record("a" * 64)
    repository = FakeRepository(IdempotencyClaim(acquired_record_id=None, existing_record=existing))
    service, session = _service(repository)

    with pytest.raises(IdempotencyKeyReusedError):
        asyncio.run(
            service.create_project(
                payload=payload,
                principal=_principal(),
                idempotency_key=existing.idempotency_key,
                correlation_id=uuid.uuid4(),
            )
        )

    assert repository.projects == []
    assert repository.events == []
    assert repository.complete_arguments is None
    assert session.committed == 0
    assert session.rolled_back == 1


@pytest.mark.parametrize(
    "record_mutation",
    ["in_progress", "invalid_snapshot", "missing_record"],
)
def test_invalid_committed_replay_state_is_rejected(
    record_mutation: str,
) -> None:
    payload = CreatePaintProjectRequest(title="Project")
    existing = _completed_record(create_payload_hash(payload))
    if record_mutation == "in_progress":
        existing.execution_status = "in_progress"
    elif record_mutation == "invalid_snapshot":
        existing.response_snapshot = {
            **cast(dict[str, object], existing.response_snapshot),
            "title": " unnormalized",
        }
    if record_mutation == "missing_record":
        claim = IdempotencyClaim(acquired_record_id=None, existing_record=None)
    else:
        claim = IdempotencyClaim(acquired_record_id=None, existing_record=existing)
    repository = FakeRepository(claim)
    service, session = _service(repository)

    with pytest.raises(StoredIdempotencyResultInvalidError):
        asyncio.run(
            service.create_project(
                payload=payload,
                principal=_principal(),
                idempotency_key=existing.idempotency_key,
                correlation_id=uuid.uuid4(),
            )
        )

    assert session.rolled_back == 1


def test_create_failure_rolls_back_before_completing_idempotency_result() -> None:
    repository = FakeRepository(
        IdempotencyClaim(acquired_record_id=uuid.uuid4(), existing_record=None)
    )
    repository.flush_error = SQLAlchemyError("synthetic database detail")
    service, session = _service(repository)

    with pytest.raises(SQLAlchemyError, match="synthetic database detail"):
        asyncio.run(
            service.create_project(
                payload=CreatePaintProjectRequest(title="Project"),
                principal=_principal(),
                idempotency_key=uuid.uuid4(),
                correlation_id=uuid.uuid4(),
            )
        )

    assert session.committed == 0
    assert session.rolled_back == 1
    assert repository.complete_arguments is None


class StructuredDriverError(Exception):
    """Synthetic DBAPI error exposing only a structured SQLSTATE."""

    def __init__(self, sqlstate: str) -> None:
        super().__init__("sensitive driver detail")
        self.sqlstate = sqlstate


@pytest.mark.parametrize("sqlstate", ["55P03", "57014"])
def test_configured_database_wait_sqlstates_become_retryable_timeout(
    sqlstate: str,
) -> None:
    repository = FakeRepository(
        IdempotencyClaim(acquired_record_id=uuid.uuid4(), existing_record=None)
    )
    original = OperationalError(
        "sensitive SQL",
        {"secret": "sensitive parameter"},
        StructuredDriverError(sqlstate),
    )
    repository.claim_error = original
    service, session = _service(
        repository,
        lock_timeout_ms=111,
        statement_timeout_ms=222,
    )

    with pytest.raises(DatabaseWaitTimeoutError) as captured:
        asyncio.run(
            service.create_project(
                payload=CreatePaintProjectRequest(title="Project"),
                principal=_principal(),
                idempotency_key=uuid.uuid4(),
                correlation_id=uuid.uuid4(),
            )
        )

    assert captured.value.sqlstate == sqlstate
    assert captured.value.status_code == 503
    assert captured.value.retryable is True
    assert captured.value.__cause__ is original
    assert session.rolled_back == 1
    assert repository.timeout_arguments == {
        "lock_timeout_ms": 111,
        "statement_timeout_ms": 222,
    }


def test_non_wait_database_error_is_not_reclassified_by_service() -> None:
    repository = FakeRepository(
        IdempotencyClaim(acquired_record_id=uuid.uuid4(), existing_record=None)
    )
    original = IntegrityError(
        "sensitive SQL",
        {"secret": "sensitive parameter"},
        StructuredDriverError("23505"),
    )
    repository.claim_error = original
    service, session = _service(repository)

    with pytest.raises(IntegrityError) as captured:
        asyncio.run(
            service.create_project(
                payload=CreatePaintProjectRequest(title="Project"),
                principal=_principal(),
                idempotency_key=uuid.uuid4(),
                correlation_id=uuid.uuid4(),
            )
        )

    assert captured.value is original
    assert session.rolled_back == 1


def test_asyncio_cancellation_is_rolled_back_and_not_converted() -> None:
    repository = FakeRepository(
        IdempotencyClaim(acquired_record_id=uuid.uuid4(), existing_record=None)
    )
    cancellation = asyncio.CancelledError()
    repository.claim_error = cancellation
    service, session = _service(repository)

    with pytest.raises(asyncio.CancelledError) as captured:
        asyncio.run(
            service.create_project(
                payload=CreatePaintProjectRequest(title="Project"),
                principal=_principal(),
                idempotency_key=uuid.uuid4(),
                correlation_id=uuid.uuid4(),
            )
        )

    assert captured.value is cancellation
    assert session.rolled_back == 1


def test_system_principal_cannot_create_a_human_owned_project() -> None:
    repository = FakeRepository(
        IdempotencyClaim(acquired_record_id=uuid.uuid4(), existing_record=None)
    )
    service, session = _service(repository)

    with pytest.raises(PrincipalTypeNotAllowedError):
        asyncio.run(
            service.create_project(
                payload=CreatePaintProjectRequest(title="Project"),
                principal=_principal(principal_type=PrincipalType.SYSTEM),
                idempotency_key=uuid.uuid4(),
                correlation_id=uuid.uuid4(),
            )
        )

    assert session.begun == 0
    assert repository.claim_arguments is None


def test_list_passes_only_current_owner_and_returns_stable_envelope() -> None:
    repository = FakeRepository(
        IdempotencyClaim(acquired_record_id=uuid.uuid4(), existing_record=None)
    )
    repository.list_result = ([_project(title="Owned")], 7)
    service, session = _service(repository)

    result = asyncio.run(
        service.list_projects(
            principal=_principal("owner"),
            limit=20,
            offset=2,
        )
    )

    assert [project.title for project in result.items] == ["Owned"]
    assert result.total == 7
    assert result.limit == 20
    assert result.offset == 2
    assert repository.list_arguments == {
        "owner_principal_id": "owner",
        "limit": 20,
        "offset": 2,
    }
    assert session.committed == 1


def test_detail_uses_combined_owner_scope_and_masks_missing_or_other_owner() -> None:
    project_id = uuid.uuid4()
    repository = FakeRepository(
        IdempotencyClaim(acquired_record_id=uuid.uuid4(), existing_record=None)
    )
    service, session = _service(repository)

    with pytest.raises(PaintProjectNotFoundError):
        asyncio.run(
            service.get_project(
                project_id=project_id,
                principal=_principal("owner"),
            )
        )

    assert repository.detail_arguments == {
        "project_id": project_id,
        "owner_principal_id": "owner",
    }
    assert session.rolled_back == 1

    repository.detail_result = _project(project_id=project_id, owner="owner")
    result = asyncio.run(
        service.get_project(
            project_id=project_id,
            principal=_principal("owner"),
        )
    )

    assert result.id == project_id
    assert session.committed == 1
