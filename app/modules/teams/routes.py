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

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.modules.teams import controller
from app.modules.teams.schema import (
    TeamCreate,
    TeamInviteCreate,
    TeamUpdate,
    DirectAddMemberBody,
    AddGuestPlayerBody,
    BatchAddPlayersBody,
)

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


@router.post(
    "",
    status_code=201,
    response_model=Dict[str, Any],
    summary="Create a new team",
    description="🔒 Auth required. Caller becomes the **owner** and is auto-added as **captain**.",
    responses={
        201: {"content": {"application/json": {"example": {
            "success": True, "message": "Team created",
            "data": {"id": 7, "name": "Dhaka Tigers", "city_id": 1, "owner_id": 12, "logo": None, "status": "active"}
        }}}},
        401: {"description": "Auth required"},
        422: {"description": "Validation error"}
    },
)
async def create_team(
    data: TeamCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Create a new team. Caller becomes the team owner and is auto-added as captain."""
    current_user_id = _require_user_id(request)
    return await controller.create_team(db, data=data, current_user_id=current_user_id)


@router.get(
    "/my",
    response_model=Dict[str, Any],
    summary="List teams I belong to (Your Teams tab)",
    description="🔒 Auth required. Includes teams where I am owner, captain, or active member.",
    responses={200: {"content": {"application/json": {"example": {
        "success": True, "message": "Teams retrieved",
        "data": {"total": 2, "page": 1, "per_page": 20, "items": [
            {"id": 7, "name": "Dhaka Tigers", "role": "captain", "members_count": 11, "logo": "https://cdn/.../t7.jpg"},
            {"id": 9, "name": "Sylhet Strikers", "role": "player", "members_count": 14, "logo": None}
        ]}
    }}}}, 401: {"description": "Auth required"}},
)
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


@router.get(
    "/opponent",
    response_model=Dict[str, Any],
    summary="Teams I have played against (Opponent Teams tab)",
    description="🔒 Auth required. Derived from completed match history.",
    responses={200: {"content": {"application/json": {"example": {
        "success": True, "message": "Opponent teams retrieved",
        "data": {"total": 1, "page": 1, "per_page": 20, "items": [
            {"id": 22, "name": "Chittagong Challengers", "matches_played": 3}
        ]}
    }}}}, 401: {"description": "Auth required"}},
)
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


@router.get(
    "/nearby",
    response_model=Dict[str, Any],
    summary="List active teams in a city",
    description="🌐 Public. Use with `city_id` from `GET /locations/cities`.",
    responses={200: {"content": {"application/json": {"example": {
        "success": True, "message": "Teams retrieved",
        "data": {"total": 1, "page": 1, "per_page": 20, "items": [
            {"id": 7, "name": "Dhaka Tigers", "city_id": 1, "members_count": 11}
        ]}
    }}}}},
)
async def nearby_teams(
    city_id: int = Query(..., description="City ID to search teams in"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List active teams in a given city (public)."""
    return await controller.get_nearby_teams(db, city_id=city_id, page=page, per_page=per_page)


@router.get(
    "/invite/preview/{token}",
    response_model=Dict[str, Any],
    summary="Public preview of a team invitation / QR token",
    description="🌐 Public. Mobile app shows this preview before the user taps **Join**.",
    responses={
        200: {"content": {"application/json": {"example": {
            "success": True, "message": "Invitation preview",
            "data": {"team": {"id": 7, "name": "Dhaka Tigers", "logo": None, "members_count": 11},
                     "kind": "qr", "expires_at": "2026-06-26T12:00:00Z"}
        }}}},
        404: {"description": "Token invalid / expired"}
    },
)
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
@router.post(
    "/join/{token}",
    response_model=Dict[str, Any],
    summary="Join a team via QR token or direct invite",
    description="""🔒 Auth required.

- **QR token** → creates a pending join request (captain must approve).
- **Direct invite** → auto-joins immediately as an active member.
""",
    responses={
        200: {"content": {"application/json": {"example": {
            "success": True, "message": "Join request created",
            "data": {"team_id": 7, "status": "pending", "request_id": 33}
        }}}},
        401: {"description": "Auth required"},
        404: {"description": "Token invalid / expired"},
        409: {"description": "Already a member or duplicate pending request"}
    },
)
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


@router.post(
    "/{team_id}/logo",
    response_model=Dict[str, Any],
    summary="Upload / replace team logo (JPEG/PNG/WebP, max 5MB)",
    description="🔒 Auth required. **Owner or captain only.** `multipart/form-data` field name `file`.",
    responses={
        200: {"content": {"application/json": {"example": {
            "success": True, "message": "Logo uploaded",
            "data": {"url": "https://cdn/cric/teams/t7-abcd.jpg"}
        }}}},
        401: {"description": "Auth required"},
        403: {"description": "Not owner or captain"},
        404: {"description": "Team not found"},
        413: {"description": "Image larger than 5 MB"},
        415: {"description": "Unsupported media type"}
    },
)
async def upload_team_logo(
    team_id: int,
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload or replace the team logo (JPEG / PNG / WebP, max 5 MB).
    Only the team owner or captain may upload.
    Saves to Cloudflare R2 and updates teams.logo in the database.
    """
    from fastapi import HTTPException, status as http_status
    _ALLOWED = {"image/jpeg", "image/png", "image/webp"}
    _MAX_BYTES = 5 * 1024 * 1024  # 5 MB

    current_user_id = _require_user_id(request)

    if file.content_type not in _ALLOWED:
        raise HTTPException(
            status_code=http_status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only JPEG, PNG, and WebP images are allowed",
        )
    contents = await file.read()
    if len(contents) > _MAX_BYTES:
        raise HTTPException(
            status_code=http_status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image must be 5 MB or smaller",
        )
    return await controller.upload_team_logo(
        db, team_id=team_id, current_user_id=current_user_id,
        contents=contents, filename=file.filename or "logo",
    )


@router.get(
    "/{team_id}",
    response_model=Dict[str, Any],
    summary="Get team by ID",
    description="🌐 Public. Returns 404 for unknown or soft-deleted teams.",
    responses={
        200: {"content": {"application/json": {"example": {
            "success": True, "message": "Team retrieved",
            "data": {"id": 7, "name": "Dhaka Tigers", "city_id": 1, "owner_id": 12, "logo": None,
                     "status": "active", "members_count": 11, "created_at": "2026-04-01T10:00:00Z"}
        }}}},
        404: {"description": "Team not found"}
    },
)
async def get_team(
    team_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a team by ID (public). Returns 404 if not found or soft-deleted."""
    return await controller.get_team(db, team_id=team_id)


@router.put(
    "/{team_id}",
    response_model=Dict[str, Any],
    summary="Update team details (owner only)",
    description="🔒 Auth required. Only the team **owner** may update.",
    responses={
        200: {"content": {"application/json": {"example": {
            "success": True, "message": "Team updated",
            "data": {"id": 7, "name": "Dhaka Tigers XI", "city_id": 1}
        }}}},
        401: {"description": "Auth required"}, 403: {"description": "Not the owner"},
        404: {"description": "Team not found"}
    },
)
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


@router.delete(
    "/{team_id}",
    response_model=Dict[str, Any],
    summary="Soft-delete a team (owner only)",
    description="🔒 Auth required. Sets `deleted_at`. Members are not removed but team becomes invisible.",
    responses={
        200: {"content": {"application/json": {"example": {"success": True, "message": "Team deleted", "data": None}}}},
        401: {"description": "Auth required"}, 403: {"description": "Not the owner"},
        404: {"description": "Team not found"}
    },
)
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


@router.get(
    "/{team_id}/members",
    response_model=Dict[str, Any],
    summary="List all team members (registered + guests)",
    description="""🌐 Public. Each item is enriched with `display_name`, `identifier`, `is_guest`, and either `user_id` (registered) or `guest_player_id` (guest).""",
    responses={200: {"content": {"application/json": {"example": {
        "success": True, "message": "Members retrieved",
        "data": [
            {"id": 100, "team_id": 7, "user_id": 12, "guest_player_id": None,
             "role": "captain", "jersey_number": 7, "status": "active",
             "display_name": "Rakib Hasan", "identifier": "01712345678", "is_guest": False,
             "joined_at": "2026-04-01T10:00:00Z", "released_at": None},
            {"id": 101, "team_id": 7, "user_id": None, "guest_player_id": 5,
             "role": "player", "jersey_number": 11, "status": "active",
             "display_name": "Karim Local", "identifier": "01911223344", "is_guest": True,
             "joined_at": "2026-05-10T09:00:00Z", "released_at": None}
        ]
    }}}}, 404: {"description": "Team not found"}},
)
async def get_team_members(
    team_id: int,
    db: AsyncSession = Depends(get_db),
):
    """List all members of a team (public)."""
    return await controller.get_team_members(db, team_id=team_id)


@router.post(
    "/{team_id}/members/invite",
    status_code=201,
    response_model=Dict[str, Any],
    summary="Send player invitation by phone/email",
    description="🔒 Auth required. **Owner or captain.** Generates a one-time invite link/token that the player can accept.",
    responses={
        201: {"content": {"application/json": {"example": {
            "success": True, "message": "Invitation sent",
            "data": {"invitation_id": 42, "token": "inv_abcd1234", "expires_at": "2026-06-03T12:00:00Z"}
        }}}},
        401: {"description": "Auth required"}, 403: {"description": "Not owner / captain"},
        404: {"description": "Team not found"}, 409: {"description": "Already a member or duplicate pending invite"}
    },
)
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


@router.post(
    "/{team_id}/members/add",
    status_code=201,
    response_model=Dict[str, Any],
    summary="Captain/owner directly adds a registered player",
    description="""🔒 Auth required. **Owner or captain.**

Provide **either**:
- `user_id` (from `GET /users/search`), or
- `identifier` (phone OR email) — must match an existing **registered** user (else use `POST /teams/{id}/guest-players` or `/members/batch-add`).

No invite step. Player becomes an active member immediately.
""",
    responses={
        201: {"content": {"application/json": {"example": {
            "success": True, "message": "Member added",
            "data": {"member": {"id": 102, "team_id": 7, "user_id": 45, "role": "player",
                                  "jersey_number": 9, "status": "active"}}
        }}}},
        401: {"description": "Auth required"}, 403: {"description": "Not owner / captain"},
        404: {"description": "Team or user not found"},
        409: {"description": "Already an active member"}
    },
)
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


@router.post(
    "/{team_id}/members/batch-add",
    status_code=201,
    response_model=Dict[str, Any],
    summary="⭐ Bulk-add players (Add New Players screen)",
    description="""🔒 Auth required. **Owner or captain.** Primary endpoint for the **Add New Players** form.

For each entry the server resolves automatically:
1. `identifier` (phone/email) matches a registered, active user → added as **registered** `TeamMember`.
2. No match → creates a `GuestPlayer` + `TeamMember` (requires `name`).
3. Errors on one row do **NOT** abort the batch — each row gets its own `status`.
""",
    responses={
        201: {
            "description": "Batch processed (may include per-row skipped/error)",
            "content": {"application/json": {"example": {
                "success": True, "message": "2 of 3 player(s) added",
                "data": {
                    "added": 2, "total": 3,
                    "results": [
                        {"identifier": "rakib@example.com", "name": None,
                         "type": "registered", "status": "added",
                         "member_id": 102, "user_id": 12, "guest_player_id": None, "message": None},
                        {"identifier": "01911223344", "name": "Karim",
                         "type": "guest", "status": "added",
                         "member_id": 103, "user_id": None, "guest_player_id": 5, "message": None},
                        {"identifier": None, "name": None,
                         "type": "guest", "status": "error",
                         "member_id": None, "user_id": None, "guest_player_id": None,
                         "message": "Player full name is required when no registered user matches"}
                    ]
                }
            }}}
        },
        401: {"description": "Auth required"}, 403: {"description": "Not owner / captain"},
        404: {"description": "Team not found"}
    },
)
async def batch_add_players(
    team_id: int,
    data: BatchAddPlayersBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Bulk add players from the "Add New Players" screen.

    Each entry is processed independently:
      - identifier matches a registered user  → added as registered member
      - else (name required)                  → created as a GuestPlayer + member

    Returns per-row results so the UI can mark each row as added / skipped / error.
    Captain or owner only.
    """
    current_user_id = _require_user_id(request)
    return await controller.batch_add_players(
        db, team_id=team_id, data=data, current_user_id=current_user_id
    )


@router.post(
    "/{team_id}/guest-players",
    status_code=201,
    response_model=Dict[str, Any],
    summary="Add a single guest / local player",
    description="""🔒 Auth required. **Owner or captain.**

For non-app players. **Strict** endpoint:
- If `identifier` matches a registered active user → returns **409**; switch to `/members/add` or `/members/batch-add`.
- For mixed lists, prefer **`/members/batch-add`** which auto-routes registered vs guest.
""",
    responses={
        201: {"content": {"application/json": {"example": {
            "success": True, "message": "Guest player added to the team",
            "data": {
                "guest_player": {"id": 5, "team_id": 7, "name": "Karim", "identifier": "01911223344",
                                  "created_by": 12, "linked_user_id": None, "linked_at": None,
                                  "status": "active", "created_at": "2026-05-27T10:00:00Z"},
                "member": {"id": 103, "team_id": 7, "user_id": None, "guest_player_id": 5,
                            "role": "player", "jersey_number": 11, "status": "active",
                            "display_name": "Karim", "identifier": "01911223344", "is_guest": True}
            }
        }}}},
        401: {"description": "Auth required"}, 403: {"description": "Not owner / captain"},
        404: {"description": "Team not found"},
        409: {"description": "Identifier matches a registered user — add them as registered instead"}
    },
)
async def add_guest_player(
    team_id: int,
    data: AddGuestPlayerBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Add a single guest / local player (non-app user) to the team roster.
    Captain or owner only.
    """
    current_user_id = _require_user_id(request)
    return await controller.add_guest_player(
        db, team_id=team_id, data=data, current_user_id=current_user_id
    )


@router.delete(
    "/{team_id}/members/{user_id}",
    response_model=Dict[str, Any],
    summary="Remove (release) a member from the team",
    description="🔒 Auth required. **Owner only.** Owner cannot remove themselves.",
    responses={
        200: {"content": {"application/json": {"example": {"success": True, "message": "Member released", "data": None}}}},
        401: {"description": "Auth required"}, 403: {"description": "Not owner / cannot remove self"},
        404: {"description": "Team or member not found"}
    },
)
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


@router.get(
    "/{team_id}/join-requests",
    response_model=Dict[str, Any],
    summary="List pending join requests (captain/owner)",
    description="🔒 Auth required. Requests created by users who scanned the QR.",
    responses={200: {"content": {"application/json": {"example": {
        "success": True, "message": "Join requests retrieved",
        "data": {"total": 1, "page": 1, "per_page": 20, "items": [
            {"id": 33, "team_id": 7, "user_id": 80, "user_name": "Karim Khan",
             "user_phone": "01911223344", "status": "pending", "created_at": "2026-05-26T08:00:00Z"}
        ]}
    }}}}, 401: {"description": "Auth required"}, 403: {"description": "Not owner / captain"}},
)
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


@router.post(
    "/{team_id}/join-requests/{request_id}/approve",
    response_model=Dict[str, Any],
    summary="Approve a pending join request",
    description="🔒 Auth required. Adds the user as an active team member.",
    responses={
        200: {"content": {"application/json": {"example": {
            "success": True, "message": "Join request approved",
            "data": {"member_id": 104, "team_id": 7, "user_id": 80}
        }}}},
        401: {"description": "Auth required"}, 403: {"description": "Not owner / captain"},
        404: {"description": "Request not found"}, 409: {"description": "Already processed"}
    },
)
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


@router.post(
    "/{team_id}/join-requests/{request_id}/reject",
    response_model=Dict[str, Any],
    summary="Reject a pending join request",
    description="🔒 Auth required.",
    responses={
        200: {"content": {"application/json": {"example": {"success": True, "message": "Join request rejected", "data": None}}}},
        401: {"description": "Auth required"}, 403: {"description": "Not owner / captain"},
        404: {"description": "Request not found"}, 409: {"description": "Already processed"}
    },
)
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


@router.get(
    "/{team_id}/qr",
    response_model=Dict[str, Any],
    summary="Get or create the team's QR invite token",
    description="🔒 Auth required. **Owner or captain.** Reuses an existing pending QR token to avoid token churn.",
    responses={
        200: {"content": {"application/json": {"example": {
            "success": True, "message": "QR token",
            "data": {"token": "qr_abc123", "expires_at": "2026-06-26T12:00:00Z",
                     "deep_link": "cricgeo://teams/join/qr_abc123"}
        }}}},
        401: {"description": "Auth required"}, 403: {"description": "Not owner / captain"},
        404: {"description": "Team not found"}
    },
)
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
