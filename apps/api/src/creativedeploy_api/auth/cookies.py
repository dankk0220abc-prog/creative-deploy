"""Central cookie names and attributes for OIDC browser state."""

from creativedeploy_api.core.config import Settings


def session_cookie_name(settings: Settings) -> str:
    return "__Host-paintpilot_session" if settings.app_env == "production" else "paintpilot_session"


def csrf_cookie_name(settings: Settings) -> str:
    return "__Host-paintpilot_csrf" if settings.app_env == "production" else "paintpilot_csrf"


def oidc_flow_cookie_name(settings: Settings) -> str:
    return (
        "__Host-paintpilot_oidc_flow"
        if settings.app_env == "production"
        else "paintpilot_oidc_flow"
    )
