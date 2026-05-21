"""add_venues_and_subscriptions_tables

Revision ID: 081c528ba146
Revises: g1h2i3j4k5l6
Create Date: 2026-05-21 15:09:08.209251

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '081c528ba146'
down_revision = 'g1h2i3j4k5l6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create subscription_plans (must come before user_subscriptions FK)
    op.create_table('subscription_plans',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('slug', sa.String(length=50), nullable=False),
    sa.Column('price_monthly', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('price_yearly', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('features', sa.JSON(), nullable=True),
    sa.Column('max_matches_per_month', sa.Integer(), nullable=True),
    sa.Column('max_teams', sa.Integer(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_subscription_plans_id'), 'subscription_plans', ['id'], unique=False)
    op.create_index(op.f('ix_subscription_plans_slug'), 'subscription_plans', ['slug'], unique=True)

    # Create venues
    op.create_table('venues',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=150), nullable=False),
    sa.Column('address', sa.Text(), nullable=True),
    sa.Column('city_id', sa.Integer(), nullable=True),
    sa.Column('country_id', sa.Integer(), nullable=True),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('latitude', sa.Numeric(precision=9, scale=6), nullable=True),
    sa.Column('longitude', sa.Numeric(precision=9, scale=6), nullable=True),
    sa.Column('is_public', sa.Boolean(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['city_id'], ['cities.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['country_id'], ['countries.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_venues_city_id'), 'venues', ['city_id'], unique=False)
    op.create_index(op.f('ix_venues_country_id'), 'venues', ['country_id'], unique=False)
    op.create_index(op.f('ix_venues_created_by'), 'venues', ['created_by'], unique=False)
    op.create_index(op.f('ix_venues_id'), 'venues', ['id'], unique=False)

    # Upgrade user_subscriptions to reference subscription_plans
    # Nullify any orphaned plan_id values before adding the FK
    op.execute(sa.text("UPDATE user_subscriptions SET plan_id = NULL WHERE plan_id IS NOT NULL"))
    op.create_index(op.f('ix_user_subscriptions_plan_id'), 'user_subscriptions', ['plan_id'], unique=False)
    op.create_index('idx_user_subscriptions_active_user', 'user_subscriptions', ['user_id'],
                    unique=False, postgresql_where=sa.text("status = 'active'"))
    op.create_foreign_key('fk_user_subscriptions_plan_id', 'user_subscriptions',
                          'subscription_plans', ['plan_id'], ['id'], ondelete='RESTRICT')


def downgrade() -> None:
    op.drop_constraint('fk_user_subscriptions_plan_id', 'user_subscriptions', type_='foreignkey')
    op.drop_index(op.f('ix_user_subscriptions_plan_id'), table_name='user_subscriptions')
    op.drop_index('idx_user_subscriptions_active_user', table_name='user_subscriptions',
                  postgresql_where=sa.text("status = 'active'"))
    op.drop_index(op.f('ix_venues_id'), table_name='venues')
    op.drop_index(op.f('ix_venues_created_by'), table_name='venues')
    op.drop_index(op.f('ix_venues_country_id'), table_name='venues')
    op.drop_index(op.f('ix_venues_city_id'), table_name='venues')
    op.drop_table('venues')
    op.drop_index(op.f('ix_subscription_plans_slug'), table_name='subscription_plans')
    op.drop_index(op.f('ix_subscription_plans_id'), table_name='subscription_plans')
    op.drop_table('subscription_plans')
