"""
Auth Pydantic schemas
"""

from pydantic import BaseModel, EmailStr, Field
from pydantic import model_validator
from typing import Optional
from datetime import datetime
from app.modules.users.schema import UserOut


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # Access token expiry in seconds


class AuthResponse(BaseModel):
    user: UserOut
    tokens: TokenResponse


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., description="Refresh token to exchange for new access token")


class RefreshTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class GoogleLoginResponse(BaseModel):
    authorization_url: str


class GoogleCallbackRequest(BaseModel):
    code: str


# OTP Authentication Schemas
class RequestOTPRequest(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, min_length=8, max_length=20)

    @model_validator(mode="after")
    def validate_identifier(self) -> "RequestOTPRequest":
        if not self.email and not self.phone:
            raise ValueError("Either email or phone is required")
        if self.email and self.phone:
            raise ValueError("Provide only one identifier: email or phone")
        return self


class RequestOTPResponse(BaseModel):
    message: str
    channel: str
    identifier: str


class VerifyOTPRequest(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, min_length=8, max_length=20)
    otp: str = Field(..., min_length=6, max_length=6, pattern=r'^\d{6}$')

    @model_validator(mode="after")
    def validate_identifier(self) -> "VerifyOTPRequest":
        if not self.email and not self.phone:
            raise ValueError("Either email or phone is required")
        if self.email and self.phone:
            raise ValueError("Provide only one identifier: email or phone")
        return self


class VerifyOTPResponse(BaseModel):
    access_token: str
    refresh_token: str
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
