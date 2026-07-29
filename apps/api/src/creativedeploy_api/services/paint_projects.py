"""PaintProject application service, transaction, and idempotency boundary."""

import hashlib
import json
import logging
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import MappingProxyType
from typing import Protocol

from pydantic import ValidationError
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from creativedeploy_api.core.config import (
    DEFAULT_DATABASE_LOCK_TIMEOUT_MS,
    DEFAULT_DATABASE_STATEMENT_TIMEOUT_MS,
    MAX_DATABASE_TRANSACTION_TIMEOUT_MS,
)
from creativedeploy_api.core.principal import PrincipalContext, PrincipalType
from creativedeploy_api.db.models import (
    CommandIdempotencyRecord,
    PaintProject,
    StateTransitionEvent,
)
from creativedeploy_api.db.models.constants import (
    IDEMPOTENCY_STATUS_COMPLETED,
    PLANNING_MODE_DEMO,
    TARGET_STYLE_CEL_SHADING,
)
from creativedeploy_api.repositories.paint_projects import (
    IdempotencyClaim,
    SqlAlchemyPaintProjectRepository,
)
from creativedeploy_api.schemas.errors import ErrorCategory
from creativedeploy_api.schemas.paint_projects import (
    CreatePaintProjectRequest,
    PaintProjectListResponse,
    PaintProjectRead,
)

logger = logging.getLogger(__name__)

CREATE_COMMAND_TYPE = "create_paint_project"
CREATE_PAYLOAD_VERSION = "create_paint_project.v1"
CREATE_EVENT = "create_project"
CREATE_REASON = "project_created"
INITIAL_STATUS = "DRAFT"
IDEMPOTENCY_RETENTION = timedelta(hours=24)


class PaintProjectApplicationError(Exception):
    """Safe application error mapped by the API boundary."""

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    category: ErrorCategory = "INTERNAL_ERROR"
    message: str = "The request could not be completed."
    retryable: bool = False
    current_state: str | None = None
    allowed_actions: tuple[str, ...] = ()
    safe_details: Mapping[str, object] = MappingProxyType({})


class IdempotencyKeyReusedError(PaintProjectApplicationError):
    """The protected command key was reused with a different payload."""

    status_code = 409
    error_code = "IDEMPOTENCY_KEY_REUSED"
    category: ErrorCategory = "IDEMPOTENCY_KEY_REUSED"
    message = "The Idempotency-Key was already used with different project data."
    allowed_actions = (
        "retry_with_original_payload",
        "start_new_command_with_new_idempotency_key",
    )


class PaintProjectNotFoundError(PaintProjectApplicationError):
    """A project is missing or inaccessible in the current owner scope."""

    status_code = 404
    error_code = "PAINT_PROJECT_NOT_FOUND"
    category: ErrorCategory = "NOT_FOUND"
    message = "The paint project was not found."
    allowed_actions = ("list_projects", "create_project")


class PrincipalTypeNotAllowedError(PaintProjectApplicationError):
    """Project creation requires an identified human Principal."""

    status_code = 403
    error_code = "ACTOR_NOT_AUTHORIZED"
    category: ErrorCategory = "CONFLICT"
    message = "The current Principal cannot create a human-owned paint project."


class StoredIdempotencyResultInvalidError(PaintProjectApplicationError):
    """A committed replay record does not satisfy the approved response schema."""

    error_code = "IDEMPOTENCY_RESULT_INVALID"
    message = "The stored command result could not be safely replayed."


class DatabaseWaitTimeoutError(PaintProjectApplicationError):
    """A create transaction exceeded its configured PostgreSQL wait policy."""

    status_code = 503
    error_code = "DATABASE_WAIT_TIMEOUT"
    category: ErrorCategory = "DATABASE_UNAVAILABLE"
    message = "The database could not complete the request within the safe wait limit."
    retryable = True
    allowed_actions = ("retry",)

    def __init__(self, *, sqlstate: str) -> None:
        super().__init__()
        self.sqlstate = sqlstate


@dataclass(frozen=True, slots=True)
class CreatePaintProjectResult:
    """Application result with explicit replay evidence."""

    project: PaintProjectRead
    replayed: bool
    http_status: int = 201


