"""Match service — creation & setup (P4-2)."""

from __future__ import annotations

import secrets
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.matches.model import (
    Match,
    MatchInnings,
    MatchInvitation,
    MatchLiveState,
    MatchOfficial,
    MatchPlayer,
    MatchPowerplay,
)
from app.modules.matches.schema import (
    MatchCreate,
    MatchInviteCreate,
    MatchOfficialCreate,
    MatchPlayerInput,
    PowerplayInput,
)


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

_SCHEDULED = "scheduled"
_TOSS_DONE = "toss_done"
_PENDING = "pending"
_INVITE_EXPIRY_HOURS = 24


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _get_match_or_404(db: AsyncSession, match_id: int) -> Match:
    """Fetch a non-deleted match or raise 404."""
    result = await db.execute(
        select(Match).where(Match.id == match_id, Match.deleted_at.is_(None))
    )
    match = result.scalar_one_or_none()
    if match is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found",
        )
    return match


async def _require_created_by(
    db: AsyncSession, match_id: int, user_id: int
) -> Match:
    """
    Fetch match and assert the caller is its creator.
    Raises 404 if not found, 403 if caller is not the creator.
    """
    match = await _get_match_or_404(db, match_id)
    if match.created_by != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the match creator can perform this action",
        )
    return match


def _invitation_expiry() -> datetime:
    return datetime.now(tz=timezone.utc) + timedelta(hours=_INVITE_EXPIRY_HOURS)


# ---------------------------------------------------------------------------
# create_match
# ---------------------------------------------------------------------------

async def create_match(
    db: AsyncSession,
    created_by: int,
    data: MatchCreate,
) -> Match:
    """
    INSERT a new match.
    Raises 400 if team_a_id == team_b_id.
    """
    if data.team_a_id == data.team_b_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="team_a_id and team_b_id must be different teams",
        )

    match = Match(
        tournament_id=data.tournament_id,
        round_id=data.round_id,
        team_a_id=data.team_a_id,
        team_b_id=data.team_b_id,
        venue_id=data.venue_id,
        venue_name=data.venue_name,
        format=data.format,
        overs_per_innings=data.overs_per_innings,
        overs_per_bowler=data.overs_per_bowler,
        match_type=data.match_type,
        visibility=data.visibility,
        status=_SCHEDULED,
        created_by=created_by,
        scheduled_at=data.scheduled_at,
    )
    db.add(match)
    return match


# ---------------------------------------------------------------------------
# set_playing_xi
# ---------------------------------------------------------------------------

async def set_playing_xi(
    db: AsyncSession,
    match_id: int,
    user_id: int,
    players: List[MatchPlayerInput],
) -> List[MatchPlayer]:
    """
    Replace all MatchPlayer rows for a match (upsert via delete + re-insert).

    Validates per team:
      - At most 11 players with is_playing_xi=True.
      - Exactly 1 captain (is_captain=True) among the playing XI.

    Only the match creator can call this. Match status must be 'scheduled' or 'toss_done'.
    """
    match = await _require_created_by(db, match_id, user_id)

    if match.status not in (_SCHEDULED, _TOSS_DONE):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Playing XI can only be set when match status is "
                f"'{_SCHEDULED}' or '{_TOSS_DONE}'; current status is '{match.status}'"
            ),
        )

    # --- Per-team validation ---
    xi_count: Dict[int, int] = defaultdict(int)
    captain_count: Dict[int, int] = defaultdict(int)

    for p in players:
        if p.is_playing_xi:
            xi_count[p.team_id] += 1
        if p.is_captain and p.is_playing_xi:
            captain_count[p.team_id] += 1

    # Validate BOTH match teams — catches teams with 0 xi entries as well
    for team_id in (match.team_a_id, match.team_b_id):
        count = xi_count.get(team_id, 0)
        if count != 11:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Team {team_id} must have exactly 11 playing XI players (found {count})",
            )
        caps = captain_count.get(team_id, 0)
        if caps != 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Team {team_id} must have exactly 1 captain in the playing XI "
                    f"(found {caps})"
                ),
            )

    # --- Upsert: delete all existing rows, then re-insert ---
    await db.execute(delete(MatchPlayer).where(MatchPlayer.match_id == match_id))

    new_players: List[MatchPlayer] = []
    for p in players:
        mp = MatchPlayer(
            match_id=match_id,
            team_id=p.team_id,
            user_id=p.user_id,
            batting_order=p.batting_order,
            is_playing_xi=p.is_playing_xi,
            is_captain=p.is_captain,
            is_wicketkeeper=p.is_wicketkeeper,
            is_substitute=p.is_substitute,
        )
        db.add(mp)
        new_players.append(mp)

    await db.flush()
    return new_players


# ---------------------------------------------------------------------------
# assign_official
# ---------------------------------------------------------------------------

