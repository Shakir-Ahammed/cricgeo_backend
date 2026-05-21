"""
Teams controller — HTTP layer only.

All business logic lives in service.py. This file:
  - Calls service functions
  - Serializes ORM objects to response dicts
  - Returns {"success": bool, "message": str, "data": any}
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.teams import service
from app.modules.teams.model import Team, TeamMember
from app.modules.teams.schema import (
    TeamCreate,
    TeamInviteCreate,
    TeamInvitationResponse,
    TeamInvitePreviewResponse,
    TeamJoinRequestResponse,
    TeamMemberResponse,
    TeamResponse,
    TeamUpdate,
    DirectAddMemberBody,
)


# ---------------------------------------------------------------------------
# Teams CRUD
# ---------------------------------------------------------------------------


async def create_team(
    db: AsyncSession,
    data: TeamCreate,
    current_user_id: int,
) -> Dict[str, Any]:
    team = await service.create_team(db, owner_id=current_user_id, data=data)
    return {
        "success": True,
        "message": "Team created successfully",
        "data": TeamResponse.model_validate(team).model_dump(),
    }


async def upload_team_logo(
    db: AsyncSession,
    team_id: int,
    current_user_id: int,
    contents: bytes,
    filename: str,
) -> Dict[str, Any]:
    """Upload team logo to R2 and save URL to teams.logo."""
    from app.core.storage import upload_team_logo as _upload
    public_url = _upload(contents, filename, team_id)
    team = await service.save_team_logo(db, team_id=team_id, requester_id=current_user_id, url=public_url)
    await db.commit()
    return {
        "success": True,
        "message": "Team logo uploaded successfully",
        "data": {"url": public_url, "team_id": team.id},
    }


async def get_my_teams(
    db: AsyncSession,
    current_user_id: int,
    page: int,
    per_page: int,
) -> Dict[str, Any]:
    result = await service.list_user_teams(db, user_id=current_user_id, page=page, per_page=per_page)
    return {
        "success": True,
        "message": "Teams retrieved successfully",
        "data": {
            "items": [TeamResponse.model_validate(t).model_dump() for t in result["items"]],
            "total": result["total"],
            "page": result["page"],
            "per_page": result["per_page"],
        },
    }


async def get_nearby_teams(
    db: AsyncSession,
    city_id: int,
    page: int,
    per_page: int,
) -> Dict[str, Any]:
    result = await service.list_nearby_teams(db, city_id=city_id, page=page, per_page=per_page)
    return {
        "success": True,
        "message": "Teams retrieved successfully",
        "data": {
            "items": [TeamResponse.model_validate(t).model_dump() for t in result["items"]],
            "total": result["total"],
            "page": result["page"],
            "per_page": result["per_page"],
        },
    }


async def get_team(db: AsyncSession, team_id: int) -> Dict[str, Any]:
    team = await service.get_team(db, team_id=team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    return {
        "success": True,
        "message": "Team retrieved successfully",
        "data": TeamResponse.model_validate(team).model_dump(),
    }


async def update_team(
    db: AsyncSession,
    team_id: int,
    data: TeamUpdate,
    current_user_id: int,
) -> Dict[str, Any]:
    team = await service.update_team(db, team_id=team_id, owner_id=current_user_id, data=data)
    return {
        "success": True,
        "message": "Team updated successfully",
        "data": TeamResponse.model_validate(team).model_dump(),
    }


async def delete_team(
    db: AsyncSession,
    team_id: int,
    current_user_id: int,
) -> Dict[str, Any]:
    await service.soft_delete_team(db, team_id=team_id, owner_id=current_user_id)
    return {
        "success": True,
        "message": "Team deleted successfully",
        "data": None,
    }


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------


async def get_team_members(
    db: AsyncSession,
    team_id: int,
) -> Dict[str, Any]:
    # Verify team exists and is not deleted
    team = await service.get_team(db, team_id=team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    members = await service.get_team_members(db, team_id=team_id)
    return {
        "success": True,
        "message": "Team members retrieved successfully",
        "data": [TeamMemberResponse.model_validate(m).model_dump() for m in members],
    }


async def remove_member(
    db: AsyncSession,
    team_id: int,
    target_user_id: int,
    current_user_id: int,
) -> Dict[str, Any]:
    """
    Release a member from the team.
    Rules enforced:
      - Caller must be team owner (only owner can remove members)
      - Team owner cannot be removed
    """
    # Fetch team to verify ownership and get owner_id
    team = await service.get_team(db, team_id=team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    if team.owner_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the team owner can remove members",
        )

    if target_user_id == team.owner_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The team owner cannot be removed from the team",
        )

    # Find the active member row
    result = await db.execute(
        select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == target_user_id,
            TeamMember.status == "active",
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found in this team",
        )

    member.status = "released"
    member.released_at = datetime.now(tz=timezone.utc)
    db.add(member)

    return {
        "success": True,
        "message": "Member released from team",
        "data": TeamMemberResponse.model_validate(member).model_dump(),
    }


# ---------------------------------------------------------------------------
# Invitations
# ---------------------------------------------------------------------------


async def invite_member(
    db: AsyncSession,
    team_id: int,
    data: TeamInviteCreate,
    current_user_id: int,
) -> Dict[str, Any]:
    invitation = await service.invite_member(
        db,
        team_id=team_id,
        invited_by=current_user_id,
        data=data,
    )
    return {
        "success": True,
        "message": "Invitation sent successfully",
        "data": TeamInvitationResponse.model_validate(invitation).model_dump(),
    }


async def add_member_direct(
    db: AsyncSession,
    team_id: int,
    data: DirectAddMemberBody,
    current_user_id: int,
) -> Dict[str, Any]:
    """
    Captain/owner directly adds a registered player to the team.
    No invitation or approval needed — the captain is adding them manually.
    """
    member = await service.direct_add_member(
        db,
        team_id=team_id,
        adder_id=current_user_id,
        user_id=data.user_id,
        identifier=data.identifier,
        role=data.role,
        jersey_number=data.jersey_number,
    )
    return {
        "success": True,
        "message": "Player added to the team successfully",
        "data": TeamMemberResponse.model_validate(member).model_dump(),
    }


async def join_via_token(
    db: AsyncSession,
    token: str,
    current_user_id: int,
) -> Dict[str, Any]:
    """
    Smart join dispatcher:
    - QR invite  → create pending TeamJoinRequest (captain must approve)
    - Direct invite → auto-join as TeamMember immediately
    """
    invitation = await service.get_invitation_by_token(db, token)
    if invitation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found or has expired",
        )

    if invitation.invite_method == "qr":
        join_req = await service.request_join_via_qr(db, invitation, current_user_id)
        return {
            "success": True,
            "message": "Join request submitted. Waiting for captain approval.",
            "data": TeamJoinRequestResponse.model_validate(join_req).model_dump(),
        }
    else:
        member = await service.accept_invitation(db, token=token, user_id=current_user_id)
        return {
            "success": True,
            "message": "You have joined the team successfully",
            "data": TeamMemberResponse.model_validate(member).model_dump(),
        }


async def get_invite_preview(
    db: AsyncSession,
    token: str,
) -> Dict[str, Any]:
    preview = await service.get_invite_preview(db, token)
    return {
        "success": True,
        "message": "Invitation preview",
        "data": preview,
    }


async def get_join_requests(
    db: AsyncSession,
    team_id: int,
    current_user_id: int,
    page: int,
    per_page: int,
) -> Dict[str, Any]:
    result = await service.get_join_requests(
        db, team_id=team_id, captain_id=current_user_id, page=page, per_page=per_page
    )
    return {
        "success": True,
        "message": "Join requests retrieved",
        "data": {
            "items": [TeamJoinRequestResponse.model_validate(r).model_dump() for r in result["items"]],
            "total": result["total"],
            "page": result["page"],
            "per_page": result["per_page"],
        },
    }


async def approve_join_request(
    db: AsyncSession,
    team_id: int,
    request_id: int,
    current_user_id: int,
) -> Dict[str, Any]:
    member = await service.approve_join_request(
        db, team_id=team_id, request_id=request_id, approver_id=current_user_id
    )
    return {
        "success": True,
        "message": "Join request approved. Player added to team.",
        "data": TeamMemberResponse.model_validate(member).model_dump(),
    }


async def reject_join_request(
    db: AsyncSession,
    team_id: int,
    request_id: int,
    current_user_id: int,
) -> Dict[str, Any]:
    from app.modules.teams.model import TeamJoinRequest
    join_req = await service.reject_join_request(
        db, team_id=team_id, request_id=request_id, rejector_id=current_user_id
    )
    return {
        "success": True,
        "message": "Join request rejected.",
        "data": TeamJoinRequestResponse.model_validate(join_req).model_dump(),
    }


async def get_opponent_teams(
    db: AsyncSession,
    current_user_id: int,
    page: int,
    per_page: int,
) -> Dict[str, Any]:
    result = await service.get_opponent_teams(
        db, user_id=current_user_id, page=page, per_page=per_page
    )
    return {
        "success": True,
        "message": "Opponent teams retrieved",
        "data": {
            "items": [TeamResponse.model_validate(t).model_dump() for t in result["items"]],
            "total": result["total"],
            "page": result["page"],
            "per_page": result["per_page"],
        },
    }


async def get_qr_token(
    db: AsyncSession,
    team_id: int,
    current_user_id: int,
) -> Dict[str, Any]:
    result = await service.generate_qr_token(db, team_id=team_id, owner_id=current_user_id)
    return {
        "success": True,
        "message": "QR token generated successfully",
        "data": result,
    }
