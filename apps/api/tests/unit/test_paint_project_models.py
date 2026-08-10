"""Contract tests for the Phase 1D-1B ORM metadata."""

import ast
import importlib.util
import re
import subprocess
import sys
import uuid
from collections.abc import Iterable
from pathlib import Path
from types import MappingProxyType

import pytest
from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, Index, MetaData, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.schema import Table, UniqueConstraint

from creativedeploy_api.db import Base
from creativedeploy_api.db.models import (
    REGISTERED_MODELS,
    AIAuditEvent,
    AICommandIdempotencyRecord,
    AICostLedger,
    AIInvocationEvent,
    AIUsageLedger,
    AuthSession,
    BudgetReservation,
    CapabilityDefinition,
    CommandIdempotencyRecord,
    CredentialProjectGrant,
    CredentialRecord,
    ExternalIdentity,
    ImageAsset,
    ImageSetReadinessReview,
    InvocationAttempt,
    InvocationRequest,
    ModelCapability,
    ModelDefinition,
    OidcLoginFlow,
    PaintPlan,
    PaintPlanRegionInstruction,
    PaintPlanReviewEvent,
    PaintProject,
    ProjectBudgetCounter,
    ProjectBudgetPolicy,
    ProjectMembership,
    ProjectModelPolicy,
    ProjectModelPolicyCapability,
    ProjectModelPolicyCredential,
    ProjectModelPolicyModel,
    ProjectModelPolicyProvider,
    PromptTemplateDefinition,
    ProviderCapability,
    ProviderDefinition,
    ProviderPricingSnapshot,
    Region,
    RegionSet,
    RegionSetReview,
    RegionVertex,
    StateTransitionEvent,
    UserAccount,
    UserBudgetCounter,
    UserBudgetPolicy,
    UserProviderPreference,
)
from creativedeploy_api.db.models.constants import (
    ACTOR_TYPES,
    IDEMPOTENCY_STATUS_COMPLETED,
    IDEMPOTENCY_STATUS_IN_PROGRESS,
    MACHINE_TOKEN_PATTERN,
    PAYLOAD_HASH_PATTERN,
    PHYSICAL_STRING_LENGTHS,
    PLANNING_MODE_DEMO,
    POSTGRESQL_MACHINE_TOKEN_PATTERN,
    TARGET_STYLE_CEL_SHADING,
    WORKFLOW_STATES,
)

EXPECTED_PHASE_1F_MODELS = frozenset(
    {
        PaintProject,
        StateTransitionEvent,
        CommandIdempotencyRecord,
        ImageAsset,
        ImageSetReadinessReview,
        UserAccount,
        ExternalIdentity,
        ProjectMembership,
        OidcLoginFlow,
        AuthSession,
        RegionSet,
        Region,
        RegionVertex,
        RegionSetReview,
    }
)
EXPECTED_PHASE_3A_MODELS = frozenset(
    {
        ProviderDefinition,
        CapabilityDefinition,
        ModelDefinition,
        ProviderCapability,
        ModelCapability,
        CredentialRecord,
        CredentialProjectGrant,
        UserProviderPreference,
        ProjectModelPolicy,
        ProjectModelPolicyProvider,
        ProjectModelPolicyModel,
        ProjectModelPolicyCapability,
        ProjectModelPolicyCredential,
        UserBudgetPolicy,
        ProjectBudgetPolicy,
        UserBudgetCounter,
        ProjectBudgetCounter,
        InvocationRequest,
        InvocationAttempt,
        BudgetReservation,
        AIInvocationEvent,
        AIUsageLedger,
        AICostLedger,
        AIAuditEvent,
        AICommandIdempotencyRecord,
    }
)
EXPECTED_PHASE_3B_MODELS = frozenset(
    {
        ProviderPricingSnapshot,
        PromptTemplateDefinition,
        PaintPlan,
        PaintPlanRegionInstruction,
        PaintPlanReviewEvent,
    }
)

