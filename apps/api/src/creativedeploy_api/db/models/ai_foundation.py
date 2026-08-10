"""Governed multi-provider foundation persistence models."""

# ruff: noqa: E501

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, MappedColumn, mapped_column
from sqlalchemy.sql.elements import conv

from creativedeploy_api.db.base import Base


def _uuid_pk() -> MappedColumn[uuid.UUID]:
    return mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _created_at() -> MappedColumn[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


def _updated_at() -> MappedColumn[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class ProviderDefinition(Base):
    __tablename__ = "provider_definitions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active','disabled','retired')",
            name=conv("ck_provider_definitions_status_allowed"),
        ),
        CheckConstraint(
            "base_url_policy IN ('provider_managed','allowlisted_custom','not_applicable')",
            name=conv("ck_provider_definitions_base_url_policy_allowed"),
        ),
        CheckConstraint(
            "model_catalog_mode IN ('bundled','remote_refresh','user_supplied')",
            name=conv("ck_provider_definitions_catalog_mode_allowed"),
        ),
        UniqueConstraint("provider_key", name="uq_provider_definitions_provider_key"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    provider_key: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    adapter_type: Mapped[str] = mapped_column(String(64), nullable=False)
    base_url_policy: Mapped[str] = mapped_column(String(32), nullable=False)
    authentication_scheme: Mapped[str] = mapped_column(String(64), nullable=False)
    model_catalog_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    allow_custom_model_id: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    catalog_status: Mapped[str] = mapped_column(String(32), nullable=False)
    catalog_fresh_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    max_timeout_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class CapabilityDefinition(Base):
    __tablename__ = "capability_definitions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active','disabled','retired')",
            name=conv("ck_capability_definitions_status_allowed"),
        ),
        UniqueConstraint("capability_key", name="uq_capability_definitions_capability_key"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    capability_key: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class ModelDefinition(Base):
    __tablename__ = "model_definitions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active','disabled','unknown','unsupported','retired')",
            name=conv("ck_model_definitions_status_allowed"),
        ),
        CheckConstraint(
            "pricing_currency IS NULL OR pricing_currency IN ('FIXTURE_CREDITS','USD')",
            name=conv("ck_model_definitions_fixture_currency_only"),
        ),
        ForeignKeyConstraint(
            ["provider_definition_id"],
            ["provider_definitions.id"],
            name="fk_model_definitions_provider_provider_definitions",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("provider_key", "model_id", name="uq_model_definitions_provider_model"),
        Index("ix_model_definitions_provider_status", "provider_definition_id", "status"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    provider_definition_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    provider_key: Mapped[str] = mapped_column(String(64), nullable=False)
    model_id: Mapped[str] = mapped_column(String(160), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    catalog_source: Mapped[str] = mapped_column(String(64), nullable=False)
    catalog_fresh_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    catalog_status: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    context_window: Mapped[int | None] = mapped_column(Integer)
    supports_structured_output: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    supports_vision: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    pricing_minor_units: Mapped[int | None] = mapped_column(BigInteger)
    pricing_currency: Mapped[str | None] = mapped_column(String(32))
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class ProviderCapability(Base):
    __tablename__ = "provider_capabilities"
    __table_args__ = (
        ForeignKeyConstraint(
            ["provider_definition_id"],
            ["provider_definitions.id"],
            name="fk_provider_capabilities_provider_provider_definitions",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["capability_definition_id"],
            ["capability_definitions.id"],
            name="fk_provider_capabilities_capability_capability_definitions",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "provider_definition_id",
            "capability_definition_id",
            name="uq_provider_capabilities_provider_capability",
        ),
        Index("ix_provider_capabilities_capability", "capability_definition_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    provider_definition_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    capability_definition_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    trust_status: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = _created_at()


class ModelCapability(Base):
    __tablename__ = "model_capabilities"
    __table_args__ = (
        ForeignKeyConstraint(
            ["model_definition_id"],
            ["model_definitions.id"],
            name="fk_model_capabilities_model_model_definitions",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["capability_definition_id"],
            ["capability_definitions.id"],
            name="fk_model_capabilities_capability_capability_definitions",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "model_definition_id",
            "capability_definition_id",
            name="uq_model_capabilities_model_capability",
        ),
        Index("ix_model_capabilities_capability", "capability_definition_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    model_definition_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    capability_definition_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    trust_status: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = _created_at()


class CredentialRecord(Base):
    __tablename__ = "credential_records"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active','revoked','replaced')",
            name=conv("ck_credential_records_status_allowed"),
        ),
        CheckConstraint(
            "replaces_credential_id IS NULL OR replaces_credential_id <> id",
            name=conv("ck_credential_records_no_self_replacement"),
        ),
        CheckConstraint(
            "(status = 'active' AND revoked_at IS NULL AND replaced_at IS NULL "
            "AND encryption_version IS NOT NULL AND data_algorithm = 'AES-256-GCM' "
            "AND ciphertext IS NOT NULL AND octet_length(ciphertext) > 0 "
            "AND data_nonce IS NOT NULL AND octet_length(data_nonce) = 12 "
            "AND data_authentication_tag IS NOT NULL AND octet_length(data_authentication_tag) = 16 "
            "AND wrapped_dek IS NOT NULL AND octet_length(wrapped_dek) > 0 "
            "AND wrap_algorithm = 'AES-256-GCM' "
            "AND wrap_nonce IS NOT NULL AND octet_length(wrap_nonce) = 12 "
            "AND wrap_authentication_tag IS NOT NULL AND octet_length(wrap_authentication_tag) = 16 "
            "AND aad_version IS NOT NULL) OR "
            "(status = 'revoked' AND revoked_at IS NOT NULL AND replaced_at IS NULL "
            "AND encryption_version IS NULL AND data_algorithm IS NULL AND ciphertext IS NULL "
            "AND data_nonce IS NULL AND data_authentication_tag IS NULL AND wrapped_dek IS NULL "
            "AND wrap_algorithm IS NULL AND wrap_nonce IS NULL "
            "AND wrap_authentication_tag IS NULL AND aad_version IS NULL) OR "
            "(status = 'replaced' AND replaced_at IS NOT NULL AND revoked_at IS NULL "
            "AND encryption_version IS NULL AND data_algorithm IS NULL AND ciphertext IS NULL "
            "AND data_nonce IS NULL AND data_authentication_tag IS NULL AND wrapped_dek IS NULL "
            "AND wrap_algorithm IS NULL AND wrap_nonce IS NULL "
            "AND wrap_authentication_tag IS NULL AND aad_version IS NULL)",
            name=conv("ck_credential_records_lifecycle_envelope"),
        ),
        ForeignKeyConstraint(
            ["owner_user_id"],
            ["user_accounts.id"],
            name="fk_credential_records_owner_user_accounts",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["provider_definition_id"],
            ["provider_definitions.id"],
            name="fk_credential_records_provider_provider_definitions",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["replaces_credential_id"],
            ["credential_records.id"],
            name="fk_credential_records_replaces_credential_records",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "replaces_credential_id", name="uq_credential_records_replacement_lineage"
        ),
        Index("ix_credential_records_owner_status", "owner_user_id", "status"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    owner_user_id: Mapped[uuid.UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    provider_definition_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    provider_key: Mapped[str] = mapped_column(String(64), nullable=False)
    key_fingerprint: Mapped[str] = mapped_column(String(96), nullable=False)
    last_four: Mapped[str | None] = mapped_column(String(4))
    alias: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    encryption_version: Mapped[str | None] = mapped_column(String(64))
    data_algorithm: Mapped[str | None] = mapped_column(String(32))
    ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary)
    data_nonce: Mapped[bytes | None] = mapped_column(LargeBinary)
    data_authentication_tag: Mapped[bytes | None] = mapped_column(LargeBinary)
    wrapped_dek: Mapped[bytes | None] = mapped_column(LargeBinary)
    wrap_algorithm: Mapped[str | None] = mapped_column(String(32))
    wrap_nonce: Mapped[bytes | None] = mapped_column(LargeBinary)
    wrap_authentication_tag: Mapped[bytes | None] = mapped_column(LargeBinary)
    aad_version: Mapped[str | None] = mapped_column(String(64))
    replaces_credential_id: Mapped[uuid.UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    last_validation_status: Mapped[str | None] = mapped_column(String(64))
    last_successful_validation_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class CredentialProjectGrant(Base):
    __tablename__ = "credential_project_grants"
    __table_args__ = (
        ForeignKeyConstraint(
            ["credential_id"],
            ["credential_records.id"],
            name="fk_credential_project_grants_credential_credential_records",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["project_id"],
            ["paint_projects.id"],
            name="fk_credential_project_grants_project_paint_projects",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["granted_by_user_id"],
            ["user_accounts.id"],
            name="fk_credential_project_grants_granted_by_user_accounts",
            ondelete="RESTRICT",
        ),
        Index("ix_credential_project_grants_project", "project_id", "credential_id"),
        Index(
            "uq_credential_project_grants_active",
            "credential_id",
            "project_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    credential_id: Mapped[uuid.UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    granted_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    created_at: Mapped[datetime] = _created_at()
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class UserProviderPreference(Base):
    __tablename__ = "user_provider_preferences"
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id"],
            ["user_accounts.id"],
            name="fk_user_provider_preferences_user",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["default_provider_definition_id"],
            ["provider_definitions.id"],
            name="fk_user_provider_preferences_provider",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["default_model_definition_id"],
            ["model_definitions.id"],
            name="fk_user_provider_preferences_model",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["default_credential_id"],
            ["credential_records.id"],
            name="fk_user_provider_preferences_credential",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("user_id", name="uq_user_provider_preferences_user"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    default_provider_definition_id: Mapped[uuid.UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True)
    )
    default_model_definition_id: Mapped[uuid.UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True)
    )
    default_credential_id: Mapped[uuid.UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    timeout_ms: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("30000"))
    streaming_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    cost_warning_minor_units: Mapped[int | None] = mapped_column(BigInteger)
    cost_warning_currency: Mapped[str | None] = mapped_column(String(32))
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    updated_at: Mapped[datetime] = _updated_at()


class ProjectModelPolicy(Base):
    __tablename__ = "project_model_policies"
    __table_args__ = (
        CheckConstraint(
            "currency IN ('FIXTURE_CREDITS','USD')",
            name=conv("ck_project_model_policies_fixture_currency_only"),
        ),
        CheckConstraint(
            "allow_fallback = false",
            name=conv("ck_project_model_policies_fallback_disabled"),
        ),
        ForeignKeyConstraint(
            ["project_id"],
            ["paint_projects.id"],
            name="fk_project_model_policies_project",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["default_provider_definition_id"],
            ["provider_definitions.id"],
            name="fk_project_model_policies_provider",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["default_model_definition_id"],
            ["model_definitions.id"],
            name="fk_project_model_policies_model",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["default_credential_id"],
            ["credential_records.id"],
            name="fk_project_model_policies_credential",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["updated_by_user_id"],
            ["user_accounts.id"],
            name="fk_project_model_policies_updated_by",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("project_id", name="uq_project_model_policies_project"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    default_provider_definition_id: Mapped[uuid.UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True)
    )
    default_model_definition_id: Mapped[uuid.UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True)
    )
    default_credential_id: Mapped[uuid.UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    per_invocation_limit_minor_units: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(32), nullable=False)
    allow_unknown_cost: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    unknown_cost_reservation_minor_units: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    allow_manual_model_id: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    allow_fallback: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    require_paid_call_confirmation: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    updated_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    updated_at: Mapped[datetime] = _updated_at()


class ProjectModelPolicyProvider(Base):
    __tablename__ = "project_model_policy_providers"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_model_policy_id"],
            ["project_model_policies.id"],
            name="fk_policy_providers_policy",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["provider_definition_id"],
            ["provider_definitions.id"],
            name="fk_policy_providers_provider",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "project_model_policy_id", "provider_definition_id", name="uq_policy_providers_pair"
        ),
        Index("ix_policy_providers_provider", "provider_definition_id"),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    project_model_policy_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    provider_definition_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    created_at: Mapped[datetime] = _created_at()


class ProjectModelPolicyModel(Base):
    __tablename__ = "project_model_policy_models"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_model_policy_id"],
            ["project_model_policies.id"],
            name="fk_policy_models_policy",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["model_definition_id"],
            ["model_definitions.id"],
            name="fk_policy_models_model",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "project_model_policy_id", "model_definition_id", name="uq_policy_models_pair"
        ),
        Index("ix_policy_models_model", "model_definition_id"),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    project_model_policy_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    model_definition_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    created_at: Mapped[datetime] = _created_at()


class ProjectModelPolicyCapability(Base):
    __tablename__ = "project_model_policy_capabilities"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_model_policy_id"],
            ["project_model_policies.id"],
            name="fk_policy_capabilities_policy",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["capability_definition_id"],
            ["capability_definitions.id"],
            name="fk_policy_capabilities_capability",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "project_model_policy_id",
            "capability_definition_id",
            name="uq_policy_capabilities_pair",
        ),
        Index("ix_policy_capabilities_capability", "capability_definition_id"),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    project_model_policy_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    capability_definition_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    created_at: Mapped[datetime] = _created_at()


class ProjectModelPolicyCredential(Base):
    __tablename__ = "project_model_policy_credentials"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_model_policy_id"],
            ["project_model_policies.id"],
            name="fk_policy_credentials_policy",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["credential_record_id"],
            ["credential_records.id"],
            name="fk_policy_credentials_credential",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "project_model_policy_id", "credential_record_id", name="uq_policy_credentials_pair"
        ),
        Index("ix_policy_credentials_credential", "credential_record_id"),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    project_model_policy_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    credential_record_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    created_at: Mapped[datetime] = _created_at()


class UserBudgetPolicy(Base):
    __tablename__ = "user_budget_policies"
    __table_args__ = (
        CheckConstraint(
            "currency IN ('FIXTURE_CREDITS','USD')",
            name=conv("ck_user_budget_policies_fixture_currency_only"),
        ),
        ForeignKeyConstraint(
            ["user_id"],
            ["user_accounts.id"],
            name="fk_user_budget_policies_user",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "user_id", "product_space", "currency", name="uq_user_budget_policies_scope"
        ),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    product_space: Mapped[str] = mapped_column(String(64), nullable=False)
    currency: Mapped[str] = mapped_column(String(32), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    per_invocation_limit_minor_units: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cumulative_limit_minor_units: Mapped[int] = mapped_column(BigInteger, nullable=False)
    window_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    allow_unknown_cost: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    unknown_cost_reservation_minor_units: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    updated_at: Mapped[datetime] = _updated_at()


class ProjectBudgetPolicy(Base):
    __tablename__ = "project_budget_policies"
    __table_args__ = (
        CheckConstraint(
            "currency IN ('FIXTURE_CREDITS','USD')",
            name=conv("ck_project_budget_policies_fixture_currency_only"),
        ),
        ForeignKeyConstraint(
            ["project_id"],
            ["paint_projects.id"],
            name="fk_project_budget_policies_project",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "project_id", "product_space", "currency", name="uq_project_budget_policies_scope"
        ),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    product_space: Mapped[str] = mapped_column(String(64), nullable=False)
    currency: Mapped[str] = mapped_column(String(32), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    per_invocation_limit_minor_units: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cumulative_limit_minor_units: Mapped[int] = mapped_column(BigInteger, nullable=False)
    window_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    allow_unknown_cost: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    unknown_cost_reservation_minor_units: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    updated_at: Mapped[datetime] = _updated_at()


class UserBudgetCounter(Base):
    __tablename__ = "user_budget_counters"
    __table_args__ = (
        CheckConstraint(
            "currency IN ('FIXTURE_CREDITS','USD')",
            name=conv("ck_user_budget_counters_fixture_currency_only"),
        ),
        CheckConstraint(
            "committed_minor_units >= 0 AND reserved_minor_units >= 0 AND limit_minor_units >= 0",
            name=conv("ck_user_budget_counters_nonnegative"),
        ),
        ForeignKeyConstraint(
            ["user_id"],
            ["user_accounts.id"],
            name="fk_user_budget_counters_user",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "user_id",
            "product_space",
            "currency",
            "window_start",
            "window_end",
            name="uq_user_budget_counters_window",
        ),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    product_space: Mapped[str] = mapped_column(String(64), nullable=False)
    currency: Mapped[str] = mapped_column(String(32), nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    limit_minor_units: Mapped[int] = mapped_column(BigInteger, nullable=False)
    committed_minor_units: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    reserved_minor_units: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class ProjectBudgetCounter(Base):
    __tablename__ = "project_budget_counters"
    __table_args__ = (
        CheckConstraint(
            "currency IN ('FIXTURE_CREDITS','USD')",
            name=conv("ck_project_budget_counters_fixture_currency_only"),
        ),
        CheckConstraint(
            "committed_minor_units >= 0 AND reserved_minor_units >= 0 AND limit_minor_units >= 0",
            name=conv("ck_project_budget_counters_nonnegative"),
        ),
        ForeignKeyConstraint(
            ["project_id"],
            ["paint_projects.id"],
            name="fk_project_budget_counters_project",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "project_id",
            "product_space",
            "currency",
            "window_start",
            "window_end",
            name="uq_project_budget_counters_window",
        ),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    product_space: Mapped[str] = mapped_column(String(64), nullable=False)
    currency: Mapped[str] = mapped_column(String(32), nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    limit_minor_units: Mapped[int] = mapped_column(BigInteger, nullable=False)
    committed_minor_units: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    reserved_minor_units: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class InvocationRequest(Base):
    __tablename__ = "invocation_requests"
    __table_args__ = (
        CheckConstraint(
            "invocation_family IN ('fixture_credential_validation','fixture_model_catalog','fixture_invocation','paint_plan_generation')",
            name=conv("ck_invocation_requests_family_allowed"),
        ),
        CheckConstraint(
            "canonicalization_version = 'phase3a-v1'",
            name=conv("ck_invocation_requests_canonicalization_version"),
        ),
        CheckConstraint(
            "canonical_request_payload_hash ~ '^sha256:[0-9a-f]{64}$'",
            name=conv("ck_invocation_requests_payload_hash"),
        ),
        CheckConstraint(
            "status IN ('pending','admitted','running','succeeded','failed','cancelled','outcome_unknown')",
            name=conv("ck_invocation_requests_status_allowed"),
        ),
        CheckConstraint(
            "final_attempt_id IS NULL OR status = 'succeeded'",
            name=conv("ck_invocation_requests_final_attempt_success_only"),
        ),
        CheckConstraint(
            "(project_id IS NULL AND project_scope_id = '00000000-0000-0000-0000-000000000000'::uuid) OR (project_id IS NOT NULL AND project_id = project_scope_id AND project_scope_id <> '00000000-0000-0000-0000-000000000000'::uuid)",
            name=conv("ck_invocation_requests_project_scope"),
        ),
        ForeignKeyConstraint(
            ["requesting_user_id"],
            ["user_accounts.id"],
            name="fk_invocation_requests_user",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["project_id"],
            ["paint_projects.id"],
            name="fk_invocation_requests_project",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["requested_provider_definition_id"],
            ["provider_definitions.id"],
            name="fk_invreq_requested_provider_definition",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["requested_model_definition_id"],
            ["model_definitions.id"],
            name="fk_invreq_requested_model_definition",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["requested_credential_id"],
            ["credential_records.id"],
            name="fk_invreq_requested_credential",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["id", "final_attempt_id"],
            ["invocation_attempts.invocation_id", "invocation_attempts.id"],
            name="fk_invocation_requests_final_attempt",
            ondelete="RESTRICT",
            use_alter=True,
        ),
        UniqueConstraint(
            "requesting_user_id",
            "product_space",
            "project_scope_id",
            "invocation_family",
            "idempotency_key",
            name="uq_invocation_requests_idempotency_scope",
        ),
        Index("ix_invocation_requests_user_created", "requesting_user_id", "created_at"),
        Index("ix_invocation_requests_project_created", "project_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    requesting_user_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    product_space: Mapped[str] = mapped_column(String(64), nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    project_scope_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    invocation_family: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[uuid.UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    canonicalization_version: Mapped[str] = mapped_column(String(32), nullable=False)
    canonical_request_payload_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    requested_capabilities: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    requested_provider_definition_id: Mapped[uuid.UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True)
    )
    requested_model_definition_id: Mapped[uuid.UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True)
    )
    requested_credential_id: Mapped[uuid.UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    request_id: Mapped[uuid.UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    total_elapsed_time_limit_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    confirmation_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    budget_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    safe_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    final_attempt_id: Mapped[uuid.UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    terminal_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    final_error_category: Mapped[str | None] = mapped_column(String(64))
    output_reference: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class InvocationAttempt(Base):
    __tablename__ = "invocation_attempts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('created','admitted','running','succeeded','failed','cancelled','outcome_unknown')",
            name=conv("ck_invocation_attempts_status_allowed"),
        ),
        CheckConstraint(
            "currency IN ('FIXTURE_CREDITS','USD')",
            name=conv("ck_invocation_attempts_fixture_currency_only"),
        ),
        CheckConstraint(
            "provider_request_id_status IN ('absent','provided','unavailable')",
            name=conv("ck_invocation_attempts_provider_request_id_status_allowed"),
        ),
        CheckConstraint(
            "(provider_request_id_status = 'provided' "
            "AND provider_request_id IS NOT NULL "
            "AND length(provider_request_id) BETWEEN 1 AND 200 "
            "AND provider_request_id = btrim(provider_request_id) "
            "AND provider_request_id !~ '[[:cntrl:]]') "
            "OR (provider_request_id_status IN ('absent','unavailable') "
            "AND provider_request_id IS NULL)",
            name=conv("ck_invocation_attempts_provider_request_id_consistent"),
        ),
        ForeignKeyConstraint(
            ["invocation_id"],
            ["invocation_requests.id"],
            name="fk_invocation_attempts_invocation",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["provider_definition_id"],
            ["provider_definitions.id"],
            name="fk_invocation_attempts_provider",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["model_definition_id"],
            ["model_definitions.id"],
            name="fk_invocation_attempts_model",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["credential_id"],
            ["credential_records.id"],
            name="fk_invocation_attempts_credential",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("invocation_id", "attempt_number", name="uq_invocation_attempts_number"),
        UniqueConstraint("invocation_id", "id", name="uq_invocation_attempts_invocation_id"),
        Index(
            "uq_invocation_attempts_active",
            "invocation_id",
            unique=True,
            postgresql_where=text("status IN ('created','admitted','running')"),
        ),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    invocation_id: Mapped[uuid.UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    provider_definition_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    model_definition_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    provider_key: Mapped[str] = mapped_column(String(64), nullable=False)
    model_id: Mapped[str] = mapped_column(String(160), nullable=False)
    adapter_version: Mapped[str] = mapped_column(String(64), nullable=False)
    capability_snapshot: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    credential_id: Mapped[uuid.UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    credential_encryption_version_snapshot: Mapped[str | None] = mapped_column(String(64))
    temporary_credential: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    retry_of_attempt_id: Mapped[uuid.UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("invocation_attempts.id", ondelete="RESTRICT")
    )
    fallback_decision: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'disabled'")
    )
    currency: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    terminal_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    final_error_category: Mapped[str | None] = mapped_column(String(64))
    output_reference: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    safe_provider_metadata: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    provider_request_id_status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'absent'")
    )
    provider_request_id: Mapped[str | None] = mapped_column(String(200))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = _created_at()


class BudgetReservation(Base):
    __tablename__ = "budget_reservations"
    __table_args__ = (
        CheckConstraint(
            "state IN ('reserved','dispatch_committed','settled','released','reconciliation_required')",
            name=conv("ck_budget_reservations_state_allowed"),
        ),
        CheckConstraint(
            "currency IN ('FIXTURE_CREDITS','USD')",
            name=conv("ck_budget_reservations_fixture_currency_only"),
        ),
        ForeignKeyConstraint(
            ["invocation_id"],
            ["invocation_requests.id"],
            name="fk_budget_reservations_invocation",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["attempt_id"],
            ["invocation_attempts.id"],
            name="fk_budget_reservations_attempt",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["user_counter_id"],
            ["user_budget_counters.id"],
            name="fk_budget_reservations_user_counter",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["project_counter_id"],
            ["project_budget_counters.id"],
            name="fk_budget_reservations_project_counter",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("attempt_id", name="uq_budget_reservations_attempt"),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    invocation_id: Mapped[uuid.UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    attempt_id: Mapped[uuid.UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    user_counter_id: Mapped[uuid.UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    project_counter_id: Mapped[uuid.UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    currency: Mapped[str] = mapped_column(String(32), nullable=False)
    reserved_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = _created_at()
    admission_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    dispatch_committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class AIInvocationEvent(Base):
    __tablename__ = "ai_invocation_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["invocation_id"],
            ["invocation_requests.id"],
            name="fk_ai_invocation_events_invocation",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["attempt_id"],
            ["invocation_attempts.id"],
            name="fk_ai_invocation_events_attempt",
            ondelete="RESTRICT",
        ),
        Index("ix_ai_invocation_events_invocation_created", "invocation_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    invocation_id: Mapped[uuid.UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    attempt_id: Mapped[uuid.UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    safe_metadata: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = _created_at()


class AIUsageLedger(Base):
    __tablename__ = "ai_usage_ledger"
    __table_args__ = (
        CheckConstraint(
            "measurement_status IN ('measured','unavailable')",
            name=conv("ck_ai_usage_ledger_measurement_status_allowed"),
        ),
        CheckConstraint(
            "(measurement_status = 'measured' "
            "AND input_units IS NOT NULL AND input_units >= 0 "
            "AND output_units IS NOT NULL AND output_units >= 0) "
            "OR (measurement_status = 'unavailable' "
            "AND input_units IS NULL AND output_units IS NULL)",
            name=conv("ck_ai_usage_ledger_measurement_consistent"),
        ),
        ForeignKeyConstraint(
            ["invocation_id"],
            ["invocation_requests.id"],
            name="fk_ai_usage_ledger_invocation",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["attempt_id"],
            ["invocation_attempts.id"],
            name="fk_ai_usage_ledger_attempt",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["provider_definition_id"],
            ["provider_definitions.id"],
            name="fk_ai_usage_ledger_provider",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["model_definition_id"],
            ["model_definitions.id"],
            name="fk_ai_usage_ledger_model",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "attempt_id", "source", "canonical_sequence", name="uq_ai_usage_ledger_dedupe"
        ),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    invocation_id: Mapped[uuid.UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    attempt_id: Mapped[uuid.UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    provider_definition_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    model_definition_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    canonical_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    measurement_status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'measured'")
    )
    input_units: Mapped[int | None] = mapped_column(BigInteger)
    output_units: Mapped[int | None] = mapped_column(BigInteger)
    safe_metadata: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = _created_at()


class AICostLedger(Base):
    __tablename__ = "ai_cost_ledger"
    __table_args__ = (
        CheckConstraint(
            "currency IN ('FIXTURE_CREDITS','USD')",
            name=conv("ck_ai_cost_ledger_fixture_currency_only"),
        ),
        CheckConstraint(
            "measurement_status IN ('estimated','measured','unavailable')",
            name=conv("ck_ai_cost_ledger_measurement_status_allowed"),
        ),
        CheckConstraint(
            "(measurement_status IN ('estimated','measured') "
            "AND amount_minor_units IS NOT NULL AND amount_minor_units >= 0) "
            "OR (measurement_status = 'unavailable' AND amount_minor_units IS NULL)",
            name=conv("ck_ai_cost_ledger_measurement_consistent"),
        ),
        ForeignKeyConstraint(
            ["invocation_id"],
            ["invocation_requests.id"],
            name="fk_ai_cost_ledger_invocation",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["attempt_id"],
            ["invocation_attempts.id"],
            name="fk_ai_cost_ledger_attempt",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["provider_definition_id"],
            ["provider_definitions.id"],
            name="fk_ai_cost_ledger_provider",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["model_definition_id"],
            ["model_definitions.id"],
            name="fk_ai_cost_ledger_model",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "attempt_id", "source", "canonical_sequence", name="uq_ai_cost_ledger_dedupe"
        ),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    invocation_id: Mapped[uuid.UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    attempt_id: Mapped[uuid.UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    provider_definition_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    model_definition_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    canonical_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    measurement_status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'measured'")
    )
    amount_minor_units: Mapped[int | None] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = _created_at()


class AIAuditEvent(Base):
    __tablename__ = "ai_audit_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["actor_user_id"],
            ["user_accounts.id"],
            name="fk_ai_audit_events_actor",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["project_id"],
            ["paint_projects.id"],
            name="fk_ai_audit_events_project",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["credential_id"],
            ["credential_records.id"],
            name="fk_ai_audit_events_credential",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["invocation_id"],
            ["invocation_requests.id"],
            name="fk_ai_audit_events_invocation",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["attempt_id"],
            ["invocation_attempts.id"],
            name="fk_ai_audit_events_attempt",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["provider_definition_id"],
            ["provider_definitions.id"],
            name="fk_ai_audit_events_provider",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["model_definition_id"],
            ["model_definitions.id"],
            name="fk_ai_audit_events_model",
            ondelete="RESTRICT",
        ),
        Index("ix_ai_audit_events_actor_created", "actor_user_id", "created_at"),
        Index("ix_ai_audit_events_project_created", "project_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    actor_user_id: Mapped[uuid.UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    product_space: Mapped[str] = mapped_column(String(64), nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    credential_id: Mapped[uuid.UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    invocation_id: Mapped[uuid.UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    attempt_id: Mapped[uuid.UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    provider_definition_id: Mapped[uuid.UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    model_definition_id: Mapped[uuid.UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    request_id: Mapped[uuid.UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    safe_metadata: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = _created_at()


class AICommandIdempotencyRecord(Base):
    __tablename__ = "ai_command_idempotency_records"
    __table_args__ = (
        ForeignKeyConstraint(
            ["requesting_user_id"],
            ["user_accounts.id"],
            name="fk_ai_command_idempotency_user",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "requesting_user_id",
            "command_scope",
            "idempotency_key",
            name="uq_ai_command_idempotency_scope",
        ),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    requesting_user_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    command_scope: Mapped[str] = mapped_column(String(256), nullable=False)
    idempotency_key: Mapped[uuid.UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    response_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    http_status: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = _created_at()
