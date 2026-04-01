"""
Auth controller handling HTTP requests/responses
"""

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any

from app.core.db import get_db
from app.modules.auth.service import AuthService
from app.modules.auth.schema import (
    RegisterRequest, LoginRequest, RefreshTokenRequest,
    VerifyEmailRequest, RequestPasswordResetRequest, PasswordResetRequest,
    GoogleCallbackRequest
)


class AuthController:
    """
    Controller for auth endpoints
    """
    
    @staticmethod
    async def register(
        request_body: RegisterRequest,
        req: Request,
        db: AsyncSession = Depends(get_db)
    ) -> Dict[str, Any]:
        service = AuthService(db)
        ip = req.client.host if req.client else None
        device = req.headers.get("User-Agent")
        
        register_response = await service.register_user(request_body, ip, device)
        
        return {
            "success": True,
            "message": register_response.message,
            "data": {"user": register_response.user.model_dump()}
        }
    
    @staticmethod
    async def login(
        request_body: LoginRequest,
        req: Request,
        db: AsyncSession = Depends(get_db)
    ) -> Dict[str, Any]:
        service = AuthService(db)
        ip = req.client.host if req.client else None
        
        auth_response = await service.login_user(request_body, ip)
        
        return {
            "success": True,
            "message": "Login successful",
            "data": auth_response.model_dump()
        }
    
    @staticmethod
    async def refresh_token(
        request_body: RefreshTokenRequest,
        req: Request,
        db: AsyncSession = Depends(get_db)
    ) -> Dict[str, Any]:
        service = AuthService(db)
        ip = req.client.host if req.client else None
        device = req.headers.get("User-Agent")
        
        token_response = await service.refresh_access_token(
            request_body.refresh_token, ip, device
        )
        
        return {
            "success": True,
            "message": "Token refreshed successfully",
            "data": token_response.model_dump()
        }
    
    @staticmethod
    async def verify_email(
        request_body: VerifyEmailRequest,
        db: AsyncSession = Depends(get_db)
    ) -> Dict[str, Any]:
        service = AuthService(db)
        user = await service.verify_email(request_body)
        
        return {
            "success": True,
            "message": "Email verified successfully",
            "data": user.model_dump()
        }
    
    @staticmethod
    async def verify_email_get(
        token: str,
        db: AsyncSession = Depends(get_db)
    ) -> Dict[str, Any]:
        """
        Verify email via GET request (for direct email links)
        """
        service = AuthService(db)
        request_body = VerifyEmailRequest(token=token)
        user = await service.verify_email(request_body)
        
        return {
            "success": True,
            "message": "Email verified successfully! You can now login.",
            "data": {
                "email": user.email,
                "name": user.name,
                "verified": True
            }
        }
    
    @staticmethod
    async def request_password_reset(
        request_body: RequestPasswordResetRequest,
        db: AsyncSession = Depends(get_db)
    ) -> Dict[str, Any]:
        service = AuthService(db)
        message = await service.request_password_reset(request_body)
        
        return {
            "success": True,
            "message": message,
            "data": None
        }
    
    @staticmethod
    async def reset_password(
        request_body: PasswordResetRequest,
        db: AsyncSession = Depends(get_db)
    ) -> Dict[str, Any]:
        service = AuthService(db)
        message = await service.reset_password(request_body)
        
        return {
            "success": True,
            "message": message,
            "data": None
        }
    
    @staticmethod
    async def google_login(
        db: AsyncSession = Depends(get_db)
    ) -> Dict[str, Any]:
        """
        Generate Google OAuth2 authorization URL
        """
        service = AuthService(db)
        authorization_url = service.generate_google_login_url()
        
        return {
            "success": True,
            "message": "Google authorization URL generated",
            "data": {"authorization_url": authorization_url}
        }
    
    @staticmethod
    async def google_callback(
        code: str,
        req: Request,
        db: AsyncSession = Depends(get_db)
    ) -> Dict[str, Any]:
        """
        Handle Google OAuth2 callback
        """
        service = AuthService(db)
        ip = req.client.host if req.client else None
        device = req.headers.get("User-Agent")
        
        auth_response = await service.google_callback(code, ip, device)
        
        return {
            "success": True,
            "message": "Google login successful",
            "data": auth_response.model_dump()
        }
