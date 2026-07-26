"""Command idempotency persistence model for guarded future services."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import conv

from creativedeploy_api.db.base import Base
from creativedeploy_api.db.models.constants import (
    IDEMPOTENCY_STATUS_COMPLETED,
    IDEMPOTENCY_STATUSES,
    PAYLOAD_HASH_PATTERN,
    POSTGRESQL_MACHINE_TOKEN_PATTERN,
)


def _sql_values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


class CommandIdempotencyRecord(Base):
    """A unique command replay boundary; execution behavior is not implemented here."""

    __tablename__ = "command_idempotency_records"
    __table_args__ = (
        CheckConstraint(
            "length(scope_key) >= 1 AND scope_key = btrim(scope_key)",
            name=conv("ck_command_idempotency_records_scope_key_normalized"),
        ),
        CheckConstraint(
            "length(principal_id) >= 1 AND principal_id = btrim(principal_id)",
            name=conv("ck_command_idempotency_records_principal_id_normalized"),
        ),
        CheckConstraint(
            f"command_type ~ '{POSTGRESQL_MACHINE_TOKEN_PATTERN}'",
            name=conv("ck_command_idempotency_records_command_type_format"),
        ),
        CheckConstraint(
            f"payload_hash ~ '{PAYLOAD_HASH_PATTERN}'",
            name=conv("ck_command_idempotency_records_payload_hash_format"),
        ),
        CheckConstraint(
            f"execution_status ~ '{POSTGRESQL_MACHINE_TOKEN_PATTERN}'",
            name=conv("ck_command_idempotency_records_execution_status_format"),
        ),
        CheckConstraint(
            f"execution_status IN ({_sql_values(IDEMPOTENCY_STATUSES)})",
            name=conv("ck_command_idempotency_records_execution_status_allowed"),
        ),
        CheckConstraint(
            f"resource_type IS NULL OR resource_type ~ '{POSTGRESQL_MACHINE_TOKEN_PATTERN}'",
            name=conv("ck_command_idempotency_records_resource_type_format"),
        ),
        CheckConstraint(
            "http_status IS NULL OR http_status BETWEEN 100 AND 599",
            name=conv("ck_command_idempotency_records_http_status_valid"),
        ),
        CheckConstraint(
            "response_snapshot IS NULL OR jsonb_typeof(response_snapshot) = 'object'",
            name=conv("ck_command_idempotency_records_response_snapshot_is_object"),
        ),
        CheckConstraint(
            f"execution_status <> '{IDEMPOTENCY_STATUS_COMPLETED}' "
            "OR (resource_type IS NOT NULL "
            "AND resource_id IS NOT NULL "
            "AND http_status IS NOT NULL "
            "AND response_snapshot IS NOT NULL)",
            name=conv("ck_command_idempotency_records_result_matches_execution_status"),
        ),
        CheckConstraint(
            "expires_at > created_at",
            name=conv("ck_command_idempotency_records_expiry_after_creation"),
        ),
        UniqueConstraint(
            "scope_key",
            "idempotency_key",
            name="uq_command_idempotency_records_scope_key_idempotency_key",
        ),
        Index("ix_command_idempotency_records_expires_at", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    scope_key: Mapped[str] = mapped_column(String(512), nullable=False)
    principal_id: Mapped[str] = mapped_column(String(128), nullable=False)
    command_type: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=False,
    )
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    execution_status: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=True,
    )
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_snapshot: Mapped[dict[str, object] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
