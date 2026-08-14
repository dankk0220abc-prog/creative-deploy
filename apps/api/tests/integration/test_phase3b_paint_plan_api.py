"""Real PostgreSQL/API closure for the offline Phase 3B Paint Plan foundation."""

from __future__ import annotations

import io
import json
import os
import socket
import subprocess
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from psycopg import sql
from sqlalchemy.engine import URL, make_url

from creativedeploy_api.ai.constants import (
    FIXTURE_PROVIDER_ID,
    FIXTURE_STRUCTURED_CAPABILITY_ID,
    FIXTURE_VISION_CAPABILITY_ID,
    FIXTURE_VISION_MODEL_ID,
)
from creativedeploy_api.ai.encryption import SecretBytes
from creativedeploy_api.ai.fixture_provider import FixtureInvocationResult
from creativedeploy_api.ai.provider_transport import (
    PreparedProviderRequest,
    ProviderContractError,
    ProviderWireResponse,
)
from creativedeploy_api.ai.zhipu_provider import (
    ZHIPU_GLM_5V_TURBO_MODEL,
    ZHIPU_GLM_52_MODEL,
    ZhipuHTTPTransport,
)
from creativedeploy_api.api.dependencies import get_current_principal
from creativedeploy_api.app_factory import create_app
from creativedeploy_api.core.config import Settings
from creativedeploy_api.core.principal import (
    AuthenticationMode,
    PrincipalContext,
    PrincipalType,
)

pytestmark = pytest.mark.integration

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
ALEMBIC_COMMAND = (
    "uv",
    "run",
    "--project",
    "apps/api",
    "alembic",
    "-c",
    "apps/api/alembic.ini",
)
SCHEMA_PREFIX = "phase3b_api_test_"
MARKER_TABLE = "fixture_ownership"
PAINT_PLAN_PROMPT_ID = "3b000000-0000-4000-8000-000000000301"
PAINT_PLAN_PROMPT_BODY = (
    "Analyze only the governed PaintPilot project images and approved semantic regions. "
    "Return exactly the paint-plan.v1 JSON schema. Produce one instruction for every "
    "paint region, produce no instruction for excluded regions, preserve every supplied "
    "region identifier, and state uncertainty without claiming verified colors, materials, "
    "safety, cost, or real-world results."
)
PAINT_PLAN_PROMPT_HASH = "8f946b8ae444637aa56b8624118f45b539eb314bf5bb6ed9013e7b89b0561de6"
ZHIPU_PROVIDER_ID = "5a000000-0000-4000-8000-000000000001"
ZHIPU_GLM_52_MODEL_ID = "5a000000-0000-4000-8000-000000000101"
ZHIPU_GLM_5V_TURBO_MODEL_ID = "5a000000-0000-4000-8000-000000000102"


class _OfflineZhipuTransport(ZhipuHTTPTransport):
    def __init__(self, expected_secret: bytes) -> None:
        super().__init__()
        self.expected_secret = expected_secret
        self.mode = "success"
        self.calls = 0

    async def execute(
        self,
        request: PreparedProviderRequest,
        credential: SecretBytes,
        *,
        live_gate_enabled: bool,
    ) -> ProviderWireResponse:
        assert live_gate_enabled is True
        assert credential.value == self.expected_secret
        assert request.model_id in {ZHIPU_GLM_52_MODEL, ZHIPU_GLM_5V_TURBO_MODEL}
        assert "body=[REDACTED]" in repr(request)
        self.calls += 1
        if self.mode == "outcome_unknown":
            raise ProviderContractError("outcome_unknown", dispatch_certainty="unknown")
        messages = request.body["messages"]
        assert isinstance(messages, list)
        user_message = messages[1]
        assert isinstance(user_message, dict)
        content = user_message["content"]
        if request.model_id == ZHIPU_GLM_5V_TURBO_MODEL:
            assert isinstance(content, list)
            assert len(content) == 4
            text_part = content[0]
            assert isinstance(text_part, dict)
            assert text_part["type"] == "text"
            text_content = text_part["text"]
            assert isinstance(text_content, str)
            for image_part in content[1:]:
                assert isinstance(image_part, dict)
                assert image_part["type"] == "image_url"
                image_url = image_part["image_url"]
                assert isinstance(image_url, dict)
                assert str(image_url["url"]).startswith("data:image/jpeg;base64,")
            context = json.loads(text_content.split("Governed context:\n", 1)[1])
            source = context["paint_plan_source"]
            paint_regions = [
                region for region in source["region_set"]["regions"] if region["kind"] == "paint"
            ]
            units = context["retrieved_context"]["units"]
            document = {
                "schema_version": "paint-plan.v1",
                "title": "Governed offline Zhipu paint plan",
                "overall_approach": (
                    "Work from the approved broad areas toward their exact boundaries while "
                    "keeping every excluded region unchanged."
                ),
                "instructions": [
                    {
                        "region_id": region["id"],
                        "stable_region_key": region["stable_region_key"],
                        "region_label": region["label"],
                        "target_color": "muted graphite",
                        "preparation": "Clean the governed area and test compatibility first.",
                        "base_coat": "Apply one thin, even base coat inside the approved boundary.",
                        "layer_strategy": (
                            "Build coverage with two thin layers after each layer cures."
                        ),
                        "edge_treatment": "Keep the approved silhouette crisp without crossing it.",
                        "lighting_guidance": "Recheck the surface under neutral, even lighting.",
                        "material_guidance": (
                            "Confirm material compatibility on an inconspicuous area."
                        ),
                        "warnings": ["Stop if the source surface differs from the reference."],
                        "confidence_ppm": 760_000,
                    }
                    for region in paint_regions
                ],
                "safety_notes": [
                    "Use ventilation and follow the coating manufacturer safety instructions."
                ],
                "knowledge_citations": [
                    {
                        "source_id": unit["source_id"],
                        "chunk_id": unit["chunk_id"],
                        "target_path": f"/safety_notes/{index}",
                    }
                    for index, unit in enumerate(units)
                ],
            }
            if self.mode == "paint_root_wrapper":
                document = {
                    "paint_plan": document,
                    "private_field": "private generated output must not persist",
                }
            return ProviderWireResponse(
                status_code=200,
                body={
                    "id": f"zhipu-offline-{self.calls}",
                    "model": ZHIPU_GLM_5V_TURBO_MODEL,
                    "choices": [
                        {"finish_reason": "stop", "message": {"content": json.dumps(document)}}
                    ],
                    "usage": {"prompt_tokens": 1_000, "completion_tokens": 500},
                },
                provider_request_id=None,
            )
        assert isinstance(content, str)
        context = json.loads(content.split("Governed context:\n", 1)[1])
        reading = context["reading"]
        cards = reading["cards"]
        units = context["retrieved_context"]["units"]
        unit_by_chunk_id = {unit["chunk_id"]: unit for unit in units}
        document = {
            "schema_version": "tarot-reading.v2",
            "generation_locale": reading["generation_locale"],
            "question_restatement": reading["question"],
            "summary": "The exact draw offers a conditional reflective sequence.",
            "positions": [
                {
                    "position_key": card["position_key"],
                    "card_id": card["card_id"],
                    "orientation": card["orientation"],
                    "headline": f"{card['position_key'].title()} reflection",
                    "contribution": "Use this exact card context as a reflective prompt.",
                }
                for card in cards
            ],
            "synthesis": "Past, present, and future form a conditional path, not a prediction.",
            "relationship_analysis": [
                {
                    "kind": "relationship",
                    "headline": "Relationship",
                    "content": "The three positions inform one another.",
                },
                {
                    "kind": "trend",
                    "headline": "Trend",
                    "content": "Attention moves from context toward choice.",
                },
                {
                    "kind": "tension",
                    "headline": "Tension",
                    "content": "Competing qualities invite deliberate balance.",
                },
                {
                    "kind": "turning_point",
                    "headline": "Turning point",
                    "content": "The present position is the practical hinge.",
                },
            ],
            "actionable_reflections": ["Name one small action that remains within your control."],
            "reflection_prompts": [
                "What pattern is ready to be reconsidered?",
                "What evidence would change your next step?",
            ],
            "knowledge_basis": [
                {
                    "card_id": card["card_id"],
                    "knowledge_id": unit_by_chunk_id[card["primary_knowledge_id"]]["chunk_id"],
                    "source_id": unit_by_chunk_id[card["primary_knowledge_id"]]["source_id"],
                    "source_title": unit_by_chunk_id[card["primary_knowledge_id"]]["source_title"],
                    "retrieval_mode": "repository_local_only",
                }
                for card in cards
            ],
            "uncertainty": "This is reflective guidance, not deterministic or professional advice.",
        }
        if self.mode == "schema_invalid":
            document["actionable_reflections"] = [
                {"reflection": "This object shape is forbidden by the application schema."}
            ]
        elif self.mode == "citation_invalid":
            document["knowledge_basis"][0]["knowledge_id"] = "hallucinated:chunk"
        return ProviderWireResponse(
            status_code=200,
            body={
                "id": f"zhipu-offline-{self.calls}",
                "model": ZHIPU_GLM_52_MODEL,
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": json.dumps(document)},
                    }
                ],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "completion_tokens_details": {"reasoning_tokens": 12},
                },
            },
            provider_request_id=None,
        )


