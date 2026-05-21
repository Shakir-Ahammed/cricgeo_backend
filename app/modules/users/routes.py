"""
User routes.
"""

from fastapi import APIRouter, Depends, Query, Request, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.modules.users.controller import UserController
from app.modules.users.service import UserService
from typing import Dict, Any, List, Optional

router = APIRouter(prefix="/users", tags=["Users"])


class _BulkCheckBody(BaseModel):
    phones: List[str]


@router.post("/bulk-check", response_model=Dict[str, Any])
async def bulk_check_phones(
    body: _BulkCheckBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Check which phone numbers from a contact list are registered.
    Auth required (prevents scraping). Max 200 phones per request.
    Returns: {registered: [{phone, user_id, name}], unregistered: [phone, ...]}
    """
    if not body.phones:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="phones list is empty")
    svc = UserService(db)
    result = await svc.bulk_check_phones(body.phones)
    return {"success": True, "message": "Contacts checked", "data": result}


@router.get("/search", response_model=Dict[str, Any])
async def search_players(
    request: Request,
    q: str = Query(..., min_length=2, description="Search query — min 2 characters"),
    limit: int = Query(20, ge=1, le=20, description="Max results (capped at 20)"),
    db: AsyncSession = Depends(get_db),
):
    """Search for players by name, phone, or username. Auth required."""
    if len(q.strip()) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query must be at least 2 characters",
        )
    return await UserController.search_players(q.strip(), limit, db)


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
