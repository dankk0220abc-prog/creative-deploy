"""OIDC session lifecycle and owner-governed reviewer membership."""

import hmac
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from creativedeploy_api.auth.oidc import (
    OidcClient,
    OidcProtocolError,
    OidcProviderUnavailableError,
    pkce_challenge,
    random_urlsafe,
    sha256_text,
)
from creativedeploy_api.core.config import Settings
from creativedeploy_api.core.principal import (
    AuthenticationMode,
    PrincipalContext,
    PrincipalType,
)
from creativedeploy_api.db.models import AuthSession, OidcLoginFlow
from creativedeploy_api.repositories.identity import SqlAlchemyIdentityRepository
from creativedeploy_api.schemas.auth import (
    AssignableUserListResponse,
    AuthenticatedUserRead,
    AuthSessionRead,
    ProjectMembershipListResponse,
    ProjectMembershipRead,
)
from creativedeploy_api.schemas.errors import ErrorCategory
from creativedeploy_api.services.paint_projects import (
    PaintProjectApplicationError,
    PaintProjectNotFoundError,
)


class AuthenticationRequiredError(PaintProjectApplicationError):
    status_code = 401
    error_code = "AUTHENTICATION_REQUIRED"
    category: ErrorCategory = "CONFLICT"
    message = "Authentication is required."
    allowed_actions = ("login",)


class InvalidCsrfTokenError(PaintProjectApplicationError):
    status_code = 403
    error_code = "CSRF_VALIDATION_FAILED"
    category: ErrorCategory = "CONFLICT"
    message = "The state-changing request failed CSRF validation."
    allowed_actions = ("refresh_session", "retry")


class OidcCallbackError(PaintProjectApplicationError):
    status_code = 400
    error_code = "OIDC_CALLBACK_INVALID"
    category: ErrorCategory = "VALIDATION_ERROR"
    message = "The sign-in callback was invalid or expired."
    allowed_actions = ("login",)


class IdentityProviderUnavailableApplicationError(PaintProjectApplicationError):
    status_code = 503
    error_code = "IDENTITY_PROVIDER_UNAVAILABLE"
    category: ErrorCategory = "CONFLICT"
    message = "The identity provider is temporarily unavailable."
    retryable = True
    allowed_actions = ("retry_login",)


class ReviewerUserNotFoundError(PaintProjectApplicationError):
    status_code = 404
    error_code = "REVIEWER_USER_NOT_FOUND"
    category: ErrorCategory = "NOT_FOUND"
    message = "The reviewer user was not found."


@dataclass(frozen=True, slots=True)
class LoginStart:
    authorization_url: str
    browser_binding: str


@dataclass(frozen=True, slots=True)
class LoginComplete:
    session_token: str
    csrf_token: str
    return_to: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class ResolvedSession:
    principal: PrincipalContext
    csrf_token_hash: str
    expires_at: datetime
    user: AuthenticatedUserRead


def validated_return_to(value: str | None) -> str:
    """Allow only a same-origin PaintPilot route."""
    candidate = value or "/paintpilot/projects"
    if (
        not candidate.startswith("/paintpilot")
        or candidate.startswith("//")
        or "\\" in candidate
        or "\r" in candidate
        or "\n" in candidate
    ):
        return "/paintpilot/projects"
    return candidate[:512]


