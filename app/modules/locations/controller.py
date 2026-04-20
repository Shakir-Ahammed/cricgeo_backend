"""
Location controller.
"""

from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.locations.service import LocationService


class LocationController:

    @staticmethod
    async def get_countries(db: AsyncSession) -> Dict[str, Any]:
        service = LocationService(db)
        countries = await service.get_countries()
        return {"success": True, "message": "Countries retrieved", "data": [c.model_dump() for c in countries]}

    @staticmethod
    async def get_country(country_id: int, db: AsyncSession) -> Dict[str, Any]:
        service = LocationService(db)
        country = await service.get_country(country_id)
        return {"success": True, "message": "Country retrieved", "data": country.model_dump()}

    @staticmethod
    async def get_cities(country_id: Optional[int], db: AsyncSession) -> Dict[str, Any]:
        service = LocationService(db)
        cities = await service.get_cities(country_id)
        return {"success": True, "message": "Cities retrieved", "data": [c.model_dump() for c in cities]}

    @staticmethod
    async def get_city(city_id: int, db: AsyncSession) -> Dict[str, Any]:
        service = LocationService(db)
        city = await service.get_city(city_id)
        return {"success": True, "message": "City retrieved", "data": city.model_dump()}
