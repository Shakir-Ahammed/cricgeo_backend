"""Seed free subscription plan

Revision ID: g1h2i3j4k5l6
Revises: f1g2h3i4j5k6
Create Date: 2026-05-21 00:00:00.000000

Strategy: data migration.
This migration inserts the canonical 'free' plan row into subscription_plans.
It must run AFTER the CC-1 schema migration creates the subscription_plans table.
A table-existence guard makes the migration safe to run out of order — it is a
no-op if the table does not yet exist and must be re-applied after CC-1.

The assign_free_plan() service function depends on this row (slug='free').
"""

from alembic import op
import sqlalchemy as sa

revision = "g1h2i3j4k5l6"
down_revision = "f1g2h3i4j5k6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # Guard: subscription_plans table is created by the CC-1 schema migration.
    # If that migration hasn't run yet, skip and re-apply this migration after CC-1.
    if "subscription_plans" not in sa.inspect(bind).get_table_names():
        return

    op.execute(
        sa.text(
            """
            INSERT INTO subscription_plans (
                name, slug, price_monthly, price_yearly, currency,
                features, max_matches_per_month, max_teams, is_active, created_at
            ) VALUES (
                'Free', 'free', 0.00, 0.00, 'BDT',
                '{"live_scoring": true, "scorecard": true, "advanced_stats": false}',
                5, 2, true, now()
            )
            ON CONFLICT (slug) DO NOTHING
            """
        )
    )

    # Partial index for the active-subscription lookup.
    # Also created by CC-1 autogenerate (via UserSubscription.__table_args__);
    # this block is a safety net if the index was missed in that migration.
    if "user_subscriptions" in sa.inspect(bind).get_table_names():
        existing_indexes = {
            idx["name"]
            for idx in sa.inspect(bind).get_indexes("user_subscriptions")
        }
        if "idx_user_subscriptions_active_user" not in existing_indexes:
            op.create_index(
                "idx_user_subscriptions_active_user",
                "user_subscriptions",
                ["user_id"],
                postgresql_where=sa.text("status = 'active'"),
            )


def downgrade() -> None:
    bind = op.get_bind()

    if "user_subscriptions" in sa.inspect(bind).get_table_names():
        existing_indexes = {
            idx["name"]
            for idx in sa.inspect(bind).get_indexes("user_subscriptions")
        }
        if "idx_user_subscriptions_active_user" in existing_indexes:
            op.drop_index(
                "idx_user_subscriptions_active_user",
                table_name="user_subscriptions",
            )

    if "subscription_plans" in sa.inspect(bind).get_table_names():
        op.execute(
            sa.text("DELETE FROM subscription_plans WHERE slug = 'free'")
        )
