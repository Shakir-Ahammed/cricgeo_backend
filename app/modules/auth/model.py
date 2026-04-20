"""
Auth models: OTP, UserAuthProvider, and UserSession.
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, UniqueConstraint, func
from app.core.db import Base


class OTP(Base):
    __tablename__ = "otps"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    identifier = Column(String(255), nullable=False, index=True)  # email or phone
    code_hash = Column(String(255), nullable=False)
    type = Column(String(20), nullable=False, default="login")  # login, signup

    expires_at = Column(DateTime(timezone=True), nullable=False)
    attempts = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<OTP(id={self.id}, identifier={self.identifier}, type={self.type})>"


class UserAuthProvider(Base):
    """
    OAuth provider links for a user (Google, Apple, Facebook, etc.).
    One user can have multiple providers.
    """
    __tablename__ = "user_auth_providers"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String(50), nullable=False)  # google, apple, facebook
    provider_user_id = Column(String(255), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id", name="uq_auth_provider_user"),
    )

    def __repr__(self) -> str:
        return f"<UserAuthProvider(id={self.id}, user_id={self.user_id}, provider={self.provider})>"


class UserSession(Base):
    """
    User session / refresh token table for secure multi-device session management.
    """
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    refresh_token_hash = Column(String(255), nullable=False, unique=True, index=True)

    device_info = Column(String(500), nullable=True)
    ip_address = Column(String(45), nullable=True)

    is_revoked = Column(Boolean, default=False, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<UserSession(id={self.id}, user_id={self.user_id}, revoked={self.is_revoked})>"
