"""
Auth controller handling HTTP requests/responses
"""

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional

from app.core.db import get_db
from app.modules.auth.service import AuthService
from app.modules.auth.schema import (
    RequestOTPRequest,
    VerifyOTPRequest,
    CompleteProfileRequest,
)


class AuthController:
    """
    Controller for auth endpoints
    """
    
    @staticmethod
    async def google_login(
        req: Request,
        redirect_to: Optional[str],
        db: AsyncSession = Depends(get_db)
    ) -> Dict[str, Any]:
        """
        Generate Google OAuth2 authorization URL
        """
        service = AuthService(db)
        final_redirect = redirect_to
        if final_redirect is None:
            final_redirect = f"{req.url.scheme}://{req.url.netloc}/sso-test"

        authorization_url = service.generate_google_login_url(final_redirect)
        
        return {
            "success": True,
            "message": "Google authorization URL generated",
            "data": {"authorization_url": authorization_url}
        }
    
    @staticmethod
    async def google_callback(
        code: str,
        state: str,
        req: Request,
        db: AsyncSession = Depends(get_db)
    ) -> Dict[str, Any]:
        """
        Handle Google OAuth2 callback
        """
        service = AuthService(db)
        ip = req.client.host if req.client else None
        device = req.headers.get("User-Agent")
        
        auth_response, redirect_to = await service.google_callback(code, state, ip, device)

        data: Dict[str, Any] = auth_response.model_dump()
        if redirect_to:
            data["redirect_url"] = service.build_google_callback_redirect_url(redirect_to, auth_response)

        return {
            "success": True,
            "message": "Google login successful",
            "data": data,
        }

    
    # ============================================================================
    # OTP AUTHENTICATION CONTROLLERS
    # ============================================================================
    
    @staticmethod
    async def request_otp(
        request_body: "RequestOTPRequest",
        db: AsyncSession = Depends(get_db)
    ) -> Dict[str, Any]:
        """
        Request OTP for email-based authentication
        """
        service = AuthService(db)
        response = await service.request_otp(request_body)
        
        return {
            "success": True,
            "message": response.message,
            "data": {"email": response.email}
        }
    
    @staticmethod
    async def verify_otp(
        request_body: "VerifyOTPRequest",
        req: Request,
        db: AsyncSession = Depends(get_db)
    ) -> Dict[str, Any]:
        """
        Verify OTP and login/register user
        """
        service = AuthService(db)
        ip = req.client.host if req.client else None
        device = req.headers.get("User-Agent")
        
        response = await service.verify_otp(request_body, ip, device)
        
        return {
            "success": True,
            "message": "OTP verified successfully",
            "data": response.model_dump()
        }
    
    @staticmethod
    async def complete_profile(
        request_body: "CompleteProfileRequest",
        user: dict,
        db: AsyncSession = Depends(get_db)
    ) -> Dict[str, Any]:
        """
        Complete user profile after OTP registration
        """
        service = AuthService(db)
        
        response = await service.complete_profile(user["id"], request_body)
        
        return {
            "success": True,
            "message": response.message,
            "data": {"user": response.user.model_dump()}
        }


    
    # ============================================================================
    # REFRESH TOKEN CONTROLLERS
    # ============================================================================
    
    @staticmethod
    async def refresh_token(
        request_body: "RefreshTokenRequest",
        req: Request,
        db: AsyncSession = Depends(get_db)
    ) -> Dict[str, Any]:
        """
        Refresh access token using refresh token.
        Implements secure token rotation.
        """
        service = AuthService(db)
        ip = req.client.host if req.client else None
        device = req.headers.get("User-Agent")
        
        response = await service.refresh_access_token(request_body, ip, device)
        
        return {
            "success": True,
            "message": "Token refreshed successfully",
            "data": response.model_dump()
        }
    
    @staticmethod
    async def logout(
        request_body: "RefreshTokenRequest",
        db: AsyncSession = Depends(get_db)
    ) -> Dict[str, Any]:
        """
        Logout from current device by revoking refresh token.
        """
        service = AuthService(db)
        message = await service.logout(request_body.refresh_token)
        
        return {
            "success": True,
            "message": message,
            "data": None
        }
    
    @staticmethod
    async def logout_all(
        user: dict,
        db: AsyncSession = Depends(get_db)
    ) -> Dict[str, Any]:
        """
        Logout from all devices by revoking all refresh tokens.
        """
        service = AuthService(db)
        message = await service.logout_all(user["id"])
        
        return {
            "success": True,
            "message": message,
            "data": None
        }
