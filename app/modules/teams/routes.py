"""
Teams routes.

Auth requirements:
  POST   /teams                                     — auth required
  GET    /teams/my                                  — auth required
  GET    /teams/opponent                            — auth required
  GET    /teams/nearby?city_id=                     — public
  GET    /teams/invite/preview/{token}              — public
  POST   /teams/join/{token}                        — auth required (QR → pending; link → auto-join)
  GET    /teams/{id}                                — public (deleted → 404)
  PUT    /teams/{id}                                — owner only
  DELETE /teams/{id}                                — owner only
  GET    /teams/{id}/members                        — public
  POST   /teams/{id}/members/invite                 — owner / captain
  POST   /teams/{id}/members/add                    — owner / captain (direct add by user_id or phone/email)
  DELETE /teams/{id}/members/{user_id}              — owner only
  GET    /teams/{id}/join-requests                  — captain / owner
  POST   /teams/{id}/join-requests/{req_id}/approve — captain / owner
  POST   /teams/{id}/join-requests/{req_id}/reject  — captain / owner
  GET    /teams/{id}/qr                             — owner / captain

Static segments registered BEFORE parameterised /{id} to avoid FastAPI shadowing.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.modules.teams import controller
from app.modules.teams.schema import TeamCreate, TeamInviteCreate, TeamUpdate, DirectAddMemberBody

router = APIRouter(prefix="/teams", tags=["Teams"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_user_id(request: Request) -> int:
    """Extract user id from request state; raises 401 if not authenticated."""
    user = getattr(request.state, "user", None)
    if user is None:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user["id"] if isinstance(user, dict) else user.id


# ---------------------------------------------------------------------------
# Static-path routes — must come before /{id}
# ---------------------------------------------------------------------------


@router.post("", status_code=201, response_model=Dict[str, Any])
async def create_team(
    data: TeamCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Create a new team. Caller becomes the team owner and is auto-added as captain."""
    current_user_id = _require_user_id(request)
    return await controller.create_team(db, data=data, current_user_id=current_user_id)


