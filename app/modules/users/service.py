"""
User service layer containing business logic for user management
Handles CRUD operations for users
"""

from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from app.modules.users.model import User
from app.modules.users.schema import UserCreate, UserUpdate, UserOut, UserList
from app.core.security import hash_password
from app.helpers.utils import normalize_email
from app.core.config import settings
from fastapi import HTTPException, status


class UserService:
    """
    Service class for user operations
    All business logic related to users should be here
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_users(
        self, 
        page: int = 1, 
        page_size: int = None,
        search: Optional[str] = None
    ) -> UserList:
        """
        Get paginated list of users with optional search
        
        Args:
            page: Page number (1-indexed)
            page_size: Number of items per page
            search: Optional search term for name or email
            
        Returns:
            UserList with paginated users
        """
        if page_size is None:
            page_size = settings.DEFAULT_PAGE_SIZE
        
        # Validate pagination parameters
        if page < 1:
            page = 1
        if page_size < 1 or page_size > settings.MAX_PAGE_SIZE:
            page_size = settings.DEFAULT_PAGE_SIZE
        
        # Build query
        query = select(User)
        
        # Add search filter if provided
        if search:
            search_filter = f"%{search}%"
            query = query.where(
                (User.name.ilike(search_filter)) | 
                (User.email.ilike(search_filter))
            )
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size).order_by(User.created_at.desc())
        
        # Execute query
        result = await self.db.execute(query)
        users = result.scalars().all()
        
        # Build response
        user_list = [UserOut.model_validate(user) for user in users]
        
        return UserList(
            total=total,
            page=page,
            page_size=page_size,
            users=user_list
        )
    
    async def get_user_by_id(self, user_id: int) -> UserOut:
        """
        Get user by ID
        
        Args:
            user_id: User's ID
            
        Returns:
            UserOut object
            
        Raises:
            HTTPException: If user not found
        """
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
            )
        
        return UserOut.model_validate(user)
    
    async def create_user(self, request: UserCreate) -> UserOut:
        """
        Create a new user (admin operation)
        
        Args:
            request: UserCreate schema with user details
            
        Returns:
            UserOut object
            
        Raises:
            HTTPException: If email already exists
        """
        # Normalize email
        email = normalize_email(request.email)
        
        # Check if user already exists
        existing_user = await self._get_user_by_email(email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Hash password
        hashed_password = hash_password(request.password)
        
        # Create new user
        new_user = User(
            name=request.name,
            email=email,
            hashed_password=hashed_password
        )
        
        self.db.add(new_user)
        await self.db.flush()
        await self.db.refresh(new_user)
        
        return UserOut.model_validate(new_user)
    
    async def update_user(self, user_id: int, request: UserUpdate) -> UserOut:
        """
        Update user profile
        
        Args:
            user_id: User's ID
            request: UserUpdate schema with fields to update
            
        Returns:
            UserOut object
            
        Raises:
            HTTPException: If user not found or email already exists
        """
        # Get existing user
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
            )
        
        # Update fields if provided
        if request.name is not None:
            user.name = request.name
        
        if request.email is not None:
            # Normalize email
            email = normalize_email(request.email)
            
            # Check if email is already taken by another user
            if email != user.email:
                existing_user = await self._get_user_by_email(email)
                if existing_user:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Email already registered"
                    )
                user.email = email
        
        if request.password is not None:
            user.hashed_password = hash_password(request.password)
        
        await self.db.flush()
        await self.db.refresh(user)
        
        return UserOut.model_validate(user)
    
    async def delete_user(self, user_id: int) -> None:
        """
        Delete user by ID
        
        Args:
            user_id: User's ID
            
        Raises:
            HTTPException: If user not found
        """
        # Check if user exists
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
            )
        
        # Delete user
        await self.db.execute(
            delete(User).where(User.id == user_id)
        )
    
    async def _get_user_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email (internal helper)
        
        Args:
            email: User's email address
            
        Returns:
            User object or None
        """
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()
