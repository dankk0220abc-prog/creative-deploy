"""add phase3a encrypted credential security

Revision ID: 3a02d8f0c5e3
Revises: 3a01c7e9b4d2
Create Date: 2026-08-05 00:01:00
"""

# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3a02d8f0c5e3"
down_revision: str | Sequence[str] | None = "3a01c7e9b4d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "credential_records",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_user_id", sa.UUID(), nullable=False),
        sa.Column("provider_definition_id", sa.UUID(), nullable=False),
        sa.Column("provider_key", sa.String(64), nullable=False),
        sa.Column("key_fingerprint", sa.String(96), nullable=False),
        sa.Column("last_four", sa.String(4), nullable=True),
        sa.Column("alias", sa.String(120), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("encryption_version", sa.String(64), nullable=True),
        sa.Column("data_algorithm", sa.String(32), nullable=True),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=True),
        sa.Column("data_nonce", sa.LargeBinary(), nullable=True),
        sa.Column("data_authentication_tag", sa.LargeBinary(), nullable=True),
        sa.Column("wrapped_dek", sa.LargeBinary(), nullable=True),
        sa.Column("wrap_algorithm", sa.String(32), nullable=True),
        sa.Column("wrap_nonce", sa.LargeBinary(), nullable=True),
        sa.Column("wrap_authentication_tag", sa.LargeBinary(), nullable=True),
        sa.Column("aad_version", sa.String(64), nullable=True),
        sa.Column("replaces_credential_id", sa.UUID(), nullable=True),
        sa.Column("last_validation_status", sa.String(64), nullable=True),
        sa.Column("last_successful_validation_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revision", sa.Integer(), server_default=sa.text("1"), nullable=False),
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
            "status IN ('active','revoked','replaced')",
            name=op.f("ck_credential_records_status_allowed"),
        ),
        sa.CheckConstraint(
            "replaces_credential_id IS NULL OR replaces_credential_id <> id",
            name=op.f("ck_credential_records_no_self_replacement"),
        ),
        sa.CheckConstraint(
            """(status = 'active' AND revoked_at IS NULL AND replaced_at IS NULL AND encryption_version IS NOT NULL AND data_algorithm = 'AES-256-GCM' AND ciphertext IS NOT NULL AND octet_length(ciphertext) > 0 AND data_nonce IS NOT NULL AND octet_length(data_nonce) = 12 AND data_authentication_tag IS NOT NULL AND octet_length(data_authentication_tag) = 16 AND wrapped_dek IS NOT NULL AND octet_length(wrapped_dek) > 0 AND wrap_algorithm = 'AES-256-GCM' AND wrap_nonce IS NOT NULL AND octet_length(wrap_nonce) = 12 AND wrap_authentication_tag IS NOT NULL AND octet_length(wrap_authentication_tag) = 16 AND aad_version IS NOT NULL) OR (status = 'revoked' AND revoked_at IS NOT NULL AND replaced_at IS NULL AND encryption_version IS NULL AND data_algorithm IS NULL AND ciphertext IS NULL AND data_nonce IS NULL AND data_authentication_tag IS NULL AND wrapped_dek IS NULL AND wrap_algorithm IS NULL AND wrap_nonce IS NULL AND wrap_authentication_tag IS NULL AND aad_version IS NULL) OR (status = 'replaced' AND replaced_at IS NOT NULL AND revoked_at IS NULL AND encryption_version IS NULL AND data_algorithm IS NULL AND ciphertext IS NULL AND data_nonce IS NULL AND data_authentication_tag IS NULL AND wrapped_dek IS NULL AND wrap_algorithm IS NULL AND wrap_nonce IS NULL AND wrap_authentication_tag IS NULL AND aad_version IS NULL)""",
            name=op.f("ck_credential_records_lifecycle_envelope"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["user_accounts.id"],
            name="fk_credential_records_owner_user_accounts",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["provider_definition_id"],
            ["provider_definitions.id"],
            name="fk_credential_records_provider_provider_definitions",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["replaces_credential_id"],
            ["credential_records.id"],
            name="fk_credential_records_replaces_credential_records",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_credential_records")),
        sa.UniqueConstraint(
            "replaces_credential_id", name="uq_credential_records_replacement_lineage"
        ),
    )
    op.create_index(
        "ix_credential_records_owner_status", "credential_records", ["owner_user_id", "status"]
    )
    op.create_table(
        "credential_project_grants",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("credential_id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("granted_by_user_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revision", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(
            ["credential_id"],
            ["credential_records.id"],
            name="fk_credential_project_grants_credential_credential_records",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["paint_projects.id"],
            name="fk_credential_project_grants_project_paint_projects",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["granted_by_user_id"],
            ["user_accounts.id"],
            name="fk_credential_project_grants_granted_by_user_accounts",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_credential_project_grants")),
    )
    op.create_index(
        "ix_credential_project_grants_project",
        "credential_project_grants",
        ["project_id", "credential_id"],
    )
    op.create_index(
        "uq_credential_project_grants_active",
        "credential_project_grants",
        ["credential_id", "project_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.execute(
        sa.text("""
        CREATE FUNCTION phase3a_verify_credential_replacement() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE old_row credential_records%ROWTYPE;
        BEGIN
            IF NEW.replaces_credential_id IS NULL THEN RETURN NEW; END IF;
            SELECT * INTO old_row FROM credential_records WHERE id = NEW.replaces_credential_id;
            IF NOT FOUND OR old_row.owner_user_id <> NEW.owner_user_id
               OR old_row.provider_definition_id <> NEW.provider_definition_id
               OR old_row.provider_key <> NEW.provider_key THEN
                RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'Credential replacement lineage mismatch';
            END IF;
            RETURN NEW;
        END
        $$;
        CREATE CONSTRAINT TRIGGER credential_replacement_identity
        AFTER INSERT OR UPDATE OF replaces_credential_id, owner_user_id, provider_definition_id, provider_key
        ON credential_records DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION phase3a_verify_credential_replacement();
    """)
    )


def downgrade() -> None:
    op.execute(
        sa.text("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM credential_project_grants)
               OR EXISTS (SELECT 1 FROM credential_records)
               OR EXISTS (SELECT 1 FROM credential_records WHERE replaces_credential_id IS NOT NULL)
            THEN
                RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'Phase 3A Migration B downgrade refused: Credential history exists';
            END IF;
        END
        $$;
    """)
    )
    op.execute(sa.text("DROP FUNCTION phase3a_verify_credential_replacement() CASCADE"))
    op.drop_index("uq_credential_project_grants_active", table_name="credential_project_grants")
    op.drop_index("ix_credential_project_grants_project", table_name="credential_project_grants")
    op.drop_table("credential_project_grants")
    op.drop_index("ix_credential_records_owner_status", table_name="credential_records")
    op.drop_table("credential_records")
