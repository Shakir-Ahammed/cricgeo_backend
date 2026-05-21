"""
Pydantic v2 schemas for the venues module.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class VenueCreate(BaseModel):
    name: str = Field(..., max_length=150)
    address: Optional[str] = None
    city_id: Optional[int] = None
    country_id: Optional[int] = None
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    is_public: bool = True

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be blank")
        return v


class VenueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    address: Optional[str] = None
    city_id: Optional[int] = None
    country_id: Optional[int] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    created_by: int
    is_public: bool
    status: str
    created_at: datetime


class VenueSearchParams(BaseModel):
    """Query parameters for venue search — used as Depends() in the route."""

    q: Optional[str] = None
    city_id: Optional[int] = None
    lat: Optional[float] = Field(None, ge=-90.0, le=90.0)
    lon: Optional[float] = Field(None, ge=-180.0, le=180.0)
    radius_km: float = Field(10.0, gt=0.0, le=500.0)
    page: int = Field(1, ge=1)
    per_page: int = Field(20, ge=1, le=100)
