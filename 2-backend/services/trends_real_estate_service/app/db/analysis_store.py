import json
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
    into it is wrong the moment it does. shared.database owns the fetch and
    its five-minute TTL, so one cache serves the whole backend.
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
    """Drop the pool and rebuild it on freshly fetched credentials.

    Called after an authentication failure, which is what a rotation looks
    like from here. Without this the process would hold a pool built on the
    old password until someone restarted it.
    """
    global _engine
    with _engine_lock:
        if _engine is not None:
            _engine.dispose()
        _engine = create_engine(_resolve_dsn(force_refresh=True), pool_pre_ping=False,
                                pool_recycle=900, pool_size=10, max_overflow=5)
    logger.warning("Rebuilt the Postgres pool with refreshed credentials")


def run_query(sql: str, params: dict | None = None) -> list[dict]:
    """Run a read-only query.

    AUTOCOMMIT because connect() otherwise wraps even a plain SELECT in an
    implicit transaction and issues a ROLLBACK on the way out. Against an
    out-of-region database that pair costs two extra round trips - roughly
    400ms on a query whose own execution is about 260ms. Writes do not come
    through here; they take an explicit engine().begin() block.
    """
    try:
        return _execute(sql, params)
    except Exception as exc:
        if not _is_auth_error(exc):
            raise
        logger.warning("Auth error on read, refreshing credentials: %s", exc)
        reset_engine()
        return _execute(sql, params)


# No request-path query has a reason to run this long. A brand endpoint was
# measured at 42 seconds and never failed - it sat under the gateway's 320s
# timeout holding a pooled connection, so the only symptom was a hung panel.
# A ceiling turns that class of regression into an error someone sees.
STATEMENT_TIMEOUT = "30s"


def _execute(sql: str, params: dict | None) -> list[dict]:
    with engine().connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.exec_driver_sql(f"SET statement_timeout = '{STATEMENT_TIMEOUT}'")
        result = conn.execute(text(sql), params or {})
        return [dict(r._mapping) for r in result]


def post_already_enriched(post_id: str, platform: str) -> bool:
    rows = run_query(
        "SELECT 1 FROM realestate_intel.post_analysis "
        "WHERE post_id = :post_id AND platform = :platform LIMIT 1",
        {"post_id": post_id, "platform": platform},
    )
    return len(rows) > 0


def fetch_enrichment_state(platform: str) -> dict[str, list[str]]:
    """post_id -> the nodes that failed, for every stored row on this platform.

    One query instead of one per post, and it returns the failure list rather
    than a bare "exists" so the caller can tell a complete row from a partial
    one. A row where six of seven nodes failed used to count as done and was
    skipped on every later run, which is how a transient rate limit became
    permanent missing data.
    """
    rows = run_query(
        "SELECT post_id, COALESCE(analysis->'_failed_nodes', '[]'::jsonb) AS failed "
        "FROM realestate_intel.post_analysis WHERE platform = :platform",
        {"platform": platform},
    )
    return {r["post_id"]: list(r["failed"] or []) for r in rows}


_UPSERT_POST_ANALYSIS = text("""
    INSERT INTO realestate_intel.post_analysis (
        platform, post_id, brand_key, brand_name, account_type, account_username,
        caption, language, engagement, engagement_total,
        analysis, image_key, posted_at, processed_at, post_url
    ) VALUES (
        :platform, :post_id, :brand_key, :brand_name, :account_type, :account_username,
        :caption, :language, :engagement, :engagement_total,
        :analysis, :image_key, :posted_at, :processed_at, :post_url
    )
    ON CONFLICT (platform, post_id) DO UPDATE SET
        brand_key = EXCLUDED.brand_key, brand_name = EXCLUDED.brand_name,
        account_type = EXCLUDED.account_type, account_username = EXCLUDED.account_username,
        caption = EXCLUDED.caption, language = EXCLUDED.language,
        engagement = EXCLUDED.engagement, engagement_total = EXCLUDED.engagement_total,
        analysis = EXCLUDED.analysis, image_key = EXCLUDED.image_key,
        posted_at = EXCLUDED.posted_at, processed_at = EXCLUDED.processed_at,
        post_url = EXCLUDED.post_url
""")

def upsert_post_analysis(row: dict) -> None:
    payload = dict(row)
    payload["analysis"] = json.dumps(row["analysis"])
    payload["engagement"] = json.dumps(row.get("engagement") or {})

    try:
        with engine().begin() as conn:
            conn.execute(_UPSERT_POST_ANALYSIS, payload)
    except Exception as exc:
        # The reads refresh on an auth error and the write did not. A password
        # rotation mid-run therefore failed every write while the pipeline kept
        # spending seven LLM calls a post with nothing stored.
        if not _is_auth_error(exc):
            raise
        logger.warning("Auth error on write, refreshing credentials: %s", exc)
        reset_engine()
        with engine().begin() as conn:
            conn.execute(_UPSERT_POST_ANALYSIS, payload)


LIVE_PROFILE_SQL = """
    (SELECT DISTINCT ON (username)
            'instagram' AS platform, username, followers, country, industry, is_verified
     FROM public.instagram_profile
     ORDER BY username, followers DESC NULLS LAST)
    UNION ALL
    (SELECT DISTINCT ON (username)
            'tiktok' AS platform, username, followers, country, industry, verified
     FROM public.tiktok_profiles
     ORDER BY username, followers DESC NULLS LAST)
"""


BRAND_ACCOUNTS_SQL = """
    SELECT brand_key, MIN(brand_name) AS brand_name, platform, account_username,
           MAX(processed_at) AS updated_at
    FROM realestate_intel.post_analysis
    WHERE account_username IS NOT NULL
    GROUP BY brand_key, platform, account_username
"""


def fetch_brand_profiles(brand_key: str) -> list[dict]:
    return run_query(f"""
        SELECT bp.brand_key, bp.brand_name, bp.platform, bp.account_username, bp.updated_at,
               lp.followers, lp.country, lp.industry, lp.is_verified
        FROM ({BRAND_ACCOUNTS_SQL}) bp
        LEFT JOIN ({LIVE_PROFILE_SQL}) lp
          ON lp.platform = bp.platform AND lp.username = bp.account_username
        WHERE bp.brand_key = :brand_key
    """, {"brand_key": brand_key})
