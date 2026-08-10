"""Strict structured Paint Plan schema tests."""

import uuid

import pytest
from pydantic import ValidationError

from creativedeploy_api.ai.encryption import SecretBytes
from creativedeploy_api.ai.fixture_provider import FixtureProviderAdapter
from creativedeploy_api.schemas.paint_plans import PaintPlanDocument, PaintPlanGenerateRequest
from creativedeploy_api.services.ai_foundation import _validated_paint_plan_output


def _instruction(*, region_id: uuid.UUID, stable_key: uuid.UUID) -> dict[str, object]:
    return {
        "region_id": region_id,
        "stable_region_key": stable_key,
        "region_label": "Front panel",
        "target_color": "warm neutral gray",
        "preparation": "Clean and lightly key the surface.",
        "base_coat": "Apply one even opaque base coat.",
        "layer_strategy": "Build two thin layers and preserve the approved silhouette.",
        "edge_treatment": "Keep the outer edge crisp.",
        "lighting_guidance": "Reserve a narrow upper-left highlight.",
        "material_guidance": "Use a matte finish.",
        "warnings": ["Do not paint protected regions."],
        "confidence_ppm": 900_000,
    }


def _document() -> dict[str, object]:
    return {
        "schema_version": "paint-plan.v1",
        "title": "Controlled panel paint plan",
        "overall_approach": "Work from broad base shapes toward bounded edge details.",
        "instructions": [
            _instruction(region_id=uuid.uuid4(), stable_key=uuid.uuid4()),
            _instruction(region_id=uuid.uuid4(), stable_key=uuid.uuid4()),
        ],
        "safety_notes": ["Keep excluded regions untouched."],
    }


def test_document_accepts_multiple_exact_typed_regions() -> None:
    parsed = PaintPlanDocument.model_validate(_document())
    assert parsed.schema_version == "paint-plan.v1"
    assert len(parsed.instructions) == 2


@pytest.mark.parametrize("unknown_field", ["raw_provider_response", "secret", "html"])
def test_document_rejects_unknown_fields(unknown_field: str) -> None:
    payload = _document()
    payload[unknown_field] = "not allowed"
    with pytest.raises(ValidationError):
        PaintPlanDocument.model_validate(payload)


def test_document_rejects_duplicate_region_or_semantic_identity() -> None:
    payload = _document()
    instructions = payload["instructions"]
    assert isinstance(instructions, list)
    second = instructions[1]
    first = instructions[0]
    assert isinstance(first, dict) and isinstance(second, dict)
    second["region_id"] = first["region_id"]
    with pytest.raises(ValidationError, match="region_id must be unique"):
        PaintPlanDocument.model_validate(payload)


def test_document_rejects_schema_drift_and_html() -> None:
    payload = _document()
    payload["schema_version"] = "paint-plan.v2"
    with pytest.raises(ValidationError):
        PaintPlanDocument.model_validate(payload)

    payload = _document()
    payload["title"] = "<script>unsafe</script>"
    with pytest.raises(ValidationError, match="must not contain HTML"):
        PaintPlanDocument.model_validate(payload)


def test_fixture_builds_deterministic_plan_and_skips_excluded_regions() -> None:
    paint_id = uuid.uuid4()
    paint_key = uuid.uuid4()
    exclude_id = uuid.uuid4()
    source = {
        "region_set": {
            "regions": [
                {
                    "id": str(paint_id),
                    "stable_region_key": str(paint_key),
                    "kind": "paint",
                    "label": "Front panel",
                },
                {
                    "id": str(exclude_id),
                    "stable_region_key": str(uuid.uuid4()),
                    "kind": "exclude",
                    "label": "Protected badge",
                },
            ]
        }
    }
    adapter = FixtureProviderAdapter()
    first = adapter.invoke(
        {"paint_plan_input": source},
        SecretBytes(b"fixture-sk-synthetic-paint-plan-test"),
    )
    second = adapter.invoke(
        {"paint_plan_input": source},
        SecretBytes(b"fixture-sk-synthetic-paint-plan-test"),
    )

    assert first.output == second.output
    parsed = PaintPlanDocument.model_validate(first.output)
    assert [item.region_id for item in parsed.instructions] == [paint_id]
    assert parsed.instructions[0].stable_region_key == paint_key


