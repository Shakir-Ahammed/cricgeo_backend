"""
Auth Pydantic schemas
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from app.modules.users.schema import UserOut


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class AuthResponse(BaseModel):
    user: UserOut
    tokens: TokenResponse


class GoogleLoginResponse(BaseModel):
    authorization_url: str


class GoogleCallbackRequest(BaseModel):
    code: str


# OTP Authentication Schemas
class RequestOTPRequest(BaseModel):
    email: EmailStr


class RequestOTPResponse(BaseModel):
    message: str
    email: str


class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6, pattern=r'^\d{6}$')


class VerifyOTPResponse(BaseModel):
    access_token: str
    is_new_user: bool
    token_type: str = "bearer"
    expires_in: int


class CompleteProfileRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="User's full name")
    gender: str = Field(..., description="User's gender: male, female, or other")
    phone: str = Field(..., min_length=10, max_length=20, description="User's phone number")
    profile_image: Optional[str] = Field(None, max_length=500, description="URL to profile image (optional)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "John Doe",
                "gender": "male",
                "phone": "+1234567890",
                "profile_image": "https://example.com/images/profile.jpg"
            }
        }


class CompleteProfileResponse(BaseModel):
    message: str
    user: UserOut
