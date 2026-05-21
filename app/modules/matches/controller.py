"""
Matches controller — HTTP layer only.

All business logic lives in service.py. This file:
  - Calls service functions
  - Serializes ORM objects to response dicts
  - Returns {"success": bool, "message": str, "data": any}
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.matches import service
from app.modules.matches.model import MatchPlayer
from app.modules.matches.schema import (
    MatchCreate,
    MatchInviteCreate,
    MatchInningsResponse,
    MatchInvitationResponse,
    MatchLiveStateResponse,
    MatchOfficialResponse,
    MatchPlayerResponse,
    MatchPowerplayResponse,
    MatchResponse,
    MatchUpdate,
    PowerplayInput,
    MatchPlayerInput,
    MatchOfficialCreate,
)


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


async def create_match(
    db: AsyncSession,
    data: MatchCreate,
    current_user_id: int,
) -> Dict[str, Any]:
    match = await service.create_match(db, created_by=current_user_id, data=data)
    await db.commit()
    await db.refresh(match)
    return {
        "success": True,
        "message": "Match created successfully",
        "data": MatchResponse.model_validate(match).model_dump(),
    }


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


async def get_match(
    db: AsyncSession,
    match_id: int,
    current_user_id: Optional[int],
) -> Dict[str, Any]:
    match = await service.get_match(db, match_id)
    if match is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")

    # Private match: only created_by or a registered player/official can view
    if match.visibility != "public":
        if current_user_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This match is private",
            )
        if match.created_by != current_user_id:
            # Check player membership
            from sqlalchemy import select
            from app.modules.matches.model import MatchPlayer, MatchOfficial
            result = await db.execute(
                select(MatchPlayer.id).where(
                    MatchPlayer.match_id == match_id,
                    MatchPlayer.user_id == current_user_id,
                )
            )
            is_player = result.scalar_one_or_none() is not None
            if not is_player:
                result2 = await db.execute(
                    select(MatchOfficial.id).where(
                        MatchOfficial.match_id == match_id,
                        MatchOfficial.user_id == current_user_id,
                    )
                )
                is_official = result2.scalar_one_or_none() is not None
                if not is_official:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="This match is private",
                    )

    return {
        "success": True,
        "message": "Match retrieved",
        "data": MatchResponse.model_validate(match).model_dump(),
    }


async def get_live_matches(
    db: AsyncSession,
    page: int,
    per_page: int,
) -> Dict[str, Any]:
    result = await service.get_live_matches(db, page=page, per_page=per_page)
    result["items"] = [
        MatchResponse.model_validate(m).model_dump() for m in result["items"]
    ]
    return {"success": True, "message": "Live matches", "data": result}


async def get_my_matches(
    db: AsyncSession,
    current_user_id: int,
    page: int,
    per_page: int,
) -> Dict[str, Any]:
    result = await service.get_user_matches(db, user_id=current_user_id, page=page, per_page=per_page)
    result["items"] = [
        MatchResponse.model_validate(m).model_dump() for m in result["items"]
    ]
    return {"success": True, "message": "Your matches", "data": result}


# ---------------------------------------------------------------------------
# Update / Delete
# ---------------------------------------------------------------------------


async def update_match(
    db: AsyncSession,
    match_id: int,
    data: MatchUpdate,
    current_user_id: int,
) -> Dict[str, Any]:
    match = await service._get_match_or_404(db, match_id)
    await service._require_created_by(db, match_id, current_user_id)

    if match.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update a completed match",
        )

    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(match, field, value)

    db.add(match)
    await db.commit()
    await db.refresh(match)
    return {
        "success": True,
        "message": "Match updated",
        "data": MatchResponse.model_validate(match).model_dump(),
    }


async def delete_match(
    db: AsyncSession,
    match_id: int,
    current_user_id: int,
) -> Dict[str, Any]:
    match = await service._get_match_or_404(db, match_id)
    await service._require_created_by(db, match_id, current_user_id)

    from datetime import datetime, timezone
    match.deleted_at = datetime.now(tz=timezone.utc)
    db.add(match)
    await db.commit()
    return {"success": True, "message": "Match deleted", "data": None}


# ---------------------------------------------------------------------------
# Players / Officials / Powerplays
# ---------------------------------------------------------------------------


async def set_players(
    db: AsyncSession,
    match_id: int,
    players: List[MatchPlayerInput],
    current_user_id: int,
) -> Dict[str, Any]:
    rows = await service.set_playing_xi(db, match_id, current_user_id, players)
    await db.commit()
    return {
        "success": True,
        "message": "Playing XI updated",
        "data": [MatchPlayerResponse.model_validate(r).model_dump() for r in rows],
    }


async def add_official(
    db: AsyncSession,
    match_id: int,
    data: MatchOfficialCreate,
    current_user_id: int,
) -> Dict[str, Any]:
    official = await service.assign_official(db, match_id, current_user_id, data)
    await db.commit()
    await db.refresh(official)
    return {
        "success": True,
        "message": "Official assigned",
        "data": MatchOfficialResponse.model_validate(official).model_dump(),
    }


async def set_powerplays(
    db: AsyncSession,
    match_id: int,
    pps: List[PowerplayInput],
    current_user_id: int,
) -> Dict[str, Any]:
    rows = await service.configure_powerplays(db, match_id, current_user_id, pps)
    await db.commit()
    return {
        "success": True,
        "message": "Powerplays configured",
        "data": [MatchPowerplayResponse.model_validate(r).model_dump() for r in rows],
    }


# ---------------------------------------------------------------------------
# Invitations
# ---------------------------------------------------------------------------


async def invite_to_match(
    db: AsyncSession,
    match_id: int,
    data: MatchInviteCreate,
    current_user_id: int,
) -> Dict[str, Any]:
    invitation = await service.create_match_invitation(db, match_id, current_user_id, data)
    await db.commit()
    await db.refresh(invitation)
    return {
        "success": True,
        "message": "Invitation created",
        "data": MatchInvitationResponse.model_validate(invitation).model_dump(),
    }


async def preview_invitation(
    db: AsyncSession,
    token: str,
) -> Dict[str, Any]:
    preview = await service.get_invitation_preview(db, token)
    return {
        "success": True,
        "message": "Invitation preview",
        "data": preview,
    }


async def join_match(
    db: AsyncSession,
    token: str,
    current_user_id: int,
) -> Dict[str, Any]:
    """
    Accept a match invitation: set status='accepted', responded_at=now(),
    then add user as a MatchPlayer with the invited role.
    """
    from datetime import datetime, timezone
    from sqlalchemy import select
    from app.modules.matches.model import MatchInvitation, MatchPlayer

    now = datetime.now(tz=timezone.utc)

    # Fetch valid pending invitation
    result = await db.execute(
        select(MatchInvitation).where(
            MatchInvitation.token == token,
            MatchInvitation.status == "pending",
            MatchInvitation.expires_at > now,
        )
    )
    invitation = result.scalar_one_or_none()
    if invitation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found or has expired",
        )

    # Determine which team the user belongs to (must already be a team member)
    from app.modules.teams.model import TeamMember
    from sqlalchemy import select as sa_select
    match = await service._get_match_or_404(db, invitation.match_id)
    team_res = await db.execute(
        sa_select(TeamMember.team_id).where(
            TeamMember.user_id == current_user_id,
            TeamMember.team_id.in_([match.team_a_id, match.team_b_id]),
            TeamMember.status == "active",
        ).limit(1)
    )
    team_id = team_res.scalar_one_or_none()
    if team_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You must be an active member of one of the match teams to join",
        )

    # Upsert MatchPlayer
    existing = await db.execute(
        select(MatchPlayer).where(
            MatchPlayer.match_id == invitation.match_id,
            MatchPlayer.user_id == current_user_id,
        )
    )
    player = existing.scalar_one_or_none()
    if player is None:
        player = MatchPlayer(
            match_id=invitation.match_id,
            team_id=team_id,
            user_id=current_user_id,
            is_playing_xi=False,
        )
        db.add(player)

    # Mark invitation accepted
    invitation.status = "accepted"
    invitation.invitee_user_id = current_user_id
    invitation.responded_at = now
    db.add(invitation)

    await db.commit()
    return {
        "success": True,
        "message": "Joined match successfully",
        "data": {"match_id": invitation.match_id, "role": invitation.role},
    }


# ---------------------------------------------------------------------------
# Toss & Start
# ---------------------------------------------------------------------------


class _TossBody:
    pass  # defined inline in routes via Pydantic


async def record_toss(
    db: AsyncSession,
    match_id: int,
    winner_team_id: int,
    decision: str,
    current_user_id: int,
) -> Dict[str, Any]:
    match = await service.record_toss(db, match_id, current_user_id, winner_team_id, decision)
    await db.commit()
    await db.refresh(match)
    return {
        "success": True,
        "message": "Toss recorded",
        "data": MatchResponse.model_validate(match).model_dump(),
    }


async def start_match(
    db: AsyncSession,
    match_id: int,
    striker_id: int,
    non_striker_id: int,
    current_bowler_id: int,
    current_user_id: int,
) -> Dict[str, Any]:
    match, innings, live_state = await service.start_match(
        db,
        match_id=match_id,
        user_id=current_user_id,
        striker_id=striker_id,
        non_striker_id=non_striker_id,
        current_bowler_id=current_bowler_id,
    )
    await db.commit()
    await db.refresh(match)
    await db.refresh(innings)
    await db.refresh(live_state)
    return {
        "success": True,
        "message": "Match started",
        "data": {
            "match": MatchResponse.model_validate(match).model_dump(),
            "innings": MatchInningsResponse.model_validate(innings).model_dump(),
            "live_state": MatchLiveStateResponse.model_validate(live_state).model_dump(),
        },
    }


# ---------------------------------------------------------------------------
# Live state
# ---------------------------------------------------------------------------


async def get_live_state(
    db: AsyncSession,
    match_id: int,
) -> Dict[str, Any]:
    """
    Try Redis first (key: match:live:{match_id}), fall back to DB.
    Returns 404 if match is not live.
    """
    # Redis read — graceful degradation on unavailability
    cached: Optional[dict] = None
    try:
        from app.core.redis import get_redis
        redis = get_redis()
        raw = await redis.get(f"match:live:{match_id}")
        if raw:
            cached = json.loads(raw)
    except Exception:
        pass  # Redis unavailable — fall back silently

    if cached is not None:
        return {"success": True, "message": "Live state (cached)", "data": cached}

    # DB fallback
    from sqlalchemy import select
    from app.modules.matches.model import MatchLiveState

    result = await db.execute(
        select(MatchLiveState).where(MatchLiveState.match_id == match_id)
    )
    live_state = result.scalar_one_or_none()
    if live_state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No live state found for this match",
        )
    return {
        "success": True,
        "message": "Live state",
        "data": MatchLiveStateResponse.model_validate(live_state).model_dump(),
    }
