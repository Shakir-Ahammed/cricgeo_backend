"""
Location models: Country and City.
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric, func
from app.core.db import Base


class Country(Base):
    __tablename__ = "countries"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    iso2 = Column(String(2), unique=True, nullable=True)   # BD, IN, US
    iso3 = Column(String(3), unique=True, nullable=True)   # BGD, IND, USA
    phone_code = Column(String(10), nullable=True)          # +880

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<Country(id={self.id}, iso2={self.iso2}, name={self.name})>"


class City(Base):
    __tablename__ = "cities"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    country_id = Column(Integer, ForeignKey("countries.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    state = Column(String(100), nullable=True)
    latitude = Column(Numeric(10, 7), nullable=True)
    longitude = Column(Numeric(10, 7), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<City(id={self.id}, name={self.name}, country_id={self.country_id})>"
