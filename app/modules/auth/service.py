"""
Auth service layer containing business logic for OTP, Google authentication, and refresh tokens.
"""

from typing import Optional, Tuple
from datetime import datetime, timedelta
from urllib.parse import urlencode, urlparse

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, and_, update
from fastapi import HTTPException, status
from jose import jwt, JWTError
import secrets

from app.modules.users.model import User, UserStatus, AuthProvider, Gender
from app.modules.auth.model import OTP, RefreshToken
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
    """
    Service class for OTP and Google-based authentication operations.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    def _is_allowed_redirect_url(self, redirect_url: str) -> bool:
        """
        Allow redirects only to known frontend hosts to avoid open-redirect abuse.
        """
        parsed = urlparse(redirect_url)
        if parsed.scheme not in {"http", "https"}:
            return False

        allowed_hosts = {
            "localhost:8000",
            "127.0.0.1:8000",
            "localhost:3000",
            "127.0.0.1:3000",
        }

        frontend = urlparse(settings.FRONTEND_URL) if settings.FRONTEND_URL else None
        if frontend and frontend.netloc:
            allowed_hosts.add(frontend.netloc)

        return parsed.netloc in allowed_hosts

    def _create_google_state_token(self, redirect_to: Optional[str] = None) -> str:
        """
        Create a signed short-lived state token for Google OAuth callback validation.
        """
        payload = {
            "type": "google_oauth_state",
            "nonce": secrets.token_urlsafe(16),
            "exp": datetime.utcnow() + timedelta(minutes=10),
        }

        if redirect_to:
            if not self._is_allowed_redirect_url(redirect_to):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid redirect URL",
                )
            payload["redirect_to"] = redirect_to

        return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

    def _parse_google_state_token(self, state_token: str) -> Optional[str]:
        """
        Validate OAuth state token and return redirect URL if it exists.
        """
        try:
            payload = jwt.decode(
                state_token,
                settings.JWT_SECRET,
                algorithms=[settings.JWT_ALGORITHM],
            )
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired OAuth state",
            )

        if payload.get("type") != "google_oauth_state":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid OAuth state type",
            )

        redirect_to = payload.get("redirect_to")
        if redirect_to and not self._is_allowed_redirect_url(redirect_to):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid redirect URL",
            )

        return redirect_to

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

    async def _create_refresh_token(
        self,
        user_id: int,
        ip: Optional[str] = None,
        device: Optional[str] = None
    ) -> Tuple[str, datetime]:
        """
        Create and store a new refresh token for the user.
        
        Returns:
            Tuple of (refresh_token, expires_at)
        """
        # Generate refresh token
        refresh_token = create_refresh_token({"user_id": user_id})
        
        # Hash token for storage
        token_hash = hash_token(refresh_token)
        
        # Calculate expiry
        expires_at = datetime.utcnow() + timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
        
        # Store in database
        db_token = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            device_info=device,
            ip_address=ip,
            is_revoked=False
        )
        self.db.add(db_token)
        await self.db.commit()
        
        return refresh_token, expires_at

    async def _revoke_refresh_token(self, token_hash: str) -> None:
        """
        Revoke a specific refresh token.
        """
        await self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.token_hash == token_hash)
            .values(is_revoked=True, revoked_at=datetime.utcnow())
        )
        await self.db.commit()

    async def _revoke_all_user_tokens(self, user_id: int) -> None:
        """
        Revoke all refresh tokens for a user (force logout from all devices).
        """
        await self.db.execute(
            update(RefreshToken)
            .where(and_(RefreshToken.user_id == user_id, RefreshToken.is_revoked == False))
            .values(is_revoked=True, revoked_at=datetime.utcnow())
        )
        await self.db.commit()

    async def _validate_refresh_token(self, refresh_token: str) -> Tuple[RefreshToken, int]:
        """
        Validate refresh token and return the database record and user_id.
        
        Implements reuse detection: if a revoked token is used, revoke all user tokens.
        
        Returns:
            Tuple of (RefreshToken record, user_id)
            
        Raises:
            HTTPException: If token is invalid, expired, or revoked
        """
        # Decode JWT
        payload = decode_token(refresh_token)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token"
            )
        
        # Verify token type
        if not verify_token_type(payload, "refresh"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
        
        # Hash token to look up in database
        token_hash = hash_token(refresh_token)
        
        # Find token in database
        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        db_token = result.scalar_one_or_none()
        
        if not db_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token not found"
            )
        
        # REUSE DETECTION: If token is already revoked, assume token theft
        if db_token.is_revoked:
            # Revoke ALL tokens for this user (force logout from all devices)
            await self._revoke_all_user_tokens(user_id)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token reuse detected. All sessions have been terminated for security."
            )
        
        # Check expiry
        if db_token.expires_at < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token expired"
            )
        
        return db_token, user_id

    def _build_token_response(
        self,
        user: User,
        refresh_token: str
    ) -> TokenResponse:
        """
        Build token response with access token and refresh token.
        """
        access_token = create_access_token({"user_id": user.id, "email": user.email})
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    def generate_google_login_url(self, redirect_to: Optional[str] = None) -> str:
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
        """
        Handle Google OAuth callback, find/create user, and return access token.
        """
        redirect_to = self._parse_google_state_token(state)

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

        # Create refresh token
        refresh_token, _ = await self._create_refresh_token(user.id, ip, device)

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

        auth_response = AuthResponse(user=user_out, tokens=self._build_token_response(user, refresh_token))
        return auth_response, redirect_to

    def build_google_callback_redirect_url(self, redirect_to: str, auth_response: AuthResponse) -> str:
        """
        Build redirect URL for browser-based OAuth test flow.
        Tokens are sent in URL fragment so they are not sent back to the server.
        """
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
        Generate and send OTP to email or phone.
        Rate limit: max 3 requests per minute per identifier.
        """
        if request.email:
            channel = "email"
            identifier = normalize_email(request.email)
        else:
            channel = "sms"
            identifier = normalize_phone(request.phone or "")

        if not identifier:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid identifier provided",
            )

        one_minute_ago = datetime.utcnow() - timedelta(minutes=1)
        result = await self.db.execute(
            select(OTP).where(and_(OTP.identifier == identifier, OTP.created_at > one_minute_ago))
        )
        recent_otps = result.scalars().all()
        if len(recent_otps) >= 3:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many OTP requests. Please wait a minute before trying again.",
            )

        await self.db.execute(delete(OTP).where(OTP.identifier == identifier))

        otp_code = generate_otp(6)
        otp_hash = hash_token(otp_code)
        expires_at = datetime.utcnow() + timedelta(minutes=5)

        self.db.add(OTP(identifier=identifier, code_hash=otp_hash, expires_at=expires_at, attempts=0))
        await self.db.commit()

        try:
            if channel == "email":
                from app.core.mailer import email_service

                sent = await email_service.send_otp_email(to_email=identifier, otp_code=otp_code)
                if not sent:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Unable to send OTP email at the moment",
                    )
            else:
                from app.core.sms import sms_service

                sent = await sms_service.send_otp_sms(phone=identifier, otp_code=otp_code)
                if not sent:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Unable to send OTP SMS at the moment",
                    )
        except HTTPException:
            # Remove unsent OTP so user can retry immediately.
            await self.db.execute(delete(OTP).where(OTP.identifier == identifier))
            await self.db.commit()
            raise
        except Exception as e:
            await self.db.execute(delete(OTP).where(OTP.identifier == identifier))
            await self.db.commit()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to send OTP: {e}",
            )

        return RequestOTPResponse(
            message=f"OTP sent via {channel}. Valid for 5 minutes.",
            channel=channel,
            identifier=identifier,
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
        Issues both access token and refresh token.
        """
        using_email = bool(request.email)
        if using_email:
            identifier = normalize_email(request.email or "")
        else:
            identifier = normalize_phone(request.phone or "")

        if not identifier:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid identifier provided",
            )

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

        user = await self._get_user_by_email(identifier) if using_email else await self._get_user_by_phone(identifier)
        is_new_user = False

        if not user:
            is_new_user = True
            generated_email = identifier if using_email else f"sms_{identifier}@sms.local"
            user = User(
                email=generated_email,
                phone=None if using_email else identifier,
                is_email_verified=using_email,
                status=UserStatus.ACTIVE,
                profile_completed=False,
                hashed_password=None,
                provider=AuthProvider.LOCAL,
            )
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)
        else:
            if using_email and not user.is_email_verified:
                user.is_email_verified = True
                user.status = UserStatus.ACTIVE
            if not using_email and not user.phone:
                user.phone = identifier
            user.last_login_at = datetime.utcnow()
            await self.db.commit()
            await self.db.refresh(user)

        # Create both access and refresh tokens
        access_token = create_access_token({"user_id": user.id, "email": user.email})
        refresh_token, _ = await self._create_refresh_token(user.id, ip, device)
        
        return VerifyOTPResponse(
            access_token=access_token,
            refresh_token=refresh_token,
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


    async def refresh_access_token(
        self,
        request: RefreshTokenRequest,
        ip: Optional[str] = None,
        device: Optional[str] = None,
    ) -> RefreshTokenResponse:
        """
        Refresh access token using refresh token.
        Implements token rotation: generates new access + refresh tokens, revokes old refresh token.
        
        Security: Detects token reuse and revokes all user sessions if a revoked token is used.
        """
        # Validate refresh token (includes reuse detection)
        db_token, user_id = await self._validate_refresh_token(request.refresh_token)
        
        # Get user
        user = await self._get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # TOKEN ROTATION: Revoke old refresh token
        await self._revoke_refresh_token(db_token.token_hash)
        
        # Generate new tokens
        new_access_token = create_access_token({"user_id": user.id, "email": user.email})
        new_refresh_token, _ = await self._create_refresh_token(user.id, ip, device)
        
        return RefreshTokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def logout(self, refresh_token: str) -> str:
        """
        Logout from current device by revoking the refresh token.
        """
        # Validate and get token
        db_token, _ = await self._validate_refresh_token(refresh_token)
        
        # Revoke the token
        await self._revoke_refresh_token(db_token.token_hash)
        
        return "Logged out successfully"

    async def logout_all(self, user_id: int) -> str:
        """
        Logout from all devices by revoking all refresh tokens for the user.
        """
        await self._revoke_all_user_tokens(user_id)
        return "Logged out from all devices successfully"
