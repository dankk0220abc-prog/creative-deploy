"""drop persisted credential plaintext fragments

Revision ID: 6a01b2c3d4e6
Revises: 5a01b2c3d4e5
Create Date: 2026-08-14 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6a01b2c3d4e6"
down_revision: str | Sequence[str] | None = "5a01b2c3d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Irreversible by design: existing plaintext suffix values are redacted.
    op.drop_column("credential_records", "last_four")


def downgrade() -> None:
    # Historical plaintext values cannot and must not be reconstructed.
    op.add_column(
        "credential_records",
        sa.Column("last_four", sa.String(length=4), nullable=True),
    )
