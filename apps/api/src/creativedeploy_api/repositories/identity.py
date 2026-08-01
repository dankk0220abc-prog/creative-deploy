"""Transactional identity, session, and reviewer-membership persistence."""

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from creativedeploy_api.db.models import (
    AuthSession,
    ExternalIdentity,
    OidcLoginFlow,
    PaintProject,
    ProjectMembership,
    UserAccount,
)


@dataclass(frozen=True, slots=True)
class ProjectAccess:
    """Resolved project owner and the current user's effective role."""

    project: PaintProject
    role: str

    @property
    def is_owner(self) -> bool:
        return self.role == "owner"


class SqlAlchemyIdentityRepository:
    """Database-authoritative identity and authorization operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add_login_flow(self, flow: OidcLoginFlow) -> None:
        self._session.add(flow)

    async def consume_login_flow(
        self,
        *,
        state_hash: str,
        browser_binding_hash: str,
        now: datetime,
    ) -> OidcLoginFlow | None:
        flow = (
            await self._session.execute(
                select(OidcLoginFlow)
                .where(
                    OidcLoginFlow.state_hash == state_hash,
                    OidcLoginFlow.browser_binding_hash == browser_binding_hash,
                    OidcLoginFlow.consumed_at.is_(None),
                    OidcLoginFlow.expires_at > now,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if flow is not None:
            flow.consumed_at = now
            await self._session.flush()
        return flow

    async def find_or_create_identity(
        self,
        *,
        issuer: str,
        subject: str,
        display_name: str,
        email: str | None,
        now: datetime,
    ) -> UserAccount:
        """Serialize issuer+subject creation and update only mutable profile facts."""
        advisory_key = hashlib.sha256(f"{issuer}\0{subject}".encode()).hexdigest()[:16]
        signed_key = int(advisory_key, 16)
        if signed_key >= 2**63:
            signed_key -= 2**64
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(:key)"),
            {"key": signed_key},
        )
        identity = (
            await self._session.execute(
                select(ExternalIdentity).where(
                    ExternalIdentity.issuer == issuer,
                    ExternalIdentity.subject == subject,
                )
            )
        ).scalar_one_or_none()
        if identity is None:
            user = UserAccount(
                id=uuid.uuid4(),
                display_name=display_name,
                email=email,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            self._session.add(user)
            await self._session.flush()
            identity = ExternalIdentity(
                id=uuid.uuid4(),
                user_id=user.id,
                issuer=issuer,
                subject=subject,
                email_snapshot=email,
                display_name_snapshot=display_name,
                created_at=now,
                last_authenticated_at=now,
            )
            self._session.add(identity)
            await self._session.flush()
            return user
        user = (
            await self._session.execute(
                select(UserAccount).where(UserAccount.id == identity.user_id).with_for_update()
            )
        ).scalar_one()
        identity.email_snapshot = email
        identity.display_name_snapshot = display_name
        identity.last_authenticated_at = now
        user.display_name = display_name
        user.email = email
        user.updated_at = now
        await self._session.flush()
        return user

    def add_session(self, session: AuthSession) -> None:
        self._session.add(session)

    async def get_session_user(
        self,
        *,
        token_hash: str,
        now: datetime,
        for_update: bool = False,
    ) -> tuple[AuthSession, UserAccount] | None:
        statement = (
            select(AuthSession, UserAccount)
            .join(UserAccount, UserAccount.id == AuthSession.user_id)
            .where(
                AuthSession.token_hash == token_hash,
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > now,
                UserAccount.is_active.is_(True),
            )
        )
        if for_update:
            statement = statement.with_for_update(of=AuthSession)
        row = (await self._session.execute(statement)).one_or_none()
        if row is None:
            return None
        return row[0], row[1]

    async def revoke_session(self, *, token_hash: str, now: datetime) -> bool:
        updated = (
            await self._session.execute(
                update(AuthSession)
                .where(
                    AuthSession.token_hash == token_hash,
                    AuthSession.revoked_at.is_(None),
                )
                .values(revoked_at=now)
                .returning(AuthSession.id)
            )
        ).scalar_one_or_none()
        return updated is not None

    async def resolve_project_access(
        self,
        *,
        project_id: uuid.UUID,
        principal_id: str,
        user_id: uuid.UUID | None,
        for_update: bool = False,
    ) -> ProjectAccess | None:
        statement = select(PaintProject).where(
            PaintProject.id == project_id,
            or_(
                PaintProject.owner_principal_id == principal_id,
                PaintProject.id.in_(
                    select(ProjectMembership.paint_project_id).where(
                        ProjectMembership.user_id == user_id
                    )
                    if user_id is not None
                    else select(ProjectMembership.paint_project_id).where(text("false"))
                ),
            ),
        )
        if for_update:
            statement = statement.with_for_update()
        project = (await self._session.execute(statement)).scalar_one_or_none()
        if project is None:
            return None
        role = "owner" if project.owner_principal_id == principal_id else "reviewer"
        return ProjectAccess(project=project, role=role)

    async def list_accessible_projects(
        self,
        *,
        principal_id: str,
        user_id: uuid.UUID | None,
        limit: int,
        offset: int,
    ) -> tuple[list[PaintProject], int]:
        membership_projects = (
            select(ProjectMembership.paint_project_id).where(ProjectMembership.user_id == user_id)
            if user_id is not None
            else select(ProjectMembership.paint_project_id).where(text("false"))
        )
        predicate = or_(
            PaintProject.owner_principal_id == principal_id,
            PaintProject.id.in_(membership_projects),
        )
        total = (
            await self._session.execute(select(func.count(PaintProject.id)).where(predicate))
        ).scalar_one()
        projects = list(
            (
                await self._session.execute(
                    select(PaintProject)
                    .where(predicate)
                    .order_by(PaintProject.updated_at.desc(), PaintProject.id.desc())
                    .limit(limit)
                    .offset(offset)
                )
            )
            .scalars()
            .all()
        )
        return projects, int(total)

    async def list_project_memberships(
        self,
        *,
        project_id: uuid.UUID,
    ) -> list[tuple[ProjectMembership, UserAccount]]:
        rows = (
            await self._session.execute(
                select(ProjectMembership, UserAccount)
                .join(UserAccount, UserAccount.id == ProjectMembership.user_id)
                .where(ProjectMembership.paint_project_id == project_id)
                .order_by(UserAccount.display_name, UserAccount.id)
            )
        ).all()
        return [(row[0], row[1]) for row in rows]

    async def find_user(self, *, user_id: uuid.UUID) -> UserAccount | None:
        return (
            await self._session.execute(
                select(UserAccount).where(
                    UserAccount.id == user_id,
                    UserAccount.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()

    async def list_assignable_users(
        self,
        *,
        exclude_user_id: uuid.UUID,
    ) -> list[UserAccount]:
        return list(
            (
                await self._session.execute(
                    select(UserAccount)
                    .where(
                        UserAccount.is_active.is_(True),
                        UserAccount.id != exclude_user_id,
                    )
                    .order_by(UserAccount.display_name, UserAccount.id)
                )
            )
            .scalars()
            .all()
        )

    async def add_membership_idempotently(
        self,
        *,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        assigned_by_user_id: uuid.UUID,
    ) -> ProjectMembership:
        now = datetime.now(UTC)
        statement = (
            insert(ProjectMembership)
            .values(
                id=uuid.uuid4(),
                paint_project_id=project_id,
                user_id=user_id,
                role="reviewer",
                assigned_by_user_id=assigned_by_user_id,
                created_at=now,
            )
            .on_conflict_do_nothing(
                index_elements=["paint_project_id", "user_id"],
            )
            .returning(ProjectMembership)
        )
        created = (await self._session.execute(statement)).scalar_one_or_none()
        if created is not None:
            return created
        return (
            await self._session.execute(
                select(ProjectMembership).where(
                    ProjectMembership.paint_project_id == project_id,
                    ProjectMembership.user_id == user_id,
                )
            )
        ).scalar_one()

    async def remove_membership_idempotently(
        self,
        *,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        membership = (
            await self._session.execute(
                select(ProjectMembership)
                .where(
                    ProjectMembership.paint_project_id == project_id,
                    ProjectMembership.user_id == user_id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if membership is None:
            return False
        await self._session.delete(membership)
        await self._session.flush()
        return True
