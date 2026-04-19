"""
Auth routes defining API endpoints for authentication
"""

from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional

from app.core.db import get_db
from app.core.security import get_current_user
from app.modules.auth.controller import AuthController
from app.modules.auth.schema import (
    RequestOTPRequest, VerifyOTPRequest, CompleteProfileRequest, RefreshTokenRequest
)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)

@router.get("/google/login", response_model=Dict[str, Any])
async def google_login(
    req: Request,
    redirect_to: Optional[str] = Query(None, description="Frontend URL to redirect after successful Google login"),
    db: AsyncSession = Depends(get_db)
):
    """
    Initiate Google OAuth2 login flow
    Returns authorization URL to redirect user to
    """
    return await AuthController.google_login(req, redirect_to, db)


@router.get("/google/callback")
async def google_callback(
    code: str,
    state: str,
    req: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Handle Google OAuth2 callback
    Exchange authorization code for user information and JWT tokens
    """
    response = await AuthController.google_callback(code, state, req, db)
    redirect_url = response.get("data", {}).get("redirect_url")
    if redirect_url:
        return RedirectResponse(url=redirect_url, status_code=302)
    return response



# ============================================================================
# OTP AUTHENTICATION ROUTES
# ============================================================================

@router.post("/request-otp", response_model=Dict[str, Any])
async def request_otp(
    request_body: RequestOTPRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Request OTP for mobile-first authentication
    - Generates 6-digit OTP
    - Sends to email or SMS
    - Valid for 5 minutes
    - Rate limited: max 3 requests per minute per identifier
    """
    return await AuthController.request_otp(request_body, db)


@router.post("/verify-otp", response_model=Dict[str, Any])
async def verify_otp(
    request_body: VerifyOTPRequest,
    req: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Verify OTP and authenticate user
    - If user exists: login and return JWT
    - If user doesn't exist: create minimal user and return JWT with is_new_user=true
    - Max 5 verification attempts per OTP
    """
    return await AuthController.verify_otp(request_body, req, db)


@router.post("/complete-profile", response_model=Dict[str, Any])
async def complete_profile(
    request_body: CompleteProfileRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Complete user profile after OTP registration
    Requires authentication token
    
    Required fields:
    - name: User's full name (2-100 characters)
    - gender: User's gender (male, female, or other)
    - phone: User's phone number (10-20 characters)
    
    Optional fields:
    - profile_image: URL to profile image
    
    Sets profile_completed=true after successful completion
    """
    return await AuthController.complete_profile(request_body, user, db)



# ============================================================================
# REFRESH TOKEN ROUTES
# ============================================================================

@router.post("/refresh-token", response_model=Dict[str, Any])
async def refresh_token(
    request_body: RefreshTokenRequest,
    req: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Refresh access token using refresh token
    
    Implements secure token rotation:
    - Validates refresh token
    - Generates new access token + new refresh token
    - Revokes old refresh token
    - Detects token reuse and revokes all sessions if compromised
    
    Request body:
    - refresh_token: The refresh token received during login
    
    Returns:
    - access_token: New short-lived access token
    - refresh_token: New long-lived refresh token
    - token_type: "bearer"
    - expires_in: Access token expiry in seconds
    """
    return await AuthController.refresh_token(request_body, req, db)


@router.post("/logout", response_model=Dict[str, Any])
async def logout(
    request_body: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Logout from current device
    
    Revokes the provided refresh token, effectively logging out from the current device.
    Other devices remain logged in.
    
    Request body:
    - refresh_token: The refresh token to revoke
    """
    return await AuthController.logout(request_body, db)


@router.post("/logout-all", response_model=Dict[str, Any])
async def logout_all(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Logout from all devices
    
    Revokes all refresh tokens for the authenticated user.
    Forces logout from all devices for security purposes.
    
    Requires authentication (access token in Authorization header).
    """
    return await AuthController.logout_all(user, db)
