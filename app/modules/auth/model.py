"""
Auth models: OTP and RefreshToken.
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, func
from app.core.db import Base


class OTP(Base):
    __tablename__ = "otps"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    identifier = Column(String(255), nullable=False, index=True)  # email
    code_hash = Column(String(255), nullable=False)  # hashed OTP code
    expires_at = Column(DateTime(timezone=True), nullable=False)
    attempts = Column(Integer, default=0, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    def __repr__(self) -> str:
        return f"<OTP(id={self.id}, identifier={self.identifier})>"


class RefreshToken(Base):
    """
    Refresh token model for secure token rotation and multi-device session management.
    Stores hashed refresh tokens to prevent token theft and enable reuse detection.
    """
    __tablename__ = "refresh_tokens"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(255), nullable=False, unique=True, index=True)  # SHA256 hash of refresh token
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    is_revoked = Column(Boolean, default=False, nullable=False, index=True)
    
    # Optional device tracking for multi-device session management
    device_info = Column(String(500), nullable=True)  # User-Agent string
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self) -> str:
        return f"<RefreshToken(id={self.id}, user_id={self.user_id}, revoked={self.is_revoked})>"
