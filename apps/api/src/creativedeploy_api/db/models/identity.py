"""Governed internal identity, OIDC session, and project-membership models."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import conv

from creativedeploy_api.db.base import Base

PROJECT_MEMBERSHIP_REVIEWER = "reviewer"


class UserAccount(Base):
    """One stable internal human user, independent of mutable profile claims."""

    __tablename__ = "user_accounts"
    __table_args__ = (
        CheckConstraint(
            "length(display_name) >= 1 AND display_name = btrim(display_name)",
            name=conv("ck_user_accounts_display_name_normalized"),
        ),
        CheckConstraint(
            "email IS NULL OR (length(email) >= 3 AND email = lower(btrim(email)))",
            name=conv("ck_user_accounts_email_normalized"),
        ),
        CheckConstraint(
            "updated_at >= created_at",
            name=conv("ck_user_accounts_updated_at_not_before_created_at"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class ExternalIdentity(Base):
    """Provider-neutral external identity keyed only by issuer plus subject."""

    __tablename__ = "external_identities"
    __table_args__ = (
        CheckConstraint(
            "length(issuer) >= 1 AND issuer = btrim(issuer)",
            name=conv("ck_external_identities_issuer_normalized"),
        ),
        CheckConstraint(
            "length(subject) >= 1 AND subject = btrim(subject)",
            name=conv("ck_external_identities_subject_normalized"),
        ),
        UniqueConstraint(
            "issuer",
            "subject",
            name="uq_external_identities_issuer_subject",
        ),
        Index("ix_external_identities_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    issuer: Mapped[str] = mapped_column(String(512), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    email_snapshot: Mapped[str | None] = mapped_column(String(320), nullable=True)
    display_name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    last_authenticated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class ProjectMembership(Base):
    """An explicit reviewer assignment for one existing user and project."""

    __tablename__ = "project_memberships"
    __table_args__ = (
        CheckConstraint(
            f"role = '{PROJECT_MEMBERSHIP_REVIEWER}'",
            name=conv("ck_project_memberships_role_allowed"),
        ),
        UniqueConstraint(
            "paint_project_id",
            "user_id",
            name="uq_project_memberships_project_user",
        ),
        ForeignKeyConstraint(
            ["paint_project_id"],
            ["paint_projects.id"],
            name="fk_project_memberships_project_paint_projects",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["user_id"],
            ["user_accounts.id"],
            name="fk_project_memberships_user_user_accounts",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["assigned_by_user_id"],
            ["user_accounts.id"],
            name="fk_project_memberships_assigned_by_user_accounts",
            ondelete="RESTRICT",
        ),
        Index("ix_project_memberships_user_project", "user_id", "paint_project_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    paint_project_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=PROJECT_MEMBERSHIP_REVIEWER,
        server_default=text(f"'{PROJECT_MEMBERSHIP_REVIEWER}'"),
    )
    assigned_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class OidcLoginFlow(Base):
    """A one-time browser-bound OIDC state, nonce, and PKCE transaction."""

    __tablename__ = "oidc_login_flows"
    __table_args__ = (
        CheckConstraint(
            "expires_at > created_at",
            name=conv("ck_oidc_login_flows_expiry_after_creation"),
        ),
        UniqueConstraint("state_hash", name="uq_oidc_login_flows_state_hash"),
        Index("ix_oidc_login_flows_expires_at", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    state_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    browser_binding_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    nonce: Mapped[str] = mapped_column(String(128), nullable=False)
    code_verifier: Mapped[str] = mapped_column(String(128), nullable=False)
    return_to: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuthSession(Base):
    """One revocable, opaque, server-side authenticated browser session."""

    __tablename__ = "auth_sessions"
    __table_args__ = (
        CheckConstraint(
            "expires_at > created_at",
            name=conv("ck_auth_sessions_expiry_after_creation"),
        ),
        CheckConstraint(
            "last_seen_at >= created_at",
            name=conv("ck_auth_sessions_last_seen_not_before_creation"),
        ),
        UniqueConstraint("token_hash", name="uq_auth_sessions_token_hash"),
        Index("ix_auth_sessions_user_expires_at", "user_id", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    csrf_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    oidc_issuer: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
