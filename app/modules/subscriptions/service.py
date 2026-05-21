from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.subscriptions.model import SubscriptionPlan, UserSubscription


async def get_active_plans(db: AsyncSession) -> list[SubscriptionPlan]:
    """Return all active subscription plans ordered by monthly price ascending."""
    result = await db.execute(
        select(SubscriptionPlan)
        .where(SubscriptionPlan.is_active == True)  # noqa: E712
        .order_by(SubscriptionPlan.price_monthly.asc())
    )
    return list(result.scalars().all())


async def get_plan_by_slug(db: AsyncSession, slug: str) -> Optional[SubscriptionPlan]:
    """Return a plan by its slug."""
    result = await db.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.slug == slug)
    )
    return result.scalar_one_or_none()


async def get_plan_by_id(db: AsyncSession, plan_id: int) -> Optional[SubscriptionPlan]:
    """Return a plan by its primary key."""
    result = await db.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id)
    )
    return result.scalar_one_or_none()


async def get_user_subscription(db: AsyncSession, user_id: int) -> Optional[UserSubscription]:
    """Return the most recent active subscription for a user."""
    result = await db.execute(
        select(UserSubscription)
        .where(
            UserSubscription.user_id == user_id,
            UserSubscription.status == "active",
        )
        .order_by(UserSubscription.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_user_subscription_with_plan(
    db: AsyncSession, user_id: int
) -> Optional[tuple[UserSubscription, SubscriptionPlan]]:
    """Return the active subscription and its plan for a user, or None."""
    result = await db.execute(
        select(UserSubscription, SubscriptionPlan)
        .join(SubscriptionPlan, UserSubscription.plan_id == SubscriptionPlan.id)
        .where(
            UserSubscription.user_id == user_id,
            UserSubscription.status == "active",
        )
        .order_by(UserSubscription.created_at.desc())
        .limit(1)
    )
    row = result.first()
    if row is None:
        return None
    return row[0], row[1]


async def assign_free_plan(db: AsyncSession, user_id: int) -> UserSubscription:
    """
    Assign the free plan to a user. Idempotent — returns the existing active
    free-plan subscription if one already exists, avoiding duplicate rows.

    NOTE: Requires a 'free' plan row in subscription_plans (slug='free').
    Seed this row in a data migration before calling this function.
    """
    # Idempotency check: return existing active subscription if present
    existing = await get_user_subscription(db, user_id)
    if existing is not None:
        return existing

    free_plan = await get_plan_by_slug(db, "free")
    if free_plan is None:
        raise ValueError("Free subscription plan not found. Ensure the 'free' plan is seeded.")

    now = datetime.now(tz=timezone.utc)
    sub = UserSubscription(
        user_id=user_id,
        plan_id=free_plan.id,
        status="active",
        starts_at=now,
        expires_at=None,  # free plan never expires
        trial_ends_at=None,
    )
    db.add(sub)
    await db.commit()
    await db.refresh(sub)
    return sub
