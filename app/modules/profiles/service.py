"""
Profile service: Profile, PlayerRole, BattingInfo, BowlingInfo.
"""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from fastapi import HTTPException, status

from app.modules.profiles.model import Profile, PlayerRole, BattingInfo, BowlingInfo
from app.modules.profiles.schema import (
    UpdateProfileRequest, UpdateSkillsRequest, FullProfileOut,
)


class ProfileService:

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Internal helper: build full profile from DB rows
    # ------------------------------------------------------------------

    async def get_full_profile(self, user_id: int) -> FullProfileOut:
        from app.modules.users.model import User

        user_result = await self.db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        profile_result = await self.db.execute(select(Profile).where(Profile.user_id == user_id))
        profile = profile_result.scalar_one_or_none()

        roles_result = await self.db.execute(select(PlayerRole).where(PlayerRole.user_id == user_id))
        roles = [r.role for r in roles_result.scalars().all()]

        batting_result = await self.db.execute(select(BattingInfo).where(BattingInfo.user_id == user_id))
        batting = batting_result.scalar_one_or_none()

        bowling_result = await self.db.execute(select(BowlingInfo).where(BowlingInfo.user_id == user_id))
        bowling = bowling_result.scalar_one_or_none()

        return FullProfileOut(
            id=user.id,
            name=user.name,
            email=user.email,
            phone=user.phone,
            is_email_verified=user.is_email_verified,
            is_phone_verified=user.is_phone_verified,
            is_profile_completed=bool(user.is_profile_completed),
            status=user.status,
            country_id=profile.country_id if profile else None,
            city_id=profile.city_id if profile else None,
            gender=profile.gender if profile else None,
            date_of_birth=profile.date_of_birth if profile else None,
            profile_image=profile.profile_image if profile else None,
            bio=profile.bio if profile else None,
            roles=roles,
            batting_style=batting.batting_style if batting else None,
            batting_order=batting.batting_order if batting else None,
            bowling_style=bowling.bowling_style if bowling else None,
            bowling_category=bowling.bowling_category if bowling else None,
            bowling_type=bowling.bowling_type if bowling else None,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    # ------------------------------------------------------------------
    # Step 1: Update personal identity
    # ------------------------------------------------------------------

    async def upsert_profile(self, user_id: int, req: UpdateProfileRequest) -> FullProfileOut:
        from app.modules.users.model import User
        from app.helpers.utils import normalize_email, normalize_phone

        user_result = await self.db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        user.name = req.name

        if req.phone is not None and user.phone is None:
            norm_phone = normalize_phone(req.phone)
            conflict = await self.db.execute(
                select(User).where(User.phone == norm_phone, User.id != user_id)
            )
            if conflict.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Phone number is already linked to another account",
                )
            user.phone = norm_phone

        if req.email is not None and user.email is None:
            norm_email = normalize_email(str(req.email))
            conflict = await self.db.execute(
                select(User).where(User.email == norm_email, User.id != user_id)
            )
            if conflict.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email address is already linked to another account",
                )
            user.email = norm_email

        user.is_profile_completed = True

        profile_result = await self.db.execute(select(Profile).where(Profile.user_id == user_id))
        profile = profile_result.scalar_one_or_none()

        if profile:
            profile.gender = req.gender
            profile.country_id = req.country_id
            profile.city_id = req.city_id
            if req.profile_image is not None:
                profile.profile_image = req.profile_image
            if req.bio is not None:
                profile.bio = req.bio
            if req.date_of_birth is not None:
                profile.date_of_birth = req.date_of_birth
        else:
            profile = Profile(
                user_id=user_id,
                gender=req.gender,
                country_id=req.country_id,
                city_id=req.city_id,
                profile_image=req.profile_image,
                bio=req.bio,
                date_of_birth=req.date_of_birth,
            )
            self.db.add(profile)

        await self.db.commit()
        return await self.get_full_profile(user_id)

    # ------------------------------------------------------------------
    # Step 2: Update player skills (role + batting + bowling)
    # ------------------------------------------------------------------

    async def update_skills(self, user_id: int, req: UpdateSkillsRequest) -> FullProfileOut:
        await self.db.execute(delete(PlayerRole).where(PlayerRole.user_id == user_id))
        self.db.add(PlayerRole(user_id=user_id, role=req.role))

        batting_result = await self.db.execute(select(BattingInfo).where(BattingInfo.user_id == user_id))
        batting = batting_result.scalar_one_or_none()
        if batting:
            batting.batting_style = req.batting_style
            batting.batting_order = req.batting_order
        else:
            self.db.add(BattingInfo(
                user_id=user_id,
                batting_style=req.batting_style,
                batting_order=req.batting_order,
            ))

        is_bowler_role = req.role in (2, 4)  # bowler or allrounder
        bowling_result = await self.db.execute(select(BowlingInfo).where(BowlingInfo.user_id == user_id))
        bowling = bowling_result.scalar_one_or_none()

        if is_bowler_role:
            bowling_category: Optional[int] = None
            if req.bowling_type is not None:
                bowling_category = 1 if req.bowling_type <= 3 else 2  # 1=pace, 2=spin

            if bowling:
                bowling.bowling_style = req.bowling_style
                bowling.bowling_category = bowling_category
                bowling.bowling_type = req.bowling_type
            else:
                self.db.add(BowlingInfo(
                    user_id=user_id,
                    bowling_style=req.bowling_style,
                    bowling_category=bowling_category,
                    bowling_type=req.bowling_type,
                ))
        else:
            if bowling:
                await self.db.delete(bowling)

        await self.db.commit()
        return await self.get_full_profile(user_id)

    # ------------------------------------------------------------------
    # Save profile image URL (called after photo upload)
    # ------------------------------------------------------------------

    async def save_profile_image(self, user_id: int, url: str) -> None:
        profile_result = await self.db.execute(select(Profile).where(Profile.user_id == user_id))
        profile = profile_result.scalar_one_or_none()
        if profile:
            profile.profile_image = url
        else:
            self.db.add(Profile(user_id=user_id, profile_image=url))
        await self.db.commit()
