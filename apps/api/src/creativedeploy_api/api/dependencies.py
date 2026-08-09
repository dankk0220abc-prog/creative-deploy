"""Explicit FastAPI dependencies for database and Principal boundaries."""

import hmac
import uuid
from collections.abc import AsyncIterator
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from creativedeploy_api.ai.encryption import CredentialCipher
from creativedeploy_api.ai.fixture_provider import FixtureProviderAdapter
from creativedeploy_api.auth.cookies import csrf_cookie_name, session_cookie_name
from creativedeploy_api.auth.oidc import OidcClient
from creativedeploy_api.core.config import Settings
from creativedeploy_api.core.principal import (
    ConfiguredDemoPrincipalAdapter,
    PrincipalContext,
)
from creativedeploy_api.services.ai_foundation import (
    AIFoundationService,
    Phase3UnavailableError,
)
from creativedeploy_api.services.identity import (
    AuthenticationService,
    InvalidCsrfTokenError,
    ProjectMembershipService,
)
from creativedeploy_api.services.image_assets import ImageAssetService
from creativedeploy_api.services.paint_projects import PaintProjectService
from creativedeploy_api.services.region_sets import RegionSetService
from creativedeploy_api.storage.images import ImageStoragePort


def get_request_id(request: Request) -> uuid.UUID:
    """Return one generated correlation ID for the lifetime of a request."""
    existing = getattr(request.state, "request_id", None)
    if isinstance(existing, uuid.UUID):
        return existing
    request_id = uuid.uuid4()
    request.state.request_id = request_id
    return request_id


async def get_database_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield one AsyncSession and always close it after the request."""
    session_factory = cast(
        async_sessionmaker[AsyncSession],
        request.app.state.database_session_factory,
    )
    async with session_factory() as session:
        yield session


DatabaseSessionDependency = Annotated[AsyncSession, Depends(get_database_session)]


def get_authentication_service(
    request: Request,
    session: DatabaseSessionDependency,
) -> AuthenticationService:
    """Build the request-scoped OIDC/session service."""
    settings = cast(Settings, request.app.state.settings)
    oidc_client = cast(OidcClient, request.app.state.oidc_client)
    return AuthenticationService(session, settings, oidc_client)


AuthenticationServiceDependency = Annotated[
    AuthenticationService,
    Depends(get_authentication_service),
]


async def get_current_principal(
    request: Request,
    session: DatabaseSessionDependency,
) -> PrincipalContext:
    """Resolve either the explicit local demo adapter or an OIDC session."""
    settings = cast(Settings, request.app.state.settings)
    if settings.identity_provider == "configured_demo":
        adapter = cast(
            ConfiguredDemoPrincipalAdapter,
            request.app.state.principal_adapter,
        )
        return adapter.resolve()
    oidc_client = cast(OidcClient, request.app.state.oidc_client)
    service = AuthenticationService(session, settings, oidc_client)
    resolved = await service.resolve_session(
        session_token=request.cookies.get(session_cookie_name(settings))
    )
    return resolved.principal


PrincipalDependency = Annotated[PrincipalContext, Depends(get_current_principal)]
RequestIdDependency = Annotated[uuid.UUID, Depends(get_request_id)]


async def enforce_csrf(
    request: Request,
    session: DatabaseSessionDependency,
) -> None:
    """Require a session-bound double-submit token on every unsafe API request."""
    if request.method in {"GET", "HEAD", "OPTIONS", "TRACE"}:
        return
    settings = cast(Settings, request.app.state.settings)
    if settings.identity_provider == "configured_demo":
        return
    csrf_cookie = request.cookies.get(csrf_cookie_name(settings))
    csrf_header = request.headers.get("X-CSRF-Token")
    if (
        csrf_cookie is None
        or csrf_header is None
        or not hmac.compare_digest(csrf_cookie, csrf_header)
    ):
        raise InvalidCsrfTokenError
    oidc_client = cast(OidcClient, request.app.state.oidc_client)
    service = AuthenticationService(session, settings, oidc_client)
    await service.validate_csrf(
        session_token=request.cookies.get(session_cookie_name(settings)),
        csrf_token=csrf_header,
    )


def get_paint_project_service(
    request: Request,
    session: DatabaseSessionDependency,
) -> PaintProjectService:
    """Build the request-scoped PaintProject service."""
    settings = cast(Settings, request.app.state.settings)
    return PaintProjectService(
        session,
        database_lock_timeout_ms=settings.database_lock_timeout_ms,
        database_statement_timeout_ms=settings.database_statement_timeout_ms,
    )


PaintProjectServiceDependency = Annotated[
    PaintProjectService,
    Depends(get_paint_project_service),
]


def get_image_asset_service(
    request: Request,
    session: DatabaseSessionDependency,
) -> ImageAssetService:
    """Build the request-scoped ImageAsset service with the private storage port."""
    settings = cast(Settings, request.app.state.settings)
    storage = cast(ImageStoragePort, request.app.state.image_storage)
    return ImageAssetService(session, storage, settings)


ImageAssetServiceDependency = Annotated[
    ImageAssetService,
    Depends(get_image_asset_service),
]


def get_region_set_service(
    request: Request,
    session: DatabaseSessionDependency,
) -> RegionSetService:
    """Build the request-scoped RegionSet service with private source access."""
    settings = cast(Settings, request.app.state.settings)
    storage = cast(ImageStoragePort, request.app.state.image_storage)
    return RegionSetService(session, storage, settings)


RegionSetServiceDependency = Annotated[
    RegionSetService,
    Depends(get_region_set_service),
]


def get_project_membership_service(
    session: DatabaseSessionDependency,
) -> ProjectMembershipService:
    return ProjectMembershipService(session)


ProjectMembershipServiceDependency = Annotated[
    ProjectMembershipService,
    Depends(get_project_membership_service),
]


def get_ai_foundation_service(
    request: Request,
    session: DatabaseSessionDependency,
) -> AIFoundationService:
    """Build the fixture service only when its fail-closed runtime gate is active."""
    settings = cast(Settings, request.app.state.settings)
    if not settings.phase3a_fixture_enabled:
        raise Phase3UnavailableError
    cipher = getattr(request.app.state, "ai_cipher", None)
    adapter = getattr(request.app.state, "fixture_provider_adapter", None)
    if not isinstance(cipher, CredentialCipher) or not isinstance(adapter, FixtureProviderAdapter):
        raise Phase3UnavailableError
    return AIFoundationService(session, cipher, adapter)


AIFoundationServiceDependency = Annotated[
    AIFoundationService,
    Depends(get_ai_foundation_service),
]
