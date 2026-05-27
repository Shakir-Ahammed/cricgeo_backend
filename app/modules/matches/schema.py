"""
Pydantic v2 schemas for the matches module.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Input schemas
# ---------------------------------------------------------------------------

class MatchCreate(BaseModel):
    tournament_id: Optional[int] = None
    round_id: Optional[int] = None
    team_a_id: int
    team_b_id: int
    venue_id: Optional[int] = None
    venue_name: Optional[str] = Field(None, max_length=200)
    format: str = Field(..., max_length=30)         # 'T20', 'ODI', 'Test', 'T10', 'Custom'
    overs_per_innings: int
    overs_per_bowler: Optional[int] = None
    match_type: str = Field("friendly", max_length=30)   # 'friendly', 'tournament', 'practice'
    visibility: str = Field("public", max_length=20)     # 'public', 'private'
    scheduled_at: Optional[datetime] = None

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "team_a_id": 7, "team_b_id": 22, "venue_id": 4,
            "format": "T20", "overs_per_innings": 20, "overs_per_bowler": 4,
            "match_type": "friendly", "visibility": "public",
            "scheduled_at": "2026-06-01T14:00:00Z"
        }
    })


class MatchUpdate(BaseModel):
    venue_id: Optional[int] = None
    venue_name: Optional[str] = Field(None, max_length=200)
    format: Optional[str] = Field(None, max_length=30)
    overs_per_innings: Optional[int] = None
    overs_per_bowler: Optional[int] = None
    match_type: Optional[str] = Field(None, max_length=30)
    visibility: Optional[str] = Field(None, max_length=20)
    scheduled_at: Optional[datetime] = None

    model_config = ConfigDict(json_schema_extra={
        "example": {"overs_per_innings": 25, "scheduled_at": "2026-06-01T15:00:00Z"}
    })


class MatchPlayerInput(BaseModel):
    """Single player entry for set_playing_xi."""
    user_id: int
    team_id: int
    batting_order: Optional[int] = None
    is_playing_xi: bool = True
    is_captain: bool = False
    is_wicketkeeper: bool = False
    is_substitute: bool = False

    model_config = ConfigDict(json_schema_extra={
        "example": {"user_id": 12, "team_id": 7, "batting_order": 1,
                    "is_playing_xi": True, "is_captain": True, "is_wicketkeeper": False}
    })


class MatchOfficialCreate(BaseModel):
    """Body for POST /matches/{id}/officials."""
    user_id: Optional[int] = None                              # registered user
    guest_name: Optional[str] = Field(None, max_length=150)   # free-text guest
    guest_phone: Optional[str] = Field(None, max_length=20)
    role: str = Field(..., max_length=30)   # 'umpire', 'scorer', 'referee', 'live_streamer'
    position: Optional[int] = None          # 1 = on-field, 2 = TV, etc.

    model_config = ConfigDict(json_schema_extra={
        "example": {"guest_name": "Mr. Rahman", "guest_phone": "01712345678",
                    "role": "umpire", "position": 1}
    })


class PowerplayInput(BaseModel):
    """Single powerplay configuration entry."""
    pp_number: int
    from_over: int
    to_over: int
    fielding_restrictions: Optional[str] = None

    model_config = ConfigDict(json_schema_extra={
        "example": {"pp_number": 1, "from_over": 1, "to_over": 6,
                    "fielding_restrictions": "max 2 fielders outside circle"}
    })


class MatchInviteCreate(BaseModel):
    """Body for POST /matches/{id}/invite."""
    invitee_user_id: Optional[int] = None
    invitee_identifier: Optional[str] = Field(None, max_length=255)  # phone/email
    invite_method: str = Field(..., max_length=20)    # 'link', 'qr', 'phone', 'email'
    role: str = Field("viewer", max_length=20)        # 'viewer', 'player', 'scorer', 'umpire'

    model_config = ConfigDict(json_schema_extra={
        "example": {"invitee_identifier": "01911223344", "invite_method": "link", "role": "player"}
    })


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class MatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tournament_id: Optional[int] = None
    round_id: Optional[int] = None
    team_a_id: int
    team_b_id: int
    venue_id: Optional[int] = None
    venue_name: Optional[str] = None
    format: str
    overs_per_innings: int
    overs_per_bowler: Optional[int] = None
    match_type: str
    visibility: str
    toss_winner_team_id: Optional[int] = None
    toss_decision: Optional[str] = None
    status: str
    winner_team_id: Optional[int] = None
    result_type: Optional[str] = None
    result_margin: Optional[int] = None
    dls_applied: bool
    dls_target: Optional[int] = None
    man_of_the_match_id: Optional[int] = None
    created_by: int
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    created_at: datetime


class MatchPlayerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    match_id: int
    team_id: int
    user_id: int
    batting_order: Optional[int] = None
    is_playing_xi: bool
    is_captain: bool
    is_wicketkeeper: bool
    is_substitute: bool


class MatchOfficialResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    match_id: int
    user_id: Optional[int] = None
    guest_name: Optional[str] = None
    guest_phone: Optional[str] = None
    role: str
    position: Optional[int] = None
    status: str


class MatchPowerplayResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    match_id: int
    pp_number: int
    from_over: int
    to_over: int
    fielding_restrictions: Optional[str] = None


class MatchInvitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    match_id: int
    invited_by: int
    invitee_user_id: Optional[int] = None
    invitee_identifier: Optional[str] = None
    invite_method: str
    token: str
    role: str
    status: str
    expires_at: datetime
    responded_at: Optional[datetime] = None
    created_at: datetime


class MatchInningsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    match_id: int
    batting_team_id: int
    bowling_team_id: int
    innings_number: int
    total_runs: int
    wickets: int
    balls_bowled: int
    extras: int
    wide_balls: int
    no_balls: int
    byes: int
    leg_byes: int
    penalty_runs: int
    target_runs: Optional[int] = None
    status: str
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None


class MatchLiveStateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    match_id: int
    current_innings_id: int
    striker_id: int
    non_striker_id: int
    current_bowler_id: int
    current_over: int
    current_ball: int
    total_deliveries: int
    current_runs: int
    current_wickets: int
    current_balls_bowled: int
    last_ball_id: Optional[int] = None
    updated_at: datetime