EXPECTED_PHASE_1F_TABLES = frozenset(
    {
        "auth_sessions",
        "command_idempotency_records",
        "external_identities",
        "image_assets",
        "image_set_readiness_reviews",
        "paint_projects",
        "oidc_login_flows",
        "project_memberships",
        "region_set_reviews",
        "region_sets",
        "region_vertices",
        "regions",
        "state_transition_events",
        "user_accounts",
    }
)
EXPECTED_PHASE_1F_CONSTRAINT_NAMES = frozenset(
    {
        "ck_command_idempotency_records_command_type_format",
        "ck_auth_sessions_expiry_after_creation",
        "ck_auth_sessions_last_seen_not_before_creation",
        "ck_external_identities_issuer_normalized",
        "ck_external_identities_subject_normalized",
        "ck_oidc_login_flows_expiry_after_creation",
        "ck_project_memberships_role_allowed",
        "ck_user_accounts_display_name_normalized",
        "ck_user_accounts_email_normalized",
        "ck_user_accounts_updated_at_not_before_created_at",
        "ck_command_idempotency_records_execution_status_allowed",
        "ck_command_idempotency_records_execution_status_format",
        "ck_command_idempotency_records_expiry_after_creation",
        "ck_command_idempotency_records_http_status_valid",
        "ck_command_idempotency_records_payload_hash_format",
        "ck_command_idempotency_records_principal_id_normalized",
        "ck_command_idempotency_records_resource_type_format",
        "ck_command_idempotency_records_response_snapshot_is_object",
        "ck_command_idempotency_records_result_matches_execution_status",
        "ck_command_idempotency_records_scope_key_normalized",
        "ck_image_assets_byte_size_allowed",
        "ck_image_assets_created_by_actor_id_normalized",
        "ck_image_assets_created_by_actor_type_allowed",
        "ck_image_assets_created_by_display_normalized",
        "ck_image_assets_current_lifecycle_consistent",
        "ck_image_assets_declared_type_matches_format",
        "ck_image_assets_detected_format_allowed",
        "ck_image_assets_dimensions_allowed",
        "ck_image_assets_exif_orientation_allowed",
        "ck_image_assets_intended_usage_allowed",
        "ck_image_assets_lifecycle_status_allowed",
        "ck_image_assets_original_filename_safe",
        "ck_image_assets_pixel_count_allowed",
        "ck_image_assets_rights_actor_required",
        "ck_image_assets_rights_status_allowed",
        "ck_image_assets_rights_version_positive",
        "ck_image_assets_role_allowed",
        "ck_image_assets_sha256_format",
        "ck_image_assets_source_type_allowed",
        "ck_image_assets_storage_key_format",
        "ck_image_assets_storage_provider_allowed",
        "ck_image_assets_upload_validation_details_is_object",
        "ck_image_assets_upload_validation_result_allowed",
        "ck_image_assets_version_positive",
        "ck_image_set_readiness_reviews_actor_display_normalized",
        "ck_image_set_readiness_reviews_actor_id_normalized",
        "ck_image_set_readiness_reviews_actor_type_allowed",
        "ck_image_set_readiness_reviews_fingerprint_format",
        "ck_image_set_readiness_reviews_not_ready_reason_required",
        "ck_image_set_readiness_reviews_primary_front_role",
        "ck_image_set_readiness_reviews_ready_required_assets",
        "ck_image_set_readiness_reviews_reason_normalized",
        "ck_image_set_readiness_reviews_reference_angle_role",
        "ck_image_set_readiness_reviews_reference_back_role",
        "ck_image_set_readiness_reviews_reference_detail_role",
        "ck_image_set_readiness_reviews_verdict_allowed",
        "ck_image_set_readiness_reviews_version_positive",
        "ck_paint_projects_description_normalized",
        "ck_paint_projects_owner_principal_id_normalized",
        "ck_paint_projects_planning_mode_allowed",
        "ck_paint_projects_planning_mode_format",
        "ck_paint_projects_requested_target_style_allowed",
        "ck_paint_projects_requested_target_style_format",
        "ck_paint_projects_status_allowed",
        "ck_paint_projects_title_normalized",
        "ck_paint_projects_title_not_blank",
        "ck_paint_projects_updated_at_not_before_created_at",
        "ck_region_set_reviews_actor_display_normalized",
        "ck_region_set_reviews_actor_id_normalized",
        "ck_region_set_reviews_actor_type_allowed",
        "ck_region_set_reviews_changes_reason_required",
        "ck_region_set_reviews_reason_normalized",
        "ck_region_set_reviews_verdict_allowed",
        "ck_region_set_reviews_version_positive",
        "ck_region_sets_counts_consistent",
        "ck_region_sets_created_by_actor_id_normalized",
        "ck_region_sets_created_by_actor_type_allowed",
        "ck_region_sets_created_by_display_normalized",
        "ck_region_sets_geometry_fingerprint_format",
        "ck_region_sets_lifecycle_allowed",
        "ck_region_sets_region_count_allowed",
        "ck_region_sets_source_dimensions_allowed",
        "ck_region_sets_source_fingerprint_format",
        "ck_region_sets_source_primary_role",
        "ck_region_sets_total_vertex_count_allowed",
        "ck_region_sets_version_positive",
        "ck_region_vertices_coordinates_allowed",
        "ck_region_vertices_sequence_allowed",
        "ck_regions_area_positive",
        "ck_regions_bbox_allowed",
        "ck_regions_kind_allowed",
        "ck_regions_label_safe",
        "ck_regions_normalized_label_safe",
        "ck_regions_notes_safe",
        "ck_regions_opacity_ppm_allowed",
        "ck_regions_vertex_count_allowed",
        "ck_regions_z_index_allowed",
        "ck_state_transition_events_actor_display_snapshot_normalized",
        "ck_state_transition_events_actor_principal_id_normalized",
        "ck_state_transition_events_actor_type_allowed",
        "ck_state_transition_events_actor_type_format",
        "ck_state_transition_events_create_project_reason",
        "ck_state_transition_events_event_format",
        "ck_state_transition_events_event_metadata_is_object",
        "ck_state_transition_events_from_state_allowed",
        "ck_state_transition_events_reason_format",
        "ck_state_transition_events_to_state_allowed",
        "ck_state_transition_events_user_display_name_required",
        "fk_state_transition_events_project_id_paint_projects",
        "fk_auth_sessions_user_id_user_accounts",
        "fk_external_identities_user_id_user_accounts",
        "fk_image_assets_project_owner_paint_projects",
        "fk_image_assets_supersedes_same_owner_project_role",
        "fk_image_set_readiness_reviews_primary_front_asset",
        "fk_image_set_readiness_reviews_project_owner_paint_projects",
        "fk_image_set_readiness_reviews_reference_angle_asset",
        "fk_image_set_readiness_reviews_reference_back_asset",
        "fk_image_set_readiness_reviews_reference_detail_asset",
        "fk_paint_projects_current_image_asset_same_owner_project",
        "fk_project_memberships_assigned_by_user_accounts",
        "fk_project_memberships_project_paint_projects",
        "fk_project_memberships_user_user_accounts",
        "fk_region_set_reviews_region_set_same_owner_project",
        "fk_region_sets_based_on_same_owner_project",
        "fk_region_sets_project_owner_paint_projects",
        "fk_region_sets_source_primary_image_asset",
        "fk_region_sets_supersedes_same_owner_project",
        "fk_region_vertices_region_same_set",
        "fk_regions_region_set_same_owner_project",
        "pk_command_idempotency_records",
        "pk_auth_sessions",
        "pk_external_identities",
        "pk_image_assets",
        "pk_image_set_readiness_reviews",
        "pk_paint_projects",
        "pk_oidc_login_flows",
        "pk_project_memberships",
        "pk_region_set_reviews",
        "pk_region_sets",
        "pk_region_vertices",
        "pk_regions",
        "pk_state_transition_events",
        "pk_user_accounts",
        "uq_auth_sessions_token_hash",
        "uq_command_idempotency_records_scope_key_idempotency_key",
        "uq_external_identities_issuer_subject",
        "uq_image_assets_id_project_owner_role",
        "uq_image_assets_project_owner_id",
        "uq_image_assets_project_role_version",
        "uq_image_assets_storage_key",
        "uq_image_set_readiness_reviews_project_version",
        "uq_paint_projects_id_owner_principal_id",
        "uq_oidc_login_flows_state_hash",
        "uq_project_memberships_project_user",
        "uq_region_set_reviews_project_version",
        "uq_region_set_reviews_region_set",
        "uq_region_sets_project_owner_id",
        "uq_region_sets_project_version",
        "uq_regions_id_region_set",
        "uq_regions_region_set_stable_key",
        "uq_regions_region_set_z_index",
    }
)
EXPECTED_PHASE_1F_INDEX_NAMES = frozenset(
    {
        "ix_auth_sessions_user_expires_at",
        "ix_command_idempotency_records_expires_at",
        "ix_external_identities_user_id",
        "ix_image_assets_owner_project_created_at",
        "ix_image_set_readiness_reviews_owner_project_created_at",
        "ix_paint_projects_owner_updated_at_id",
        "ix_oidc_login_flows_expires_at",
        "ix_project_memberships_user_project",
        "ix_region_set_reviews_owner_project_created_at",
        "ix_region_sets_owner_project_version",
        "ix_region_vertices_region_set_region_sequence",
        "ix_regions_region_set_z_index",
        "ix_state_transition_events_project_created_at_id",
        "uq_image_assets_project_role_current",
    }
)
EXPECTED_PHASE_3A_TABLES = frozenset(
    {
        "ai_audit_events",
        "ai_command_idempotency_records",
        "ai_cost_ledger",
        "ai_invocation_events",
        "ai_usage_ledger",
        "budget_reservations",
        "capability_definitions",
        "credential_project_grants",
        "credential_records",
        "invocation_attempts",
        "invocation_requests",
        "model_capabilities",
        "model_definitions",
        "project_budget_counters",
        "project_budget_policies",
        "project_model_policies",
        "project_model_policy_capabilities",
        "project_model_policy_credentials",
        "project_model_policy_models",
        "project_model_policy_providers",
        "provider_capabilities",
        "provider_definitions",
        "user_budget_counters",
        "user_budget_policies",
        "user_provider_preferences",
    }
)
EXPECTED_PHASE_3B_TABLES = frozenset(
    {
        "provider_pricing_snapshots",
        "prompt_template_definitions",
        "paint_plans",
        "paint_plan_region_instructions",
        "paint_plan_review_events",
    }
)
EXPECTED_PHASE_3A_CHECK_CONSTRAINT_NAMES = frozenset(
    {
        "ck_ai_cost_ledger_fixture_currency_only",
        "ck_ai_cost_ledger_measurement_consistent",
        "ck_ai_cost_ledger_measurement_status_allowed",
        "ck_ai_usage_ledger_measurement_consistent",
        "ck_ai_usage_ledger_measurement_status_allowed",
        "ck_budget_reservations_fixture_currency_only",
        "ck_budget_reservations_state_allowed",
        "ck_capability_definitions_status_allowed",
        "ck_credential_records_lifecycle_envelope",
        "ck_credential_records_no_self_replacement",
        "ck_credential_records_status_allowed",
        "ck_invocation_attempts_fixture_currency_only",
        "ck_invocation_attempts_provider_request_id_consistent",
        "ck_invocation_attempts_provider_request_id_status_allowed",
        "ck_invocation_attempts_status_allowed",
        "ck_invocation_requests_canonicalization_version",
        "ck_invocation_requests_family_allowed",
        "ck_invocation_requests_final_attempt_success_only",
        "ck_invocation_requests_payload_hash",
        "ck_invocation_requests_project_scope",
        "ck_invocation_requests_status_allowed",
        "ck_model_definitions_fixture_currency_only",
        "ck_model_definitions_status_allowed",
        "ck_paint_projects_id_not_zero_uuid",
        "ck_project_budget_counters_fixture_currency_only",
        "ck_project_budget_counters_nonnegative",
        "ck_project_budget_policies_fixture_currency_only",
        "ck_project_model_policies_fallback_disabled",
        "ck_project_model_policies_fixture_currency_only",
        "ck_provider_definitions_base_url_policy_allowed",
        "ck_provider_definitions_catalog_mode_allowed",
        "ck_provider_definitions_status_allowed",
        "ck_user_budget_counters_fixture_currency_only",
        "ck_user_budget_counters_nonnegative",
        "ck_user_budget_policies_fixture_currency_only",
    }
)
EXPECTED_PHASE_3A_FOREIGN_KEY_NAMES = frozenset(
    {
        "fk_ai_audit_events_actor",
        "fk_ai_audit_events_attempt",
        "fk_ai_audit_events_credential",
        "fk_ai_audit_events_invocation",
        "fk_ai_audit_events_model",
        "fk_ai_audit_events_project",
        "fk_ai_audit_events_provider",
        "fk_ai_command_idempotency_user",
        "fk_ai_cost_ledger_attempt",
        "fk_ai_cost_ledger_invocation",
        "fk_ai_cost_ledger_model",
        "fk_ai_cost_ledger_provider",
        "fk_ai_invocation_events_attempt",
        "fk_ai_invocation_events_invocation",
        "fk_ai_usage_ledger_attempt",
        "fk_ai_usage_ledger_invocation",
        "fk_ai_usage_ledger_model",
        "fk_ai_usage_ledger_provider",
        "fk_budget_reservations_attempt",
        "fk_budget_reservations_invocation",
        "fk_budget_reservations_project_counter",
        "fk_budget_reservations_user_counter",
        "fk_credential_project_grants_credential_credential_records",
        "fk_credential_project_grants_granted_by_user_accounts",
        "fk_credential_project_grants_project_paint_projects",
        "fk_credential_records_owner_user_accounts",
        "fk_credential_records_provider_provider_definitions",
        "fk_credential_records_replaces_credential_records",
        "fk_invocation_attempts_credential",
        "fk_invocation_attempts_invocation",
        "fk_invocation_attempts_model",
        "fk_invocation_attempts_provider",
        "fk_invocation_attempts_retry_of_attempt_id_invocation_attempts",
        "fk_invocation_requests_final_attempt",
        "fk_invocation_requests_project",
        "fk_invocation_requests_user",
        "fk_invreq_requested_credential",
        "fk_invreq_requested_model_definition",
        "fk_invreq_requested_provider_definition",
        "fk_model_capabilities_capability_capability_definitions",
        "fk_model_capabilities_model_model_definitions",
        "fk_model_definitions_provider_provider_definitions",
        "fk_policy_capabilities_capability",
        "fk_policy_capabilities_policy",
        "fk_policy_credentials_credential",
        "fk_policy_credentials_policy",
        "fk_policy_models_model",
        "fk_policy_models_policy",
        "fk_policy_providers_policy",
        "fk_policy_providers_provider",
        "fk_project_budget_counters_project",
        "fk_project_budget_policies_project",
        "fk_project_model_policies_credential",
        "fk_project_model_policies_model",
        "fk_project_model_policies_project",
        "fk_project_model_policies_provider",
        "fk_project_model_policies_updated_by",
        "fk_provider_capabilities_capability_capability_definitions",
        "fk_provider_capabilities_provider_provider_definitions",
        "fk_user_budget_counters_user",
        "fk_user_budget_policies_user",
        "fk_user_provider_preferences_credential",
        "fk_user_provider_preferences_model",
        "fk_user_provider_preferences_provider",
        "fk_user_provider_preferences_user",
    }
)
EXPECTED_PHASE_3A_UNIQUE_CONSTRAINT_NAMES = frozenset(
    {
        "uq_ai_command_idempotency_scope",
        "uq_ai_cost_ledger_dedupe",
        "uq_ai_usage_ledger_dedupe",
        "uq_budget_reservations_attempt",
        "uq_capability_definitions_capability_key",
        "uq_credential_records_replacement_lineage",
        "uq_invocation_attempts_invocation_id",
        "uq_invocation_attempts_number",
        "uq_invocation_requests_idempotency_scope",
        "uq_model_capabilities_model_capability",
        "uq_model_definitions_provider_model",
        "uq_policy_capabilities_pair",
        "uq_policy_credentials_pair",
        "uq_policy_models_pair",
        "uq_policy_providers_pair",
        "uq_project_budget_counters_window",
        "uq_project_budget_policies_scope",
        "uq_project_model_policies_project",
        "uq_provider_capabilities_provider_capability",
        "uq_provider_definitions_provider_key",
        "uq_user_budget_counters_window",
        "uq_user_budget_policies_scope",
        "uq_user_provider_preferences_user",
    }
)
EXPECTED_PHASE_3A_PRIMARY_KEY_NAMES = frozenset(
    f"pk_{table_name}" for table_name in EXPECTED_PHASE_3A_TABLES
)
EXPECTED_PHASE_3A_CONSTRAINT_NAMES = (
    EXPECTED_PHASE_3A_CHECK_CONSTRAINT_NAMES
    | EXPECTED_PHASE_3A_FOREIGN_KEY_NAMES
    | EXPECTED_PHASE_3A_UNIQUE_CONSTRAINT_NAMES
    | EXPECTED_PHASE_3A_PRIMARY_KEY_NAMES
)
EXPECTED_PHASE_3A_INDEX_NAMES = frozenset(
    {
        "ix_ai_audit_events_actor_created",
        "ix_ai_audit_events_project_created",
        "ix_ai_invocation_events_invocation_created",
        "ix_credential_project_grants_project",
        "ix_credential_records_owner_status",
        "ix_invocation_requests_project_created",
        "ix_invocation_requests_user_created",
        "ix_model_capabilities_capability",
        "ix_model_definitions_provider_status",
        "ix_policy_capabilities_capability",
        "ix_policy_credentials_credential",
        "ix_policy_models_model",
        "ix_policy_providers_provider",
        "ix_provider_capabilities_capability",
        "uq_credential_project_grants_active",
        "uq_invocation_attempts_active",
    }
)
EXPECTED_PHASE_3B_CHECK_CONSTRAINT_NAMES = frozenset(
    {
        "ck_paint_plan_region_instructions_confidence_allowed",
        "ck_paint_plan_region_instructions_kind_paint",
        "ck_paint_plan_region_instructions_label_safe",
        "ck_paint_plan_region_instructions_sequence_allowed",
        "ck_paint_plan_region_instructions_text_safe",
        "ck_paint_plan_region_instructions_warnings_bounded",
        "ck_paint_plan_review_events_action_allowed",
        "ck_paint_plan_review_events_actor_safe",
        "ck_paint_plan_review_events_reason_safe",
        "ck_paint_plan_review_events_reject_reason_required",
        "ck_paint_plan_review_events_version_positive",
        "ck_paint_plans_actor_snapshots_safe",
        "ck_paint_plans_actor_type_allowed",
        "ck_paint_plans_content_hash_format",
        "ck_paint_plans_instruction_count_allowed",
        "ck_paint_plans_lifecycle_allowed",
        "ck_paint_plans_lineage_consistent",
        "ck_paint_plans_model_revisions_positive",
        "ck_paint_plans_model_snapshots_safe",
        "ck_paint_plans_overall_approach_safe",
        "ck_paint_plans_pricing_snapshot_required",
        "ck_paint_plans_prompt_contract_format",
        "ck_paint_plans_revision_actor_consistent",
        "ck_paint_plans_revision_kind_allowed",
        "ck_paint_plans_revisions_positive",
        "ck_paint_plans_safety_notes_bounded",
        "ck_paint_plans_source_fingerprints_format",
        "ck_paint_plans_source_versions_positive",
        "ck_paint_plans_title_safe",
        "ck_prompt_template_definitions_body_bounded",
        "ck_prompt_template_definitions_hash_format",
        "ck_prompt_template_definitions_key_format",
        "ck_prompt_template_definitions_schema_format",
        "ck_prompt_template_definitions_status_allowed",
        "ck_prompt_template_definitions_version_positive",
        "ck_provider_pricing_snapshots_currency_usd",
        "ck_provider_pricing_snapshots_model_id_safe",
        "ck_provider_pricing_snapshots_prices_nonnegative",
        "ck_provider_pricing_snapshots_provider_key_safe",
        "ck_provider_pricing_snapshots_source_url_safe",
        "ck_provider_pricing_snapshots_time_order",
        "ck_provider_pricing_snapshots_unit_basis_allowed",
        "ck_provider_pricing_snapshots_version_safe",
    }
)
EXPECTED_PHASE_3B_FOREIGN_KEY_NAMES = frozenset(
    {
        "fk_paint_plan_region_instructions_plan_region_set",
        "fk_paint_plan_region_instructions_region_same_set",
        "fk_paint_plan_review_events_actor_user",
        "fk_paint_plan_review_events_exact_revision",
        "fk_paint_plans_lineage_same_project_owner",
        "fk_paint_plans_model",
        "fk_paint_plans_parent_same_project_owner",
        "fk_paint_plans_pricing_snapshot_exact_model",
        "fk_paint_plans_project_owner",
        "fk_paint_plans_prompt_exact_contract",
        "fk_paint_plans_provider",
        "fk_paint_plans_source_attempt",
        "fk_paint_plans_source_invocation",
        "fk_paint_plans_source_readiness_review",
        "fk_paint_plans_source_region_set_same_project_owner",
        "fk_provider_pricing_snapshots_model",
        "fk_provider_pricing_snapshots_provider",
    }
)
EXPECTED_PHASE_3B_UNIQUE_CONSTRAINT_NAMES = frozenset(
    {
        "uq_paint_plan_region_instructions_plan_region",
        "uq_paint_plan_region_instructions_plan_sequence",
        "uq_paint_plan_region_instructions_plan_stable_key",
        "uq_paint_plan_review_events_plan_action",
        "uq_paint_plans_exact_revision",
        "uq_paint_plans_id_region_set",
        "uq_paint_plans_lineage_revision",
        "uq_paint_plans_project_owner_id",
        "uq_paint_plans_project_version",
        "uq_prompt_template_definitions_exact_contract",
        "uq_prompt_template_definitions_key_version",
        "uq_provider_pricing_snapshots_exact_model",
        "uq_provider_pricing_snapshots_provider_model_version",
    }
)
EXPECTED_PHASE_3B_PRIMARY_KEY_NAMES = frozenset(
    f"pk_{table_name}" for table_name in EXPECTED_PHASE_3B_TABLES
)
EXPECTED_PHASE_3B_CONSTRAINT_NAMES = (
    EXPECTED_PHASE_3B_CHECK_CONSTRAINT_NAMES
    | EXPECTED_PHASE_3B_FOREIGN_KEY_NAMES
    | EXPECTED_PHASE_3B_UNIQUE_CONSTRAINT_NAMES
    | EXPECTED_PHASE_3B_PRIMARY_KEY_NAMES
)
EXPECTED_PHASE_3B_INDEX_NAMES = frozenset(
    {
        "ix_paint_plan_region_instructions_plan_sequence",
        "ix_paint_plan_review_events_owner_project_created",
        "ix_paint_plans_lineage_revision",
        "ix_paint_plans_owner_project_version",
        "ix_paint_plans_source_invocation",
        "ix_provider_pricing_snapshots_model_effective",
        "uq_paint_plan_review_events_decision",
        "uq_paint_plans_generated_attempt",
        "uq_paint_plans_one_current_per_project",
    }
)
EXPECTED_TABLES = EXPECTED_PHASE_1F_TABLES | EXPECTED_PHASE_3A_TABLES | EXPECTED_PHASE_3B_TABLES
EXPECTED_CONSTRAINT_NAMES = (
    EXPECTED_PHASE_1F_CONSTRAINT_NAMES
    | EXPECTED_PHASE_3A_CONSTRAINT_NAMES
    | EXPECTED_PHASE_3B_CONSTRAINT_NAMES
)
EXPECTED_INDEX_NAMES = (
    EXPECTED_PHASE_1F_INDEX_NAMES | EXPECTED_PHASE_3A_INDEX_NAMES | EXPECTED_PHASE_3B_INDEX_NAMES
)
EXPECTED_DATABASE_IDENTIFIERS = EXPECTED_TABLES | EXPECTED_CONSTRAINT_NAMES | EXPECTED_INDEX_NAMES
EXPECTED_CHECK_CONSTRAINTS_BY_TABLE = MappingProxyType(
    {
        "ai_audit_events": frozenset(),
        "ai_command_idempotency_records": frozenset(),
        "ai_cost_ledger": frozenset(
            {
                "ck_ai_cost_ledger_fixture_currency_only",
                "ck_ai_cost_ledger_measurement_consistent",
                "ck_ai_cost_ledger_measurement_status_allowed",
            }
        ),
        "ai_invocation_events": frozenset(),
        "ai_usage_ledger": frozenset(
            {
                "ck_ai_usage_ledger_measurement_consistent",
                "ck_ai_usage_ledger_measurement_status_allowed",
            }
        ),
        "auth_sessions": frozenset(
            {
                "ck_auth_sessions_expiry_after_creation",
                "ck_auth_sessions_last_seen_not_before_creation",
            }
        ),
        "budget_reservations": frozenset(
            {
                "ck_budget_reservations_fixture_currency_only",
                "ck_budget_reservations_state_allowed",
            }
        ),
        "capability_definitions": frozenset({"ck_capability_definitions_status_allowed"}),
        "command_idempotency_records": frozenset(
            {
                "ck_command_idempotency_records_command_type_format",
                "ck_command_idempotency_records_execution_status_allowed",
                "ck_command_idempotency_records_execution_status_format",
                "ck_command_idempotency_records_expiry_after_creation",
                "ck_command_idempotency_records_http_status_valid",
                "ck_command_idempotency_records_payload_hash_format",
                "ck_command_idempotency_records_principal_id_normalized",
                "ck_command_idempotency_records_resource_type_format",
                "ck_command_idempotency_records_response_snapshot_is_object",
                "ck_command_idempotency_records_result_matches_execution_status",
                "ck_command_idempotency_records_scope_key_normalized",
            }
        ),
        "credential_project_grants": frozenset(),
        "credential_records": frozenset(
            {
                "ck_credential_records_lifecycle_envelope",
                "ck_credential_records_no_self_replacement",
                "ck_credential_records_status_allowed",
            }
        ),
        "external_identities": frozenset(
            {
                "ck_external_identities_issuer_normalized",
                "ck_external_identities_subject_normalized",
            }
        ),
        "image_assets": frozenset(
            {
                "ck_image_assets_byte_size_allowed",
                "ck_image_assets_created_by_actor_id_normalized",
                "ck_image_assets_created_by_actor_type_allowed",
                "ck_image_assets_created_by_display_normalized",
                "ck_image_assets_current_lifecycle_consistent",
                "ck_image_assets_declared_type_matches_format",
                "ck_image_assets_detected_format_allowed",
                "ck_image_assets_dimensions_allowed",
                "ck_image_assets_exif_orientation_allowed",
                "ck_image_assets_intended_usage_allowed",
                "ck_image_assets_lifecycle_status_allowed",
                "ck_image_assets_original_filename_safe",
                "ck_image_assets_pixel_count_allowed",
                "ck_image_assets_rights_actor_required",
                "ck_image_assets_rights_status_allowed",
                "ck_image_assets_rights_version_positive",
                "ck_image_assets_role_allowed",
                "ck_image_assets_sha256_format",
                "ck_image_assets_source_type_allowed",
                "ck_image_assets_storage_key_format",
                "ck_image_assets_storage_provider_allowed",
                "ck_image_assets_upload_validation_details_is_object",
                "ck_image_assets_upload_validation_result_allowed",
                "ck_image_assets_version_positive",
            }
        ),
        "image_set_readiness_reviews": frozenset(
            {
                "ck_image_set_readiness_reviews_actor_display_normalized",
                "ck_image_set_readiness_reviews_actor_id_normalized",
                "ck_image_set_readiness_reviews_actor_type_allowed",
                "ck_image_set_readiness_reviews_fingerprint_format",
                "ck_image_set_readiness_reviews_not_ready_reason_required",
                "ck_image_set_readiness_reviews_primary_front_role",
                "ck_image_set_readiness_reviews_ready_required_assets",
                "ck_image_set_readiness_reviews_reason_normalized",
                "ck_image_set_readiness_reviews_reference_angle_role",
                "ck_image_set_readiness_reviews_reference_back_role",
                "ck_image_set_readiness_reviews_reference_detail_role",
                "ck_image_set_readiness_reviews_verdict_allowed",
                "ck_image_set_readiness_reviews_version_positive",
            }
        ),
        "invocation_attempts": frozenset(
            {
                "ck_invocation_attempts_fixture_currency_only",
                "ck_invocation_attempts_provider_request_id_consistent",
                "ck_invocation_attempts_provider_request_id_status_allowed",
                "ck_invocation_attempts_status_allowed",
            }
        ),
        "invocation_requests": frozenset(
            {
                "ck_invocation_requests_canonicalization_version",
                "ck_invocation_requests_family_allowed",
                "ck_invocation_requests_final_attempt_success_only",
                "ck_invocation_requests_payload_hash",
                "ck_invocation_requests_project_scope",
                "ck_invocation_requests_status_allowed",
            }
        ),
        "model_capabilities": frozenset(),
        "model_definitions": frozenset(
            {
                "ck_model_definitions_fixture_currency_only",
                "ck_model_definitions_status_allowed",
            }
        ),
        "oidc_login_flows": frozenset({"ck_oidc_login_flows_expiry_after_creation"}),
        "paint_projects": frozenset(
            {
                "ck_paint_projects_description_normalized",
                "ck_paint_projects_id_not_zero_uuid",
                "ck_paint_projects_owner_principal_id_normalized",
                "ck_paint_projects_planning_mode_allowed",
                "ck_paint_projects_planning_mode_format",
                "ck_paint_projects_requested_target_style_allowed",
                "ck_paint_projects_requested_target_style_format",
                "ck_paint_projects_status_allowed",
                "ck_paint_projects_title_normalized",
                "ck_paint_projects_title_not_blank",
                "ck_paint_projects_updated_at_not_before_created_at",
            }
        ),
        "paint_plan_region_instructions": frozenset(
            {
                "ck_paint_plan_region_instructions_confidence_allowed",
                "ck_paint_plan_region_instructions_kind_paint",
                "ck_paint_plan_region_instructions_label_safe",
                "ck_paint_plan_region_instructions_sequence_allowed",
                "ck_paint_plan_region_instructions_text_safe",
                "ck_paint_plan_region_instructions_warnings_bounded",
            }
        ),
        "paint_plan_review_events": frozenset(
            {
                "ck_paint_plan_review_events_action_allowed",
                "ck_paint_plan_review_events_actor_safe",
                "ck_paint_plan_review_events_reason_safe",
                "ck_paint_plan_review_events_reject_reason_required",
                "ck_paint_plan_review_events_version_positive",
            }
        ),
        "paint_plans": frozenset(
            {
                "ck_paint_plans_actor_snapshots_safe",
                "ck_paint_plans_actor_type_allowed",
                "ck_paint_plans_content_hash_format",
                "ck_paint_plans_instruction_count_allowed",
                "ck_paint_plans_lifecycle_allowed",
                "ck_paint_plans_lineage_consistent",
                "ck_paint_plans_model_revisions_positive",
                "ck_paint_plans_model_snapshots_safe",
                "ck_paint_plans_overall_approach_safe",
                "ck_paint_plans_pricing_snapshot_required",
                "ck_paint_plans_prompt_contract_format",
                "ck_paint_plans_revision_actor_consistent",
                "ck_paint_plans_revision_kind_allowed",
                "ck_paint_plans_revisions_positive",
                "ck_paint_plans_safety_notes_bounded",
                "ck_paint_plans_source_fingerprints_format",
                "ck_paint_plans_source_versions_positive",
                "ck_paint_plans_title_safe",
            }
        ),
        "project_budget_counters": frozenset(
            {
                "ck_project_budget_counters_fixture_currency_only",
                "ck_project_budget_counters_nonnegative",
            }
        ),
        "project_budget_policies": frozenset({"ck_project_budget_policies_fixture_currency_only"}),
        "project_memberships": frozenset({"ck_project_memberships_role_allowed"}),
        "project_model_policies": frozenset(
            {
                "ck_project_model_policies_fallback_disabled",
                "ck_project_model_policies_fixture_currency_only",
            }
        ),
        "project_model_policy_capabilities": frozenset(),
        "project_model_policy_credentials": frozenset(),
        "project_model_policy_models": frozenset(),
        "project_model_policy_providers": frozenset(),
        "provider_capabilities": frozenset(),
        "provider_definitions": frozenset(
            {
                "ck_provider_definitions_base_url_policy_allowed",
                "ck_provider_definitions_catalog_mode_allowed",
                "ck_provider_definitions_status_allowed",
            }
        ),
        "provider_pricing_snapshots": frozenset(
            {
                "ck_provider_pricing_snapshots_currency_usd",
                "ck_provider_pricing_snapshots_model_id_safe",
                "ck_provider_pricing_snapshots_prices_nonnegative",
                "ck_provider_pricing_snapshots_provider_key_safe",
                "ck_provider_pricing_snapshots_source_url_safe",
                "ck_provider_pricing_snapshots_time_order",
                "ck_provider_pricing_snapshots_unit_basis_allowed",
                "ck_provider_pricing_snapshots_version_safe",
            }
        ),
        "prompt_template_definitions": frozenset(
            {
                "ck_prompt_template_definitions_body_bounded",
                "ck_prompt_template_definitions_hash_format",
                "ck_prompt_template_definitions_key_format",
                "ck_prompt_template_definitions_schema_format",
                "ck_prompt_template_definitions_status_allowed",
                "ck_prompt_template_definitions_version_positive",
            }
        ),
        "region_set_reviews": frozenset(
            {
                "ck_region_set_reviews_actor_display_normalized",
                "ck_region_set_reviews_actor_id_normalized",
                "ck_region_set_reviews_actor_type_allowed",
                "ck_region_set_reviews_changes_reason_required",
                "ck_region_set_reviews_reason_normalized",
                "ck_region_set_reviews_verdict_allowed",
                "ck_region_set_reviews_version_positive",
            }
        ),
        "region_sets": frozenset(
            {
                "ck_region_sets_counts_consistent",
                "ck_region_sets_created_by_actor_id_normalized",
                "ck_region_sets_created_by_actor_type_allowed",
                "ck_region_sets_created_by_display_normalized",
                "ck_region_sets_geometry_fingerprint_format",
                "ck_region_sets_lifecycle_allowed",
                "ck_region_sets_region_count_allowed",
                "ck_region_sets_source_dimensions_allowed",
                "ck_region_sets_source_fingerprint_format",
                "ck_region_sets_source_primary_role",
                "ck_region_sets_total_vertex_count_allowed",
                "ck_region_sets_version_positive",
            }
        ),
        "region_vertices": frozenset(
            {
                "ck_region_vertices_coordinates_allowed",
                "ck_region_vertices_sequence_allowed",
            }
        ),
        "regions": frozenset(
            {
                "ck_regions_area_positive",
                "ck_regions_bbox_allowed",
                "ck_regions_kind_allowed",
                "ck_regions_label_safe",
                "ck_regions_normalized_label_safe",
                "ck_regions_notes_safe",
                "ck_regions_opacity_ppm_allowed",
                "ck_regions_vertex_count_allowed",
                "ck_regions_z_index_allowed",
            }
        ),
        "state_transition_events": frozenset(
            {
                "ck_state_transition_events_actor_display_snapshot_normalized",
                "ck_state_transition_events_actor_principal_id_normalized",
                "ck_state_transition_events_actor_type_allowed",
                "ck_state_transition_events_actor_type_format",
                "ck_state_transition_events_create_project_reason",
                "ck_state_transition_events_event_format",
                "ck_state_transition_events_event_metadata_is_object",
                "ck_state_transition_events_from_state_allowed",
                "ck_state_transition_events_reason_format",
                "ck_state_transition_events_to_state_allowed",
                "ck_state_transition_events_user_display_name_required",
            }
        ),
        "user_accounts": frozenset(
            {
                "ck_user_accounts_display_name_normalized",
                "ck_user_accounts_email_normalized",
                "ck_user_accounts_updated_at_not_before_created_at",
            }
        ),
        "user_budget_counters": frozenset(
            {
                "ck_user_budget_counters_fixture_currency_only",
                "ck_user_budget_counters_nonnegative",
            }
        ),
        "user_budget_policies": frozenset({"ck_user_budget_policies_fixture_currency_only"}),
        "user_provider_preferences": frozenset(),
    }
)
EXPECTED_WORKFLOW_STATES = (
    "DRAFT",
    "IMAGE_UPLOADED",
    "IMAGE_REVIEW_REQUIRED",
    "IMAGE_VALIDATION_FAILED",
    "IMAGE_VALIDATED",
    "REGION_ANALYSIS_RUNNING",
    "REGION_REVIEW_REQUIRED",
    "REGIONS_CONFIRMED",
    "PLAN_GENERATION_RUNNING",
    "PLAN_REVIEW_REQUIRED",
    "PLAN_APPROVED",
    "COMPLETED",
    "BLOCKED_LOW_CONFIDENCE",
    "FAILED_RETRYABLE",
    "FAILED_FINAL",
    "ABANDONED",
)
EXPECTED_PHYSICAL_STRING_LENGTHS = MappingProxyType(
    {
        "owner_principal_id": 128,
        "title": 80,
        "description": 500,
        "requested_target_style": 32,
        "planning_mode": 32,
        "status": 64,
        "from_state": 64,
        "to_state": 64,
        "event": 64,
        "actor_type": 32,
        "actor_principal_id": 128,
        "actor_display_name_snapshot": 200,
        "reason": 128,
        "scope_key": 512,
        "principal_id": 128,
        "command_type": 64,
        "payload_hash": 64,
        "execution_status": 32,
        "resource_type": 64,
    }
)
EXPECTED_ACTOR_TYPES = ("user", "api", "worker", "system")
EXPECTED_MACHINE_TOKEN_PATTERN = r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$"
EXPECTED_POSTGRESQL_MACHINE_TOKEN_PATTERN = r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$"
EXPECTED_PAYLOAD_HASH_PATTERN = r"^[0-9a-f]{64}$"
EXPECTED_TARGET_STYLE = "cel_shading"
EXPECTED_PLANNING_MODE = "planning_only_demo"
EXPECTED_IDEMPOTENCY_STATUSES = ("in_progress", "completed")
EXPECTED_CREATE_EVENT = "create_project"
EXPECTED_CREATE_REASON = "project_created"
EXPECTED_USER_ACTOR_TYPE = "user"
VALID_MACHINE_TOKENS = ("user", "create_project", "paint_project", "state2", "step_2")
INVALID_MACHINE_TOKENS = (
    "User",
    "create-project",
    "create project",
    "_create",
    "create_",
    "create__project",
    "2create",
    "",
)
EXPECTED_POSTGRESQL_MACHINE_TOKEN_CONSTRAINTS = MappingProxyType(
    {
        "ck_command_idempotency_records_command_type_format": ("command_idempotency_records"),
        "ck_command_idempotency_records_execution_status_format": ("command_idempotency_records"),
        "ck_command_idempotency_records_resource_type_format": ("command_idempotency_records"),
        "ck_paint_projects_planning_mode_format": "paint_projects",
        "ck_paint_projects_requested_target_style_format": "paint_projects",
        "ck_state_transition_events_actor_type_format": "state_transition_events",
        "ck_state_transition_events_event_format": "state_transition_events",
        "ck_state_transition_events_reason_format": "state_transition_events",
    }
)
POSTGRESQL_IDENTIFIER_LIMIT = 63
POSTGRESQL_IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9_]+$")
API_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATHS = (
    API_ROOT / "migrations" / "versions" / "a10d3d8dab38_create_paintproject_persistence_.py",
    API_ROOT / "migrations" / "versions" / "5ed9906e7d33_add_imageasset_foundation.py",
    API_ROOT / "migrations" / "versions" / "d4c8a1f7b2e9_add_multi_role_image_set_readiness.py",
    API_ROOT / "migrations" / "versions" / "7f3a2b9c4d1e_add_human_region_annotation.py",
    API_ROOT
    / "migrations"
    / "versions"
    / "2b1c4d5e6f70_add_governed_identity_and_private_storage.py",
    API_ROOT / "migrations" / "versions" / "3b01a1c2d3e4_add_phase3b_paint_plan_foundation.py",
)
PHASE_3A_MIGRATION_PATHS = (
    API_ROOT / "migrations" / "versions" / "3a01c7e9b4d2_add_phase3a_registries.py",
    API_ROOT / "migrations" / "versions" / "3a02d8f0c5e3_add_phase3a_credential_security.py",
    API_ROOT
    / "migrations"
    / "versions"
    / "3a03e9a1d6f4_add_phase3a_policies_invocations_ledgers.py",
)