def _connection_kwargs(database_url: URL) -> dict[str, object]:
    values: dict[str, object] = {
        "dbname": database_url.database,
        "user": database_url.username,
        "password": database_url.password,
        "host": database_url.host,
        "port": database_url.port,
    }
    options = database_url.query.get("options")
    if isinstance(options, str):
        values["options"] = options
    return values


def _schema_database_url(base_url: URL, schema_name: str) -> URL:
    return base_url.update_query_dict({"options": f"-csearch_path={schema_name}"})


def _run_alembic(database_url: URL, *arguments: str) -> None:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url.render_as_string(hide_password=False)
    completed = subprocess.run(
        [*ALEMBIC_COMMAND, *arguments],
        cwd=REPOSITORY_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert completed.returncode == 0, (
        f"Alembic {' '.join(arguments)} failed for isolated schema.\n"
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )


@pytest.fixture
def paint_plan_integration_settings(tmp_path: Path) -> Iterator[Settings]:
    development = Settings()
    base_url = make_url(development.database_url.get_secret_value())
    schema_name = f"{SCHEMA_PREFIX}{uuid.uuid4().hex}"
    ownership_token = uuid.uuid4().hex
    with psycopg.connect(**_connection_kwargs(base_url), autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema_name)))
        connection.execute(
            sql.SQL("CREATE TABLE {}.{} (token text PRIMARY KEY)").format(
                sql.Identifier(schema_name),
                sql.Identifier(MARKER_TABLE),
            )
        )
        connection.execute(
            sql.SQL("INSERT INTO {}.{} (token) VALUES (%s)").format(
                sql.Identifier(schema_name),
                sql.Identifier(MARKER_TABLE),
            ),
            (ownership_token,),
        )

    schema_url = _schema_database_url(base_url, schema_name)
    _run_alembic(schema_url, "upgrade", "head")
    root_key = tmp_path / "fixture-root.key"
    root_key.write_bytes(bytes(range(32)))
    root_key.chmod(0o400)
    settings = Settings(
        app_env="test",
        database_url=schema_url.render_as_string(hide_password=False),
        database_lock_timeout_ms=3_000,
        database_statement_timeout_ms=8_000,
        paintpilot_demo_principal_id=f"unused-phase3b-{uuid.uuid4().hex}",
        paintpilot_demo_principal_display_name="Unused Phase 3B Demo Principal",
        image_storage_root=tmp_path / "private-images",
        phase3a_fixture_enabled=True,
        phase3b_paint_plan_enabled=True,
        credential_fixture_root_key_file=root_key,
        _env_file=None,
    )
    try:
        yield settings
    finally:
        with psycopg.connect(**_connection_kwargs(base_url), autocommit=True) as connection:
            marker = connection.execute(
                sql.SQL("SELECT token FROM {}.{}").format(
                    sql.Identifier(schema_name),
                    sql.Identifier(MARKER_TABLE),
                )
            ).fetchone()
            assert marker == (ownership_token,)
            connection.execute(
                sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema_name))
            )


def _principal(*, label: str, user_id: uuid.UUID) -> PrincipalContext:
    return PrincipalContext(
        principal_id=f"phase3b-{label}-{uuid.uuid4().hex}",
        principal_type=PrincipalType.HUMAN,
        display_name=f"Phase 3B {label.title()}",
        authentication_mode=AuthenticationMode.OIDC_AUTHORIZATION_CODE,
        user_id=user_id,
    )


def _seed_users(settings: Settings, *principals: PrincipalContext) -> None:
    database_url = make_url(settings.database_url.get_secret_value())
    with psycopg.connect(**_connection_kwargs(database_url)) as connection:
        for principal in principals:
            assert principal.user_id is not None
            connection.execute(
                """
                INSERT INTO user_accounts (id, display_name, is_active)
                VALUES (%s, %s, true)
                """,
                (principal.user_id, principal.display_name),
            )


def _image_bytes(color: str) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (900, 768), color).save(output, format="JPEG", quality=90)
    return output.getvalue()


