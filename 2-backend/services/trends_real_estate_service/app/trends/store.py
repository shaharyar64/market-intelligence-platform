"""All Postgres I/O for the trend pipeline. Single seam: get_conn().

Vectors cross the wire as '[f1,f2,...]' text with a ::vector cast — no
pgvector python dependency needed.
"""
import contextlib
import io
import json
import logging
import threading
import time
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
import psycopg2.pool
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("trends.store")

_pool: psycopg2.pool.ThreadedConnectionPool | None = None
_pool_lock = threading.Lock()


def _dsn(force_refresh: bool = False) -> str:
    """psycopg2 DSN, built from the same Secrets Manager credentials the rest
    of the backend uses. psycopg2 wants the bare `postgresql://` scheme, so the
    SQLAlchemy driver suffix is stripped; nothing else differs.
    """
    from services.trends_real_estate_service.app.db.analysis_store import _resolve_dsn
    return _resolve_dsn(force_refresh).replace("postgresql+psycopg2://", "postgresql://")


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    """Connections are pooled: opening one costs a full round trip to RDS
    (~500ms from outside the VPC), and every request used to pay it."""
    global _pool
    with _pool_lock:
        if _pool is None:
            last: Exception | None = None
            for attempt in range(5):
                try:
                    # Sized for the web service, not the batch pipeline it was
                    # first written for. One assistant question can hold several
                    # at once - the session read, two parallel context lookups,
                    # and however many tools the agent runs concurrently - so a
                    # ceiling of 8 was exhausted by a single user's
                    # conversation, and the failure surfaced as "I don't have
                    # any data on that".
                    _pool = psycopg2.pool.ThreadedConnectionPool(
                        1, 32, _dsn(), connect_timeout=20)
                    break
                except psycopg2.OperationalError as exc:   # flaky local DNS
                    last = exc
                    wait = 2 ** attempt
                    logger.warning("pool init failed (attempt %s/5, retry in %ss): %s",
                                   attempt + 1, wait, exc)
                    time.sleep(wait)
            if _pool is None:
                raise last or RuntimeError(
                    "connection pool could not be created and no error was recorded")
        return _pool


def reset_pool() -> None:
    """Throw the pool away so the next borrow dials a fresh connection.

    A connection idle through a long batch can be closed by RDS without the
    client noticing: psycopg2 still reports it as open, and the next statement
    dies with "server closed the connection unexpectedly". Recycling the whole
    pool is the only reliable recovery, since sibling connections are usually
    just as stale.
    """
    global _pool
    with _pool_lock:
        if _pool is not None:
            try:
                _pool.closeall()
            except Exception:
                logger.warning("closing the connection pool failed", exc_info=True)
            _pool = None


@contextmanager
def get_conn():
    """Borrow a pooled connection, commit on success, roll back on error, and
    always hand it back.

    psycopg2's own `with connection` commits but does NOT close or release, so
    the previous `with get_conn()` usage leaked one connection per call.
    """
    pool = _get_pool()
    conn = pool.getconn()
    if conn.closed:                       # socket died while idle in the pool
        pool.putconn(conn, close=True)
        conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        # A failed rollback must not replace the exception being propagated -
        # the caller needs the original error, not the cleanup's.
        with contextlib.suppress(psycopg2.Error):
            conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def _rows_as_dicts(cur) -> list[dict]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]


def model_tag(model: str, dim: int, variant: str | None = None) -> str:
    """The key embeddings are stored under.

    A variant suffix keeps a re-embedding run from colliding with the vectors
    already stored: save_embeddings is ON CONFLICT DO NOTHING, so re-embedding
    under the same tag silently discards every new vector and the run appears to
    have changed nothing. It also lets the old and new vectors sit side by side,
    so the assistant keeps answering from the current set while a new one builds.
    """
    if variant is None:
        from services.trends_real_estate_service.app.core.config import get_settings
        variant = get_settings().TREND_EMBED_VARIANT
    suffix = f"+{variant}" if variant else ""
    return f"{model}@{dim}{suffix}"


