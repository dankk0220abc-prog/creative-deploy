"""Strict schemas for health endpoints."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictSchema(BaseModel):
    """Base schema that rejects unknown fields and implicit coercion."""

    model_config = ConfigDict(extra="forbid", strict=True)


class ServiceHealthResponse(StrictSchema):
    """Liveness response."""

    status: Literal["ok"]
    service: str
    version: str


class DatabaseCheck(StrictSchema):
    """PostgreSQL readiness result."""

    status: Literal["ok", "error"]
    latency_ms: Annotated[float, Field(ge=0)] | None
    error_code: Literal["DATABASE_UNAVAILABLE"] | None


class ReadinessChecks(StrictSchema):
    """Collection of readiness dependencies."""

    database: DatabaseCheck


class ReadinessResponse(StrictSchema):
    """Shared schema for healthy and degraded readiness responses."""

    status: Literal["ok", "degraded"]
    service: str
    version: str
    checks: ReadinessChecks
