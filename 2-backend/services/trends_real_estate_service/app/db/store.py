import logging
import threading

from sqlalchemy import create_engine, text

from shared.database import _is_auth_error
from shared.database import db as shared_db

logger = logging.getLogger(__name__)

_engine = None
_engine_lock = threading.Lock()


def _resolve_dsn(force_refresh: bool = False) -> str:
    """Credentials come from Secrets Manager, the same source every other
    service reads. There is deliberately no DSN-from-environment branch: the
    RDS password rotates, so a connection string with the password written
    into it is wrong the moment it does.
    """
    return shared_db.get_uri(force_refresh=force_refresh)


def engine():
    global _engine
    with _engine_lock:
        if _engine is None:
            _engine = create_engine(_resolve_dsn(), pool_pre_ping=False,
                                    pool_recycle=900, pool_size=10, max_overflow=5)
        return _engine


def reset_engine() -> None:
    """Drop the pool and rebuild it on freshly fetched credentials. Called
    after an auth failure, which is what a password rotation looks like from
    here."""
    global _engine
    with _engine_lock:
        if _engine is not None:
            _engine.dispose()
        _engine = create_engine(_resolve_dsn(force_refresh=True), pool_pre_ping=False,
                                pool_recycle=900, pool_size=10, max_overflow=5)
    logger.warning("Rebuilt the Postgres pool with refreshed credentials")


def run_query(sql: str, params: dict | None = None) -> list[dict]:
    """Run a read-only query. AUTOCOMMIT because connect() otherwise wraps
    even a plain SELECT in an implicit transaction and issues a ROLLBACK on
    the way out, costing two extra round trips to an out-of-region database.
    """
    try:
        return _execute(sql, params)
    except Exception as exc:
        if not _is_auth_error(exc):
            raise
        logger.warning("Auth error on read, refreshing credentials: %s", exc)
        reset_engine()
        return _execute(sql, params)


def _execute(sql: str, params: dict | None) -> list[dict]:
    with engine().connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        result = conn.execute(text(sql), params or {})
        return [dict(r._mapping) for r in result]
