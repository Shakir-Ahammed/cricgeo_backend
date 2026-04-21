"""
Cloudflare R2 object storage client.
Provides a single helper to upload a file and return its public URL.
"""

import uuid
import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException, status

from app.core.config import settings


def _get_s3_client():
    """Return a boto3 S3 client configured for Cloudflare R2."""
    return boto3.client(
        "s3",
        endpoint_url=settings.STORAGE_ENDPOINT,
        aws_access_key_id=settings.STORAGE_ACCESS_KEY_ID,
        aws_secret_access_key=settings.STORAGE_SECRET_ACCESS_KEY,
        region_name="auto",  # R2 requires region="auto"
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},  # R2 uses path-style
        ),
    )


def upload_profile_photo(contents: bytes, original_filename: str, user_id: int) -> str:
    """
    Upload raw image bytes to R2 under profiles/<user_id>/<uuid>.<ext>.
    Returns the public URL of the uploaded object.

    Raises HTTPException on failure.
    """
    ext = (original_filename or "photo").rsplit(".", 1)[-1].lower()
    if ext not in ("jpg", "jpeg", "png", "webp"):
        ext = "jpg"

    key = f"profiles/{user_id}/{uuid.uuid4().hex}.{ext}"

    content_type_map = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
    }

    try:
        client = _get_s3_client()
        client.put_object(
            Bucket=settings.STORAGE_BUCKET,
            Key=key,
            Body=contents,
            ContentType=content_type_map.get(ext, "image/jpeg"),
        )
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to upload image: {exc}",
        )

    # Public URL: STORAGE_PUBLIC_URL/<key>
    public_url = f"{settings.STORAGE_PUBLIC_URL.rstrip('/')}/{key}"
    return public_url
