"""
Profile controller.
"""

from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.profiles.service import ProfileService
from app.modules.profiles.schema import PlayerRoleRequest, BattingInfoRequest, BowlingInfoRequest


class ProfileController:

    @staticmethod
    async def get_profile(user_id: int, db: AsyncSession) -> Dict[str, Any]:
        service = ProfileService(db)
        profile = await service.get_profile(user_id)
        return {"success": True, "message": "Profile retrieved", "data": profile.model_dump()}

    @staticmethod
    async def get_player_roles(user_id: int, db: AsyncSession) -> Dict[str, Any]:
        service = ProfileService(db)
        roles = await service.get_player_roles(user_id)
        return {"success": True, "message": "Player roles retrieved", "data": [r.model_dump() for r in roles]}

    @staticmethod
    async def set_player_roles(user_id: int, roles: List[PlayerRoleRequest], db: AsyncSession) -> Dict[str, Any]:
        service = ProfileService(db)
        result = await service.set_player_roles(user_id, roles)
        return {"success": True, "message": "Player roles updated", "data": [r.model_dump() for r in result]}

    @staticmethod
    async def get_batting_info(user_id: int, db: AsyncSession) -> Dict[str, Any]:
        service = ProfileService(db)
        info = await service.get_batting_info(user_id)
        return {"success": True, "message": "Batting info retrieved", "data": info.model_dump()}

    @staticmethod
    async def upsert_batting_info(user_id: int, req: BattingInfoRequest, db: AsyncSession) -> Dict[str, Any]:
        service = ProfileService(db)
        info = await service.upsert_batting_info(user_id, req)
        return {"success": True, "message": "Batting info saved", "data": info.model_dump()}

    @staticmethod
    async def get_bowling_info(user_id: int, db: AsyncSession) -> Dict[str, Any]:
        service = ProfileService(db)
        info = await service.get_bowling_info(user_id)
        return {"success": True, "message": "Bowling info retrieved", "data": info.model_dump()}

    @staticmethod
    async def upsert_bowling_info(user_id: int, req: BowlingInfoRequest, db: AsyncSession) -> Dict[str, Any]:
        service = ProfileService(db)
        info = await service.upsert_bowling_info(user_id, req)
        return {"success": True, "message": "Bowling info saved", "data": info.model_dump()}
