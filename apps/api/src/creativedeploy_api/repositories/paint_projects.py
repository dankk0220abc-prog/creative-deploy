"""SQLAlchemy persistence access for the PaintProject application service."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from creativedeploy_api.db.models import (
    CommandIdempotencyRecord,
    PaintProject,
    StateTransitionEvent,
)
from creativedeploy_api.db.models.constants import (
    IDEMPOTENCY_STATUS_COMPLETED,
    IDEMPOTENCY_STATUS_IN_PROGRESS,
)


@dataclass(frozen=True, slots=True)
class IdempotencyClaim:
    """Result of database-authoritative create-command arbitration."""

    acquired_record_id: uuid.UUID | None
    existing_record: CommandIdempotencyRecord | None

    @property
    def acquired(self) -> bool:
        """Return whether this transaction owns command execution."""
        return self.acquired_record_id is not None


class SqlAlchemyPaintProjectRepository:
    """Small, PaintProject-specific SQLAlchemy repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def configure_create_transaction_timeouts(
        self,
        *,
        lock_timeout_ms: int,
        statement_timeout_ms: int,
    ) -> None:
        """Apply bounded PostgreSQL wait limits to only the active transaction."""
        await self._session.execute(
            text(
                """
                SELECT
                    set_config('lock_timeout', :lock_timeout, true),
                    set_config('statement_timeout', :statement_timeout, true)
                """
            ),
            {
                "lock_timeout": f"{lock_timeout_ms}ms",
                "statement_timeout": f"{statement_timeout_ms}ms",
            },
        )

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
    ) -> IdempotencyClaim:
        """Acquire execution or read the committed winner after a unique conflict."""
        statement = (
            insert(CommandIdempotencyRecord)
            .values(
                id=record_id,
                scope_key=scope_key,
                principal_id=principal_id,
                command_type="create_paint_project",
                idempotency_key=idempotency_key,
                payload_hash=payload_hash,
                execution_status=IDEMPOTENCY_STATUS_IN_PROGRESS,
                created_at=created_at,
                expires_at=expires_at,
            )
            .on_conflict_do_nothing(
                index_elements=["scope_key", "idempotency_key"],
            )
            .returning(CommandIdempotencyRecord.id)
        )
        claimed_id = (await self._session.execute(statement)).scalar_one_or_none()
        if claimed_id is not None:
            return IdempotencyClaim(
                acquired_record_id=claimed_id,
                existing_record=None,
            )

        existing = (
            await self._session.execute(
                select(CommandIdempotencyRecord).where(
                    CommandIdempotencyRecord.scope_key == scope_key,
                    CommandIdempotencyRecord.idempotency_key == idempotency_key,
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            raise RuntimeError(
                "Idempotency arbitration completed without a claim or committed record."
            )
        return IdempotencyClaim(
            acquired_record_id=None,
            existing_record=existing,
        )

    def add_project(self, project: PaintProject) -> None:
        """Stage a new project in the active service transaction."""
        self._session.add(project)

    def add_initial_event(self, event: StateTransitionEvent) -> None:
        """Stage the authoritative initial event in the same transaction."""
        self._session.add(event)

    async def flush(self) -> None:
        """Flush pending business writes without committing the transaction."""
        await self._session.flush()

    async def complete_create_command(
        self,
        *,
        record_id: uuid.UUID,
        project_id: uuid.UUID,
        response_snapshot: dict[str, object],
    ) -> None:
        """Complete the uncommitted winner record with the controlled response."""
        completed_id = (
            await self._session.execute(
                update(CommandIdempotencyRecord)
                .where(
                    CommandIdempotencyRecord.id == record_id,
                    CommandIdempotencyRecord.execution_status == IDEMPOTENCY_STATUS_IN_PROGRESS,
                )
                .values(
                    execution_status=IDEMPOTENCY_STATUS_COMPLETED,
                    resource_type="paint_project",
                    resource_id=project_id,
                    http_status=201,
                    response_snapshot=response_snapshot,
                )
                .returning(CommandIdempotencyRecord.id)
            )
        ).scalar_one_or_none()
        if completed_id is None:
            raise RuntimeError("The acquired idempotency record could not be completed.")

    async def list_owned_projects(
        self,
        *,
        owner_principal_id: str,
        limit: int,
        offset: int,
    ) -> tuple[list[PaintProject], int]:
        """Return a deterministic page and the pre-pagination owner count."""
        total = (
            await self._session.execute(
                select(func.count(PaintProject.id)).where(
                    PaintProject.owner_principal_id == owner_principal_id
                )
            )
        ).scalar_one()
        projects = list(
            (
                await self._session.execute(
                    select(PaintProject)
                    .where(PaintProject.owner_principal_id == owner_principal_id)
                    .order_by(PaintProject.updated_at.desc(), PaintProject.id.desc())
                    .limit(limit)
                    .offset(offset)
                )
            )
            .scalars()
            .all()
        )
        return projects, total

    async def get_owned_project(
        self,
        *,
        project_id: uuid.UUID,
        owner_principal_id: str,
    ) -> PaintProject | None:
        """Read by ID and owner in one non-disclosing query."""
        return (
            await self._session.execute(
                select(PaintProject).where(
                    PaintProject.id == project_id,
                    PaintProject.owner_principal_id == owner_principal_id,
                )
            )
        ).scalar_one_or_none()
