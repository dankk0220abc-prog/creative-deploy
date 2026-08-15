"""Strict structured Paint Plan schema tests."""

import uuid

import pytest
from pydantic import ValidationError

from creativedeploy_api.ai.encryption import SecretBytes
from creativedeploy_api.ai.fixture_provider import FixtureProviderAdapter
from creativedeploy_api.ai.provider_transport import StructuredOutputValidationError
from creativedeploy_api.ai.retrieval import RetrievedContextBundle, RetrievedContextUnit
from creativedeploy_api.db.models import Region
from creativedeploy_api.schemas.paint_plans import (
    PAINT_PLAN_CITATION_KEYS,
    PAINT_PLAN_INSTRUCTION_KEYS,
    PAINT_PLAN_LIVE_PROMPT_VERSION,
    PAINT_PLAN_OPTIONAL_ROOT_KEYS,
    PAINT_PLAN_REQUIRED_ROOT_KEYS,
    PAINT_PLAN_ROOT_KEYS,
    PaintPlanDocument,
    PaintPlanGenerateRequest,
    paint_plan_live_output_contract,
    paint_plan_live_output_template,
)
from creativedeploy_api.services.ai_foundation import _validated_paint_plan_output
from creativedeploy_api.services.paint_plans import _validate_live_paint_plan_output


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


def _retrieval() -> RetrievedContextBundle:
    return RetrievedContextBundle(
        product_space="paintpilot",
        units=[
            RetrievedContextUnit(
                source_id="paint-preparation-v1",
                source_title="Surface preparation",
                source_type="repository_local_practice_note",
                repository_reference="repo://paintpilot/knowledge/surface-preparation",
                chunk_id="surface-preparation",
                section="Preparation",
                content="Clean, abrade, and test compatibility before applying paint.",
                retrieval_rationale="Exact local support for preparation guidance.",
                retrieval_score_ppm=1_000_000,
                locale="en-US",
                corpus_id="paintpilot-practice-notes",
                corpus_version="1",
            )
        ],
    )


def _live_contract() -> tuple[dict[str, object], list[Region], RetrievedContextBundle]:
    document = _document()
    document["knowledge_citations"] = [
        {
            "source_id": "paint-preparation-v1",
            "chunk_id": "surface-preparation",
            "target_path": "/instructions/0/preparation",
        }
    ]
    raw_instructions = document["instructions"]
    assert isinstance(raw_instructions, list)
    regions: list[Region] = []
    for index, instruction in enumerate(raw_instructions):
        assert isinstance(instruction, dict)
        regions.append(
            Region(
                id=instruction["region_id"],
                region_set_id=uuid.uuid4(),
                paint_project_id=uuid.uuid4(),
                owner_principal_id="paint-plan-schema-test-owner",
                stable_region_key=instruction["stable_region_key"],
                kind="paint",
                label=instruction["region_label"],
                normalized_label=str(instruction["region_label"]).casefold(),
                z_index=index,
                opacity_ppm=1_000_000,
                notes=None,
                vertex_count=3,
                area_twice_ppm_squared=1,
                bbox_min_x_ppm=0,
                bbox_min_y_ppm=0,
                bbox_max_x_ppm=1,
                bbox_max_y_ppm=1,
            )
        )
    return document, regions, _retrieval()


def test_document_accepts_multiple_exact_typed_regions() -> None:
    parsed = PaintPlanDocument.model_validate(_document())
    assert parsed.schema_version == "paint-plan.v1"
    assert len(parsed.instructions) == 2


def test_live_prompt_template_has_exact_schema_parity_without_aliases() -> None:
    schema = PaintPlanDocument.model_json_schema()
    properties = schema["properties"]
    definitions = schema["$defs"]
    template = paint_plan_live_output_template()

    assert tuple(properties) == PAINT_PLAN_ROOT_KEYS
    assert tuple(schema["required"]) == PAINT_PLAN_REQUIRED_ROOT_KEYS
    assert tuple(key for key in properties if key not in schema["required"]) == (
        PAINT_PLAN_OPTIONAL_ROOT_KEYS
    )
    assert tuple(template) == PAINT_PLAN_ROOT_KEYS
    assert tuple(template["instructions"][0]) == PAINT_PLAN_INSTRUCTION_KEYS
    assert tuple(template["knowledge_citations"][0]) == PAINT_PLAN_CITATION_KEYS
    assert tuple(definitions["PaintPlanRegionInstruction"]["properties"]) == (
        PAINT_PLAN_INSTRUCTION_KEYS
    )
    assert tuple(definitions["RetrievedCitation"]["properties"]) == PAINT_PLAN_CITATION_KEYS
    assert all(field.alias is None for field in PaintPlanDocument.model_fields.values())
    assert PAINT_PLAN_LIVE_PROMPT_VERSION == 2
    contract = paint_plan_live_output_contract()
    assert "direct JSON object" in contract
    assert "Do not wrap it in paint_plan" in contract
    assert "knowledge_citations must contain 1..24" in contract


