"""Read-only access to the raw scraped posts/profiles in Postgres.

The service NEVER writes to Postgres. It reads brand posts + profiles, normalizes
the per-platform column differences into one shape, and hands them to the
enrichment pipeline. Credentials come from Secrets Manager, the same pattern as
the other services.
"""
import logging
from functools import lru_cache

from sqlalchemy import create_engine, text

from shared.database import db as shared_db
from services.food_intelligence_service.app.core.config import get_settings
from services.food_intelligence_service.app.enrichment.adapters import PLATFORM_CONFIG

settings = get_settings()
logger = logging.getLogger(__name__)


def _resolve_dsn(force_refresh: bool = False) -> str:
    """Credentials from Secrets Manager, the same source every other service
    reads. No DSN-from-environment branch: the RDS password rotates.
    """
    return shared_db.get_uri(force_refresh=force_refresh)


@lru_cache()
def _engine():
    return create_engine(_resolve_dsn(), pool_pre_ping=True, pool_size=3, max_overflow=2, pool_recycle=1800)


def _rows(sql: str, params: dict) -> list[dict]:
    with _engine().connect() as conn:
        result = conn.execute(text(sql), params)
        return [dict(r._mapping) for r in result]


def fetch_posts(platform: str, projects: list[str], limit: int | None = None) -> list[dict]:
    """Return brand posts for a platform, normalized to a common column set:
    post_id, account_username, text, posted_at, likes, comments, views, shares, bookmarks.
    """
    cfg = PLATFORM_CONFIG[platform]
    c = cfg["columns"]

    def col(logical: str, default_sql: str = "NULL"):
        physical = c.get(logical)
        return f"p.{physical}" if physical else default_sql

    select = f"""
        p.{c['post_id']}          AS post_id,
        p.{c['account_username']} AS account_username,
        p.{c['text']}             AS text,
        p.{c['posted_at']}        AS posted_at,
        {col('likes')}            AS likes,
        {col('comments')}         AS comments,
        {col('views')}            AS views,
        {col('shares')}           AS shares,
        {col('bookmarks')}        AS bookmarks,
        {col('post_url')}         AS post_url
    """
    sql = f"""
        SELECT {select}
        FROM {cfg['posts_table']} p
        JOIN {cfg['profile_table']} pr
          ON p.{c['account_username']} = pr.{cfg['profile_join_key']}
        WHERE pr.project = ANY(:projects)
        ORDER BY p.{c['posted_at']} DESC NULLS LAST
    """
    if limit:
        sql += " LIMIT :limit"
    return _rows(sql, {"projects": projects, "limit": limit})


def fetch_profiles(platform: str, projects: list[str]) -> list[dict]:
    """Return brand profiles for a platform, normalized to:
    account_username, name, followers, country, industry, is_verified.
    """
    cfg = PLATFORM_CONFIG[platform]
    p = cfg["profile_columns"]

    def col(logical: str, default_sql: str = "NULL"):
        physical = p.get(logical)
        return physical if physical else default_sql

    sql = f"""
        SELECT
            {p['username']}      AS account_username,
            {col('name')}        AS name,
            {col('followers')}   AS followers,
            {col('country')}     AS country,
            {col('industry')}    AS industry,
            {col('is_verified')} AS is_verified
        FROM {cfg['profile_table']}
        WHERE project = ANY(:projects)
    """
    return _rows(sql, {"projects": projects})