def _cohort_clause(cohort: str) -> tuple[str, list]:
    """cohort 'all' means every row in trend_posts (no cohort filter)."""
    if cohort == "all":
        return "TRUE", []
    return "p.cohort = %s", [cohort]


def fetch_posts_missing_embeddings(cohort: str, tag: str, limit: int | None = None) -> list[dict]:
    clause, cparams = _cohort_clause(cohort)
    sql = f"""
        SELECT p.platform, p.post_id, p.caption, p.hashtags
        FROM realestate_intel.trend_posts p
        WHERE {clause} AND p.caption IS NOT NULL AND p.caption <> ''
          AND NOT EXISTS (SELECT 1 FROM realestate_intel.post_embedding e
                          WHERE e.platform = p.platform AND e.post_id = p.post_id
                            AND e.model = %s)
        ORDER BY p.posted_at DESC
    """
    params: list = [*cparams, tag]
    if limit:
        sql += " LIMIT %s"
        params.append(limit)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return _rows_as_dicts(cur)


_ANALYSED = """(jsonb_array_length(coalesce(pa.analysis->'themes', '[]'::jsonb)) > 0
                OR coalesce(pa.analysis->>'description', '') <> '')"""


def fetch_documents_to_embed(tag: str, limit: int | None = None) -> list[dict]:
    sql = f"""
        SELECT pa.platform, pa.post_id, pa.analysis
          FROM realestate_intel.post_analysis pa
          LEFT JOIN realestate_intel.post_embedding e
            ON e.platform = pa.platform AND e.post_id = pa.post_id AND e.model = %s
         WHERE {_ANALYSED}
           AND (e.post_id IS NULL OR e.created_at < pa.processed_at)
         ORDER BY pa.processed_at DESC
    """
    params: list = [tag]
    if limit:
        sql += " LIMIT %s"
        params.append(limit)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return _rows_as_dicts(cur)


def fetch_analyses() -> dict[tuple[str, str], dict]:
    sql = f"""
        SELECT pa.platform, pa.post_id,
               jsonb_build_object('description', pa.analysis->'description',
                                  'themes', pa.analysis->'themes',
                                  'offering_focus', pa.analysis->'offering_focus',
                                  'semiotic', pa.analysis->'semiotic',
                                  'functional_visual', pa.analysis->'functional_visual')
          FROM realestate_intel.post_analysis pa
         WHERE {_ANALYSED}
    """
    out: dict[tuple[str, str], dict] = {}
    with get_conn() as conn, conn.cursor(name="analyses") as cur:
        cur.itersize = 4000
        cur.execute(sql)
        for platform, post_id, analysis in cur:
            out[(platform, post_id)] = analysis if isinstance(analysis, dict) else json.loads(analysis)
    return out


def save_embeddings(rows: list[tuple[str, str, str, list[float]]],
                    chunk_size: int = 1000, replace: bool = False) -> int:
    """rows: (platform, post_id, model_tag, vector).

    Uses COPY into a temp table then an upsert. execute_values sent one
    multi-megabyte INSERT per batch, which crawled across the WAN to RDS;
    COPY streams instead and is several times faster for bulk vectors.
    """
    if not rows:
        return 0
    conflict = ("ON CONFLICT (platform, post_id, model) DO UPDATE "
                "SET embedding = EXCLUDED.embedding, created_at = now()"
                if replace else "ON CONFLICT DO NOTHING")
    with get_conn() as conn:
        for start in range(0, len(rows), chunk_size):
            chunk = rows[start:start + chunk_size]
            buf = io.StringIO()
            for platform, post_id, tag, vec in chunk:
                vector = "[" + ",".join(f"{v:.6f}" for v in vec) + "]"
                buf.write(f"{platform}\t{post_id}\t{tag}\t{vector}\n")
            buf.seek(0)
            with conn.cursor() as cur:
                cur.execute("""CREATE TEMP TABLE IF NOT EXISTS _emb_stage
                               (platform text, post_id text, model text, embedding vector(1024))
                               ON COMMIT DROP""")
                cur.copy_expert(
                    "COPY _emb_stage (platform, post_id, model, embedding) FROM STDIN", buf)
                cur.execute(f"""INSERT INTO realestate_intel.post_embedding
                                    (platform, post_id, model, embedding)
                                SELECT platform, post_id, model, embedding FROM _emb_stage
                                {conflict}""")
                cur.execute("TRUNCATE _emb_stage")
            conn.commit()
    return len(rows)


