"""
User controller: thin layer between routes and UserService.
"""

from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.modules.users.service import UserService
from typing import Dict, Any, Optional


class UserController:

    @staticmethod
    async def get_users(
        page: int,
        page_size: int,
        search: Optional[str],
        db: AsyncSession,
    ) -> Dict[str, Any]:
        service = UserService(db)
        user_list = await service.get_users(page, page_size, search)
        return {"success": True, "message": "Users retrieved successfully", "data": user_list.model_dump()}

    @staticmethod
    async def get_user(user_id: int, db: AsyncSession) -> Dict[str, Any]:
        service = UserService(db)
        user = await service.get_user_by_id(user_id)
        return {"success": True, "message": "User retrieved successfully", "data": user.model_dump()}
