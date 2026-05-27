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
    RequestOTPRequest, VerifyOTPRequest, CompleteProfileRequest, RefreshTokenRequest, GoogleTokenRequest
)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)

@router.get(
    "/google/login",
    response_model=Dict[str, Any],
    summary="Initiate Google OAuth2 login (web)",
    responses={
        200: {
            "description": "Authorization URL generated",
            "content": {"application/json": {"example": {
                "success": True, "message": "Redirect to Google",
                "data": {"authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?..."}
            }}},
        }
    },
)
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


@router.get(
    "/google/callback",
    summary="Google OAuth2 callback (web)",
    description="""🌐 Public. Used by the **web** Google login flow.

Google redirects the browser here with `code` + `state`; we exchange the code, create or log in the user, and 302-redirect back to `redirect_to` with tokens in the query string.

Mobile apps should NOT call this — use `POST /auth/google/token` instead.""",
)
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


@router.post(
    "/google/token",
    response_model=Dict[str, Any],
    summary="Google Sign-In (mobile id_token)",
    description="""🌐 Public. Mobile flow:
1. App uses Google Sign-In SDK → receives `id_token`.
2. App POSTs that `id_token` here.
3. Backend verifies with Google, finds/creates the user, returns JWT tokens.""",
    responses={
        200: {
            "description": "Authenticated",
            "content": {"application/json": {"example": {
                "success": True, "message": "Login successful",
                "data": {
                    "user": {"id": 12, "name": "Rakib Hasan", "email": "rakib@example.com", "is_profile_completed": True},
                    "tokens": {
                        "access_token": "eyJhbGciOi...", "refresh_token": "eyJhbGciOi...",
                        "token_type": "bearer", "expires_in": 900
                    },
                    "is_new_user": False
                }
            }}}
        },
        401: {"description": "Invalid Google id_token"}
    },
)
async def google_token_login(
    request_body: GoogleTokenRequest,
    req: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Mobile Google Sign-In endpoint.
    The mobile app uses the Google Sign-In SDK to obtain an id_token,
    then POSTs it here to receive access_token + refresh_token.
    """
    return await AuthController.google_token_login(request_body, req, db)


# ============================================================================
# OTP AUTHENTICATION ROUTES
# ============================================================================

@router.post(
    "/request-otp",
    response_model=Dict[str, Any],
    summary="Send 6-digit OTP to phone or email",
    description="""🌐 Public. Step 1 of mobile-first auth.

- Provide **exactly one** of `phone` or `email`.
- OTP is 6 digits, valid **5 minutes**.
- Rate-limited: **3 requests / minute** per identifier.
- If the identifier is new, `otp_type="signup"`; else `"login"`.""",
    responses={
        200: {
            "description": "OTP sent",
            "content": {"application/json": {"example": {
                "success": True, "message": "OTP sent",
                "data": {"message": "OTP sent via sms", "channel": "sms", "identifier": "01712345678", "otp_type": "login"}
            }}}
        },
        400: {"description": "Both / neither identifier provided"},
        429: {"description": "Too many requests"}
    },
)
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


@router.post(
    "/verify-otp",
    response_model=Dict[str, Any],
    summary="Verify OTP and receive JWT tokens",
    description="""🌐 Public. Step 2 of mobile-first auth.

- Same identifier (`phone` OR `email`) used in `/request-otp` plus the 6-digit `otp`.
- Max **5** verification attempts per OTP before it's invalidated.
- New users get a minimal account; `is_new_user=true` and `is_profile_completed=false` — send them through `/auth/complete-profile`.""",
    responses={
        200: {
            "description": "OTP verified, tokens issued",
            "content": {"application/json": {"example": {
                "success": True, "message": "Login successful",
                "data": {
                    "access_token": "eyJhbGciOi...", "refresh_token": "eyJhbGciOi...",
                    "token_type": "bearer", "expires_in": 900,
                    "is_new_user": False, "is_profile_completed": True
                }
            }}}
        },
        400: {"description": "Invalid / expired OTP"},
        401: {"description": "Too many wrong attempts"}
    },
)
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


@router.post(
    "/complete-profile",
    response_model=Dict[str, Any],
    summary="Complete profile after OTP signup",
    description="""🔒 Requires Bearer access token.

Call right after `/verify-otp` if `is_profile_completed=false`. Sets `users.is_profile_completed=true` so subsequent screens are unlocked.""",
    responses={
        200: {
            "description": "Profile completed",
            "content": {"application/json": {"example": {
                "success": True, "message": "Profile completed",
                "data": {"user": {"id": 12, "name": "Rakib Hasan", "is_profile_completed": True}}
            }}}
        },
        401: {"description": "Missing / invalid access token"}
    },
)
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

@router.post(
    "/refresh-token",
    response_model=Dict[str, Any],
    summary="Rotate access + refresh tokens",
    description="""🌐 Public (uses the refresh token itself).

Secure rotation:
- Validates the refresh token.
- Issues a **new** access AND a **new** refresh token.
- Old refresh token is revoked.
- Reuse of an already-revoked refresh token revokes the **entire** session family (theft detection).""",
    responses={
        200: {
            "description": "New token pair issued",
            "content": {"application/json": {"example": {
                "success": True, "message": "Token refreshed",
                "data": {
                    "access_token": "eyJhbGciOi...", "refresh_token": "eyJhbGciOi...",
                    "token_type": "bearer", "expires_in": 900
                }
            }}}
        },
        401: {"description": "Refresh token invalid / expired / revoked"}
    },
)
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


@router.post(
    "/logout",
    response_model=Dict[str, Any],
    summary="Logout current device",
    description="🌐 Public. Revokes the supplied refresh token. Other devices stay logged in.",
    responses={200: {"content": {"application/json": {"example": {"success": True, "message": "Logged out", "data": None}}}}},
)
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


@router.post(
    "/logout-all",
    response_model=Dict[str, Any],
    summary="Logout all devices for the current user",
    description="🔒 Requires Bearer access token. Revokes every active refresh token of the user.",
    responses={
        200: {"content": {"application/json": {"example": {"success": True, "message": "All sessions revoked", "data": {"revoked": 3}}}}},
        401: {"description": "Missing / invalid access token"}
    },
)
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
