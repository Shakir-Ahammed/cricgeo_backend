"""
Venue routes.

Public:
  GET  /venues/search   — search with optional filters
  GET  /venues/{id}     — get single venue (403 if private and not owner)

Auth required:
  POST /venues          — create a venue
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.modules.venues import controller
from app.modules.venues.schema import VenueCreate, VenueSearchParams

router = APIRouter(prefix="/venues", tags=["Venues"])


def _optional_user_id(request: Request) -> Optional[int]:
    """
    Extract the authenticated user's id from request.state if present,
    or return None for unauthenticated requests.
    """
    user = getattr(request.state, "user", None)
    if user is None:
        return None
    return user.get("id") if isinstance(user, dict) else getattr(user, "id", None)


@router.get("/search", response_model=Dict[str, Any])
async def search_venues(
    request: Request,
    params: VenueSearchParams = Depends(),
    db: AsyncSession = Depends(get_db),
):
    current_user_id = _optional_user_id(request)
    return await controller.search_venues(db, params=params, current_user_id=current_user_id)


@router.get("/{venue_id}", response_model=Dict[str, Any])
async def get_venue(
    venue_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    current_user_id = _optional_user_id(request)
    return await controller.get_venue(db, venue_id=venue_id, current_user_id=current_user_id)


@router.post("", status_code=201, response_model=Dict[str, Any])
async def create_venue(
    data: VenueCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Auth required — current_user injected by AuthMiddleware."""
    current_user_id: int = request.state.user["id"]
    return await controller.create_venue(db, data=data, current_user_id=current_user_id)
