from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class SubscriptionPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    price_monthly: Decimal
    price_yearly: Decimal
    currency: str
    features: Optional[Any] = None
    max_matches_per_month: Optional[int] = None
    max_teams: Optional[int] = None


class UserSubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    plan_id: int
    status: str
    starts_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    plan: SubscriptionPlanResponse
