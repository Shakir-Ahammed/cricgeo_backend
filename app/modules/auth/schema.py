"""
Auth Pydantic schemas
"""

from pydantic import BaseModel, EmailStr, Field, ConfigDict
from pydantic import model_validator
from typing import Optional
from datetime import datetime, date
from app.modules.users.schema import UserOut


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class AuthResponse(BaseModel):
    user: UserOut
    tokens: TokenResponse


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., description="Refresh token to exchange for new access token")

    model_config = ConfigDict(json_schema_extra={
        "example": {"refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}
    })


class RefreshTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


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

    model_config = ConfigDict(json_schema_extra={
        "examples": [
            {"phone": "01712345678"},
            {"email": "rakib@example.com"}
        ]
    })


class RequestOTPResponse(BaseModel):
    message: str
    channel: str
    identifier: str
    otp_type: str  # login or signup


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

    model_config = ConfigDict(json_schema_extra={
        "example": {"phone": "01712345678", "otp": "123456"}
    })


class VerifyOTPResponse(BaseModel):
    access_token: str
    refresh_token: str
    is_new_user: bool
    is_profile_completed: bool = False
    token_type: str = "bearer"
    expires_in: int


class CompleteProfileRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="User's full name")
    gender: Optional[int] = Field(None, ge=1, le=3, description="1=male, 2=female, 3=other")
    date_of_birth: Optional[date] = Field(None, description="Date of birth")
    country_id: Optional[int] = Field(None, description="Country ID")
    city_id: Optional[int] = Field(None, description="City ID")
    profile_image: Optional[str] = Field(None, max_length=500, description="URL to profile image")
    bio: Optional[str] = Field(None, max_length=1000, description="Short bio")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "name": "Rakib Hasan",
            "gender": 1,
            "date_of_birth": "1998-04-15",
            "country_id": 1,
            "city_id": 1,
            "bio": "Right-hand bat | Right-arm off-break"
        }
    })


class CompleteProfileResponse(BaseModel):
    message: str
    user: UserOut


class GoogleTokenRequest(BaseModel):
    id_token: str = Field(..., description="Google ID token obtained from the mobile Google Sign-In SDK")

    model_config = ConfigDict(json_schema_extra={
        "example": {"id_token": "eyJhbGciOiJSUzI1NiIsImtpZCI6Ij..."}
    })
