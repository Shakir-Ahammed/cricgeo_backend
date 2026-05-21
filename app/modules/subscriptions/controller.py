from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.subscriptions import service
from app.modules.subscriptions.schema import SubscriptionPlanResponse, UserSubscriptionResponse


async def get_plans(db: AsyncSession) -> dict:
    plans = await service.get_active_plans(db)
    return {
        "success": True,
        "message": "Subscription plans retrieved successfully",
        "data": [SubscriptionPlanResponse.model_validate(p) for p in plans],
    }


async def get_my_subscription(db: AsyncSession, user_id: int) -> dict:
    row = await service.get_user_subscription_with_plan(db, user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="No active subscription found")

    sub, plan = row
    response = UserSubscriptionResponse.model_validate(
        {
            "id": sub.id,
            "user_id": sub.user_id,
            "plan_id": sub.plan_id,
            "status": sub.status,
            "starts_at": sub.starts_at,
            "expires_at": sub.expires_at,
            "plan": SubscriptionPlanResponse.model_validate(plan),
        }
    )
    return {
        "success": True,
        "message": "Subscription retrieved successfully",
        "data": response,
    }
