import ssl
from contextlib import asynccontextmanager
from urllib.parse import quote_plus

from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.exc import OperationalError

from gateway.app.core.config import get_settings
from gateway.app.core.security import get_db_secret, invalidate_db_secret
from shared.logger import get_logger

logger = get_logger("uvicorn.error")
settings = get_settings()

_engine: AsyncEngine | None = None


def _build_ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _async_dsn(dsn: str) -> URL:
    url = make_url(dsn)
    if url.drivername in ("postgresql", "postgres") or url.drivername.startswith("postgresql+"):
        url = url.set(drivername="postgresql+asyncpg")
    if settings.DB_ADMIN:
        url = url.set(database=settings.DB_ADMIN)
    return url.difference_update_query(["sslmode"])


def _build_engine() -> AsyncEngine | None:
    if settings.POSTGRES_DSN:
        url = _async_dsn(settings.POSTGRES_DSN)
        logger.info(f"Using POSTGRES_DSN for the gateway database connection (database={url.database})")
        return create_async_engine(
            url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            pool_recycle=1800,
        )

    if not settings.DB_ADMIN or not settings.DB_HOST:
        return None

    secret = get_db_secret()
    if not secret:
        return None

    user = secret.get("username")
    password = secret.get("password")
    if not user or not password:
        raise RuntimeError("DB credentials missing in secret")

    safe_user = quote_plus(str(user))
    safe_password = quote_plus(str(password))
    url = (
        f"postgresql+asyncpg://{safe_user}:{safe_password}"
        f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_ADMIN}"
    )
    return create_async_engine(
        url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_recycle=1800,
        connect_args={"ssl": _build_ssl_context()},
    )


def get_engine() -> AsyncEngine | None:
    global _engine
    if _engine is None:
        _engine = _build_engine()
    return _engine


async def reset_engine() -> AsyncEngine | None:
    """Dispose current engine, refresh credentials, rebuild."""
    global _engine
    logger.warning("Resetting DB engine with fresh credentials")
    if _engine:
        await _engine.dispose()
        _engine = None
    invalidate_db_secret()
    get_db_secret(force_refresh=True)
    _engine = _build_engine()
    return _engine


def _is_auth_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "password authentication failed" in msg or "invalid password" in msg


@asynccontextmanager
async def get_db_conn():
    """
    Async context manager for a DB connection with automatic credential
    refresh on auth failures. Retries once after re-fetching the secret.
    """
    engine = get_engine()
    try:
        async with engine.connect() as conn:
            yield conn
    except (OperationalError, Exception) as exc:
        if not _is_auth_error(exc):
            raise
        logger.warning(f"Auth failure detected ({exc!r}) — refreshing credentials and retrying")
        engine = await reset_engine()
        async with engine.connect() as conn:
            yield conn