class PaintProjectRepositoryPort(Protocol):
    """The narrow persistence operations required by this service."""

    async def configure_create_transaction_timeouts(
        self,
        *,
        lock_timeout_ms: int,
        statement_timeout_ms: int,
    ) -> None: ...

    async def claim_create_command(
        self,
        *,
        record_id: uuid.UUID,
        scope_key: str,
        principal_id: str,
        idempotency_key: uuid.UUID,
        payload_hash: str,
        created_at: datetime,
        expires_at: datetime,
    ) -> IdempotencyClaim: ...

    def add_project(self, project: PaintProject) -> None: ...

    def add_initial_event(self, event: StateTransitionEvent) -> None: ...

    async def flush(self) -> None: ...

    async def complete_create_command(
        self,
        *,
        record_id: uuid.UUID,
        project_id: uuid.UUID,
        response_snapshot: dict[str, object],
    ) -> None: ...

    async def list_owned_projects(
        self,
        *,
        owner_principal_id: str,
        limit: int,
        offset: int,
    ) -> tuple[Sequence[PaintProject], int]: ...

    async def get_owned_project(
        self,
        *,
        project_id: uuid.UUID,
        owner_principal_id: str,
    ) -> PaintProject | None: ...


def create_scope_key(principal_id: str) -> str:
    """Compute the server-owned create-command scope."""
    return f"principal:{principal_id}:command:{CREATE_COMMAND_TYPE}"


def canonical_create_payload(payload: CreatePaintProjectRequest) -> bytes:
    """Serialize the normalized create payload using the frozen v1 format."""
    canonical = {
        "description": payload.description,
        "title": payload.title,
        "version": CREATE_PAYLOAD_VERSION,
    }
    return json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def create_payload_hash(payload: CreatePaintProjectRequest) -> str:
    """Return the lowercase SHA-256 digest of the canonical v1 payload."""
    return hashlib.sha256(canonical_create_payload(payload)).hexdigest()


def _database_sqlstate(error: DBAPIError) -> str | None:
    original = error.orig
    for attribute in ("sqlstate", "pgcode"):
        value = getattr(original, attribute, None)
        if isinstance(value, str):
            return value
    diagnostic = getattr(original, "diag", None)
    value = getattr(diagnostic, "sqlstate", None)
    return value if isinstance(value, str) else None


def _project_read(project: PaintProject) -> PaintProjectRead:
    return PaintProjectRead.model_validate(project)


