"""
User SQLAlchemy models: User and UserSubscription.
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, func
from app.core.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=True)
    email = Column(String(255), unique=True, nullable=True, index=True)
    phone = Column(String(20), unique=True, nullable=True, index=True)

    is_email_verified = Column(Boolean, default=False, nullable=False)
    is_phone_verified = Column(Boolean, default=False, nullable=False)
    is_profile_completed = Column(Boolean, default=False, nullable=False)

    status = Column(String(20), default="active", nullable=False)  # active, inactive, suspended

    last_login_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"


class UserSubscription(Base):
    __tablename__ = "user_subscriptions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    plan_id = Column(Integer, nullable=True)  # FK to plans table (future)
    status = Column(String(20), default="trial", nullable=False)  # active, trial, expired, cancelled

    starts_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    trial_ends_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<UserSubscription(id={self.id}, user_id={self.user_id}, status={self.status})>"
