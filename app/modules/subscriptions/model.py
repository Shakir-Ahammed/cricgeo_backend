from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, text
from sqlalchemy.sql import func

from app.core.db import Base


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name = Column(String(100), nullable=False)
    slug = Column(String(50), unique=True, nullable=False, index=True)
    price_monthly = Column(Numeric(10, 2), nullable=False, default=0)
    price_yearly = Column(Numeric(10, 2), nullable=False, default=0)
    currency = Column(String(3), nullable=False, default="BDT")
    features = Column(JSON, nullable=True)
    max_matches_per_month = Column(Integer, nullable=True)
    max_teams = Column(Integer, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class UserSubscription(Base):
    __tablename__ = "user_subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_id = Column(Integer, ForeignKey("subscription_plans.id", ondelete="RESTRICT"), nullable=False, index=True)
    status = Column(String(20), nullable=False)
    starts_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    trial_ends_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    __table_args__ = (
        # Partial index: optimises the common lookup (user_id, status='active').
        # Picked up by alembic autogenerate when the table is first created.
        Index(
            "idx_user_subscriptions_active_user",
            "user_id",
            postgresql_where=text("status = 'active'"),
        ),
    )
