"""add_team_join_requests

Revision ID: a1b2c3d4e5f7
Revises: 6075a571e00d
Create Date: 2026-05-21 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f7'
down_revision = '6075a571e00d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'team_join_requests',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('team_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('invitation_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('message', sa.String(200), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('responded_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invitation_id'], ['team_invitations.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['responded_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('team_id', 'user_id', name='uq_team_join_request_team_user'),
    )
    op.create_index('ix_team_join_requests_id', 'team_join_requests', ['id'])
    op.create_index('ix_team_join_requests_team_id', 'team_join_requests', ['team_id'])
    op.create_index('ix_team_join_requests_user_id', 'team_join_requests', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_team_join_requests_user_id', table_name='team_join_requests')
    op.drop_index('ix_team_join_requests_team_id', table_name='team_join_requests')
    op.drop_index('ix_team_join_requests_id', table_name='team_join_requests')
    op.drop_table('team_join_requests')
