"""Add OTP table and profile_completed field

Revision ID: a1b2c3d4e5f6
Revises: ffa7d372b27b
Create Date: 2026-04-07 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'ffa7d372b27b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create Gender enum
    bind = op.get_bind()
    gender_enum = sa.Enum('MALE', 'FEMALE', 'OTHER', name='gender')
    gender_enum.create(bind, checkfirst=True)
    
    # Create OTP table
    op.create_table('otps',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('identifier', sa.String(length=255), nullable=False),
        sa.Column('code_hash', sa.String(length=255), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_otps_id'), 'otps', ['id'], unique=False)
    op.create_index(op.f('ix_otps_identifier'), 'otps', ['identifier'], unique=False)
    
    # Add new columns to users table
    op.add_column('users', sa.Column('profile_completed', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('gender', gender_enum, nullable=True))
    op.add_column('users', sa.Column('profile_image', sa.String(length=500), nullable=True))
    
    # Make name nullable for OTP flow
    op.alter_column('users', 'name',
               existing_type=sa.String(length=100),
               nullable=True)


def downgrade() -> None:
    # Revert name to not nullable
    op.alter_column('users', 'name',
               existing_type=sa.String(length=100),
               nullable=False)
    
    # Remove new columns from users table
    op.drop_column('users', 'profile_image')
    op.drop_column('users', 'gender')
    op.drop_column('users', 'profile_completed')
    
    # Drop OTP table
    op.drop_index(op.f('ix_otps_identifier'), table_name='otps')
    op.drop_index(op.f('ix_otps_id'), table_name='otps')
    op.drop_table('otps')
    
    # Drop Gender enum
    bind = op.get_bind()
    gender_enum = sa.Enum('MALE', 'FEMALE', 'OTHER', name='gender')
    gender_enum.drop(bind, checkfirst=True)
