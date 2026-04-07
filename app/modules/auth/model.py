"""
Auth OTP model.
"""

from sqlalchemy import Column, Integer, String, DateTime, func
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
