"""
Matches routes.

Auth requirements:
  POST   /matches                          — auth required
  GET    /matches/live                     — public
  GET    /matches/my                       — auth required
  GET    /matches/invite/{token}           — public (preview)
  POST   /matches/join/{token}             — auth required
  GET    /matches/{id}                     — public if visibility=public, else auth+member
  PUT    /matches/{id}                     — created_by only
  DELETE /matches/{id}                     — created_by only
  PUT    /matches/{id}/players             — created_by only
  POST   /matches/{id}/officials           — created_by only
  PUT    /matches/{id}/powerplays          — created_by only
  POST   /matches/{id}/invite              — created_by only
  POST   /matches/{id}/toss               — created_by or umpire
  POST   /matches/{id}/start              — created_by or umpire
  GET    /matches/{id}/live-state          — public

IMPORTANT: All static-path routes (/live, /my, /invite/{token}, /join/{token})
are registered BEFORE parameterised /{id} routes to prevent FastAPI shadowing.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.modules.matches import controller
from app.modules.matches.schema import (
    MatchCreate,
    MatchInviteCreate,
    MatchOfficialCreate,
    MatchPlayerInput,
    MatchUpdate,
    PowerplayInput,
)

router = APIRouter(prefix="/matches", tags=["Matches"])


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------


def _require_user_id(request: Request) -> int:
    """Extract authenticated user id or raise 401."""
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user["id"] if isinstance(user, dict) else user.id


def _optional_user_id(request: Request) -> Optional[int]:
    """Return user id if authenticated, else None (for optionally-auth endpoints)."""
    user = getattr(request.state, "user", None)
    if user is None:
        return None
    return user["id"] if isinstance(user, dict) else user.id


# ---------------------------------------------------------------------------
# Request body schemas (inline — small, matches-only)
# ---------------------------------------------------------------------------


class _TossBody(BaseModel):
    winner_team_id: int
    decision: str   # 'bat' or 'field'

    model_config = {"json_schema_extra": {"example": {"winner_team_id": 7, "decision": "bat"}}}


class _StartBody(BaseModel):
    striker_id: int
    non_striker_id: int
    current_bowler_id: int

    model_config = {"json_schema_extra": {"example": {"striker_id": 12, "non_striker_id": 45, "current_bowler_id": 80}}}


# ---------------------------------------------------------------------------
# Static-path routes — MUST come before /{id}
# ---------------------------------------------------------------------------


@router.get(
    "/live",
    response_model=Dict[str, Any],
    summary="List all public live matches",
    description="🌐 Public. Powers the home **Live Matches** feed.",
    responses={200: {"content": {"application/json": {"example": {
        "success": True, "message": "Live matches",
        "data": {"total": 1, "page": 1, "per_page": 20, "items": [
            {"id": 33, "team_a": "Dhaka Tigers", "team_b": "Sylhet Strikers",
             "venue": "Mirpur Ground", "overs": 20, "status": "in_progress",
             "current_score": "112/3 (14.2)"}
        ]}
    }}}}},
)
async def list_live_matches(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List all public live matches (no auth required)."""
    return await controller.get_live_matches(db, page=page, per_page=per_page)