def count_community_posts(cohort: str) -> int:
    clause, cparams = _cohort_clause(cohort)
    sql = f"""
        SELECT count(*) FROM realestate_intel.trend_posts p
        WHERE {clause} AND p.source = 'community'
          AND p.caption IS NOT NULL AND p.caption <> ''
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, cparams)
        return cur.fetchone()[0]


def sample_predicate(cohort: str, sample: int | None,
                     threshold: int | None = None) -> tuple[str, list]:
    """A deterministic community subset that every stage resolves identically.

    Trends are discovered from a sample, so clustering and metrics
    must agree on exactly which posts are in it — otherwise metrics count posts
    that were never clustered. Selection is a hash of the post's identity, so it
    depends on nothing but the post itself: no ORDER BY, no LIMIT, no physical
    row order. An earlier LIMIT-based version returned 86% Instagram from a
    corpus that is 58% Instagram, because it truncated in scan order.

    The threshold always derives from the community count, never from the
    caller's own source filter, so a caller asking for every source picks the
    same community posts as one asking for community alone. Brand and
    influencer rows are never sampled — they are the tracked accounts only,
    ~4.4k relevant posts, and trends need all of them.
    """
    if not sample and threshold is None:
        return "", []
    if threshold is None:
        # `sample` is truthy here: the guard above returned when it was not.
        threshold = resolve_sample_threshold(cohort, int(sample or 0))
    return (" AND (p.source <> 'community' OR "
            "('x' || substr(md5(p.platform || p.post_id), 1, 8))::bit(32)::bigint < %s)",
            [threshold])


def resolve_sample_threshold(cohort: str, sample: int) -> int:
    """The hash cut-off that admits about `sample` community posts today.

    Derived from the current corpus size, so it moves whenever the corpus does.
    A run that resolves it once and records it can be re-run months later on
    exactly the posts it first saw; a run that resolves it afresh each stage
    cannot. Re-running the demo50k metrics after 16,887 posts were relabelled
    would have dropped 1,502 already-clustered posts out of the sample.
    """
    total = count_community_posts(cohort)
    fraction = min(1.0, sample / total) if total else 1.0
    return int(fraction * 2**32)


def fetch_cohort_captions(cohort: str, sources: list[str] | None = None,
                          sample: int | None = None,
                          itersize: int = 20000,
                          sample_threshold: int | None = None) -> list[dict]:
    """platform, post_id and caption only — no embedding join.

    Sentiment reads captions and nothing else; going through
    fetch_cohort_posts made it drag ~5GB of vectors across the wire at
    roughly 50 rows/s for data it never touches.
    """
    clause, cparams = _cohort_clause(cohort)
    src_clause = ""
    if sources:
        src_clause = " AND p.source = ANY(%s)"
        cparams = [*cparams, sources]
    smp_clause, sparams = sample_predicate(cohort, sample, sample_threshold)
    sql = f"""
        SELECT p.platform, p.post_id, p.caption
        FROM realestate_intel.trend_posts p
        WHERE {clause}{src_clause}
          AND p.caption IS NOT NULL AND p.caption <> ''
          {smp_clause}
    """
    cparams = [*cparams, *sparams]
    rows: list[dict] = []
    with get_conn() as conn, conn.cursor(name="cohort_captions") as cur:
        cur.itersize = itersize
        cur.execute(sql, cparams)
        while True:
            batch = cur.fetchmany(itersize)
            if not batch:
                break
            rows.extend({"platform": p, "post_id": i, "caption": c}
                        for p, i, c in batch)
    return rows


def count_cohort_posts(cohort: str, tag: str,
                       sources: list[str] | None = None) -> int:
    clause, cparams = _cohort_clause(cohort)
    src_clause = ""
    if sources:
        src_clause = " AND p.source = ANY(%s)"
        cparams = [*cparams, sources]
    sql = f"""
        SELECT count(*) FROM realestate_intel.trend_posts p
        WHERE {clause}{src_clause}
          AND p.caption IS NOT NULL AND p.caption <> ''
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, cparams)
        return cur.fetchone()[0]


