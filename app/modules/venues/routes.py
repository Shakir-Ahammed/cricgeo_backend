"""
Venue routes.

Public:
  GET  /venues/search     — search with optional filters
  GET  /venues/{id}       — get single venue (403 if private and not owner)

Auth required:
  POST /venues            — create a venue
  POST /venues/{id}/photo — upload venue photo (creator only)
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.modules.venues import controller
from app.modules.venues.schema import VenueCreate, VenueSearchParams

router = APIRouter(prefix="/venues", tags=["Venues"])

_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
_MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB


def _optional_user_id(request: Request) -> Optional[int]:
    """
    Extract the authenticated user's id from request.state if present,
    or return None for unauthenticated requests.
    """
    user = getattr(request.state, "user", None)
    if user is None:
        return None
    return user.get("id") if isinstance(user, dict) else getattr(user, "id", None)


def _require_user_id(request: Request) -> int:
    uid = _optional_user_id(request)
    if uid is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return uid


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


@router.post("/{venue_id}/photo", response_model=Dict[str, Any])
async def upload_venue_photo(
    venue_id: int,
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload or replace the venue photo (JPEG / PNG / WebP, max 5 MB).
    Only the venue creator may upload.
    Saves to Cloudflare R2 and updates venues.photo in the database.
    """
    current_user_id = _require_user_id(request)

    if file.content_type not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only JPEG, PNG, and WebP images are allowed",
        )
    contents = await file.read()
    if len(contents) > _MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image must be 5 MB or smaller",
        )
    return await controller.upload_venue_photo(
        db, venue_id=venue_id, current_user_id=current_user_id,
        contents=contents, filename=file.filename or "photo",
    )
