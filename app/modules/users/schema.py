"""
User Pydantic schemas
"""

from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional
from datetime import datetime


class UserOut(BaseModel):
    id: int
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    is_email_verified: bool
    is_phone_verified: bool
    is_profile_completed: bool = False
    status: str
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserList(BaseModel):
    total: int
    page: int
    page_size: int
    users: list[UserOut]

    class Config:
        from_attributes = True


class PlayerSearchResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: Optional[str] = None
    phone: Optional[str] = None       # masked: last 4 digits only e.g. "****5978"
    username: Optional[str] = None
    profile_image: Optional[str] = None

