"""
Venue controller: HTTP layer for venue endpoints.
"""

from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.venues import service
from app.modules.venues.schema import VenueCreate, VenueResponse, VenueSearchParams


async def create_venue(
    db: AsyncSession,
    data: VenueCreate,
    current_user_id: int,
) -> Dict[str, Any]:
    venue = await service.create_venue(db, user_id=current_user_id, data=data)
    return {
        "success": True,
        "message": "Venue created successfully",
        "data": VenueResponse.model_validate(venue).model_dump(),
    }


async def get_venue(
    db: AsyncSession,
    venue_id: int,
    current_user_id: Optional[int],
) -> Dict[str, Any]:
    venue = await service.get_venue(db, venue_id=venue_id)
    if venue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venue not found")

    # Private venue: only the creator may view it
    if not venue.is_public and venue.created_by != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this venue",
        )

    return {
        "success": True,
        "message": "Venue retrieved successfully",
        "data": VenueResponse.model_validate(venue).model_dump(),
    }


async def search_venues(
    db: AsyncSession,
    params: VenueSearchParams,
    current_user_id: Optional[int],
) -> Dict[str, Any]:
    result = await service.search_venues(db, params=params, current_user_id=current_user_id)
    return {
        "success": True,
        "message": "Venues retrieved successfully",
        "data": {
            "items": [VenueResponse.model_validate(v).model_dump() for v in result["items"]],
            "total": result["total"],
            "page": result["page"],
            "per_page": result["per_page"],
        },
    }


async def upload_venue_photo(
    db: AsyncSession,
    venue_id: int,
    current_user_id: int,
    contents: bytes,
    filename: str,
) -> Dict[str, Any]:
    """Upload venue photo to R2 and save URL to venues.photo."""
    from app.core.storage import upload_venue_photo as _upload
    public_url = _upload(contents, filename, venue_id)
    venue = await service.save_venue_photo(
        db, venue_id=venue_id, requester_id=current_user_id, url=public_url
    )
    return {
        "success": True,
        "message": "Venue photo uploaded successfully",
        "data": {"url": public_url, "venue_id": venue.id},
    }


async def list_all_venues(
    db: AsyncSession,
    current_user_id: Optional[int],
    page: int,
    per_page: int,
) -> Dict[str, Any]:
    result = await service.list_all_venues(
        db, current_user_id=current_user_id, page=page, per_page=per_page
    )
    return {
        "success": True,
        "message": "Venues retrieved successfully",
        "data": {
            "items": [VenueResponse.model_validate(v).model_dump() for v in result["items"]],
            "total": result["total"],
            "page": result["page"],
            "per_page": result["per_page"],
        },
    }
