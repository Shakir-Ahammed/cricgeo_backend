"""Add is_profile_completed to users

Revision ID: f1g2h3i4j5k6
Revises: e1f2a3b4c5d6
Create Date: 2026-04-21 00:01:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "f1g2h3i4j5k6"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_profile_completed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "is_profile_completed")
