"""Strict public schemas for authenticated sessions and reviewer membership."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

RequestUUID = Annotated[
    UUID,
    BeforeValidator(lambda value: UUID(value) if isinstance(value, str) else value),
]


class AuthenticatedUserRead(BaseModel):
    """Non-sensitive current-user profile backed by the internal user ID."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: UUID
    display_name: Annotated[str, Field(min_length=1, max_length=200)]
    email: Annotated[str, Field(min_length=3, max_length=320)] | None


class AuthSessionRead(BaseModel):
    """Browser bootstrap state; CSRF is supplied by a separate bound cookie."""

    model_config = ConfigDict(extra="forbid", strict=True)

    authenticated: Literal[True]
    user: AuthenticatedUserRead
    expires_at: datetime


class AnonymousSessionRead(BaseModel):
    """Explicit unauthenticated session state."""

    model_config = ConfigDict(extra="forbid", strict=True)

    authenticated: Literal[False] = False


class AssignReviewerRequest(BaseModel):
    """Owner command selecting one already-existing internal user."""

    model_config = ConfigDict(extra="forbid", strict=True)

    user_id: RequestUUID


class ProjectMembershipRead(BaseModel):
    """Reviewer membership without external subject or storage internals."""

    model_config = ConfigDict(extra="forbid", strict=True)

    user_id: UUID
    role: Literal["reviewer"]
    display_name: Annotated[str, Field(min_length=1, max_length=200)]
    email: Annotated[str, Field(min_length=3, max_length=320)] | None
    created_at: datetime


class ProjectMembershipListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    items: list[ProjectMembershipRead]


class AssignableUserListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    items: list[AuthenticatedUserRead]
