"""Real PostgreSQL integration tests for Phase 1D-2 persistence and API behavior."""

import asyncio
import uuid
from collections.abc import Awaitable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from creativedeploy_api.app_factory import create_app
from creativedeploy_api.core.config import Settings
from creativedeploy_api.core.principal import (
    AuthenticationMode,
    PrincipalContext,
    PrincipalType,
)
from creativedeploy_api.db.engine import create_database_engine
from creativedeploy_api.db.models import (
    CommandIdempotencyRecord,
    PaintProject,
    StateTransitionEvent,
)
from creativedeploy_api.db.session import create_database_session_factory
from creativedeploy_api.repositories.paint_projects import (
    SqlAlchemyPaintProjectRepository,
)
from creativedeploy_api.schemas.paint_projects import CreatePaintProjectRequest
from creativedeploy_api.services.paint_projects import (
    CreatePaintProjectResult,
    DatabaseWaitTimeoutError,
    IdempotencyKeyReusedError,
    PaintProjectNotFoundError,
    PaintProjectService,
    create_payload_hash,
    create_scope_key,
)

pytestmark = pytest.mark.integration

TEST_SYNC_TIMEOUT_SECONDS = 5.0
TEST_OPERATION_TIMEOUT_SECONDS = 12.0
TEST_LOCK_TIMEOUT_MS = 3_000
TEST_STATEMENT_TIMEOUT_MS = 5_000
TEST_SHORT_LOCK_TIMEOUT_MS = 500
TEST_SHORT_STATEMENT_TIMEOUT_MS = 1_500
TEST_STATEMENT_PROBE_TIMEOUT_MS = 50
TEST_SNAPSHOT_REGRESSION_LOCK_TIMEOUT_MS = 8_000
TEST_SNAPSHOT_REGRESSION_STATEMENT_TIMEOUT_MS = 10_000


@dataclass(frozen=True, slots=True)
class IntegrationIdentity:
    """Unique exact cleanup scope for one integration test."""

    settings: Settings
    principal_id: str

    @property
    def principal(self) -> PrincipalContext:
        return PrincipalContext(
            principal_id=self.principal_id,
            principal_type=PrincipalType.HUMAN,
            display_name="Phase 1D-2 Integration Owner",
            authentication_mode=AuthenticationMode.CONFIGURED_DEMO_OPERATOR,
        )


def _settings(
    principal_id: str,
    *,
    lock_timeout_ms: int = TEST_LOCK_TIMEOUT_MS,
    statement_timeout_ms: int = TEST_STATEMENT_TIMEOUT_MS,
) -> Settings:
    development_settings = Settings()
    return Settings(
        app_env="test",
        database_url=development_settings.database_url.get_secret_value(),
        database_lock_timeout_ms=lock_timeout_ms,
        database_statement_timeout_ms=statement_timeout_ms,
        paintpilot_demo_principal_id=principal_id,
        paintpilot_demo_principal_display_name="Phase 1D-2 Integration Owner",
        _env_file=None,
    )


async def _cleanup(identity: IntegrationIdentity) -> None:
    engine = create_database_engine(identity.settings)
    project_ids = select(PaintProject.id).where(
        PaintProject.owner_principal_id == identity.principal_id
    )
    try:
        async with engine.begin() as connection:
            await connection.execute(
                delete(CommandIdempotencyRecord).where(
                    CommandIdempotencyRecord.principal_id == identity.principal_id
                )
            )
            await connection.execute(
                delete(StateTransitionEvent).where(StateTransitionEvent.project_id.in_(project_ids))
            )
            await connection.execute(
                delete(PaintProject).where(PaintProject.owner_principal_id == identity.principal_id)
            )
    finally:
        await engine.dispose()


@pytest.fixture
def integration_identity() -> Iterator[IntegrationIdentity]:
    principal_id = f"phase1d2-integration-{uuid.uuid4().hex}"
    identity = IntegrationIdentity(
        settings=_settings(principal_id),
        principal_id=principal_id,
    )
    asyncio.run(_cleanup(identity))
    yield identity
    asyncio.run(_cleanup(identity))


async def _counts(
    session_factory: async_sessionmaker[AsyncSession],
    principal_id: str,
) -> tuple[int, int, int]:
    project_ids = select(PaintProject.id).where(PaintProject.owner_principal_id == principal_id)
    async with session_factory() as session, session.begin():
        projects = (
            await session.execute(
                select(func.count(PaintProject.id)).where(
                    PaintProject.owner_principal_id == principal_id
                )
            )
        ).scalar_one()
        events = (
            await session.execute(
                select(func.count(StateTransitionEvent.id)).where(
                    StateTransitionEvent.project_id.in_(project_ids)
                )
            )
        ).scalar_one()
        records = (
            await session.execute(
                select(func.count(CommandIdempotencyRecord.id)).where(
                    CommandIdempotencyRecord.principal_id == principal_id
                )
            )
        ).scalar_one()
    return projects, events, records


class AsyncBarrier:
    """Deterministic task rendezvous with an explicit failure bound."""

    def __init__(self, parties: int) -> None:
        self._parties = parties
        self._lock = asyncio.Lock()
        self._all_arrived = asyncio.Event()
        self.arrivals = 0

    async def wait(self) -> None:
        async with self._lock:
            self.arrivals += 1
            if self.arrivals == self._parties:
                self._all_arrived.set()
        await asyncio.wait_for(
            self._all_arrived.wait(),
            timeout=TEST_SYNC_TIMEOUT_SECONDS,
        )


class BarrierPaintProjectRepository(SqlAlchemyPaintProjectRepository):
    """Rendezvous immediately before preserving the real PostgreSQL claim."""

    def __init__(self, session: AsyncSession, barrier: AsyncBarrier) -> None:
        super().__init__(session)
        self._barrier = barrier

    async def claim_create_command(self, **arguments: object):  # type: ignore[no-untyped-def]
        await self._barrier.wait()
        return await super().claim_create_command(**arguments)  # type: ignore[arg-type]


