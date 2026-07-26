"""Stable, safe PaintPilot API error response schemas."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

ErrorCategory = Literal[
    "VALIDATION_ERROR",
    "NOT_FOUND",
    "IDEMPOTENCY_KEY_REUSED",
    "INVALID_STATE_TRANSITION",
    "CONFLICT",
    "DATABASE_UNAVAILABLE",
    "STORAGE_ERROR",
    "PROVIDER_TIMEOUT",
    "PROVIDER_RATE_LIMIT",
    "PROVIDER_RESPONSE_INVALID",
    "RETRIEVAL_ERROR",
    "SCHEMA_VALIDATION_ERROR",
    "INTERNAL_ERROR",
]


class ErrorResponse(BaseModel):
    """Product-contract error envelope with controlled diagnostic content."""

    model_config = ConfigDict(extra="forbid", strict=True)

    error_code: str
    category: ErrorCategory
    message: str
    retryable: bool
    request_id: UUID
    current_state: str | None
    allowed_actions: list[str]
    safe_details: dict[str, object]
