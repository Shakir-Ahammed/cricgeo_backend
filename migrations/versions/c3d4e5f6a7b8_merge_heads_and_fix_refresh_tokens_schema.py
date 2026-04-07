"""merge heads and fix refresh_tokens schema

Revision ID: c3d4e5f6a7b8
Revises: a1b2c3d4e5f6, b1c2d3e4f5g6
Create Date: 2026-04-08 20:45:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c3d4e5f6a7b8"
down_revision = ("a1b2c3d4e5f6", "b1c2d3e4f5g6")
branch_labels = None
depends_on = None


def _has_table(bind, table_name: str) -> bool:
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _has_column(bind, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    columns = inspector.get_columns(table_name)
    return any(col["name"] == column_name for col in columns)


def upgrade() -> None:
    bind = op.get_bind()

    if not _has_table(bind, "refresh_tokens"):
        return

    # Ensure columns expected by app.modules.auth.model.RefreshToken exist.
    if not _has_column(bind, "refresh_tokens", "is_revoked"):
        op.add_column(
            "refresh_tokens",
            sa.Column("is_revoked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )

    if not _has_column(bind, "refresh_tokens", "device_info"):
        op.add_column("refresh_tokens", sa.Column("device_info", sa.String(length=500), nullable=True))

    if not _has_column(bind, "refresh_tokens", "ip_address"):
        op.add_column("refresh_tokens", sa.Column("ip_address", sa.String(length=45), nullable=True))

    if not _has_column(bind, "refresh_tokens", "revoked_at"):
        op.add_column("refresh_tokens", sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))

    # Helpful indexes for refresh token validation/rotation.
    inspector = sa.inspect(bind)
    existing_indexes = {idx["name"] for idx in inspector.get_indexes("refresh_tokens")}

    if "ix_refresh_tokens_is_revoked" not in existing_indexes:
        op.create_index("ix_refresh_tokens_is_revoked", "refresh_tokens", ["is_revoked"], unique=False)

    if "ix_refresh_tokens_expires_at" not in existing_indexes:
        op.create_index("ix_refresh_tokens_expires_at", "refresh_tokens", ["expires_at"], unique=False)


def downgrade() -> None:
    # Merge+compatibility migration. Keep schema additions in place for safety.
    pass