class SignalingPaintProjectRepository(SqlAlchemyPaintProjectRepository):
    """Expose the real waiter backend PID before executing the real claim."""

    def __init__(self, session: AsyncSession, claim_entered: asyncio.Event) -> None:
        super().__init__(session)
        self._claim_entered = claim_entered
        self.backend_pid: int | None = None

    async def claim_create_command(self, **arguments: object):  # type: ignore[no-untyped-def]
        self.backend_pid = (
            await self._session.execute(text("SELECT pg_backend_pid()"))
        ).scalar_one()
        self._claim_entered.set()
        return await super().claim_create_command(**arguments)  # type: ignore[arg-type]


class GatedSignalingPaintProjectRepository(SqlAlchemyPaintProjectRepository):
    """Expose the waiter PID and hold it immediately before the real claim."""

    def __init__(
        self,
        session: AsyncSession,
        backend_ready: asyncio.Event,
        continue_claim: asyncio.Event,
    ) -> None:
        super().__init__(session)
        self._backend_ready = backend_ready
        self._continue_claim = continue_claim
        self.backend_pid: int | None = None

    async def claim_create_command(self, **arguments: object):  # type: ignore[no-untyped-def]
        self.backend_pid = (
            await self._session.execute(text("SELECT pg_backend_pid()"))
        ).scalar_one()
        self._backend_ready.set()
        await asyncio.wait_for(
            self._continue_claim.wait(),
            timeout=TEST_SYNC_TIMEOUT_SECONDS,
        )
        return await super().claim_create_command(**arguments)  # type: ignore[arg-type]


class StatementDelayRepository(SqlAlchemyPaintProjectRepository):
    """Inject a real PostgreSQL delay before preserving the real claim call."""

    async def claim_create_command(self, **arguments: object):  # type: ignore[no-untyped-def]
        await self._session.execute(
            text("SELECT pg_sleep(:delay_seconds)"),
            {"delay_seconds": 0.2},
        )
        return await super().claim_create_command(**arguments)  # type: ignore[arg-type]


