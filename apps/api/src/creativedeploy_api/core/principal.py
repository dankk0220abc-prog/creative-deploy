"""PaintPilot request Principal value object and configured demo adapter."""

import uuid
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from creativedeploy_api.core.config import Settings

PrincipalId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]
PrincipalDisplayName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]


class PrincipalType(StrEnum):
    """Approved Principal categories."""

    HUMAN = "human"
    SYSTEM = "system"


class AuthenticationMode(StrEnum):
    """Approved Principal authentication modes."""

    LOCAL_DEVELOPMENT = "local_development"
    CONFIGURED_DEMO_OPERATOR = "configured_demo_operator"
    FUTURE_AUTHENTICATED_USER = "future_authenticated_user"
    OIDC_AUTHORIZATION_CODE = "oidc_authorization_code"


class PrincipalContext(BaseModel):
    """Non-persistent identity context supplied by an explicit adapter."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    principal_id: PrincipalId
    principal_type: PrincipalType
    display_name: PrincipalDisplayName
    authentication_mode: AuthenticationMode
    user_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class ConfiguredDemoPrincipalAdapter:
    """Resolve the protected single-operator Principal from non-secret settings."""

    principal_id: str
    display_name: str

    @classmethod
    def from_settings(cls, settings: Settings) -> "ConfiguredDemoPrincipalAdapter":
        """Build the adapter only from explicit, validated non-production settings."""
        principal_id, display_name = settings.require_configured_demo_principal()
        return cls(
            principal_id=principal_id,
            display_name=display_name,
        )

    def resolve(self) -> PrincipalContext:
        """Return the configured human Principal for the current request."""
        return PrincipalContext(
            principal_id=self.principal_id,
            principal_type=PrincipalType.HUMAN,
            display_name=self.display_name,
            authentication_mode=AuthenticationMode.CONFIGURED_DEMO_OPERATOR,
        )