def _stored_project_read(record: CommandIdempotencyRecord) -> PaintProjectRead:
    if (
        record.execution_status != IDEMPOTENCY_STATUS_COMPLETED
        or record.http_status != 201
        or record.response_snapshot is None
    ):
        raise StoredIdempotencyResultInvalidError
    try:
        encoded_snapshot = json.dumps(
            record.response_snapshot,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return PaintProjectRead.model_validate_json(encoded_snapshot)
    except (TypeError, ValueError, ValidationError) as error:
        raise StoredIdempotencyResultInvalidError from error


class PaintProjectService:
    """Orchestrate owner-scoped project persistence and approved business rules."""

    def __init__(
        self,
        session: AsyncSession,
        repository: PaintProjectRepositoryPort | None = None,
        *,
        database_lock_timeout_ms: int = DEFAULT_DATABASE_LOCK_TIMEOUT_MS,
        database_statement_timeout_ms: int = DEFAULT_DATABASE_STATEMENT_TIMEOUT_MS,
    ) -> None:
        for name, value in (
            ("database_lock_timeout_ms", database_lock_timeout_ms),
            ("database_statement_timeout_ms", database_statement_timeout_ms),
        ):
            if not 0 < value <= MAX_DATABASE_TRANSACTION_TIMEOUT_MS:
                raise ValueError(f"{name} is outside the approved runtime boundary.")
        self._session = session
        self._repository = repository or SqlAlchemyPaintProjectRepository(session)
        self._database_lock_timeout_ms = database_lock_timeout_ms
        self._database_statement_timeout_ms = database_statement_timeout_ms

    async def create_project(
        self,
        *,
        payload: CreatePaintProjectRequest,
        principal: PrincipalContext,
        idempotency_key: uuid.UUID,
        correlation_id: uuid.UUID,
    ) -> CreatePaintProjectResult:
        """Create or replay one project through a single short transaction."""
        if principal.principal_type is not PrincipalType.HUMAN:
            raise PrincipalTypeNotAllowedError

        payload_hash = create_payload_hash(payload)
        scope_key = create_scope_key(principal.principal_id)
        created_at = datetime.now(UTC)
        result: CreatePaintProjectResult

        try:
            async with self._session.begin():
                await self._repository.configure_create_transaction_timeouts(
                    lock_timeout_ms=self._database_lock_timeout_ms,
                    statement_timeout_ms=self._database_statement_timeout_ms,
                )
                record_id = uuid.uuid4()
                claim = await self._repository.claim_create_command(
                    record_id=record_id,
                    scope_key=scope_key,
                    principal_id=principal.principal_id,
                    idempotency_key=idempotency_key,
                    payload_hash=payload_hash,
                    created_at=created_at,
                    expires_at=created_at + IDEMPOTENCY_RETENTION,
                )
                if not claim.acquired:
                    existing = claim.existing_record
                    if existing is None:
                        raise StoredIdempotencyResultInvalidError
                    if existing.payload_hash != payload_hash:
                        raise IdempotencyKeyReusedError
                    result = CreatePaintProjectResult(
                        project=_stored_project_read(existing),
                        replayed=True,
                    )
                else:
                    project_id = uuid.uuid4()
                    project = PaintProject(
                        id=project_id,
                        owner_principal_id=principal.principal_id,
                        title=payload.title,
                        description=payload.description,
                        requested_target_style=TARGET_STYLE_CEL_SHADING,
                        planning_mode=PLANNING_MODE_DEMO,
                        status=INITIAL_STATUS,
                        created_at=created_at,
                        updated_at=created_at,
                    )
                    event = StateTransitionEvent(
                        id=uuid.uuid4(),
                        project_id=project_id,
                        from_state=None,
                        to_state=INITIAL_STATUS,
                        event=CREATE_EVENT,
                        actor_type="user",
                        actor_principal_id=principal.principal_id,
                        actor_display_name_snapshot=principal.display_name,
                        reason=CREATE_REASON,
                        correlation_id=correlation_id,
                        event_metadata={},
                        created_at=created_at,
                    )
                    self._repository.add_project(project)
                    self._repository.add_initial_event(event)
                    await self._repository.flush()

                    project_read = _project_read(project)
                    acquired_record_id = claim.acquired_record_id
                    if acquired_record_id is None:
                        raise StoredIdempotencyResultInvalidError
                    await self._repository.complete_create_command(
                        record_id=acquired_record_id,
                        project_id=project_id,
                        response_snapshot=project_read.model_dump(mode="json"),
                    )
                    result = CreatePaintProjectResult(
                        project=project_read,
                        replayed=False,
                    )
        except DBAPIError as error:
            sqlstate = _database_sqlstate(error)
            if sqlstate in {"55P03", "57014"}:
                raise DatabaseWaitTimeoutError(sqlstate=sqlstate) from error
            raise

        logger.info(
            "PaintProject create command completed",
            extra={
                "request_id": str(correlation_id),
                "principal_id": principal.principal_id,
                "project_id": str(result.project.id),
                "idempotent_replayed": result.replayed,
            },
        )
        return result

    async def list_projects(
        self,
        *,
        principal: PrincipalContext,
        limit: int,
        offset: int,
    ) -> PaintProjectListResponse:
        """List only projects owned by the current Principal."""
        async with self._session.begin():
            projects, total = await self._repository.list_owned_projects(
                owner_principal_id=principal.principal_id,
                limit=limit,
                offset=offset,
            )
            items = [_project_read(project) for project in projects]
        return PaintProjectListResponse(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
        )

    async def get_project(
        self,
        *,
        project_id: uuid.UUID,
        principal: PrincipalContext,
    ) -> PaintProjectRead:
        """Read within the owner predicate so missing and inaccessible are identical."""
        async with self._session.begin():
            project = await self._repository.get_owned_project(
                project_id=project_id,
                owner_principal_id=principal.principal_id,
            )
            if project is None:
                raise PaintProjectNotFoundError
            return _project_read(project)
