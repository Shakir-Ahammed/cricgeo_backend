"""
Profile service: Profile, PlayerRole, BattingInfo, BowlingInfo.
"""

from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from fastapi import HTTPException, status

from app.modules.profiles.model import Profile, PlayerRole, BattingInfo, BowlingInfo
from app.modules.profiles.schema import (
    ProfileOut, PlayerRoleOut, PlayerRoleRequest,
    BattingInfoOut, BattingInfoRequest,
    BowlingInfoOut, BowlingInfoRequest,
)


class ProfileService:

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Profile
    # ------------------------------------------------------------------

    async def get_profile(self, user_id: int) -> ProfileOut:
        result = await self.db.execute(select(Profile).where(Profile.user_id == user_id))
        profile = result.scalar_one_or_none()
        if not profile:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
        return ProfileOut.model_validate(profile)

    # ------------------------------------------------------------------
    # Player roles
    # ------------------------------------------------------------------

    async def get_player_roles(self, user_id: int) -> List[PlayerRoleOut]:
        result = await self.db.execute(select(PlayerRole).where(PlayerRole.user_id == user_id))
        return [PlayerRoleOut.model_validate(r) for r in result.scalars().all()]

    async def set_player_roles(self, user_id: int, roles: List[PlayerRoleRequest]) -> List[PlayerRoleOut]:
        await self.db.execute(delete(PlayerRole).where(PlayerRole.user_id == user_id))
        seen = set()
        for req in roles:
            if req.role not in seen:
                seen.add(req.role)
                self.db.add(PlayerRole(user_id=user_id, role=req.role))
        await self.db.commit()
        return await self.get_player_roles(user_id)

    # ------------------------------------------------------------------
    # Batting info
    # ------------------------------------------------------------------

    async def get_batting_info(self, user_id: int) -> BattingInfoOut:
        result = await self.db.execute(select(BattingInfo).where(BattingInfo.user_id == user_id))
        info = result.scalar_one_or_none()
        if not info:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batting info not found")
        return BattingInfoOut.model_validate(info)

    async def upsert_batting_info(self, user_id: int, req: BattingInfoRequest) -> BattingInfoOut:
        result = await self.db.execute(select(BattingInfo).where(BattingInfo.user_id == user_id))
        info = result.scalar_one_or_none()
        if info:
            info.batting_style = req.batting_style
            info.batting_order = req.batting_order
        else:
            info = BattingInfo(user_id=user_id, batting_style=req.batting_style, batting_order=req.batting_order)
            self.db.add(info)
        await self.db.commit()
        await self.db.refresh(info)
        return BattingInfoOut.model_validate(info)

    # ------------------------------------------------------------------
    # Bowling info
    # ------------------------------------------------------------------

    async def get_bowling_info(self, user_id: int) -> BowlingInfoOut:
        result = await self.db.execute(select(BowlingInfo).where(BowlingInfo.user_id == user_id))
        info = result.scalar_one_or_none()
        if not info:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bowling info not found")
        return BowlingInfoOut.model_validate(info)

    async def upsert_bowling_info(self, user_id: int, req: BowlingInfoRequest) -> BowlingInfoOut:
        result = await self.db.execute(select(BowlingInfo).where(BowlingInfo.user_id == user_id))
        info = result.scalar_one_or_none()
        if info:
            info.bowling_style = req.bowling_style
            info.bowling_category = req.bowling_category
            info.bowling_type = req.bowling_type
        else:
            info = BowlingInfo(
                user_id=user_id,
                bowling_style=req.bowling_style,
                bowling_category=req.bowling_category,
                bowling_type=req.bowling_type,
            )
            self.db.add(info)
        await self.db.commit()
        await self.db.refresh(info)
        return BowlingInfoOut.model_validate(info)