@router.get(
    "/my",
    response_model=Dict[str, Any],
    summary="List matches I created or played in",
    description="🔒 Auth required.",
    responses={200: {"content": {"application/json": {"example": {
        "success": True, "message": "My matches",
        "data": {"total": 1, "page": 1, "per_page": 20, "items": [
            {"id": 33, "team_a": "Dhaka Tigers", "team_b": "Sylhet Strikers",
             "status": "upcoming", "start_time": "2026-06-01T14:00:00Z"}
        ]}
    }}}}, 401: {"description": "Auth required"}},
)
async def list_my_matches(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List matches where the authenticated user is creator or player."""
    user_id = _require_user_id(request)
    return await controller.get_my_matches(db, current_user_id=user_id, page=page, per_page=per_page)


@router.get(
    "/invite/{token}",
    response_model=Dict[str, Any],
    summary="Preview a match invitation",
    description="🌐 Public. Does NOT accept the invitation.",
    responses={200: {"content": {"application/json": {"example": {
        "success": True, "message": "Invitation preview",
        "data": {"match_id": 33, "team_a": "Dhaka Tigers", "team_b": "Sylhet Strikers",
                 "role": "player", "expires_at": "2026-06-03T12:00:00Z"}
    }}}}, 404: {"description": "Token invalid / expired"}},
)
async def preview_invitation(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Public preview of a match invitation — does not accept it."""
    return await controller.preview_invitation(db, token=token)


@router.post(
    "/join/{token}",
    response_model=Dict[str, Any],
    summary="Accept match invitation and register as player",
    description="🔒 Auth required.",
    responses={
        200: {"content": {"application/json": {"example": {
            "success": True, "message": "Joined match",
            "data": {"match_id": 33, "role": "player"}
        }}}},
        401: {"description": "Auth required"}, 404: {"description": "Token invalid"},
        409: {"description": "Already joined"}
    },
)
async def join_match(
    token: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Accept a match invitation and register as a player."""
    user_id = _require_user_id(request)
    return await controller.join_match(db, token=token, current_user_id=user_id)


# ---------------------------------------------------------------------------
# GET /matches/officials/search — find registered users for the "Add Umpire" UI
# ---------------------------------------------------------------------------


@router.get(
    "/officials/search",
    response_model=Dict[str, Any],
    summary="Search registered users to add as a match official",
    description="""🔒 Auth required.

Powers the **Add an Umpire / Scorer / Commentator** flow's *Find* button — the
captain types a mobile no. or email, and this endpoint returns matching registered
users (partial match on name / phone / email / username).

If nothing is returned, the UI should fall back to creating a **guest** official
via `POST /matches/{match_id}/officials` with `guest_name` + `guest_phone`.
""",
    responses={
        200: {"content": {"application/json": {"example": {
            "success": True, "message": "Officials search results",
            "data": {"total": 1, "items": [
                {"id": 99, "name": "Mr. Rahman", "email": "rahman@example.com",
                 "phone": "****5678", "username": "umpire_rahman",
                 "profile_image": None}
            ]}
        }}}},
        401: {"description": "Auth required"}
    },
)
async def search_officials_route(
    request: Request,
    q: str = Query(..., min_length=1, description="Phone, email, name, or username (partial OK)"),
    limit: int = Query(20, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    _require_user_id(request)
    return await controller.search_officials(db, q=q, limit=limit)


# ---------------------------------------------------------------------------
# POST /matches — create a new match
# ---------------------------------------------------------------------------


@router.post(
    "",
    status_code=201,
    response_model=Dict[str, Any],
    summary="Create a new match",
    description="🔒 Auth required. Caller becomes `created_by` and gains full edit rights.",
    responses={
        201: {"content": {"application/json": {"example": {
            "success": True, "message": "Match created",
            "data": {"id": 33, "team_a_id": 7, "team_b_id": 22, "venue_id": 4,
                     "overs": 20, "status": "upcoming", "visibility": "public",
                     "start_time": "2026-06-01T14:00:00Z"}
        }}}},
        401: {"description": "Auth required"}, 422: {"description": "Validation error"}
    },
)
async def create_match(
    data: MatchCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Create a new match."""
    user_id = _require_user_id(request)
    return await controller.create_match(db, data=data, current_user_id=user_id)


# ---------------------------------------------------------------------------
# Parameterised /{id} routes — AFTER static routes
# ---------------------------------------------------------------------------


@router.get(
    "/{match_id}",
    response_model=Dict[str, Any],
    summary="Get match details",
    description="🌐🔒 Public if `visibility='public'`; requires auth + membership for private matches.",
    responses={
        200: {"content": {"application/json": {"example": {
            "success": True, "message": "Match retrieved",
            "data": {"id": 33, "team_a": {"id": 7, "name": "Dhaka Tigers"},
                     "team_b": {"id": 22, "name": "Sylhet Strikers"},
                     "venue": "Sher-e-Bangla National Cricket Stadium",
                     "overs": 20, "status": "upcoming", "visibility": "public"}
        }}}},
        403: {"description": "Private match — not a member"},
        404: {"description": "Match not found"}
    },
)
async def get_match(
    match_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Get match details.
    Public if visibility='public'; requires auth + membership for private matches.
    """
    user_id = _optional_user_id(request)
    return await controller.get_match(db, match_id=match_id, current_user_id=user_id)


@router.put(
    "/{match_id}",
    response_model=Dict[str, Any],
    summary="Update match details (created_by only)",
    description="🔒 Auth required.",
    responses={
        200: {"content": {"application/json": {"example": {
            "success": True, "message": "Match updated",
            "data": {"id": 33, "overs": 25, "start_time": "2026-06-01T15:00:00Z"}
        }}}},
        401: {"description": "Auth required"}, 403: {"description": "Not the creator"},
        404: {"description": "Match not found"}
    },
)
async def update_match(
    match_id: int,
    data: MatchUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Update match details (created_by only)."""
    user_id = _require_user_id(request)
    return await controller.update_match(db, match_id=match_id, data=data, current_user_id=user_id)


@router.delete(
    "/{match_id}",
    response_model=Dict[str, Any],
    summary="Soft-delete a match (created_by only)",
    description="🔒 Auth required.",
    responses={
        200: {"content": {"application/json": {"example": {"success": True, "message": "Match deleted", "data": None}}}},
        401: {"description": "Auth required"}, 403: {"description": "Not the creator"}, 404: {"description": "Not found"}
    },
)
async def delete_match(
    match_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a match (created_by only)."""
    user_id = _require_user_id(request)
    return await controller.delete_match(db, match_id=match_id, current_user_id=user_id)


@router.put(
    "/{match_id}/players",
    response_model=Dict[str, Any],
    summary="Set / replace playing XI (created_by only)",
    description="🔒 Auth required. Submit the full list for both teams in one call.",
    responses={
        200: {"content": {"application/json": {"example": {
            "success": True, "message": "Playing XI set",
            "data": {"team_a_count": 11, "team_b_count": 11}
        }}}},
        401: {"description": "Auth required"}, 403: {"description": "Not the creator"},
        404: {"description": "Match not found"}, 422: {"description": "Invalid roster"}
    },
)
async def set_playing_xi(
    match_id: int,
    players: List[MatchPlayerInput],
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Set / replace the playing XI for both teams (created_by only)."""
    user_id = _require_user_id(request)
    return await controller.set_players(db, match_id=match_id, players=players, current_user_id=user_id)


@router.post(
    "/{match_id}/officials",
    status_code=201,
    response_model=Dict[str, Any],
    summary="Assign a match official (umpire / scorer)",
    description="🔒 Auth required. **Created_by only.**",
    responses={
        201: {"content": {"application/json": {"example": {
            "success": True, "message": "Official assigned",
            "data": {"id": 5, "match_id": 33, "user_id": 99, "role": "umpire"}
        }}}},
        401: {"description": "Auth required"}, 403: {"description": "Not the creator"}
    },
)
async def assign_official(
    match_id: int,
    data: MatchOfficialCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Add a match official (umpire, scorer, etc.) — created_by only."""
    user_id = _require_user_id(request)
    return await controller.add_official(db, match_id=match_id, data=data, current_user_id=user_id)


@router.get(
    "/{match_id}/officials",
    response_model=Dict[str, Any],
    summary="List all officials assigned to a match",
    description="""🌐🔒 Public if the match is public; otherwise the caller must be a match member.

Returns a flat list of officials across every role — group client-side by `role`
(`umpire`, `scorer`, `commentator`, `referee`, `live_streamer`) and `position`
(1st / 2nd / 3rd / 4th) to render the *Match Officials* screen.
""",
    responses={
        200: {"content": {"application/json": {"example": {
            "success": True, "message": "Match officials retrieved",
            "data": {"total": 3, "items": [
                {"id": 5, "match_id": 33, "user_id": 99,
                 "guest_name": None, "guest_phone": None,
                 "role": "umpire", "position": 1, "status": "invited",
                 "display_name": "Mr. Rahman", "phone": "****5678",
                 "profile_image": None, "is_guest": False},
                {"id": 6, "match_id": 33, "user_id": None,
                 "guest_name": "Karim Local", "guest_phone": "01911223344",
                 "role": "umpire", "position": 2, "status": "invited",
                 "display_name": "Karim Local", "phone": "****3344",
                 "profile_image": None, "is_guest": True},
                {"id": 7, "match_id": 33, "user_id": None,
                 "guest_name": "Sabbir Scorer", "guest_phone": None,
                 "role": "scorer", "position": 1, "status": "invited",
                 "display_name": "Sabbir Scorer", "phone": None,
                 "profile_image": None, "is_guest": True}
            ]}
        }}}},
        404: {"description": "Match not found"}
    },
)
async def list_match_officials_route(
    match_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await controller.list_officials(db, match_id=match_id)


@router.put(
    "/{match_id}/powerplays",
    response_model=Dict[str, Any],
    summary="Configure powerplay overs",
    description="🔒 Auth required. **Created_by only.** Pass the full powerplay list — replaces existing.",
    responses={
        200: {"content": {"application/json": {"example": {
            "success": True, "message": "Powerplays set",
            "data": {"count": 1}
        }}}},
        401: {"description": "Auth required"}, 403: {"description": "Not the creator"}
    },
)
async def configure_powerplays(
    match_id: int,
    pps: List[PowerplayInput],
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Configure powerplay overs for a match (created_by only)."""
    user_id = _require_user_id(request)
    return await controller.set_powerplays(db, match_id=match_id, pps=pps, current_user_id=user_id)


@router.post(
    "/{match_id}/invite",
    status_code=201,
    response_model=Dict[str, Any],
    summary="Create a match invitation link/token",
    description="🔒 Auth required. **Created_by only.**",
    responses={
        201: {"content": {"application/json": {"example": {
            "success": True, "message": "Invitation created",
            "data": {"token": "minv_abc123", "expires_at": "2026-06-03T12:00:00Z",
                     "deep_link": "cricgeo://matches/join/minv_abc123"}
        }}}},
        401: {"description": "Auth required"}, 403: {"description": "Not the creator"}
    },
)
async def create_invitation(
    match_id: int,
    data: MatchInviteCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Create a match invitation link/token (created_by only)."""
    user_id = _require_user_id(request)
    return await controller.invite_to_match(db, match_id=match_id, data=data, current_user_id=user_id)


@router.post(
    "/{match_id}/toss",
    response_model=Dict[str, Any],
    summary="Record toss result",
    description="🔒 Auth required. **Created_by or umpire.** `decision` is `\"bat\"` or `\"field\"`.",
    responses={
        200: {"content": {"application/json": {"example": {
            "success": True, "message": "Toss recorded",
            "data": {"match_id": 33, "toss_winner_team_id": 7, "decision": "bat"}
        }}}},
        401: {"description": "Auth required"}, 403: {"description": "Not creator/umpire"},
        409: {"description": "Toss already recorded"}
    },
)
async def record_toss(
    match_id: int,
    body: _TossBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Record toss result (created_by or umpire only)."""
    user_id = _require_user_id(request)
    return await controller.record_toss(
        db,
        match_id=match_id,
        winner_team_id=body.winner_team_id,
        decision=body.decision,
        current_user_id=user_id,
    )


@router.post(
    "/{match_id}/start",
    response_model=Dict[str, Any],
    summary="Start the match (creates innings + live state)",
    description="""🔒 Auth required. **Created_by or umpire.**

**Pre-requisites:** toss must be recorded first.

Body supplies the opening **striker**, **non-striker**, and the first **bowler** — all must be in the playing XI of the correct team.
""",
    responses={
        200: {"content": {"application/json": {"example": {
            "success": True, "message": "Match started",
            "data": {"match_id": 33, "innings_id": 1, "status": "in_progress"}
        }}}},
        401: {"description": "Auth required"}, 403: {"description": "Not creator/umpire"},
        409: {"description": "Toss not recorded / match already started"}
    },
)
async def start_match(
    match_id: int,
    body: _StartBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Start the match: creates innings + live state.
    Requires toss to have been recorded first.
    Body must supply the opening striker, non-striker, and first bowler.
    (created_by or umpire only)
    """
    user_id = _require_user_id(request)
    return await controller.start_match(
        db,
        match_id=match_id,
        striker_id=body.striker_id,
        non_striker_id=body.non_striker_id,
        current_bowler_id=body.current_bowler_id,
        current_user_id=user_id,
    )


@router.get(
    "/{match_id}/live-state",
    response_model=Dict[str, Any],
    summary="Get current live match state",
    description="🌐 Public. Cached in Redis (`match:live:{match_id}`), falls back to DB on miss.",
    responses={200: {"content": {"application/json": {"example": {
        "success": True, "message": "Live state",
        "data": {"match_id": 33, "innings": 1, "score": "112/3", "overs": "14.2",
                 "striker": {"id": 12, "name": "Rakib", "runs": 45, "balls": 32},
                 "non_striker": {"id": 45, "name": "Karim", "runs": 18, "balls": 20},
                 "bowler": {"id": 80, "name": "Sabbir", "overs": "3.2", "runs": 28, "wickets": 1},
                 "crr": 7.85, "required_rr": None}
    }}}}, 404: {"description": "Match not found / not started"}},
)
async def get_live_state(
    match_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get the current live state of a match.
    Checks Redis first (match:live:{match_id}), falls back to DB.
    Public — no auth required.
    """
    return await controller.get_live_state(db, match_id=match_id)
