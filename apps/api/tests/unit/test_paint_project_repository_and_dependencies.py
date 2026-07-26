"""Unit coverage for repository SQL shape and request dependency lifecycle."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from creativedeploy_api.api.dependencies import (
    get_current_principal,
    get_database_session,
    get_paint_project_service,
    get_request_id,
)
from creativedeploy_api.core.config import Settings
from creativedeploy_api.core.principal import ConfiguredDemoPrincipalAdapter
from creativedeploy_api.db.models import (
    CommandIdempotencyRecord,
    PaintProject,
    StateTransitionEvent,
)
from creativedeploy_api.repositories.paint_projects import (
    SqlAlchemyPaintProjectRepository,
)
from creativedeploy_api.services.paint_projects import PaintProjectService

_UNSET = object()


class FakeScalarCollection:
    def __init__(self, items: list[object]) -> None:
        self._items = items

    def all(self) -> list[object]:
        return self._items


class FakeResult:
    def __init__(
        self,
        *,
        scalar_one: object = _UNSET,
        scalar_one_or_none: object = _UNSET,
        scalar_items: list[object] | None = None,
    ) -> None:
        self._scalar_one = scalar_one
        self._scalar_one_or_none = scalar_one_or_none
        self._scalar_items = scalar_items or []

    def scalar_one(self) -> object:
        assert self._scalar_one is not _UNSET
        return self._scalar_one

    def scalar_one_or_none(self) -> object | None:
        assert self._scalar_one_or_none is not _UNSET
        return None if self._scalar_one_or_none is None else self._scalar_one_or_none

    def scalars(self) -> FakeScalarCollection:
        return FakeScalarCollection(self._scalar_items)


class FakeAsyncSession:
    def __init__(self, results: list[FakeResult] | None = None) -> None:
        self.results = results or []
        self.statements: list[object] = []
        self.execution_parameters: list[dict[str, object] | None] = []
        self.added: list[object] = []
        self.flush_calls = 0

    async def execute(
        self,
        statement: object,
        parameters: dict[str, object] | None = None,
    ) -> FakeResult:
        self.statements.append(statement)
        self.execution_parameters.append(parameters)
        assert self.results
        return self.results.pop(0)

    def add(self, entity: object) -> None:
        self.added.append(entity)

    async def flush(self) -> None:
        self.flush_calls += 1


def _project() -> PaintProject:
    created_at = datetime(2026, 7, 26, 8, 0, tzinfo=UTC)
    return PaintProject(
        id=uuid.uuid4(),
        owner_principal_id="owner",
        title="Project",
        description=None,
        requested_target_style="cel_shading",
        planning_mode="planning_only_demo",
        status="DRAFT",
        created_at=created_at,
        updated_at=created_at,
    )


def _record() -> CommandIdempotencyRecord:
    created_at = datetime(2026, 7, 26, 8, 0, tzinfo=UTC)
    return CommandIdempotencyRecord(
        id=uuid.uuid4(),
        scope_key="principal:owner:command:create_paint_project",
        principal_id="owner",
        command_type="create_paint_project",
        idempotency_key=uuid.uuid4(),
        payload_hash="a" * 64,
        execution_status="completed",
        resource_type="paint_project",
        resource_id=uuid.uuid4(),
        http_status=201,
        response_snapshot={"status": "DRAFT"},
        created_at=created_at,
        expires_at=created_at + timedelta(hours=24),
    )


def test_create_transaction_timeouts_use_bound_transaction_local_settings() -> None:
    session = FakeAsyncSession([FakeResult(scalar_one=None)])
    repository = SqlAlchemyPaintProjectRepository(cast(AsyncSession, session))

    asyncio.run(
        repository.configure_create_transaction_timeouts(
            lock_timeout_ms=321,
            statement_timeout_ms=654,
        )
    )

    compiled = str(
        session.statements[0].compile(
            dialect=postgresql.dialect(),
        )
    )
    assert "set_config('lock_timeout'" in compiled
    assert "set_config('statement_timeout'" in compiled
    assert ", true)" in compiled
    assert "321ms" not in compiled
    assert "654ms" not in compiled
    assert session.execution_parameters[0] == {
        "lock_timeout": "321ms",
        "statement_timeout": "654ms",
    }


def test_claim_insert_omits_nullable_json_result_and_returns_acquired_id() -> None:
    record_id = uuid.uuid4()
    session = FakeAsyncSession([FakeResult(scalar_one_or_none=record_id)])
    repository = SqlAlchemyPaintProjectRepository(cast(AsyncSession, session))
    created_at = datetime(2026, 7, 26, 8, 0, tzinfo=UTC)

    claim = asyncio.run(
        repository.claim_create_command(
            record_id=record_id,
            scope_key="principal:owner:command:create_paint_project",
            principal_id="owner",
            idempotency_key=uuid.uuid4(),
            payload_hash="a" * 64,
            created_at=created_at,
            expires_at=created_at + timedelta(hours=24),
        )
    )

    assert claim.acquired is True
    assert claim.acquired_record_id == record_id
    assert claim.existing_record is None
    compiled = str(
        session.statements[0].compile(
            dialect=postgresql.dialect(),
        )
    )
    assert "ON CONFLICT (scope_key, idempotency_key) DO NOTHING" in compiled
    assert "response_snapshot" not in compiled
    assert "resource_type" not in compiled
    assert "resource_id" not in compiled
    assert "http_status" not in compiled


def test_claim_conflict_reads_committed_record_and_rejects_missing_winner() -> None:
    existing = _record()
    session = FakeAsyncSession(
        [
            FakeResult(scalar_one_or_none=None),
            FakeResult(scalar_one_or_none=existing),
        ]
    )
    repository = SqlAlchemyPaintProjectRepository(cast(AsyncSession, session))
    created_at = datetime(2026, 7, 26, 8, 0, tzinfo=UTC)

    claim = asyncio.run(
        repository.claim_create_command(
            record_id=uuid.uuid4(),
            scope_key=existing.scope_key,
            principal_id=existing.principal_id,
            idempotency_key=existing.idempotency_key,
            payload_hash=existing.payload_hash,
            created_at=created_at,
            expires_at=created_at + timedelta(hours=24),
        )
    )

    assert claim.acquired is False
    assert claim.existing_record is existing
    assert len(session.statements) == 2

    missing_session = FakeAsyncSession(
        [
            FakeResult(scalar_one_or_none=None),
            FakeResult(scalar_one_or_none=None),
        ]
    )
    missing_repository = SqlAlchemyPaintProjectRepository(cast(AsyncSession, missing_session))
    with pytest.raises(RuntimeError, match="without a claim or committed record"):
        asyncio.run(
            missing_repository.claim_create_command(
                record_id=uuid.uuid4(),
                scope_key=existing.scope_key,
                principal_id=existing.principal_id,
                idempotency_key=existing.idempotency_key,
                payload_hash=existing.payload_hash,
                created_at=created_at,
                expires_at=created_at + timedelta(hours=24),
            )
        )


def test_repository_stages_flushes_completes_lists_and_reads() -> None:
    project = _project()
    event = StateTransitionEvent(
        id=uuid.uuid4(),
        project_id=project.id,
        from_state=None,
        to_state="DRAFT",
        event="create_project",
        actor_type="user",
        actor_principal_id="owner",
        actor_display_name_snapshot="Owner",
        reason="project_created",
        correlation_id=uuid.uuid4(),
        event_metadata={},
        created_at=project.created_at,
    )
    completed_id = uuid.uuid4()
    session = FakeAsyncSession(
        [
            FakeResult(scalar_one_or_none=completed_id),
            FakeResult(scalar_one=1),
            FakeResult(scalar_items=[project]),
            FakeResult(scalar_one_or_none=project),
        ]
    )
    repository = SqlAlchemyPaintProjectRepository(cast(AsyncSession, session))

    repository.add_project(project)
    repository.add_initial_event(event)
    asyncio.run(repository.flush())
    asyncio.run(
        repository.complete_create_command(
            record_id=completed_id,
            project_id=project.id,
            response_snapshot={"id": str(project.id), "status": "DRAFT"},
        )
    )
    projects, total = asyncio.run(
        repository.list_owned_projects(
            owner_principal_id="owner",
            limit=20,
            offset=0,
        )
    )
    detail = asyncio.run(
        repository.get_owned_project(
            project_id=project.id,
            owner_principal_id="owner",
        )
    )

    assert session.added == [project, event]
    assert session.flush_calls == 1
    assert projects == [project]
    assert total == 1
    assert detail is project

    failed_completion = SqlAlchemyPaintProjectRepository(
        cast(
            AsyncSession,
            FakeAsyncSession([FakeResult(scalar_one_or_none=None)]),
        )
    )
    with pytest.raises(RuntimeError, match="could not be completed"):
        asyncio.run(
            failed_completion.complete_create_command(
                record_id=uuid.uuid4(),
                project_id=project.id,
                response_snapshot={"status": "DRAFT"},
            )
        )


class FakeSessionContext:
    def __init__(self, session: object) -> None:
        self.session = session
        self.closed = False

    async def __aenter__(self) -> object:
        return self.session

    async def __aexit__(
        self,
        _exception_type: object,
        _exception: object,
        _traceback: object,
    ) -> None:
        self.closed = True


class FakeSessionFactory:
    def __init__(self, context: FakeSessionContext) -> None:
        self.context = context

    def __call__(self) -> FakeSessionContext:
        return self.context


def _request(app: object) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
            "app": app,
        }
    )


def test_request_dependencies_reuse_id_close_session_and_resolve_adapter() -> None:
    fake_session = object()
    session_context = FakeSessionContext(fake_session)
    state = SimpleNamespace(
        database_session_factory=FakeSessionFactory(session_context),
        settings=Settings(
            app_env="test",
            database_url="postgresql+psycopg://test:test@127.0.0.1:1/test",
            database_lock_timeout_ms=123,
            database_statement_timeout_ms=456,
            paintpilot_demo_principal_id="owner",
            paintpilot_demo_principal_display_name="Owner",
            _env_file=None,
        ),
        principal_adapter=ConfiguredDemoPrincipalAdapter(
            principal_id="owner",
            display_name="Owner",
        ),
    )
    request = _request(SimpleNamespace(state=state))

    first_request_id = get_request_id(request)
    assert get_request_id(request) == first_request_id
    assert get_current_principal(request).principal_id == "owner"

    async def consume_session() -> object:
        generator = get_database_session(request)
        yielded = await anext(generator)
        await generator.aclose()
        return yielded

    assert asyncio.run(consume_session()) is fake_session
    assert session_context.closed is True

    typed_session = cast(AsyncSession, FakeAsyncSession())
    service = get_paint_project_service(request, typed_session)
    assert isinstance(service, PaintProjectService)
    assert service._database_lock_timeout_ms == 123
    assert service._database_statement_timeout_ms == 456
