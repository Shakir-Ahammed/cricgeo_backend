"""
Location routes: Countries and Cities (public, no auth required).
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional

from app.core.db import get_db
from app.modules.locations.controller import LocationController

router = APIRouter(prefix="/locations", tags=["Locations"])


@router.get("/countries", response_model=Dict[str, Any])
async def get_countries(db: AsyncSession = Depends(get_db)):
    return await LocationController.get_countries(db)


@router.get("/countries/{country_id}", response_model=Dict[str, Any])
async def get_country(country_id: int, db: AsyncSession = Depends(get_db)):
    return await LocationController.get_country(country_id, db)


@router.get("/cities", response_model=Dict[str, Any])
async def get_cities(
    country_id: Optional[int] = Query(None, description="Filter cities by country ID"),
    db: AsyncSession = Depends(get_db),
):
    return await LocationController.get_cities(country_id, db)


@router.get("/cities/{city_id}", response_model=Dict[str, Any])
async def get_city(city_id: int, db: AsyncSession = Depends(get_db)):
    return await LocationController.get_city(city_id, db)
