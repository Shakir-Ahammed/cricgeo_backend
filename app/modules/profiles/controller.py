"""
Profile controller.
"""

from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.profiles.service import ProfileService
from app.modules.profiles.schema import UpdateProfileRequest, UpdateSkillsRequest


class ProfileController:

    @staticmethod
    async def get_full_profile(user_id: int, db: AsyncSession) -> Dict[str, Any]:
        service = ProfileService(db)
        data = await service.get_full_profile(user_id)
        return {"success": True, "message": "Profile retrieved", "data": data.model_dump()}

    @staticmethod
    async def upsert_profile(user_id: int, req: UpdateProfileRequest, db: AsyncSession) -> Dict[str, Any]:
        service = ProfileService(db)
        data = await service.upsert_profile(user_id, req)
        return {"success": True, "message": "Profile updated successfully", "data": data.model_dump()}

    @staticmethod
    async def update_skills(user_id: int, req: UpdateSkillsRequest, db: AsyncSession) -> Dict[str, Any]:
        service = ProfileService(db)
        data = await service.update_skills(user_id, req)
        return {"success": True, "message": "Player skills updated successfully", "data": data.model_dump()}

    @staticmethod
    async def save_profile_image(user_id: int, url: str, db: AsyncSession) -> None:
        service = ProfileService(db)
        await service.save_profile_image(user_id, url)
