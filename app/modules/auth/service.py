"""
Auth service layer: OTP authentication, Google OAuth, session management.
"""

from typing import Optional, Tuple
from datetime import datetime, timedelta
from urllib.parse import urlencode, urlparse

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, and_, update
from fastapi import HTTPException, status
from jose import jwt, JWTError
import secrets

from app.modules.users.model import User
from app.modules.auth.model import OTP, UserAuthProvider, UserSession
from app.modules.auth.schema import (
    TokenResponse,
    AuthResponse,
    RequestOTPRequest,
    RequestOTPResponse,
    VerifyOTPRequest,
    VerifyOTPResponse,
    CompleteProfileRequest,
    CompleteProfileResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
)
from app.modules.users.schema import UserOut
from app.core.security import create_access_token, create_refresh_token, hash_token, decode_token, verify_token_type
from app.core.config import settings
from app.helpers.utils import normalize_email, normalize_phone, generate_otp

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow


class AuthService:

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Redirect URL validation
    # ------------------------------------------------------------------

    def _is_allowed_redirect_url(self, redirect_url: str) -> bool:
        parsed = urlparse(redirect_url)
        if parsed.scheme not in {"http", "https"}:
            return False
        allowed_hosts = {
            "localhost:8000", "127.0.0.1:8000", "0.0.0.0:8000",
            "localhost:3000", "127.0.0.1:3000",
        }
        frontend = urlparse(settings.FRONTEND_URL) if settings.FRONTEND_URL else None
        if frontend and frontend.netloc:
            allowed_hosts.add(frontend.netloc)
        return parsed.netloc in allowed_hosts

    # ------------------------------------------------------------------
    # Google OAuth state token
    # ------------------------------------------------------------------

    def _create_google_state_token(self, redirect_to: Optional[str] = None) -> str:
        payload = {
            "type": "google_oauth_state",
            "nonce": secrets.token_urlsafe(16),
            "exp": datetime.utcnow() + timedelta(minutes=10),
        }
        if redirect_to:
            if not self._is_allowed_redirect_url(redirect_to):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid redirect URL")
            payload["redirect_to"] = redirect_to
        return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

    def _parse_google_state_token(self, state_token: str) -> Optional[str]:
        try:
            payload = jwt.decode(state_token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        except JWTError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OAuth state")
        if payload.get("type") != "google_oauth_state":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state type")
        redirect_to = payload.get("redirect_to")
        if redirect_to and not self._is_allowed_redirect_url(redirect_to):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid redirect URL")
        return redirect_to

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------

    async def _get_user_by_email(self, email: str) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def _get_user_by_phone(self, phone: str) -> Optional[User]:
        phone_candidates = {phone, f"+{phone}"}
        if phone.startswith("880"):
            phone_candidates.add(f"0{phone[3:]}")
        result = await self.db.execute(select(User).where(User.phone.in_(list(phone_candidates))))
        return result.scalar_one_or_none()

    async def _get_user_by_id(self, user_id: int) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    def _user_out(self, user: User) -> UserOut:
        return UserOut(
            id=user.id,
            name=user.name,
            email=user.email,
            phone=user.phone,
            is_email_verified=user.is_email_verified,
            is_phone_verified=user.is_phone_verified,
            status=user.status,
            last_login_at=user.last_login_at,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    # ------------------------------------------------------------------
    # Session management (replaces RefreshToken)
    # ------------------------------------------------------------------

    async def _create_user_session(
        self,
        user_id: int,
        ip: Optional[str] = None,
        device: Optional[str] = None,
    ) -> Tuple[str, datetime]:
        refresh_token = create_refresh_token({"user_id": user_id})
        token_hash = hash_token(refresh_token)
        expires_at = datetime.utcnow() + timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)

        session = UserSession(
            user_id=user_id,
            refresh_token_hash=token_hash,
            expires_at=expires_at,
            device_info=device,
            ip_address=ip,
            is_revoked=False,
        )
        self.db.add(session)
        await self.db.commit()
        return refresh_token, expires_at

    async def _revoke_user_session(self, token_hash: str) -> None:
        await self.db.execute(
            update(UserSession)
            .where(UserSession.refresh_token_hash == token_hash)
            .values(is_revoked=True, revoked_at=datetime.utcnow())
        )
        await self.db.commit()

    async def _revoke_all_user_sessions(self, user_id: int) -> None:
        await self.db.execute(
            update(UserSession)
            .where(and_(UserSession.user_id == user_id, UserSession.is_revoked == False))
            .values(is_revoked=True, revoked_at=datetime.utcnow())
        )
        await self.db.commit()

    async def _validate_user_session(self, refresh_token: str) -> Tuple[UserSession, int]:
        payload = decode_token(refresh_token)
        if not payload:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")
        if not verify_token_type(payload, "refresh"):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

        token_hash = hash_token(refresh_token)
        result = await self.db.execute(
            select(UserSession).where(UserSession.refresh_token_hash == token_hash)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session not found")

        if session.is_revoked:
            await self._revoke_all_user_sessions(user_id)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token reuse detected. All sessions have been terminated for security.",
            )

        if session.expires_at < datetime.utcnow():
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

        return session, user_id

    # ------------------------------------------------------------------
    # Token response builder
    # ------------------------------------------------------------------

    def _build_token_response(self, user: User, refresh_token: str) -> TokenResponse:
        access_token = create_access_token({"user_id": user.id, "email": user.email})
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    # ------------------------------------------------------------------
    # Google OAuth
    # ------------------------------------------------------------------

    def _build_google_flow(self) -> Flow:
        return Flow.from_client_config(
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

    def generate_google_login_url(self, redirect_to: Optional[str] = None) -> str:
        flow = self._build_google_flow()
        state_token = self._create_google_state_token(redirect_to)
        authorization_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            state=state_token,
        )
        return authorization_url

    async def google_callback(
        self,
        code: str,
        state: str,
        ip: Optional[str] = None,
        device: Optional[str] = None,
    ) -> Tuple[AuthResponse, Optional[str]]:
        redirect_to = self._parse_google_state_token(state)

        flow = self._build_google_flow()
        try:
            flow.fetch_token(code=code)
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to fetch Google tokens: {e}")

        try:
            idinfo = id_token.verify_oauth2_token(
                flow.credentials.id_token,
                google_requests.Request(),
                settings.GOOGLE_CLIENT_ID,
            )
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to verify Google token: {e}")

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
            email=email, name=name, google_user_id=google_user_id, email_verified=email_verified
        )
        user.last_login_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(user)

        refresh_token, _ = await self._create_user_session(user.id, ip, device)
        auth_response = AuthResponse(user=self._user_out(user), tokens=self._build_token_response(user, refresh_token))
        return auth_response, redirect_to

    def build_google_callback_redirect_url(self, redirect_to: str, auth_response: AuthResponse) -> str:
        from urllib.parse import urlencode
        fragment_payload = {
            "access_token": auth_response.tokens.access_token,
            "refresh_token": auth_response.tokens.refresh_token,
            "token_type": auth_response.tokens.token_type,
            "expires_in": auth_response.tokens.expires_in,
            "email": auth_response.user.email,
            "user_id": auth_response.user.id,
        }
        return f"{redirect_to}#{urlencode(fragment_payload)}"

    async def _find_or_create_google_user(
        self,
        email: str,
        name: Optional[str],
        google_user_id: str,
        email_verified: bool,
    ) -> User:
        result = await self.db.execute(
            select(UserAuthProvider).where(
                and_(
                    UserAuthProvider.provider == "google",
                    UserAuthProvider.provider_user_id == google_user_id,
                )
            )
        )
        auth_provider = result.scalar_one_or_none()
        if auth_provider:
            user = await self._get_user_by_id(auth_provider.user_id)
            if user:
                return user

        user = await self._get_user_by_email(email)
        if user:
            self.db.add(UserAuthProvider(user_id=user.id, provider="google", provider_user_id=google_user_id))
            if email_verified and not user.is_email_verified:
                user.is_email_verified = True
            await self.db.commit()
            await self.db.refresh(user)
            return user

        new_user = User(name=name, email=email, is_email_verified=email_verified, status="active")
        self.db.add(new_user)
        await self.db.flush()
        self.db.add(UserAuthProvider(user_id=new_user.id, provider="google", provider_user_id=google_user_id))
        await self.db.commit()
        await self.db.refresh(new_user)
        return new_user

    # ------------------------------------------------------------------
    # OTP
    # ------------------------------------------------------------------

    async def request_otp(self, request: RequestOTPRequest) -> RequestOTPResponse:
        if request.email:
            channel = "email"
            identifier = normalize_email(request.email)
        else:
            channel = "sms"
            identifier = normalize_phone(request.phone or "")

        if not identifier:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid identifier provided")

        one_minute_ago = datetime.utcnow() - timedelta(minutes=1)
        result = await self.db.execute(
            select(OTP).where(and_(OTP.identifier == identifier, OTP.created_at > one_minute_ago))
        )
        if len(result.scalars().all()) >= 3:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many OTP requests. Please wait a minute before trying again.",
            )

        await self.db.execute(delete(OTP).where(OTP.identifier == identifier))

        user = (
            await self._get_user_by_email(identifier)
            if channel == "email"
            else await self._get_user_by_phone(identifier)
        )
        otp_type = "login" if user else "signup"

        otp_code = generate_otp(6)
        otp_hash = hash_token(otp_code)
        expires_at = datetime.utcnow() + timedelta(minutes=5)

        self.db.add(
            OTP(
                user_id=user.id if user else None,
                identifier=identifier,
                code_hash=otp_hash,
                type=otp_type,
                expires_at=expires_at,
                attempts=0,
            )
        )

        try:
            if channel == "email":
                from app.core.mailer import email_service
                sent = await email_service.send_otp_email(to_email=identifier, otp_code=otp_code)
                if not sent:
                    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Unable to send OTP email")
            else:
                from app.core.sms import sms_service
                sent = await sms_service.send_otp_sms(phone=identifier, otp_code=otp_code)
                if not sent:
                    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Unable to send OTP SMS")
            await self.db.commit()
        except HTTPException:
            await self.db.execute(delete(OTP).where(OTP.identifier == identifier))
            await self.db.commit()
            raise
        except Exception as e:
            await self.db.execute(delete(OTP).where(OTP.identifier == identifier))
            await self.db.commit()
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Failed to send OTP: {e}")

        return RequestOTPResponse(
            message=f"OTP sent via {channel}. Valid for 5 minutes.",
            channel=channel,
            identifier=identifier,
            otp_type=otp_type,
        )

    async def verify_otp(
        self,
        request: VerifyOTPRequest,
        ip: Optional[str] = None,
        device: Optional[str] = None,
    ) -> VerifyOTPResponse:
        using_email = bool(request.email)
        identifier = normalize_email(request.email or "") if using_email else normalize_phone(request.phone or "")

        if not identifier:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid identifier provided")

        result = await self.db.execute(
            select(OTP)
            .where(and_(OTP.identifier == identifier, OTP.expires_at > datetime.utcnow()))
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

        if hash_token(request.otp) != otp_record.code_hash:
            otp_record.attempts += 1
            await self.db.commit()
            remaining = max(0, 5 - otp_record.attempts)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid OTP. {remaining} attempts remaining.",
            )

        await self.db.delete(otp_record)
        await self.db.commit()

        user = await self._get_user_by_email(identifier) if using_email else await self._get_user_by_phone(identifier)
        is_new_user = False

        if not user:
            is_new_user = True
            user = User(
                email=identifier if using_email else None,
                phone=None if using_email else identifier,
                is_email_verified=using_email,
                is_phone_verified=not using_email,
                status="active",
            )
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)
        else:
            if using_email and not user.is_email_verified:
                user.is_email_verified = True
            if not using_email and not user.is_phone_verified:
                user.is_phone_verified = True
            user.last_login_at = datetime.utcnow()
            await self.db.commit()
            await self.db.refresh(user)

        access_token = create_access_token({"user_id": user.id, "email": user.email})
        refresh_token, _ = await self._create_user_session(user.id, ip, device)

        return VerifyOTPResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            is_new_user=is_new_user,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def complete_profile(self, user_id: int, request: CompleteProfileRequest) -> CompleteProfileResponse:
        from app.modules.profiles.model import Profile

        user = await self._get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        user.name = request.name
        await self.db.flush()

        result = await self.db.execute(select(Profile).where(Profile.user_id == user_id))
        profile = result.scalar_one_or_none()

        if profile:
            profile.gender = request.gender
            profile.date_of_birth = request.date_of_birth
            profile.country_id = request.country_id
            profile.city_id = request.city_id
            profile.profile_image = request.profile_image
            profile.bio = request.bio
        else:
            self.db.add(
                Profile(
                    user_id=user_id,
                    gender=request.gender,
                    date_of_birth=request.date_of_birth,
                    country_id=request.country_id,
                    city_id=request.city_id,
                    profile_image=request.profile_image,
                    bio=request.bio,
                )
            )

        await self.db.commit()
        await self.db.refresh(user)

        return CompleteProfileResponse(message="Profile completed successfully.", user=self._user_out(user))

    # ------------------------------------------------------------------
    # Token refresh / logout
    # ------------------------------------------------------------------

    async def refresh_access_token(
        self,
        request: RefreshTokenRequest,
        ip: Optional[str] = None,
        device: Optional[str] = None,
    ) -> RefreshTokenResponse:
        session, user_id = await self._validate_user_session(request.refresh_token)

        user = await self._get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        await self._revoke_user_session(session.refresh_token_hash)

        new_access_token = create_access_token({"user_id": user.id, "email": user.email})
        new_refresh_token, _ = await self._create_user_session(user.id, ip, device)

        return RefreshTokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def logout(self, refresh_token: str) -> str:
        session, _ = await self._validate_user_session(refresh_token)
        await self._revoke_user_session(session.refresh_token_hash)
        return "Logged out successfully"

    async def logout_all(self, user_id: int) -> str:
        await self._revoke_all_user_sessions(user_id)
        return "Logged out from all devices successfully"
