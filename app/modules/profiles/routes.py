"""
Profile routes.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List

from app.core.db import get_db
from app.core.security import get_current_user
from app.modules.profiles.controller import ProfileController
from app.modules.profiles.schema import PlayerRoleRequest, BattingInfoRequest, BowlingInfoRequest

router = APIRouter(prefix="/profiles", tags=["Profiles"])


@router.get("/me", response_model=Dict[str, Any])
async def get_my_profile(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    return await ProfileController.get_profile(user["id"], db)


@router.get("/me/player-roles", response_model=Dict[str, Any])
async def get_player_roles(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    return await ProfileController.get_player_roles(user["id"], db)


@router.put("/me/player-roles", response_model=Dict[str, Any])
async def set_player_roles(
    roles: List[PlayerRoleRequest],
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    return await ProfileController.set_player_roles(user["id"], roles, db)


@router.get("/me/batting", response_model=Dict[str, Any])
async def get_batting_info(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    return await ProfileController.get_batting_info(user["id"], db)


@router.put("/me/batting", response_model=Dict[str, Any])
async def upsert_batting_info(
    req: BattingInfoRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    return await ProfileController.upsert_batting_info(user["id"], req, db)


@router.get("/me/bowling", response_model=Dict[str, Any])
async def get_bowling_info(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    return await ProfileController.get_bowling_info(user["id"], db)


@router.put("/me/bowling", response_model=Dict[str, Any])
async def upsert_bowling_info(
    req: BowlingInfoRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    return await ProfileController.upsert_bowling_info(user["id"], req, db)
