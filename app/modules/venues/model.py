"""
Venue model for CricGeo backend.
"""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)

from app.core.db import Base


class Venue(Base):
    __tablename__ = "venues"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)

    name = Column(String(150), nullable=False)
    address = Column(Text, nullable=True)

    # FK columns only — no ORM relationships
    city_id = Column(Integer, ForeignKey("cities.id", ondelete="SET NULL"), nullable=True, index=True)
    country_id = Column(Integer, ForeignKey("countries.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)

    latitude = Column(Numeric(9, 6), nullable=True)
    longitude = Column(Numeric(9, 6), nullable=True)

    is_public = Column(Boolean, nullable=False, default=True)
    status = Column(String(20), nullable=False, default="active")

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    def __repr__(self) -> str:
        return f"<Venue(id={self.id}, name={self.name!r}, city_id={self.city_id})>"