@router.get("/my", response_model=Dict[str, Any])
async def my_teams(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List all teams the authenticated user is a member of (Your Teams tab)."""
    current_user_id = _require_user_id(request)
    return await controller.get_my_teams(
        db, current_user_id=current_user_id, page=page, per_page=per_page
    )


@router.get("/opponent", response_model=Dict[str, Any])
async def opponent_teams(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Teams that appeared as opponents in user's match history (Opponent Teams tab)."""
    current_user_id = _require_user_id(request)
    return await controller.get_opponent_teams(
        db, current_user_id=current_user_id, page=page, per_page=per_page
    )


@router.get("/nearby", response_model=Dict[str, Any])
async def nearby_teams(
    city_id: int = Query(..., description="City ID to search teams in"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List active teams in a given city (public)."""
    return await controller.get_nearby_teams(db, city_id=city_id, page=page, per_page=per_page)


@router.get("/invite/preview/{token}", response_model=Dict[str, Any])
async def invite_preview(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Public endpoint. Returns team info for a QR token so mobile app
    can show a preview before the user confirms they want to join.
    """
    return await controller.get_invite_preview(db, token=token)


# POST /teams/join/{token} — must be before /{id} to avoid shadowing
@router.post("/join/{token}", response_model=Dict[str, Any])
async def join_team(
    token: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Join via token.
    - QR token  → creates pending join request (captain approval required)
    - Direct invite → auto-joins immediately
    """
    current_user_id = _require_user_id(request)
    return await controller.join_via_token(db, token=token, current_user_id=current_user_id)


# ---------------------------------------------------------------------------
# Parameterised team routes  /{id}
# ---------------------------------------------------------------------------


@router.get("/{team_id}", response_model=Dict[str, Any])
async def get_team(
    team_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a team by ID (public). Returns 404 if not found or soft-deleted."""
    return await controller.get_team(db, team_id=team_id)


@router.put("/{team_id}", response_model=Dict[str, Any])
async def update_team(
    team_id: int,
    data: TeamUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Update a team. Only the team owner may update."""
    current_user_id = _require_user_id(request)
    return await controller.update_team(
        db, team_id=team_id, data=data, current_user_id=current_user_id
    )


@router.delete("/{team_id}", response_model=Dict[str, Any])
async def delete_team(
    team_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a team. Only the team owner may delete."""
    current_user_id = _require_user_id(request)
    return await controller.delete_team(db, team_id=team_id, current_user_id=current_user_id)


# ---------------------------------------------------------------------------
# Member sub-routes  /{id}/members
# ---------------------------------------------------------------------------


@router.get("/{team_id}/members", response_model=Dict[str, Any])
async def get_team_members(
    team_id: int,
    db: AsyncSession = Depends(get_db),
):
    """List all members of a team (public)."""
    return await controller.get_team_members(db, team_id=team_id)


@router.post("/{team_id}/members/invite", status_code=201, response_model=Dict[str, Any])
async def invite_member(
    team_id: int,
    data: TeamInviteCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Invite a player to the team. Caller must be team owner or captain."""
    current_user_id = _require_user_id(request)
    return await controller.invite_member(
        db, team_id=team_id, data=data, current_user_id=current_user_id
    )


@router.post("/{team_id}/members/add", status_code=201, response_model=Dict[str, Any])
async def add_member_direct(
    team_id: int,
    data: DirectAddMemberBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Captain / owner directly adds a registered player to the team.
    Pass either user_id (from player search) or identifier (phone / email).
    No invitation or approval step — player is added immediately.
    """
    current_user_id = _require_user_id(request)
    return await controller.add_member_direct(
        db, team_id=team_id, data=data, current_user_id=current_user_id
    )


@router.delete("/{team_id}/members/{user_id}", response_model=Dict[str, Any])
async def remove_member(
    team_id: int,
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Release a member from the team. Only team owner can remove. Owner cannot remove themselves."""
    current_user_id = _require_user_id(request)
    return await controller.remove_member(
        db,
        team_id=team_id,
        target_user_id=user_id,
        current_user_id=current_user_id,
    )


# ---------------------------------------------------------------------------
# Join-request sub-routes  /{id}/join-requests
# ---------------------------------------------------------------------------


@router.get("/{team_id}/join-requests", response_model=Dict[str, Any])
async def get_join_requests(
    team_id: int,
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List pending join requests for a team. Captain / owner only."""
    current_user_id = _require_user_id(request)
    return await controller.get_join_requests(
        db, team_id=team_id, current_user_id=current_user_id, page=page, per_page=per_page
    )


@router.post("/{team_id}/join-requests/{request_id}/approve", response_model=Dict[str, Any])
async def approve_join_request(
    team_id: int,
    request_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Approve a pending join request. Adds the user as a team member."""
    current_user_id = _require_user_id(request)
    return await controller.approve_join_request(
        db, team_id=team_id, request_id=request_id, current_user_id=current_user_id
    )


@router.post("/{team_id}/join-requests/{request_id}/reject", response_model=Dict[str, Any])
async def reject_join_request(
    team_id: int,
    request_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Reject a pending join request."""
    current_user_id = _require_user_id(request)
    return await controller.reject_join_request(
        db, team_id=team_id, request_id=request_id, current_user_id=current_user_id
    )


# ---------------------------------------------------------------------------
# QR code route  /{id}/qr
# ---------------------------------------------------------------------------


@router.get("/{team_id}/qr", response_model=Dict[str, Any])
async def get_qr_token(
    team_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Get or create a QR invitation token for the team.
    Reuses an existing pending QR token if one exists (avoids token churn).
    Caller must be team owner or captain (enforced in service).
    """
    current_user_id = _require_user_id(request)
    return await controller.get_qr_token(db, team_id=team_id, current_user_id=current_user_id)
