"""
Profile routes.
"""

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any

from app.core.db import get_db
from app.core.security import get_current_user
from app.core.storage import upload_profile_photo
from app.modules.profiles.controller import ProfileController
from app.modules.profiles.schema import UpdateProfileRequest, UpdateSkillsRequest

router = APIRouter(prefix="/profiles", tags=["Profiles"])

_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
_MAX_IMAGE_BYTES = 2 * 1024 * 1024  # 2 MB


# ===========================================================================
# GET full profile
# ===========================================================================

@router.get(
    "/me",
    response_model=Dict[str, Any],
    summary="Get the current user's full profile",
    description="🔒 Auth required. Returns user identity + personal details + player skills in a single payload — used to hydrate the Profile screen.",
    responses={
        200: {"content": {"application/json": {"example": {
            "success": True, "message": "Profile retrieved",
            "data": {
                "id": 12, "name": "Rakib Hasan", "email": "rakib@example.com", "phone": "01712345678",
                "is_profile_completed": True, "status": "active",
                "country_id": 1, "city_id": 1, "gender": 1, "date_of_birth": "1998-04-15",
                "profile_image": "https://cdn/cric/u12.jpg", "bio": "Opening batsman from Dhaka",
                "roles": [4], "batting_style": 2, "batting_order": 1,
                "bowling_style": 2, "bowling_category": 2, "bowling_type": 4,
                "created_at": "2026-05-01T08:00:00Z", "updated_at": "2026-05-20T12:00:00Z"
            }
        }}}},
        401: {"description": "Missing / invalid access token"}
    },
)
async def get_full_profile(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Return combined profile: personal info + player skills."""
    return await ProfileController.get_full_profile(user["id"], db)


# ===========================================================================
# Step 1: personal identity  (Profile page 1/2)
# ===========================================================================

@router.put(
    "/me",
    response_model=Dict[str, Any],
    summary="Update personal identity (Profile page 1/2)",
    description="""🔒 Auth required.

- `name`, `gender` are required.
- `phone` / `email` are only **set** if the account doesn't already have one — to change an existing value use the dedicated change-phone / change-email flow.
- Sets `users.is_profile_completed = true`.
""",
    responses={
        200: {"content": {"application/json": {"example": {
            "success": True, "message": "Profile updated",
            "data": {"id": 12, "name": "Rakib Hasan", "is_profile_completed": True}
        }}}},
        401: {"description": "Missing / invalid access token"},
        422: {"description": "Validation error"}
    },
)
async def update_profile(
    req: UpdateProfileRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    Update personal identity (Profile page 1/2).

    Required fields: name, gender
    Optional fields: country_id, city_id, phone, email, profile_image, bio, date_of_birth

    - phone/email are only set when the field is currently empty on the account
      (use the dedicated change-phone / change-email flow to update an existing value).
    - Sets is_profile_completed = true.
    """
    return await ProfileController.upsert_profile(user["id"], req, db)


# ===========================================================================
# Step 2: player skills  (Profile page 2/2)
# ===========================================================================

@router.put(
    "/me/skills",
    response_model=Dict[str, Any],
    summary="Update player skills (Profile page 2/2)",
    description="""🔒 Auth required.

| Field | Values |
|---|---|
| `role` | 1=batsman, 2=bowler, 3=wicketkeeper batsman, 4=allrounder |
| `batting_style` | 1=left-hand, 2=right-hand |
| `batting_order` | 1=opening, 2=top, 3=middle, 4=lower |
| `bowling_style` | 1=left-arm, 2=right-arm |
| `bowling_type` | 1=fast, 2=fast medium, 3=medium, 4=off break, 5=leg break, 6=orthodox, 7=wrist spin |

`bowling_style` + `bowling_type` are **required** when `role` is bowler (2) or allrounder (4).
""",
    responses={
        200: {"content": {"application/json": {"example": {
            "success": True, "message": "Skills updated",
            "data": {"roles": [4], "batting_style": 2, "batting_order": 1, "bowling_style": 2, "bowling_type": 4}
        }}}},
        401: {"description": "Missing / invalid access token"},
        422: {"description": "Missing bowling fields for bowler/allrounder"}
    },
)
async def update_skills(
    req: UpdateSkillsRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    Update player skills (Profile page 2/2).

    - role: 1=batsman, 2=bowler, 3=wicketkeeper batsman, 4=allrounder
    - batting_style: 1=left-hand, 2=right-hand
    - batting_order: 1=opening, 2=top, 3=middle, 4=lower
    - bowling_style + bowling_type: required when role is bowler (2) or allrounder (4)
      bowling_type: 1=fast, 2=fast medium, 3=medium, 4=off break, 5=leg break, 6=orthodox, 7=wrist spin
    """
    return await ProfileController.update_skills(user["id"], req, db)


# ===========================================================================
# Profile photo upload
# ===========================================================================

@router.post(
    "/me/photo",
    response_model=Dict[str, Any],
    summary="Upload profile photo (JPEG/PNG/WebP, max 2MB)",
    description="🔒 Auth required. `multipart/form-data` with file field `file`. Returns the CDN URL.",
    responses={
        200: {"content": {"application/json": {"example": {
            "success": True, "message": "Photo uploaded successfully",
            "data": {"url": "https://cdn/cric/profiles/u12-abcd1234.jpg"}
        }}}},
        401: {"description": "Missing / invalid access token"},
        413: {"description": "Image larger than 2 MB"},
        415: {"description": "Unsupported media type — only JPEG/PNG/WebP"}
    },
)
async def upload_profile_photo_endpoint(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    Upload a profile photo (JPEG / PNG / WebP, max 2 MB).
    Saves the image to object storage and updates profile_image in the database.
    Returns the public URL.
    """
    if file.content_type not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only JPEG, PNG, and WebP images are allowed",
        )

    contents = await file.read()
    if len(contents) > _MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image must be 2 MB or smaller",
        )

    # Upload to object storage
    public_url = upload_profile_photo(contents, file.filename or "photo", user["id"])

    # Persist URL in profiles table
    await ProfileController.save_profile_image(user["id"], public_url, db)

    return {
        "success": True,
        "message": "Photo uploaded successfully",
        "data": {"url": public_url},
    }



