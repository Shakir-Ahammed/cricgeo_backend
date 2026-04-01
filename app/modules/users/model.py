"""
User SQLAlchemy model
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Enum as SQLEnum, func
from app.core.db import Base
import enum


class PlanType(str, enum.Enum):
    FREE = "free"
    PREMIUM = "premium"
    PRO = "pro"


class UserType(str, enum.Enum):
    ADMIN = "admin"
    MEMBER = "member"


class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class AuthProvider(str, enum.Enum):
    LOCAL = "local"
    GOOGLE = "google"


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(20), nullable=True)
    hashed_password = Column(String(255), nullable=True)
    
    provider = Column(SQLEnum(AuthProvider), default=AuthProvider.LOCAL, nullable=False)
    provider_user_id = Column(String(255), nullable=True, index=True)
    
    plan = Column(SQLEnum(PlanType), default=PlanType.FREE, nullable=False)
    user_type = Column(SQLEnum(UserType), default=UserType.MEMBER, nullable=False)
    is_email_verified = Column(Boolean, default=False, nullable=False)
    status = Column(SQLEnum(UserStatus), default=UserStatus.ACTIVE, nullable=False)
    
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by = Column(Integer, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    updated_by = Column(Integer, nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"
