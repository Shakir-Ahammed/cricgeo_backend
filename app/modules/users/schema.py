"""
User Pydantic schemas
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from app.modules.users.model import PlanType, UserType, UserStatus


class UserCreate(BaseModel):
    """
    Schema for creating a new user (admin operation)
    """
    name: str = Field(..., min_length=2, max_length=100, description="User's full name")
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=8, max_length=100, description="User's password")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Jane Smith",
                "email": "jane.smith@example.com",
                "password": "SecurePassword123"
            }
        }


class UserUpdate(BaseModel):
    """
    Schema for updating user profile
    All fields are optional
    """
    name: Optional[str] = Field(None, min_length=2, max_length=100, description="User's full name")
    email: Optional[EmailStr] = Field(None, description="User's email address")
    password: Optional[str] = Field(None, min_length=8, max_length=100, description="New password")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Jane Doe",
                "email": "jane.doe@example.com"
            }
        }


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    phone: Optional[str] = None
    plan: PlanType
    user_type: UserType
    is_email_verified: bool
    status: UserStatus
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class UserList(BaseModel):
    """
    Schema for paginated user list response
    """
    total: int = Field(..., description="Total number of users")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of items per page")
    users: list[UserOut] = Field(..., description="List of users")
    
    class Config:
        json_schema_extra = {
            "example": {
                "total": 100,
                "page": 1,
                "page_size": 20,
                "users": [
                    {
                        "id": 1,
                        "name": "Jane Doe",
                        "email": "jane.doe@example.com",
                        "created_at": "2025-01-01T00:00:00",
                        "updated_at": "2025-01-15T10:30:00"
                    }
                ]
            }
        }
