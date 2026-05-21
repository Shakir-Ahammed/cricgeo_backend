"""add_username_to_profiles

Revision ID: ad377d760965
Revises: 081c528ba146
Create Date: 2026-05-21 16:45:43.132966

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ad377d760965'
down_revision = '081c528ba146'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('profiles', sa.Column('username', sa.String(50), nullable=True))
    op.create_index('ix_profiles_username', 'profiles', ['username'], unique=True)
    # Case-insensitive unique index (matches DBML spec)
    op.execute(
        "CREATE UNIQUE INDEX idx_profiles_username_lower ON profiles (lower(username)) "
        "WHERE username IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_profiles_username_lower")
    op.drop_index('ix_profiles_username', table_name='profiles')
    op.drop_column('profiles', 'username')
