"""add governed identity authorization and private storage

Revision ID: 2b1c4d5e6f70
Revises: 7f3a2b9c4d1e
Create Date: 2026-07-31 00:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "2b1c4d5e6f70"
down_revision: str | Sequence[str] | None = "7f3a2b9c4d1e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add stable users, OIDC sessions, reviewer membership, and S3 metadata support."""
    op.create_table(
        "user_accounts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(display_name) >= 1 AND display_name = btrim(display_name)",
            name=op.f("ck_user_accounts_display_name_normalized"),
        ),
        sa.CheckConstraint(
            "email IS NULL OR (length(email) >= 3 AND email = lower(btrim(email)))",
            name=op.f("ck_user_accounts_email_normalized"),
        ),
        sa.CheckConstraint(
            "updated_at >= created_at",
            name=op.f("ck_user_accounts_updated_at_not_before_created_at"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_accounts")),
    )

    op.create_table(
        "external_identities",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("issuer", sa.String(length=512), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("email_snapshot", sa.String(length=320), nullable=True),
        sa.Column("display_name_snapshot", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_authenticated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(issuer) >= 1 AND issuer = btrim(issuer)",
            name=op.f("ck_external_identities_issuer_normalized"),
        ),
        sa.CheckConstraint(
            "length(subject) >= 1 AND subject = btrim(subject)",
            name=op.f("ck_external_identities_subject_normalized"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user_accounts.id"],
            name=op.f("fk_external_identities_user_id_user_accounts"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_external_identities")),
        sa.UniqueConstraint(
            "issuer",
            "subject",
            name="uq_external_identities_issuer_subject",
        ),
    )
    op.create_index(
        "ix_external_identities_user_id",
        "external_identities",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "project_memberships",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("paint_project_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "role",
            sa.String(length=32),
            server_default=sa.text("'reviewer'"),
            nullable=False,
        ),
        sa.Column("assigned_by_user_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role = 'reviewer'",
            name=op.f("ck_project_memberships_role_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["paint_project_id"],
            ["paint_projects.id"],
            name="fk_project_memberships_project_paint_projects",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user_accounts.id"],
            name="fk_project_memberships_user_user_accounts",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["assigned_by_user_id"],
            ["user_accounts.id"],
            name="fk_project_memberships_assigned_by_user_accounts",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project_memberships")),
        sa.UniqueConstraint(
            "paint_project_id",
            "user_id",
            name="uq_project_memberships_project_user",
        ),
    )
    op.create_index(
        "ix_project_memberships_user_project",
        "project_memberships",
        ["user_id", "paint_project_id"],
        unique=False,
    )

    op.create_table(
        "oidc_login_flows",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("state_hash", sa.String(length=64), nullable=False),
        sa.Column("browser_binding_hash", sa.String(length=64), nullable=False),
        sa.Column("nonce", sa.String(length=128), nullable=False),
        sa.Column("code_verifier", sa.String(length=128), nullable=False),
        sa.Column("return_to", sa.String(length=512), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "expires_at > created_at",
            name=op.f("ck_oidc_login_flows_expiry_after_creation"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_oidc_login_flows")),
        sa.UniqueConstraint("state_hash", name="uq_oidc_login_flows_state_hash"),
    )
    op.create_index(
        "ix_oidc_login_flows_expires_at",
        "oidc_login_flows",
        ["expires_at"],
        unique=False,
    )

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("csrf_token_hash", sa.String(length=64), nullable=False),
        sa.Column("oidc_issuer", sa.String(length=512), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "expires_at > created_at",
            name=op.f("ck_auth_sessions_expiry_after_creation"),
        ),
        sa.CheckConstraint(
            "last_seen_at >= created_at",
            name=op.f("ck_auth_sessions_last_seen_not_before_creation"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user_accounts.id"],
            name=op.f("fk_auth_sessions_user_id_user_accounts"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_sessions")),
        sa.UniqueConstraint("token_hash", name="uq_auth_sessions_token_hash"),
    )
    op.create_index(
        "ix_auth_sessions_user_expires_at",
        "auth_sessions",
        ["user_id", "expires_at"],
        unique=False,
    )

    op.drop_constraint(
        op.f("ck_image_assets_storage_provider_allowed"),
        "image_assets",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_image_assets_storage_provider_allowed"),
        "image_assets",
        "storage_provider IN ('local_filesystem','s3')",
    )


def downgrade() -> None:
    """Restore the sealed pre-identity schema without deleting existing image objects."""
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM auth_sessions)
                   OR EXISTS (SELECT 1 FROM oidc_login_flows)
                   OR EXISTS (SELECT 1 FROM project_memberships)
                   OR EXISTS (SELECT 1 FROM external_identities)
                   OR EXISTS (SELECT 1 FROM user_accounts)
                   OR EXISTS (
                       SELECT 1
                       FROM image_assets
                       WHERE storage_provider = 's3'
                   )
                THEN
                    RAISE EXCEPTION USING
                        ERRCODE = '55000',
                        MESSAGE = 'Phase 2B-1 downgrade refused: governed facts exist';
                END IF;
            END
            $$;
            """
        )
    )
    op.drop_constraint(
        op.f("ck_image_assets_storage_provider_allowed"),
        "image_assets",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_image_assets_storage_provider_allowed"),
        "image_assets",
        "storage_provider IN ('local_filesystem')",
    )

    op.drop_index("ix_auth_sessions_user_expires_at", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_index("ix_oidc_login_flows_expires_at", table_name="oidc_login_flows")
    op.drop_table("oidc_login_flows")
    op.drop_index(
        "ix_project_memberships_user_project",
        table_name="project_memberships",
    )
    op.drop_table("project_memberships")
    op.drop_index("ix_external_identities_user_id", table_name="external_identities")
    op.drop_table("external_identities")
    op.drop_table("user_accounts")
