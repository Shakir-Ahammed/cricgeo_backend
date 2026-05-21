"""
User service layer: business logic for user management.
"""

from __future__ import annotations

from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, outerjoin
from app.modules.users.model import User
from app.modules.profiles.model import Profile
from app.modules.users.schema import UserOut, UserList, PlayerSearchResult
from app.helpers.utils import normalize_email
from app.core.config import settings
from fastapi import HTTPException, status


class UserService:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_users(
        self,
        page: int = 1,
        page_size: Optional[int] = None,
        search: Optional[str] = None,
    ) -> UserList:
        if page_size is None:
            page_size = settings.DEFAULT_PAGE_SIZE
        if page < 1:
            page = 1
        if page_size < 1 or page_size > settings.MAX_PAGE_SIZE:
            page_size = settings.DEFAULT_PAGE_SIZE

        query = select(User).where(User.deleted_at == None)  # noqa: E711

        if search:
            like = f"%{search}%"
            query = query.where(
                (User.name.ilike(like)) | (User.email.ilike(like)) | (User.phone.ilike(like))
            )

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar()

        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size).order_by(User.created_at.desc())
        users = (await self.db.execute(query)).scalars().all()

        return UserList(
            total=total,
            page=page,
            page_size=page_size,
            users=[UserOut.model_validate(u) for u in users],
        )

    async def get_user_by_id(self, user_id: int) -> UserOut:
        result = await self.db.execute(select(User).where(User.id == user_id, User.deleted_at == None))  # noqa: E711
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {user_id} not found")
        return UserOut.model_validate(user)

    async def search_players(self, q: str, limit: int = 20) -> List[PlayerSearchResult]:
        """
        Search users by name (ILIKE), exact phone, or username (ILIKE).
        LEFT JOINs profiles so users without a profile row still appear.
        Phone is masked — only last 4 digits returned.
        """
        limit = min(limit, 20)  # cap server-side

        like = f"%{q}%"
        stmt = (
            select(
                User.id,
                User.name,
                User.phone,
                Profile.username,
                Profile.profile_image,
            )
            .select_from(outerjoin(User, Profile, User.id == Profile.user_id))
            .where(
                User.deleted_at == None,  # noqa: E711
                User.status == "active",
                (
                    User.name.ilike(like)
                    | (User.phone == q)
                    | Profile.username.ilike(like)
                ),
            )
            .limit(limit)
        )

        rows = (await self.db.execute(stmt)).all()

        results: List[PlayerSearchResult] = []
        for row in rows:
            masked_phone: Optional[str] = None
            if row.phone:
                masked_phone = "****" + row.phone[-4:]
            results.append(
                PlayerSearchResult(
                    id=row.id,
                    name=row.name,
                    phone=masked_phone,
                    username=row.username,
                    profile_image=row.profile_image,
                )
            )
        return results

    async def bulk_check_phones(self, phones: List[str]) -> dict:
        """
        Given a list of phone numbers (from contacts), return which are
        registered users and which are not. Used by 'Add From Contacts' flow.
        Max 200 phones per request.
        """
        phones = list(dict.fromkeys(phones))[:200]  # dedupe + cap

        stmt = (
            select(User.id, User.name, User.phone)
            .where(
                User.phone.in_(phones),
                User.deleted_at.is_(None),
                User.status == "active",
            )
        )
        rows = (await self.db.execute(stmt)).all()

        registered_phones = {row.phone for row in rows}
        registered = [
            {"phone": row.phone, "user_id": row.id, "name": row.name}
            for row in rows
        ]
        unregistered = [p for p in phones if p not in registered_phones]

        return {"registered": registered, "unregistered": unregistered}