def _create_project(client: TestClient, title: str) -> dict[str, Any]:
    response = client.post(
        "/api/v1/paint-projects",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={"title": title, "description": "Synthetic governed Phase 3B source."},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _ready_image_set(client: TestClient, project_id: str) -> dict[str, Any]:
    for role, color in (
        ("primary_front", "#d05040"),
        ("reference_back", "#3060b0"),
        ("reference_angle", "#40a060"),
    ):
        response = client.post(
            f"/api/v1/paint-projects/{project_id}/images",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            data={
                "role": role,
                "source_type": "user_provided",
                "intended_usage": "private_project",
                "rights_attestation_confirmed": "true",
                "rights_attestation_version": "1",
            },
            files={"file": (f"{role}.jpg", _image_bytes(color), "image/jpeg")},
        )
        assert response.status_code == 201, response.text
    review = client.post(
        f"/api/v1/paint-projects/{project_id}/image-set/readiness-reviews",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={"verdict": "ready", "reason": None},
    )
    assert review.status_code == 201, review.text
    response = client.get(f"/api/v1/paint-projects/{project_id}/image-set")
    assert response.status_code == 200, response.text
    return response.json()


def _regions() -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for z_index, (kind, label, x, y) in enumerate(
        (
            ("paint", "hair", 50_000, 50_000),
            ("paint", "shirt", 300_000, 100_000),
            ("exclude", "background", 650_000, 600_000),
        )
    ):
        result.append(
            {
                "stable_region_key": str(uuid.uuid5(uuid.NAMESPACE_URL, f"phase3b:{kind}:{label}")),
                "kind": kind,
                "label": label,
                "z_index": z_index,
                "opacity_ppm": 500_000,
                "notes": f"Human {label} annotation.",
                "vertices": [
                    {"x_ppm": x, "y_ppm": y},
                    {"x_ppm": x + 180_000, "y_ppm": y},
                    {"x_ppm": x + 180_000, "y_ppm": y + 180_000},
                    {"x_ppm": x, "y_ppm": y + 180_000},
                ],
            }
        )
    return result


def _approved_region_set(client: TestClient, project_id: str) -> dict[str, Any]:
    saved = client.post(
        f"/api/v1/paint-projects/{project_id}/region-sets",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={"base_region_set_id": None, "base_version": None, "regions": _regions()},
    )
    assert saved.status_code == 201, saved.text
    submitted = client.post(
        f"/api/v1/paint-projects/{project_id}/region-sets/{saved.json()['id']}/submit",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={},
    )
    assert submitted.status_code == 201, submitted.text
    reviewed = client.post(
        f"/api/v1/paint-projects/{project_id}/region-sets/{submitted.json()['id']}/reviews",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={"verdict": "approved", "reason": None},
    )
    assert reviewed.status_code == 201, reviewed.text
    detail = client.get(f"/api/v1/paint-projects/{project_id}/region-sets/{submitted.json()['id']}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["effective_lifecycle"] == "approved"
    return detail.json()


def _configure_fixture_ai(
    client: TestClient,
    project_id: str,
) -> str:
    credential_response = client.post(
        "/api/v1/ai/credentials",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={
            "provider_key": "fixture_local",
            "alias": "Phase 3B offline fixture",
            "credential": f"fixture-sk-{uuid.uuid4().hex}",
            "confirm_save": True,
        },
    )
    assert credential_response.status_code == 201, credential_response.text
    credential = credential_response.json()
    grant = client.post(
        f"/api/v1/ai/credentials/{credential['id']}/grants",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={"project_id": project_id, "expected_credential_revision": credential["revision"]},
    )
    assert grant.status_code == 201, grant.text
    preference = client.patch(
        "/api/v1/ai/preferences",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={
            "enabled": True,
            "default_provider_definition_id": str(FIXTURE_PROVIDER_ID),
            "default_model_definition_id": str(FIXTURE_VISION_MODEL_ID),
            "default_credential_id": credential["id"],
            "timeout_ms": 30_000,
            "streaming_enabled": False,
            "cost_warning_minor_units": 5_000,
            "currency": "FIXTURE_CREDITS",
            "budget_per_invocation_minor_units": 10_000,
            "budget_cumulative_minor_units": 50_000,
            "budget_window_seconds": 86_400,
            "expected_revision": 0,
        },
    )
    assert preference.status_code == 200, preference.text
    policy = client.patch(
        f"/api/v1/paint-projects/{project_id}/ai-model-policy",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={
            "enabled": True,
            "default_provider_definition_id": str(FIXTURE_PROVIDER_ID),
            "default_model_definition_id": str(FIXTURE_VISION_MODEL_ID),
            "default_credential_id": credential["id"],
            "provider_allowlist": [str(FIXTURE_PROVIDER_ID)],
            "model_allowlist": [str(FIXTURE_VISION_MODEL_ID)],
            "capability_allowlist": [
                str(FIXTURE_VISION_CAPABILITY_ID),
                str(FIXTURE_STRUCTURED_CAPABILITY_ID),
            ],
            "credential_allowlist": [credential["id"]],
            "per_invocation_limit_minor_units": 10_000,
            "cumulative_limit_minor_units": 50_000,
            "budget_window_seconds": 86_400,
            "currency": "FIXTURE_CREDITS",
            "allow_unknown_cost": False,
            "allow_manual_model_id": False,
            "allow_fallback": False,
            "require_paid_call_confirmation": True,
            "expected_revision": 0,
        },
    )
    assert policy.status_code == 200, policy.text
    return credential["id"]


def _configure_zhipu_ai(
    client: TestClient,
    project_id: str,
    synthetic_secret: str,
) -> str:
    credential_response = client.post(
        "/api/v1/ai/credentials",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={
            "provider_key": "zhipu",
            "alias": "Synthetic Zhipu offline transport",
            "credential": synthetic_secret,
            "confirm_save": True,
        },
    )
    assert credential_response.status_code == 201, credential_response.text
    credential = credential_response.json()
    assert synthetic_secret not in credential_response.text
    grant = client.post(
        f"/api/v1/ai/credentials/{credential['id']}/grants",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={"project_id": project_id, "expected_credential_revision": credential["revision"]},
    )
    assert grant.status_code == 201, grant.text
    preference = client.patch(
        "/api/v1/ai/preferences",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={
            "enabled": True,
            "default_provider_definition_id": ZHIPU_PROVIDER_ID,
            "default_model_definition_id": ZHIPU_GLM_5V_TURBO_MODEL_ID,
            "default_credential_id": credential["id"],
            "timeout_ms": 60_000,
            "streaming_enabled": False,
            "cost_warning_minor_units": 1,
            "currency": "CNY",
            "budget_per_invocation_minor_units": 100,
            "budget_cumulative_minor_units": 100,
            "budget_window_seconds": 86_400,
            "expected_revision": 0,
        },
    )
    assert preference.status_code == 200, preference.text
    policy = client.patch(
        f"/api/v1/paint-projects/{project_id}/ai-model-policy",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={
            "enabled": True,
            "default_provider_definition_id": ZHIPU_PROVIDER_ID,
            "default_model_definition_id": ZHIPU_GLM_5V_TURBO_MODEL_ID,
            "default_credential_id": credential["id"],
            "provider_allowlist": [ZHIPU_PROVIDER_ID],
            "model_allowlist": [ZHIPU_GLM_5V_TURBO_MODEL_ID],
            "capability_allowlist": [
                str(FIXTURE_VISION_CAPABILITY_ID),
                str(FIXTURE_STRUCTURED_CAPABILITY_ID),
            ],
            "credential_allowlist": [credential["id"]],
            "per_invocation_limit_minor_units": 100,
            "cumulative_limit_minor_units": 100,
            "budget_window_seconds": 86_400,
            "currency": "CNY",
            "allow_unknown_cost": False,
            "allow_manual_model_id": False,
            "allow_fallback": False,
            "require_paid_call_confirmation": True,
            "expected_revision": 0,
        },
    )
    assert policy.status_code == 200, policy.text
    return credential["id"]


def _selection(image_set: dict[str, Any], region_set: dict[str, Any], credential_id: str) -> dict:
    return {
        "image_set_fingerprint": image_set["image_set_fingerprint"],
        "region_set_id": region_set["id"],
        "provider_definition_id": str(FIXTURE_PROVIDER_ID),
        "model_definition_id": str(FIXTURE_VISION_MODEL_ID),
        "credential_id": credential_id,
        "generation_locale": "en-US",
        "intent": "Preserve the approved silhouette and make layer order explicit.",
    }


def _edited_document(document: dict[str, Any]) -> dict[str, Any]:
    edited = {
        **document,
        "title": "Human-reviewed deterministic Paint Plan",
        "overall_approach": f"{document['overall_approach']} Verify each edge before cure.",
        "instructions": [dict(item) for item in document["instructions"]],
        "safety_notes": list(document["safety_notes"]),
    }
    edited["instructions"][0]["warnings"] = [
        *edited["instructions"][0]["warnings"],
        "Human edit: verify coverage under neutral light.",
    ]
    return edited


def test_phase3b_paint_plan_api_governance_review_budget_and_lineage(
    paint_plan_integration_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = paint_plan_integration_settings
    owner = _principal(label="owner", user_id=uuid.uuid4())
    reviewer = _principal(label="reviewer", user_id=uuid.uuid4())
    outsider = _principal(label="outsider", user_id=uuid.uuid4())
    _seed_users(settings, owner, reviewer, outsider)

    app = create_app(settings)
    current_principal = owner

    async def principal_override() -> PrincipalContext:
        return current_principal

    app.dependency_overrides[get_current_principal] = principal_override
    with TestClient(app) as client:
        project = _create_project(client, "Phase 3B governed fixture plan")
        project_id = project["id"]
        image_set = _ready_image_set(client, project_id)
        region_set = _approved_region_set(client, project_id)
        credential_id = _configure_fixture_ai(client, project_id)
        selection = _selection(image_set, region_set, credential_id)

        public_paint_plan_payload = {
            "product_space": "paintpilot",
            "project_id": project_id,
            "invocation_family": "paint_plan_generation",
            "provider_definition_id": str(FIXTURE_PROVIDER_ID),
            "model_definition_id": str(FIXTURE_VISION_MODEL_ID),
            "credential_id": credential_id,
            "requested_capabilities": ["vision_understanding", "structured_output"],
            "artifacts": [],
            "payload": {
                "prompt_label": "client-controlled-generic-prompt",
                "fixture_input": "client-controlled",
                "scenario": "success",
            },
            "confirm_fixture_use": True,
        }
        public_preview = client.post(
            "/api/v1/ai/invocations/preview",
            json=public_paint_plan_payload,
        )
        assert public_preview.status_code == 409, public_preview.text
        assert public_preview.json()["error_code"] == "INVOCATION_ADMISSION_REJECTED"
        public_create = client.post(
            "/api/v1/ai/invocations",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json={
                **public_paint_plan_payload,
                "max_attempts": 1,
                "total_elapsed_time_limit_ms": 30_000,
            },
        )
        assert public_create.status_code == 409, public_create.text
        assert public_create.json()["error_code"] == "INVOCATION_ADMISSION_REJECTED"

        initial_workbench = client.get(f"/api/v1/paint-projects/{project_id}/paint-plans/workbench")
        assert initial_workbench.status_code == 200, initial_workbench.text
        workbench_payload = initial_workbench.json()
        client_supplied_paint_input = {
            "image_set_fingerprint": image_set["image_set_fingerprint"],
            "readiness_review_id": image_set["latest_review"]["id"],
            "readiness_review_version": image_set["latest_review"]["version"],
            "image_assets": workbench_payload["image_assets"],
            "region_set": workbench_payload["region_set"],
            "prompt_template_id": PAINT_PLAN_PROMPT_ID,
            "prompt_template_key": "paint-plan",
            "prompt_template_version": 1,
            "prompt_template_body": PAINT_PLAN_PROMPT_BODY,
            "prompt_content_hash": PAINT_PLAN_PROMPT_HASH,
            "response_schema_version": "paint-plan.v1",
            "intent": "Client must never define governed provenance.",
            "regeneration_of_plan_id": None,
        }
        public_embedded_input = {
            **public_paint_plan_payload,
            "invocation_family": "fixture_invocation",
            "payload": {
                "prompt_label": "paint-plan.v1",
                "fixture_input": "governed-server-snapshot",
                "scenario": "success",
                "paint_plan_input": client_supplied_paint_input,
            },
        }
        embedded_preview = client.post(
            "/api/v1/ai/invocations/preview",
            json=public_embedded_input,
        )
        assert embedded_preview.status_code == 422, embedded_preview.text
        assert embedded_preview.json()["error_code"] == "REQUEST_VALIDATION_FAILED"
        embedded_create = client.post(
            "/api/v1/ai/invocations",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json={
                **public_embedded_input,
                "max_attempts": 1,
                "total_elapsed_time_limit_ms": 30_000,
            },
        )
        assert embedded_create.status_code == 422, embedded_create.text
        assert embedded_create.json()["error_code"] == "REQUEST_VALIDATION_FAILED"

        preview = client.post(
            f"/api/v1/paint-projects/{project_id}/paint-plans/preview",
            json=selection,
        )
        assert preview.status_code == 200, preview.text
        assert preview.json() == {
            "admissible": True,
            "execution_mode": "fixture_available",
            "provider_key": "fixture_local",
            "model_id": "fixture-vision-v1",
            "source_ready": True,
            "estimated_cost_minor_units": preview.json()["estimated_cost_minor_units"],
            "currency": "FIXTURE_CREDITS",
            "estimate_status": "estimated",
            "live_execution_authorized": False,
            "blockers": [],
        }
        assert 0 < preview.json()["estimated_cost_minor_units"] <= 10_000

        unsupported_locale = client.post(
            f"/api/v1/paint-projects/{project_id}/paint-plans/generate",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json={
                **selection,
                "generation_locale": "fr-FR",
                "confirm_generation": True,
                "max_attempts": 1,
            },
        )
        assert unsupported_locale.status_code == 422, unsupported_locale.text
        assert unsupported_locale.json()["error_code"] == "REQUEST_VALIDATION_FAILED"
        after_invalid_locale = client.get(
            f"/api/v1/paint-projects/{project_id}/paint-plans/workbench"
        )
        assert after_invalid_locale.status_code == 200
        assert after_invalid_locale.json()["current_plan"] is None

        adapter = app.state.fixture_provider_adapter
        original_invoke: Callable[..., Any] = adapter.invoke
        invocation_calls = 0

        def no_network_fixture_invoke(*args: object, **kwargs: object) -> Any:
            nonlocal invocation_calls
            invocation_calls += 1

            def forbid_socket(*_args: object, **_kwargs: object) -> None:
                raise AssertionError("offline Paint Plan fixture attempted network construction")

            with monkeypatch.context() as context:
                context.setattr(socket, "socket", forbid_socket)
                return original_invoke(*args, **kwargs)

        monkeypatch.setattr(adapter, "invoke", no_network_fixture_invoke)
        invalid_output_marker = "raw-provider-output-must-never-persist"
        invalid_key = uuid.uuid4()

        def malformed_fixture_invoke(*_args: object, **_kwargs: object) -> FixtureInvocationResult:
            nonlocal invocation_calls
            invocation_calls += 1
            return FixtureInvocationResult(
                output={
                    "schema_version": "paint-plan.v1",
                    "raw_provider_response": invalid_output_marker,
                },
                input_units=31,
                output_units=7,
                cost_minor_units=38,
            )

        with monkeypatch.context() as context:
            context.setattr(adapter, "invoke", malformed_fixture_invoke)
            invalid_response = client.post(
                f"/api/v1/paint-projects/{project_id}/paint-plans/generate",
                headers={"Idempotency-Key": str(invalid_key)},
                json={**selection, "confirm_generation": True, "max_attempts": 1},
            )
        assert invalid_response.status_code == 502, invalid_response.text
        assert invalid_response.json()["error_code"] == "PAINT_PLAN_OUTPUT_INVALID"
        assert invalid_output_marker not in invalid_response.text

        generate_key = uuid.uuid4()
        generate_payload = {**selection, "confirm_generation": True, "max_attempts": 1}
        generated_response = client.post(
            f"/api/v1/paint-projects/{project_id}/paint-plans/generate",
            headers={"Idempotency-Key": str(generate_key)},
            json=generate_payload,
        )
        assert generated_response.status_code == 201, generated_response.text
        generated = generated_response.json()
        assert invocation_calls == 2
        assert generated["revision_kind"] == "generated"
        assert generated["lifecycle"] == "generated"
        assert generated["lineage_id"] == generated["id"]
        assert generated["source_image_set_fingerprint"] == image_set["image_set_fingerprint"]
        assert generated["source_region_set_id"] == region_set["id"]
        assert generated["requested_by_user_id"] == str(owner.user_id)
        assert generated["generation_locale"] == "en-US"
        assert generated["invocation_created_at"]
        assert len(generated["document"]["instructions"]) == 2
        assert {item["region_label"] for item in generated["document"]["instructions"]} == {
            "hair",
            "shirt",
        }

        edit_key = uuid.uuid4()
        edit_payload = {
            "expected_current_plan_id": generated["id"],
            "expected_current_version": generated["version"],
            "document": _edited_document(generated["document"]),
        }
        edit_response = client.post(
            f"/api/v1/paint-projects/{project_id}/paint-plans/{generated['id']}/edits",
            headers={"Idempotency-Key": str(edit_key)},
            json=edit_payload,
        )
        assert edit_response.status_code == 201, edit_response.text
        edited = edit_response.json()
        assert edited["revision_kind"] == "edited"
        assert edited["lineage_id"] == generated["lineage_id"]
        assert edited["parent_plan_id"] == generated["id"]
        assert edited["lifecycle"] == "edited"

        generated_replay = client.post(
            f"/api/v1/paint-projects/{project_id}/paint-plans/generate",
            headers={"Idempotency-Key": str(generate_key)},
            json=generate_payload,
        )
        assert generated_replay.status_code == 201, generated_replay.text
        generated_replayed = generated_replay.json()
        assert generated_replayed["id"] == generated["id"]
        assert generated_replayed["lifecycle"] == "superseded"
        assert generated_replayed["effective_lifecycle"] == "superseded"
        assert generated_replayed["approval_valid"] is False
        assert generated_replayed["allowed_actions"] == []
        assert invocation_calls == 2
        generated_conflict = client.post(
            f"/api/v1/paint-projects/{project_id}/paint-plans/generate",
            headers={"Idempotency-Key": str(generate_key)},
            json={**generate_payload, "intent": "Different intent under the same key."},
        )
        assert generated_conflict.status_code == 409
        assert generated_conflict.json()["error_code"] == "IDEMPOTENCY_KEY_REUSED"
        locale_conflict = client.post(
            f"/api/v1/paint-projects/{project_id}/paint-plans/generate",
            headers={"Idempotency-Key": str(generate_key)},
            json={**generate_payload, "generation_locale": "zh-CN"},
        )
        assert locale_conflict.status_code == 409
        assert locale_conflict.json()["error_code"] == "IDEMPOTENCY_KEY_REUSED"

        stale_revision = client.post(
            f"/api/v1/paint-projects/{project_id}/paint-plans/{edited['id']}/submit",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json={
                "expected_current_plan_id": edited["id"],
                "expected_current_version": generated["version"],
            },
        )
        assert stale_revision.status_code == 409
        assert stale_revision.json()["error_code"] == "PAINT_PLAN_LIFECYCLE_CONFLICT"

        submitted_response = client.post(
            f"/api/v1/paint-projects/{project_id}/paint-plans/{edited['id']}/submit",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json={
                "expected_current_plan_id": edited["id"],
                "expected_current_version": edited["version"],
            },
        )
        assert submitted_response.status_code == 201, submitted_response.text
        submitted = submitted_response.json()
        assert submitted["lifecycle"] == "under_review"

        database_url = make_url(settings.database_url.get_secret_value())
        assert owner.user_id is not None and reviewer.user_id is not None
        with psycopg.connect(**_connection_kwargs(database_url)) as connection:
            connection.execute(
                """
                INSERT INTO project_memberships (
                    id, paint_project_id, user_id, role, assigned_by_user_id
                ) VALUES (%s, %s, %s, 'reviewer', %s)
                """,
                (uuid.uuid4(), project_id, reviewer.user_id, owner.user_id),
            )

        current_principal = reviewer
        approve_key = uuid.uuid4()
        approved_response = client.post(
            f"/api/v1/paint-projects/{project_id}/paint-plans/{edited['id']}/approve",
            headers={"Idempotency-Key": str(approve_key)},
            json={
                "expected_current_plan_id": edited["id"],
                "expected_current_version": edited["version"],
                "reason": "Exact revision and governed source verified.",
            },
        )
        assert approved_response.status_code == 201, approved_response.text
        approved = approved_response.json()
        assert approved["effective_lifecycle"] == "approved"
        assert approved["approval_valid"] is True
        assert approved["latest_review"]["actor_id"] == reviewer.principal_id

        current_principal = owner
        edit_replay = client.post(
            f"/api/v1/paint-projects/{project_id}/paint-plans/{generated['id']}/edits",
            headers={"Idempotency-Key": str(edit_key)},
            json=edit_payload,
        )
        assert edit_replay.status_code == 201, edit_replay.text
        edit_replayed = edit_replay.json()
        assert edit_replayed["id"] == edited["id"]
        assert edit_replayed["effective_lifecycle"] == "approved"
        assert edit_replayed["approval_valid"] is True
        assert edit_replayed["latest_review"]["action"] == "approve"
        conflicting_edit_payload = {
            **edit_payload,
            "document": {
                **edit_payload["document"],
                "title": "A conflicting edit under the same key",
            },
        }
        edit_conflict = client.post(
            f"/api/v1/paint-projects/{project_id}/paint-plans/{generated['id']}/edits",
            headers={"Idempotency-Key": str(edit_key)},
            json=conflicting_edit_payload,
        )
        assert edit_conflict.status_code == 409
        assert edit_conflict.json()["error_code"] == "IDEMPOTENCY_KEY_REUSED"
        history_after_edit_replay = client.get(f"/api/v1/paint-projects/{project_id}/paint-plans")
        assert history_after_edit_replay.status_code == 200, history_after_edit_replay.text
        assert [item["id"] for item in history_after_edit_replay.json()["items"]] == [
            edited["id"],
            generated["id"],
        ]

        regeneration_key = uuid.uuid4()
        regeneration_payload = {
            **selection,
            "generation_locale": "zh-CN",
            "expected_current_plan_id": edited["id"],
            "expected_current_version": edited["version"],
            "confirm_generation": True,
            "max_attempts": 1,
        }
        regeneration_response = client.post(
            f"/api/v1/paint-projects/{project_id}/paint-plans/{edited['id']}/regenerate",
            headers={"Idempotency-Key": str(regeneration_key)},
            json=regeneration_payload,
        )
        assert regeneration_response.status_code == 201, regeneration_response.text
        regenerated = regeneration_response.json()
        assert invocation_calls == 3
        assert regenerated["revision_kind"] == "regenerated"
        assert regenerated["lineage_id"] == regenerated["id"]
        assert regenerated["lineage_id"] != edited["lineage_id"]
        assert regenerated["parent_plan_id"] == edited["id"]
        assert regenerated["generation_locale"] == "zh-CN"
        assert regenerated["document"]["title"].startswith("受管 Fixture 涂装方案")
        assert "排除区域" in regenerated["document"]["overall_approach"]
        assert all(
            item["preparation"] == "清洁表面，并均匀轻磨以提高附着力。"  # noqa: RUF001
            for item in regenerated["document"]["instructions"]
        )
        regenerated_replay = client.post(
            f"/api/v1/paint-projects/{project_id}/paint-plans/{edited['id']}/regenerate",
            headers={"Idempotency-Key": str(regeneration_key)},
            json=regeneration_payload,
        )
        assert regenerated_replay.status_code == 201, regenerated_replay.text
        assert regenerated_replay.json() == regenerated
        assert invocation_calls == 3
        regenerated_conflict = client.post(
            f"/api/v1/paint-projects/{project_id}/paint-plans/{edited['id']}/regenerate",
            headers={"Idempotency-Key": str(regeneration_key)},
            json={**regeneration_payload, "intent": "Conflicting regeneration intent."},
        )
        assert regenerated_conflict.status_code == 409
        assert regenerated_conflict.json()["error_code"] == "IDEMPOTENCY_KEY_REUSED"

        history = client.get(f"/api/v1/paint-projects/{project_id}/paint-plans")
        assert history.status_code == 200, history.text
        history_items = history.json()["items"]
        assert [item["version"] for item in history_items] == [
            regenerated["version"],
            edited["version"],
            generated["version"],
        ]
        assert [item["effective_lifecycle"] for item in history_items] == [
            "generated",
            "superseded",
            "superseded",
        ]
        assert [item["generation_locale"] for item in history_items] == [
            "zh-CN",
            "en-US",
            "en-US",
        ]

        current_principal = outsider
        hidden = client.get(f"/api/v1/paint-projects/{project_id}/paint-plans")
        assert hidden.status_code == 404
        assert hidden.json()["error_code"] == "PAINT_PROJECT_NOT_FOUND"

        current_principal = owner
        unconfigured_project = _create_project(client, "No project Grant or policy")
        unconfigured_images = _ready_image_set(client, unconfigured_project["id"])
        unconfigured_regions = _approved_region_set(client, unconfigured_project["id"])
        unconfigured_selection = _selection(
            unconfigured_images,
            unconfigured_regions,
            credential_id,
        )
        no_policy_preview = client.post(
            f"/api/v1/paint-projects/{unconfigured_project['id']}/paint-plans/preview",
            json=unconfigured_selection,
        )
        assert no_policy_preview.status_code == 200, no_policy_preview.text
        assert no_policy_preview.json()["admissible"] is False
        assert "invocation_admission_rejected" in no_policy_preview.json()["blockers"]
        no_policy_generate = client.post(
            f"/api/v1/paint-projects/{unconfigured_project['id']}/paint-plans/generate",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json={**unconfigured_selection, "confirm_generation": True, "max_attempts": 1},
        )
        assert no_policy_generate.status_code == 404
        assert no_policy_generate.json()["error_code"] == "AI_RESOURCE_NOT_FOUND"
        assert invocation_calls == 3

        replacement = client.post(
            f"/api/v1/paint-projects/{project_id}/images",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            data={
                "role": "reference_angle",
                "source_type": "user_provided",
                "intended_usage": "private_project",
                "rights_attestation_confirmed": "true",
                "rights_attestation_version": "1",
            },
            files={
                "file": (
                    "replacement.jpg",
                    _image_bytes("#8020a0"),
                    "image/jpeg",
                )
            },
        )
        assert replacement.status_code == 201, replacement.text
        stale_generate = client.post(
            f"/api/v1/paint-projects/{project_id}/paint-plans/{regenerated['id']}/regenerate",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json={
                **selection,
                "expected_current_plan_id": regenerated["id"],
                "expected_current_version": regenerated["version"],
                "confirm_generation": True,
                "max_attempts": 1,
            },
        )
        assert stale_generate.status_code == 409
        assert stale_generate.json()["error_code"] == "PAINT_PLAN_SOURCE_NOT_READY"
        assert invocation_calls == 3

        drifted_regeneration_replay = client.post(
            f"/api/v1/paint-projects/{project_id}/paint-plans/{edited['id']}/regenerate",
            headers={"Idempotency-Key": str(regeneration_key)},
            json=regeneration_payload,
        )
        assert drifted_regeneration_replay.status_code == 201
        drifted_replayed = drifted_regeneration_replay.json()
        assert drifted_replayed["id"] == regenerated["id"]
        assert drifted_replayed["stale"] is True
        assert drifted_replayed["effective_lifecycle"] == "superseded"
        assert drifted_replayed["approval_valid"] is False
        assert drifted_replayed["allowed_actions"] == []
        assert invocation_calls == 3

        current_principal = reviewer
        stale_approval_replay = client.post(
            f"/api/v1/paint-projects/{project_id}/paint-plans/{edited['id']}/approve",
            headers={"Idempotency-Key": str(approve_key)},
            json={
                "expected_current_plan_id": edited["id"],
                "expected_current_version": edited["version"],
                "reason": "Exact revision and governed source verified.",
            },
        )
        assert stale_approval_replay.status_code == 201
        stale_approval = stale_approval_replay.json()
        assert stale_approval["id"] == edited["id"]
        assert stale_approval["lifecycle"] == "superseded"
        assert stale_approval["effective_lifecycle"] == "superseded"
        assert stale_approval["approval_valid"] is False
        assert stale_approval["latest_review"]["action"] == "approve"
        current_principal = owner

        with psycopg.connect(**_connection_kwargs(database_url)) as connection:
            connection.execute(
                "UPDATE paint_projects SET status = 'ABANDONED' WHERE id = %s",
                (project_id,),
            )
        abandoned_workbench = client.get(
            f"/api/v1/paint-projects/{project_id}/paint-plans/workbench"
        )
        assert abandoned_workbench.status_code == 200, abandoned_workbench.text
        assert "project_abandoned" in abandoned_workbench.json()["blockers"]
        assert "preview" not in abandoned_workbench.json()["allowed_actions"]
        abandoned_replay = client.post(
            f"/api/v1/paint-projects/{project_id}/paint-plans/{edited['id']}/regenerate",
            headers={"Idempotency-Key": str(regeneration_key)},
            json=regeneration_payload,
        )
        assert abandoned_replay.status_code == 404
        assert abandoned_replay.json()["error_code"] == "PAINT_PROJECT_NOT_FOUND"

    database_url = make_url(settings.database_url.get_secret_value())
    with psycopg.connect(**_connection_kwargs(database_url)) as connection:
        invocation_rows = connection.execute(
            """
            SELECT id, status, invocation_family, final_attempt_id
            FROM invocation_requests
            WHERE project_id = %s
            ORDER BY created_at
            """,
            (project_id,),
        ).fetchall()
        assert len(invocation_rows) == 3
        assert invocation_rows[0][1:4] == ("failed", "paint_plan_generation", None)
        assert all(
            row[1:3] == ("succeeded", "paint_plan_generation") for row in invocation_rows[1:]
        )
        assert all(row[3] is not None for row in invocation_rows[1:])
        locale_rows = connection.execute(
            """
            SELECT safe_payload->'paint_plan_provenance'->>'generation_locale'
            FROM invocation_requests
            WHERE project_id = %s
            ORDER BY created_at
            """,
            (project_id,),
        ).fetchall()
        assert [row[0] for row in locale_rows] == ["en-US", "en-US", "zh-CN"]
        attempt_rows = connection.execute(
            """
            SELECT invocation_id, status, provider_key, model_id
            FROM invocation_attempts
            WHERE invocation_id = ANY(%s)
            ORDER BY invocation_id, attempt_number
            """,
            ([row[0] for row in invocation_rows],),
        ).fetchall()
        assert len(attempt_rows) == 3
        attempts_by_invocation = {row[0]: row for row in attempt_rows}
        assert attempts_by_invocation[invocation_rows[0][0]][1:4] == (
            "failed",
            "fixture_local",
            "fixture-vision-v1",
        )
        assert all(
            attempts_by_invocation[row[0]][1:4]
            == ("succeeded", "fixture_local", "fixture-vision-v1")
            for row in invocation_rows[1:]
        )
        assert connection.execute(
            "SELECT count(*) FROM ai_usage_ledger WHERE invocation_id = ANY(%s)",
            ([row[0] for row in invocation_rows],),
        ).fetchone() == (3,)
        assert connection.execute(
            "SELECT count(*) FROM ai_cost_ledger WHERE invocation_id = ANY(%s)",
            ([row[0] for row in invocation_rows],),
        ).fetchone() == (3,)
        settled = connection.execute(
            """
            SELECT count(*)
            FROM budget_reservations
            WHERE invocation_id = ANY(%s) AND state = 'settled'
            """,
            ([row[0] for row in invocation_rows],),
        ).fetchone()
        assert settled == (3,)
        invalid_persistence = connection.execute(
            """
            SELECT i.output_reference, a.output_reference, a.final_error_category,
                   r.state, u.input_units, u.output_units, c.amount_minor_units
            FROM invocation_requests AS i
            JOIN invocation_attempts AS a ON a.invocation_id = i.id
            JOIN budget_reservations AS r ON r.attempt_id = a.id
            JOIN ai_usage_ledger AS u ON u.attempt_id = a.id
            JOIN ai_cost_ledger AS c ON c.attempt_id = a.id
            WHERE i.id = %s
            """,
            (invocation_rows[0][0],),
        ).fetchone()
        assert invalid_persistence == (None, None, "schema_invalid", "settled", 31, 7, 38)
        assert (
            invalid_output_marker
            not in connection.execute(
                """
            SELECT concat_ws(' ', i.safe_payload::text, i.output_reference::text,
                                    a.safe_provider_metadata::text, a.output_reference::text)
            FROM invocation_requests AS i
            JOIN invocation_attempts AS a ON a.invocation_id = i.id
            WHERE i.id = %s
            """,
                (invocation_rows[0][0],),
            ).fetchone()[0]
        )
        plan_links = connection.execute(
            """
            SELECT source_invocation_id, source_attempt_id, revision_kind
            FROM paint_plans
            WHERE paint_project_id = %s
            ORDER BY version
            """,
            (project_id,),
        ).fetchall()
        assert [row[2] for row in plan_links] == ["generated", "edited", "regenerated"]
        assert plan_links[0][0:2] == (invocation_rows[1][0], invocation_rows[1][3])
        assert plan_links[1][0:2] == plan_links[0][0:2]
        assert plan_links[2][0:2] == (invocation_rows[2][0], invocation_rows[2][3])

    with psycopg.connect(**_connection_kwargs(database_url), autocommit=True) as connection:
        for invocation_id in (invocation_rows[0][0], invocation_rows[1][0]):
            with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
                connection.execute(
                    """
                    UPDATE invocation_requests
                    SET safe_payload = safe_payload || '{"tampered": true}'::jsonb
                    WHERE id = %s
                    """,
                    (invocation_id,),
                )
        with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
            connection.execute(
                """
                UPDATE invocation_requests
                SET invocation_family = 'fixture_invocation'
                WHERE id = %s
                """,
                (invocation_rows[0][0],),
            )
        with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
            connection.execute(
                """
                UPDATE invocation_requests
                SET requesting_user_id = %s, created_at = created_at - interval '1 second'
                WHERE id = %s
                """,
                (reviewer.user_id, invocation_rows[1][0]),
            )
        with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
            connection.execute(
                """
                UPDATE provider_definitions
                SET display_name = display_name || ' tampered'
                WHERE id = '3b000000-0000-4000-8000-000000000001'::uuid
                """
            )


def test_zhipu_arcana_offline_live_coordinator_budget_isolation_and_unknown_outcome(
    paint_plan_integration_settings: Settings,
) -> None:
    settings = paint_plan_integration_settings.model_copy(update={"zhipu_live_enabled": True})
    owner = _principal(label="zhipu-owner", user_id=uuid.uuid4())
    other = _principal(label="zhipu-other", user_id=uuid.uuid4())
    _seed_users(settings, owner, other)
    synthetic_secret = f"zhipu-synthetic-{uuid.uuid4().hex}".encode()
    transport = _OfflineZhipuTransport(synthetic_secret)
    app = create_app(settings)
    app.state.zhipu_transport = transport
    active_principal = [owner]
    app.dependency_overrides[get_current_principal] = lambda: active_principal[0]

    def start_draw(client: TestClient) -> str:
        created = client.post(
            "/api/v1/arcana/readings",
            json={
                "question": "What practical choice deserves calm attention?",
                "generation_locale": "en-US",
            },
        )
        assert created.status_code == 201, created.text
        reading_id = created.json()["id"]
        drawn = client.post(f"/api/v1/arcana/readings/{reading_id}/draw")
        assert drawn.status_code == 200, drawn.text
        return str(reading_id)

    with TestClient(app) as client:
        providers = client.get("/api/v1/ai/providers")
        assert providers.status_code == 200
        zhipu = next(item for item in providers.json()["items"] if item["provider_key"] == "zhipu")
        assert zhipu == {
            **zhipu,
            "id": ZHIPU_PROVIDER_ID,
            "real_model_calls": True,
            "real_cost": True,
            "local_only": False,
        }
        models = client.get("/api/v1/ai/providers/zhipu/models")
        assert models.status_code == 200
        glm_52 = next(item for item in models.json()["items"] if item["model_id"] == "glm-5.2")
        assert glm_52["id"] == ZHIPU_GLM_52_MODEL_ID
        assert glm_52["pricing_currency"] == "CNY"

        validated = client.post(
            "/api/v1/ai/credentials/validate",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json={"provider_key": "zhipu", "credential": synthetic_secret.decode()},
        )
        assert validated.status_code == 200, validated.text
        assert validated.json() == {
            "provider_key": "zhipu",
            "valid": True,
            "validation_status": "live_validation_not_authorized",
            "message_code": "SECURE_INPUT_ACCEPTED_LIVE_VALIDATION_PENDING",
            "fixture": False,
            "local_only": False,
            "persisted": False,
        }
        created_credential = client.post(
            "/api/v1/ai/credentials",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json={
                "provider_key": "zhipu",
                "alias": "Synthetic Zhipu offline transport",
                "credential": synthetic_secret.decode(),
                "confirm_save": True,
            },
        )
        assert created_credential.status_code == 201, created_credential.text
        credential = created_credential.json()
        assert synthetic_secret.decode() not in created_credential.text

        def save_preference(*, revision: int, cumulative_limit: int) -> None:
            response = client.patch(
                "/api/v1/ai/preferences",
                headers={"Idempotency-Key": str(uuid.uuid4())},
                json={
                    "enabled": True,
                    "default_provider_definition_id": ZHIPU_PROVIDER_ID,
                    "default_model_definition_id": ZHIPU_GLM_52_MODEL_ID,
                    "default_credential_id": credential["id"],
                    "timeout_ms": 60_000,
                    "streaming_enabled": False,
                    "cost_warning_minor_units": 1,
                    "currency": "CNY",
                    "budget_per_invocation_minor_units": cumulative_limit,
                    "budget_cumulative_minor_units": cumulative_limit,
                    "budget_window_seconds": 86_400,
                    "expected_revision": revision,
                },
            )
            assert response.status_code == 200, response.text

        save_preference(revision=0, cumulative_limit=1)
        capped_reading = start_draw(client)
        capped = client.post(
            f"/api/v1/arcana/readings/{capped_reading}/interpret-live",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json={
                "provider_definition_id": ZHIPU_PROVIDER_ID,
                "model_definition_id": ZHIPU_GLM_52_MODEL_ID,
                "credential_id": credential["id"],
                "confirm_paid_live_call": True,
            },
        )
        assert capped.status_code == 409
        assert capped.json()["error_code"] == "ARCANA_ZHIPU_LIVE_UNAVAILABLE"
        assert transport.calls == 0

        save_preference(revision=1, cumulative_limit=100)
        successful_reading = start_draw(client)
        succeeded = client.post(
            f"/api/v1/arcana/readings/{successful_reading}/interpret-live",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json={
                "provider_definition_id": ZHIPU_PROVIDER_ID,
                "model_definition_id": ZHIPU_GLM_52_MODEL_ID,
                "credential_id": credential["id"],
                "confirm_paid_live_call": True,
            },
        )
        assert succeeded.status_code == 200, succeeded.text
        live_interpretation = succeeded.json()["interpretation"]
        assert live_interpretation["source"] == "zhipu_live"
        assert live_interpretation["model_id"] == "glm-5.2"
        retrieved_context = live_interpretation["retrieved_context"]
        assert 12 <= len(retrieved_context) <= 15
        assert sum(item["section"].startswith("card/") for item in retrieved_context) == 3
        assert sum(item["section"].startswith("position/") for item in retrieved_context) == 3
        assert sum(item["section"].startswith("question/") for item in retrieved_context) == 3
        assert (
            3 <= sum(item["section"].startswith("relationship/") for item in retrieved_context) <= 6
        )
        assert len(live_interpretation["citations"]) == 3
        retrieved_pairs = {(item["source_id"], item["chunk_id"]) for item in retrieved_context}
        assert {
            (item["source_id"], item["chunk_id"]) for item in live_interpretation["citations"]
        }.issubset(retrieved_pairs)
        assert transport.calls == 1
        journal = client.put(
            f"/api/v1/arcana/readings/{successful_reading}/journal",
            json={"personal_interpretation": "A grounded choice", "notes": "Private note"},
        )
        assert journal.status_code == 200
        assert journal.json()["journal"]["notes"] == "Private note"

        transport.mode = "schema_invalid"
        schema_invalid_reading = start_draw(client)
        schema_invalid = client.post(
            f"/api/v1/arcana/readings/{schema_invalid_reading}/interpret-live",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json={
                "provider_definition_id": ZHIPU_PROVIDER_ID,
                "model_definition_id": ZHIPU_GLM_52_MODEL_ID,
                "credential_id": credential["id"],
                "confirm_paid_live_call": True,
            },
        )
        assert schema_invalid.status_code == 409
        assert transport.calls == 2

        transport.mode = "citation_invalid"
        citation_invalid_reading = start_draw(client)
        citation_invalid = client.post(
            f"/api/v1/arcana/readings/{citation_invalid_reading}/interpret-live",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json={
                "provider_definition_id": ZHIPU_PROVIDER_ID,
                "model_definition_id": ZHIPU_GLM_52_MODEL_ID,
                "credential_id": credential["id"],
                "confirm_paid_live_call": True,
            },
        )
        assert citation_invalid.status_code == 409
        assert transport.calls == 3

        transport.mode = "outcome_unknown"
        unknown_reading = start_draw(client)
        unknown_key = str(uuid.uuid4())
        unknown_payload = {
            "provider_definition_id": ZHIPU_PROVIDER_ID,
            "model_definition_id": ZHIPU_GLM_52_MODEL_ID,
            "credential_id": credential["id"],
            "confirm_paid_live_call": True,
        }
        unknown = client.post(
            f"/api/v1/arcana/readings/{unknown_reading}/interpret-live",
            headers={"Idempotency-Key": unknown_key},
            json=unknown_payload,
        )
        assert unknown.status_code == 409
        assert transport.calls == 4
        duplicate = client.post(
            f"/api/v1/arcana/readings/{unknown_reading}/interpret-live",
            headers={"Idempotency-Key": unknown_key},
            json=unknown_payload,
        )
        assert duplicate.status_code == 409
        assert transport.calls == 4

        active_principal[0] = other
        other_reading = start_draw(client)
        cross_user = client.post(
            f"/api/v1/arcana/readings/{other_reading}/interpret-live",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json=unknown_payload,
        )
        assert cross_user.status_code == 409
        assert transport.calls == 4

        active_principal[0] = owner
        transport.mode = "success"
        current_credential = next(
            item
            for item in client.get("/api/v1/ai/credentials").json()["items"]
            if item["id"] == credential["id"]
        )
        revoked = client.post(
            f"/api/v1/ai/credentials/{credential['id']}/revoke",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json={"expected_revision": current_credential["revision"], "confirm": True},
        )
        assert revoked.status_code == 200, revoked.text
        revoked_reading = start_draw(client)
        revoked_attempt = client.post(
            f"/api/v1/arcana/readings/{revoked_reading}/interpret-live",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json=unknown_payload,
        )
        assert revoked_attempt.status_code == 409
        assert transport.calls == 4

    database_url = make_url(settings.database_url.get_secret_value())
    with psycopg.connect(**_connection_kwargs(database_url)) as connection:
        successful = connection.execute(
            """
            SELECT i.status, a.status, r.state, c.measurement_status, c.amount_minor_units,
                   u.measurement_status, u.input_units, u.output_units
            FROM invocation_requests AS i
            JOIN invocation_attempts AS a ON a.invocation_id = i.id
            JOIN budget_reservations AS r ON r.attempt_id = a.id
            JOIN ai_cost_ledger AS c ON c.attempt_id = a.id
            JOIN ai_usage_ledger AS u ON u.attempt_id = a.id
            WHERE i.product_space = 'arcana' AND i.status = 'succeeded'
            """
        ).fetchone()
        assert successful == (
            "succeeded",
            "succeeded",
            "settled",
            "measured",
            1,
            "measured",
            100,
            50,
        )
        structured_failures = connection.execute(
            """
            SELECT a.safe_provider_metadata ->> 'structured_failure_category',
                   a.safe_provider_metadata ->> 'structured_error_path',
                   a.safe_provider_metadata ->> 'structured_expected_json_type',
                   a.safe_provider_metadata ->> 'structured_received_json_type',
                   a.safe_provider_metadata ->> 'structured_received_item_count',
                   a.safe_provider_metadata ? 'structured_received_object_keys',
                   a.safe_provider_metadata ->> 'structured_validator_error_category',
                   a.safe_provider_metadata ->> 'finish_reason',
                   a.safe_provider_metadata ->> 'json_parse_status',
                   a.safe_provider_metadata ->> 'schema_validation_status',
                   a.safe_provider_metadata ->> 'citation_validation_status',
                   r.state, c.measurement_status, c.amount_minor_units,
                   u.safe_metadata ->> 'reasoning_tokens'
            FROM invocation_requests AS i
            JOIN invocation_attempts AS a ON a.invocation_id = i.id
            JOIN budget_reservations AS r ON r.attempt_id = a.id
            JOIN ai_cost_ledger AS c ON c.attempt_id = a.id
            JOIN ai_usage_ledger AS u ON u.attempt_id = a.id
            WHERE i.product_space = 'arcana' AND i.status = 'failed'
            ORDER BY i.created_at
            """
        ).fetchall()
        assert structured_failures == [
            (
                "SCHEMA_VALIDATION_FAILED",
                "$.actionable_reflections[0]",
                "array<string>",
                "array<object>",
                "1",
                False,
                "string_type",
                "stop",
                "parsed",
                "failed",
                "not_attempted",
                "settled",
                "measured",
                1,
                "12",
            ),
            (
                "CITATION_VALIDATION_FAILED",
                "$.knowledge_basis[0]",
                None,
                None,
                None,
                False,
                None,
                "stop",
                "parsed",
                "failed",
                "failed",
                "settled",
                "measured",
                1,
                "12",
            ),
        ]
        request_configuration = connection.execute(
            """
            SELECT i.safe_payload -> 'request_configuration',
                   i.budget_snapshot ->> 'reserved_minor_units'
            FROM invocation_requests AS i
            WHERE i.product_space = 'arcana' AND i.status = 'succeeded'
            """
        ).fetchone()
        assert request_configuration is not None
        assert request_configuration[0] == {
            "max_tokens": 8_192,
            "response_format": {"type": "json_object"},
            "thinking": {"type": "enabled"},
            "reasoning_effort": "high",
            "do_sample": False,
        }
        assert int(request_configuration[1]) >= 1
        unknown_state = connection.execute(
            """
            SELECT i.status, a.status, r.state, i.max_attempts, a.attempt_number
            FROM invocation_requests AS i
            JOIN invocation_attempts AS a ON a.invocation_id = i.id
            JOIN budget_reservations AS r ON r.attempt_id = a.id
            WHERE i.product_space = 'arcana' AND i.status = 'outcome_unknown'
            """
        ).fetchone()
        assert unknown_state == (
            "outcome_unknown",
            "outcome_unknown",
            "reconciliation_required",
            1,
            1,
        )
        credential_state = connection.execute(
            """
            SELECT status, ciphertext, wrapped_dek, last_validation_status
            FROM credential_records WHERE id = %s
            """,
            (credential["id"],),
        ).fetchone()
        assert credential_state == ("revoked", None, None, "provider_valid")
        committed = connection.execute(
            """
            SELECT coalesce(sum(amount_minor_units), 0)
            FROM ai_cost_ledger
            WHERE currency = 'CNY' AND amount_minor_units IS NOT NULL
            """
        ).fetchone()
        assert committed is not None and 0 <= committed[0] <= 100


def test_zhipu_paint_plan_offline_live_multimodal_provenance_and_citations(
    paint_plan_integration_settings: Settings,
) -> None:
    settings = paint_plan_integration_settings.model_copy(update={"zhipu_live_enabled": True})
    owner = _principal(label="zhipu-paint-owner", user_id=uuid.uuid4())
    _seed_users(settings, owner)
    synthetic_secret = f"zhipu-synthetic-{uuid.uuid4().hex}"
    transport = _OfflineZhipuTransport(synthetic_secret.encode())
    app = create_app(settings)
    app.state.zhipu_transport = transport
    app.dependency_overrides[get_current_principal] = lambda: owner

    with TestClient(app) as client:
        project = _create_project(client, "Zhipu governed offline multimodal plan")
        project_id = project["id"]
        image_set = _ready_image_set(client, project_id)
        region_set = _approved_region_set(client, project_id)
        credential_id = _configure_zhipu_ai(client, project_id, synthetic_secret)
        selection = {
            "image_set_fingerprint": image_set["image_set_fingerprint"],
            "region_set_id": region_set["id"],
            "provider_definition_id": ZHIPU_PROVIDER_ID,
            "model_definition_id": ZHIPU_GLM_5V_TURBO_MODEL_ID,
            "credential_id": credential_id,
            "generation_locale": "en-US",
            "intent": "Use only the approved regions and preserve the excluded background.",
        }
        preview = client.post(
            f"/api/v1/paint-projects/{project_id}/paint-plans/preview",
            json=selection,
        )
        assert preview.status_code == 200, preview.text
        assert preview.json() == {
            "admissible": True,
            "execution_mode": "live_authorization_required",
            "provider_key": "zhipu",
            "model_id": ZHIPU_GLM_5V_TURBO_MODEL,
            "source_ready": True,
            "estimated_cost_minor_units": preview.json()["estimated_cost_minor_units"],
            "currency": "CNY",
            "estimate_status": "estimated",
            "live_execution_authorized": True,
            "blockers": [],
        }
        assert 0 < preview.json()["estimated_cost_minor_units"] <= 100
        transport.mode = "paint_root_wrapper"
        invalid_response = client.post(
            f"/api/v1/paint-projects/{project_id}/paint-plans/generate",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json={**selection, "confirm_generation": True, "max_attempts": 1},
        )
        assert invalid_response.status_code == 502, invalid_response.text
        assert invalid_response.json()["error_code"] == "PAINT_PLAN_OUTPUT_INVALID"

        transport.mode = "success"
        generated_response = client.post(
            f"/api/v1/paint-projects/{project_id}/paint-plans/generate",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json={**selection, "confirm_generation": True, "max_attempts": 1},
        )
        assert generated_response.status_code == 201, generated_response.text
        generated = generated_response.json()
        assert generated["provider_key"] == "zhipu"
        assert generated["model_id"] == ZHIPU_GLM_5V_TURBO_MODEL
        assert len(generated["document"]["instructions"]) == 2
        assert len(generated["retrieved_context"]) >= 1
        assert len(generated["document"]["knowledge_citations"]) >= 1
        retrieved_pairs = {
            (item["source_id"], item["chunk_id"]) for item in generated["retrieved_context"]
        }
        assert {
            (item["source_id"], item["chunk_id"])
            for item in generated["document"]["knowledge_citations"]
        }.issubset(retrieved_pairs)
        assert transport.calls == 2

    database_url = make_url(settings.database_url.get_secret_value())
    with psycopg.connect(**_connection_kwargs(database_url)) as connection:
        provenance = connection.execute(
            """
            SELECT p.provider_key_snapshot, p.model_id_snapshot,
                   jsonb_array_length(p.retrieved_context_snapshot),
                   jsonb_array_length(p.citation_snapshot),
                   i.status, a.status, r.state, c.measurement_status,
                   c.amount_minor_units, u.input_units, u.output_units
            FROM paint_plans AS p
            JOIN invocation_requests AS i ON i.id = p.source_invocation_id
            JOIN invocation_attempts AS a ON a.id = p.source_attempt_id
            JOIN budget_reservations AS r ON r.attempt_id = a.id
            JOIN ai_cost_ledger AS c ON c.attempt_id = a.id
            JOIN ai_usage_ledger AS u ON u.attempt_id = a.id
            WHERE p.paint_project_id = %s
            """,
            (project_id,),
        ).fetchone()
        assert provenance == (
            "zhipu",
            ZHIPU_GLM_5V_TURBO_MODEL,
            3,
            3,
            "succeeded",
            "succeeded",
            "settled",
            "measured",
            2,
            1_000,
            500,
        )
        failure = connection.execute(
            """
            SELECT i.output_reference, a.output_reference,
                   a.safe_provider_metadata ->> 'structured_failure_category',
                   a.safe_provider_metadata ->> 'structured_error_path',
                   a.safe_provider_metadata ->> 'structured_expected_root_json_type',
                   a.safe_provider_metadata ->> 'structured_received_root_json_type',
                   a.safe_provider_metadata ->> 'structured_expected_json_type',
                   a.safe_provider_metadata ->> 'structured_received_json_type',
                   a.safe_provider_metadata -> 'structured_missing_required_keys',
                   a.safe_provider_metadata -> 'structured_unexpected_object_keys',
                   a.safe_provider_metadata ->> 'structured_validator_error_category',
                   a.safe_provider_metadata ->> 'finish_reason',
                   a.safe_provider_metadata ->> 'json_parse_status',
                   a.safe_provider_metadata ->> 'schema_validation_status',
                   a.safe_provider_metadata ->> 'citation_validation_status',
                   r.state,
                   i.safe_payload -> 'request_configuration'
            FROM invocation_requests AS i
            JOIN invocation_attempts AS a ON a.invocation_id = i.id
            JOIN budget_reservations AS r ON r.attempt_id = a.id
            WHERE i.project_id = %s AND i.status = 'failed'
            """,
            (project_id,),
        ).fetchone()
        assert failure == (
            None,
            None,
            "SCHEMA_VALIDATION_FAILED",
            "$.schema_version",
            "object",
            "object",
            "string",
            "missing",
            [
                "schema_version",
                "title",
                "overall_approach",
                "instructions",
                "safety_notes",
            ],
            ["paint_plan"],
            "missing",
            "stop",
            "parsed",
            "failed",
            "not_attempted",
            "settled",
            {
                "max_tokens": 4_096,
                "thinking": {"type": "enabled"},
                "do_sample": False,
            },
        )
        assert connection.execute(
            "SELECT count(*) FROM paint_plans WHERE paint_project_id = %s",
            (project_id,),
        ).fetchone() == (1,)
        stored_failure = connection.execute(
            """
            SELECT concat_ws(' ', i.safe_payload::text, a.safe_provider_metadata::text)
            FROM invocation_requests AS i
            JOIN invocation_attempts AS a ON a.invocation_id = i.id
            WHERE i.project_id = %s AND i.status = 'failed'
            """,
            (project_id,),
        ).fetchone()
        assert stored_failure is not None
        assert "private generated output must not persist" not in stored_failure[0]
        assert "response_format" not in failure[-1]
