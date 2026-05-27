"""
Location routes: Countries and Cities (public, no auth required).
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional

from app.core.db import get_db
from app.modules.locations.controller import LocationController

router = APIRouter(prefix="/locations", tags=["Locations"])


@router.get(
    "/countries",
    response_model=Dict[str, Any],
    summary="List all countries",
    description="🌐 Public.",
    responses={200: {"content": {"application/json": {"example": {
        "success": True, "message": "Countries",
        "data": [{"id": 1, "name": "Bangladesh", "code": "BD"},
                 {"id": 2, "name": "India", "code": "IN"}]
    }}}}},
)
async def get_countries(db: AsyncSession = Depends(get_db)):
    return await LocationController.get_countries(db)


@router.get(
    "/countries/{country_id}",
    response_model=Dict[str, Any],
    summary="Get a country by id",
    description="🌐 Public.",
    responses={
        200: {"content": {"application/json": {"example": {
            "success": True, "message": "Country",
            "data": {"id": 1, "name": "Bangladesh", "code": "BD"}
        }}}},
        404: {"description": "Country not found"}
    },
)
async def get_country(country_id: int, db: AsyncSession = Depends(get_db)):
    return await LocationController.get_country(country_id, db)


@router.get(
    "/cities",
    response_model=Dict[str, Any],
    summary="List cities (optionally filtered by country)",
    description="🌐 Public. Pass `?country_id=1` for Bangladesh cities only.",
    responses={200: {"content": {"application/json": {"example": {
        "success": True, "message": "Cities",
        "data": [{"id": 1, "name": "Dhaka", "country_id": 1},
                 {"id": 2, "name": "Chittagong", "country_id": 1},
                 {"id": 3, "name": "Sylhet", "country_id": 1},
                 {"id": 4, "name": "Rajshahi", "country_id": 1}]
    }}}}},
)
async def get_cities(
    country_id: Optional[int] = Query(None, description="Filter cities by country ID"),
    db: AsyncSession = Depends(get_db),
):
    return await LocationController.get_cities(country_id, db)


@router.get(
    "/cities/{city_id}",
    response_model=Dict[str, Any],
    summary="Get a city by id",
    description="🌐 Public.",
    responses={
        200: {"content": {"application/json": {"example": {
            "success": True, "message": "City",
            "data": {"id": 1, "name": "Dhaka", "country_id": 1}
        }}}},
        404: {"description": "City not found"}
    },
)
async def get_city(city_id: int, db: AsyncSession = Depends(get_db)):
    return await LocationController.get_city(city_id, db)