class TimeoutObservingRepository(SqlAlchemyPaintProjectRepository):
    """Observe the active transaction settings, then execute the real claim."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.observed: tuple[str, str] | None = None

    async def claim_create_command(self, **arguments: object):  # type: ignore[no-untyped-def]
        row = (
            await self._session.execute(
                text(
                    """
                    SELECT
                        current_setting('lock_timeout'),
                        current_setting('statement_timeout')
                    """
                )
            )
        ).one()
        self.observed = (row[0], row[1])
        return await super().claim_create_command(**arguments)  # type: ignore[arg-type]


async def _run_pair[FirstResult, SecondResult](
    first: Awaitable[FirstResult],
    second: Awaitable[SecondResult],
) -> tuple[FirstResult, SecondResult]:
    async with asyncio.timeout(TEST_OPERATION_TIMEOUT_SECONDS):
        async with asyncio.TaskGroup() as task_group:
            first_task = task_group.create_task(first)
            second_task = task_group.create_task(second)
    return first_task.result(), second_task.result()


async def _create_with_repository(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    repository_factory: type[SqlAlchemyPaintProjectRepository],
    repository_arguments: tuple[object, ...],
    payload: CreatePaintProjectRequest,
    principal: PrincipalContext,
    idempotency_key: uuid.UUID,
    lock_timeout_ms: int = TEST_LOCK_TIMEOUT_MS,
    statement_timeout_ms: int = TEST_STATEMENT_TIMEOUT_MS,
) -> CreatePaintProjectResult:
    async with session_factory() as session:
        repository = repository_factory(session, *repository_arguments)
        return await PaintProjectService(
            session,
            repository,
            database_lock_timeout_ms=lock_timeout_ms,
            database_statement_timeout_ms=statement_timeout_ms,
        ).create_project(
            payload=payload,
            principal=principal,
            idempotency_key=idempotency_key,
            correlation_id=uuid.uuid4(),
        )


async def _create_or_conflict(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    barrier: AsyncBarrier,
    payload: CreatePaintProjectRequest,
    principal: PrincipalContext,
    idempotency_key: uuid.UUID,
) -> CreatePaintProjectResult | IdempotencyKeyReusedError:
    try:
        return await _create_with_repository(
            session_factory,
            repository_factory=BarrierPaintProjectRepository,
            repository_arguments=(barrier,),
            payload=payload,
            principal=principal,
            idempotency_key=idempotency_key,
        )
    except IdempotencyKeyReusedError as error:
        return error


async def _wait_until_blocked_by(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    blocked_pid: int,
    blocking_pid: int,
    observer: AsyncSession | None = None,
) -> None:
    query = text(
        """
        SELECT EXISTS (
            SELECT 1
            FROM pg_stat_activity
            WHERE pid = :blocked_pid
              AND state = 'active'
              AND wait_event_type = 'Lock'
              AND :blocking_pid = ANY(pg_blocking_pids(pid))
        )
        """
    )
    refresh_stats_snapshot = text("SELECT pg_stat_clear_snapshot()")

    async def observe(active_observer: AsyncSession) -> None:
        while True:
            await active_observer.execute(refresh_stats_snapshot)
            is_blocked = (
                await active_observer.execute(
                    query,
                    {
                        "blocked_pid": blocked_pid,
                        "blocking_pid": blocking_pid,
                    },
                )
            ).scalar_one()
            if is_blocked:
                return
            await asyncio.sleep(0)

    try:
        async with asyncio.timeout(TEST_SYNC_TIMEOUT_SECONDS):
            if observer is not None:
                await observe(observer)
                return
            async with session_factory() as owned_observer:
                await observe(owned_observer)
    except TimeoutError:
        raise AssertionError(
            f"Timed out after {TEST_SYNC_TIMEOUT_SECONDS} seconds waiting for "
            f"PostgreSQL backend {blocked_pid} to be blocked by backend {blocking_pid}."
        ) from None


async def _wait_for_blocked_pid_by(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    blocking_pid: int,
    observer: AsyncSession | None = None,
) -> int:
    query = text(
        """
        SELECT pid
        FROM pg_stat_activity
        WHERE state = 'active'
          AND wait_event_type = 'Lock'
          AND :blocking_pid = ANY(pg_blocking_pids(pid))
        ORDER BY pid
        LIMIT 1
        """
    )
    refresh_stats_snapshot = text("SELECT pg_stat_clear_snapshot()")

    async def observe(active_observer: AsyncSession) -> int:
        while True:
            await active_observer.execute(refresh_stats_snapshot)
            blocked_pid = (
                await active_observer.execute(
                    query,
                    {"blocking_pid": blocking_pid},
                )
            ).scalar_one_or_none()
            if blocked_pid is not None:
                return blocked_pid
            await asyncio.sleep(0)

    try:
        async with asyncio.timeout(TEST_SYNC_TIMEOUT_SECONDS):
            if observer is not None:
                return await observe(observer)
            async with session_factory() as owned_observer:
                return await observe(owned_observer)
    except TimeoutError:
        raise AssertionError(
            f"Timed out after {TEST_SYNC_TIMEOUT_SECONDS} seconds waiting for a "
            f"PostgreSQL backend blocked by backend {blocking_pid}."
        ) from None


async def _idempotency_record(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    principal_id: str,
    idempotency_key: uuid.UUID,
) -> CommandIdempotencyRecord:
    async with session_factory() as session, session.begin():
        return (
            await session.execute(
                select(CommandIdempotencyRecord).where(
                    CommandIdempotencyRecord.scope_key == create_scope_key(principal_id),
                    CommandIdempotencyRecord.idempotency_key == idempotency_key,
                )
            )
        ).scalar_one()


def test_api_create_replay_list_detail_owner_isolation_and_restart_persistence(
    integration_identity: IntegrationIdentity,
) -> None:
    settings = integration_identity.settings
    first_key = uuid.uuid4()
    payload = {"title": "  First project  ", "description": "  Planning only  "}
    app = create_app(settings)

    with TestClient(app, raise_server_exceptions=False) as client:
        created = client.post(
            "/api/v1/paint-projects?owner_principal_id=query-attacker",
            headers={
                "Idempotency-Key": str(first_key),
                "X-Principal-ID": "header-attacker",
                "X-Owner-Principal-ID": "header-attacker",
            },
            json=payload,
        )
        replayed = client.post(
            "/api/v1/paint-projects",
            headers={"Idempotency-Key": str(first_key)},
            json=payload,
        )
        conflict = client.post(
            "/api/v1/paint-projects",
            headers={"Idempotency-Key": str(first_key)},
            json={"title": "Different project"},
        )
        rejected_owner = client.post(
            "/api/v1/paint-projects",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json={"title": "Attack", "owner_principal_id": "other-owner"},
        )

        assert created.status_code == 201
        created_body = created.json()
        project_id = uuid.UUID(created_body["id"])
        assert created_body["owner_principal_id"] == integration_identity.principal_id
        assert created_body["title"] == "First project"
        assert created_body["description"] == "Planning only"
        assert created_body["requested_target_style"] == "cel_shading"
        assert created_body["planning_mode"] == "planning_only_demo"
        assert created_body["status"] == "DRAFT"
        assert project_id != first_key

        assert replayed.status_code == 201
        assert replayed.headers["Idempotent-Replayed"] == "true"
        assert replayed.json() == created_body
        assert conflict.status_code == 409
        assert conflict.json()["error_code"] == "IDEMPOTENCY_KEY_REUSED"
        assert rejected_owner.status_code == 422

        second = client.post(
            "/api/v1/paint-projects",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json={"title": "Second project"},
        )
        assert second.status_code == 201
        second_project_id = uuid.UUID(second.json()["id"])

        listed = client.get("/api/v1/paint-projects")
        page = client.get("/api/v1/paint-projects?limit=1&offset=1")
        detail = client.get(f"/api/v1/paint-projects/{project_id}")
        missing = client.get(f"/api/v1/paint-projects/{uuid.uuid4()}")

        assert listed.status_code == 200
        assert listed.json()["total"] == 2
        assert [item["id"] for item in listed.json()["items"]] == [
            str(second_project_id),
            str(project_id),
        ]
        assert page.status_code == 200
        assert page.json()["total"] == 2
        assert page.json()["limit"] == 1
        assert page.json()["offset"] == 1
        assert [item["id"] for item in page.json()["items"]] == [str(project_id)]
        assert detail.status_code == 200
        assert detail.json() == created_body
        assert missing.status_code == 404

    restarted_app = create_app(settings)
    with TestClient(restarted_app, raise_server_exceptions=False) as restarted_client:
        after_restart = restarted_client.get(f"/api/v1/paint-projects/{project_id}")
    assert after_restart.status_code == 200
    assert after_restart.json() == created_body

    other_owner_settings = _settings(f"other-{uuid.uuid4().hex}")
    other_owner_app = create_app(other_owner_settings)
    with TestClient(other_owner_app, raise_server_exceptions=False) as other_client:
        hidden_detail = other_client.get(f"/api/v1/paint-projects/{project_id}")
        hidden_list = other_client.get("/api/v1/paint-projects")
    assert hidden_detail.status_code == 404
    assert hidden_list.status_code == 200
    assert hidden_list.json() == {
        "items": [],
        "total": 0,
        "limit": 20,
        "offset": 0,
    }

    async def assert_database_facts() -> None:
        engine = create_database_engine(settings)
        factory = create_database_session_factory(engine)
        try:
            assert await _counts(factory, integration_identity.principal_id) == (2, 2, 2)
            async with factory() as session, session.begin():
                event = (
                    await session.execute(
                        select(StateTransitionEvent).where(
                            StateTransitionEvent.project_id == project_id
                        )
                    )
                ).scalar_one()
                record = (
                    await session.execute(
                        select(CommandIdempotencyRecord).where(
                            CommandIdempotencyRecord.scope_key
                            == create_scope_key(integration_identity.principal_id),
                            CommandIdempotencyRecord.idempotency_key == first_key,
                        )
                    )
                ).scalar_one()
                assert event.from_state is None
                assert event.to_state == "DRAFT"
                assert event.event == "create_project"
                assert event.actor_type == "user"
                assert event.actor_principal_id == integration_identity.principal_id
                assert event.actor_display_name_snapshot == ("Phase 1D-2 Integration Owner")
                assert event.reason == "project_created"
                assert event.event_metadata == {}
                assert record.execution_status == "completed"
                assert record.resource_type == "paint_project"
                assert record.resource_id == project_id
                assert record.http_status == 201
                assert record.response_snapshot == created_body
                assert record.expires_at - record.created_at == timedelta(hours=24)
        finally:
            await engine.dispose()

    asyncio.run(assert_database_facts())


class InvalidInitialEventRepository(SqlAlchemyPaintProjectRepository):
    """Inject a real database Check violation after all three writes are staged."""

    def add_initial_event(self, event: StateTransitionEvent) -> None:
        event.reason = "invalid_reason"
        super().add_initial_event(event)


def test_real_constraint_failure_rolls_back_all_rows_and_session_recovers(
    integration_identity: IntegrationIdentity,
) -> None:
    async def run_scenario() -> None:
        engine = create_database_engine(integration_identity.settings)
        factory = create_database_session_factory(engine)
        idempotency_key = uuid.uuid4()
        payload = CreatePaintProjectRequest(title="Rollback project")
        try:
            async with factory() as session:
                failing_service = PaintProjectService(
                    session,
                    InvalidInitialEventRepository(session),
                )
                with pytest.raises(SQLAlchemyError):
                    await failing_service.create_project(
                        payload=payload,
                        principal=integration_identity.principal,
                        idempotency_key=idempotency_key,
                        correlation_id=uuid.uuid4(),
                    )
                assert await _counts(factory, integration_identity.principal_id) == (0, 0, 0)

                async with session.begin():
                    assert (await session.execute(text("SELECT 1"))).scalar_one() == 1

                recovered = await PaintProjectService(session).create_project(
                    payload=payload,
                    principal=integration_identity.principal,
                    idempotency_key=idempotency_key,
                    correlation_id=uuid.uuid4(),
                )
                assert recovered.replayed is False

            assert await _counts(factory, integration_identity.principal_id) == (1, 1, 1)
        finally:
            await engine.dispose()

    asyncio.run(run_scenario())


def test_matrix_a_concurrent_same_principal_key_and_payload_creates_and_replays(
    integration_identity: IntegrationIdentity,
) -> None:
    async def run_scenario() -> None:
        engine = create_database_engine(integration_identity.settings)
        factory = create_database_session_factory(engine)
        idempotency_key = uuid.uuid4()
        barrier = AsyncBarrier(2)
        payload = CreatePaintProjectRequest(
            title="Concurrent project",
            description="Same logical command",
        )

        try:
            first, second = await _run_pair(
                _create_with_repository(
                    factory,
                    repository_factory=BarrierPaintProjectRepository,
                    repository_arguments=(barrier,),
                    payload=payload,
                    principal=integration_identity.principal,
                    idempotency_key=idempotency_key,
                ),
                _create_with_repository(
                    factory,
                    repository_factory=BarrierPaintProjectRepository,
                    repository_arguments=(barrier,),
                    payload=payload,
                    principal=integration_identity.principal,
                    idempotency_key=idempotency_key,
                ),
            )
            assert barrier.arrivals == 2
            assert first.http_status == second.http_status == 201
            assert first.project.id == second.project.id
            assert sorted((first.replayed, second.replayed)) == [False, True]
            assert await _counts(factory, integration_identity.principal_id) == (1, 1, 1)
        finally:
            await engine.dispose()

    asyncio.run(run_scenario())


def test_matrix_b_concurrent_same_key_different_payload_is_one_success_one_conflict(
    integration_identity: IntegrationIdentity,
) -> None:
    async def run_scenario() -> None:
        engine = create_database_engine(integration_identity.settings)
        factory = create_database_session_factory(engine)
        idempotency_key = uuid.uuid4()
        barrier = AsyncBarrier(2)
        first_payload = CreatePaintProjectRequest(title="Concurrent payload A")
        second_payload = CreatePaintProjectRequest(title="Concurrent payload B")
        try:
            first, second = await _run_pair(
                _create_or_conflict(
                    factory,
                    barrier=barrier,
                    payload=first_payload,
                    principal=integration_identity.principal,
                    idempotency_key=idempotency_key,
                ),
                _create_or_conflict(
                    factory,
                    barrier=barrier,
                    payload=second_payload,
                    principal=integration_identity.principal,
                    idempotency_key=idempotency_key,
                ),
            )
            outcomes = (first, second)
            successes = [
                outcome for outcome in outcomes if isinstance(outcome, CreatePaintProjectResult)
            ]
            conflicts = [
                outcome for outcome in outcomes if isinstance(outcome, IdempotencyKeyReusedError)
            ]
            assert barrier.arrivals == 2
            assert len(successes) == 1
            assert len(conflicts) == 1
            assert successes[0].http_status == 201
            assert conflicts[0].status_code == 409
            assert await _counts(factory, integration_identity.principal_id) == (1, 1, 1)

            successful_payload = (
                first_payload
                if successes[0].project.title == first_payload.title
                else second_payload
            )
            record = await _idempotency_record(
                factory,
                principal_id=integration_identity.principal_id,
                idempotency_key=idempotency_key,
            )
            assert record.payload_hash == create_payload_hash(successful_payload)
        finally:
            await engine.dispose()

    asyncio.run(run_scenario())


def test_matrix_c_and_i_concurrent_cross_principal_scope_and_owner_isolation(
    integration_identity: IntegrationIdentity,
) -> None:
    async def run_scenario() -> None:
        second_principal_id = f"phase1d2-other-{uuid.uuid4().hex}"
        second_identity = IntegrationIdentity(
            settings=_settings(second_principal_id),
            principal_id=second_principal_id,
        )
        engine = create_database_engine(integration_identity.settings)
        factory = create_database_session_factory(engine)
        idempotency_key = uuid.uuid4()
        barrier = AsyncBarrier(2)
        payload = CreatePaintProjectRequest(title="Cross-principal command")
        try:
            first, second = await _run_pair(
                _create_with_repository(
                    factory,
                    repository_factory=BarrierPaintProjectRepository,
                    repository_arguments=(barrier,),
                    payload=payload,
                    principal=integration_identity.principal,
                    idempotency_key=idempotency_key,
                ),
                _create_with_repository(
                    factory,
                    repository_factory=BarrierPaintProjectRepository,
                    repository_arguments=(barrier,),
                    payload=payload,
                    principal=second_identity.principal,
                    idempotency_key=idempotency_key,
                ),
            )
            assert barrier.arrivals == 2
            assert first.replayed is second.replayed is False
            assert first.http_status == second.http_status == 201
            assert first.project.id != second.project.id
            assert await _counts(factory, integration_identity.principal_id) == (1, 1, 1)
            assert await _counts(factory, second_principal_id) == (1, 1, 1)

            async with factory() as first_session:
                first_service = PaintProjectService(first_session)
                first_list = await first_service.list_projects(
                    principal=integration_identity.principal,
                    limit=20,
                    offset=0,
                )
                assert [item.id for item in first_list.items] == [first.project.id]
                with pytest.raises(PaintProjectNotFoundError):
                    await first_service.get_project(
                        project_id=second.project.id,
                        principal=integration_identity.principal,
                    )

            async with factory() as second_session:
                second_service = PaintProjectService(second_session)
                second_list = await second_service.list_projects(
                    principal=second_identity.principal,
                    limit=20,
                    offset=0,
                )
                assert [item.id for item in second_list.items] == [second.project.id]
                with pytest.raises(PaintProjectNotFoundError) as hidden:
                    await second_service.get_project(
                        project_id=first.project.id,
                        principal=second_identity.principal,
                    )
                assert hidden.value.status_code == 404
                assert first.project.title not in hidden.value.message
                assert integration_identity.principal_id not in hidden.value.message
        finally:
            await engine.dispose()
            await _cleanup(second_identity)

    asyncio.run(run_scenario())


def test_matrix_d_concurrent_different_keys_create_distinct_projects(
    integration_identity: IntegrationIdentity,
) -> None:
    async def run_scenario() -> None:
        engine = create_database_engine(integration_identity.settings)
        factory = create_database_session_factory(engine)
        barrier = AsyncBarrier(2)
        payload = CreatePaintProjectRequest(title="Independent commands")
        try:
            first, second = await _run_pair(
                _create_with_repository(
                    factory,
                    repository_factory=BarrierPaintProjectRepository,
                    repository_arguments=(barrier,),
                    payload=payload,
                    principal=integration_identity.principal,
                    idempotency_key=uuid.uuid4(),
                ),
                _create_with_repository(
                    factory,
                    repository_factory=BarrierPaintProjectRepository,
                    repository_arguments=(barrier,),
                    payload=payload,
                    principal=integration_identity.principal,
                    idempotency_key=uuid.uuid4(),
                ),
            )
            assert barrier.arrivals == 2
            assert first.replayed is second.replayed is False
            assert first.project.id != second.project.id
            assert await _counts(factory, integration_identity.principal_id) == (2, 2, 2)
        finally:
            await engine.dispose()

    asyncio.run(run_scenario())


def test_matrix_e_committed_result_replays_after_response_confirmation_loss(
    integration_identity: IntegrationIdentity,
) -> None:
    class ResponseConfirmationLost(ConnectionError):
        pass

    async def run_scenario() -> None:
        engine = create_database_engine(integration_identity.settings)
        factory = create_database_session_factory(engine)
        idempotency_key = uuid.uuid4()
        payload = CreatePaintProjectRequest(title="Unknown response outcome")

        async def send_without_confirmation() -> None:
            async with factory() as session:
                await PaintProjectService(session).create_project(
                    payload=payload,
                    principal=integration_identity.principal,
                    idempotency_key=idempotency_key,
                    correlation_id=uuid.uuid4(),
                )
            raise ResponseConfirmationLost("response confirmation was not delivered")

        try:
            with pytest.raises(ResponseConfirmationLost):
                await send_without_confirmation()
            assert await _counts(factory, integration_identity.principal_id) == (1, 1, 1)

            async with factory() as retry_session:
                replayed = await PaintProjectService(retry_session).create_project(
                    payload=payload,
                    principal=integration_identity.principal,
                    idempotency_key=idempotency_key,
                    correlation_id=uuid.uuid4(),
                )
            assert replayed.replayed is True
            assert replayed.http_status == 201
            assert await _counts(factory, integration_identity.principal_id) == (1, 1, 1)
        finally:
            await engine.dispose()

    asyncio.run(run_scenario())


def test_cached_stats_snapshot_is_refreshed_before_real_block_observation(
    integration_identity: IntegrationIdentity,
) -> None:
    async def run_scenario() -> None:
        engine = create_database_engine(integration_identity.settings)
        factory = create_database_session_factory(engine)
        idempotency_key = uuid.uuid4()
        payload = CreatePaintProjectRequest(title="Cached stats snapshot")
        created_at = datetime.now(UTC)
        blocking_observation_query = text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM pg_stat_activity
                WHERE pid = :blocked_pid
                  AND state = 'active'
                  AND wait_event_type = 'Lock'
                  AND :blocking_pid = ANY(pg_blocking_pids(pid))
            )
            """
        )
        winner_session = factory()
        winner_transaction = await winner_session.begin()
        waiter_session = factory()
        observer_session = factory()
        control_session = factory()
        backend_ready = asyncio.Event()
        continue_claim = asyncio.Event()
        waiter_repository = GatedSignalingPaintProjectRepository(
            waiter_session,
            backend_ready,
            continue_claim,
        )
        waiter_task: asyncio.Task[CreatePaintProjectResult] | None = None
        try:
            winner_repository = SqlAlchemyPaintProjectRepository(winner_session)
            await winner_repository.configure_create_transaction_timeouts(
                lock_timeout_ms=TEST_SNAPSHOT_REGRESSION_LOCK_TIMEOUT_MS,
                statement_timeout_ms=TEST_SNAPSHOT_REGRESSION_STATEMENT_TIMEOUT_MS,
            )
            winner_pid = (
                await winner_session.execute(text("SELECT pg_backend_pid()"))
            ).scalar_one()
            winner_claim = await winner_repository.claim_create_command(
                record_id=uuid.uuid4(),
                scope_key=create_scope_key(integration_identity.principal_id),
                principal_id=integration_identity.principal_id,
                idempotency_key=idempotency_key,
                payload_hash=create_payload_hash(payload),
                created_at=created_at,
                expires_at=created_at + timedelta(hours=24),
            )
            assert winner_claim.acquired is True

            async def waiting_create() -> CreatePaintProjectResult:
                return await PaintProjectService(
                    waiter_session,
                    waiter_repository,
                    database_lock_timeout_ms=TEST_SNAPSHOT_REGRESSION_LOCK_TIMEOUT_MS,
                    database_statement_timeout_ms=(TEST_SNAPSHOT_REGRESSION_STATEMENT_TIMEOUT_MS),
                ).create_project(
                    payload=payload,
                    principal=integration_identity.principal,
                    idempotency_key=idempotency_key,
                    correlation_id=uuid.uuid4(),
                )

            async with asyncio.timeout(TEST_OPERATION_TIMEOUT_SECONDS):
                async with asyncio.TaskGroup() as task_group:
                    waiter_task = task_group.create_task(waiting_create())
                    await asyncio.wait_for(
                        backend_ready.wait(),
                        timeout=TEST_SYNC_TIMEOUT_SECONDS,
                    )
                    assert waiter_repository.backend_pid is not None
                    waiter_pid = waiter_repository.backend_pid

                    consistency = (
                        await observer_session.execute(
                            text(
                                """
                                SELECT set_config(
                                    'stats_fetch_consistency',
                                    :consistency,
                                    true
                                )
                                """
                            ),
                            {"consistency": "cache"},
                        )
                    ).scalar_one()
                    assert consistency == "cache"
                    observer_pid = (
                        await observer_session.execute(text("SELECT pg_backend_pid()"))
                    ).scalar_one()
                    control_pid = (
                        await control_session.execute(text("SELECT pg_backend_pid()"))
                    ).scalar_one()
                    assert len({winner_pid, waiter_pid, observer_pid, control_pid}) == 4

                    blocking_parameters = {
                        "blocked_pid": waiter_pid,
                        "blocking_pid": winner_pid,
                    }
                    stale_is_blocked = (
                        await observer_session.execute(
                            blocking_observation_query,
                            blocking_parameters,
                        )
                    ).scalar_one()
                    assert stale_is_blocked is False

                    continue_claim.set()
                    await _wait_until_blocked_by(
                        factory,
                        blocked_pid=waiter_pid,
                        blocking_pid=winner_pid,
                        observer=control_session,
                    )
                    assert waiter_task.done() is False
                    cached_after_block = (
                        await observer_session.execute(
                            blocking_observation_query,
                            blocking_parameters,
                        )
                    ).scalar_one()
                    assert cached_after_block is False
                    await _wait_until_blocked_by(
                        factory,
                        blocked_pid=waiter_pid,
                        blocking_pid=winner_pid,
                        observer=observer_session,
                    )
                    assert waiter_task.done() is False
                    await winner_transaction.rollback()

            assert waiter_task is not None
            result = waiter_task.result()
            assert result.replayed is False
            assert waiter_task.done() is True
            assert await _counts(factory, integration_identity.principal_id) == (1, 1, 1)
        finally:
            continue_claim.set()
            if winner_transaction.is_active:
                await winner_transaction.rollback()
            await control_session.close()
            await observer_session.close()
            await waiter_session.close()
            await winner_session.close()
            await engine.dispose()

        await _cleanup(integration_identity)
        verification_engine = create_database_engine(integration_identity.settings)
        verification_factory = create_database_session_factory(verification_engine)
        try:
            assert await _counts(verification_factory, integration_identity.principal_id) == (
                0,
                0,
                0,
            )
        finally:
            await verification_engine.dispose()

    asyncio.run(run_scenario())


