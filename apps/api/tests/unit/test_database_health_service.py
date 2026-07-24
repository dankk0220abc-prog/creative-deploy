"""Focused failure-path tests for the PostgreSQL readiness service."""

import asyncio
import logging
from typing import NoReturn, cast

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from creativedeploy_api.services.database_health import (
    DatabaseHealthResult,
    DatabaseHealthService,
)

EXPECTED_FAILURE = DatabaseHealthResult(
    status="error",
    latency_ms=None,
    error_code="DATABASE_UNAVAILABLE",
)


def run_check(engine: object, timeout_seconds: float = 1.0) -> DatabaseHealthResult:
    """Run a service check against a deliberately small engine test double."""
    return asyncio.run(
        DatabaseHealthService(
            cast(AsyncEngine, engine),
            timeout_seconds=timeout_seconds,
        ).check()
    )


class ConnectionFailureEngine:
    def connect(self) -> NoReturn:
        raise OSError("synthetic-connection-detail")


class SqlFailureConnection:
    async def execute(self, _statement: object) -> None:
        raise SQLAlchemyError("synthetic-sql-detail")


class SqlFailureConnectionContext:
    async def __aenter__(self) -> SqlFailureConnection:
        return SqlFailureConnection()

    async def __aexit__(
        self,
        _exception_type: object,
        _exception: object,
        _traceback: object,
    ) -> None:
        return None


class SqlFailureEngine:
    def connect(self) -> SqlFailureConnectionContext:
        return SqlFailureConnectionContext()


class SlowConnectionContext:
    async def __aenter__(self) -> object:
        await asyncio.sleep(60)
        return object()

    async def __aexit__(
        self,
        _exception_type: object,
        _exception: object,
        _traceback: object,
    ) -> None:
        return None


class SlowEngine:
    def connect(self) -> SlowConnectionContext:
        return SlowConnectionContext()


class CancelledConnectionContext:
    async def __aenter__(self) -> object:
        raise asyncio.CancelledError

    async def __aexit__(
        self,
        _exception_type: object,
        _exception: object,
        _traceback: object,
    ) -> None:
        return None


class CancelledEngine:
    def connect(self) -> CancelledConnectionContext:
        return CancelledConnectionContext()


def test_connection_failure_maps_to_safe_result(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(
        logging.WARNING,
        logger="creativedeploy_api.services.database_health",
    )

    result = run_check(ConnectionFailureEngine())

    assert result == EXPECTED_FAILURE
    assert "OSError" in caplog.text
    assert "synthetic-connection-detail" not in caplog.text


def test_sqlalchemy_failure_maps_to_safe_result(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(
        logging.WARNING,
        logger="creativedeploy_api.services.database_health",
    )

    result = run_check(SqlFailureEngine())

    assert result == EXPECTED_FAILURE
    assert "SQLAlchemyError" in caplog.text
    assert "synthetic-sql-detail" not in caplog.text


def test_timeout_maps_to_safe_result() -> None:
    result = run_check(SlowEngine(), timeout_seconds=0.001)

    assert result == EXPECTED_FAILURE


def test_cancellation_is_not_swallowed() -> None:
    with pytest.raises(asyncio.CancelledError):
        run_check(CancelledEngine())
