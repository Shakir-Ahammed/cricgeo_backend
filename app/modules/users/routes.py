"""
User routes.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.modules.users.controller import UserController
from typing import Dict, Any, Optional

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=Dict[str, Any])
async def get_users(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by name, email or phone"),
    db: AsyncSession = Depends(get_db),
):
    return await UserController.get_users(page, page_size, search, db)


@router.get("/{user_id}", response_model=Dict[str, Any])
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
    return await UserController.get_user(user_id, db)
