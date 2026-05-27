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

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "name": "Dhaka Tigers",
            "short_name": "DT",
            "type": "club",
            "country_id": 1,
            "city_id": 1,
            "description": "Local T20 club from Mirpur"
        }
    })

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

    model_config = ConfigDict(json_schema_extra={
        "example": {"name": "Dhaka Tigers XI", "short_name": "DTX"}
    })


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
    user_id: Optional[int] = None
    guest_player_id: Optional[int] = None
    role: str
    jersey_number: Optional[int] = None
    status: str
    joined_at: datetime
    released_at: Optional[datetime] = None
    # Enriched fields (filled by service layer when listing members)
    display_name: Optional[str] = None
    identifier: Optional[str] = None
    is_guest: bool = False


# ---------------------------------------------------------------------------
# Guest player schemas
# ---------------------------------------------------------------------------

class AddGuestPlayerBody(BaseModel):
    """Body for POST /teams/{id}/guest-players — add a single local player."""
    name: str = Field(..., min_length=1, max_length=150)
    identifier: Optional[str] = Field(None, max_length=255, description="phone or email — optional")
    role: str = Field("player", max_length=30)
    jersey_number: Optional[int] = Field(None, ge=0, le=999)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be blank")
        return v

    @field_validator("identifier")
    @classmethod
    def strip_identifier(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v else v

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "name": "Karim Local",
            "identifier": "01911223344",
            "role": "player",
            "jersey_number": 11
        }
    })


class GuestPlayerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    name: str
    identifier: Optional[str] = None
    created_by: int
    linked_user_id: Optional[int] = None
    linked_at: Optional[datetime] = None
    status: str
    created_at: datetime


class BatchAddPlayerEntry(BaseModel):
    """
    One row from the "Add New Players" UI.
    - identifier: phone OR email typed by the captain (optional for guests with name only)
    - name: required ONLY when no registered user matches the identifier
    """
    identifier: Optional[str] = Field(None, max_length=255)
    name: Optional[str] = Field(None, max_length=150)
    role: str = Field("player", max_length=30)
    jersey_number: Optional[int] = Field(None, ge=0, le=999)

    @field_validator("identifier", "name")
    @classmethod
    def strip_strings(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        return v or None


class BatchAddPlayersBody(BaseModel):
    """Body for POST /teams/{id}/members/batch-add — captain submits the whole list at once."""
    entries: List[BatchAddPlayerEntry] = Field(..., min_length=1, max_length=50)

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "entries": [
                {"identifier": "rakib@example.com"},
                {"identifier": "01911223344", "name": "Karim Local", "role": "player"},
                {"name": "Walk-in Player", "role": "player"}
            ]
        }
    })


class BatchAddPlayersResultItem(BaseModel):
    """Per-row result so the UI can show what happened to each entry."""
    identifier: Optional[str] = None
    name: Optional[str] = None
    type: str  # 'registered' | 'guest'
    status: str  # 'added' | 'skipped' | 'error'
    member_id: Optional[int] = None
    user_id: Optional[int] = None
    guest_player_id: Optional[int] = None
    message: Optional[str] = None


class TeamInviteCreate(BaseModel):
    """Body for POST /teams/{id}/members/invite"""
    invitee_user_id: Optional[int] = None          # registered user found via player search
    invitee_identifier: Optional[str] = Field(None, max_length=255)  # phone/email fallback
    invitee_name: Optional[str] = Field(None, max_length=150)
    role: str = Field("player", max_length=30)
    invite_method: str = Field("link", max_length=30)

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "invitee_identifier": "01911223344",
            "invitee_name": "Karim Khan",
            "role": "player",
            "invite_method": "link"
        }
    })


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

    model_config = ConfigDict(json_schema_extra={
        "examples": [
            {"user_id": 45, "role": "player", "jersey_number": 9},
            {"identifier": "rakib@example.com", "role": "player"}
        ]
    })


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