class _Phase3AMigrationRecorder:
    def __init__(self) -> None:
        self.metadata = MetaData()
        self.tables: dict[str, Table] = {}
        self.indexes: list[tuple[str, str, tuple[str, ...], bool, str]] = []
        self.added_checks: list[tuple[str, str, str]] = []
        self.added_foreign_keys: list[
            tuple[str, tuple[str, ...], tuple[str, ...], str, str | None]
        ] = []

    def f(self, name: str) -> str:
        return name

    def execute(self, *_args: object, **_kwargs: object) -> None:
        return None

    def create_table(self, name: str, *items: object, **_kwargs: object) -> Table:
        assert name not in self.tables
        table = Table(name, self.metadata, *items)
        self.tables[name] = table
        return table

    def create_index(
        self,
        name: str,
        table_name: str,
        columns: list[str],
        *,
        unique: bool = False,
        **kwargs: object,
    ) -> None:
        where = kwargs.get("postgresql_where")
        normalized_where = " ".join(str(where).split()) if where is not None else ""
        self.indexes.append((table_name, name, tuple(columns), unique, normalized_where))

    def create_check_constraint(
        self,
        name: str,
        table_name: str,
        condition: str,
        **_kwargs: object,
    ) -> None:
        self.added_checks.append((table_name, name, " ".join(condition.split())))

    def create_foreign_key(
        self,
        name: str,
        source_table: str,
        target_table: str,
        source_columns: list[str],
        target_columns: list[str],
        *,
        ondelete: str | None = None,
        **_kwargs: object,
    ) -> None:
        self.added_foreign_keys.append(
            (
                source_table,
                tuple(source_columns),
                tuple(f"{target_table}.{column}" for column in target_columns),
                name,
                ondelete,
            )
        )


