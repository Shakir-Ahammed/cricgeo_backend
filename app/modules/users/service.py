"""
User service layer: business logic for user management.
"""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.modules.users.model import User
from app.modules.users.schema import UserOut, UserList
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
