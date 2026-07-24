"""Safe PostgreSQL readiness checks."""

import asyncio
import logging
from dataclasses import dataclass
from time import perf_counter_ns
from typing import Literal

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DatabaseHealthResult:
    """Structured result without internal exception details."""

    status: Literal["ok", "error"]
    latency_ms: float | None
    error_code: Literal["DATABASE_UNAVAILABLE"] | None


class DatabaseHealthService:
    """Execute the minimal PostgreSQL readiness query with a hard timeout."""

    def __init__(self, engine: AsyncEngine, timeout_seconds: float) -> None:
        self._engine = engine
        self._timeout_seconds = timeout_seconds

    async def check(self) -> DatabaseHealthResult:
        """Run SELECT 1 and convert expected infrastructure failures safely."""
        started_at = perf_counter_ns()
        try:
            async with asyncio.timeout(self._timeout_seconds):
                async with self._engine.connect() as connection:
                    await connection.execute(text("SELECT 1"))
        except (TimeoutError, OSError, SQLAlchemyError) as error:
            logger.warning("Database health check failed (%s)", type(error).__name__)
            return DatabaseHealthResult(
                status="error",
                latency_ms=None,
                error_code="DATABASE_UNAVAILABLE",
            )

        latency_ms = max((perf_counter_ns() - started_at) / 1_000_000, 0.0)
        return DatabaseHealthResult(
            status="ok",
            latency_ms=round(latency_ms, 2),
            error_code=None,
        )
