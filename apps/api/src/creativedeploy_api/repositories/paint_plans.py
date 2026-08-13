"""Transactional access for immutable Paint Plan revisions and review events."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from creativedeploy_api.db.models import (
    AICostLedger,
    AIUsageLedger,
    CommandIdempotencyRecord,
    CredentialProjectGrant,
    CredentialRecord,
    InvocationAttempt,
    InvocationRequest,
    ModelDefinition,
    PaintPlan,
    PaintPlanRegionInstruction,
    PaintPlanReviewEvent,
    PromptTemplateDefinition,
    ProviderDefinition,
    ProviderPricingSnapshot,
)
from creativedeploy_api.db.models.constants import (
    IDEMPOTENCY_STATUS_COMPLETED,
    IDEMPOTENCY_STATUS_IN_PROGRESS,
)
from creativedeploy_api.repositories.paint_projects import IdempotencyClaim


class SqlAlchemyPaintPlanRepository:
    """Paint Plan-specific append, exact-revision, and replay operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_plans(
        self,
        *,
        project_id: uuid.UUID,
        owner_principal_id: str,
        for_update: bool = False,
    ) -> list[PaintPlan]:
        statement = (
            select(PaintPlan)
            .where(
                PaintPlan.paint_project_id == project_id,
                PaintPlan.owner_principal_id == owner_principal_id,
            )
            .order_by(PaintPlan.version.desc(), PaintPlan.id.desc())
        )
        if for_update:
            statement = statement.with_for_update()
        return list((await self._session.execute(statement)).scalars().all())

    async def get_plan(
        self,
        *,
        project_id: uuid.UUID,
        owner_principal_id: str,
        plan_id: uuid.UUID,
        for_update: bool = False,
    ) -> PaintPlan | None:
        statement = select(PaintPlan).where(
            PaintPlan.id == plan_id,
            PaintPlan.paint_project_id == project_id,
            PaintPlan.owner_principal_id == owner_principal_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def get_plan_by_invocation(
        self,
        *,
        source_invocation_id: uuid.UUID,
    ) -> PaintPlan | None:
        return (
            await self._session.execute(
                select(PaintPlan).where(
                    PaintPlan.source_invocation_id == source_invocation_id,
                    PaintPlan.revision_kind.in_(("generated", "regenerated")),
                )
            )
        ).scalar_one_or_none()

    async def get_attempt_accounting(
        self,
        *,
        invocation_id: uuid.UUID,
        attempt_id: uuid.UUID,
    ) -> tuple[
        InvocationRequest | None,
        InvocationAttempt | None,
        AIUsageLedger | None,
        AICostLedger | None,
    ]:
        invocation = await self._session.get(InvocationRequest, invocation_id)
        attempt = (
            await self._session.execute(
                select(InvocationAttempt).where(
                    InvocationAttempt.id == attempt_id,
                    InvocationAttempt.invocation_id == invocation_id,
                )
            )
        ).scalar_one_or_none()
        usage = (
            await self._session.execute(
                select(AIUsageLedger)
                .where(
                    AIUsageLedger.attempt_id == attempt_id,
                    AIUsageLedger.invocation_id == invocation_id,
                )
                .order_by(AIUsageLedger.created_at.desc(), AIUsageLedger.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        cost = (
            await self._session.execute(
                select(AICostLedger)
                .where(
                    AICostLedger.attempt_id == attempt_id,
                    AICostLedger.invocation_id == invocation_id,
                )
                .order_by(AICostLedger.created_at.desc(), AICostLedger.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        return invocation, attempt, usage, cost

    async def list_instructions(self, *, plan_id: uuid.UUID) -> list[PaintPlanRegionInstruction]:
        return list(
            (
                await self._session.execute(
                    select(PaintPlanRegionInstruction)
                    .where(PaintPlanRegionInstruction.paint_plan_id == plan_id)
                    .order_by(
                        PaintPlanRegionInstruction.sequence,
                        PaintPlanRegionInstruction.id,
                    )
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
    ) -> list[PaintPlanReviewEvent]:
        return list(
            (
                await self._session.execute(
                    select(PaintPlanReviewEvent)
                    .where(
                        PaintPlanReviewEvent.paint_project_id == project_id,
                        PaintPlanReviewEvent.owner_principal_id == owner_principal_id,
                    )
                    .order_by(
                        PaintPlanReviewEvent.created_at.desc(),
                        PaintPlanReviewEvent.id.desc(),
                    )
                )
            )
            .scalars()
            .all()
        )

    async def next_project_version(self, *, project_id: uuid.UUID) -> int:
        latest = (
            await self._session.execute(
                select(func.max(PaintPlan.version)).where(PaintPlan.paint_project_id == project_id)
            )
        ).scalar_one()
        return 1 if latest is None else int(latest) + 1

    async def get_prompt(
        self,
        *,
        template_key: str,
        version: int,
    ) -> PromptTemplateDefinition | None:
        return (
            await self._session.execute(
                select(PromptTemplateDefinition).where(
                    PromptTemplateDefinition.template_key == template_key,
                    PromptTemplateDefinition.version == version,
                    PromptTemplateDefinition.status == "active",
                )
            )
        ).scalar_one_or_none()

    async def get_provider(self, provider_id: uuid.UUID) -> ProviderDefinition | None:
        return await self._session.get(ProviderDefinition, provider_id)

    async def get_model(self, model_id: uuid.UUID) -> ModelDefinition | None:
        return await self._session.get(ModelDefinition, model_id)

    async def get_pricing(
        self,
        *,
        model_definition_id: uuid.UUID,
    ) -> ProviderPricingSnapshot | None:
        return (
            await self._session.execute(
                select(ProviderPricingSnapshot)
                .where(ProviderPricingSnapshot.model_definition_id == model_definition_id)
                .order_by(
                    ProviderPricingSnapshot.effective_at.desc(),
                    ProviderPricingSnapshot.id.desc(),
                )
                .limit(1)
            )
        ).scalar_one_or_none()

    async def list_provider_models(self) -> list[tuple[ProviderDefinition, ModelDefinition]]:
        rows = (
            await self._session.execute(
                select(ProviderDefinition, ModelDefinition)
                .join(
                    ModelDefinition,
                    ModelDefinition.provider_definition_id == ProviderDefinition.id,
                )
                .where(ProviderDefinition.provider_key.in_(("fixture_local", "openai", "zhipu")))
                .order_by(ProviderDefinition.provider_key, ModelDefinition.model_id)
            )
        ).all()
        return [(row[0], row[1]) for row in rows]

    async def list_owned_credentials_with_grants(
        self,
        *,
        owner_user_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> list[tuple[CredentialRecord, CredentialProjectGrant | None]]:
        rows = (
            await self._session.execute(
                select(CredentialRecord, CredentialProjectGrant)
                .outerjoin(
                    CredentialProjectGrant,
                    (CredentialProjectGrant.credential_id == CredentialRecord.id)
                    & (CredentialProjectGrant.project_id == project_id)
                    & (CredentialProjectGrant.revoked_at.is_(None)),
                )
                .where(
                    CredentialRecord.owner_user_id == owner_user_id,
                    CredentialRecord.status == "active",
                )
                .order_by(CredentialRecord.created_at, CredentialRecord.id)
            )
        ).all()
        return [(row[0], row[1]) for row in rows]

    async def add_plan(
        self,
        *,
        plan: PaintPlan,
        instructions: list[PaintPlanRegionInstruction],
    ) -> None:
        self._session.add(plan)
        await self._session.flush()
        self._session.add_all(instructions)
        await self._session.flush()

    def add_review(self, review: PaintPlanReviewEvent) -> None:
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
            raise RuntimeError("Paint Plan idempotency arbitration has no committed winner.")
        return IdempotencyClaim(acquired_record_id=None, existing_record=existing)

    async def get_command(
        self,
        *,
        scope_key: str,
        idempotency_key: uuid.UUID,
    ) -> CommandIdempotencyRecord | None:
        return (
            await self._session.execute(
                select(CommandIdempotencyRecord).where(
                    CommandIdempotencyRecord.scope_key == scope_key,
                    CommandIdempotencyRecord.idempotency_key == idempotency_key,
                )
            )
        ).scalar_one_or_none()

    async def complete_command(
        self,
        *,
        record_id: uuid.UUID,
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
                    resource_type="paint_plan",
                    resource_id=resource_id,
                    http_status=201,
                    response_snapshot=response_snapshot,
                )
                .returning(CommandIdempotencyRecord.id)
            )
        ).scalar_one_or_none()
        if completed_id is None:
            raise RuntimeError("The acquired Paint Plan command could not be completed.")
