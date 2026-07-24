"""Integration test against the real Compose PostgreSQL service."""

import pytest
from fastapi.testclient import TestClient

from creativedeploy_api.app_factory import create_app
from creativedeploy_api.core.config import Settings

pytestmark = pytest.mark.integration


def test_database_readiness_with_compose_postgres() -> None:
    app = create_app(Settings())

    with TestClient(app) as client:
        response = client.get("/api/v1/health/ready")

    response_text = response.text.lower()
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["checks"]["database"]["status"] == "ok"
    assert "database_url" not in response_text
    assert "postgresql+psycopg" not in response_text
    assert "creativedeploy_dev_password" not in response_text