# The market of a tracked account, from its own profile, as an ISO code.
#
# trend_posts.country is NULL on every post the community scrape found, and that
# includes the 16.9k it relabels as brand because a tracked developer wrote them.
# Every tracked profile carries a country, so the account is where it comes from.
# Joined on (platform, username) first and on username alone second: meraasdubai
# posts on Instagram but has a profile only on X, and its Instagram posts would
# otherwise have no market.
ACCOUNT_COUNTRY_CTE = """
acct_raw AS (
    SELECT 'instagram' AS platform, lower(ltrim(username, '@')) AS username,
           country, project FROM public.instagram_profile
    UNION ALL SELECT 'tiktok', lower(ltrim(username::text, '@')), country::text, project::text
      FROM public.tiktok_profiles
    UNION ALL SELECT 'twitter', lower(ltrim(username, '@')), country, project
      FROM public.twitter_profiles
    UNION ALL SELECT 'linkedin', lower(ltrim(universal_name, '@')), country, project::text
      FROM public.linkedin_profiles
), acct AS (
    SELECT platform, username,
           min(CASE upper(btrim(country)) WHEN 'KSA' THEN 'SA' WHEN 'UAE' THEN 'AE' END) AS cc
      FROM acct_raw
     WHERE project IN ('realestate_dbh', 'realestate_trends', 'realestate_trends_influencers')
     GROUP BY 1, 2
), acct_any AS (
    SELECT username, min(cc) AS cc FROM acct GROUP BY 1
)"""
POST_COUNTRY = "COALESCE(p.country, ac.cc, aa.cc)"
ACCOUNT_COUNTRY_JOIN = """
        LEFT JOIN acct ac ON ac.platform = p.platform AND ac.username = p.author_username
        LEFT JOIN acct_any aa ON aa.username = p.author_username"""


