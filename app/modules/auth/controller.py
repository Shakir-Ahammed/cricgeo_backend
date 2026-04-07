"""
Auth controller handling HTTP requests/responses
"""

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any

from app.core.db import get_db
from app.modules.auth.service import AuthService
from app.modules.auth.schema import (
    RequestOTPRequest, VerifyOTPRequest, CompleteProfileRequest
)


class AuthController:
    """
    Controller for auth endpoints
    """
    
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