async def assign_official(
    db: AsyncSession,
    match_id: int,
    user_id: int,
    data: MatchOfficialCreate,
) -> MatchOfficial:
    """
    Add an official to a match.
    Either data.user_id OR data.guest_name must be provided (not both null).
    Only the match creator can call this.
    """
    await _require_created_by(db, match_id, user_id)

    if data.user_id is None and not data.guest_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either user_id or guest_name must be provided for an official",
        )

    official = MatchOfficial(
        match_id=match_id,
        user_id=data.user_id,
        guest_name=data.guest_name,
        guest_phone=data.guest_phone,
        role=data.role,
        position=data.position,
        status="invited",
    )
    db.add(official)
    await db.flush()
    return official


# ---------------------------------------------------------------------------
# configure_powerplays
# ---------------------------------------------------------------------------

async def configure_powerplays(
    db: AsyncSession,
    match_id: int,
    user_id: int,
    pps: List[PowerplayInput],
) -> List[MatchPowerplay]:
    """
    Replace all powerplay configurations for a match (upsert via delete + re-insert).
    Validates from_over < to_over for every powerplay.
    Only the match creator can call this.
    """
    await _require_created_by(db, match_id, user_id)

    for pp in pps:
        if pp.from_over >= pp.to_over:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Powerplay {pp.pp_number}: from_over ({pp.from_over}) "
                    f"must be less than to_over ({pp.to_over})"
                ),
            )

    await db.execute(delete(MatchPowerplay).where(MatchPowerplay.match_id == match_id))

    new_pps: List[MatchPowerplay] = []
    for pp in pps:
        obj = MatchPowerplay(
            match_id=match_id,
            pp_number=pp.pp_number,
            from_over=pp.from_over,
            to_over=pp.to_over,
            fielding_restrictions=pp.fielding_restrictions,
        )
        db.add(obj)
        new_pps.append(obj)

    await db.flush()
    return new_pps


# ---------------------------------------------------------------------------
# create_match_invitation
# ---------------------------------------------------------------------------

async def create_match_invitation(
    db: AsyncSession,
    match_id: int,
    invited_by: int,
    data: MatchInviteCreate,
) -> MatchInvitation:
    """
    Generate a secure token and INSERT a match invitation.
    Token expires in 24 hours. Only the match creator can invite.
    """
    await _require_created_by(db, match_id, invited_by)

    token = secrets.token_urlsafe(32)
    invitation = MatchInvitation(
        match_id=match_id,
        invited_by=invited_by,
        invitee_user_id=data.invitee_user_id,
        invitee_identifier=data.invitee_identifier,
        invite_method=data.invite_method,
        token=token,
        role=data.role,
        status=_PENDING,
        expires_at=_invitation_expiry(),
    )
    db.add(invitation)
    await db.flush()
    return invitation


# ---------------------------------------------------------------------------
# get_invitation_preview
# ---------------------------------------------------------------------------

async def get_invitation_preview(db: AsyncSession, token: str) -> dict:
    """
    Return match details + role for a pending, non-expired invitation token.
    Does NOT accept or mutate the invitation.
    Raises 404 if token is unknown, expired, or already accepted/declined.
    """
    now = datetime.now(tz=timezone.utc)
    result = await db.execute(
        select(MatchInvitation).where(
            MatchInvitation.token == token,
            MatchInvitation.status == _PENDING,
            MatchInvitation.expires_at > now,
        )
    )
    invitation = result.scalar_one_or_none()
    if invitation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found or has expired",
        )

    match = await _get_match_or_404(db, invitation.match_id)

    return {
        "invitation_id": invitation.id,
        "match_id": match.id,
        "match_status": match.status,
        "format": match.format,
        "overs_per_innings": match.overs_per_innings,
        "match_type": match.match_type,
        "team_a_id": match.team_a_id,
        "team_b_id": match.team_b_id,
        "venue_name": match.venue_name,
        "scheduled_at": match.scheduled_at,
        "role": invitation.role,
        "invite_method": invitation.invite_method,
        "expires_at": invitation.expires_at,
    }


# ---------------------------------------------------------------------------
# Permission helper — created_by OR umpire
# ---------------------------------------------------------------------------

async def _is_umpire(db: AsyncSession, match_id: int, user_id: int) -> bool:
    """Return True if user has role='umpire' in match_officials for this match."""
    result = await db.execute(
        select(MatchOfficial.id).where(
            MatchOfficial.match_id == match_id,
            MatchOfficial.user_id == user_id,
            MatchOfficial.role == "umpire",
        )
    )
    return result.scalar_one_or_none() is not None


async def _require_created_by_or_umpire(
    db: AsyncSession, match: Match, user_id: int
) -> None:
    """Raise 403 unless user is the match creator or a registered umpire."""
    if match.created_by == user_id:
        return
    if await _is_umpire(db, match.id, user_id):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Only the match creator or an umpire can perform this action",
    )


# ---------------------------------------------------------------------------
# record_toss
# ---------------------------------------------------------------------------

