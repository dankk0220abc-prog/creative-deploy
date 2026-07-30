"""Transactional SQLAlchemy access for immutable RegionSets."""

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
    Region,
    RegionSet,
    RegionSetReview,
    RegionVertex,
)
from creativedeploy_api.db.models.constants import (
    IDEMPOTENCY_STATUS_COMPLETED,
    IDEMPOTENCY_STATUS_IN_PROGRESS,
)
from creativedeploy_api.repositories.paint_projects import IdempotencyClaim


class SqlAlchemyRegionSetRepository:
    """RegionSet-specific read and append operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def configure_transaction_timeouts(
        self,
        *,
        lock_timeout_ms: int,
        statement_timeout_ms: int,
    ) -> None:
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
        statement = select(PaintProject).where(
            PaintProject.id == project_id,
            PaintProject.owner_principal_id == owner_principal_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def list_current_assets(
        self,
        *,
        project_id: uuid.UUID,
        owner_principal_id: str,
        for_update: bool = False,
    ) -> list[ImageAsset]:
        statement = (
            select(ImageAsset)
            .where(
                ImageAsset.paint_project_id == project_id,
                ImageAsset.owner_principal_id == owner_principal_id,
                ImageAsset.is_current.is_(True),
            )
            .order_by(ImageAsset.role)
        )
        if for_update:
            statement = statement.with_for_update()
        return list((await self._session.execute(statement)).scalars().all())

    async def list_readiness_reviews(
        self,
        *,
        project_id: uuid.UUID,
        owner_principal_id: str,
    ) -> list[ImageSetReadinessReview]:
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

    async def list_region_sets(
        self,
        *,
        project_id: uuid.UUID,
        owner_principal_id: str,
    ) -> list[RegionSet]:
        return list(
            (
                await self._session.execute(
                    select(RegionSet)
                    .where(
                        RegionSet.paint_project_id == project_id,
                        RegionSet.owner_principal_id == owner_principal_id,
                    )
                    .order_by(RegionSet.version.desc(), RegionSet.id.desc())
                )
            )
            .scalars()
            .all()
        )

    async def get_owned_region_set(
        self,
        *,
        project_id: uuid.UUID,
        region_set_id: uuid.UUID,
        owner_principal_id: str,
    ) -> RegionSet | None:
        return (
            await self._session.execute(
                select(RegionSet).where(
                    RegionSet.id == region_set_id,
                    RegionSet.paint_project_id == project_id,
                    RegionSet.owner_principal_id == owner_principal_id,
                )
            )
        ).scalar_one_or_none()

    async def list_regions(self, *, region_set_id: uuid.UUID) -> list[Region]:
        return list(
            (
                await self._session.execute(
                    select(Region)
                    .where(Region.region_set_id == region_set_id)
                    .order_by(Region.z_index, Region.stable_region_key)
                )
            )
            .scalars()
            .all()
        )

    async def list_vertices(self, *, region_set_id: uuid.UUID) -> list[RegionVertex]:
        return list(
            (
                await self._session.execute(
                    select(RegionVertex)
                    .where(RegionVertex.region_set_id == region_set_id)
                    .order_by(RegionVertex.region_id, RegionVertex.sequence)
                )
            )
            .scalars()
            .all()
        )

    async def list_reviews(
        self,
        *,
        project_id: uuid.UUID,
        owner_principal_id: str,
    ) -> list[RegionSetReview]:
        return list(
            (
                await self._session.execute(
                    select(RegionSetReview)
                    .where(
                        RegionSetReview.paint_project_id == project_id,
                        RegionSetReview.owner_principal_id == owner_principal_id,
                    )
                    .order_by(RegionSetReview.version.desc(), RegionSetReview.id.desc())
                )
            )
            .scalars()
            .all()
        )

    async def next_region_set_version(self, *, project_id: uuid.UUID) -> int:
        latest = (
            await self._session.execute(
                select(func.max(RegionSet.version)).where(RegionSet.paint_project_id == project_id)
            )
        ).scalar_one()
        return 1 if latest is None else int(latest) + 1

    async def next_review_version(self, *, project_id: uuid.UUID) -> int:
        latest = (
            await self._session.execute(
                select(func.max(RegionSetReview.version)).where(
                    RegionSetReview.paint_project_id == project_id
                )
            )
        ).scalar_one()
        return 1 if latest is None else int(latest) + 1

    async def add_snapshot(
        self,
        *,
        region_set: RegionSet,
        regions: list[Region],
        vertices: list[RegionVertex],
    ) -> None:
        """Flush each immutable ownership level before its restricted children."""
        self._session.add(region_set)
        await self._session.flush()
        self._session.add_all(regions)
        await self._session.flush()
        self._session.add_all(vertices)
        await self._session.flush()

    def add_review(self, review: RegionSetReview) -> None:
        self._session.add(review)

    async def flush(self) -> None:
        await self._session.flush()

    async def claim_command(
        self,
        *,
        record_id: uuid.UUID,
        scope_key: str,
        principal_id: str,
        command_type: str,
        idempotency_key: uuid.UUID,
        payload_hash: str,
        created_at: datetime,
        expires_at: datetime,
    ) -> IdempotencyClaim:
        statement = (
            insert(CommandIdempotencyRecord)
            .values(
                id=record_id,
                scope_key=scope_key,
                principal_id=principal_id,
                command_type=command_type,
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
                "RegionSet idempotency arbitration completed without a committed winner."
            )
        return IdempotencyClaim(acquired_record_id=None, existing_record=existing)

    async def complete_command(
        self,
        *,
        record_id: uuid.UUID,
        resource_type: str,
        resource_id: uuid.UUID,
        response_snapshot: dict[str, object],
    ) -> None:
        completed_id = (
            await self._session.execute(
                update(CommandIdempotencyRecord)
                .where(
                    CommandIdempotencyRecord.id == record_id,
                    CommandIdempotencyRecord.execution_status == IDEMPOTENCY_STATUS_IN_PROGRESS,
                )
                .values(
                    execution_status=IDEMPOTENCY_STATUS_COMPLETED,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    http_status=201,
                    response_snapshot=response_snapshot,
                )
                .returning(CommandIdempotencyRecord.id)
            )
        ).scalar_one_or_none()
        if completed_id is None:
            raise RuntimeError("The acquired RegionSet idempotency record could not be completed.")