def _phase3a_migration_recorder() -> _Phase3AMigrationRecorder:
    recorder = _Phase3AMigrationRecorder()
    for migration_path in PHASE_3A_MIGRATION_PATHS:
        spec = importlib.util.spec_from_file_location(
            f"creativedeploy_test_{migration_path.stem}", migration_path
        )
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.op = recorder
        module.upgrade()
    return recorder


def _check_constraints(table: Table) -> dict[str, CheckConstraint]:
    return {
        str(constraint.name): constraint
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }


def _constraint_sql(constraint: CheckConstraint) -> str:
    return " ".join(str(constraint.sqltext).split())


def _quoted_sql_values(constraint: CheckConstraint) -> tuple[str, ...]:
    return tuple(re.findall(r"'([^']+)'", _constraint_sql(constraint)))


def _index_columns(index: Index) -> tuple[str, ...]:
    return tuple(column.name for column in index.columns)


def _assert_string_column(table: Table, name: str, length: int, *, nullable: bool) -> None:
    column = table.c[name]
    assert isinstance(column.type, String)
    assert column.type.length == length
    assert column.nullable is nullable


def _assert_timestamps(table: Table, names: Iterable[str]) -> None:
    for name in names:
        column = table.c[name]
        assert isinstance(column.type, DateTime)
        assert column.type.timezone is True


