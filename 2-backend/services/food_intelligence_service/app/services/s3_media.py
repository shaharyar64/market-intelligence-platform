import logging
from functools import lru_cache

import boto3
from botocore.exceptions import ClientError

from services.food_intelligence_service.app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


@lru_cache()
def _client():
    return boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
    )


def _key(platform: str, post_id: str) -> str:
    prefix = settings.FOOD_MEDIA_S3_PREFIX_TEMPLATE.format(platform=platform)
    return f"{prefix}{post_id}.jpg"


_MISSING_CODES = ("404", "NoSuchKey", "NoSuchBucket")
_DENIED_CODES = ("403", "AccessDenied", "AllAccessDisabled", "InvalidAccessKeyId", "SignatureDoesNotMatch")


def resolve_image_key(platform: str, post_id: str) -> str | None:
    key = _key(platform, post_id)
    try:
        _client().head_object(Bucket=settings.FOOD_MEDIA_S3_BUCKET, Key=key)
        return key
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code")
        if code in _MISSING_CODES:
            return None
        if code in _DENIED_CODES:
            logger.warning(
                f"S3 access denied resolving {key} (code {code}). "
                f"Treating the image as unavailable so text analysis can continue. "
                f"Check the IAM policy on the bucket if this repeats."
            )
            return None
        raise


def presigned_url(image_key: str, expires_in: int = 900) -> str:
    """Presign an image for the vision node.

    A key may name its own bucket as "s3://bucket/key", the same convention the
    trend API uses. Brand and influencer crawls left their images in the raw
    bucket, but the community scrape migrated its media to the trends bucket, so
    enriching a consumer post means reading from a different bucket than a brand
    post. A bare key still means the raw bucket.
    """
    bucket, key = settings.FOOD_MEDIA_S3_BUCKET, image_key
    if image_key.startswith("s3://"):
        bucket, _, key = image_key[len("s3://"):].partition("/")
    return _client().generate_presigned_url(
        "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=expires_in,
    )
