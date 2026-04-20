"""
Location service: Countries and Cities.
"""

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status

from app.modules.locations.model import Country, City
from app.modules.locations.schema import CountryOut, CityOut


class LocationService:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_countries(self) -> List[CountryOut]:
        result = await self.db.execute(select(Country).order_by(Country.name))
        return [CountryOut.model_validate(c) for c in result.scalars().all()]

    async def get_country(self, country_id: int) -> CountryOut:
        result = await self.db.execute(select(Country).where(Country.id == country_id))
        country = result.scalar_one_or_none()
        if not country:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Country not found")
        return CountryOut.model_validate(country)

    async def get_cities(self, country_id: Optional[int] = None) -> List[CityOut]:
        query = select(City).order_by(City.name)
        if country_id:
            query = query.where(City.country_id == country_id)
        result = await self.db.execute(query)
        return [CityOut.model_validate(c) for c in result.scalars().all()]

    async def get_city(self, city_id: int) -> CityOut:
        result = await self.db.execute(select(City).where(City.id == city_id))
        city = result.scalar_one_or_none()
        if not city:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="City not found")
        return CityOut.model_validate(city)
