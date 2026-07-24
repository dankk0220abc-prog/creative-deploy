"""Unit tests for health endpoints and the database health service."""

import asyncio
from contextlib import AbstractContextManager
from pathlib import Path
from typing import cast

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncEngine

from creativedeploy_api.api.routes.health import get_database_health_service
from creativedeploy_api.app_factory import create_app
from creativedeploy_api.core.config import DEFAULT_ENV_FILE, REPOSITORY_ROOT, Settings
from creativedeploy_api.db.engine import create_database_engine
from creativedeploy_api.services.database_health import (
    DatabaseHealthResult,
    DatabaseHealthService,
)


class StubDatabaseHealthService:
    """Controllable route dependency."""

    def __init__(self, result: DatabaseHealthResult) -> None:
        self.result = result
        self.calls = 0

    async def check(self) -> DatabaseHealthResult:
        self.calls += 1
        return self.result


def build_client(
    settings: Settings,
    service: StubDatabaseHealthService,
) -> tuple[AbstractContextManager[TestClient], StubDatabaseHealthService]:
    app = create_app(settings)
    app.dependency_overrides[get_database_health_service] = lambda: service
    return TestClient(app), service


def test_liveness_returns_200_without_database(test_settings: Settings) -> None:
    service = StubDatabaseHealthService(
        DatabaseHealthResult(status="error", latency_ms=None, error_code="DATABASE_UNAVAILABLE")
    )
    client_context, tracked_service = build_client(test_settings, service)

    with client_context as client:
        response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "creativedeploy-api",
        "version": "0.1.0",
    }
    assert tracked_service.calls == 0


def test_readiness_returns_healthy_schema(test_settings: Settings) -> None:
    service = StubDatabaseHealthService(
        DatabaseHealthResult(status="ok", latency_ms=1.25, error_code=None)
    )
    client_context, _ = build_client(test_settings, service)

    with client_context as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "creativedeploy-api",
        "version": "0.1.0",
        "checks": {
            "database": {
                "status": "ok",
                "latency_ms": 1.25,
                "error_code": None,
            }
        },
    }


def test_readiness_returns_safe_503(test_settings: Settings) -> None:
    service = StubDatabaseHealthService(
        DatabaseHealthResult(status="error", latency_ms=None, error_code="DATABASE_UNAVAILABLE")
    )
    client_context, _ = build_client(test_settings, service)

    with client_context as client:
        response = client.get("/api/v1/health/ready")

    response_text = response.text.lower()
    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "service": "creativedeploy-api",
        "version": "0.1.0",
        "checks": {
            "database": {
                "status": "error",
                "latency_ms": None,
                "error_code": "DATABASE_UNAVAILABLE",
            }
        },
    }
    assert "postgresql" not in response_text
    assert "test:test" not in response_text
    assert "traceback" not in response_text


class SuccessfulConnection:
    async def execute(self, _statement: object) -> None:
        await asyncio.sleep(0)


class SuccessfulConnectionContext:
    async def __aenter__(self) -> SuccessfulConnection:
        await asyncio.sleep(0)
        return SuccessfulConnection()

    async def __aexit__(
        self,
        _exception_type: object,
        _exception: object,
        _traceback: object,
    ) -> None:
        await asyncio.sleep(0)


class SuccessfulEngine:
    def connect(self) -> SuccessfulConnectionContext:
        return SuccessfulConnectionContext()


def test_database_health_latency_is_non_negative() -> None:
    engine = cast(AsyncEngine, SuccessfulEngine())
    result = asyncio.run(DatabaseHealthService(engine, timeout_seconds=1.0).check())

    assert result.status == "ok"
    assert result.latency_ms is not None
    assert result.latency_ms >= 0


def test_database_url_is_redacted_from_settings_display() -> None:
    database_url = "postgresql+psycopg://review-user:synthetic-review-password@127.0.0.1:1/review"
    settings = Settings(database_url=database_url, _env_file=None)

    for rendered_settings in (repr(settings), str(settings)):
        assert "synthetic-review-password" not in rendered_settings
        assert database_url not in rendered_settings


def test_database_engine_uses_unwrapped_secret_value() -> None:
    settings = Settings(
        database_url=(
            "postgresql+psycopg://engine-user:synthetic-engine-password@127.0.0.1:1/engine"
        ),
        _env_file=None,
    )

    engine = create_database_engine(settings)
    try:
        assert engine.url.password == "synthetic-engine-password"
    finally:
        asyncio.run(engine.dispose())


def test_default_env_file_points_to_repository_root() -> None:
    expected_root = Path(__file__).resolve().parents[4]

    assert expected_root == REPOSITORY_ROOT
    assert expected_root / ".env" == DEFAULT_ENV_FILE
    assert Settings.model_config["env_file"] == DEFAULT_ENV_FILE


def test_absolute_env_file_loading_does_not_depend_on_working_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    temporary_env_file = tmp_path / "review.env"
    temporary_env_file.write_text(
        "DATABASE_URL=postgresql+psycopg://cwd-user:synthetic-cwd-password@127.0.0.1:1/cwd\n",
        encoding="utf-8",
    )
    unrelated_directory = tmp_path / "unrelated"
    unrelated_directory.mkdir()
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setitem(Settings.model_config, "env_file", temporary_env_file)
    monkeypatch.chdir(unrelated_directory)

    settings = Settings()

    assert settings.database_url.get_secret_value().endswith("@127.0.0.1:1/cwd")


def test_missing_database_url_has_clear_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None)

    assert "database_url" in str(error.value)
