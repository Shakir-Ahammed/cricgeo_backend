from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.modules.subscriptions import controller

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


@router.get("/plans")
async def list_plans(db: AsyncSession = Depends(get_db)):
    """List all active subscription plans. Public endpoint."""
    return await controller.get_plans(db)


@router.get("/me")
async def my_subscription(request: Request, db: AsyncSession = Depends(get_db)):
    """Return the current user's active subscription. Requires authentication."""
    user_id: int = request.state.user["id"]
    return await controller.get_my_subscription(db, user_id)
