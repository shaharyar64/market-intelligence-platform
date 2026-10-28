"""Resolves a Cognito sub to a display-friendly email, for the Knowledge
Base's uploaded_by field only. Never used as a query/filter key.
"""
import logging

import psycopg2

from shared.database import db as shared_db

logger = logging.getLogger(__name__)


def resolve_email(sub: str) -> str | None:
    conn = None
    try:
        dsn = shared_db.get_uri(override_db="dashboards").replace(
            "postgresql+psycopg2://", "postgresql://")
        conn = psycopg2.connect(dsn, connect_timeout=3)
        with conn.cursor() as cur:
            cur.execute("SELECT email FROM public.users WHERE cognito_sub = %(sub)s", {"sub": sub})
            row = cur.fetchone()
        return row[0] if row else None
    except Exception:
        logger.warning("resolve_email failed for sub %s", sub, exc_info=True)
        return None
    finally:
        if conn is not None:
            conn.close()
