"""Database-authoritative Phase 3A fixture foundation queries and locks."""

import uuid
from datetime import datetime

from sqlalchemy import Select, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from creativedeploy_api.db.models import (
    AIAuditEvent,
    AICostLedger,
    AIInvocationEvent,
    AIUsageLedger,
    BudgetReservation,
    CapabilityDefinition,
    CredentialProjectGrant,
    CredentialRecord,
    InvocationAttempt,
    InvocationRequest,
    ModelCapability,
    ModelDefinition,
    PaintProject,
    ProjectBudgetCounter,
    ProjectBudgetPolicy,
    ProjectModelPolicy,
    ProjectModelPolicyCapability,
    ProjectModelPolicyCredential,
    ProjectModelPolicyModel,
    ProjectModelPolicyProvider,
    ProviderCapability,
    ProviderDefinition,
    UserAccount,
    UserBudgetCounter,
    UserBudgetPolicy,
    UserProviderPreference,
)


class SqlAlchemyAIFoundationRepository:
    """Keep owner/project predicates and global-order row locks explicit."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def lock_active_user(self, user_id: uuid.UUID) -> UserAccount | None:
        return (
            await self.session.execute(
                select(UserAccount)
                .where(UserAccount.id == user_id, UserAccount.is_active.is_(True))
                .with_for_update()
            )
        ).scalar_one_or_none()

    async def lock_user(self, user_id: uuid.UUID) -> UserAccount | None:
        return (
            await self.session.execute(
                select(UserAccount).where(UserAccount.id == user_id).with_for_update()
            )
        ).scalar_one_or_none()

    async def lock_project(self, project_id: uuid.UUID) -> PaintProject | None:
        return (
            await self.session.execute(
                select(PaintProject).where(PaintProject.id == project_id).with_for_update()
            )
        ).scalar_one_or_none()

    async def list_providers(
        self,
    ) -> list[tuple[ProviderDefinition, CapabilityDefinition, ProviderCapability]]:
        return list(
            (
                await self.session.execute(
                    select(ProviderDefinition, CapabilityDefinition, ProviderCapability)
                    .join(
                        ProviderCapability,
                        ProviderCapability.provider_definition_id == ProviderDefinition.id,
                    )
                    .join(
                        CapabilityDefinition,
                        CapabilityDefinition.id == ProviderCapability.capability_definition_id,
                    )
                    .order_by(ProviderDefinition.provider_key, CapabilityDefinition.capability_key)
                )
            )
            .tuples()
            .all()
        )

    async def list_capabilities(self) -> list[CapabilityDefinition]:
        return list(
            (
                await self.session.execute(
                    select(CapabilityDefinition).order_by(CapabilityDefinition.capability_key)
                )
            )
            .scalars()
            .all()
        )

    async def list_models(
        self, provider_key: str
    ) -> list[tuple[ModelDefinition, CapabilityDefinition, ModelCapability]]:
        return list(
            (
                await self.session.execute(
                    select(ModelDefinition, CapabilityDefinition, ModelCapability)
                    .join(
                        ModelCapability,
                        ModelCapability.model_definition_id == ModelDefinition.id,
                    )
                    .join(
                        CapabilityDefinition,
                        CapabilityDefinition.id == ModelCapability.capability_definition_id,
                    )
                    .where(ModelDefinition.provider_key == provider_key)
                    .order_by(ModelDefinition.model_id, CapabilityDefinition.capability_key)
                )
            )
            .tuples()
            .all()
        )

    async def get_provider(self, provider_key: str) -> ProviderDefinition | None:
        return (
            await self.session.execute(
                select(ProviderDefinition).where(ProviderDefinition.provider_key == provider_key)
            )
        ).scalar_one_or_none()

    async def get_provider_by_id(
        self, provider_definition_id: uuid.UUID
    ) -> ProviderDefinition | None:
        return await self.session.get(ProviderDefinition, provider_definition_id)

    async def get_model(self, model_id: uuid.UUID) -> ModelDefinition | None:
        return await self.session.get(ModelDefinition, model_id)

    async def model_capability_keys(self, model_id: uuid.UUID) -> list[str]:
        return list(
            (
                await self.session.execute(
                    select(CapabilityDefinition.capability_key)
                    .join(
                        ModelCapability,
                        ModelCapability.capability_definition_id == CapabilityDefinition.id,
                    )
                    .where(
                        ModelCapability.model_definition_id == model_id,
                        ModelCapability.status == "active",
                        CapabilityDefinition.status == "active",
                        CapabilityDefinition.enabled.is_(True),
                    )
                    .order_by(CapabilityDefinition.capability_key)
                )
            )
            .scalars()
            .all()
        )

    async def list_credentials(self, owner_user_id: uuid.UUID) -> list[CredentialRecord]:
        return list(
            (
                await self.session.execute(
                    select(CredentialRecord)
                    .where(CredentialRecord.owner_user_id == owner_user_id)
                    .order_by(CredentialRecord.created_at.desc(), CredentialRecord.id.desc())
                )
            )
            .scalars()
            .all()
        )

    async def get_owned_credential(
        self,
        *,
        credential_id: uuid.UUID,
        owner_user_id: uuid.UUID,
        for_update: bool = False,
    ) -> CredentialRecord | None:
        statement: Select[tuple[CredentialRecord]] = select(CredentialRecord).where(
            CredentialRecord.id == credential_id,
            CredentialRecord.owner_user_id == owner_user_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def get_credential_by_id(self, credential_id: uuid.UUID) -> CredentialRecord | None:
        return await self.session.get(CredentialRecord, credential_id)

    async def lock_owned_credentials(
        self,
        *,
        credential_ids: list[uuid.UUID],
        owner_user_id: uuid.UUID,
    ) -> list[CredentialRecord]:
        ordered_ids = sorted(set(credential_ids))
        if not ordered_ids:
            return []
        return list(
            (
                await self.session.execute(
                    select(CredentialRecord)
                    .where(
                        CredentialRecord.id.in_(ordered_ids),
                        CredentialRecord.owner_user_id == owner_user_id,
                    )
                    .order_by(CredentialRecord.id)
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )

    async def lock_active_grants_for_credentials(
        self,
        *,
        credential_ids: list[uuid.UUID],
        project_id: uuid.UUID,
    ) -> list[CredentialProjectGrant]:
        ordered_ids = sorted(set(credential_ids))
        if not ordered_ids:
            return []
        return list(
            (
                await self.session.execute(
                    select(CredentialProjectGrant)
                    .where(
                        CredentialProjectGrant.credential_id.in_(ordered_ids),
                        CredentialProjectGrant.project_id == project_id,
                        CredentialProjectGrant.revoked_at.is_(None),
                    )
                    .order_by(
                        CredentialProjectGrant.credential_id,
                        CredentialProjectGrant.project_id,
                        CredentialProjectGrant.id,
                    )
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )

    async def lock_credential_grants(
        self, credential_id: uuid.UUID
    ) -> list[CredentialProjectGrant]:
        return list(
            (
                await self.session.execute(
                    select(CredentialProjectGrant)
                    .where(CredentialProjectGrant.credential_id == credential_id)
                    .order_by(CredentialProjectGrant.project_id, CredentialProjectGrant.id)
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )

    async def get_active_grant(
        self,
        *,
        credential_id: uuid.UUID,
        project_id: uuid.UUID,
        for_update: bool = False,
    ) -> CredentialProjectGrant | None:
        statement: Select[tuple[CredentialProjectGrant]] = select(CredentialProjectGrant).where(
            CredentialProjectGrant.credential_id == credential_id,
            CredentialProjectGrant.project_id == project_id,
            CredentialProjectGrant.revoked_at.is_(None),
        )
        if for_update:
            statement = statement.with_for_update()
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def get_preference(
        self, user_id: uuid.UUID, *, for_update: bool = False
    ) -> UserProviderPreference | None:
        statement: Select[tuple[UserProviderPreference]] = select(UserProviderPreference).where(
            UserProviderPreference.user_id == user_id
        )
        if for_update:
            statement = statement.with_for_update()
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def get_project_policy(
        self, project_id: uuid.UUID, *, for_update: bool = False
    ) -> ProjectModelPolicy | None:
        statement: Select[tuple[ProjectModelPolicy]] = select(ProjectModelPolicy).where(
            ProjectModelPolicy.project_id == project_id
        )
        if for_update:
            statement = statement.with_for_update()
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def policy_allowlists(
        self, policy_id: uuid.UUID
    ) -> tuple[list[uuid.UUID], list[uuid.UUID], list[uuid.UUID], list[uuid.UUID]]:
        return (
            list(
                (
                    await self.session.execute(
                        select(ProjectModelPolicyProvider.provider_definition_id).where(
                            ProjectModelPolicyProvider.project_model_policy_id == policy_id
                        )
                    )
                )
                .scalars()
                .all()
            ),
            list(
                (
                    await self.session.execute(
                        select(ProjectModelPolicyModel.model_definition_id).where(
                            ProjectModelPolicyModel.project_model_policy_id == policy_id
                        )
                    )
                )
                .scalars()
                .all()
            ),
            list(
                (
                    await self.session.execute(
                        select(ProjectModelPolicyCapability.capability_definition_id).where(
                            ProjectModelPolicyCapability.project_model_policy_id == policy_id
                        )
                    )
                )
                .scalars()
                .all()
            ),
            list(
                (
                    await self.session.execute(
                        select(ProjectModelPolicyCredential.credential_record_id).where(
                            ProjectModelPolicyCredential.project_model_policy_id == policy_id
                        )
                    )
                )
                .scalars()
                .all()
            ),
        )

    async def capability_ids_for_keys(self, keys: list[str]) -> list[uuid.UUID]:
        return list(
            (
                await self.session.execute(
                    select(CapabilityDefinition.id).where(
                        CapabilityDefinition.capability_key.in_(keys),
                        CapabilityDefinition.enabled.is_(True),
                        CapabilityDefinition.status == "active",
                    )
                )
            )
            .scalars()
            .all()
        )

    async def existing_provider_ids(self, values: list[uuid.UUID]) -> set[uuid.UUID]:
        return set(
            (
                await self.session.execute(
                    select(ProviderDefinition.id).where(ProviderDefinition.id.in_(values))
                )
            )
            .scalars()
            .all()
        )

    async def existing_model_ids(self, values: list[uuid.UUID]) -> set[uuid.UUID]:
        return set(
            (
                await self.session.execute(
                    select(ModelDefinition.id).where(ModelDefinition.id.in_(values))
                )
            )
            .scalars()
            .all()
        )

    async def existing_capability_ids(self, values: list[uuid.UUID]) -> set[uuid.UUID]:
        return set(
            (
                await self.session.execute(
                    select(CapabilityDefinition.id).where(CapabilityDefinition.id.in_(values))
                )
            )
            .scalars()
            .all()
        )

    async def owned_credential_ids(
        self, owner_user_id: uuid.UUID, values: list[uuid.UUID]
    ) -> set[uuid.UUID]:
        return set(
            (
                await self.session.execute(
                    select(CredentialRecord.id).where(
                        CredentialRecord.owner_user_id == owner_user_id,
                        CredentialRecord.id.in_(values),
                        CredentialRecord.status == "active",
                    )
                )
            )
            .scalars()
            .all()
        )

    async def replace_policy_allowlists(
        self,
        *,
        policy_id: uuid.UUID,
        providers: list[uuid.UUID],
        models: list[uuid.UUID],
        capabilities: list[uuid.UUID],
        credentials: list[uuid.UUID],
        created_at: datetime,
    ) -> None:
        for model in (
            ProjectModelPolicyProvider,
            ProjectModelPolicyModel,
            ProjectModelPolicyCapability,
            ProjectModelPolicyCredential,
        ):
            await self.session.execute(
                delete(model).where(model.project_model_policy_id == policy_id)
            )
        self.session.add_all(
            [
                ProjectModelPolicyProvider(
                    id=uuid.uuid4(),
                    project_model_policy_id=policy_id,
                    provider_definition_id=value,
                    created_at=created_at,
                )
                for value in sorted(set(providers))
            ]
            + [
                ProjectModelPolicyModel(
                    id=uuid.uuid4(),
                    project_model_policy_id=policy_id,
                    model_definition_id=value,
                    created_at=created_at,
                )
                for value in sorted(set(models))
            ]
            + [
                ProjectModelPolicyCapability(
                    id=uuid.uuid4(),
                    project_model_policy_id=policy_id,
                    capability_definition_id=value,
                    created_at=created_at,
                )
                for value in sorted(set(capabilities))
            ]
            + [
                ProjectModelPolicyCredential(
                    id=uuid.uuid4(),
                    project_model_policy_id=policy_id,
                    credential_record_id=value,
                    created_at=created_at,
                )
                for value in sorted(set(credentials))
            ]
        )

    async def get_user_budget_policy(
        self, user_id: uuid.UUID, *, currency: str, for_update: bool = False
    ) -> UserBudgetPolicy | None:
        statement: Select[tuple[UserBudgetPolicy]] = select(UserBudgetPolicy).where(
            UserBudgetPolicy.user_id == user_id,
            UserBudgetPolicy.product_space == "paintpilot",
            UserBudgetPolicy.currency == currency,
        )
        if for_update:
            statement = statement.with_for_update()
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def get_project_budget_policy(
        self, project_id: uuid.UUID, *, currency: str, for_update: bool = False
    ) -> ProjectBudgetPolicy | None:
        statement: Select[tuple[ProjectBudgetPolicy]] = select(ProjectBudgetPolicy).where(
            ProjectBudgetPolicy.project_id == project_id,
            ProjectBudgetPolicy.product_space == "paintpilot",
            ProjectBudgetPolicy.currency == currency,
        )
        if for_update:
            statement = statement.with_for_update()
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def get_user_counter(
        self,
        user_id: uuid.UUID,
        now: datetime,
        *,
        currency: str,
        for_update: bool = False,
    ) -> UserBudgetCounter | None:
        statement: Select[tuple[UserBudgetCounter]] = (
            select(UserBudgetCounter)
            .where(
                UserBudgetCounter.user_id == user_id,
                UserBudgetCounter.product_space == "paintpilot",
                UserBudgetCounter.currency == currency,
                UserBudgetCounter.window_start <= now,
                UserBudgetCounter.window_end > now,
            )
            .order_by(UserBudgetCounter.window_start.desc())
            .limit(1)
        )
        if for_update:
            statement = statement.with_for_update()
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def get_project_counter(
        self,
        project_id: uuid.UUID,
        now: datetime,
        *,
        currency: str,
        for_update: bool = False,
    ) -> ProjectBudgetCounter | None:
        statement: Select[tuple[ProjectBudgetCounter]] = (
            select(ProjectBudgetCounter)
            .where(
                ProjectBudgetCounter.project_id == project_id,
                ProjectBudgetCounter.product_space == "paintpilot",
                ProjectBudgetCounter.currency == currency,
                ProjectBudgetCounter.window_start <= now,
                ProjectBudgetCounter.window_end > now,
            )
            .order_by(ProjectBudgetCounter.window_start.desc())
            .limit(1)
        )
        if for_update:
            statement = statement.with_for_update()
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def get_invocation(
        self, invocation_id: uuid.UUID, *, for_update: bool = False
    ) -> InvocationRequest | None:
        statement: Select[tuple[InvocationRequest]] = select(InvocationRequest).where(
            InvocationRequest.id == invocation_id
        )
        if for_update:
            statement = statement.with_for_update()
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def list_attempts(self, invocation_id: uuid.UUID) -> list[InvocationAttempt]:
        return list(
            (
                await self.session.execute(
                    select(InvocationAttempt)
                    .where(InvocationAttempt.invocation_id == invocation_id)
                    .order_by(InvocationAttempt.attempt_number)
                )
            )
            .scalars()
            .all()
        )

    async def get_attempt(
        self, attempt_id: uuid.UUID, *, for_update: bool = False
    ) -> InvocationAttempt | None:
        statement: Select[tuple[InvocationAttempt]] = select(InvocationAttempt).where(
            InvocationAttempt.id == attempt_id
        )
        if for_update:
            statement = statement.with_for_update()
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def get_user_counter_by_id(
        self, counter_id: uuid.UUID, *, for_update: bool = False
    ) -> UserBudgetCounter | None:
        statement: Select[tuple[UserBudgetCounter]] = select(UserBudgetCounter).where(
            UserBudgetCounter.id == counter_id
        )
        if for_update:
            statement = statement.with_for_update()
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def get_project_counter_by_id(
        self, counter_id: uuid.UUID, *, for_update: bool = False
    ) -> ProjectBudgetCounter | None:
        statement: Select[tuple[ProjectBudgetCounter]] = select(ProjectBudgetCounter).where(
            ProjectBudgetCounter.id == counter_id
        )
        if for_update:
            statement = statement.with_for_update()
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def get_reservation(
        self, attempt_id: uuid.UUID, *, for_update: bool = False
    ) -> BudgetReservation | None:
        statement: Select[tuple[BudgetReservation]] = select(BudgetReservation).where(
            BudgetReservation.attempt_id == attempt_id
        )
        if for_update:
            statement = statement.with_for_update()
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def attempt_has_dispatch_evidence(
        self, *, invocation_id: uuid.UUID, attempt_id: uuid.UUID
    ) -> bool:
        usage = (
            await self.session.execute(
                select(AIUsageLedger.id)
                .where(
                    AIUsageLedger.invocation_id == invocation_id,
                    AIUsageLedger.attempt_id == attempt_id,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if usage is not None:
            return True
        cost = (
            await self.session.execute(
                select(AICostLedger.id)
                .where(
                    AICostLedger.invocation_id == invocation_id,
                    AICostLedger.attempt_id == attempt_id,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if cost is not None:
            return True
        event = (
            await self.session.execute(
                select(AIInvocationEvent.id)
                .where(
                    AIInvocationEvent.invocation_id == invocation_id,
                    AIInvocationEvent.attempt_id == attempt_id,
                    AIInvocationEvent.to_status.in_(
                        ("running", "succeeded", "failed", "cancelled", "outcome_unknown")
                    ),
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        return event is not None

    async def active_grant_credential_ids(self, project_id: uuid.UUID) -> list[uuid.UUID]:
        return list(
            (
                await self.session.execute(
                    select(CredentialProjectGrant.credential_id)
                    .where(
                        CredentialProjectGrant.project_id == project_id,
                        CredentialProjectGrant.revoked_at.is_(None),
                    )
                    .order_by(CredentialProjectGrant.credential_id)
                )
            )
            .scalars()
            .all()
        )

    async def validation_count_since(self, user_id: uuid.UUID, since: datetime) -> int:
        return int(
            (
                await self.session.execute(
                    select(func.count(AIAuditEvent.id)).where(
                        AIAuditEvent.actor_user_id == user_id,
                        AIAuditEvent.action.in_(
                            ("credential_validate_temporary", "credential_validate_saved")
                        ),
                        AIAuditEvent.created_at >= since,
                    )
                )
            ).scalar_one()
        )

    async def list_audit(
        self,
        *,
        user_id: uuid.UUID,
        project_id: uuid.UUID | None,
        limit: int,
        offset: int,
    ) -> tuple[list[AIAuditEvent], int]:
        predicate = (
            AIAuditEvent.actor_user_id == user_id
            if project_id is None
            else AIAuditEvent.project_id == project_id
        )
        total = int(
            (
                await self.session.execute(select(func.count(AIAuditEvent.id)).where(predicate))
            ).scalar_one()
        )
        items = list(
            (
                await self.session.execute(
                    select(AIAuditEvent)
                    .where(predicate)
                    .order_by(AIAuditEvent.created_at.desc(), AIAuditEvent.id.desc())
                    .limit(limit)
                    .offset(offset)
                )
            )
            .scalars()
            .all()
        )
        return items, total

    def add(self, value: object) -> None:
        self.session.add(value)

    def add_all(self, values: list[object]) -> None:
        self.session.add_all(values)

    async def flush(self) -> None:
        await self.session.flush()


__all__ = ["SqlAlchemyAIFoundationRepository"]