async def record_toss(
    db: AsyncSession,
    match_id: int,
    user_id: int,
    winner_team_id: int,
    decision: str,
) -> Match:
    """
    Record the toss result and advance match status to 'toss_done'.
    Only created_by or a registered umpire may call this.
    decision must be 'bat' or 'field'.
    Raises 400 if decision is invalid or winner_team_id is not one of the match teams.
    """
    match = await _get_match_or_404(db, match_id)
    await _require_created_by_or_umpire(db, match, user_id)

    if match.status in ("live", "innings_break", "completed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot record toss when match status is '{match.status}'",
        )

    if decision not in ("bat", "field"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="toss_decision must be 'bat' or 'field'",
        )

    if winner_team_id not in (match.team_a_id, match.team_b_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="toss winner must be one of the two match teams",
        )

    match.toss_winner_team_id = winner_team_id
    match.toss_decision = decision
    match.status = _TOSS_DONE
    db.add(match)
    return match


# ---------------------------------------------------------------------------
# start_match
# ---------------------------------------------------------------------------

async def start_match(
    db: AsyncSession,
    match_id: int,
    user_id: int,
    striker_id: int,
    non_striker_id: int,
    current_bowler_id: int,
) -> tuple[Match, MatchInnings, MatchLiveState]:
    """
    Transition match from 'toss_done' to 'live'.
    Atomically:
      1. Determines batting/bowling teams from toss result.
      2. INSERTs MatchInnings (innings_number=1, status='live').
      3. INSERTs MatchLiveState with the opening batsmen and bowler.
      4. UPDATEs match status='live', started_at=now().

    Only created_by or umpire may call this.
    striker_id, non_striker_id, current_bowler_id come from the request body
    (first two batsmen and first bowler chosen by the scorer/umpire).
    """
    match = await _get_match_or_404(db, match_id)
    await _require_created_by_or_umpire(db, match, user_id)

    if match.status != _TOSS_DONE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Match can only be started when status is '{_TOSS_DONE}'; "
                f"current status is '{match.status}'"
            ),
        )

    # Determine batting / bowling teams from toss
    # toss winner bats  → batting_team = toss_winner, bowling_team = other
    # toss winner fields → batting_team = other, bowling_team = toss_winner
    other_team_id = (
        match.team_a_id
        if match.toss_winner_team_id == match.team_b_id
        else match.team_b_id
    )
    if match.toss_decision == "bat":
        batting_team_id = match.toss_winner_team_id
        bowling_team_id = other_team_id
    else:  # 'field'
        batting_team_id = other_team_id
        bowling_team_id = match.toss_winner_team_id

    # INSERT innings
    innings = MatchInnings(
        match_id=match_id,
        batting_team_id=batting_team_id,
        bowling_team_id=bowling_team_id,
        innings_number=1,
        status="live",
        started_at=datetime.now(tz=timezone.utc),
    )
    db.add(innings)
    await db.flush()  # get innings.id

    # INSERT live state — match_id is the PK
    live_state = MatchLiveState(
        match_id=match_id,
        current_innings_id=innings.id,
        striker_id=striker_id,
        non_striker_id=non_striker_id,
        current_bowler_id=current_bowler_id,
        current_over=1,
        current_ball=0,
        total_deliveries=0,
        current_runs=0,
        current_wickets=0,
        current_balls_bowled=0,
    )
    db.add(live_state)

    # UPDATE match
    match.status = "live"
    match.started_at = datetime.now(tz=timezone.utc)
    db.add(match)

    await db.flush()
    return match, innings, live_state


# ---------------------------------------------------------------------------
# Read functions
# ---------------------------------------------------------------------------

async def get_match(db: AsyncSession, match_id: int) -> Optional[Match]:
    """Return match by id (deleted_at IS NULL), or None if not found."""
    result = await db.execute(
        select(Match).where(Match.id == match_id, Match.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()


async def get_live_matches(
    db: AsyncSession, page: int, per_page: int
) -> dict:
    """
    Return paginated public live matches ordered by most recently started.
    Filters: status='live', visibility='public', deleted_at IS NULL.
    """
    base = (
        select(Match)
        .where(
            Match.status == "live",
            Match.visibility == "public",
            Match.deleted_at.is_(None),
        )
        .order_by(Match.started_at.desc())
    )
    total: int = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()
    items = (
        await db.execute(base.offset((page - 1) * per_page).limit(per_page))
    ).scalars().all()
    return {"items": list(items), "total": total, "page": page, "per_page": per_page}


async def get_user_matches(
    db: AsyncSession, user_id: int, page: int, per_page: int
) -> dict:
    """
    Return paginated matches where the user is creator OR a registered player.
    Uses a subquery to avoid duplicates when user appears in multiple player rows.
    """
    base = (
        select(Match)
        .where(
            Match.deleted_at.is_(None),
            or_(
                Match.created_by == user_id,
                Match.id.in_(
                    select(MatchPlayer.match_id).where(
                        MatchPlayer.user_id == user_id
                    )
                ),
            ),
        )
        .order_by(Match.created_at.desc())
    )
    total: int = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()
    items = (
        await db.execute(base.offset((page - 1) * per_page).limit(per_page))
    ).scalars().all()
    return {"items": list(items), "total": total, "page": page, "per_page": per_page}
