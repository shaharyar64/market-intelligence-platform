import json
import os
import zlib
import hashlib
from shared.redis import ensure_redis
from shared.logger import get_logger

logger = get_logger("uvicorn.error")

CACHE_TTL_30_MIN = 1800
CACHE_TTL_5_MIN = 300

# Namespace all keys by environment so dev/staging/prod never collide
_ENV = os.getenv("ENV_NAME", "dev")


def _make_cache_key(prefix: str, filters: dict) -> str:
    serialized = json.dumps(filters, sort_keys=True, default=str)
    digest = hashlib.md5(serialized.encode()).hexdigest()
    return f"{_ENV}:{prefix}:{digest}"


def _compress(data: dict) -> bytes:
    return zlib.compress(json.dumps(data, default=str).encode(), level=6)


def _decompress(raw: bytes) -> dict:
    return json.loads(zlib.decompress(raw).decode())


async def get_cached(key: str) -> dict | None:
    redis = await ensure_redis()
    if not redis:
        return None
    try:
        value = await redis.get(key)
        if value:
            logger.info(f"Cache hit [redis] [{key}]")
            return _decompress(value)
    except Exception as e:
        logger.error(f"Redis get error [{key}]: {e}")
    return None


async def set_cached(key: str, data: dict, ttl: int = CACHE_TTL_30_MIN) -> None:
    redis = await ensure_redis()
    if not redis:
        logger.warning(f"Redis unavailable — skipping cache for [{key}]")
        return
    try:
        await redis.set(key, _compress(data), ex=ttl)
        logger.info(f"Cached [redis] [{key}] for {ttl}s")
    except Exception as e:
        logger.error(f"Redis set error [{key}]: {e}")


async def cache_query(prefix: str, filters: dict, fetcher, ttl: int = CACHE_TTL_30_MIN):
    key = _make_cache_key(prefix, filters)
    cached = await get_cached(key)
    if cached is not None:
        return cached
    data = await fetcher()
    normalized = json.loads(json.dumps(data, default=str))
    await set_cached(key, normalized, ttl)
    return normalized
