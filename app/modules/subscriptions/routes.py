from typing import Any, Dict

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.modules.subscriptions import controller

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


@router.get(
    "/plans",
    response_model=Dict[str, Any],
    summary="List all active subscription plans",
    description="🌐 Public.",
    responses={200: {"content": {"application/json": {"example": {
        "success": True, "message": "Plans",
        "data": [
            {"id": 1, "code": "free", "name": "Free", "price": 0, "currency": "BDT",
             "features": ["1 team", "Public matches only"]},
            {"id": 2, "code": "premium", "name": "Premium", "price": 499, "currency": "BDT",
             "features": ["Unlimited teams", "Private matches", "Match invites", "Live scoring"]}
        ]
    }}}}},
)
async def list_plans(db: AsyncSession = Depends(get_db)):
    return await controller.get_plans(db)


@router.get(
    "/me",
    response_model=Dict[str, Any],
    summary="Get my active subscription",
    description="🔒 Auth required.",
    responses={
        200: {"content": {"application/json": {"example": {
            "success": True, "message": "Subscription",
            "data": {"plan_code": "free", "status": "active",
                     "started_at": "2025-01-15T00:00:00Z", "expires_at": None}
        }}}},
        401: {"description": "Auth required"}
    },
)
async def my_subscription(request: Request, db: AsyncSession = Depends(get_db)):
    user_id: int = request.state.user["id"]
    return await controller.get_my_subscription(db, user_id)