def test_matrix_f_waiter_acquires_after_confirmed_blocked_winner_rolls_back(
    integration_identity: IntegrationIdentity,
) -> None:
    async def run_scenario() -> None:
        engine = create_database_engine(integration_identity.settings)
        factory = create_database_session_factory(engine)
        idempotency_key = uuid.uuid4()
        payload = CreatePaintProjectRequest(title="Rollback winner")
        created_at = datetime.now(UTC)
        winner_session = factory()
        winner_transaction = await winner_session.begin()
        winner_repository = SqlAlchemyPaintProjectRepository(winner_session)
        claim_entered = asyncio.Event()
        waiter_session = factory()
        waiter_repository = SignalingPaintProjectRepository(waiter_session, claim_entered)
        try:
            await winner_repository.configure_create_transaction_timeouts(
                lock_timeout_ms=TEST_LOCK_TIMEOUT_MS,
                statement_timeout_ms=TEST_STATEMENT_TIMEOUT_MS,
            )
            winner_pid = (
                await winner_session.execute(text("SELECT pg_backend_pid()"))
            ).scalar_one()
            claim = await winner_repository.claim_create_command(
                record_id=uuid.uuid4(),
                scope_key=create_scope_key(integration_identity.principal_id),
                principal_id=integration_identity.principal_id,
                idempotency_key=idempotency_key,
                payload_hash=create_payload_hash(payload),
                created_at=created_at,
                expires_at=created_at + timedelta(hours=24),
            )
            assert claim.acquired is True

            async def waiting_create() -> CreatePaintProjectResult:
                return await PaintProjectService(
                    waiter_session,
                    waiter_repository,
                    database_lock_timeout_ms=TEST_LOCK_TIMEOUT_MS,
                    database_statement_timeout_ms=TEST_STATEMENT_TIMEOUT_MS,
                ).create_project(
                    payload=payload,
                    principal=integration_identity.principal,
                    idempotency_key=idempotency_key,
                    correlation_id=uuid.uuid4(),
                )

            async with asyncio.timeout(TEST_OPERATION_TIMEOUT_SECONDS):
                async with asyncio.TaskGroup() as task_group:
                    waiter = task_group.create_task(waiting_create())
                    await asyncio.wait_for(
                        claim_entered.wait(),
                        timeout=TEST_SYNC_TIMEOUT_SECONDS,
                    )
                    assert waiter_repository.backend_pid is not None
                    await _wait_until_blocked_by(
                        factory,
                        blocked_pid=waiter_repository.backend_pid,
                        blocking_pid=winner_pid,
                    )
                    assert waiter.done() is False
                    await winner_transaction.rollback()
            result = waiter.result()
            assert result.replayed is False
            assert await _counts(factory, integration_identity.principal_id) == (1, 1, 1)
        finally:
            if winner_transaction.is_active:
                await winner_transaction.rollback()
            await waiter_session.close()
            await winner_session.close()
            await engine.dispose()

    asyncio.run(run_scenario())


