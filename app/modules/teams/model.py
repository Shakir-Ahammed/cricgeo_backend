"""
Team SQLAlchemy models: Team, TeamMember, TeamInvitation.
"""

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean,
    ForeignKey, UniqueConstraint, func,
)
from app.core.db import Base


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    name = Column(String(150), nullable=False)
    short_name = Column(String(10), nullable=True)
    logo = Column(String(500), nullable=True)
    type = Column(String(30), nullable=True)            # e.g. 'club', 'school', 'corporate'
    country_id = Column(Integer, ForeignKey("countries.id", ondelete="SET NULL"), nullable=True)
    city_id = Column(Integer, ForeignKey("cities.id", ondelete="SET NULL"), nullable=True)
    description = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="active")

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)   # soft delete

    def __repr__(self) -> str:
        return f"<Team(id={self.id}, name={self.name!r})>"


class TeamMember(Base):
    __tablename__ = "team_members"
    __table_args__ = (
        UniqueConstraint("team_id", "user_id", name="uq_team_members_team_user"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(30), nullable=False)           # 'captain', 'player', 'coach', etc.
    jersey_number = Column(Integer, nullable=True)
    status = Column(String(20), nullable=False, default="active")  # active, released
    joined_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    released_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<TeamMember(team_id={self.team_id}, user_id={self.user_id}, role={self.role!r})>"


class TeamInvitation(Base):
    __tablename__ = "team_invitations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    invited_by = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Invitee may be a registered user (invitee_user_id) OR an external contact
    # (invitee_identifier = phone/email, invitee_name for display)
    invitee_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    invitee_identifier = Column(String(255), nullable=True)   # phone or email if not a registered user
    invitee_name = Column(String(150), nullable=True)

    role = Column(String(30), nullable=False, default="player")
    invite_method = Column(String(30), nullable=False, default="link")  # 'link', 'qr', 'phone', 'email'
    token = Column(String(255), unique=True, nullable=False, index=True)
    status = Column(String(20), nullable=False, default="pending")      # pending, accepted, declined, expired
    expires_at = Column(DateTime(timezone=True), nullable=False)
    responded_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<TeamInvitation(id={self.id}, team_id={self.team_id}, status={self.status!r})>"


class TeamJoinRequest(Base):
    """
    Created when a user scans a QR code and requests to join.
    Captain must approve before the user becomes a TeamMember.
    UniqueConstraint prevents duplicate pending requests per (team, user).
    """
    __tablename__ = "team_join_requests"
    __table_args__ = (
        UniqueConstraint("team_id", "user_id", name="uq_team_join_request_team_user"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # The QR invitation that triggered this request
    invitation_id = Column(Integer, ForeignKey("team_invitations.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(20), nullable=False, default="pending")  # pending, approved, rejected
    message = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    responded_at = Column(DateTime(timezone=True), nullable=True)
    responded_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    def __repr__(self) -> str:
        return f"<TeamJoinRequest(id={self.id}, team_id={self.team_id}, user_id={self.user_id}, status={self.status!r})>"
