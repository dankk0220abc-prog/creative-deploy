"""Feature-gate and route inventory tests for Phase 3A fixture APIs."""

from contextlib import AbstractContextManager

from fastapi.testclient import TestClient

from creativedeploy_api.app_factory import create_app
from creativedeploy_api.core.config import Settings


def _disabled_client() -> AbstractContextManager[TestClient]:
    settings = Settings(
        app_env="test",
        database_url="postgresql+psycopg://test:test@127.0.0.1:1/test",
        paintpilot_demo_principal_id="test-owner",
        paintpilot_demo_principal_display_name="Test Owner",
        phase3a_fixture_enabled=False,
        _env_file=None,
    )
    return TestClient(create_app(settings), raise_server_exceptions=False)


def test_feature_off_returns_controlled_not_found_without_database_or_key_access() -> None:
    with _disabled_client() as client:
        response = client.get("/api/v1/ai/providers")

    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["error_code"] == "PHASE3A_FIXTURE_UNAVAILABLE"
    assert response.json()["category"] == "NOT_FOUND"
    assert "credential" not in response.text.lower()
    assert "database_url" not in response.text.lower()


def test_openapi_contains_the_frozen_first_slice_route_inventory() -> None:
    with _disabled_client() as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = set(response.json()["paths"])
    assert {
        "/api/v1/ai/providers",
        "/api/v1/ai/providers/{provider_key}/models",
        "/api/v1/ai/capabilities",
        "/api/v1/ai/credentials/validate",
        "/api/v1/ai/credentials",
        "/api/v1/ai/credentials/{credential_id}/validate",
        "/api/v1/ai/credentials/{credential_id}/replace",
        "/api/v1/ai/credentials/{credential_id}/revoke",
        "/api/v1/ai/credentials/{credential_id}/grants",
        "/api/v1/ai/credentials/{credential_id}/grants/{project_id}",
        "/api/v1/ai/preferences",
        "/api/v1/paint-projects/{project_id}/ai-model-policy",
        "/api/v1/ai/invocations/preview",
        "/api/v1/ai/invocations",
        "/api/v1/ai/invocations/{invocation_id}",
        "/api/v1/ai/invocations/{invocation_id}/cancel",
        "/api/v1/ai/audit",
    }.issubset(paths)
