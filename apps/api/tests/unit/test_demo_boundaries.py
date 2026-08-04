"""Focused Phase 2E tests for explicit seed authorization and read-only Demo traffic."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from creativedeploy_api.app_factory import create_app
from creativedeploy_api.core.config import Settings


def _oidc_settings(tmp_path: Path, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "test",
        "database_url": "postgresql+psycopg://test:test@127.0.0.1:1/test",
        "identity_provider": "oidc",
        "oidc_issuer": "http://127.0.0.1:18173",
        "oidc_discovery_url": "http://127.0.0.1:18173/.well-known/openid-configuration",
        "oidc_client_id": "phase2e-test-client",
        "oidc_client_secret": "synthetic-test-client-secret",
        "oidc_redirect_uri": "http://127.0.0.1:18173/api/v1/auth/callback",
        "image_storage_root": tmp_path / "private-images",
        "_env_file": None,
    }
    values.update(overrides)
    return Settings(**values)


def test_demo_seed_requires_explicit_flag(tmp_path: Path) -> None:
    settings = _oidc_settings(tmp_path)

    with pytest.raises(ValueError, match="PAINTPILOT_DEMO_SEED_ENABLED"):
        settings.require_demo_seed_identity()


def test_demo_seed_accepts_only_explicit_reserved_synthetic_identity(tmp_path: Path) -> None:
    settings = _oidc_settings(
        tmp_path,
        paintpilot_demo_seed_enabled=True,
        paintpilot_demo_seed_subject="paintpilot-public-demo-v1",
        paintpilot_demo_seed_display_name="PaintPilot Demo Visitor",
        paintpilot_demo_seed_email="public-demo@paintpilot.invalid",
    )

    assert settings.require_demo_seed_identity() == (
        "paintpilot-public-demo-v1",
        "PaintPilot Demo Visitor",
        "public-demo@paintpilot.invalid",
    )


def test_demo_seed_rejects_non_reserved_email(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match=r"reserved .invalid"):
        _oidc_settings(
            tmp_path,
            paintpilot_demo_seed_enabled=True,
            paintpilot_demo_seed_subject="paintpilot-public-demo-v1",
            paintpilot_demo_seed_display_name="PaintPilot Demo Visitor",
            paintpilot_demo_seed_email="person@example.com",
        )


def test_demo_read_only_rejects_unsafe_api_request_before_route_dependency(tmp_path: Path) -> None:
    settings = _oidc_settings(tmp_path, paintpilot_demo_read_only=True)

    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        response = client.post(
            "/api/v1/paint-projects",
            headers={"Idempotency-Key": "00000000-0000-4000-8000-000000000001"},
            json={"title": "must not reach service"},
        )

    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["error_code"] == "DEMO_READ_ONLY"
    assert response.json()["allowed_actions"] == ["inspect_demo_data", "run_demo_reset"]
