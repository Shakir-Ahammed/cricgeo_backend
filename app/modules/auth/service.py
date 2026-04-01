"""
Auth service layer containing business logic for authentication
"""

from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, and_
from fastapi import HTTPException, status

from app.modules.users.model import User, UserStatus, AuthProvider
from app.modules.auth.model import RefreshToken, PasswordResetToken, EmailVerificationToken
from app.modules.auth.schema import (
    RegisterRequest, LoginRequest, TokenResponse, AuthResponse, RegisterResponse,
    RequestPasswordResetRequest, PasswordResetRequest, VerifyEmailRequest
)
from app.modules.users.schema import UserOut
from app.core.security import (
    hash_password, verify_password, create_access_token, create_refresh_token,
    decode_token, verify_token_type, generate_random_token, hash_token, verify_hashed_token
)
from app.core.config import settings
from app.helpers.utils import normalize_email

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
import json


class AuthService:
    """
    Service class for authentication operations
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def register_user(self, request: RegisterRequest, ip: Optional[str] = None, device: Optional[str] = None) -> RegisterResponse:
        """
        Register a new user and send email verification token
        User must verify email before logging in
        """
        email = normalize_email(request.email)
        
        existing_user = await self._get_user_by_email(email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        hashed_password = hash_password(request.password)
        
        new_user = User(
            name=request.name,
            email=email,
            phone=request.phone,
            hashed_password=hashed_password,
            is_email_verified=False,
            status=UserStatus.INACTIVE
        )
        
        self.db.add(new_user)
        await self.db.commit()
        await self.db.refresh(new_user)
        
        # Generate and send email verification token
        verification_token = await self._create_email_verification_token(new_user.id)
        
        from app.core.mailer import email_service
        try:
            await email_service.send_verification_email(
                to_email=new_user.email,
                to_name=new_user.name,
                token=verification_token
            )
        except Exception as e:
            print(f"❌ Failed to send verification email: {e}")
        
        # Do NOT generate auth tokens - user must verify email first
        # tokens = await self._generate_tokens(new_user, ip, device)
        
        # Convert user to dict to avoid lazy loading issues
        user_dict = {
            "id": new_user.id,
            "name": new_user.name,
            "email": new_user.email,
            "phone": new_user.phone,
            "plan": new_user.plan,
            "user_type": new_user.user_type,
            "is_email_verified": new_user.is_email_verified,
            "status": new_user.status,
            "last_login_at": new_user.last_login_at,
            "created_at": new_user.created_at,
            "updated_at": new_user.updated_at
        }
        user_out = UserOut(**user_dict)
        
        return RegisterResponse(
            message="Registration successful! Please check your email to verify your account.",
            user=user_out
        )
    
    async def login_user(self, request: LoginRequest, ip: Optional[str] = None) -> AuthResponse:
        """
        Authenticate user and return tokens
        """
        email = normalize_email(request.email)
        
        user = await self._get_user_by_email(email)
        if not user or user.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        if not user.is_email_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email not verified. Please check your email for verification link."
            )
        
        if user.status != UserStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive"
            )
        
        if not verify_password(request.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Update last login
        user.last_login_at = datetime.utcnow()
        await self.db.commit()  # Commit to ensure updated_at is set by DB
        await self.db.refresh(user)  # Refresh to load all attributes eagerly
        
        tokens = await self._generate_tokens(user, ip, request.device)
        
        # Convert user to dict to avoid lazy loading issues
        user_dict = {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "phone": user.phone,
            "plan": user.plan,
            "user_type": user.user_type,
            "is_email_verified": user.is_email_verified,
            "status": user.status,
            "last_login_at": user.last_login_at,
            "created_at": user.created_at,
            "updated_at": user.updated_at
        }
        user_out = UserOut(**user_dict)
        
        return AuthResponse(user=user_out, tokens=tokens)
    
    async def refresh_access_token(self, refresh_token: str, ip: Optional[str] = None, device: Optional[str] = None) -> TokenResponse:
        """
        Generate new access token using refresh token
        """
        token_hash = hash_token(refresh_token)
        
        # Verify token exists in DB and not expired
        result = await self.db.execute(
            select(RefreshToken).where(
                and_(
                    RefreshToken.token_hash == token_hash,
                    RefreshToken.expires_at > datetime.utcnow()
                )
            )
        )
        stored_token = result.scalar_one_or_none()
        
        if not stored_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token"
            )
        
        user = await self._get_user_by_id(stored_token.user_id)
        if not user or user.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        if user.status != UserStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive"
            )
        
        # Delete old refresh token (rotation)
        await self.db.delete(stored_token)
        
        # Generate new tokens
        tokens = await self._generate_tokens(user, ip, device)
        
        return tokens
    
    async def verify_email(self, request: VerifyEmailRequest) -> UserOut:
        """
        Verify user email with token
        """
        token_hash = hash_token(request.token)
        
        result = await self.db.execute(
            select(EmailVerificationToken).where(
                and_(
                    EmailVerificationToken.token_hash == token_hash,
                    EmailVerificationToken.expires_at > datetime.utcnow(),
                    EmailVerificationToken.used_at.is_(None)
                )
            )
        )
        token_record = result.scalar_one_or_none()
        
        if not token_record:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired verification token"
            )
        
        user = await self._get_user_by_id(token_record.user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        if user.is_email_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already verified"
            )
        
        user.is_email_verified = True
        user.status = UserStatus.ACTIVE
        token_record.used_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(user)
        
        user_dict = {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "phone": user.phone,
            "plan": user.plan,
            "user_type": user.user_type,
            "is_email_verified": user.is_email_verified,
            "status": user.status,
            "last_login_at": user.last_login_at,
            "created_at": user.created_at,
            "updated_at": user.updated_at
        }
        
        return UserOut(**user_dict)
    
    async def request_password_reset(self, request: RequestPasswordResetRequest) -> str:
        """
        Create password reset token and return it (for email sending)
        """
        email = normalize_email(request.email)
        user = await self._get_user_by_email(email)
        
        if not user or user.deleted_at is not None:
            # Don't reveal if email exists
            return "If email exists, reset link will be sent"
        
        # Delete old unused tokens for this user
        await self.db.execute(
            delete(PasswordResetToken).where(
                and_(
                    PasswordResetToken.user_id == user.id,
                    PasswordResetToken.used_at.is_(None)
                )
            )
        )
        
        reset_token = generate_random_token()
        token_hash = hash_token(reset_token)
        expires_at = datetime.utcnow() + timedelta(hours=1)
        
        token_record = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            created_by=user.id
        )
        
        self.db.add(token_record)
        await self.db.commit()
        
        from app.core.mailer import email_service
        try:
            await email_service.send_password_reset_email(
                to_email=user.email,
                to_name=user.name,
                token=reset_token
            )
        except Exception as e:
            print(f"❌ Failed to send password reset email: {e}")
        
        return "If email exists, reset link will be sent"
    
    async def reset_password(self, request: PasswordResetRequest) -> str:
        """
        Reset user password with token
        """
        token_hash = hash_token(request.token)
        
        result = await self.db.execute(
            select(PasswordResetToken).where(
                and_(
                    PasswordResetToken.token_hash == token_hash,
                    PasswordResetToken.expires_at > datetime.utcnow(),
                    PasswordResetToken.used_at.is_(None)
                )
            )
        )
        token_record = result.scalar_one_or_none()
        
        if not token_record:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token"
            )
        
        user = await self._get_user_by_id(token_record.user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user.hashed_password = hash_password(request.new_password)
        token_record.used_at = datetime.utcnow()
        
        # Revoke all refresh tokens for security
        await self.db.execute(
            delete(RefreshToken).where(RefreshToken.user_id == user.id)
        )
        
        await self.db.flush()
        
        return "Password reset successfully"
    
    async def _get_user_by_email(self, email: str) -> Optional[User]:
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()
    
    async def _get_user_by_id(self, user_id: int) -> Optional[User]:
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def _generate_tokens(self, user: User, ip: Optional[str] = None, device: Optional[str] = None) -> TokenResponse:
        """
        Generate access and refresh tokens, store refresh token hash in DB
        """
        token_data = {
            "user_id": user.id,
            "email": user.email
        }
        
        access_token = create_access_token(token_data)
        refresh_token_raw = generate_random_token(32)
        refresh_token_hash = hash_token(refresh_token_raw)
        
        expires_at = datetime.utcnow() + timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
        
        refresh_token_record = RefreshToken(
            user_id=user.id,
            token_hash=refresh_token_hash,
            expires_at=expires_at,
            ip=ip,
            device=device,
            created_by=user.id
        )
        
        self.db.add(refresh_token_record)
        await self.db.flush()
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token_raw,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
    
    async def _create_email_verification_token(self, user_id: int) -> str:
        """
        Create email verification token
        """
        verification_token = generate_random_token()
        token_hash = hash_token(verification_token)
        expires_at = datetime.utcnow() + timedelta(hours=24)
        
        token_record = EmailVerificationToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            created_by=user_id
        )
        
        self.db.add(token_record)
        await self.db.flush()
        
        return verification_token
    
    def generate_google_login_url(self) -> str:
        """
        Generate Google OAuth2 authorization URL
        """
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [settings.GOOGLE_REDIRECT_URI]
                }
            },
            scopes=[
                "openid",
                "https://www.googleapis.com/auth/userinfo.email",
                "https://www.googleapis.com/auth/userinfo.profile"
            ],
            redirect_uri=settings.GOOGLE_REDIRECT_URI
        )
        
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        
        return authorization_url
    
    async def google_callback(self, code: str, ip: Optional[str] = None, device: Optional[str] = None) -> AuthResponse:
        """
        Handle Google OAuth2 callback, exchange code for tokens,
        create/find user, and return JWT tokens
        """
        # Exchange authorization code for tokens
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [settings.GOOGLE_REDIRECT_URI]
                }
            },
            scopes=[
                "openid",
                "https://www.googleapis.com/auth/userinfo.email",
                "https://www.googleapis.com/auth/userinfo.profile"
            ],
            redirect_uri=settings.GOOGLE_REDIRECT_URI
        )
        
        try:
            flow.fetch_token(code=code)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to fetch Google tokens: {str(e)}"
            )
        
        credentials = flow.credentials
        
        # Verify and decode the ID token
        try:
            idinfo = id_token.verify_oauth2_token(
                credentials.id_token,
                google_requests.Request(),
                settings.GOOGLE_CLIENT_ID
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to verify Google token: {str(e)}"
            )
        
        # Extract user information
        google_user_id = idinfo.get("sub")
        email = normalize_email(idinfo.get("email"))
        name = idinfo.get("name")
        email_verified = idinfo.get("email_verified", False)
        
        if not email or not google_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to get user information from Google"
            )
        
        # Find or create user
        user = await self._find_or_create_google_user(
            email=email,
            name=name,
            google_user_id=google_user_id,
            email_verified=email_verified
        )
        
        # Update last login
        user.last_login_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(user)
        
        # Generate tokens
        tokens = await self._generate_tokens(user, ip, device)
        
        # Convert user to dict to avoid lazy loading issues
        user_dict = {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "phone": user.phone,
            "plan": user.plan,
            "user_type": user.user_type,
            "is_email_verified": user.is_email_verified,
            "status": user.status,
            "last_login_at": user.last_login_at,
            "created_at": user.created_at,
            "updated_at": user.updated_at
        }
        user_out = UserOut(**user_dict)
        
        return AuthResponse(user=user_out, tokens=tokens)
    
    async def _find_or_create_google_user(
        self,
        email: str,
        name: str,
        google_user_id: str,
        email_verified: bool
    ) -> User:
        """
        Find existing user by Google ID or email, or create new user
        """
        # First, try to find by provider_user_id
        result = await self.db.execute(
            select(User).where(
                and_(
                    User.provider == AuthProvider.GOOGLE,
                    User.provider_user_id == google_user_id
                )
            )
        )
        user = result.scalar_one_or_none()
        
        if user:
            return user
        
        # Try to find by email (could be existing LOCAL user)
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()
        
        if user:
            # Link existing account with Google
            user.provider = AuthProvider.GOOGLE
            user.provider_user_id = google_user_id
            if email_verified and not user.is_email_verified:
                user.is_email_verified = True
                user.status = UserStatus.ACTIVE
            await self.db.commit()
            await self.db.refresh(user)
            return user
        
        # Create new user
        new_user = User(
            name=name or "Google User",
            email=email,
            provider=AuthProvider.GOOGLE,
            provider_user_id=google_user_id,
            is_email_verified=email_verified,
            status=UserStatus.ACTIVE,
            hashed_password=None  # No password for OAuth users
        )
        
        self.db.add(new_user)
        await self.db.commit()
        await self.db.refresh(new_user)
        
        return new_user
