"""
Cloudflare R2 object storage client.

Supported asset folders:
  profiles/   — user profile photos
  teams/      — team logos
  venues/     — venue photos
  matches/    — match-related images
  misc/       — anything else

Public URL structure:
  {STORAGE_PUBLIC_URL}/{folder}/{owner_id}/{uuid}.{ext}

To get STORAGE_PUBLIC_URL:
  Cloudflare Dashboard → R2 → your bucket → Settings
  → Public access → Enable R2.dev subdomain (free)
  → URL format: https://pub-XXXX.r2.dev
"""

import uuid
import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException, status

from app.core.config import settings

# Allowed image extensions
_ALLOWED_EXTS = {"jpg", "jpeg", "png", "webp", "gif"}
_CONTENT_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "gif": "image/gif",
}

# Valid asset folders
_VALID_FOLDERS = {"profiles", "teams", "venues", "matches", "misc"}


def _get_s3_client():
    """Return a boto3 S3 client configured for Cloudflare R2."""
    return boto3.client(
        "s3",
        endpoint_url=settings.STORAGE_ENDPOINT,
        aws_access_key_id=settings.STORAGE_ACCESS_KEY_ID,
        aws_secret_access_key=settings.STORAGE_SECRET_ACCESS_KEY,
        region_name="auto",          # R2 requires region="auto"
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},  # R2 uses path-style addressing
        ),
    )


def upload_image(
    contents: bytes,
    original_filename: str,
    folder: str,
    owner_id: int,
) -> str:
    """
    Upload raw image bytes to R2 and return the public URL.

    Args:
        contents:          Raw file bytes.
        original_filename: Original file name (used to extract extension).
        folder:            Asset category — one of: profiles, teams, venues, matches, misc.
        owner_id:          ID of the owning entity (user_id, team_id, venue_id, etc.).

    Returns:
        Public URL string: {STORAGE_PUBLIC_URL}/{folder}/{owner_id}/{uuid}.{ext}

    Raises:
        HTTPException 400 — unsupported file type.
        HTTPException 503 — R2 upload failed.
    """
    if folder not in _VALID_FOLDERS:
        folder = "misc"

    ext = (original_filename or "photo").rsplit(".", 1)[-1].lower()
    if ext not in _ALLOWED_EXTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported image type '.{ext}'. Allowed: {', '.join(sorted(_ALLOWED_EXTS))}",
        )

    key = f"{folder}/{owner_id}/{uuid.uuid4().hex}.{ext}"
    content_type = _CONTENT_TYPES.get(ext, "image/jpeg")

    try:
        client = _get_s3_client()
        client.put_object(
            Bucket=settings.STORAGE_BUCKET,
            Key=key,
            Body=contents,
            ContentType=content_type,
        )
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to upload image: {exc}",
        )

    public_url = f"{settings.STORAGE_PUBLIC_URL.rstrip('/')}/{key}"
    return public_url


def delete_image(public_url: str) -> None:
    """
    Delete an image from R2 using its public URL.
    Silently ignores errors (best-effort cleanup).

    Args:
        public_url: The public URL returned by upload_image().
    """
    base = settings.STORAGE_PUBLIC_URL.rstrip("/")
    if not public_url.startswith(base + "/"):
        return  # Not our bucket — skip

    key = public_url[len(base) + 1:]
    try:
        client = _get_s3_client()
        client.delete_object(Bucket=settings.STORAGE_BUCKET, Key=key)
    except (BotoCoreError, ClientError):
        pass  # Best-effort — don't fail the request


# ---------------------------------------------------------------------------
# Convenience wrappers (backwards-compatible)
# ---------------------------------------------------------------------------

def upload_profile_photo(contents: bytes, original_filename: str, user_id: int) -> str:
    """Upload a user profile photo. Returns public URL."""
    return upload_image(contents, original_filename, "profiles", user_id)


def upload_team_logo(contents: bytes, original_filename: str, team_id: int) -> str:
    """Upload a team logo. Returns public URL."""
    return upload_image(contents, original_filename, "teams", team_id)


def upload_venue_photo(contents: bytes, original_filename: str, venue_id: int) -> str:
    """Upload a venue photo. Returns public URL."""
    return upload_image(contents, original_filename, "venues", venue_id)


def upload_match_photo(contents: bytes, original_filename: str, match_id: int) -> str:
    """Upload a match-related image. Returns public URL."""
    return upload_image(contents, original_filename, "matches", match_id)

