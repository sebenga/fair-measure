"""Object storage behind a single interface.

Cloudflare R2 and AWS S3 both speak the S3 API, so one boto3 client covers both;
the only difference is the endpoint and the region. Swapping providers is a
change to `STORAGE_PROVIDER` and the credentials, not a change to any code that
stores files.
"""

from __future__ import annotations

import mimetypes
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache

import boto3
from botocore.client import Config
from django.conf import settings
from rest_framework.exceptions import ValidationError

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/heic"}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/webm", "video/x-matroska"}


@dataclass(slots=True)
class SignedUpload:
    upload_url: str
    method: str
    key: str
    headers: dict[str, str]
    expires_in: int


@lru_cache(maxsize=1)
def get_s3_client():
    if not settings.STORAGE_ACCESS_KEY_ID or not settings.STORAGE_SECRET_ACCESS_KEY:
        raise ValidationError(
            "Object storage is not configured. Set STORAGE_ACCESS_KEY_ID and "
            "STORAGE_SECRET_ACCESS_KEY."
        )

    return boto3.client(
        "s3",
        endpoint_url=settings.STORAGE_ENDPOINT_URL or None,
        region_name=settings.STORAGE_REGION or "auto",
        aws_access_key_id=settings.STORAGE_ACCESS_KEY_ID,
        aws_secret_access_key=settings.STORAGE_SECRET_ACCESS_KEY,
        # R2 requires SigV4 and rejects the default virtual-host addressing.
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def build_key(prefix: str, filename: str) -> str:
    """Date-partitioned, collision-proof key. Never trusts the client's filename."""

    suffix = ""
    if "." in filename:
        candidate = filename.rsplit(".", 1)[-1].lower()
        if candidate.isalnum() and len(candidate) <= 5:
            suffix = f".{candidate}"

    stamp = datetime.now(tz=UTC).strftime("%Y/%m/%d")
    return f"{prefix}/{stamp}/{uuid.uuid4().hex}{suffix}"


def validate_upload(kind: str, content_type: str, size_bytes: int | None) -> str:
    resolved = content_type or mimetypes.guess_type(f"x.{kind}")[0] or ""
    allowed = ALLOWED_IMAGE_TYPES if kind == "image" else ALLOWED_VIDEO_TYPES

    if resolved not in allowed:
        raise ValidationError(
            {"content_type": f"'{resolved}' is not an accepted {kind} type."}
        )
    if size_bytes is not None and size_bytes > settings.MAX_UPLOAD_BYTES:
        limit_mb = settings.MAX_UPLOAD_BYTES // (1024 * 1024)
        raise ValidationError({"size_bytes": f"Files must be {limit_mb} MB or smaller."})
    return resolved


def create_presigned_upload(key: str, content_type: str) -> SignedUpload:
    ttl = settings.STORAGE_UPLOAD_URL_TTL_SECONDS
    url = get_s3_client().generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": settings.STORAGE_BUCKET,
            "Key": key,
            "ContentType": content_type,
        },
        ExpiresIn=ttl,
    )
    return SignedUpload(
        upload_url=url,
        method="PUT",
        key=key,
        headers={"Content-Type": content_type},
        expires_in=ttl,
    )


def create_presigned_download(key: str, ttl: int = 3600) -> str:
    """For private buckets. Public buckets should use STORAGE_PUBLIC_BASE_URL."""

    return get_s3_client().generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": settings.STORAGE_BUCKET, "Key": key},
        ExpiresIn=ttl,
    )


def head_object(key: str) -> dict | None:
    """Confirm an upload actually landed, and read back its real size and type."""

    try:
        response = get_s3_client().head_object(Bucket=settings.STORAGE_BUCKET, Key=key)
    except Exception:
        return None
    return {
        "size_bytes": response.get("ContentLength"),
        "content_type": response.get("ContentType", ""),
    }


def delete_object(key: str) -> None:
    get_s3_client().delete_object(Bucket=settings.STORAGE_BUCKET, Key=key)
