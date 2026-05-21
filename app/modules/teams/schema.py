"""
Pydantic v2 schemas for the teams module.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Input schemas
# ---------------------------------------------------------------------------

class TeamCreate(BaseModel):
    name: str = Field(..., max_length=150)
    short_name: Optional[str] = Field(None, max_length=10)
    logo: Optional[str] = Field(None, max_length=500)
    type: Optional[str] = Field(None, max_length=30)   # 'club', 'school', 'corporate', …
    country_id: Optional[int] = None
    city_id: Optional[int] = None
    description: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be blank")
        return v

    @field_validator("short_name")
    @classmethod
    def short_name_upper(cls, v: Optional[str]) -> Optional[str]:
        return v.strip().upper() if v else v


class TeamUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=150)
    short_name: Optional[str] = Field(None, max_length=10)
    logo: Optional[str] = Field(None, max_length=500)
    type: Optional[str] = Field(None, max_length=30)
    country_id: Optional[int] = None
    city_id: Optional[int] = None
    description: Optional[str] = None
    status: Optional[str] = Field(None, max_length=20)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class TeamResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    name: str
    short_name: Optional[str] = None
    logo: Optional[str] = None
    type: Optional[str] = None
    country_id: Optional[int] = None
    city_id: Optional[int] = None
    description: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None


class TeamMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    user_id: int
    role: str
    jersey_number: Optional[int] = None
    status: str
    joined_at: datetime
    released_at: Optional[datetime] = None


class TeamInviteCreate(BaseModel):
    """Body for POST /teams/{id}/members/invite"""
    invitee_user_id: Optional[int] = None          # registered user found via player search
    invitee_identifier: Optional[str] = Field(None, max_length=255)  # phone/email fallback
    invitee_name: Optional[str] = Field(None, max_length=150)
    role: str = Field("player", max_length=30)
    invite_method: str = Field("link", max_length=30)


class DirectAddMemberBody(BaseModel):
    """
    Body for POST /teams/{id}/members/add — captain/owner adds a player directly.
    Provide exactly one of user_id or identifier (phone/email).
    """
    user_id: Optional[int] = None                        # from player search result
    identifier: Optional[str] = Field(None, max_length=255)  # phone or email
    role: str = Field("player", max_length=30)
    jersey_number: Optional[int] = Field(None, ge=0, le=999)

    @field_validator("identifier")
    @classmethod
    def strip_identifier(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v else v


class TeamInvitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    invited_by: int
    invitee_user_id: Optional[int] = None
    invitee_identifier: Optional[str] = None
    invitee_name: Optional[str] = None
    role: str
    invite_method: str
    token: str
    status: str
    expires_at: datetime
    responded_at: Optional[datetime] = None
    created_at: datetime


class TeamInvitePreviewResponse(BaseModel):
    """Returned by GET /teams/invite/preview/{token} — no join, just info."""
    model_config = ConfigDict(from_attributes=True)

    team_id: int
    team_name: str
    team_logo: Optional[str] = None
    team_short_name: Optional[str] = None
    role: str
    invite_method: str
    expires_at: datetime


class TeamJoinRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    user_id: int
    invitation_id: Optional[int] = None
    status: str
    message: Optional[str] = None
    created_at: datetime
    responded_at: Optional[datetime] = None
    responded_by: Optional[int] = None
