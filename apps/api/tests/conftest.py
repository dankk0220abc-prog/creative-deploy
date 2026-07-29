"""Shared backend test fixtures."""

import pytest

from creativedeploy_api.core.config import Settings

TEST_DEMO_PRINCIPAL_ID = "test-demo-owner"
TEST_DEMO_PRINCIPAL_DISPLAY_NAME = "Test Demo Owner"


@pytest.fixture(autouse=True)
def explicit_test_runtime_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: object,
) -> None:
    """Supply per-test trusted config without changing or bypassing production validation."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("PAINTPILOT_DEMO_PRINCIPAL_ID", TEST_DEMO_PRINCIPAL_ID)
    monkeypatch.setenv(
        "PAINTPILOT_DEMO_PRINCIPAL_DISPLAY_NAME",
        TEST_DEMO_PRINCIPAL_DISPLAY_NAME,
    )
    monkeypatch.setenv("IMAGE_STORAGE_ROOT", str(tmp_path))


@pytest.fixture
def test_settings() -> Settings:
    """Return explicit trusted test config, never an HTTP or public-auth identity source."""
    return Settings(
        app_env="test",
        database_url="postgresql+psycopg://test:test@127.0.0.1:1/test",
        database_health_timeout_seconds=0.1,
        paintpilot_demo_principal_id=TEST_DEMO_PRINCIPAL_ID,
        paintpilot_demo_principal_display_name=TEST_DEMO_PRINCIPAL_DISPLAY_NAME,
        _env_file=None,
    )
