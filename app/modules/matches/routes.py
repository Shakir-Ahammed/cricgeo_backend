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


class _StartBody(BaseModel):
    striker_id: int
    non_striker_id: int
    current_bowler_id: int


# ---------------------------------------------------------------------------
# Static-path routes — MUST come before /{id}
# ---------------------------------------------------------------------------


@router.get("/live", response_model=Dict[str, Any])
async def list_live_matches(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List all public live matches (no auth required)."""
    return await controller.get_live_matches(db, page=page, per_page=per_page)


@router.get("/my", response_model=Dict[str, Any])
async def list_my_matches(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List matches where the authenticated user is creator or player."""
    user_id = _require_user_id(request)
    return await controller.get_my_matches(db, current_user_id=user_id, page=page, per_page=per_page)


@router.get("/invite/{token}", response_model=Dict[str, Any])
async def preview_invitation(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Public preview of a match invitation — does not accept it."""
    return await controller.preview_invitation(db, token=token)


@router.post("/join/{token}", response_model=Dict[str, Any])
async def join_match(
    token: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Accept a match invitation and register as a player."""
    user_id = _require_user_id(request)
    return await controller.join_match(db, token=token, current_user_id=user_id)


# ---------------------------------------------------------------------------
# POST /matches — create a new match
# ---------------------------------------------------------------------------


@router.post("", status_code=201, response_model=Dict[str, Any])
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


@router.get("/{match_id}", response_model=Dict[str, Any])
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


@router.put("/{match_id}", response_model=Dict[str, Any])
async def update_match(
    match_id: int,
    data: MatchUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Update match details (created_by only)."""
    user_id = _require_user_id(request)
    return await controller.update_match(db, match_id=match_id, data=data, current_user_id=user_id)


@router.delete("/{match_id}", response_model=Dict[str, Any])
async def delete_match(
    match_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a match (created_by only)."""
    user_id = _require_user_id(request)
    return await controller.delete_match(db, match_id=match_id, current_user_id=user_id)


@router.put("/{match_id}/players", response_model=Dict[str, Any])
async def set_playing_xi(
    match_id: int,
    players: List[MatchPlayerInput],
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Set / replace the playing XI for both teams (created_by only)."""
    user_id = _require_user_id(request)
    return await controller.set_players(db, match_id=match_id, players=players, current_user_id=user_id)


@router.post("/{match_id}/officials", status_code=201, response_model=Dict[str, Any])
async def assign_official(
    match_id: int,
    data: MatchOfficialCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Add a match official (umpire, scorer, etc.) — created_by only."""
    user_id = _require_user_id(request)
    return await controller.add_official(db, match_id=match_id, data=data, current_user_id=user_id)


@router.put("/{match_id}/powerplays", response_model=Dict[str, Any])
async def configure_powerplays(
    match_id: int,
    pps: List[PowerplayInput],
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Configure powerplay overs for a match (created_by only)."""
    user_id = _require_user_id(request)
    return await controller.set_powerplays(db, match_id=match_id, pps=pps, current_user_id=user_id)


@router.post("/{match_id}/invite", status_code=201, response_model=Dict[str, Any])
async def create_invitation(
    match_id: int,
    data: MatchInviteCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Create a match invitation link/token (created_by only)."""
    user_id = _require_user_id(request)
    return await controller.invite_to_match(db, match_id=match_id, data=data, current_user_id=user_id)


@router.post("/{match_id}/toss", response_model=Dict[str, Any])
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


@router.post("/{match_id}/start", response_model=Dict[str, Any])
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


@router.get("/{match_id}/live-state", response_model=Dict[str, Any])
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
