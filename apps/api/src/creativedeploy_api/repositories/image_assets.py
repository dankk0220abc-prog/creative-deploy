"""SQLAlchemy persistence access for immutable owner-scoped ImageAssets."""

import uuid
from datetime import datetime

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from creativedeploy_api.db.models import (
    CommandIdempotencyRecord,
    ImageAsset,
    ImageSetReadinessReview,
    PaintProject,
    StateTransitionEvent,
)
from creativedeploy_api.db.models.constants import (
    IDEMPOTENCY_STATUS_COMPLETED,
    IDEMPOTENCY_STATUS_IN_PROGRESS,
)
from creativedeploy_api.repositories.paint_projects import IdempotencyClaim


class SqlAlchemyImageAssetRepository:
    """ImageAsset-specific transactional operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def configure_transaction_timeouts(
        self,
        *,
        lock_timeout_ms: int,
        statement_timeout_ms: int,
    ) -> None:
        """Apply bounded PostgreSQL waits only to the active transaction."""
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

    async def get_owned_project(
        self,
        *,
        project_id: uuid.UUID,
        owner_principal_id: str,
        for_update: bool = False,
    ) -> PaintProject | None:
        """Read and optionally lock a project inside its owner predicate."""
        statement = select(PaintProject).where(
            PaintProject.id == project_id,
            PaintProject.owner_principal_id == owner_principal_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def claim_upload_command(
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
        """Acquire one upload command or read the committed winner."""
        statement = (
            insert(CommandIdempotencyRecord)
            .values(
                id=record_id,
                scope_key=scope_key,
                principal_id=principal_id,
                command_type="upload_image",
                idempotency_key=idempotency_key,
                payload_hash=payload_hash,
                execution_status=IDEMPOTENCY_STATUS_IN_PROGRESS,
                created_at=created_at,
                expires_at=expires_at,
            )
            .on_conflict_do_nothing(index_elements=["scope_key", "idempotency_key"])
            .returning(CommandIdempotencyRecord.id)
        )
        claimed_id = (await self._session.execute(statement)).scalar_one_or_none()
        if claimed_id is not None:
            return IdempotencyClaim(acquired_record_id=claimed_id, existing_record=None)
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
        return IdempotencyClaim(acquired_record_id=None, existing_record=existing)

    async def get_upload_command(
        self,
        *,
        scope_key: str,
        idempotency_key: uuid.UUID,
    ) -> CommandIdempotencyRecord | None:
        """Read a committed upload command before staging a possible replay."""
        return (
            await self._session.execute(
                select(CommandIdempotencyRecord).where(
                    CommandIdempotencyRecord.scope_key == scope_key,
                    CommandIdempotencyRecord.idempotency_key == idempotency_key,
                )
            )
        ).scalar_one_or_none()

    async def get_current_for_update(
        self,
        *,
        project_id: uuid.UUID,
        role: str,
    ) -> ImageAsset | None:
        """Lock the role's current asset after the project lock is held."""
        return (
            await self._session.execute(
                select(ImageAsset)
                .where(
                    ImageAsset.paint_project_id == project_id,
                    ImageAsset.role == role,
                    ImageAsset.is_current.is_(True),
                )
                .with_for_update()
            )
        ).scalar_one_or_none()

    async def list_current_for_update(
        self,
        *,
        project_id: uuid.UUID,
        owner_principal_id: str,
    ) -> list[ImageAsset]:
        """Read and lock every current role after the project row lock is held."""
        return list(
            (
                await self._session.execute(
                    select(ImageAsset)
                    .where(
                        ImageAsset.paint_project_id == project_id,
                        ImageAsset.owner_principal_id == owner_principal_id,
                        ImageAsset.is_current.is_(True),
                    )
                    .order_by(ImageAsset.role)
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )

    async def supersede(self, asset_id: uuid.UUID) -> None:
        """Mark one locked current asset as retained immutable history."""
        updated_id = (
            await self._session.execute(
                update(ImageAsset)
                .where(ImageAsset.id == asset_id, ImageAsset.is_current.is_(True))
                .values(is_current=False, lifecycle_status="superseded")
                .returning(ImageAsset.id)
            )
        ).scalar_one_or_none()
        if updated_id is None:
            raise RuntimeError("The current image asset changed during replacement.")

    def add_asset(self, asset: ImageAsset) -> None:
        """Stage one immutable asset."""
        self._session.add(asset)

    def add_event(self, event: StateTransitionEvent) -> None:
        """Stage its authoritative workflow event."""
        self._session.add(event)

    async def flush(self) -> None:
        """Flush pending asset, project, and event writes."""
        await self._session.flush()

    async def complete_upload_command(
        self,
        *,
        record_id: uuid.UUID,
        image_asset_id: uuid.UUID,
        response_snapshot: dict[str, object],
    ) -> None:
        """Persist the exact successful upload response for confirmation-loss replay."""
        completed_id = (
            await self._session.execute(
                update(CommandIdempotencyRecord)
                .where(
                    CommandIdempotencyRecord.id == record_id,
                    CommandIdempotencyRecord.execution_status == IDEMPOTENCY_STATUS_IN_PROGRESS,
                )
                .values(
                    execution_status=IDEMPOTENCY_STATUS_COMPLETED,
                    resource_type="image_asset",
                    resource_id=image_asset_id,
                    http_status=201,
                    response_snapshot=response_snapshot,
                )
                .returning(CommandIdempotencyRecord.id)
            )
        ).scalar_one_or_none()
        if completed_id is None:
            raise RuntimeError("The acquired upload idempotency record could not be completed.")

    async def list_owned_assets(
        self,
        *,
        project_id: uuid.UUID,
        owner_principal_id: str,
    ) -> list[ImageAsset]:
        """Return current plus retained history within one owner/project predicate."""
        return list(
            (
                await self._session.execute(
                    select(ImageAsset)
                    .where(
                        ImageAsset.paint_project_id == project_id,
                        ImageAsset.owner_principal_id == owner_principal_id,
                    )
                    .order_by(ImageAsset.role, ImageAsset.version.desc())
                )
            )
            .scalars()
            .all()
        )

    async def claim_readiness_command(
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
        """Acquire one Project-scoped readiness command or read its winner."""
        statement = (
            insert(CommandIdempotencyRecord)
            .values(
                id=record_id,
                scope_key=scope_key,
                principal_id=principal_id,
                command_type="review_image_set_readiness",
                idempotency_key=idempotency_key,
                payload_hash=payload_hash,
                execution_status=IDEMPOTENCY_STATUS_IN_PROGRESS,
                created_at=created_at,
                expires_at=expires_at,
            )
            .on_conflict_do_nothing(index_elements=["scope_key", "idempotency_key"])
            .returning(CommandIdempotencyRecord.id)
        )
        claimed_id = (await self._session.execute(statement)).scalar_one_or_none()
        if claimed_id is not None:
            return IdempotencyClaim(acquired_record_id=claimed_id, existing_record=None)
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
                "Readiness arbitration completed without a claim or committed record."
            )
        return IdempotencyClaim(acquired_record_id=None, existing_record=existing)

    async def next_readiness_version(self, *, project_id: uuid.UUID) -> int:
        """Compute the next version while the caller holds the project row lock."""
        latest = (
            await self._session.execute(
                select(func.max(ImageSetReadinessReview.version)).where(
                    ImageSetReadinessReview.paint_project_id == project_id
                )
            )
        ).scalar_one()
        return 1 if latest is None else int(latest) + 1

    def add_readiness_review(self, review: ImageSetReadinessReview) -> None:
        """Stage one append-only human review."""
        self._session.add(review)

    async def complete_readiness_command(
        self,
        *,
        record_id: uuid.UUID,
        review_id: uuid.UUID,
        response_snapshot: dict[str, object],
    ) -> None:
        """Persist the strict response for confirmation-loss replay."""
        completed_id = (
            await self._session.execute(
                update(CommandIdempotencyRecord)
                .where(
                    CommandIdempotencyRecord.id == record_id,
                    CommandIdempotencyRecord.execution_status == IDEMPOTENCY_STATUS_IN_PROGRESS,
                )
                .values(
                    execution_status=IDEMPOTENCY_STATUS_COMPLETED,
                    resource_type="image_set_readiness_review",
                    resource_id=review_id,
                    http_status=201,
                    response_snapshot=response_snapshot,
                )
                .returning(CommandIdempotencyRecord.id)
            )
        ).scalar_one_or_none()
        if completed_id is None:
            raise RuntimeError("The acquired readiness command could not be completed.")

    async def list_readiness_reviews(
        self,
        *,
        project_id: uuid.UUID,
        owner_principal_id: str,
    ) -> list[ImageSetReadinessReview]:
        """Return immutable review history newest-first within the owner scope."""
        return list(
            (
                await self._session.execute(
                    select(ImageSetReadinessReview)
                    .where(
                        ImageSetReadinessReview.paint_project_id == project_id,
                        ImageSetReadinessReview.owner_principal_id == owner_principal_id,
                    )
                    .order_by(
                        ImageSetReadinessReview.version.desc(),
                        ImageSetReadinessReview.id.desc(),
                    )
                )
            )
            .scalars()
            .all()
        )

    async def get_owned_asset(
        self,
        *,
        project_id: uuid.UUID,
        image_asset_id: uuid.UUID,
        owner_principal_id: str,
    ) -> ImageAsset | None:
        """Read by project, asset, and owner in one non-disclosing query."""
        return (
            await self._session.execute(
                select(ImageAsset).where(
                    ImageAsset.id == image_asset_id,
                    ImageAsset.paint_project_id == project_id,
                    ImageAsset.owner_principal_id == owner_principal_id,
                )
            )
        ).scalar_one_or_none()

    async def referenced_storage_keys(self) -> set[str]:
        """Return database-authoritative keys for explicit orphan inspection."""
        return set((await self._session.execute(select(ImageAsset.storage_key))).scalars().all())
