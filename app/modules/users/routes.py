"""
User routes.
"""

from fastapi import APIRouter, Depends, Query, Request, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.modules.users.controller import UserController
from app.modules.users.service import UserService
from typing import Dict, Any, List, Optional

router = APIRouter(prefix="/users", tags=["Users"])


class _BulkCheckBody(BaseModel):
    phones: List[str]

    model_config = {
        "json_schema_extra": {
            "example": {"phones": ["01712345678", "01987654321", "01511122233"]}
        }
    }


@router.post(
    "/bulk-check",
    response_model=Dict[str, Any],
    summary="Match phone contacts against registered users",
    description="""🔒 Auth required. Used by the **Add From Contacts** flow.

- Max **200** phones per request (extras silently dropped).
- Duplicates are de-duplicated server-side.
- Returns which phones already have an account so the UI can show "Add to team" vs "Invite".
""",
    responses={
        200: {
            "description": "Contacts checked",
            "content": {"application/json": {"example": {
                "success": True, "message": "Contacts checked",
                "data": {
                    "registered": [{"phone": "01712345678", "user_id": 12, "name": "Rakib Hasan"}],
                    "unregistered": ["01987654321", "01511122233"]
                }
            }}}
        },
        400: {"description": "Empty phones list"},
        401: {"description": "Missing / invalid access token"}
    },
)
async def bulk_check_phones(
    body: _BulkCheckBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Check which phone numbers from a contact list are registered.
    Auth required (prevents scraping). Max 200 phones per request.
    Returns: {registered: [{phone, user_id, name}], unregistered: [phone, ...]}
    """
    if not body.phones:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="phones list is empty")
    svc = UserService(db)
    result = await svc.bulk_check_phones(body.phones)
    return {"success": True, "message": "Contacts checked", "data": result}


@router.get(
    "/search",
    response_model=Dict[str, Any],
    summary="Search users for player picker",
    description="""🔒 Auth required. Powers the **Add New Players → Search Players** screen.

Searches active users by partial **name**, **phone**, **email**, or **username** (all case-insensitive, partial). Useful as the captain types in the identifier field — if a match exists, add as registered; otherwise show the "Player full name" field and add as guest.

Phone is **masked** in the response (only last 4 digits, e.g. `"****5678"`).""",
    responses={
        200: {
            "description": "Matching players",
            "content": {"application/json": {"example": {
                "success": True, "message": "Players found",
                "data": [
                    {"id": 12, "name": "Rakib Hasan", "phone": "****5678", "username": "rakib_h", "profile_image": "https://cdn/cric/u12.jpg"},
                    {"id": 45, "name": "Rakib Khan", "phone": "****1122", "username": None, "profile_image": None}
                ]
            }}}
        },
        400: {"description": "Query too short (<2 chars)"},
        401: {"description": "Missing / invalid access token"}
    },
)
async def search_players(
    request: Request,
    q: str = Query(..., min_length=2, description="Search query — min 2 characters"),
    limit: int = Query(20, ge=1, le=20, description="Max results (capped at 20)"),
    db: AsyncSession = Depends(get_db),
):
    """Search for players by name, phone, or username. Auth required."""
    if len(q.strip()) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query must be at least 2 characters",
        )
    return await UserController.search_players(q.strip(), limit, db)


@router.get(
    "",
    response_model=Dict[str, Any],
    summary="List users (admin / paged)",
    description="Paged list of users with optional substring search on name, email or phone.",
    responses={200: {"content": {"application/json": {"example": {
        "success": True, "message": "Users retrieved",
        "data": {"total": 1, "page": 1, "page_size": 20, "users": [
            {"id": 12, "name": "Rakib Hasan", "email": "rakib@example.com", "phone": "01712345678",
             "is_email_verified": False, "is_phone_verified": True, "is_profile_completed": True,
             "status": "active", "created_at": "2026-05-01T08:00:00Z", "updated_at": "2026-05-20T12:00:00Z",
             "last_login_at": "2026-05-26T09:30:00Z"}
        ]}
    }}}}},
)
async def get_users(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by name, email or phone"),
    db: AsyncSession = Depends(get_db),
):
    return await UserController.get_users(page, page_size, search, db)


@router.get(
    "/{user_id}",
    response_model=Dict[str, Any],
    summary="Get user by ID",
    responses={
        200: {"content": {"application/json": {"example": {
            "success": True, "message": "User retrieved",
            "data": {"id": 12, "name": "Rakib Hasan", "email": "rakib@example.com", "phone": "01712345678",
                     "is_profile_completed": True, "status": "active"}
        }}}},
        404: {"description": "User not found"}
    },
)
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
    return await UserController.get_user(user_id, db)
