"""Focused metadata contracts for the Phase 3B Paint Plan persistence slice."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
from types import ModuleType

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Table, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

from creativedeploy_api.db.base import Base
from creativedeploy_api.db.models import (
    REGISTERED_MODELS,
    PaintPlan,
    PaintPlanRegionInstruction,
    PaintPlanReviewEvent,
    PromptTemplateDefinition,
    ProviderPricingSnapshot,
)

API_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = (
    API_ROOT / "migrations" / "versions" / "3b01a1c2d3e4_add_phase3b_paint_plan_foundation.py"
)


def _checks(table: Table) -> dict[str, str]:
    return {
        str(constraint.name): " ".join(str(constraint.sqltext).split())
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }


def _foreign_keys(table: Table) -> dict[str, ForeignKeyConstraint]:
    return {
        str(constraint.name): constraint
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }


def _foreign_key_shape(
    constraint: ForeignKeyConstraint,
) -> tuple[tuple[str, ...], tuple[str, ...], str | None]:
    return (
        tuple(constraint.column_keys),
        tuple(element.target_fullname for element in constraint.elements),
        constraint.ondelete,
    )


def _unique_shapes(table: Table) -> set[tuple[str, tuple[str, ...]]]:
    return {
        (str(constraint.name), tuple(constraint.columns.keys()))
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def _load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("phase3b_paint_plan_migration", MIGRATION_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("Phase 3B migration could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_phase3b_models_are_registered_as_one_exact_additive_slice() -> None:
    expected = (
        ProviderPricingSnapshot,
        PromptTemplateDefinition,
        PaintPlan,
        PaintPlanRegionInstruction,
        PaintPlanReviewEvent,
    )

    assert REGISTERED_MODELS[39:44] == expected
    assert {model.__table__.name for model in expected} == {
        "provider_pricing_snapshots",
        "prompt_template_definitions",
        "paint_plans",
        "paint_plan_region_instructions",
        "paint_plan_review_events",
    }
    assert all(model.metadata is Base.metadata for model in expected)


def test_phase3b_tables_have_exact_columns_and_json_nullability() -> None:
    assert tuple(ProviderPricingSnapshot.__table__.columns.keys()) == (
        "id",
        "provider_definition_id",
        "model_definition_id",
        "provider_key",
        "model_id",
        "pricing_version",
        "currency",
        "unit_basis",
        "input_minor_units_per_million",
        "output_minor_units_per_million",
        "source_url",
        "effective_at",
        "captured_at",
        "created_at",
    )
    assert tuple(PromptTemplateDefinition.__table__.columns.keys()) == (
        "id",
        "template_key",
        "version",
        "schema_version",
        "template_body",
        "content_hash",
        "status",
        "created_at",
    )
    assert tuple(PaintPlan.__table__.columns.keys()) == (
        "id",
        "owner_principal_id",
        "paint_project_id",
        "lineage_id",
        "version",
        "lineage_revision",
        "revision_kind",
        "lifecycle",
        "parent_plan_id",
        "source_readiness_review_id",
        "source_readiness_review_version",
        "source_image_set_fingerprint",
        "source_region_set_id",
        "source_region_set_version",
        "source_geometry_fingerprint",
        "source_invocation_id",
        "source_attempt_id",
        "provider_definition_id",
        "provider_key_snapshot",
        "provider_revision_snapshot",
        "model_definition_id",
        "model_id_snapshot",
        "model_revision_snapshot",
        "provider_pricing_snapshot_id",
        "prompt_template_definition_id",
        "prompt_template_key_snapshot",
        "prompt_template_version_snapshot",
        "prompt_content_hash",
        "response_schema_version",
        "title",
        "overall_approach",
        "safety_notes",
        "instruction_count",
        "content_hash",
        "created_by_actor_type",
        "created_by_actor_id",
        "created_by_actor_display_name_snapshot",
        "created_at",
    )
    assert tuple(PaintPlanRegionInstruction.__table__.columns.keys()) == (
        "id",
        "paint_plan_id",
        "region_set_id",
        "region_id",
        "stable_region_key",
        "region_label_snapshot",
        "region_kind_snapshot",
        "sequence",
        "target_color",
        "preparation",
        "base_coat",
        "layer_strategy",
        "edge_treatment",
        "lighting_guidance",
        "material_guidance",
        "warnings",
        "confidence_ppm",
        "created_at",
    )
    assert tuple(PaintPlanReviewEvent.__table__.columns.keys()) == (
        "id",
        "owner_principal_id",
        "paint_project_id",
        "paint_plan_id",
        "paint_plan_version",
        "action",
        "actor_user_id",
        "actor_principal_id",
        "actor_display_name_snapshot",
        "reason",
        "created_at",
    )

    assert isinstance(PaintPlan.__table__.c.safety_notes.type, JSONB)
    assert PaintPlan.__table__.c.safety_notes.nullable is False
    assert str(PaintPlan.__table__.c.safety_notes.server_default.arg) == "'[]'::jsonb"
    assert isinstance(PaintPlanRegionInstruction.__table__.c.warnings.type, JSONB)
    assert PaintPlanRegionInstruction.__table__.c.warnings.nullable is False
    assert PaintPlanReviewEvent.__table__.c.actor_user_id.nullable is True


def test_paint_plan_provenance_uses_restrict_and_exact_composite_foreign_keys() -> None:
    plan_fks = _foreign_keys(PaintPlan.__table__)
    assert _foreign_key_shape(plan_fks["fk_paint_plans_project_owner"]) == (
        ("paint_project_id", "owner_principal_id"),
        ("paint_projects.id", "paint_projects.owner_principal_id"),
        "RESTRICT",
    )
    assert _foreign_key_shape(plan_fks["fk_paint_plans_source_region_set_same_project_owner"]) == (
        ("paint_project_id", "owner_principal_id", "source_region_set_id"),
        (
            "region_sets.paint_project_id",
            "region_sets.owner_principal_id",
            "region_sets.id",
        ),
        "RESTRICT",
    )
    assert _foreign_key_shape(plan_fks["fk_paint_plans_source_attempt"]) == (
        ("source_invocation_id", "source_attempt_id"),
        ("invocation_attempts.invocation_id", "invocation_attempts.id"),
        "RESTRICT",
    )
    assert _foreign_key_shape(plan_fks["fk_paint_plans_pricing_snapshot_exact_model"]) == (
        (
            "provider_pricing_snapshot_id",
            "provider_definition_id",
            "model_definition_id",
        ),
        (
            "provider_pricing_snapshots.id",
            "provider_pricing_snapshots.provider_definition_id",
            "provider_pricing_snapshots.model_definition_id",
        ),
        "RESTRICT",
    )
    assert _foreign_key_shape(plan_fks["fk_paint_plans_prompt_exact_contract"]) == (
        (
            "prompt_template_definition_id",
            "prompt_template_key_snapshot",
            "prompt_template_version_snapshot",
            "prompt_content_hash",
            "response_schema_version",
        ),
        (
            "prompt_template_definitions.id",
            "prompt_template_definitions.template_key",
            "prompt_template_definitions.version",
            "prompt_template_definitions.content_hash",
            "prompt_template_definitions.schema_version",
        ),
        "RESTRICT",
    )
    assert (
        _foreign_key_shape(plan_fks["fk_paint_plans_lineage_same_project_owner"])[2] == "RESTRICT"
    )
    assert _foreign_key_shape(plan_fks["fk_paint_plans_parent_same_project_owner"])[2] == "RESTRICT"
    assert all(foreign_key.ondelete == "RESTRICT" for foreign_key in plan_fks.values())

    instruction_fks = _foreign_keys(PaintPlanRegionInstruction.__table__)
    assert _foreign_key_shape(
        instruction_fks["fk_paint_plan_region_instructions_plan_region_set"]
    ) == (
        ("paint_plan_id", "region_set_id"),
        ("paint_plans.id", "paint_plans.source_region_set_id"),
        "RESTRICT",
    )
    assert _foreign_key_shape(
        instruction_fks["fk_paint_plan_region_instructions_region_same_set"]
    ) == (
        ("region_id", "region_set_id"),
        ("regions.id", "regions.region_set_id"),
        "RESTRICT",
    )

    review_fk = _foreign_keys(PaintPlanReviewEvent.__table__)[
        "fk_paint_plan_review_events_exact_revision"
    ]
    assert _foreign_key_shape(review_fk) == (
        (
            "paint_plan_id",
            "paint_plan_version",
            "paint_project_id",
            "owner_principal_id",
        ),
        (
            "paint_plans.id",
            "paint_plans.version",
            "paint_plans.paint_project_id",
            "paint_plans.owner_principal_id",
        ),
        "RESTRICT",
    )


def test_paint_plan_revision_instruction_and_review_uniqueness_is_explicit() -> None:
    assert {
        ("uq_paint_plans_project_version", ("paint_project_id", "version")),
        ("uq_paint_plans_lineage_revision", ("lineage_id", "lineage_revision")),
        (
            "uq_paint_plans_exact_revision",
            ("id", "version", "paint_project_id", "owner_principal_id"),
        ),
    } <= _unique_shapes(PaintPlan.__table__)
    assert {
        (
            "uq_paint_plan_region_instructions_plan_region",
            ("paint_plan_id", "region_id"),
        ),
        (
            "uq_paint_plan_region_instructions_plan_stable_key",
            ("paint_plan_id", "stable_region_key"),
        ),
        (
            "uq_paint_plan_region_instructions_plan_sequence",
            ("paint_plan_id", "sequence"),
        ),
    } <= _unique_shapes(PaintPlanRegionInstruction.__table__)
    assert (
        "uq_paint_plan_review_events_plan_action",
        ("paint_plan_id", "action"),
    ) in _unique_shapes(PaintPlanReviewEvent.__table__)

    plan_indexes = {str(index.name): index for index in PaintPlan.__table__.indexes}
    assert plan_indexes["uq_paint_plans_generated_attempt"].unique is True
    review_indexes = {str(index.name): index for index in PaintPlanReviewEvent.__table__.indexes}
    assert review_indexes["uq_paint_plan_review_events_decision"].unique is True


def test_paint_plan_checks_bound_lifecycle_content_and_typed_region_contract() -> None:
    plan_checks = _checks(PaintPlan.__table__)
    assert "generated" in plan_checks["ck_paint_plans_lifecycle_allowed"]
    assert "under_review" in plan_checks["ck_paint_plans_lifecycle_allowed"]
    assert "superseded" in plan_checks["ck_paint_plans_lifecycle_allowed"]
    assert "regenerated" in plan_checks["ck_paint_plans_revision_kind_allowed"]
    assert (
        "source_image_set_fingerprint" in plan_checks["ck_paint_plans_source_fingerprints_format"]
    )
    assert (
        "provider_pricing_snapshot_id IS NOT NULL"
        in plan_checks["ck_paint_plans_pricing_snapshot_required"]
    )
    assert (
        "jsonb_typeof(safety_notes) = 'array'" in plan_checks["ck_paint_plans_safety_notes_bounded"]
    )
    assert (
        "instruction_count BETWEEN 1 AND 128"
        in plan_checks["ck_paint_plans_instruction_count_allowed"]
    )

    instruction_checks = _checks(PaintPlanRegionInstruction.__table__)
    assert instruction_checks["ck_paint_plan_region_instructions_kind_paint"] == (
        "region_kind_snapshot = 'paint'"
    )
    assert (
        "length(target_color) BETWEEN 1 AND 120"
        in instruction_checks["ck_paint_plan_region_instructions_text_safe"]
    )
    assert (
        "jsonb_array_length(warnings) <= 8"
        in instruction_checks["ck_paint_plan_region_instructions_warnings_bounded"]
    )
    assert (
        "confidence_ppm BETWEEN 0 AND 1000000"
        in instruction_checks["ck_paint_plan_region_instructions_confidence_allowed"]
    )

    review_checks = _checks(PaintPlanReviewEvent.__table__)
    assert "submit" in review_checks["ck_paint_plan_review_events_action_allowed"]
    assert "approve" in review_checks["ck_paint_plan_review_events_action_allowed"]
    assert "reject" in review_checks["ck_paint_plan_review_events_action_allowed"]
    assert (
        "action <> 'reject' OR reason IS NOT NULL"
        in review_checks["ck_paint_plan_review_events_reject_reason_required"]
    )


def test_provider_neutral_usage_cost_and_request_id_envelopes_are_typed() -> None:
    attempt = Base.metadata.tables["invocation_attempts"]
    usage = Base.metadata.tables["ai_usage_ledger"]
    cost = Base.metadata.tables["ai_cost_ledger"]

    assert attempt.c.provider_request_id_status.nullable is False
    assert str(attempt.c.provider_request_id_status.server_default.arg) == "'absent'"
    assert attempt.c.provider_request_id.nullable is True
    assert usage.c.measurement_status.nullable is False
    assert str(usage.c.measurement_status.server_default.arg) == "'measured'"
    assert usage.c.input_units.nullable is True
    assert usage.c.output_units.nullable is True
    assert cost.c.measurement_status.nullable is False
    assert str(cost.c.measurement_status.server_default.arg) == "'measured'"
    assert cost.c.amount_minor_units.nullable is True

    assert (
        "unavailable"
        in _checks(attempt)["ck_invocation_attempts_provider_request_id_status_allowed"]
    )
    assert "unavailable" in _checks(usage)["ck_ai_usage_ledger_measurement_status_allowed"]
    assert "estimated" in _checks(cost)["ck_ai_cost_ledger_measurement_status_allowed"]
    assert (
        "paint_plan_generation"
        in _checks(Base.metadata.tables["invocation_requests"])[
            "ck_invocation_requests_family_allowed"
        ]
    )

    for table_name in (
        "model_definitions",
        "project_model_policies",
        "user_budget_policies",
        "project_budget_policies",
        "user_budget_counters",
        "project_budget_counters",
        "invocation_attempts",
        "budget_reservations",
        "ai_cost_ledger",
    ):
        currency_checks = " ".join(_checks(Base.metadata.tables[table_name]).values())
        assert "USD" in currency_checks
        assert "FIXTURE_CREDITS" in currency_checks


def test_phase3b_migration_identity_and_immutable_seed_contract_are_pinned() -> None:
    migration = _load_migration()

    assert migration.revision == "3b01a1c2d3e4"
    assert migration.down_revision == "3a04fab2e7a5"
    assert str(migration.OPENAI_PROVIDER_ID).startswith("3b")
    assert str(migration.OPENAI_MODEL_ID).startswith("3b")
    assert str(migration.OPENAI_PRICING_ID).startswith("3b")
    assert str(migration.PAINT_PLAN_PROMPT_ID).startswith("3b")
    assert (
        hashlib.sha256(migration.PAINT_PLAN_PROMPT_BODY.encode("utf-8")).hexdigest()
        == migration.PAINT_PLAN_PROMPT_HASH
    )
    assert len(migration.CURRENCY_CHECKS) == 9

    source = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "'openai', 'OpenAI', 'openai_responses', 'provider_managed'" in source
    assert "false, false, 'disabled'" in source
    assert "'gpt-5.4-mini-2026-03-17'" in source
    assert "'per_million_tokens', 75, 450" in source
    assert "'https://openai.com/api/pricing/'" in source
    assert "'paint-plan', 1, 'paint-plan.v1'" in source
    assert "phase3b_reject_immutable_mutation" in source
    assert "phase3b_guard_paint_plan_mutation" in source
    assert "to_jsonb(NEW) - 'lifecycle'" in source
    assert "NEW.lifecycle IN ('under_review','superseded')" in source
    assert "NEW.lifecycle IN ('approved','rejected','superseded')" in source
