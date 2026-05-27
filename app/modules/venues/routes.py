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

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
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


@router.get(
    "",
    response_model=Dict[str, Any],
    summary="List all venues (paginated)",
    description="""🌐 Public (auth optional — also returns the caller's private venues when logged in).

Simple paginated listing without filters. For text / city / radius filters use **`GET /venues/search`** instead.
""",
    responses={200: {"content": {"application/json": {"example": {
        "success": True, "message": "Venues retrieved successfully",
        "data": {"total": 2, "page": 1, "per_page": 20, "items": [
            {"id": 4, "name": "Sher-e-Bangla National Cricket Stadium",
             "address": "Mirpur, Dhaka 1216", "city_id": 1, "country_id": 1,
             "latitude": 23.8073, "longitude": 90.3536,
             "is_public": True, "photo": None, "status": "active"},
            {"id": 7, "name": "Zahur Ahmed Chowdhury Stadium",
             "address": "Agrabad, Chittagong", "city_id": 2, "country_id": 1,
             "latitude": 22.3343, "longitude": 91.8194,
             "is_public": True, "photo": None, "status": "active"}
        ]}
    }}}}},
)
async def list_all_venues(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    current_user_id = _optional_user_id(request)
    return await controller.list_all_venues(
        db, current_user_id=current_user_id, page=page, per_page=per_page
    )


@router.get(
    "/search",
    response_model=Dict[str, Any],
    summary="Search venues by text, city, or geo radius",
    description="""🌐 Public (auth optional — also returns the caller's private venues if logged in).

**Query params:** `q`, `city_id`, `lat`+`lon`+`radius_km`, `page`, `per_page`.
""",
    responses={200: {"content": {"application/json": {"example": {
        "success": True, "message": "Venues",
        "data": {"total": 1, "page": 1, "per_page": 20, "items": [
            {"id": 4, "name": "Sher-e-Bangla National Cricket Stadium",
             "address": "Mirpur, Dhaka 1216", "city_id": 1,
             "latitude": 23.8073, "longitude": 90.3536,
             "is_public": True, "photo": None}
        ]}
    }}}}},
)
async def search_venues(
    request: Request,
    params: VenueSearchParams = Depends(),
    db: AsyncSession = Depends(get_db),
):
    current_user_id = _optional_user_id(request)
    return await controller.search_venues(db, params=params, current_user_id=current_user_id)


@router.get(
    "/{venue_id}",
    response_model=Dict[str, Any],
    summary="Get a single venue",
    description="🌐🔒 Public if `is_public=true`; otherwise must be the creator.",
    responses={
        200: {"content": {"application/json": {"example": {
            "success": True, "message": "Venue",
            "data": {"id": 4, "name": "Sher-e-Bangla National Cricket Stadium",
                     "address": "Mirpur, Dhaka 1216", "city_id": 1,
                     "latitude": 23.8073, "longitude": 90.3536, "is_public": True}
        }}}},
        403: {"description": "Private venue — not owner"},
        404: {"description": "Venue not found"}
    },
)
async def get_venue(
    venue_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    current_user_id = _optional_user_id(request)
    return await controller.get_venue(db, venue_id=venue_id, current_user_id=current_user_id)


@router.post(
    "",
    status_code=201,
    response_model=Dict[str, Any],
    summary="Create a new venue",
    description="🔒 Auth required. Caller becomes the venue's `created_by`.",
    responses={
        201: {"content": {"application/json": {"example": {
            "success": True, "message": "Venue created",
            "data": {"id": 4, "name": "Sher-e-Bangla National Cricket Stadium",
                     "is_public": True}
        }}}},
        401: {"description": "Auth required"}, 422: {"description": "Validation error"}
    },
)
async def create_venue(
    data: VenueCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Auth required — current_user injected by AuthMiddleware."""
    current_user_id: int = request.state.user["id"]
    return await controller.create_venue(db, data=data, current_user_id=current_user_id)


@router.post(
    "/{venue_id}/photo",
    response_model=Dict[str, Any],
    summary="Upload / replace venue photo",
    description="""🔒 Auth required. **Creator only.**

Accepts **JPEG / PNG / WebP**, max **5 MB**. Stored on Cloudflare R2; `venues.photo` is updated.
""",
    responses={
        200: {"content": {"application/json": {"example": {
            "success": True, "message": "Photo uploaded",
            "data": {"venue_id": 4, "photo": "https://cdn.cricgeo.com/venues/4/photo.jpg"}
        }}}},
        401: {"description": "Auth required"}, 403: {"description": "Not the creator"},
        413: {"description": "Image larger than 5 MB"}, 415: {"description": "Unsupported media type"}
    },
)
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
