"""
Location schemas: Country and City.
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from decimal import Decimal


class CountryOut(BaseModel):
    id: int
    name: str
    iso2: Optional[str] = None
    iso3: Optional[str] = None
    phone_code: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class CityOut(BaseModel):
    id: int
    country_id: int
    name: str
    state: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    created_at: datetime

    class Config:
        from_attributes = True