def test_matrix_g_expired_record_concurrent_replay_and_conflict_remain_stable(
    integration_identity: IntegrationIdentity,
) -> None:
    async def run_scenario() -> None:
        engine = create_database_engine(integration_identity.settings)
        factory = create_database_session_factory(engine)
        idempotency_key = uuid.uuid4()
        payload = CreatePaintProjectRequest(title="Retention project")
        try:
            async with factory() as session:
                created = await PaintProjectService(session).create_project(
                    payload=payload,
                    principal=integration_identity.principal,
                    idempotency_key=idempotency_key,
                    correlation_id=uuid.uuid4(),
                )
                historical_created_at = datetime.now(UTC) - timedelta(hours=48)
                async with session.begin():
                    await session.execute(
                        update(CommandIdempotencyRecord)
                        .where(
                            CommandIdempotencyRecord.scope_key
                            == create_scope_key(integration_identity.principal_id),
                            CommandIdempotencyRecord.idempotency_key == idempotency_key,
                        )
                        .values(
                            created_at=historical_created_at,
                            expires_at=historical_created_at + timedelta(hours=24),
                        )
                    )

            same_barrier = AsyncBarrier(2)
            first_replay, second_replay = await _run_pair(
                _create_with_repository(
                    factory,
                    repository_factory=BarrierPaintProjectRepository,
                    repository_arguments=(same_barrier,),
                    payload=payload,
                    principal=integration_identity.principal,
                    idempotency_key=idempotency_key,
                ),
                _create_with_repository(
                    factory,
                    repository_factory=BarrierPaintProjectRepository,
                    repository_arguments=(same_barrier,),
                    payload=payload,
                    principal=integration_identity.principal,
                    idempotency_key=idempotency_key,
                ),
            )
            assert same_barrier.arrivals == 2
            assert first_replay.replayed is second_replay.replayed is True
            assert first_replay.project.id == second_replay.project.id == created.project.id

            mixed_barrier = AsyncBarrier(2)
            replay_outcome, conflict_outcome = await _run_pair(
                _create_or_conflict(
                    factory,
                    barrier=mixed_barrier,
                    payload=payload,
                    principal=integration_identity.principal,
                    idempotency_key=idempotency_key,
                ),
                _create_or_conflict(
                    factory,
                    barrier=mixed_barrier,
                    payload=CreatePaintProjectRequest(title="Different payload"),
                    principal=integration_identity.principal,
                    idempotency_key=idempotency_key,
                ),
            )
            assert mixed_barrier.arrivals == 2
            assert isinstance(replay_outcome, CreatePaintProjectResult)
            assert replay_outcome.replayed is True
            assert isinstance(conflict_outcome, IdempotencyKeyReusedError)
            assert conflict_outcome.status_code == 409
            record = await _idempotency_record(
                factory,
                principal_id=integration_identity.principal_id,
                idempotency_key=idempotency_key,
            )
            assert record.payload_hash == create_payload_hash(payload)
            assert await _counts(factory, integration_identity.principal_id) == (1, 1, 1)
        finally:
            await engine.dispose()

    asyncio.run(run_scenario())


