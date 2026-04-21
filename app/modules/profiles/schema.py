"""
Profile schemas.
"""

from pydantic import BaseModel, EmailStr, Field, model_validator, field_validator
from typing import Optional, List
from datetime import datetime, date


# ---------------------------------------------------------------------------
# Step 1: Update personal identity  (Profile page 1/2)
# ---------------------------------------------------------------------------

class UpdateProfileRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Full name (required)")
    gender: int = Field(..., ge=1, le=3, description="1=male, 2=female, 3=other (required)")
    country_id: Optional[int] = Field(None, description="Country ID from GET /locations/countries")
    city_id: Optional[int] = Field(None, description="City ID from GET /locations/cities?country_id=X")
    phone: Optional[str] = Field(
        None, min_length=8, max_length=20,
        description="Phone with country code e.g. +8801XXXXXXXXX. Only sets if account has no phone yet.",
    )
    email: Optional[EmailStr] = Field(
        None,
        description="Email address. Only sets if account has no email yet.",
    )
    profile_image: Optional[str] = Field(None, max_length=500, description="URL returned by POST /profiles/me/photo")
    bio: Optional[str] = Field(None, max_length=1000)
    date_of_birth: Optional[date] = None

    @field_validator("country_id", "city_id", mode="before")
    @classmethod
    def zero_to_none(cls, v):
        """Treat 0 as not provided — avoids FK violations."""
        if v == 0:
            return None
        return v

    @field_validator("phone", mode="before")
    @classmethod
    def empty_string_to_none(cls, v):
        """Treat empty string as not provided."""
        if v == "":
            return None
        return v


# ---------------------------------------------------------------------------
# Step 2: Update player skills  (Profile page 2/2)
# ---------------------------------------------------------------------------

class UpdateSkillsRequest(BaseModel):
    role: int = Field(..., ge=1, le=4, description="1=batsman, 2=bowler, 3=wicketkeeper batsman, 4=allrounder")
    batting_style: Optional[int] = Field(None, ge=1, le=2, description="1=left-hand, 2=right-hand")
    batting_order: Optional[int] = Field(None, ge=1, le=4, description="1=opening, 2=top, 3=middle, 4=lower")
    # Required for bowler (2) and allrounder (4)
    bowling_style: Optional[int] = Field(None, ge=1, le=2, description="1=left-arm, 2=right-arm")
    bowling_type: Optional[int] = Field(
        None, ge=1, le=7,
        description="1=fast, 2=fast medium, 3=medium, 4=off break, 5=leg break, 6=orthodox, 7=wrist spin",
    )

    @model_validator(mode="after")
    def validate_bowling_fields(self) -> "UpdateSkillsRequest":
        if self.role in (2, 4) and (self.bowling_style is None or self.bowling_type is None):
            raise ValueError("bowling_style and bowling_type are required for bowler and allrounder roles")
        return self


# ---------------------------------------------------------------------------
# Full combined profile response (GET /profiles/me)
# ---------------------------------------------------------------------------

class FullProfileOut(BaseModel):
    # User identity
    id: int
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    is_email_verified: bool
    is_phone_verified: bool
    is_profile_completed: bool
    status: str
    # Personal profile
    country_id: Optional[int] = None
    city_id: Optional[int] = None
    gender: Optional[int] = None        # 1=male, 2=female, 3=other
    date_of_birth: Optional[date] = None
    profile_image: Optional[str] = None
    bio: Optional[str] = None
    # Player skills
    roles: List[int] = Field(default_factory=list)  # e.g. [1] = batsman
    batting_style: Optional[int] = None             # 1=left-hand, 2=right-hand
    batting_order: Optional[int] = None             # 1=opening, 2=top, 3=middle, 4=lower
    bowling_style: Optional[int] = None             # 1=left-arm, 2=right-arm
    bowling_category: Optional[int] = None          # 1=pace, 2=spin (auto-derived)
    bowling_type: Optional[int] = None              # 1-7
    # Timestamps
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