def _metadata_identifier_categories() -> tuple[
    frozenset[str],
    frozenset[str],
    frozenset[str],
]:
    table_names: set[str] = set()
    constraint_names: set[str] = set()
    index_names: set[str] = set()
    for table in Base.metadata.tables.values():
        table_names.add(table.name)
        for constraint in table.constraints:
            assert constraint.name is not None
            constraint_names.add(str(constraint.name))
        for index in table.indexes:
            assert index.name is not None
            index_names.add(index.name)
    return (
        frozenset(table_names),
        frozenset(constraint_names),
        frozenset(index_names),
    )


def _metadata_identifiers() -> frozenset[str]:
    tables, constraints, indexes = _metadata_identifier_categories()
    return tables | constraints | indexes


def _op_formatted_identifier(node: ast.expr) -> str | None:
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "op"
        and node.func.attr == "f"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    ):
        return node.args[0].value
    return None


def _migration_identifier_categories() -> tuple[
    frozenset[str],
    frozenset[str],
    frozenset[str],
]:
    table_names: set[str] = set()
    constraint_names: set[str] = set()
    index_names: set[str] = set()
    for migration_path in MIGRATION_PATHS:
        module = ast.parse(migration_path.read_text(encoding="utf-8"))
        for node in ast.walk(module):
            if not isinstance(node, ast.Call):
                continue
            if (
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "op"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                if node.func.attr == "create_table":
                    table_names.add(node.args[0].value)
                elif node.func.attr == "create_index":
                    index_names.add(node.args[0].value)
                elif node.func.attr in {
                    "create_check_constraint",
                    "create_foreign_key",
                    "create_unique_constraint",
                    "f",
                }:
                    constraint_names.add(node.args[0].value)
            for keyword in node.keywords:
                if (
                    keyword.arg == "name"
                    and isinstance(keyword.value, ast.Constant)
                    and isinstance(keyword.value.value, str)
                ):
                    constraint_names.add(keyword.value.value)
    phase3a = _phase3a_migration_recorder()
    table_names.update(phase3a.tables)
    constraint_names.update(
        str(constraint.name)
        for table in phase3a.tables.values()
        for constraint in table.constraints
    )
    constraint_names.update(name for _table, name, _sql in phase3a.added_checks)
    constraint_names.update(
        name for _table, _source, _target, name, _delete in phase3a.added_foreign_keys
    )
    index_names.update(name for _table, name, _columns, _unique, _where in phase3a.indexes)
    return (
        frozenset(table_names),
        frozenset(constraint_names),
        frozenset(index_names),
    )


def _migration_identifiers() -> frozenset[str]:
    tables, constraints, indexes = _migration_identifier_categories()
    return tables | constraints | indexes


def _migration_check_constraint_sql() -> dict[str, str]:
    checks: dict[str, str] = {}
    for migration_path in MIGRATION_PATHS:
        module = ast.parse(migration_path.read_text(encoding="utf-8"))
        for node in ast.walk(module):
            if (
                not isinstance(node, ast.Call)
                or not isinstance(node.func, ast.Attribute)
                or node.func.attr != "CheckConstraint"
                or not node.args
            ):
                continue
            sql_text = ast.literal_eval(node.args[0])
            assert isinstance(sql_text, str)
            name_keyword = next(keyword for keyword in node.keywords if keyword.arg == "name")
            constraint_name = _op_formatted_identifier(name_keyword.value)
            assert constraint_name is not None
            checks[constraint_name] = " ".join(sql_text.split())
    return checks


def _foreign_key_shapes(
    tables: Iterable[Table],
) -> frozenset[tuple[str, tuple[str, ...], tuple[str, ...], str, str | None]]:
    return frozenset(
        (
            table.name,
            tuple(element.parent.name for element in constraint.elements),
            tuple(element.target_fullname for element in constraint.elements),
            str(constraint.name),
            constraint.ondelete,
        )
        for table in tables
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    )


def _unique_constraint_shapes(
    tables: Iterable[Table],
) -> frozenset[tuple[str, tuple[str, ...], str]]:
    return frozenset(
        (table.name, tuple(constraint.columns.keys()), str(constraint.name))
        for table in tables
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    )


def _index_shapes(
    tables: Iterable[Table],
) -> frozenset[tuple[str, str, tuple[str, ...], bool, str]]:
    shapes: set[tuple[str, str, tuple[str, ...], bool, str]] = set()
    for table in tables:
        for index in table.indexes:
            where = index.dialect_options["postgresql"].get("where")
            normalized_where = " ".join(str(where).split()) if where is not None else ""
            shapes.add(
                (
                    table.name,
                    str(index.name),
                    tuple(column.name for column in index.columns),
                    index.unique,
                    normalized_where,
                )
            )
    return frozenset(shapes)


def _check_sql_by_name(tables: Iterable[Table]) -> dict[str, str]:
    return {
        str(constraint.name): _constraint_sql(constraint)
        for table in tables
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }


def test_registered_models_and_metadata_contain_exact_phase_1f_phase3a_and_phase3b_sets() -> None:
    registered_phase_1f = set(REGISTERED_MODELS[:14])
    registered_phase_3a = set(REGISTERED_MODELS[14:39])
    registered_phase_3b = set(REGISTERED_MODELS[39:])
    registered_complete = set(REGISTERED_MODELS)
    expected_complete = (
        EXPECTED_PHASE_1F_MODELS | EXPECTED_PHASE_3A_MODELS | EXPECTED_PHASE_3B_MODELS
    )

    assert not EXPECTED_PHASE_1F_MODELS - registered_phase_1f
    assert not registered_phase_1f - EXPECTED_PHASE_1F_MODELS
    assert not EXPECTED_PHASE_3A_MODELS - registered_phase_3a
    assert not registered_phase_3a - EXPECTED_PHASE_3A_MODELS
    assert not EXPECTED_PHASE_3B_MODELS - registered_phase_3b
    assert not registered_phase_3b - EXPECTED_PHASE_3B_MODELS
    assert not expected_complete - registered_complete
    assert not registered_complete - expected_complete
    assert not EXPECTED_PHASE_1F_MODELS & EXPECTED_PHASE_3A_MODELS
    assert not EXPECTED_PHASE_1F_MODELS & EXPECTED_PHASE_3B_MODELS
    assert not EXPECTED_PHASE_3A_MODELS & EXPECTED_PHASE_3B_MODELS
    assert len(REGISTERED_MODELS) == 44
    assert set(Base.metadata.tables) == EXPECTED_TABLES
    assert {model.__table__.name for model in REGISTERED_MODELS} == EXPECTED_TABLES
    assert not {
        "users",
        "workspaces",
        "tenants",
        "agent_runs",
    } & set(Base.metadata.tables)


def test_production_contract_constants_match_independent_expectations() -> None:
    assert WORKFLOW_STATES == EXPECTED_WORKFLOW_STATES
    assert len(WORKFLOW_STATES) == 16
    assert dict(PHYSICAL_STRING_LENGTHS) == dict(EXPECTED_PHYSICAL_STRING_LENGTHS)
    assert ACTOR_TYPES == EXPECTED_ACTOR_TYPES
    assert MACHINE_TOKEN_PATTERN == EXPECTED_MACHINE_TOKEN_PATTERN
    assert POSTGRESQL_MACHINE_TOKEN_PATTERN == EXPECTED_POSTGRESQL_MACHINE_TOKEN_PATTERN
    assert PAYLOAD_HASH_PATTERN == EXPECTED_PAYLOAD_HASH_PATTERN
    assert TARGET_STYLE_CEL_SHADING == EXPECTED_TARGET_STYLE
    assert PLANNING_MODE_DEMO == EXPECTED_PLANNING_MODE
    assert (
        IDEMPOTENCY_STATUS_IN_PROGRESS,
        IDEMPOTENCY_STATUS_COMPLETED,
    ) == EXPECTED_IDEMPOTENCY_STATUSES


@pytest.mark.parametrize("token", VALID_MACHINE_TOKENS)
def test_canonical_machine_token_contract_accepts_independent_valid_examples(
    token: str,
) -> None:
    assert re.fullmatch(EXPECTED_MACHINE_TOKEN_PATTERN, token)
    assert re.fullmatch(POSTGRESQL_MACHINE_TOKEN_PATTERN, token)


@pytest.mark.parametrize("token", INVALID_MACHINE_TOKENS)
def test_canonical_machine_token_contract_rejects_independent_invalid_examples(
    token: str,
) -> None:
    assert re.fullmatch(EXPECTED_MACHINE_TOKEN_PATTERN, token) is None
    assert re.fullmatch(POSTGRESQL_MACHINE_TOKEN_PATTERN, token) is None


def test_payload_hash_contract_uses_independent_examples() -> None:
    valid_hash = "0123456789abcdef" * 4

    assert re.fullmatch(EXPECTED_PAYLOAD_HASH_PATTERN, valid_hash)
    assert re.fullmatch(PAYLOAD_HASH_PATTERN, valid_hash)
    for invalid_hash in ("a" * 63, "a" * 65, "A" * 64, "g" * 64, ""):
        assert re.fullmatch(EXPECTED_PAYLOAD_HASH_PATTERN, invalid_hash) is None
        assert re.fullmatch(PAYLOAD_HASH_PATTERN, invalid_hash) is None


def test_all_database_identifiers_fit_postgresql_limit() -> None:
    identifiers = _metadata_identifiers()

    assert identifiers == EXPECTED_DATABASE_IDENTIFIERS
    assert len(identifiers) == 470
    assert all(
        len(identifier.encode("utf-8")) <= POSTGRESQL_IDENTIFIER_LIMIT for identifier in identifiers
    )
    assert all(POSTGRESQL_IDENTIFIER_PATTERN.fullmatch(identifier) for identifier in identifiers)
    assert "ck_state_transition_events_actor_display_snapshot_normalized" in identifiers
    assert "ck_state_transition_events_actor_display_name_snapshot_normalized" not in identifiers


def test_orm_and_migration_identifiers_each_match_independent_contract() -> None:
    metadata_tables, metadata_constraints, metadata_indexes = _metadata_identifier_categories()
    migration_tables, migration_constraints, migration_indexes = _migration_identifier_categories()

    assert metadata_tables == EXPECTED_TABLES
    assert metadata_constraints == EXPECTED_CONSTRAINT_NAMES
    assert metadata_indexes == EXPECTED_INDEX_NAMES
    assert migration_tables == EXPECTED_TABLES
    assert migration_constraints == EXPECTED_CONSTRAINT_NAMES
    assert migration_indexes == EXPECTED_INDEX_NAMES
    assert _metadata_identifiers() == EXPECTED_DATABASE_IDENTIFIERS
    assert _migration_identifiers() == EXPECTED_DATABASE_IDENTIFIERS
    assert _migration_identifiers() == _metadata_identifiers()
    assert all(
        len(identifier.encode("utf-8")) <= POSTGRESQL_IDENTIFIER_LIMIT
        for identifier in _migration_identifiers()
    )
    assert all(
        POSTGRESQL_IDENTIFIER_PATTERN.fullmatch(identifier)
        for identifier in _migration_identifiers()
    )
    assert not any("_8ef7" in identifier for identifier in _migration_identifiers())


def test_phase3a_orm_and_migrations_match_exact_metadata_contract() -> None:
    orm_tables = [Base.metadata.tables[name] for name in EXPECTED_PHASE_3A_TABLES]
    migration = _phase3a_migration_recorder()

    assert set(migration.tables) == EXPECTED_PHASE_3A_TABLES

    orm_foreign_keys = _foreign_key_shapes(orm_tables)
    migration_foreign_keys = _foreign_key_shapes(migration.tables.values()) | frozenset(
        migration.added_foreign_keys
    )
    assert {shape[3] for shape in orm_foreign_keys} == EXPECTED_PHASE_3A_FOREIGN_KEY_NAMES
    assert migration_foreign_keys == orm_foreign_keys

    orm_unique_constraints = _unique_constraint_shapes(orm_tables)
    migration_unique_constraints = _unique_constraint_shapes(migration.tables.values())
    assert {
        shape[2] for shape in orm_unique_constraints
    } == EXPECTED_PHASE_3A_UNIQUE_CONSTRAINT_NAMES
    assert migration_unique_constraints == orm_unique_constraints

    orm_indexes = _index_shapes(orm_tables)
    migration_indexes = frozenset(migration.indexes)
    assert {shape[1] for shape in orm_indexes} == EXPECTED_PHASE_3A_INDEX_NAMES
    assert migration_indexes == orm_indexes

    orm_check_sql = _check_sql_by_name([*orm_tables, Base.metadata.tables["paint_projects"]])
    orm_phase3a_check_sql = {
        name: sql
        for name, sql in orm_check_sql.items()
        if name in EXPECTED_PHASE_3A_CHECK_CONSTRAINT_NAMES
    }
    migration_check_sql = _check_sql_by_name(migration.tables.values())
    migration_check_sql.update({name: sql for _table, name, sql in migration.added_checks})
    assert set(orm_phase3a_check_sql) == EXPECTED_PHASE_3A_CHECK_CONSTRAINT_NAMES
    phase3b_added_checks = {
        "ck_ai_cost_ledger_measurement_consistent",
        "ck_ai_cost_ledger_measurement_status_allowed",
        "ck_ai_usage_ledger_measurement_consistent",
        "ck_ai_usage_ledger_measurement_status_allowed",
        "ck_invocation_attempts_provider_request_id_consistent",
        "ck_invocation_attempts_provider_request_id_status_allowed",
    }
    phase3b_expanded_checks = {
        "ck_ai_cost_ledger_fixture_currency_only",
        "ck_budget_reservations_fixture_currency_only",
        "ck_invocation_attempts_fixture_currency_only",
        "ck_invocation_requests_family_allowed",
        "ck_model_definitions_fixture_currency_only",
        "ck_project_budget_counters_fixture_currency_only",
        "ck_project_budget_policies_fixture_currency_only",
        "ck_project_model_policies_fixture_currency_only",
        "ck_user_budget_counters_fixture_currency_only",
        "ck_user_budget_policies_fixture_currency_only",
    }
    unchanged_checks = (
        EXPECTED_PHASE_3A_CHECK_CONSTRAINT_NAMES - phase3b_added_checks - phase3b_expanded_checks
    )
    assert set(migration_check_sql) == (
        EXPECTED_PHASE_3A_CHECK_CONSTRAINT_NAMES - phase3b_added_checks
    )
    assert {name: migration_check_sql[name] for name in unchanged_checks} == {
        name: orm_phase3a_check_sql[name] for name in unchanged_checks
    }


def test_explicit_identifier_names_do_not_collide_in_postgresql_namespaces() -> None:
    assert len(Base.metadata.tables) == len(set(Base.metadata.tables))

    all_index_names: list[str] = []
    for table in Base.metadata.tables.values():
        constraint_names = [str(constraint.name) for constraint in table.constraints]
        assert all(constraint_names)
        assert len(constraint_names) == len(set(constraint_names))
        all_index_names.extend(str(index.name) for index in table.indexes)

    assert all(all_index_names)
    assert len(all_index_names) == len(set(all_index_names))


def test_postgresql_machine_token_constraints_match_independent_contract() -> None:
    migration_checks = _migration_check_constraint_sql()

    for constraint_name, table_name in EXPECTED_POSTGRESQL_MACHINE_TOKEN_CONSTRAINTS.items():
        orm_checks = _check_constraints(Base.metadata.tables[table_name])
        assert EXPECTED_POSTGRESQL_MACHINE_TOKEN_PATTERN in _constraint_sql(
            orm_checks[constraint_name]
        )
        assert EXPECTED_POSTGRESQL_MACHINE_TOKEN_PATTERN in migration_checks[constraint_name]


def test_model_column_sets_are_exact() -> None:
    assert tuple(PaintProject.__table__.c.keys()) == (
        "id",
        "owner_principal_id",
        "title",
        "description",
        "requested_target_style",
        "planning_mode",
        "status",
        "current_image_asset_id",
        "created_at",
        "updated_at",
    )
    assert tuple(StateTransitionEvent.__table__.c.keys()) == (
        "id",
        "project_id",
        "from_state",
        "to_state",
        "event",
        "actor_type",
        "actor_principal_id",
        "actor_display_name_snapshot",
        "reason",
        "correlation_id",
        "event_metadata",
        "created_at",
    )
    assert tuple(CommandIdempotencyRecord.__table__.c.keys()) == (
        "id",
        "scope_key",
        "principal_id",
        "command_type",
        "idempotency_key",
        "payload_hash",
        "execution_status",
        "resource_type",
        "resource_id",
        "http_status",
        "response_snapshot",
        "created_at",
        "expires_at",
    )
    assert tuple(ImageAsset.__table__.c.keys()) == (
        "id",
        "paint_project_id",
        "owner_principal_id",
        "role",
        "version",
        "supersedes_image_asset_id",
        "is_current",
        "lifecycle_status",
        "storage_provider",
        "storage_key",
        "original_filename",
        "declared_content_type",
        "detected_format",
        "byte_size",
        "width",
        "height",
        "pixel_count",
        "color_mode",
        "has_alpha",
        "exif_orientation",
        "sha256",
        "upload_validation_result",
        "upload_validation_details",
        "source_type",
        "rights_attestation_status",
        "rights_attestation_version",
        "intended_usage",
        "rights_attested_by_principal_id",
        "rights_attested_at",
        "created_by_actor_type",
        "created_by_actor_id",
        "created_by_actor_display_name_snapshot",
        "created_at",
    )
    assert tuple(ImageSetReadinessReview.__table__.c.keys()) == (
        "id",
        "owner_principal_id",
        "paint_project_id",
        "version",
        "verdict",
        "reason",
        "primary_front_image_asset_id",
        "primary_front_role",
        "reference_back_image_asset_id",
        "reference_back_role",
        "reference_angle_image_asset_id",
        "reference_angle_role",
        "reference_detail_image_asset_id",
        "reference_detail_role",
        "image_set_fingerprint",
        "actor_type",
        "actor_id",
        "actor_display_name_snapshot",
        "created_at",
    )
    all_columns = {
        column.name for table in Base.metadata.tables.values() for column in table.columns
    }
    assert (
        not {
            "current_region_version_id",
            "current_plan_id",
            "agent_run_id",
            "metadata",
        }
        & all_columns
    )


@pytest.mark.parametrize(
    ("table", "column_name"),
    [
        (PaintProject.__table__, "id"),
        (StateTransitionEvent.__table__, "id"),
        (StateTransitionEvent.__table__, "project_id"),
        (StateTransitionEvent.__table__, "correlation_id"),
        (CommandIdempotencyRecord.__table__, "id"),
        (CommandIdempotencyRecord.__table__, "idempotency_key"),
        (CommandIdempotencyRecord.__table__, "resource_id"),
    ],
)
def test_uuid_columns_use_native_postgresql_uuid(table: Table, column_name: str) -> None:
    column = table.c[column_name]
    assert isinstance(column.type, PostgreSQLUUID)
    assert column.type.as_uuid is True


@pytest.mark.parametrize(
    "table",
    [
        PaintProject.__table__,
        StateTransitionEvent.__table__,
        CommandIdempotencyRecord.__table__,
    ],
)
def test_uuid_primary_keys_use_python_uuid4_without_server_default(table: Table) -> None:
    column = table.c.id
    assert column.primary_key is True
    assert column.nullable is False
    assert column.default is not None
    assert callable(column.default.arg)
    assert column.default.arg.__name__ == uuid.uuid4.__name__
    assert column.server_default is None


def test_paint_project_types_nullability_and_defaults() -> None:
    table = PaintProject.__table__
    for name in (
        "owner_principal_id",
        "title",
        "description",
        "requested_target_style",
        "planning_mode",
        "status",
    ):
        _assert_string_column(
            table,
            name,
            EXPECTED_PHYSICAL_STRING_LENGTHS[name],
            nullable=name == "description",
        )
    _assert_timestamps(table, ("created_at", "updated_at"))
    assert str(table.c.requested_target_style.server_default.arg) == (f"'{EXPECTED_TARGET_STYLE}'")
    assert str(table.c.planning_mode.server_default.arg) == f"'{EXPECTED_PLANNING_MODE}'"
    assert str(table.c.status.server_default.arg) == "'DRAFT'"
    assert str(table.c.created_at.server_default.arg) == "now()"
    assert str(table.c.updated_at.server_default.arg) == "now()"


def test_state_transition_types_and_conditional_audit_nullability() -> None:
    table = StateTransitionEvent.__table__
    for name in (
        "from_state",
        "to_state",
        "event",
        "actor_type",
        "actor_principal_id",
        "actor_display_name_snapshot",
        "reason",
    ):
        _assert_string_column(
            table,
            name,
            EXPECTED_PHYSICAL_STRING_LENGTHS[name],
            nullable=name in {"from_state", "actor_display_name_snapshot", "reason"},
        )
    assert table.c.actor_display_name_snapshot.nullable is True
    assert table.c.reason.nullable is True
    assert isinstance(table.c.event_metadata.type, JSONB)
    assert table.c.event_metadata.nullable is False
    assert str(table.c.event_metadata.server_default.arg) == "'{}'::jsonb"
    _assert_timestamps(table, ("created_at",))


def test_event_metadata_default_factory_returns_isolated_empty_objects() -> None:
    column_default = StateTransitionEvent.__table__.c.event_metadata.default

    assert column_default is not None
    assert column_default.is_callable
    factory = column_default.arg
    assert callable(factory)

    first = factory(None)
    second = factory(None)

    assert isinstance(first, dict)
    assert isinstance(second, dict)
    assert first == {}
    assert second == {}
    assert first is not second

    first["mutated"] = True

    assert first == {"mutated": True}
    assert second == {}


def test_idempotency_types_nullability_and_defaults() -> None:
    table = CommandIdempotencyRecord.__table__
    for name in (
        "scope_key",
        "principal_id",
        "command_type",
        "payload_hash",
        "execution_status",
        "resource_type",
    ):
        _assert_string_column(
            table,
            name,
            EXPECTED_PHYSICAL_STRING_LENGTHS[name],
            nullable=name == "resource_type",
        )
    assert table.c.resource_id.nullable is True
    assert table.c.http_status.nullable is True
    assert isinstance(table.c.response_snapshot.type, JSONB)
    assert table.c.response_snapshot.nullable is True
    _assert_timestamps(table, ("created_at", "expires_at"))


def test_check_constraints_match_exact_table_governance_contract() -> None:
    assert set(EXPECTED_CHECK_CONSTRAINTS_BY_TABLE) == EXPECTED_TABLES

    for table in Base.metadata.tables.values():
        checks = [
            constraint
            for constraint in table.constraints
            if isinstance(constraint, CheckConstraint)
        ]
        assert {str(constraint.name) for constraint in checks} == (
            EXPECTED_CHECK_CONSTRAINTS_BY_TABLE[table.name]
        )
        assert all(
            constraint.name is not None and str(constraint.name).startswith(f"ck_{table.name}_")
            for constraint in checks
        )
        assert len({str(constraint.name) for constraint in checks}) == len(checks)


def test_paint_project_constraints_match_contract() -> None:
    checks = _check_constraints(PaintProject.__table__)
    expected = {
        "ck_paint_projects_owner_principal_id_normalized",
        "ck_paint_projects_id_not_zero_uuid",
        "ck_paint_projects_title_not_blank",
        "ck_paint_projects_title_normalized",
        "ck_paint_projects_description_normalized",
        "ck_paint_projects_requested_target_style_format",
        "ck_paint_projects_requested_target_style_allowed",
        "ck_paint_projects_planning_mode_format",
        "ck_paint_projects_planning_mode_allowed",
        "ck_paint_projects_status_allowed",
        "ck_paint_projects_updated_at_not_before_created_at",
    }
    assert set(checks) == expected
    assert EXPECTED_POSTGRESQL_MACHINE_TOKEN_PATTERN in _constraint_sql(
        checks["ck_paint_projects_requested_target_style_format"]
    )
    assert _quoted_sql_values(checks["ck_paint_projects_requested_target_style_allowed"]) == (
        EXPECTED_TARGET_STYLE,
    )
    assert _quoted_sql_values(checks["ck_paint_projects_planning_mode_allowed"]) == (
        EXPECTED_PLANNING_MODE,
    )
    status_constraint = checks["ck_paint_projects_status_allowed"]
    status_sql = _constraint_sql(status_constraint)
    assert _quoted_sql_values(status_constraint) == EXPECTED_WORKFLOW_STATES
    assert MACHINE_TOKEN_PATTERN not in status_sql
    assert "btrim" in _constraint_sql(checks["ck_paint_projects_owner_principal_id_normalized"])
    assert "updated_at >= created_at" in _constraint_sql(
        checks["ck_paint_projects_updated_at_not_before_created_at"]
    )


def test_state_transition_constraints_match_conditional_contract() -> None:
    checks = _check_constraints(StateTransitionEvent.__table__)
    expected = {
        "ck_state_transition_events_from_state_allowed",
        "ck_state_transition_events_to_state_allowed",
        "ck_state_transition_events_event_format",
        "ck_state_transition_events_actor_type_format",
        "ck_state_transition_events_actor_type_allowed",
        "ck_state_transition_events_actor_principal_id_normalized",
        "ck_state_transition_events_actor_display_snapshot_normalized",
        "ck_state_transition_events_user_display_name_required",
        "ck_state_transition_events_reason_format",
        "ck_state_transition_events_create_project_reason",
        "ck_state_transition_events_event_metadata_is_object",
    }
    assert set(checks) == expected
    assert "actor_display_name_snapshot IS NULL" in _constraint_sql(
        checks["ck_state_transition_events_actor_display_snapshot_normalized"]
    )
    assert f"actor_type <> '{EXPECTED_USER_ACTOR_TYPE}'" in _constraint_sql(
        checks["ck_state_transition_events_user_display_name_required"]
    )
    assert "reason IS NULL" in _constraint_sql(checks["ck_state_transition_events_reason_format"])
    assert EXPECTED_POSTGRESQL_MACHINE_TOKEN_PATTERN in _constraint_sql(
        checks["ck_state_transition_events_reason_format"]
    )
    assert f"event <> '{EXPECTED_CREATE_EVENT}'" in _constraint_sql(
        checks["ck_state_transition_events_create_project_reason"]
    )
    assert "reason IS NOT NULL" in _constraint_sql(
        checks["ck_state_transition_events_create_project_reason"]
    )
    assert f"reason = '{EXPECTED_CREATE_REASON}'" in _constraint_sql(
        checks["ck_state_transition_events_create_project_reason"]
    )
    assert "jsonb_typeof(event_metadata) = 'object'" in _constraint_sql(
        checks["ck_state_transition_events_event_metadata_is_object"]
    )
    actor_constraint = checks["ck_state_transition_events_actor_type_allowed"]
    assert _quoted_sql_values(actor_constraint) == EXPECTED_ACTOR_TYPES
    assert "agent" not in EXPECTED_ACTOR_TYPES


def test_idempotency_constraints_match_contract() -> None:
    checks = _check_constraints(CommandIdempotencyRecord.__table__)
    expected = {
        "ck_command_idempotency_records_scope_key_normalized",
        "ck_command_idempotency_records_principal_id_normalized",
        "ck_command_idempotency_records_command_type_format",
        "ck_command_idempotency_records_payload_hash_format",
        "ck_command_idempotency_records_execution_status_format",
        "ck_command_idempotency_records_execution_status_allowed",
        "ck_command_idempotency_records_resource_type_format",
        "ck_command_idempotency_records_http_status_valid",
        "ck_command_idempotency_records_response_snapshot_is_object",
        "ck_command_idempotency_records_result_matches_execution_status",
        "ck_command_idempotency_records_expiry_after_creation",
    }
    assert set(checks) == expected
    assert EXPECTED_PAYLOAD_HASH_PATTERN in _constraint_sql(
        checks["ck_command_idempotency_records_payload_hash_format"]
    )
    assert (
        EXPECTED_PAYLOAD_HASH_PATTERN
        in _migration_check_constraint_sql()["ck_command_idempotency_records_payload_hash_format"]
    )
    assert (
        _quoted_sql_values(checks["ck_command_idempotency_records_execution_status_allowed"])
        == EXPECTED_IDEMPOTENCY_STATUSES
    )
    assert "jsonb_typeof(response_snapshot) = 'object'" in _constraint_sql(
        checks["ck_command_idempotency_records_response_snapshot_is_object"]
    )
    assert "execution_status <> 'completed'" in _constraint_sql(
        checks["ck_command_idempotency_records_result_matches_execution_status"]
    )
    assert "expires_at > created_at" in _constraint_sql(
        checks["ck_command_idempotency_records_expiry_after_creation"]
    )


def test_required_indexes_have_exact_names_and_column_order() -> None:
    expected = {
        "paint_projects": {
            "ix_paint_projects_owner_updated_at_id": (
                "owner_principal_id",
                "updated_at",
                "id",
            )
        },
        "state_transition_events": {
            "ix_state_transition_events_project_created_at_id": (
                "project_id",
                "created_at",
                "id",
            )
        },
        "command_idempotency_records": {
            "ix_command_idempotency_records_expires_at": ("expires_at",)
        },
    }
    for table_name, expected_indexes in expected.items():
        table = Base.metadata.tables[table_name]
        actual = {index.name: _index_columns(index) for index in table.indexes}
        assert actual == expected_indexes


def test_state_transition_foreign_key_is_restrict_without_orm_cascade() -> None:
    table = StateTransitionEvent.__table__
    constraints = [
        constraint
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    ]
    assert len(constraints) == 1
    constraint = constraints[0]
    assert tuple(element.parent.name for element in constraint.elements) == ("project_id",)
    assert tuple(element.target_fullname for element in constraint.elements) == (
        "paint_projects.id",
    )
    assert constraint.ondelete == "RESTRICT"
    assert not StateTransitionEvent.__mapper__.relationships


def test_idempotency_unique_constraint_has_exact_scope_and_name() -> None:
    constraints = [
        constraint
        for constraint in CommandIdempotencyRecord.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    ]
    assert len(constraints) == 1
    constraint = constraints[0]
    assert str(constraint.name) == ("uq_command_idempotency_records_scope_key_idempotency_key")
    assert tuple(column.name for column in constraint.columns) == (
        "scope_key",
        "idempotency_key",
    )


def test_importing_all_models_has_no_runtime_or_output_side_effect() -> None:
    source = """
import sqlalchemy.ext.asyncio

def fail(*args, **kwargs):
    raise AssertionError("Model import attempted to create an engine")

sqlalchemy.ext.asyncio.create_async_engine = fail
from creativedeploy_api.db.models import REGISTERED_MODELS
assert len(REGISTERED_MODELS) == 44
"""
    result = subprocess.run(
        [sys.executable, "-c", source],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert result.stderr == ""
