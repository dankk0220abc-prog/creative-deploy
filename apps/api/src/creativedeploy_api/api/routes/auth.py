"""OIDC login, callback, session bootstrap, and logout routes."""

from typing import Annotated, Any
from urllib.parse import urlencode

from fastapi import APIRouter, Query, Request, Response, status
from fastapi.responses import RedirectResponse

from creativedeploy_api.api.dependencies import (
    AuthenticationServiceDependency,
    DatabaseSessionDependency,
)
from creativedeploy_api.auth.cookies import (
    clear_oidc_flow_cookie,
    clear_session_cookies,
    csrf_cookie_name,
    oidc_flow_cookie_name,
    session_cookie_name,
)
from creativedeploy_api.auth.oidc import OidcClient
from creativedeploy_api.core.config import Settings
from creativedeploy_api.schemas.auth import AnonymousSessionRead, AuthSessionRead
from creativedeploy_api.schemas.errors import ErrorResponse
from creativedeploy_api.services.identity import (
    AuthenticationService,
    IdentityProviderUnavailableApplicationError,
    OidcCallbackError,
    validated_return_to,
)

router = APIRouter(prefix="/auth", tags=["authentication"])

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse, "description": "Invalid or expired OIDC callback."},
    401: {"model": ErrorResponse, "description": "Authentication is required."},
    403: {"model": ErrorResponse, "description": "CSRF validation failed."},
    503: {"model": ErrorResponse, "description": "Identity provider unavailable."},
}


def _service_for_request(
    request: Request,
    session: DatabaseSessionDependency,
) -> AuthenticationService:
    settings: Settings = request.app.state.settings
    oidc_client: OidcClient = request.app.state.oidc_client
    return AuthenticationService(session, settings, oidc_client)


@router.get("/login", responses=ERROR_RESPONSES)
async def login(
    request: Request,
    session: DatabaseSessionDependency,
    return_to: Annotated[str | None, Query(max_length=512)] = None,
) -> RedirectResponse:
    """Begin OIDC login and bind state/nonce/PKCE to this browser."""
    settings: Settings = request.app.state.settings
    service = _service_for_request(request, session)
    safe_return_to = validated_return_to(return_to)
    try:
        started = await service.start_login(return_to=safe_return_to)
    except IdentityProviderUnavailableApplicationError:
        return RedirectResponse(
            url=f"/paintpilot/login?{
                urlencode(
                    {
                        'auth_error': 'identity_provider_unavailable',
                        'return_to': safe_return_to,
                    }
                )
            }",
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Cache-Control": "no-store"},
        )
    except OidcCallbackError:
        return RedirectResponse(
            url=f"/paintpilot/login?{
                urlencode(
                    {
                        'auth_error': 'login_failed',
                        'return_to': safe_return_to,
                    }
                )
            }",
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Cache-Control": "no-store"},
        )
    response = RedirectResponse(
        url=started.authorization_url,
        status_code=status.HTTP_302_FOUND,
        headers={"Cache-Control": "no-store"},
    )
    response.set_cookie(
        oidc_flow_cookie_name(settings),
        started.browser_binding,
        max_age=settings.oidc_login_ttl_seconds,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        path="/",
    )
    return response


@router.get("/callback", responses=ERROR_RESPONSES)
async def callback(
    request: Request,
    session: DatabaseSessionDependency,
    code: Annotated[str | None, Query(min_length=1, max_length=2048)] = None,
    state: Annotated[str | None, Query(min_length=32, max_length=256)] = None,
    error: Annotated[str | None, Query(max_length=128)] = None,
) -> RedirectResponse:
    """Consume one callback, rotate any prior session, and set opaque cookies."""
    settings: Settings = request.app.state.settings
    if error is not None or code is None or state is None:
        raise OidcCallbackError
    browser_binding = request.cookies.get(oidc_flow_cookie_name(settings))
    if browser_binding is None:
        raise OidcCallbackError
    service = _service_for_request(request, session)
    completed = await service.complete_login(
        state=state,
        code=code,
        browser_binding=browser_binding,
        prior_session_token=request.cookies.get(session_cookie_name(settings)),
    )
    response = RedirectResponse(
        url=completed.return_to,
        status_code=status.HTTP_303_SEE_OTHER,
        headers={"Cache-Control": "no-store"},
    )
    clear_oidc_flow_cookie(response, settings)
    response.set_cookie(
        session_cookie_name(settings),
        completed.session_token,
        max_age=settings.auth_session_ttl_seconds,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        csrf_cookie_name(settings),
        completed.csrf_token,
        max_age=settings.auth_session_ttl_seconds,
        httponly=False,
        secure=settings.secure_cookies,
        samesite="strict",
        path="/",
    )
    return response


@router.get(
    "/session",
    response_model=AuthSessionRead | AnonymousSessionRead,
    responses=ERROR_RESPONSES,
)
async def session_status(
    request: Request,
    service: AuthenticationServiceDependency,
) -> AuthSessionRead | AnonymousSessionRead:
    """Return explicit current-user or anonymous state without token material."""
    settings: Settings = request.app.state.settings
    current = await service.session_status(
        session_token=request.cookies.get(session_cookie_name(settings))
    )
    return AnonymousSessionRead() if current is None else current


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, responses=ERROR_RESPONSES)
async def logout(
    request: Request,
    service: AuthenticationServiceDependency,
) -> Response:
    """Revoke the current server session and expire both browser cookies."""
    settings: Settings = request.app.state.settings
    await service.logout(session_token=request.cookies.get(session_cookie_name(settings)))
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_session_cookies(response, settings)
    return response
