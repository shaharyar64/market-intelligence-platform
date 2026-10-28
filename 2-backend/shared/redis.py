import time
import redis.asyncio as aioredis
from shared.logger import get_logger

logger = get_logger("uvicorn.error")

_redis_client: aioredis.Redis | None = None
_redis_host: str | None = None
_redis_password: str | None = None
_last_failed_at: float = 0
_RETRY_INTERVAL = 30  # seconds between reconnect attempts


def _build_redis_url(host: str, password: str | None) -> str:
    if password:
        return f"redis://:{password}@{host}"
    return f"redis://{host}"


async def _try_connect() -> aioredis.Redis | None:
    global _redis_client, _last_failed_at
    if not _redis_host:
        return None
    try:
        client = aioredis.from_url(
            _build_redis_url(_redis_host, _redis_password),
            decode_responses=False,
            socket_connect_timeout=5,
            socket_timeout=30,
        )
        await client.ping()
        _redis_client = client
        _last_failed_at = 0
        logger.info("Redis client connected")
        return _redis_client
    except Exception as err:
        _last_failed_at = time.monotonic()
        _redis_client = None
        logger.error(f"Redis connection failed. Continuing without Redis. - {err}")
        return None


def get_redis_client() -> aioredis.Redis | None:
    return _redis_client


async def ensure_redis() -> aioredis.Redis | None:
    """Return Redis client, reconnecting if the existing connection is stale."""
    global _redis_client
    if _redis_client:
        try:
            await _redis_client.ping()
            return _redis_client
        except Exception:
            _redis_client = None
    if not _redis_host:
        return None
    if time.monotonic() - _last_failed_at < _RETRY_INTERVAL:
        return None
    logger.info(f"Retrying Redis connection to {_redis_host}")
    return await _try_connect()


async def connect_redis(host: str, password: str | None = None) -> None:
    global _redis_host, _redis_password
    _redis_host = host
    _redis_password = password
    logger.info(f"Connecting to Redis at {host}")
    await _try_connect()


async def disconnect_redis() -> None:
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None
        logger.warning("Redis client disconnected")