@pytest.mark.parametrize("generation_locale", ["zh-CN", "en-US"])
def test_generation_request_accepts_only_supported_product_locales(
    generation_locale: str,
) -> None:
    parsed = PaintPlanGenerateRequest.model_validate(
        {
            "image_set_fingerprint": "a" * 64,
            "region_set_id": uuid.uuid4(),
            "provider_definition_id": uuid.uuid4(),
            "model_definition_id": uuid.uuid4(),
            "credential_id": uuid.uuid4(),
            "generation_locale": generation_locale,
            "intent": None,
            "confirm_generation": True,
            "max_attempts": 1,
        }
    )
    assert parsed.generation_locale == generation_locale


def test_generation_request_rejects_unsupported_locale() -> None:
    with pytest.raises(ValidationError):
        PaintPlanGenerateRequest.model_validate(
            {
                "image_set_fingerprint": "a" * 64,
                "region_set_id": uuid.uuid4(),
                "provider_definition_id": uuid.uuid4(),
                "model_definition_id": uuid.uuid4(),
                "credential_id": uuid.uuid4(),
                "generation_locale": "fr-FR",
                "intent": None,
                "confirm_generation": True,
                "max_attempts": 1,
            }
        )


def test_fixture_localizes_owned_content_deterministically_without_translating_region_label() -> (
    None
):
    paint_id = uuid.UUID("51515151-5151-4515-8515-515151515151")
    stable_key = uuid.UUID("52525252-5252-4525-8525-525252525252")
    source = {
        "generation_locale": "zh-CN",
        "region_set": {
            "regions": [
                {
                    "id": str(paint_id),
                    "stable_region_key": str(stable_key),
                    "kind": "paint",
                    "label": "User custom region name",
                }
            ]
        },
    }
    adapter = FixtureProviderAdapter()
    secret = SecretBytes(b"fixture-sk-synthetic-localized-plan-test")

    first = adapter.invoke({"paint_plan_input": source}, secret)
    second = adapter.invoke({"paint_plan_input": source}, secret)

    assert first.output == second.output
    parsed = PaintPlanDocument.model_validate(first.output)
    assert parsed.title.startswith("受管 Fixture 涂装方案")
    assert parsed.instructions[0].region_label == "User custom region name"
    assert parsed.instructions[0].target_color in {
        "暖中性灰",
        "低饱和铜色",
        "深石墨色",
        "柔和青绿色点缀",
        "低饱和赭石色",
    }
    assert parsed.instructions[0].warnings == ["不得越过已批准的区域边界。"]
    assert parsed.safety_notes[0] == "仅使用已批准的图像与 RegionSet 修订。"


def test_invocation_output_projection_requires_exact_governed_region_identities() -> None:
    output = _document()
    instructions = output["instructions"]
    assert isinstance(instructions, list)
    contract_regions = [
        {
            "region_id": str(item["region_id"]),
            "stable_region_key": str(item["stable_region_key"]),
            "region_label": item["region_label"],
        }
        for item in instructions
        if isinstance(item, dict)
    ]
    safe_payload = {
        "paint_plan_contract": {
            "paint_regions": contract_regions,
            "excluded_region_ids": [str(uuid.uuid4())],
        }
    }

    projected = _validated_paint_plan_output(output, safe_payload=safe_payload)

    assert projected["schema_version"] == "paint-plan.v1"
    assert (
        projected["instructions"]
        == PaintPlanDocument.model_validate(output).model_dump(mode="json")["instructions"]
    )

    unknown = {**output, "provider_response": "must not persist"}
    with pytest.raises(ValidationError):
        _validated_paint_plan_output(unknown, safe_payload=safe_payload)

    first_region_id = contract_regions[0]["region_id"]
    excluded_contract = {
        "paint_plan_contract": {
            "paint_regions": contract_regions,
            "excluded_region_ids": [first_region_id],
        }
    }
    with pytest.raises(ValueError, match="exact governed RegionSet"):
        _validated_paint_plan_output(output, safe_payload=excluded_contract)
