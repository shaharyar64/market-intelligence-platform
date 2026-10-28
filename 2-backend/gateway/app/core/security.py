import json
import time
import boto3
from botocore.exceptions import ClientError
from gateway.app.core.config import get_settings
from shared.logger import get_logger

logger = get_logger("uvicorn.error")

_SECRET_TTL = 300  # 5 minutes
_secret_cache: dict | None = None
_secret_fetched_at: float = 0


def _fetch_from_aws() -> dict | None:
    settings = get_settings()
    if not settings.SECRET_NAME:
        return None
    try:
        client = boto3.client(
            "secretsmanager",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )
        response = client.get_secret_value(SecretId=settings.SECRET_NAME)
        secret_str = response.get("SecretString")
        return json.loads(secret_str) if secret_str else None
    except ClientError as exc:
        raise RuntimeError(f"Failed to fetch secret '{settings.SECRET_NAME}': {exc}")


def get_db_secret(force_refresh: bool = False) -> dict | None:
    """Fetch DB credentials from AWS Secrets Manager with 5-min TTL cache."""
    global _secret_cache, _secret_fetched_at
    now = time.monotonic()
    if force_refresh or _secret_cache is None or (now - _secret_fetched_at) > _SECRET_TTL:
        logger.info("Fetching DB secret from Secrets Manager")
        _secret_cache = _fetch_from_aws()
        _secret_fetched_at = now
    return _secret_cache


def invalidate_db_secret() -> None:
    """Force next call to re-fetch from Secrets Manager."""
    global _secret_cache, _secret_fetched_at
    _secret_cache = None
    _secret_fetched_at = 0
    logger.info("DB secret cache invalidated")
