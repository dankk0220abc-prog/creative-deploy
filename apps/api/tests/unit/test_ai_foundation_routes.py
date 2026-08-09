"""Feature-gate and route inventory tests for Phase 3A fixture APIs."""

from contextlib import AbstractContextManager
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from creativedeploy_api.api.dependencies import (
    get_ai_foundation_service,
    get_current_principal,
)
from creativedeploy_api.app_factory import create_app
from creativedeploy_api.core.config import Settings
from creativedeploy_api.core.principal import (
    AuthenticationMode,
    PrincipalContext,
    PrincipalType,
)
from creativedeploy_api.schemas.ai_foundation import (
    CapabilityListResponse,
    ModelListResponse,
    ProviderListResponse,
)
from creativedeploy_api.services.identity import AuthenticationRequiredError


class _CatalogService:
    async def list_providers(self) -> ProviderListResponse:
        return ProviderListResponse(items=[])

    async def list_models(self, _provider_key: str) -> ModelListResponse:
        return ModelListResponse(items=[])

    async def list_capabilities(self) -> CapabilityListResponse:
        return CapabilityListResponse(items=[])


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


def _enabled_catalog_client(
    tmp_path: Path, *, authenticated: bool
) -> AbstractContextManager[TestClient]:
    key_file = tmp_path / "fixture-root.key"
    if key_file.exists():
        key_file.chmod(0o600)
    key_file.write_bytes(bytes(range(32)))
    key_file.chmod(0o400)
    settings = Settings(
        app_env="test",
        database_url="postgresql+psycopg://test:test@127.0.0.1:1/test",
        paintpilot_demo_principal_id="test-owner",
        paintpilot_demo_principal_display_name="Test Owner",
        phase3a_fixture_enabled=True,
        credential_fixture_root_key_file=key_file,
        _env_file=None,
    )
    app = create_app(settings)
    app.dependency_overrides[get_ai_foundation_service] = lambda: _CatalogService()
    if authenticated:
        app.dependency_overrides[get_current_principal] = lambda: PrincipalContext(
            principal_id="catalog-user",
            principal_type=PrincipalType.HUMAN,
            display_name="Catalog User",
            authentication_mode=AuthenticationMode.OIDC_AUTHORIZATION_CODE,
            user_id=uuid4(),
        )
    else:

        async def authentication_required() -> PrincipalContext:
            raise AuthenticationRequiredError

        app.dependency_overrides[get_current_principal] = authentication_required
    return TestClient(app, raise_server_exceptions=False)


def test_catalog_routes_require_authenticated_principal(tmp_path: Path) -> None:
    for path in (
        "/api/v1/ai/providers",
        "/api/v1/ai/providers/fixture_local/models",
        "/api/v1/ai/capabilities",
    ):
        with _enabled_catalog_client(tmp_path, authenticated=False) as client:
            response = client.get(path)
        assert response.status_code == 401
        assert response.json()["error_code"] == "AUTHENTICATION_REQUIRED"


def test_catalog_routes_allow_authenticated_fixture_user(tmp_path: Path) -> None:
    for path in (
        "/api/v1/ai/providers",
        "/api/v1/ai/providers/fixture_local/models",
        "/api/v1/ai/capabilities",
    ):
        with _enabled_catalog_client(tmp_path, authenticated=True) as client:
            response = client.get(path)
        assert response.status_code == 200
        assert response.json() == {"items": []}