def test_matrix_h_real_lock_timeout_returns_503_without_partial_writes_and_recovers(
    integration_identity: IntegrationIdentity,
) -> None:
    async def run_scenario() -> None:
        timeout_settings = _settings(
            integration_identity.principal_id,
            lock_timeout_ms=TEST_SHORT_LOCK_TIMEOUT_MS,
            statement_timeout_ms=TEST_SHORT_STATEMENT_TIMEOUT_MS,
        )
        engine = create_database_engine(timeout_settings)
        factory = create_database_session_factory(engine)
        idempotency_key = uuid.uuid4()
        payload = {"title": "Finite lock wait"}
        normalized_payload = CreatePaintProjectRequest.model_validate(payload)
        winner_session = factory()
        winner_transaction = await winner_session.begin()
        winner_repository = SqlAlchemyPaintProjectRepository(winner_session)
        try:
            await winner_repository.configure_create_transaction_timeouts(
                lock_timeout_ms=TEST_SHORT_LOCK_TIMEOUT_MS,
                statement_timeout_ms=TEST_SHORT_STATEMENT_TIMEOUT_MS,
            )
            winner_pid = (
                await winner_session.execute(text("SELECT pg_backend_pid()"))
            ).scalar_one()
            winner_claim = await winner_repository.claim_create_command(
                record_id=uuid.uuid4(),
                scope_key=create_scope_key(integration_identity.principal_id),
                principal_id=integration_identity.principal_id,
                idempotency_key=idempotency_key,
                payload_hash=create_payload_hash(normalized_payload),
                created_at=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(hours=24),
            )
            assert winner_claim.acquired is True

            app = create_app(timeout_settings)
            async with app.router.lifespan_context(app):
                transport = ASGITransport(app=app, raise_app_exceptions=False)
                async with AsyncClient(
                    transport=transport,
                    base_url="http://testserver",
                ) as client:
                    async with asyncio.timeout(TEST_OPERATION_TIMEOUT_SECONDS):
                        async with asyncio.TaskGroup() as task_group:
                            request_task = task_group.create_task(
                                client.post(
                                    "/api/v1/paint-projects",
                                    headers={"Idempotency-Key": str(idempotency_key)},
                                    json=payload,
                                )
                            )
                            blocked_pid = await _wait_for_blocked_pid_by(
                                factory,
                                blocking_pid=winner_pid,
                            )
                            assert blocked_pid != winner_pid
                    response = request_task.result()
                    assert response.status_code == 503
                    assert response.json()["error_code"] == "DATABASE_WAIT_TIMEOUT"
                    assert response.json()["retryable"] is True
                    assert "lock_timeout" not in response.text
                    assert "postgresql" not in response.text.lower()
                    assert await _counts(factory, integration_identity.principal_id) == (0, 0, 0)

                    await winner_transaction.rollback()
                    retry = await client.post(
                        "/api/v1/paint-projects",
                        headers={"Idempotency-Key": str(idempotency_key)},
                        json=payload,
                    )
                    assert retry.status_code == 201
                    assert retry.headers.get("Idempotent-Replayed") is None
            assert await _counts(factory, integration_identity.principal_id) == (1, 1, 1)
        finally:
            if winner_transaction.is_active:
                await winner_transaction.rollback()
            await winner_session.close()
            await engine.dispose()

    asyncio.run(run_scenario())