class AuthenticationService:
    """Execute one-time OIDC login flows and opaque server-side sessions."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        oidc_client: OidcClient,
    ) -> None:
        self._session = session
        self._settings = settings
        self._oidc = oidc_client
        self._repository = SqlAlchemyIdentityRepository(session)

    async def start_login(self, *, return_to: str | None) -> LoginStart:
        state = random_urlsafe()
        nonce = random_urlsafe()
        verifier = random_urlsafe(64)
        browser_binding = random_urlsafe()
        try:
            authorization_url = await self._oidc.authorization_url(
                state=state,
                nonce=nonce,
                code_challenge=pkce_challenge(verifier),
            )
        except OidcProviderUnavailableError as error:
            raise IdentityProviderUnavailableApplicationError from error
        except OidcProtocolError as error:
            raise OidcCallbackError from error
        created_at = datetime.now(UTC)
        async with self._session.begin():
            self._repository.add_login_flow(
                OidcLoginFlow(
                    id=uuid.uuid4(),
                    state_hash=sha256_text(state),
                    browser_binding_hash=sha256_text(browser_binding),
                    nonce=nonce,
                    code_verifier=verifier,
                    return_to=validated_return_to(return_to),
                    created_at=created_at,
                    expires_at=created_at
                    + timedelta(seconds=self._settings.oidc_login_ttl_seconds),
                )
            )
        return LoginStart(
            authorization_url=authorization_url,
            browser_binding=browser_binding,
        )

    async def complete_login(
        self,
        *,
        state: str,
        code: str,
        browser_binding: str,
        prior_session_token: str | None,
    ) -> LoginComplete:
        now = datetime.now(UTC)
        async with self._session.begin():
            flow = await self._repository.consume_login_flow(
                state_hash=sha256_text(state),
                browser_binding_hash=sha256_text(browser_binding),
                now=now,
            )
            if flow is None:
                raise OidcCallbackError
            verifier = flow.code_verifier
            nonce = flow.nonce
            return_to = flow.return_to
        try:
            claims = await self._oidc.exchange_and_validate(
                code=code,
                code_verifier=verifier,
                expected_nonce=nonce,
            )
        except OidcProviderUnavailableError as error:
            raise IdentityProviderUnavailableApplicationError from error
        except OidcProtocolError as error:
            raise OidcCallbackError from error

        session_token = random_urlsafe(48)
        csrf_token = random_urlsafe(32)
        expires_at = now + timedelta(seconds=self._settings.auth_session_ttl_seconds)
        async with self._session.begin():
            user = await self._repository.find_or_create_identity(
                issuer=claims.issuer,
                subject=claims.subject,
                display_name=claims.display_name,
                email=claims.email,
                now=now,
            )
            if prior_session_token:
                await self._repository.revoke_session(
                    token_hash=sha256_text(prior_session_token),
                    now=now,
                )
            self._repository.add_session(
                AuthSession(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    token_hash=sha256_text(session_token),
                    csrf_token_hash=sha256_text(csrf_token),
                    oidc_issuer=claims.issuer,
                    created_at=now,
                    last_seen_at=now,
                    expires_at=expires_at,
                )
            )
        return LoginComplete(
            session_token=session_token,
            csrf_token=csrf_token,
            return_to=return_to,
            expires_at=expires_at,
        )

    async def resolve_session(self, *, session_token: str | None) -> ResolvedSession:
        if not session_token:
            raise AuthenticationRequiredError
        now = datetime.now(UTC)
        async with self._session.begin():
            row = await self._repository.get_session_user(
                token_hash=sha256_text(session_token),
                now=now,
            )
            if row is None:
                raise AuthenticationRequiredError
            session, user = row
            session.last_seen_at = now
        return ResolvedSession(
            principal=PrincipalContext(
                principal_id=str(user.id),
                principal_type=PrincipalType.HUMAN,
                display_name=user.display_name,
                authentication_mode=AuthenticationMode.OIDC_AUTHORIZATION_CODE,
                user_id=user.id,
            ),
            csrf_token_hash=session.csrf_token_hash,
            expires_at=session.expires_at,
            user=AuthenticatedUserRead(
                id=user.id,
                display_name=user.display_name,
                email=user.email,
            ),
        )

    async def session_status(self, *, session_token: str | None) -> AuthSessionRead | None:
        try:
            resolved = await self.resolve_session(session_token=session_token)
        except AuthenticationRequiredError:
            return None
        return AuthSessionRead(
            authenticated=True,
            user=resolved.user,
            expires_at=resolved.expires_at,
        )

    async def validate_csrf(
        self,
        *,
        session_token: str | None,
        csrf_token: str | None,
    ) -> None:
        if not session_token or not csrf_token:
            raise InvalidCsrfTokenError
        resolved = await self.resolve_session(session_token=session_token)
        if not hmac.compare_digest(
            sha256_text(csrf_token),
            resolved.csrf_token_hash,
        ):
            raise InvalidCsrfTokenError

    async def logout(self, *, session_token: str | None) -> None:
        if not session_token:
            return
        async with self._session.begin():
            await self._repository.revoke_session(
                token_hash=sha256_text(session_token),
                now=datetime.now(UTC),
            )


class ProjectMembershipService:
    """Apply Owner-only reviewer assignment with immediate session enforcement."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repository = SqlAlchemyIdentityRepository(session)

    async def _require_owner(
        self,
        *,
        project_id: uuid.UUID,
        principal: PrincipalContext,
    ) -> None:
        access = await self._repository.resolve_project_access(
            project_id=project_id,
            principal_id=principal.principal_id,
            user_id=principal.user_id,
            for_update=True,
        )
        if access is None or not access.is_owner:
            raise PaintProjectNotFoundError

    async def list_memberships(
        self,
        *,
        project_id: uuid.UUID,
        principal: PrincipalContext,
    ) -> ProjectMembershipListResponse:
        async with self._session.begin():
            await self._require_owner(project_id=project_id, principal=principal)
            rows = await self._repository.list_project_memberships(project_id=project_id)
        return ProjectMembershipListResponse(
            items=[
                ProjectMembershipRead(
                    user_id=user.id,
                    role="reviewer",
                    display_name=user.display_name,
                    email=user.email,
                    created_at=membership.created_at,
                )
                for membership, user in rows
            ]
        )

    async def list_assignable_users(
        self,
        *,
        project_id: uuid.UUID,
        principal: PrincipalContext,
    ) -> AssignableUserListResponse:
        if principal.user_id is None:
            raise PaintProjectNotFoundError
        async with self._session.begin():
            await self._require_owner(project_id=project_id, principal=principal)
            users = await self._repository.list_assignable_users(exclude_user_id=principal.user_id)
        return AssignableUserListResponse(
            items=[
                AuthenticatedUserRead(
                    id=user.id,
                    display_name=user.display_name,
                    email=user.email,
                )
                for user in users
            ]
        )

    async def assign(
        self,
        *,
        project_id: uuid.UUID,
        reviewer_user_id: uuid.UUID,
        principal: PrincipalContext,
    ) -> ProjectMembershipRead:
        if principal.user_id is None or reviewer_user_id == principal.user_id:
            raise ReviewerUserNotFoundError
        async with self._session.begin():
            await self._require_owner(project_id=project_id, principal=principal)
            user = await self._repository.find_user(user_id=reviewer_user_id)
            if user is None:
                raise ReviewerUserNotFoundError
            membership = await self._repository.add_membership_idempotently(
                project_id=project_id,
                user_id=reviewer_user_id,
                assigned_by_user_id=principal.user_id,
            )
        return ProjectMembershipRead(
            user_id=user.id,
            role="reviewer",
            display_name=user.display_name,
            email=user.email,
            created_at=membership.created_at,
        )

    async def remove(
        self,
        *,
        project_id: uuid.UUID,
        reviewer_user_id: uuid.UUID,
        principal: PrincipalContext,
    ) -> None:
        async with self._session.begin():
            await self._require_owner(project_id=project_id, principal=principal)
            await self._repository.remove_membership_idempotently(
                project_id=project_id,
                user_id=reviewer_user_id,
            )
