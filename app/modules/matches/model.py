"""
Match SQLAlchemy models:
Match, MatchPowerplay, MatchOfficial, MatchInvitation,
MatchPlayer, MatchInnings, MatchLiveState.
"""

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, ForeignKey,
    Integer, SmallInteger, String, Text, UniqueConstraint, func,
)
from app.core.db import Base


class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Optional linkage to tournament/round (nullable for friendly matches)
    tournament_id = Column(Integer, ForeignKey("tournaments.id", ondelete="SET NULL"), nullable=True, index=True)
    round_id = Column(Integer, ForeignKey("tournament_rounds.id", ondelete="SET NULL"), nullable=True, index=True)

    # Teams
    team_a_id = Column(Integer, ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False, index=True)
    team_b_id = Column(Integer, ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False, index=True)

    # Venue — either FK or free-text name
    venue_id = Column(Integer, ForeignKey("venues.id", ondelete="SET NULL"), nullable=True, index=True)
    venue_name = Column(String(200), nullable=True)

    # Match configuration
    format = Column(String(30), nullable=False)                         # 'T20', 'ODI', 'Test', 'T10', 'Custom'
    overs_per_innings = Column(Integer, nullable=False)
    overs_per_bowler = Column(Integer, nullable=True)
    match_type = Column(String(30), nullable=False, default="friendly") # 'friendly', 'tournament', 'practice'
    visibility = Column(String(20), nullable=False, default="public")   # 'public', 'private'

    # Toss
    toss_winner_team_id = Column(Integer, ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    toss_decision = Column(String(10), nullable=True)                   # 'bat', 'field'

    # Result
    status = Column(String(30), nullable=False, default="scheduled")   # scheduled, toss_done, live, innings_break, completed, abandoned, cancelled
    winner_team_id = Column(Integer, ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    result_type = Column(String(30), nullable=True)                     # 'runs', 'wickets', 'tie', 'no_result', 'dls'
    result_margin = Column(Integer, nullable=True)

    # DLS
    dls_applied = Column(Boolean, nullable=False, default=False)
    dls_target = Column(Integer, nullable=True)

    # Awards
    man_of_the_match_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Meta
    created_by = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)         # soft delete

    def __repr__(self) -> str:
        return f"<Match(id={self.id}, status={self.status!r})>"


class MatchPowerplay(Base):
    __tablename__ = "match_powerplays"
    __table_args__ = (
        UniqueConstraint("match_id", "pp_number", name="uq_match_powerplays_match_pp"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    match_id = Column(Integer, ForeignKey("matches.id", ondelete="CASCADE"), nullable=False, index=True)
    pp_number = Column(Integer, nullable=False)        # 1 = mandatory PP, 2/3 = optional PPs
    from_over = Column(Integer, nullable=False)        # 1-indexed over number (inclusive)
    to_over = Column(Integer, nullable=False)          # 1-indexed over number (inclusive)
    fielding_restrictions = Column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<MatchPowerplay(match_id={self.match_id}, pp_number={self.pp_number})>"


class MatchOfficial(Base):
    __tablename__ = "match_officials"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    match_id = Column(Integer, ForeignKey("matches.id", ondelete="CASCADE"), nullable=False, index=True)

    # Official may be a registered user OR a guest (not both null — enforced at service layer)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    guest_name = Column(String(150), nullable=True)
    guest_phone = Column(String(20), nullable=True)

    role = Column(String(30), nullable=False)          # 'umpire', 'scorer', 'referee', 'live_streamer'
    position = Column(SmallInteger, nullable=True)     # e.g. 1 = on-field, 2 = TV umpire
    status = Column(String(20), nullable=False, default="invited")  # invited, confirmed, declined

    def __repr__(self) -> str:
        return f"<MatchOfficial(match_id={self.match_id}, role={self.role!r})>"


class MatchInvitation(Base):
    __tablename__ = "match_invitations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    match_id = Column(Integer, ForeignKey("matches.id", ondelete="CASCADE"), nullable=False, index=True)
    invited_by = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Invitee — registered user or external identifier
    invitee_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    invitee_identifier = Column(String(255), nullable=True)    # phone/email for non-registered invitees

    invite_method = Column(String(20), nullable=False)         # 'link', 'qr', 'phone', 'email'
    token = Column(String(255), unique=True, nullable=False, index=True)
    role = Column(String(20), nullable=False, default="viewer")   # 'viewer', 'player', 'scorer', 'umpire'
    status = Column(String(20), nullable=False, default="pending")   # pending, accepted, declined, expired
    expires_at = Column(DateTime(timezone=True), nullable=False)
    responded_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<MatchInvitation(id={self.id}, match_id={self.match_id}, status={self.status!r})>"


class MatchPlayer(Base):
    __tablename__ = "match_players"
    __table_args__ = (
        UniqueConstraint("match_id", "user_id", name="uq_match_players_match_user"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    match_id = Column(Integer, ForeignKey("matches.id", ondelete="CASCADE"), nullable=False, index=True)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    batting_order = Column(Integer, nullable=True)
    is_playing_xi = Column(Boolean, nullable=False, default=True)
    is_captain = Column(Boolean, nullable=False, default=False)
    is_wicketkeeper = Column(Boolean, nullable=False, default=False)
    is_substitute = Column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:
        return f"<MatchPlayer(match_id={self.match_id}, user_id={self.user_id})>"


class MatchInnings(Base):
    __tablename__ = "match_innings"
    __table_args__ = (
        UniqueConstraint("match_id", "innings_number", name="uq_match_innings_match_number"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    match_id = Column(Integer, ForeignKey("matches.id", ondelete="CASCADE"), nullable=False, index=True)
    batting_team_id = Column(Integer, ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False)
    bowling_team_id = Column(Integer, ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False)

    innings_number = Column(Integer, nullable=False)   # 1 or 2

    # Running totals — updated after every ball
    total_runs = Column(Integer, nullable=False, default=0)
    wickets = Column(Integer, nullable=False, default=0)
    balls_bowled = Column(Integer, nullable=False, default=0)   # legal deliveries only

    # Extras breakdown
    extras = Column(Integer, nullable=False, default=0)
    wide_balls = Column(Integer, nullable=False, default=0)
    no_balls = Column(Integer, nullable=False, default=0)
    byes = Column(Integer, nullable=False, default=0)
    leg_byes = Column(Integer, nullable=False, default=0)
    penalty_runs = Column(Integer, nullable=False, default=0)

    # Second innings only
    target_runs = Column(Integer, nullable=True)

    status = Column(String(20), nullable=False, default="upcoming")  # upcoming, live, completed, cancelled
    started_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<MatchInnings(match_id={self.match_id}, innings_number={self.innings_number})>"


class MatchLiveState(Base):
    """
    Single-row live state for a match.
    match_id is the PRIMARY KEY — O(1) PK lookup, no autoincrement id.
    """
    __tablename__ = "match_live_states"

    match_id = Column(
        Integer,
        ForeignKey("matches.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )

    current_innings_id = Column(Integer, ForeignKey("match_innings.id", ondelete="RESTRICT"), nullable=False)

    # Current batsmen and bowler
    striker_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    non_striker_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    current_bowler_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)

    # Current over progress
    current_over = Column(Integer, nullable=False, default=1)       # 1-indexed
    current_ball = Column(Integer, nullable=False, default=0)       # legal deliveries in current over (0–5)
    total_deliveries = Column(Integer, nullable=False, default=0)   # all deliveries inc. wides/no-balls

    # Running totals for current innings (denormalised for fast reads)
    current_runs = Column(Integer, nullable=False, default=0)
    current_wickets = Column(Integer, nullable=False, default=0)
    current_balls_bowled = Column(Integer, nullable=False, default=0)  # legal deliveries in innings

    # Reference to last ball (for undo support)
    last_ball_id = Column(BigInteger, nullable=True)

    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return (
            f"<MatchLiveState(match_id={self.match_id}, "
            f"over={self.current_over}, ball={self.current_ball})>"
        )
