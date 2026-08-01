"""Central cookie names, attributes, and standards-compliant expiry helpers."""

from fastapi import Response

from creativedeploy_api.core.config import Settings


def session_cookie_name(settings: Settings) -> str:
    return "__Host-paintpilot_session" if settings.secure_cookies else "paintpilot_session"


def csrf_cookie_name(settings: Settings) -> str:
    return "__Host-paintpilot_csrf" if settings.secure_cookies else "paintpilot_csrf"


def oidc_flow_cookie_name(settings: Settings) -> str:
    return "__Host-paintpilot_oidc_flow" if settings.secure_cookies else "paintpilot_oidc_flow"


def clear_oidc_flow_cookie(response: Response, settings: Settings) -> None:
    """Expire the browser-bound OIDC cookie without violating host-prefix rules."""
    response.delete_cookie(
        oidc_flow_cookie_name(settings),
        path="/",
        secure=settings.secure_cookies,
        httponly=True,
        samesite="lax",
    )


def clear_session_cookies(response: Response, settings: Settings) -> None:
    """Expire session and CSRF cookies using their original security attributes."""
    response.delete_cookie(
        session_cookie_name(settings),
        path="/",
        secure=settings.secure_cookies,
        httponly=True,
        samesite="lax",
    )
    response.delete_cookie(
        csrf_cookie_name(settings),
        path="/",
        secure=settings.secure_cookies,
        httponly=False,
        samesite="strict",
    )
