"""Phase 3B Paint Plan provenance, typed instructions, and review models."""

# ruff: noqa: E501

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import conv

from creativedeploy_api.db.base import Base

PAINT_PLAN_LIFECYCLES = (
    "generated",
    "edited",
    "under_review",
    "approved",
    "rejected",
    "superseded",
)
PAINT_PLAN_REVISION_KINDS = ("generated", "edited", "regenerated")
PAINT_PLAN_REVIEW_ACTIONS = ("submit", "approve", "reject")
MAX_PAINT_PLAN_INSTRUCTIONS = 128
MAX_PAINT_PLAN_WARNINGS = 8
MAX_PAINT_PLAN_SAFETY_NOTES = 16
PPM_MAX = 1_000_000


def _sql_values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )


def _created_at() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class ProviderPricingSnapshot(Base):
    """One immutable, source-attributed provider/model price contract."""

    __tablename__ = "provider_pricing_snapshots"
    __table_args__ = (
        CheckConstraint(
            "length(provider_key) BETWEEN 1 AND 64 "
            "AND provider_key = btrim(provider_key) "
            "AND provider_key !~ '[<>]' AND provider_key !~ '[[:cntrl:]]'",
            name=conv("ck_provider_pricing_snapshots_provider_key_safe"),
        ),
        CheckConstraint(
            "length(model_id) BETWEEN 1 AND 160 "
            "AND model_id = btrim(model_id) "
            "AND model_id !~ '[<>]' AND model_id !~ '[[:cntrl:]]'",
            name=conv("ck_provider_pricing_snapshots_model_id_safe"),
        ),
        CheckConstraint(
            "length(pricing_version) BETWEEN 1 AND 64 "
            "AND pricing_version = btrim(pricing_version) "
            "AND pricing_version !~ '[<>]' AND pricing_version !~ '[[:cntrl:]]'",
            name=conv("ck_provider_pricing_snapshots_version_safe"),
        ),
        CheckConstraint(
            "currency = 'USD'",
            name=conv("ck_provider_pricing_snapshots_currency_usd"),
        ),
        CheckConstraint(
            "unit_basis = 'per_million_tokens'",
            name=conv("ck_provider_pricing_snapshots_unit_basis_allowed"),
        ),
        CheckConstraint(
            "input_minor_units_per_million >= 0 AND output_minor_units_per_million >= 0",
            name=conv("ck_provider_pricing_snapshots_prices_nonnegative"),
        ),
        CheckConstraint(
            "length(source_url) BETWEEN 1 AND 512 "
            "AND source_url = btrim(source_url) "
            "AND source_url ~ '^https://[^[:space:]<>]+$'",
            name=conv("ck_provider_pricing_snapshots_source_url_safe"),
        ),
        CheckConstraint(
            "effective_at <= captured_at",
            name=conv("ck_provider_pricing_snapshots_time_order"),
        ),
        ForeignKeyConstraint(
            ["provider_definition_id"],
            ["provider_definitions.id"],
            name="fk_provider_pricing_snapshots_provider",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["model_definition_id"],
            ["model_definitions.id"],
            name="fk_provider_pricing_snapshots_model",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "provider_definition_id",
            "model_definition_id",
            "pricing_version",
            name="uq_provider_pricing_snapshots_provider_model_version",
        ),
        UniqueConstraint(
            "id",
            "provider_definition_id",
            "model_definition_id",
            name="uq_provider_pricing_snapshots_exact_model",
        ),
        Index(
            "ix_provider_pricing_snapshots_model_effective",
            "model_definition_id",
            "effective_at",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    provider_definition_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    model_definition_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    provider_key: Mapped[str] = mapped_column(String(64), nullable=False)
    model_id: Mapped[str] = mapped_column(String(160), nullable=False)
    pricing_version: Mapped[str] = mapped_column(String(64), nullable=False)
    currency: Mapped[str] = mapped_column(String(32), nullable=False)
    unit_basis: Mapped[str] = mapped_column(String(32), nullable=False)
    input_minor_units_per_million: Mapped[int] = mapped_column(BigInteger, nullable=False)
    output_minor_units_per_million: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_url: Mapped[str] = mapped_column(String(512), nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = _created_at()


class PromptTemplateDefinition(Base):
    """One immutable prompt body and response-schema contract."""

    __tablename__ = "prompt_template_definitions"
    __table_args__ = (
        CheckConstraint(
            "template_key ~ '^[a-z0-9]+(-[a-z0-9]+)*$'",
            name=conv("ck_prompt_template_definitions_key_format"),
        ),
        CheckConstraint(
            "version >= 1",
            name=conv("ck_prompt_template_definitions_version_positive"),
        ),
        CheckConstraint(
            "schema_version ~ '^[a-z0-9]+(-[a-z0-9]+)*\\.v[1-9][0-9]*$'",
            name=conv("ck_prompt_template_definitions_schema_format"),
        ),
        CheckConstraint(
            "length(template_body) BETWEEN 1 AND 12000 AND template_body = btrim(template_body)",
            name=conv("ck_prompt_template_definitions_body_bounded"),
        ),
        CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$'",
            name=conv("ck_prompt_template_definitions_hash_format"),
        ),
        CheckConstraint(
            "status IN ('active','retired')",
            name=conv("ck_prompt_template_definitions_status_allowed"),
        ),
        UniqueConstraint(
            "template_key",
            "version",
            name="uq_prompt_template_definitions_key_version",
        ),
        UniqueConstraint(
            "id",
            "template_key",
            "version",
            "content_hash",
            "schema_version",
            name="uq_prompt_template_definitions_exact_contract",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    template_key: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    template_body: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = _created_at()


class PaintPlan(Base):
    """One content-immutable revision with a governed lifecycle field."""

    __tablename__ = "paint_plans"
    __table_args__ = (
        CheckConstraint(
            "version >= 1 AND lineage_revision >= 1",
            name=conv("ck_paint_plans_revisions_positive"),
        ),
        CheckConstraint(
            f"revision_kind IN ({_sql_values(PAINT_PLAN_REVISION_KINDS)})",
            name=conv("ck_paint_plans_revision_kind_allowed"),
        ),
        CheckConstraint(
            f"lifecycle IN ({_sql_values(PAINT_PLAN_LIFECYCLES)})",
            name=conv("ck_paint_plans_lifecycle_allowed"),
        ),
        CheckConstraint(
            "(revision_kind = 'generated' AND lineage_revision = 1 "
            "AND lineage_id = id AND parent_plan_id IS NULL) "
            "OR (revision_kind = 'edited' AND lineage_revision >= 2 "
            "AND lineage_id <> id AND parent_plan_id IS NOT NULL) "
            "OR (revision_kind = 'regenerated' AND lineage_revision = 1 "
            "AND lineage_id = id AND parent_plan_id IS NOT NULL)",
            name=conv("ck_paint_plans_lineage_consistent"),
        ),
        CheckConstraint(
            "source_readiness_review_version >= 1 AND source_region_set_version >= 1",
            name=conv("ck_paint_plans_source_versions_positive"),
        ),
        CheckConstraint(
            "source_image_set_fingerprint ~ '^[0-9a-f]{64}$' "
            "AND source_geometry_fingerprint ~ '^[0-9a-f]{64}$'",
            name=conv("ck_paint_plans_source_fingerprints_format"),
        ),
        CheckConstraint(
            "length(provider_key_snapshot) BETWEEN 1 AND 64 "
            "AND provider_key_snapshot = btrim(provider_key_snapshot) "
            "AND length(model_id_snapshot) BETWEEN 1 AND 160 "
            "AND model_id_snapshot = btrim(model_id_snapshot) "
            "AND provider_key_snapshot !~ '[<>]' AND model_id_snapshot !~ '[<>]' "
            "AND provider_key_snapshot !~ '[[:cntrl:]]' "
            "AND model_id_snapshot !~ '[[:cntrl:]]'",
            name=conv("ck_paint_plans_model_snapshots_safe"),
        ),
        CheckConstraint(
            "provider_revision_snapshot >= 1 AND model_revision_snapshot >= 1",
            name=conv("ck_paint_plans_model_revisions_positive"),
        ),
        CheckConstraint(
            "provider_pricing_snapshot_id IS NOT NULL OR provider_key_snapshot = 'fixture_local'",
            name=conv("ck_paint_plans_pricing_snapshot_required"),
        ),
        CheckConstraint(
            "prompt_template_key_snapshot ~ '^[a-z0-9]+(-[a-z0-9]+)*$' "
            "AND prompt_template_version_snapshot >= 1 "
            "AND prompt_content_hash ~ '^[0-9a-f]{64}$' "
            "AND response_schema_version ~ "
            "'^[a-z0-9]+(-[a-z0-9]+)*\\.v[1-9][0-9]*$'",
            name=conv("ck_paint_plans_prompt_contract_format"),
        ),
        CheckConstraint(
            "length(title) BETWEEN 1 AND 160 AND title = btrim(title) "
            "AND title !~ '[<>]' AND title !~ '[[:cntrl:]]'",
            name=conv("ck_paint_plans_title_safe"),
        ),
        CheckConstraint(
            "length(overall_approach) BETWEEN 1 AND 2000 "
            "AND overall_approach = btrim(overall_approach) "
            "AND overall_approach !~ '[<>]' "
            "AND overall_approach !~ '[[:cntrl:]]'",
            name=conv("ck_paint_plans_overall_approach_safe"),
        ),
        CheckConstraint(
            "jsonb_typeof(safety_notes) = 'array' "
            f"AND jsonb_array_length(safety_notes) <= {MAX_PAINT_PLAN_SAFETY_NOTES} "
            "AND octet_length(safety_notes::text) <= 7000 "
            "AND NOT jsonb_path_exists(safety_notes, '$[*] ? (@.type() != \"string\")')",
            name=conv("ck_paint_plans_safety_notes_bounded"),
        ),
        CheckConstraint(
            f"instruction_count BETWEEN 1 AND {MAX_PAINT_PLAN_INSTRUCTIONS}",
            name=conv("ck_paint_plans_instruction_count_allowed"),
        ),
        CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$'",
            name=conv("ck_paint_plans_content_hash_format"),
        ),
        CheckConstraint(
            "created_by_actor_type IN ('provider','user')",
            name=conv("ck_paint_plans_actor_type_allowed"),
        ),
        CheckConstraint(
            "length(created_by_actor_id) BETWEEN 1 AND 128 "
            "AND created_by_actor_id = btrim(created_by_actor_id) "
            "AND created_by_actor_id !~ '[[:cntrl:]]' "
            "AND length(created_by_actor_display_name_snapshot) BETWEEN 1 AND 200 "
            "AND created_by_actor_display_name_snapshot = "
            "btrim(created_by_actor_display_name_snapshot) "
            "AND created_by_actor_display_name_snapshot !~ '[[:cntrl:]]'",
            name=conv("ck_paint_plans_actor_snapshots_safe"),
        ),
        CheckConstraint(
            "(revision_kind = 'edited' AND created_by_actor_type = 'user') "
            "OR (revision_kind IN ('generated','regenerated') "
            "AND created_by_actor_type = 'provider')",
            name=conv("ck_paint_plans_revision_actor_consistent"),
        ),
        ForeignKeyConstraint(
            ["paint_project_id", "owner_principal_id"],
            ["paint_projects.id", "paint_projects.owner_principal_id"],
            name="fk_paint_plans_project_owner",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["source_readiness_review_id"],
            ["image_set_readiness_reviews.id"],
            name="fk_paint_plans_source_readiness_review",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["paint_project_id", "owner_principal_id", "source_region_set_id"],
            ["region_sets.paint_project_id", "region_sets.owner_principal_id", "region_sets.id"],
            name="fk_paint_plans_source_region_set_same_project_owner",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["source_invocation_id"],
            ["invocation_requests.id"],
            name="fk_paint_plans_source_invocation",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["source_invocation_id", "source_attempt_id"],
            ["invocation_attempts.invocation_id", "invocation_attempts.id"],
            name="fk_paint_plans_source_attempt",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["provider_definition_id"],
            ["provider_definitions.id"],
            name="fk_paint_plans_provider",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["model_definition_id"],
            ["model_definitions.id"],
            name="fk_paint_plans_model",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["provider_pricing_snapshot_id", "provider_definition_id", "model_definition_id"],
            [
                "provider_pricing_snapshots.id",
                "provider_pricing_snapshots.provider_definition_id",
                "provider_pricing_snapshots.model_definition_id",
            ],
            name="fk_paint_plans_pricing_snapshot_exact_model",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "prompt_template_definition_id",
                "prompt_template_key_snapshot",
                "prompt_template_version_snapshot",
                "prompt_content_hash",
                "response_schema_version",
            ],
            [
                "prompt_template_definitions.id",
                "prompt_template_definitions.template_key",
                "prompt_template_definitions.version",
                "prompt_template_definitions.content_hash",
                "prompt_template_definitions.schema_version",
            ],
            name="fk_paint_plans_prompt_exact_contract",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["paint_project_id", "owner_principal_id", "lineage_id"],
            ["paint_plans.paint_project_id", "paint_plans.owner_principal_id", "paint_plans.id"],
            name="fk_paint_plans_lineage_same_project_owner",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["paint_project_id", "owner_principal_id", "parent_plan_id"],
            ["paint_plans.paint_project_id", "paint_plans.owner_principal_id", "paint_plans.id"],
            name="fk_paint_plans_parent_same_project_owner",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "paint_project_id",
            "owner_principal_id",
            "id",
            name="uq_paint_plans_project_owner_id",
        ),
        UniqueConstraint(
            "paint_project_id",
            "version",
            name="uq_paint_plans_project_version",
        ),
        UniqueConstraint(
            "lineage_id",
            "lineage_revision",
            name="uq_paint_plans_lineage_revision",
        ),
        UniqueConstraint(
            "id",
            "source_region_set_id",
            name="uq_paint_plans_id_region_set",
        ),
        UniqueConstraint(
            "id",
            "version",
            "paint_project_id",
            "owner_principal_id",
            name="uq_paint_plans_exact_revision",
        ),
        Index(
            "ix_paint_plans_owner_project_version",
            "owner_principal_id",
            "paint_project_id",
            "version",
        ),
        Index("ix_paint_plans_lineage_revision", "lineage_id", "lineage_revision"),
        Index("ix_paint_plans_source_invocation", "source_invocation_id"),
        Index(
            "uq_paint_plans_one_current_per_project",
            "paint_project_id",
            unique=True,
            postgresql_where=text("lifecycle <> 'superseded'"),
        ),
        Index(
            "uq_paint_plans_generated_attempt",
            "source_attempt_id",
            unique=True,
            postgresql_where=text("revision_kind IN ('generated','regenerated')"),
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    owner_principal_id: Mapped[str] = mapped_column(String(128), nullable=False)
    paint_project_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    lineage_id: Mapped[uuid.UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    lineage_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    revision_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    lifecycle: Mapped[str] = mapped_column(String(32), nullable=False)
    parent_plan_id: Mapped[uuid.UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    source_readiness_review_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    source_readiness_review_version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_image_set_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    source_region_set_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    source_region_set_version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_geometry_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    source_invocation_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    source_attempt_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    provider_definition_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    provider_key_snapshot: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_revision_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    model_definition_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    model_id_snapshot: Mapped[str] = mapped_column(String(160), nullable=False)
    model_revision_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    provider_pricing_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True)
    )
    prompt_template_definition_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    prompt_template_key_snapshot: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_template_version_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    overall_approach: Mapped[str] = mapped_column(String(2000), nullable=False)
    safety_notes: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    instruction_count: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by_actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    created_by_actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_by_actor_display_name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = _created_at()


class PaintPlanRegionInstruction(Base):
    """One immutable typed instruction bound to one exact paint Region."""

    __tablename__ = "paint_plan_region_instructions"
    __table_args__ = (
        CheckConstraint(
            "region_kind_snapshot = 'paint'",
            name=conv("ck_paint_plan_region_instructions_kind_paint"),
        ),
        CheckConstraint(
            "sequence BETWEEN 0 AND 127",
            name=conv("ck_paint_plan_region_instructions_sequence_allowed"),
        ),
        CheckConstraint(
            "length(region_label_snapshot) BETWEEN 1 AND 80 "
            "AND region_label_snapshot = btrim(region_label_snapshot) "
            "AND region_label_snapshot !~ '[<>]' "
            "AND region_label_snapshot !~ '[[:cntrl:]]'",
            name=conv("ck_paint_plan_region_instructions_label_safe"),
        ),
        CheckConstraint(
            "length(target_color) BETWEEN 1 AND 120 AND target_color = btrim(target_color) "
            "AND length(preparation) BETWEEN 1 AND 600 AND preparation = btrim(preparation) "
            "AND length(base_coat) BETWEEN 1 AND 600 AND base_coat = btrim(base_coat) "
            "AND length(layer_strategy) BETWEEN 1 AND 1000 AND layer_strategy = btrim(layer_strategy) "
            "AND length(edge_treatment) BETWEEN 1 AND 600 AND edge_treatment = btrim(edge_treatment) "
            "AND length(lighting_guidance) BETWEEN 1 AND 600 AND lighting_guidance = btrim(lighting_guidance) "
            "AND length(material_guidance) BETWEEN 1 AND 600 AND material_guidance = btrim(material_guidance) "
            "AND target_color !~ '[<>]' AND preparation !~ '[<>]' "
            "AND base_coat !~ '[<>]' AND layer_strategy !~ '[<>]' "
            "AND edge_treatment !~ '[<>]' AND lighting_guidance !~ '[<>]' "
            "AND material_guidance !~ '[<>]' "
            "AND target_color !~ '[[:cntrl:]]' AND preparation !~ '[[:cntrl:]]' "
            "AND base_coat !~ '[[:cntrl:]]' AND layer_strategy !~ '[[:cntrl:]]' "
            "AND edge_treatment !~ '[[:cntrl:]]' "
            "AND lighting_guidance !~ '[[:cntrl:]]' "
            "AND material_guidance !~ '[[:cntrl:]]'",
            name=conv("ck_paint_plan_region_instructions_text_safe"),
        ),
        CheckConstraint(
            "jsonb_typeof(warnings) = 'array' "
            f"AND jsonb_array_length(warnings) <= {MAX_PAINT_PLAN_WARNINGS} "
            "AND octet_length(warnings::text) <= 2200 "
            "AND NOT jsonb_path_exists(warnings, '$[*] ? (@.type() != \"string\")')",
            name=conv("ck_paint_plan_region_instructions_warnings_bounded"),
        ),
        CheckConstraint(
            f"confidence_ppm BETWEEN 0 AND {PPM_MAX}",
            name=conv("ck_paint_plan_region_instructions_confidence_allowed"),
        ),
        ForeignKeyConstraint(
            ["paint_plan_id", "region_set_id"],
            ["paint_plans.id", "paint_plans.source_region_set_id"],
            name="fk_paint_plan_region_instructions_plan_region_set",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["region_id", "region_set_id"],
            ["regions.id", "regions.region_set_id"],
            name="fk_paint_plan_region_instructions_region_same_set",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "paint_plan_id",
            "region_id",
            name="uq_paint_plan_region_instructions_plan_region",
        ),
        UniqueConstraint(
            "paint_plan_id",
            "stable_region_key",
            name="uq_paint_plan_region_instructions_plan_stable_key",
        ),
        UniqueConstraint(
            "paint_plan_id",
            "sequence",
            name="uq_paint_plan_region_instructions_plan_sequence",
        ),
        Index(
            "ix_paint_plan_region_instructions_plan_sequence",
            "paint_plan_id",
            "sequence",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    paint_plan_id: Mapped[uuid.UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    region_set_id: Mapped[uuid.UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    region_id: Mapped[uuid.UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    stable_region_key: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    region_label_snapshot: Mapped[str] = mapped_column(String(80), nullable=False)
    region_kind_snapshot: Mapped[str] = mapped_column(String(16), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    target_color: Mapped[str] = mapped_column(String(120), nullable=False)
    preparation: Mapped[str] = mapped_column(String(600), nullable=False)
    base_coat: Mapped[str] = mapped_column(String(600), nullable=False)
    layer_strategy: Mapped[str] = mapped_column(String(1000), nullable=False)
    edge_treatment: Mapped[str] = mapped_column(String(600), nullable=False)
    lighting_guidance: Mapped[str] = mapped_column(String(600), nullable=False)
    material_guidance: Mapped[str] = mapped_column(String(600), nullable=False)
    warnings: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    confidence_ppm: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = _created_at()


class PaintPlanReviewEvent(Base):
    """One append-only human action bound to one exact Paint Plan revision."""

    __tablename__ = "paint_plan_review_events"
    __table_args__ = (
        CheckConstraint(
            f"action IN ({_sql_values(PAINT_PLAN_REVIEW_ACTIONS)})",
            name=conv("ck_paint_plan_review_events_action_allowed"),
        ),
        CheckConstraint(
            "paint_plan_version >= 1",
            name=conv("ck_paint_plan_review_events_version_positive"),
        ),
        CheckConstraint(
            "reason IS NULL OR (length(reason) BETWEEN 1 AND 1000 "
            "AND reason = btrim(reason) AND reason !~ '[[:cntrl:]]')",
            name=conv("ck_paint_plan_review_events_reason_safe"),
        ),
        CheckConstraint(
            "action <> 'reject' OR reason IS NOT NULL",
            name=conv("ck_paint_plan_review_events_reject_reason_required"),
        ),
        CheckConstraint(
            "length(actor_principal_id) BETWEEN 1 AND 128 "
            "AND actor_principal_id = btrim(actor_principal_id) "
            "AND actor_principal_id !~ '[[:cntrl:]]' "
            "AND length(actor_display_name_snapshot) BETWEEN 1 AND 200 "
            "AND actor_display_name_snapshot = btrim(actor_display_name_snapshot) "
            "AND actor_display_name_snapshot !~ '[[:cntrl:]]'",
            name=conv("ck_paint_plan_review_events_actor_safe"),
        ),
        ForeignKeyConstraint(
            ["actor_user_id"],
            ["user_accounts.id"],
            name="fk_paint_plan_review_events_actor_user",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["paint_plan_id", "paint_plan_version", "paint_project_id", "owner_principal_id"],
            [
                "paint_plans.id",
                "paint_plans.version",
                "paint_plans.paint_project_id",
                "paint_plans.owner_principal_id",
            ],
            name="fk_paint_plan_review_events_exact_revision",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "paint_plan_id",
            "action",
            name="uq_paint_plan_review_events_plan_action",
        ),
        Index(
            "uq_paint_plan_review_events_decision",
            "paint_plan_id",
            unique=True,
            postgresql_where=text("action IN ('approve','reject')"),
        ),
        Index(
            "ix_paint_plan_review_events_owner_project_created",
            "owner_principal_id",
            "paint_project_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    owner_principal_id: Mapped[str] = mapped_column(String(128), nullable=False)
    paint_project_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    paint_plan_id: Mapped[uuid.UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    paint_plan_version: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    actor_principal_id: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_display_name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = _created_at()