def fetch_cohort_posts(cohort: str, tag: str,
                       sources: list[str] | None = None,
                       itersize: int = 5000,
                       sample: int | None = None,
                       seed: float = 0.42,
                       sample_threshold: int | None = None,
                       date_from: str | None = None,
                       date_to: str | None = None,
                       exclude_containers: list[str] | None = None,
                       country: str | None = None,
                       exclude_authors: list[str] | None = None) -> list[dict]:
    """Posts joined to their embeddings — the pipeline working set.

    Streamed through a server-side cursor and left unordered on purpose: at
    540k rows each carrying a 1024-dim vector, an ORDER BY spills roughly 5GB
    of temp file and exhausted the RDS instance's disk. Nothing downstream
    depends on row order. Vectors land as float32 arrays rather than Python
    lists, which is about four times smaller.

    country scopes the set to one market ('AE' or 'SA'), resolved per post as
    POST_COUNTRY. exclude_authors drops accounts that sit on a tracked list
    without being in the category (a motorsport event, a charity).
    """
    import numpy as np

    clause, cparams = _cohort_clause(cohort)
    src_clause = ""
    if sources:
        src_clause = " AND p.source = ANY(%s)"
        cparams = [*cparams, sources]
    if country:
        src_clause += f" AND {POST_COUNTRY} = %s"
        cparams = [*cparams, country]
    if exclude_authors:
        src_clause += " AND NOT (p.author_username = ANY(%s))"
        cparams = [*cparams, [a.lower() for a in exclude_authors]]
    if date_from:
        src_clause += " AND p.posted_at >= %s"
        cparams = [*cparams, date_from]
    if date_to:
        src_clause += " AND p.posted_at < %s"
        cparams = [*cparams, date_to]
    if exclude_containers:
        src_clause += (" AND NOT EXISTS (SELECT 1 FROM public.community_posts cx"
                       " WHERE cx.platform = p.platform AND cx.post_id = p.post_id"
                       " AND cx.source_container = ANY(%s))")
        cparams = [*cparams, exclude_containers]
    sql = f"""
        WITH {ACCOUNT_COUNTRY_CTE}
        SELECT p.platform, p.post_id, p.source, p.caption, p.hashtags, p.posted_at,
               p.author_username, p.engagement_total, p.likes, p.comments,
               p.views, p.media_keys, p.post_url, {POST_COUNTRY} AS country,
               e.embedding::text AS vec
        FROM realestate_intel.trend_posts p
        JOIN realestate_intel.post_embedding e
          ON e.platform = p.platform AND e.post_id = p.post_id AND e.model = %s
        {ACCOUNT_COUNTRY_JOIN}
        WHERE {clause}{src_clause}
    """
    smp_clause, sparams = sample_predicate(cohort, sample, sample_threshold)
    sql += smp_clause
    params: list = [tag, *cparams, *sparams]
    rows: list[dict] = []
    with get_conn() as conn, conn.cursor(name="cohort_posts") as cur:
        cur.itersize = itersize
        cur.execute(sql, params)
        cols: list[str] | None = None
        vec_at = 0
        while True:
            batch = cur.fetchmany(itersize)
            if not batch:
                break
            if cols is None:
                cols = [d[0] for d in cur.description]
                vec_at = cols.index("vec")
            for record in batch:
                row = dict(zip(cols, record, strict=True))
                row["vec"] = np.array(record[vec_at][1:-1].split(","), dtype=np.float32)
                rows.append(row)
    return rows


def count_brand_accounts(country: str | None = None) -> int:
    """Brands the platform monitors — the canonical registry, not a count of
    scraped accounts.

    This used to count DISTINCT author_username where source='brand', which
    returned 4,261: the upstream scraper labels many personal creator accounts
    as 'brand', and 80% of them appeared only once in the corpus. That number
    described scrape composition, not a tracked brand roster.

    With a country, only brands with an account in that market count, so a KSA
    run does not report the UAE's developers as tracked. Brands whose accounts
    are excluded from trends (TREND_EXCLUDE_AUTHORS) are not counted either:
    the figure sits next to trends those accounts no longer feed.
    """
    from services.trends_real_estate_service.app.core.config import get_settings
    excluded = [a.lower() for a in get_settings().TREND_EXCLUDE_AUTHORS]
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(f"""
            WITH {ACCOUNT_COUNTRY_CTE}
            SELECT count(DISTINCT b.brand_key)
              FROM realestate_intel.brand b
              LEFT JOIN acct ac ON ac.platform = b.platform AND ac.username = lower(b.username)
             WHERE (%(country)s::text IS NULL OR ac.cc = %(country)s)
               AND b.brand_key NOT IN (SELECT brand_key FROM realestate_intel.brand
                                        WHERE lower(username) = ANY(%(excluded)s))""",
                    {"country": country, "excluded": excluded})
        return cur.fetchone()[0]


