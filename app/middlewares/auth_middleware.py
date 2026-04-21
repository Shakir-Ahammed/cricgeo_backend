"""
Authentication middleware for JWT token verification
Intercepts requests, validates JWT tokens, and attaches user data to request state
"""

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.security import decode_token, verify_token_type
from typing import Callable, List
import re


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to verify JWT tokens and attach user data to request
    
    Public routes (skip authentication):
    - /auth/request-otp
    - /auth/verify-otp
    - /auth/google/login
    - /auth/google/callback
    - /health
    - /docs
    - /openapi.json
    - /
    
    For protected routes:
    - Extracts JWT from Authorization header
    - Validates token
    - Attaches user data to request.state.user
    """
    
    # Routes that don't require authentication
    PUBLIC_ROUTES = [
        r'^/auth/google/login$',
        r'^/auth/google/callback.*',
        r'^/auth/request-otp$',
        r'^/auth/verify-otp$',
        r'^/auth/refresh-token$',
        r'^/auth/logout$',
        r'^/locations/.*',          # Countries and cities are public
        r'^/health$',
        r'^/docs.*',
        r'^/openapi.json$',
        r'^/redoc.*',
        r'^/sso-test$',
        r'^/$',
    ]
    
    def __init__(self, app, exclude_routes: List[str] = None):
        """
        Initialize auth middleware
        
        Args:
            app: FastAPI application
            exclude_routes: Additional routes to exclude from authentication
        """
        super().__init__(app)
        
        # Add custom excluded routes if provided
        if exclude_routes:
            self.PUBLIC_ROUTES.extend(exclude_routes)
    
    async def dispatch(self, request: Request, call_next: Callable):
        """
        Process each request
        
        Args:
            request: Incoming request
            call_next: Next middleware or route handler
            
        Returns:
            Response from next handler or error response
        """
        path = request.url.path
        
        # Skip authentication for public routes
        if self._is_public_route(path):
            return await call_next(request)
        
        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization")
        
        if not auth_header:
            return self._unauthorized_response("Missing authorization header")
        
        # Check if header format is correct (Bearer <token>)
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return self._unauthorized_response("Invalid authorization header format")
        
        token = parts[1]
        
        # Decode and verify token
        payload = decode_token(token)
        if not payload:
            return self._unauthorized_response("Invalid or expired token")
        
        # Verify token type (must be access token)
        if not verify_token_type(payload, "access"):
            return self._unauthorized_response("Invalid token type")
        
        # Extract user data from token
        user_id = payload.get("user_id")
        email = payload.get("email")

        if not user_id:
            return self._unauthorized_response("Invalid token payload")

        # Attach user data to request state
        request.state.user = {
            "id": user_id,
            "email": email,
        }
        
        # Continue to next handler
        response = await call_next(request)
        return response
    
    def _is_public_route(self, path: str) -> bool:
        """
        Check if route is public (doesn't require authentication)
        
        Args:
            path: Request path
            
        Returns:
            True if route is public, False otherwise
        """
        for pattern in self.PUBLIC_ROUTES:
            if re.match(pattern, path):
                return True
        return False
    
    def _unauthorized_response(self, detail: str) -> JSONResponse:
        """
        Return standardized unauthorized response
        
        Args:
            detail: Error detail message
            
        Returns:
            JSONResponse with 401 status
        """
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "success": False,
                "message": "Unauthorized",
                "data": {
                    "detail": detail
                }
            }
        )


def get_current_user(request: Request) -> dict:
    """
    Dependency to get current authenticated user from request state
    Use this in route handlers to access user data
    
    Args:
        request: Current request
        
    Returns:
        User data dictionary
        
    Raises:
        HTTPException: If user not found in request state
        
    Example:
        @router.get("/profile")
        async def get_profile(user: dict = Depends(get_current_user)):
            return {"user_id": user["id"]}
    """
    if not hasattr(request.state, "user"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    return request.state.user
