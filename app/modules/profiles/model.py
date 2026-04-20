"""
Profile models: Profile, PlayerRole, BattingInfo, BowlingInfo.
"""

from sqlalchemy import Column, Integer, String, DateTime, Date, Text, ForeignKey, func
from app.core.db import Base


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)

    country_id = Column(Integer, ForeignKey("countries.id", ondelete="SET NULL"), nullable=True)
    city_id = Column(Integer, ForeignKey("cities.id", ondelete="SET NULL"), nullable=True)

    gender = Column(Integer, nullable=True)          # 1=male, 2=female, 3=other
    date_of_birth = Column(Date, nullable=True)
    profile_image = Column(String(500), nullable=True)
    bio = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<Profile(id={self.id}, user_id={self.user_id})>"


class PlayerRole(Base):
    __tablename__ = "player_roles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # 1=batsman, 2=bowler, 3=wicketkeeper, 4=allrounder
    role = Column(Integer, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<PlayerRole(id={self.id}, user_id={self.user_id}, role={self.role})>"


class BattingInfo(Base):
    __tablename__ = "batting_infos"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)

    batting_style = Column(Integer, nullable=True)   # 1=left, 2=right
    batting_order = Column(Integer, nullable=True)   # 1=opening, 2=middle, 3=lower, 4=tailender

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<BattingInfo(id={self.id}, user_id={self.user_id})>"


class BowlingInfo(Base):
    __tablename__ = "bowling_infos"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)

    bowling_style = Column(Integer, nullable=True)     # 1=left-arm, 2=right-arm
    bowling_category = Column(Integer, nullable=True)  # 1=pace, 2=spin
    # 1=fast,2=fast medium,3=medium,4=off break,5=leg break,6=orthodox,7=wrist spin
    bowling_type = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<BowlingInfo(id={self.id}, user_id={self.user_id})>"
