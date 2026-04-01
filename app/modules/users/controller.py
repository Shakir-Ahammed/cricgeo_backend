"""
User controller handling HTTP requests/responses
Thin layer between routes and service - only handles request/response logic
"""

from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.modules.users.service import UserService
from app.modules.users.schema import UserCreate, UserUpdate, UserOut, UserList
from typing import Dict, Any, Optional


class UserController:
    """
    Controller for user endpoints
    Delegates business logic to UserService
    """
    
    @staticmethod
    async def get_users(
        page: int = Query(1, ge=1, description="Page number"),
        page_size: int = Query(20, ge=1, le=100, description="Items per page"),
        search: Optional[str] = Query(None, description="Search term for name or email"),
        db: AsyncSession = Depends(get_db)
    ) -> Dict[str, Any]:
        """
        Get paginated list of users
        
        Args:
            page: Page number (minimum 1)
            page_size: Number of items per page (1-100)
            search: Optional search term
            db: Database session
            
        Returns:
            Standardized API response with user list
        """
        service = UserService(db)
        user_list = await service.get_users(page, page_size, search)
        
        return {
            "success": True,
            "message": "Users retrieved successfully",
            "data": user_list.model_dump()
        }
    
    @staticmethod
    async def get_user(
        user_id: int,
        db: AsyncSession = Depends(get_db)
    ) -> Dict[str, Any]:
        """
        Get user by ID
        
        Args:
            user_id: User's ID
            db: Database session
            
        Returns:
            Standardized API response with user data
        """
        service = UserService(db)
        user = await service.get_user_by_id(user_id)
        
        return {
            "success": True,
            "message": "User retrieved successfully",
            "data": user.model_dump()
        }
    
    @staticmethod
    async def create_user(
        request: UserCreate,
        db: AsyncSession = Depends(get_db)
    ) -> Dict[str, Any]:
        """
        Create a new user (admin operation)
        
        Args:
            request: UserCreate with user details
            db: Database session
            
        Returns:
            Standardized API response with created user
        """
        service = UserService(db)
        user = await service.create_user(request)
        
        return {
            "success": True,
            "message": "User created successfully",
            "data": user.model_dump()
        }
    
    @staticmethod
    async def update_user(
        user_id: int,
        request: UserUpdate,
        db: AsyncSession = Depends(get_db)
    ) -> Dict[str, Any]:
        """
        Update user profile
        
        Args:
            user_id: User's ID
            request: UserUpdate with fields to update
            db: Database session
            
        Returns:
            Standardized API response with updated user
        """
        service = UserService(db)
        user = await service.update_user(user_id, request)
        
        return {
            "success": True,
            "message": "User updated successfully",
            "data": user.model_dump()
        }
    
    @staticmethod
    async def delete_user(
        user_id: int,
        db: AsyncSession = Depends(get_db)
    ) -> Dict[str, Any]:
        """
        Delete user by ID
        
        Args:
            user_id: User's ID
            db: Database session
            
        Returns:
            Standardized API response
        """
        service = UserService(db)
        await service.delete_user(user_id)
        
        return {
            "success": True,
            "message": "User deleted successfully",
            "data": None
        }