def run_country(run_id: str) -> str | None:
    """The market a run is scoped to, or None for an all-markets run."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT country FROM realestate_intel.trends WHERE run_id = %s LIMIT 1", (run_id,))
        row = cur.fetchone()
        return row[0] if row else None


def fetch_company_handles() -> dict[tuple[str, str], str]:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT platform, lower(username), brand_key FROM realestate_intel.brand")
        return {(platform, username): brand_key for platform, username, brand_key in cur.fetchall()}


def update_trend_narrative(trend_id: str, narrative: dict) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE realestate_intel.trends SET narrative = %s WHERE trend_id = %s",
                    (json.dumps(narrative), trend_id))


def delete_run(run_id: str) -> int:
    """Clear a run before rewriting it — pipeline rows only.

    Trends a user generated from the assistant share the run they were measured
    against, so that they rank and filter alongside it. An unscoped delete here
    would destroy that user's work every time metrics re-ran, with nothing in
    the logs to say so.
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""DELETE FROM realestate_intel.trends
                       WHERE run_id = %s AND origin = 'pipeline'""", (run_id,))
        return cur.rowcount


TREND_COLUMNS = [
    "trend_id", "run_id", "level", "parent_trend_id", "name", "quadrant",
    "volume_index", "growth_index", "post_count", "unique_authors",
    "narrative", "metrics", "timeline", "example_posts", "member_posts",
    "origin", "created_by", "source_query", "country",
]

# The run every reader gets unless it asks for a market: the newest all-markets
# run. Country runs (country = 'AE' / 'SA') are read only when named, so writing
# one never changes what the default views, the brand pages or the assistant see.
LATEST_RUN_SQL = """SELECT run_id FROM realestate_intel.trends
                     WHERE country IS NULL ORDER BY created_at DESC LIMIT 1"""

_JSONB = {"narrative", "metrics", "timeline", "example_posts", "member_posts"}


def replace_run(run_id: str, rows: list[dict]) -> int:
    """Delete the run's previous rows and write the new ones together.

    Two separate commits meant a failure in the write left the run's old
    rows already deleted, with nothing to roll back to and every consumer
    pointed at whatever survived.
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM realestate_intel.trends "
                    "WHERE run_id = %s AND origin = 'pipeline'", (run_id,))
        cur.execute("DELETE FROM realestate_intel.trend_member WHERE run_id = %s",
                    (run_id,))
        _write_trend_rows(cur, rows)
    return len(rows)


def _write_trend_rows(cur, rows: list[dict]) -> int:
    """Write trends and their membership index on an open cursor.

    Shared by upsert_trends and replace_run so the two paths cannot drift, and
    so both keep trends and trend_member in the same transaction - they are the
    same fact, and a crash between them leaves the brand endpoints reading a
    membership that does not match the run they are told is current.
    """
    if not rows:
        return 0
    # Provenance columns are optional on the caller's row: the batch pipeline
    # builds rows without them and everything it writes is pipeline-origin.
    defaults = {"origin": "pipeline", "created_by": None, "source_query": None, "country": None}
    values = [
        tuple(json.dumps(r[c]) if c in _JSONB else r.get(c, defaults.get(c))
              for c in TREND_COLUMNS)
        for r in rows
    ]
    update = ", ".join(f"{c} = EXCLUDED.{c}" for c in TREND_COLUMNS if c != "trend_id")
    members = [
        (r["run_id"], r["trend_id"], r.get("level") or "micro",
         m.get("platform"), str(m.get("post_id")), (m.get("author_username") or None))
        for r in rows
        for m in (r.get("member_posts") or [])
        if m.get("platform") and m.get("post_id") is not None
    ]
    psycopg2.extras.execute_values(
        cur,
        f"""INSERT INTO realestate_intel.trends ({", ".join(TREND_COLUMNS)})
            VALUES %s
            ON CONFLICT (trend_id) DO UPDATE SET {update}""",
        values,
        page_size=100,
    )
    cur.execute("DELETE FROM realestate_intel.trend_member WHERE trend_id = ANY(%s)",
                ([r["trend_id"] for r in rows],))
    if members:
        psycopg2.extras.execute_values(
            cur,
            """INSERT INTO realestate_intel.trend_member
                   (run_id, trend_id, level, platform, post_id, author_username)
               VALUES %s
               ON CONFLICT (trend_id, platform, post_id) DO NOTHING""",
            members,
            page_size=1000,
        )
    logger.info("wrote %s trends, %s membership rows", len(rows), len(members))
    return len(rows)


def upsert_trends(rows: list[dict]) -> int:
    if not rows:
        return 0
    with get_conn() as conn, conn.cursor() as cur:
        return _write_trend_rows(cur, rows)
