"""
User routes defining API endpoints for user management
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.modules.users.controller import UserController
from app.modules.users.schema import UserCreate, UserUpdate
from typing import Dict, Any, Optional

# Create router for user endpoints
router = APIRouter(
    prefix="/users",
    tags=["Users"]
)


@router.get("", response_model=Dict[str, Any])
async def get_users(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search term for name or email"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get paginated list of users with optional search
    
    - **page**: Page number (minimum 1)
    - **page_size**: Number of items per page (1-100)
    - **search**: Optional search term to filter by name or email
    
    Returns paginated user list
    """
    return await UserController.get_users(page, page_size, search, db)


@router.get("/{user_id}", response_model=Dict[str, Any])
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get user by ID
    
    - **user_id**: User's unique ID
    
    Returns user details
    """
    return await UserController.get_user(user_id, db)


@router.post("", response_model=Dict[str, Any])
async def create_user(
    request: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new user (admin operation)
    
    - **name**: User's full name (2-100 characters)
    - **email**: Valid email address (will be normalized)
    - **password**: Password (min 8 characters)
    
    Returns created user details
    """
    return await UserController.create_user(request, db)


@router.put("/{user_id}", response_model=Dict[str, Any])
async def update_user(
    user_id: int,
    request: UserUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Update user profile
    
    - **user_id**: User's unique ID
    - **name**: Optional - User's new full name
    - **email**: Optional - User's new email address
    - **password**: Optional - User's new password
    
    All fields are optional. Only provided fields will be updated.
    Returns updated user details
    """
    return await UserController.update_user(user_id, request, db)


@router.delete("/{user_id}", response_model=Dict[str, Any])
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete user by ID
    
    - **user_id**: User's unique ID
    
    Returns success message
    """
    return await UserController.delete_user(user_id, db)
