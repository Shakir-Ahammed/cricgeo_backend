"""
Auth routes defining API endpoints for authentication
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any

from app.core.db import get_db
from app.modules.auth.controller import AuthController
from app.modules.auth.schema import (
    RegisterRequest, LoginRequest, RefreshTokenRequest,
    VerifyEmailRequest, RequestPasswordResetRequest, PasswordResetRequest
)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


@router.post("/register", response_model=Dict[str, Any])
async def register(
    request_body: RegisterRequest,
    req: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new user and send email verification token
    """
    return await AuthController.register(request_body, req, db)


@router.post("/login", response_model=Dict[str, Any])
async def login(
    request_body: LoginRequest,
    req: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Authenticate user and get JWT tokens
    """
    return await AuthController.login(request_body, req, db)


@router.post("/refresh", response_model=Dict[str, Any])
async def refresh_token(
    request_body: RefreshTokenRequest,
    req: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Refresh access token using refresh token
    """
    return await AuthController.refresh_token(request_body, req, db)


@router.post("/verify-email", response_model=Dict[str, Any])
async def verify_email(
    request_body: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Verify user email with token (POST)
    """
    return await AuthController.verify_email(request_body, db)


@router.get("/verify-email", response_model=Dict[str, Any])
async def verify_email_get(
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Verify user email with token (GET - for email links)
    Usage: /auth/verify-email?token=<token>
    """
    return await AuthController.verify_email_get(token, db)


@router.post("/request-password-reset", response_model=Dict[str, Any])
async def request_password_reset(
    request_body: RequestPasswordResetRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Request password reset token (will be sent via email)
    """
    return await AuthController.request_password_reset(request_body, db)


@router.post("/reset-password", response_model=Dict[str, Any])
async def reset_password(
    request_body: PasswordResetRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Reset password with token
    """
    return await AuthController.reset_password(request_body, db)


@router.get("/google/login", response_model=Dict[str, Any])
async def google_login(
    db: AsyncSession = Depends(get_db)
):
    """
    Initiate Google OAuth2 login flow
    Returns authorization URL to redirect user to
    """
    return await AuthController.google_login(db)


@router.get("/google/callback", response_model=Dict[str, Any])
async def google_callback(
    code: str,
    req: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Handle Google OAuth2 callback
    Exchange authorization code for user information and JWT tokens
    """
    return await AuthController.google_callback(code, req, db)
