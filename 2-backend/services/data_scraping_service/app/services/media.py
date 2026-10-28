import mimetypes
from pathlib import PurePosixPath
from urllib.parse import urlparse

import boto3
import requests
from botocore.exceptions import ClientError

from services.data_scraping_service.app.core.config import get_settings


def _extension(url: str, content_type: str) -> str:
    suffix = PurePosixPath(urlparse(url).path).suffix
    if suffix and len(suffix) <= 8:
        return suffix.lower()
    return mimetypes.guess_extension(content_type.split(";", 1)[0]) or ".bin"


def upload_post_thumbnail(url: str, post_id: str) -> tuple[str | None, str]:
    settings = get_settings()
    s3 = boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
    )
    try:
        with requests.get(url, stream=True, timeout=30) as response:
            response.raise_for_status()
            content_type = response.headers.get("content-type", "application/octet-stream")
            key = (
                f"{settings.INSTAGRAM_MEDIA_PREFIX.rstrip('/')}/"
                f"{post_id}{_extension(url, content_type)}"
            )
            try:
                s3.head_object(Bucket=settings.INSTAGRAM_MEDIA_BUCKET, Key=key)
                return key, "skipped"
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code")
                if code not in {"404", "NoSuchKey", "NotFound"}:
                    raise
            s3.upload_fileobj(
                response.raw,
                settings.INSTAGRAM_MEDIA_BUCKET,
                key,
                ExtraArgs={"ContentType": content_type},
            )
            return key, "uploaded"
    except Exception:
        return None, "failed"
