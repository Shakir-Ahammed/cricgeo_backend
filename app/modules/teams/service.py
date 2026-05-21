"""Team service — CRUD + Invitations & join flow."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, List

from fastapi import HTTPException, status
from sqlalchemy import select, func, case as sql_case
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.teams.model import Team, TeamMember, TeamInvitation, TeamJoinRequest
from app.modules.teams.schema import TeamCreate, TeamInviteCreate, TeamUpdate


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_ACTIVE = "active"
_CAPTAIN = "captain"


async def _get_team_or_404(db: AsyncSession, team_id: int) -> Team:
    """Fetch a non-deleted team or raise 404."""
    result = await db.execute(
        select(Team).where(Team.id == team_id, Team.deleted_at.is_(None))
    )
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    return team


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

async def create_team(db: AsyncSession, owner_id: int, data: TeamCreate) -> Team:
    """
    INSERT team + INSERT team_members captain row in a single transaction.
    The caller (get_db dependency) commits; we only flush to obtain the new team.id.
    """
    team = Team(
        owner_id=owner_id,
        name=data.name,
        short_name=data.short_name,
        logo=data.logo,
        type=data.type,
        country_id=data.country_id,
        city_id=data.city_id,
        description=data.description,
        status=_ACTIVE,
    )
    db.add(team)
    await db.flush()   # get team.id without committing

    member = TeamMember(
        team_id=team.id,
        user_id=owner_id,
        role=_CAPTAIN,
        status=_ACTIVE,
    )
    db.add(member)
    # Caller (get_db) commits — both rows land in the same transaction.
    return team


async def get_team(db: AsyncSession, team_id: int) -> Optional[Team]:
    """Return team by id if not soft-deleted, else None."""
    result = await db.execute(
        select(Team).where(Team.id == team_id, Team.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()


async def list_user_teams(
    db: AsyncSession, user_id: int, page: int = 1, per_page: int = 20
) -> dict:
    """
    All teams where user_id appears in team_members (any role, any status),
    provided the team itself is not soft-deleted.
    """
    base = (
        select(Team)
        .join(TeamMember, TeamMember.team_id == Team.id)
        .where(
            TeamMember.user_id == user_id,
            Team.deleted_at.is_(None),
        )
        .distinct()
    )

    total: int = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()

    offset = (page - 1) * per_page
    rows = (
        await db.execute(
            base.order_by(Team.created_at.desc()).offset(offset).limit(per_page)
        )
    ).scalars().all()

    return {"items": rows, "total": total, "page": page, "per_page": per_page}


async def list_nearby_teams(
    db: AsyncSession, city_id: int, page: int = 1, per_page: int = 20
) -> dict:
    """Teams in the given city that are active and not soft-deleted."""
    base = select(Team).where(
        Team.city_id == city_id,
        Team.deleted_at.is_(None),
        Team.status == _ACTIVE,
    )

    total: int = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()

    offset = (page - 1) * per_page
    rows = (
        await db.execute(
            base.order_by(Team.created_at.desc()).offset(offset).limit(per_page)
        )
    ).scalars().all()

    return {"items": rows, "total": total, "page": page, "per_page": per_page}


async def update_team(
    db: AsyncSession, team_id: int, owner_id: int, data: TeamUpdate
) -> Team:
    """Only the team owner may update. Raises 403 otherwise."""
    team = await _get_team_or_404(db, team_id)

    if team.owner_id != owner_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the team owner can update this team",
        )

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(team, field, value)

    db.add(team)
    return team


async def soft_delete_team(
    db: AsyncSession, team_id: int, owner_id: int
) -> bool:
    """
    Soft-delete a team (set deleted_at = now()).
    Only the owner may delete. Raises 403/404 as appropriate.
    """
    team = await _get_team_or_404(db, team_id)

    if team.owner_id != owner_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the team owner can delete this team",
        )

    team.deleted_at = func.now()
    db.add(team)
    return True


async def get_team_members(db: AsyncSession, team_id: int) -> List[TeamMember]:
    """
    All members of the team in a single query.
    No N+1 — returns all rows at once.
    """
    result = await db.execute(
        select(TeamMember)
        .where(TeamMember.team_id == team_id)
        .order_by(TeamMember.joined_at.asc())
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Invitation helpers
# ---------------------------------------------------------------------------

_PENDING = "pending"
_ACCEPTED = "accepted"
_INVITE_QR = "qr"
_INVITE_EXPIRY_DAYS = 7


async def _require_captain_or_owner(
    db: AsyncSession, team_id: int, user_id: int
) -> None:
    """Raise 403 unless user_id is team owner or has role 'captain' in team_members."""
    # Check owner
    team_row = await db.execute(
        select(Team.owner_id).where(Team.id == team_id, Team.deleted_at.is_(None))
    )
    owner_id = team_row.scalar_one_or_none()
    if owner_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    if owner_id == user_id:
        return

    # Check captain role
    captain_row = await db.execute(
        select(TeamMember.id).where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == user_id,
            TeamMember.role == _CAPTAIN,
            TeamMember.status == _ACTIVE,
        )
    )
    if captain_row.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the team captain or owner can perform this action",
        )


def _invitation_expiry() -> datetime:
    return datetime.now(tz=timezone.utc) + timedelta(days=_INVITE_EXPIRY_DAYS)


# ---------------------------------------------------------------------------
# Invitations & join
# ---------------------------------------------------------------------------

async def invite_member(
    db: AsyncSession,
    team_id: int,
    invited_by: int,
    data: TeamInviteCreate,
) -> TeamInvitation:
    """
    Create a team invitation.
    Caller must be captain or owner (enforced here — not just in controller).
    Token is cryptographically random (secrets.token_urlsafe).
    """
    await _require_captain_or_owner(db, team_id, invited_by)

    token = secrets.token_urlsafe(32)
    invitation = TeamInvitation(
        team_id=team_id,
        invited_by=invited_by,
        invitee_user_id=data.invitee_user_id,
        invitee_identifier=data.invitee_identifier,
        invitee_name=data.invitee_name,
        role=data.role,
        invite_method=data.invite_method,
        token=token,
        status=_PENDING,
        expires_at=_invitation_expiry(),
    )
    db.add(invitation)
    await db.flush()   # get invitation.id; caller's get_db commits
    return invitation


async def get_invitation_by_token(
    db: AsyncSession, token: str
) -> Optional[TeamInvitation]:
    """
    O(1) lookup via unique token index.
    Returns None if token not found, already used, or expired.
    """
    now = datetime.now(tz=timezone.utc)
    result = await db.execute(
        select(TeamInvitation).where(
            TeamInvitation.token == token,
            TeamInvitation.status == _PENDING,
            TeamInvitation.expires_at > now,
        )
    )
    return result.scalar_one_or_none()


async def accept_invitation(
    db: AsyncSession, token: str, user_id: int
) -> TeamMember:
    """
    Accept a direct (non-QR) pending invitation → auto-join as TeamMember.
    For QR-based joins, use request_join_via_qr() instead.
    """
    invitation = await get_invitation_by_token(db, token)
    if invitation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found or has expired",
        )

    # Check not already a member
    existing_member = await db.execute(
        select(TeamMember).where(
            TeamMember.team_id == invitation.team_id,
            TeamMember.user_id == user_id,
            TeamMember.status == _ACTIVE,
        )
    )
    if existing_member.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are already an active member of this team",
        )

    member = TeamMember(
        team_id=invitation.team_id,
        user_id=user_id,
        role=invitation.role,
        status=_ACTIVE,
    )
    db.add(member)

    invitation.status = _ACCEPTED
    invitation.responded_at = datetime.now(tz=timezone.utc)
    db.add(invitation)

    await db.flush()
    return member


async def request_join_via_qr(
    db: AsyncSession, invitation: TeamInvitation, user_id: int
) -> TeamJoinRequest:
    """
    For QR scans: create a pending TeamJoinRequest.
    The QR invitation stays 'pending' so others can still use it.
    Captain must approve before the user becomes a TeamMember.
    """
    # Check not already a member
    existing_member = await db.execute(
        select(TeamMember).where(
            TeamMember.team_id == invitation.team_id,
            TeamMember.user_id == user_id,
            TeamMember.status == _ACTIVE,
        )
    )
    if existing_member.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are already an active member of this team",
        )

    # Check no duplicate pending request
    existing_req = await db.execute(
        select(TeamJoinRequest).where(
            TeamJoinRequest.team_id == invitation.team_id,
            TeamJoinRequest.user_id == user_id,
            TeamJoinRequest.status == _PENDING,
        )
    )
    if existing_req.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have a pending join request for this team",
        )

    join_req = TeamJoinRequest(
        team_id=invitation.team_id,
        user_id=user_id,
        invitation_id=invitation.id,
        status=_PENDING,
    )
    db.add(join_req)
    await db.flush()
    return join_req


async def generate_qr_token(
    db: AsyncSession, team_id: int, owner_id: int
) -> dict:
    """
    Return an existing valid QR invitation or create a fresh one.
    Reuse avoids token churn — only one active QR code per team.
    Returns: {token, join_url, expires_at}
    """
    await _require_captain_or_owner(db, team_id, owner_id)

    now = datetime.now(tz=timezone.utc)

    # Try to reuse an existing pending QR invitation
    existing = await db.execute(
        select(TeamInvitation).where(
            TeamInvitation.team_id == team_id,
            TeamInvitation.invite_method == _INVITE_QR,
            TeamInvitation.status == _PENDING,
            TeamInvitation.expires_at > now,
        )
    )
    invitation = existing.scalar_one_or_none()

    if invitation is None:
        token = secrets.token_urlsafe(32)
        invitation = TeamInvitation(
            team_id=team_id,
            invited_by=owner_id,
            role="player",
            invite_method=_INVITE_QR,
            token=token,
            status=_PENDING,
            expires_at=_invitation_expiry(),
        )
        db.add(invitation)
        await db.flush()

    join_url = f"{settings.FRONTEND_URL.rstrip('/')}/teams/join/{invitation.token}"
    return {
        "token": invitation.token,
        "join_url": join_url,
        "expires_at": invitation.expires_at,
    }


# ---------------------------------------------------------------------------
# Invite preview  (public — no auth required)
# ---------------------------------------------------------------------------

async def get_invite_preview(db: AsyncSession, token: str) -> dict:
    """
    Return team info from an invitation token without joining.
    Used by mobile app to show team details when QR is scanned.
    """
    now = datetime.now(tz=timezone.utc)
    result = await db.execute(
        select(TeamInvitation).where(
            TeamInvitation.token == token,
            TeamInvitation.status == _PENDING,
            TeamInvitation.expires_at > now,
        )
    )
    invitation = result.scalar_one_or_none()
    if invitation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found or has expired",
        )

    team_result = await db.execute(
        select(Team).where(Team.id == invitation.team_id, Team.deleted_at.is_(None))
    )
    team = team_result.scalar_one_or_none()
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    return {
        "team_id": team.id,
        "team_name": team.name,
        "team_logo": team.logo,
        "team_short_name": team.short_name,
        "role": invitation.role,
        "invite_method": invitation.invite_method,
        "expires_at": invitation.expires_at,
    }


# ---------------------------------------------------------------------------
# Join-request approval flow
# ---------------------------------------------------------------------------

_APPROVED = "approved"
_REJECTED = "rejected"


async def get_join_requests(
    db: AsyncSession, team_id: int, captain_id: int,
    page: int = 1, per_page: int = 20
) -> dict:
    """List pending join requests for a team. Captain/owner only."""
    await _require_captain_or_owner(db, team_id, captain_id)

    base = select(TeamJoinRequest).where(
        TeamJoinRequest.team_id == team_id,
        TeamJoinRequest.status == _PENDING,
    )
    total: int = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()

    offset = (page - 1) * per_page
    rows = (
        await db.execute(
            base.order_by(TeamJoinRequest.created_at.desc()).offset(offset).limit(per_page)
        )
    ).scalars().all()

    return {"items": rows, "total": total, "page": page, "per_page": per_page}


async def approve_join_request(
    db: AsyncSession, team_id: int, request_id: int, approver_id: int
) -> TeamMember:
    """Captain approves a pending join request → creates TeamMember."""
    await _require_captain_or_owner(db, team_id, approver_id)

    req_result = await db.execute(
        select(TeamJoinRequest).where(
            TeamJoinRequest.id == request_id,
            TeamJoinRequest.team_id == team_id,
            TeamJoinRequest.status == _PENDING,
        )
    )
    join_req = req_result.scalar_one_or_none()
    if join_req is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Join request not found")

    # Determine role from the original invitation if available
    role = "player"
    if join_req.invitation_id:
        inv_result = await db.execute(
            select(TeamInvitation.role).where(TeamInvitation.id == join_req.invitation_id)
        )
        inv_role = inv_result.scalar_one_or_none()
        if inv_role:
            role = inv_role

    member = TeamMember(
        team_id=team_id,
        user_id=join_req.user_id,
        role=role,
        status=_ACTIVE,
    )
    db.add(member)

    join_req.status = _APPROVED
    join_req.responded_at = datetime.now(tz=timezone.utc)
    join_req.responded_by = approver_id
    db.add(join_req)

    await db.flush()
    return member


async def reject_join_request(
    db: AsyncSession, team_id: int, request_id: int, rejector_id: int
) -> TeamJoinRequest:
    """Captain rejects a pending join request."""
    await _require_captain_or_owner(db, team_id, rejector_id)

    req_result = await db.execute(
        select(TeamJoinRequest).where(
            TeamJoinRequest.id == request_id,
            TeamJoinRequest.team_id == team_id,
            TeamJoinRequest.status == _PENDING,
        )
    )
    join_req = req_result.scalar_one_or_none()
    if join_req is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Join request not found")

    join_req.status = _REJECTED
    join_req.responded_at = datetime.now(tz=timezone.utc)
    join_req.responded_by = rejector_id
    db.add(join_req)
    return join_req


# ---------------------------------------------------------------------------
# Opponent teams (6.1 — Opponent Team tab)
# ---------------------------------------------------------------------------

async def get_opponent_teams(
    db: AsyncSession, user_id: int, page: int = 1, per_page: int = 20
) -> dict:
    """
    Teams that have appeared as the opponent in any match
    where the current user was a registered match player.
    """
    from app.modules.matches.model import Match, MatchPlayer

    # Subquery: (match_id, user_team_id) for every match the user played in
    user_match_teams = (
        select(MatchPlayer.match_id, MatchPlayer.team_id.label("user_team_id"))
        .where(MatchPlayer.user_id == user_id)
        .subquery()
    )

    # Opponent team_id = the OTHER team in that match
    opponent_ids_sq = (
        select(
            sql_case(
                (Match.team_a_id == user_match_teams.c.user_team_id, Match.team_b_id),
                else_=Match.team_a_id,
            ).label("opp_id")
        )
        .join(user_match_teams, Match.id == user_match_teams.c.match_id)
        .where(Match.deleted_at.is_(None))
        .distinct()
        .subquery()
    )

    base = (
        select(Team)
        .where(
            Team.id.in_(select(opponent_ids_sq.c.opp_id)),
            Team.deleted_at.is_(None),
        )
    )

    total: int = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()

    offset = (page - 1) * per_page
    rows = (
        await db.execute(
            base.order_by(Team.created_at.desc()).offset(offset).limit(per_page)
        )
    ).scalars().all()

    return {"items": rows, "total": total, "page": page, "per_page": per_page}


# ---------------------------------------------------------------------------
# Direct add member (captain/owner adds any app user without invitation)
# ---------------------------------------------------------------------------

async def direct_add_member(
    db: AsyncSession,
    team_id: int,
    adder_id: int,
    user_id: Optional[int],
    identifier: Optional[str],
    role: str,
    jersey_number: Optional[int],
) -> TeamMember:
    """
    Captain / owner directly adds a registered user as a team member.

    Lookup priority:
      1. user_id  — from GET /users/search result
      2. identifier (phone or email) — from "Add Via Phone Number or Email" screen
    Raises 400 if neither is provided, 404 if user not found, 409 if already a member.
    """
    await _require_captain_or_owner(db, team_id, adder_id)

    if user_id is None and not identifier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either user_id or identifier (phone / email)",
        )

    from app.modules.users.model import User as UserModel
    from sqlalchemy import or_

    if user_id is not None:
        user_row = await db.execute(
            select(UserModel.id).where(
                UserModel.id == user_id,
                UserModel.status == "active",
                UserModel.deleted_at.is_(None),
            )
        )
        target_user_id: Optional[int] = user_row.scalar_one_or_none()
    else:
        user_row = await db.execute(
            select(UserModel.id).where(
                or_(UserModel.phone == identifier, UserModel.email == identifier),
                UserModel.status == "active",
                UserModel.deleted_at.is_(None),
            )
        )
        target_user_id = user_row.scalar_one_or_none()

    if target_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found or inactive",
        )

    # Check not already an active member
    existing = await db.execute(
        select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == target_user_id,
            TeamMember.status == _ACTIVE,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already an active member of this team",
        )

    member = TeamMember(
        team_id=team_id,
        user_id=target_user_id,
        role=role,
        jersey_number=jersey_number,
        status=_ACTIVE,
    )
    db.add(member)
    await db.flush()
    return member
