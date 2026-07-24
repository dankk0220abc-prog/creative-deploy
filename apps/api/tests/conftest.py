"""Shared backend test fixtures."""

import pytest

from creativedeploy_api.core.config import Settings


@pytest.fixture
def test_settings() -> Settings:
    """Return isolated settings that never connect unless a test requests readiness."""
    return Settings(
        app_env="test",
        database_url="postgresql+psycopg://test:test@127.0.0.1:1/test",
        database_health_timeout_seconds=0.1,
        _env_file=None,
    )