def test_live_root_contract_accepts_exact_document_and_real_retrieval_citation() -> None:
    document, regions, retrieval = _live_contract()

    validated = _validate_live_paint_plan_output(
        document,
        regions=regions,
        retrieval=retrieval,
    )

    assert validated == PaintPlanDocument.model_validate(document).model_dump(mode="json")


@pytest.mark.parametrize(
    ("mutate", "path", "expected_type", "received_type", "category"),
    [
        (
            lambda value: value.pop("title"),
            "$.title",
            "string",
            "missing",
            "missing",
        ),
        (
            lambda value: value.update({"schema_version": "paint-plan.v2"}),
            "$.schema_version",
            "string",
            "string",
            "literal_error",
        ),
        (
            lambda value: value["instructions"][0].update({"confidence_ppm": "high"}),
            "$.instructions[0].confidence_ppm",
            "integer",
            "string",
            "int_type",
        ),
    ],
)
def test_live_schema_failures_report_exact_value_free_path_and_shape(
    mutate: object,
    path: str,
    expected_type: str,
    received_type: str,
    category: str,
) -> None:
    document, regions, retrieval = _live_contract()
    assert callable(mutate)
    mutate(document)

    with pytest.raises(StructuredOutputValidationError) as captured:
        _validate_live_paint_plan_output(document, regions=regions, retrieval=retrieval)

    error = captured.value
    assert error.category == "SCHEMA_VALIDATION_FAILED"
    assert error.path == path
    assert error.expected_root_json_type == "object"
    assert error.received_root_json_type == "object"
    assert error.expected_json_type == expected_type
    assert error.received_json_type == received_type
    assert error.validator_error_category == category
    assert not hasattr(error, "raw_response")


def test_live_wrapper_and_renamed_root_fields_fail_with_allowlisted_key_diagnostics() -> None:
    document, regions, retrieval = _live_contract()
    marker = "private generated value must not persist"
    wrapper = {"paint_plan": document, "private_field": marker}

    with pytest.raises(StructuredOutputValidationError) as wrapped:
        _validate_live_paint_plan_output(wrapper, regions=regions, retrieval=retrieval)

    assert wrapped.value.path == "$.schema_version"
    assert wrapped.value.received_object_keys == ()
    assert wrapped.value.missing_required_keys == PAINT_PLAN_REQUIRED_ROOT_KEYS
    assert wrapped.value.unexpected_object_keys == ("paint_plan",)
    assert marker not in repr(wrapped.value.__dict__)

    renamed = dict(document)
    renamed["overall_strategy"] = renamed.pop("overall_approach")
    with pytest.raises(StructuredOutputValidationError) as renamed_error:
        _validate_live_paint_plan_output(renamed, regions=regions, retrieval=retrieval)

    assert renamed_error.value.path == "$.overall_approach"
    assert renamed_error.value.missing_required_keys == ("overall_approach",)
    assert renamed_error.value.unexpected_object_keys == ("overall_strategy",)


def test_live_hallucinated_citation_fails_only_after_schema_validation() -> None:
    document, regions, retrieval = _live_contract()
    citations = document["knowledge_citations"]
    assert isinstance(citations, list) and isinstance(citations[0], dict)
    citations[0]["source_id"] = "hallucinated-source"

    with pytest.raises(StructuredOutputValidationError) as captured:
        _validate_live_paint_plan_output(document, regions=regions, retrieval=retrieval)

    assert captured.value.category == "CITATION_VALIDATION_FAILED"
    assert captured.value.path == "$.knowledge_citations"
    assert captured.value.validator_error_category == "retrieved_citation_mismatch"


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
