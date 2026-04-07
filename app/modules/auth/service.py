"""
Auth service layer containing business logic for OTP and Google authentication.
"""

from typing import Optional
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, and_
from fastapi import HTTPException, status

from app.modules.users.model import User, UserStatus, AuthProvider, Gender
from app.modules.auth.model import OTP
from app.modules.auth.schema import (
    TokenResponse,
    AuthResponse,
    RequestOTPRequest,
    RequestOTPResponse,
    VerifyOTPRequest,
    VerifyOTPResponse,
    CompleteProfileRequest,
    CompleteProfileResponse,
)
from app.modules.users.schema import UserOut
from app.core.security import create_access_token, hash_token
from app.core.config import settings
from app.helpers.utils import normalize_email, generate_otp

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow


class AuthService:
    """
    Service class for OTP and Google-based authentication operations.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_user_by_email(self, email: str) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def _get_user_by_id(self, user_id: int) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    def _build_access_token(self, user: User) -> TokenResponse:
        access_token = create_access_token({"user_id": user.id, "email": user.email})
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    def generate_google_login_url(self) -> str:
        """
        Generate Google OAuth2 authorization URL.
        """
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
                }
            },
            scopes=[
                "openid",
                "https://www.googleapis.com/auth/userinfo.email",
                "https://www.googleapis.com/auth/userinfo.profile",
            ],
            redirect_uri=settings.GOOGLE_REDIRECT_URI,
        )

        authorization_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )
        return authorization_url

    async def google_callback(self, code: str, ip: Optional[str] = None, device: Optional[str] = None) -> AuthResponse:
        """
        Handle Google OAuth callback, find/create user, and return access token.
        """
        del ip, device

        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
                }
            },
            scopes=[
                "openid",
                "https://www.googleapis.com/auth/userinfo.email",
                "https://www.googleapis.com/auth/userinfo.profile",
            ],
            redirect_uri=settings.GOOGLE_REDIRECT_URI,
        )

        try:
            flow.fetch_token(code=code)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to fetch Google tokens: {str(e)}",
            )

        credentials = flow.credentials

        try:
            idinfo = id_token.verify_oauth2_token(
                credentials.id_token,
                google_requests.Request(),
                settings.GOOGLE_CLIENT_ID,
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to verify Google token: {str(e)}",
            )

        google_user_id = idinfo.get("sub")
        email = normalize_email(idinfo.get("email"))
        name = idinfo.get("name")
        email_verified = idinfo.get("email_verified", False)

        if not email or not google_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to get user information from Google",
            )

        user = await self._find_or_create_google_user(
            email=email,
            name=name,
            google_user_id=google_user_id,
            email_verified=email_verified,
        )

        user.last_login_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(user)

        user_out = UserOut(
            id=user.id,
            name=user.name,
            email=user.email,
            phone=user.phone,
            gender=user.gender,
            profile_image=user.profile_image,
            plan=user.plan,
            user_type=user.user_type,
            is_email_verified=user.is_email_verified,
            profile_completed=user.profile_completed,
            status=user.status,
            last_login_at=user.last_login_at,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

        return AuthResponse(user=user_out, tokens=self._build_access_token(user))

    async def _find_or_create_google_user(
        self,
        email: str,
        name: str,
        google_user_id: str,
        email_verified: bool,
    ) -> User:
        """
        Find existing user by Google ID or email, otherwise create a new user.
        """
        result = await self.db.execute(
            select(User).where(
                and_(
                    User.provider == AuthProvider.GOOGLE,
                    User.provider_user_id == google_user_id,
                )
            )
        )
        user = result.scalar_one_or_none()
        if user:
            return user

        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user:
            user.provider = AuthProvider.GOOGLE
            user.provider_user_id = google_user_id
            if email_verified and not user.is_email_verified:
                user.is_email_verified = True
                user.status = UserStatus.ACTIVE
            await self.db.commit()
            await self.db.refresh(user)
            return user

        new_user = User(
            name=name or "Google User",
            email=email,
            provider=AuthProvider.GOOGLE,
            provider_user_id=google_user_id,
            is_email_verified=email_verified,
            status=UserStatus.ACTIVE,
            profile_completed=bool(name),
            hashed_password=None,
        )
        self.db.add(new_user)
        await self.db.commit()
        await self.db.refresh(new_user)
        return new_user

    async def request_otp(self, request: RequestOTPRequest) -> RequestOTPResponse:
        """
        Generate and send OTP to email.
        Rate limit: max 3 requests per minute per email.
        """
        email = normalize_email(request.email)

        one_minute_ago = datetime.utcnow() - timedelta(minutes=1)
        result = await self.db.execute(
            select(OTP).where(and_(OTP.identifier == email, OTP.created_at > one_minute_ago))
        )
        recent_otps = result.scalars().all()
        if len(recent_otps) >= 3:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many OTP requests. Please wait a minute before trying again.",
            )

        await self.db.execute(delete(OTP).where(OTP.identifier == email))

        otp_code = generate_otp(6)
        otp_hash = hash_token(otp_code)
        expires_at = datetime.utcnow() + timedelta(minutes=5)

        self.db.add(OTP(identifier=email, code_hash=otp_hash, expires_at=expires_at, attempts=0))
        await self.db.commit()

        from app.core.mailer import email_service

        try:
            await email_service.send_otp_email(to_email=email, otp_code=otp_code)
        except Exception as e:
            print(f"Failed to send OTP email: {e}")

        return RequestOTPResponse(
            message="OTP sent to your email. Valid for 5 minutes.",
            email=email,
        )

    async def verify_otp(
        self,
        request: VerifyOTPRequest,
        ip: Optional[str] = None,
        device: Optional[str] = None,
    ) -> VerifyOTPResponse:
        """
        Verify OTP and authenticate user.
        Existing user: login.
        New user: create minimal user and return is_new_user=true.
        """
        del ip, device

        email = normalize_email(request.email)

        result = await self.db.execute(
            select(OTP)
            .where(and_(OTP.identifier == email, OTP.expires_at > datetime.utcnow()))
            .order_by(OTP.created_at.desc())
        )
        otp_record = result.scalar_one_or_none()

        if not otp_record:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP")

        if otp_record.attempts >= 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum OTP verification attempts exceeded. Please request a new OTP.",
            )

        otp_hash = hash_token(request.otp)
        if otp_hash != otp_record.code_hash:
            otp_record.attempts += 1
            await self.db.commit()
            remaining_attempts = max(0, 5 - otp_record.attempts)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid OTP. {remaining_attempts} attempts remaining.",
            )

        await self.db.delete(otp_record)
        await self.db.commit()

        user = await self._get_user_by_email(email)
        is_new_user = False

        if not user:
            is_new_user = True
            user = User(
                email=email,
                is_email_verified=True,
                status=UserStatus.ACTIVE,
                profile_completed=False,
                hashed_password=None,
                provider=AuthProvider.LOCAL,
            )
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)
        else:
            if not user.is_email_verified:
                user.is_email_verified = True
                user.status = UserStatus.ACTIVE
            user.last_login_at = datetime.utcnow()
            await self.db.commit()
            await self.db.refresh(user)

        access_token = create_access_token({"user_id": user.id, "email": user.email})
        return VerifyOTPResponse(
            access_token=access_token,
            is_new_user=is_new_user,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def complete_profile(self, user_id: int, request: CompleteProfileRequest) -> CompleteProfileResponse:
        """
        Complete user profile after OTP registration.
        """
        user = await self._get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        if user.profile_completed:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Profile already completed")

        try:
            gender_enum = Gender(request.gender.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid gender. Must be 'male', 'female', or 'other'",
            )

        user.name = request.name
        user.gender = gender_enum
        user.phone = request.phone
        user.profile_image = request.profile_image
        user.profile_completed = True

        await self.db.commit()
        await self.db.refresh(user)

        user_out = UserOut(
            id=user.id,
            name=user.name,
            email=user.email,
            phone=user.phone,
            gender=user.gender,
            profile_image=user.profile_image,
            plan=user.plan,
            user_type=user.user_type,
            is_email_verified=user.is_email_verified,
            profile_completed=user.profile_completed,
            status=user.status,
            last_login_at=user.last_login_at,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

        return CompleteProfileResponse(
            message="Profile completed successfully. Welcome!",
            user=user_out,
        )