def test_real_statement_timeout_is_tagged_and_leaves_no_partial_writes(
    integration_identity: IntegrationIdentity,
) -> None:
    async def run_scenario() -> None:
        engine = create_database_engine(integration_identity.settings)
        factory = create_database_session_factory(engine)
        try:
            async with factory() as session:
                repository = StatementDelayRepository(session)
                with pytest.raises(DatabaseWaitTimeoutError) as captured:
                    await PaintProjectService(
                        session,
                        repository,
                        database_lock_timeout_ms=TEST_LOCK_TIMEOUT_MS,
                        database_statement_timeout_ms=TEST_STATEMENT_PROBE_TIMEOUT_MS,
                    ).create_project(
                        payload=CreatePaintProjectRequest(title="Statement timeout"),
                        principal=integration_identity.principal,
                        idempotency_key=uuid.uuid4(),
                        correlation_id=uuid.uuid4(),
                    )
                assert captured.value.sqlstate == "57014"
                assert captured.value.status_code == 503
                assert captured.value.retryable is True
            assert await _counts(factory, integration_identity.principal_id) == (0, 0, 0)
        finally:
            await engine.dispose()

    asyncio.run(run_scenario())


def test_transaction_local_timeouts_do_not_contaminate_later_transactions(
    integration_identity: IntegrationIdentity,
) -> None:
    async def run_scenario() -> None:
        engine = create_database_engine(integration_identity.settings)
        factory = create_database_session_factory(engine)
        settings_query = text(
            """
            SELECT
                current_setting('lock_timeout'),
                current_setting('statement_timeout')
            """
        )
        try:
            async with factory() as session:
                async with session.begin():
                    baseline_row = (await session.execute(settings_query)).one()
                    baseline = (baseline_row[0], baseline_row[1])

                repository = TimeoutObservingRepository(session)
                created = await PaintProjectService(
                    session,
                    repository,
                    database_lock_timeout_ms=321,
                    database_statement_timeout_ms=654,
                ).create_project(
                    payload=CreatePaintProjectRequest(title="Local timeout scope"),
                    principal=integration_identity.principal,
                    idempotency_key=uuid.uuid4(),
                    correlation_id=uuid.uuid4(),
                )
                assert created.replayed is False
                assert repository.observed == ("321ms", "654ms")

                async with session.begin():
                    after_row = (await session.execute(settings_query)).one()
                    after = (after_row[0], after_row[1])
                assert after == baseline
            assert await _counts(factory, integration_identity.principal_id) == (1, 1, 1)
        finally:
            await engine.dispose()

    asyncio.run(run_scenario())


def test_actual_database_connection_failure_returns_safe_503() -> None:
    unavailable_settings = Settings(
        app_env="test",
        database_url="postgresql+psycopg://synthetic:synthetic-password@127.0.0.1:1/unavailable",
        paintpilot_demo_principal_id="unavailable-test-owner",
        paintpilot_demo_principal_display_name="Unavailable Test Owner",
        _env_file=None,
    )
    app = create_app(unavailable_settings)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/v1/paint-projects",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json={"title": "Unavailable"},
        )

    assert response.status_code == 503
    assert response.json()["error_code"] == "DATABASE_UNAVAILABLE"
    assert response.json()["retryable"] is True
    response_text = response.text.lower()
    assert "synthetic-password" not in response_text
    assert "postgresql" not in response_text
    assert "traceback" not in response_text
