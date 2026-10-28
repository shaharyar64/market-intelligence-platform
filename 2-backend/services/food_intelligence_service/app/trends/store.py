"""All Postgres I/O for the trend pipeline. Single seam: get_conn().

Vectors cross the wire as '[f1,f2,...]' text with a ::vector cast — no
pgvector python dependency needed.
"""
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
    from services.food_intelligence_service.app.db.analysis_store import _resolve_dsn
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
                raise last
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
                pass
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
        try:
            conn.rollback()
        except psycopg2.Error:
            pass
        raise
    finally:
        pool.putconn(conn)


def _rows_as_dicts(cur) -> list[dict]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def model_tag(model: str, dim: int, variant: str | None = None) -> str:
    """The key embeddings are stored under.

    A variant suffix keeps a re-embedding run from colliding with the vectors
    already stored: save_embeddings is ON CONFLICT DO NOTHING, so re-embedding
    under the same tag silently discards every new vector and the run appears to
    have changed nothing. It also lets the old and new vectors sit side by side,
    so the assistant keeps answering from the current set while a new one builds.
    """
    if variant is None:
        from services.food_intelligence_service.app.core.config import get_settings
        variant = get_settings().TREND_EMBED_VARIANT
    suffix = f"+{variant}" if variant else ""
    return f"{model}@{dim}{suffix}"


def _cohort_clause(cohort: str) -> tuple[str, list]:
    """cohort 'all' means every row in trend_posts (no cohort filter)."""
    if cohort == "all":
        return "TRUE", []
    return "p.cohort = %s", [cohort]


# Every read path in this module carries this. `IS TRUE` deliberately excludes
# unclassified rows: a post the food filter has not ruled on yet must not reach
# embedding or clustering, so the safe default is to withhold it rather than
# let it through and hope a later stage catches it.
FOOD_ONLY = " AND p.is_food IS TRUE"


def ensure_food_column() -> None:
    """The food verdict lives beside the embeddings, not on the source rows.

    It is computed here, so it belongs to this pipeline rather than to the
    community dump or to the brand crawl's table — and it has to cover posts
    from both, which no single source table can do.
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS food_intel.post_food (
                           platform  text NOT NULL,
                           post_id   text NOT NULL,
                           is_food   boolean,
                           scored_at timestamptz NOT NULL DEFAULT now(),
                           PRIMARY KEY (platform, post_id))""")
        cur.execute("""CREATE INDEX IF NOT EXISTS post_food_is_food_idx
                       ON food_intel.post_food (is_food)""")


def fetch_unclassified_captions(limit: int | None = None) -> list[dict]:
    sql = """
        SELECT platform, post_id, caption FROM food_intel.trend_posts
        WHERE is_food IS NULL AND caption IS NOT NULL AND caption <> ''
    """
    params: list = []
    if limit:
        sql += " LIMIT %s"
        params.append(limit)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return [{"platform": p, "post_id": i, "caption": c} for p, i, c in cur.fetchall()]


def save_food_flags(rows: list[tuple[str, str, bool]], chunk_size: int = 5000) -> int:
    """COPY into a temp table, then one UPDATE ... FROM per chunk.

    Row-at-a-time UPDATEs over a corpus this size spend their whole runtime on
    round trips to RDS.
    """
    if not rows:
        return 0
    with get_conn() as conn:
        for start in range(0, len(rows), chunk_size):
            buf = io.StringIO()
            for platform, post_id, is_food in rows[start:start + chunk_size]:
                buf.write(f"{platform}\t{post_id}\t{'t' if is_food else 'f'}\n")
            buf.seek(0)
            with conn.cursor() as cur:
                cur.execute("""CREATE TEMP TABLE IF NOT EXISTS _food_stage
                               (platform text, post_id text, is_food boolean)
                               ON COMMIT DROP""")
                cur.copy_expert("COPY _food_stage (platform, post_id, is_food) FROM STDIN", buf)
                cur.execute("""INSERT INTO food_intel.post_food
                                   (platform, post_id, is_food)
                               SELECT platform, post_id, is_food FROM _food_stage
                               ON CONFLICT (platform, post_id) DO UPDATE
                                  SET is_food = EXCLUDED.is_food, scored_at = now()""")
                cur.execute("TRUNCATE _food_stage")
            conn.commit()
    return len(rows)


def mark_junk_captions() -> int:
    """Rule out captions with nothing to read, without spending a model call.

    An upstream export stringified missing captions, so 42,927 rows carry the
    literal text "nan" and were embedded as if that were their content.
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""INSERT INTO food_intel.post_food (platform, post_id, is_food)
                       SELECT p.platform, p.post_id, false
                         FROM food_intel.trend_posts p
                        WHERE p.is_food IS NULL
                          AND (p.caption IS NULL
                               OR lower(btrim(p.caption))
                                   IN ('', 'nan', 'none', 'null', 'undefined'))
                       ON CONFLICT (platform, post_id) DO UPDATE
                          SET is_food = false, scored_at = now()""")
        return cur.rowcount


def fetch_labeling_set(fraction: float, tag: str) -> list[dict]:
    """Captions plus their vectors, for teaching the food classifier."""
    import numpy as np
    sql = """
        SELECT p.platform, p.post_id, p.caption, e.embedding::text
        FROM food_intel.trend_posts p
        JOIN food_intel.post_embedding e
          ON e.platform = p.platform AND e.post_id = p.post_id AND e.model = %s
        WHERE p.caption IS NOT NULL AND p.caption <> ''
          AND lower(btrim(p.caption)) NOT IN ('nan', 'none', 'null', 'undefined')
          AND ('x' || substr(md5(p.post_id), 1, 8))::bit(32)::bigint < %s
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (tag, int(fraction * 2**32)))
        return [{"platform": p, "post_id": i, "caption": c,
                 "vec": np.fromstring(v[1:-1], sep=",", dtype=np.float32)}
                for p, i, c, v in cur.fetchall()]


def apply_food_model(coef: list[float], intercept: float, tag: str) -> int:
    """Score every unclassified post with the linear model, inside Postgres.

    A logistic regression is a dot product against its coefficients, and pgvector
    computes that server-side: `<#>` is the negative inner product, so the
    decision value is -(embedding <#> coef) + intercept. Pulling 556k vectors
    over the wire to score them in Python would take about half an hour and move
    roughly 5GB; this moves one vector and stays inside the database.
    """
    vector = "[" + ",".join(f"{c:.8f}" for c in coef) + "]"
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = '0'")
        cur.execute("""INSERT INTO food_intel.post_food (platform, post_id, is_food)
                       SELECT p.platform, p.post_id,
                              ((-(e.embedding <#> %s::vector) + %s) > 0)
                         FROM food_intel.trend_posts p
                         JOIN food_intel.post_embedding e
                           ON e.platform = p.platform AND e.post_id = p.post_id
                        WHERE e.model = %s AND p.is_food IS NULL
                       ON CONFLICT (platform, post_id) DO UPDATE
                          SET is_food = EXCLUDED.is_food, scored_at = now()""",
                    (vector, intercept, tag))
        return cur.rowcount


def food_filter_status() -> dict:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""SELECT source,
                              count(*) FILTER (WHERE is_food IS TRUE)  AS food,
                              count(*) FILTER (WHERE is_food IS FALSE) AS not_food,
                              count(*) FILTER (WHERE is_food IS NULL)  AS pending
                       FROM food_intel.trend_posts
                       WHERE caption IS NOT NULL AND caption <> ''
                       GROUP BY source ORDER BY source""")
        return {r[0]: {"food": r[1], "not_food": r[2], "pending": r[3]} for r in cur.fetchall()}


def fetch_posts_missing_embeddings(cohort: str, tag: str, limit: int | None = None) -> list[dict]:
    clause, cparams = _cohort_clause(cohort)
    sql = f"""
        SELECT p.platform, p.post_id, p.caption, p.hashtags
        FROM food_intel.trend_posts p
        WHERE {clause} AND p.caption IS NOT NULL AND p.caption <> ''
          {FOOD_ONLY}
          AND NOT EXISTS (SELECT 1 FROM food_intel.post_embedding e
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


def save_embeddings(rows: list[tuple[str, str, str, list[float]]],
                    chunk_size: int = 1000) -> int:
    """rows: (platform, post_id, model_tag, vector).

    Uses COPY into a temp table then an upsert. execute_values sent one
    multi-megabyte INSERT per batch, which crawled across the WAN to RDS;
    COPY streams instead and is several times faster for bulk vectors.
    """
    if not rows:
        return 0
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
                cur.execute("""INSERT INTO food_intel.post_embedding
                                   (platform, post_id, model, embedding)
                               SELECT platform, post_id, model, embedding FROM _emb_stage
                               ON CONFLICT DO NOTHING""")
                cur.execute("TRUNCATE _emb_stage")
            conn.commit()
    return len(rows)


_ANALYSED = """(jsonb_array_length(coalesce(pa.analysis->'themes', '[]'::jsonb)) > 0
                OR coalesce(pa.analysis->>'description', '') <> '')"""


def fetch_analyses() -> dict[tuple[str, str], dict]:
    sql = f"""
        SELECT pa.platform, pa.post_id,
               jsonb_build_object('description', pa.analysis->'description',
                                  'themes', pa.analysis->'themes',
                                  'product_focus', pa.analysis->'product_focus',
                                  'semiotic', pa.analysis->'semiotic',
                                  'functional_visual', pa.analysis->'functional_visual')
          FROM food_intel.post_analysis pa
         WHERE {_ANALYSED}
    """
    out: dict[tuple[str, str], dict] = {}
    with get_conn() as conn, conn.cursor(name="analyses") as cur:
        cur.itersize = 4000
        cur.execute(sql)
        for platform, post_id, analysis in cur:
            out[(platform, post_id)] = analysis if isinstance(analysis, dict) else json.loads(analysis)
    return out


def posts_missing_embedding(tag: str, limit: int | None = None) -> list[dict]:
    sql = f"""
        SELECT pa.platform, pa.post_id
          FROM food_intel.post_analysis pa
          LEFT JOIN food_intel.post_embedding e
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


def upsert_post_embeddings(rows: list[tuple[str, str, str, list[float]]],
                           chunk_size: int = 1000) -> int:
    """rows: (platform, post_id, model_tag, vector).

    Unlike save_embeddings (ON CONFLICT DO NOTHING), this overwrites an
    existing vector: posts_missing_embedding re-selects a post whose analysis
    changed since it was last embedded, and that re-embed must replace the
    stale vector rather than be silently dropped.
    """
    if not rows:
        return 0
    with get_conn() as conn:
        for start in range(0, len(rows), chunk_size):
            chunk = rows[start:start + chunk_size]
            buf = io.StringIO()
            for platform, post_id, tag, vec in chunk:
                vector = "[" + ",".join(f"{v:.6f}" for v in vec) + "]"
                buf.write(f"{platform}\t{post_id}\t{tag}\t{vector}\n")
            buf.seek(0)
            with conn.cursor() as cur:
                cur.execute("""CREATE TEMP TABLE IF NOT EXISTS _emb_upsert_stage
                               (platform text, post_id text, model text, embedding vector(1024))
                               ON COMMIT DROP""")
                cur.copy_expert(
                    "COPY _emb_upsert_stage (platform, post_id, model, embedding) FROM STDIN", buf)
                cur.execute("""INSERT INTO food_intel.post_embedding
                                   (platform, post_id, model, embedding)
                               SELECT platform, post_id, model, embedding FROM _emb_upsert_stage
                               ON CONFLICT (platform, post_id, model) DO UPDATE
                                  SET embedding = EXCLUDED.embedding, created_at = now()""")
                cur.execute("TRUNCATE _emb_upsert_stage")
            conn.commit()
    return len(rows)


def count_community_posts(cohort: str) -> int:
    clause, cparams = _cohort_clause(cohort)
    sql = f"""
        SELECT count(*) FROM food_intel.trend_posts p
        WHERE {clause} AND p.source = 'community'
          AND p.caption IS NOT NULL AND p.caption <> ''
          {FOOD_ONLY}
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
    ~4.4k food posts, and trends need all of them.
    """
    if not sample and threshold is None:
        return "", []
    if threshold is None:
        threshold = resolve_sample_threshold(cohort, sample)
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
        FROM food_intel.trend_posts p
        WHERE {clause}{src_clause}
          AND p.caption IS NOT NULL AND p.caption <> ''
          {FOOD_ONLY}
          {smp_clause}
    """
    cparams = [*cparams, *sparams]
    rows: list[dict] = []
    with get_conn() as conn:
        with conn.cursor(name="cohort_captions") as cur:
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
        SELECT count(*) FROM food_intel.trend_posts p
        WHERE {clause}{src_clause}
          AND p.caption IS NOT NULL AND p.caption <> ''
          {FOOD_ONLY}
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, cparams)
        return cur.fetchone()[0]


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
    """
    import numpy as np

    clause, cparams = _cohort_clause(cohort)
    src_clause = ""
    if sources:
        src_clause = " AND p.source = ANY(%s)"
        cparams = [*cparams, sources]
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
    if country:
        src_clause += " AND p.country = %s"
        cparams = [*cparams, country]
    if exclude_authors:
        src_clause += " AND NOT (p.author_username = ANY(%s))"
        cparams = [*cparams, list(exclude_authors)]
    sql = f"""
        SELECT p.platform, p.post_id, p.source, p.caption, p.hashtags, p.posted_at,
               p.author_username, p.engagement_total, p.likes, p.comments,
               p.views, p.media_keys, p.post_url,
               e.embedding::text AS vec
        FROM food_intel.trend_posts p
        JOIN food_intel.post_embedding e
          ON e.platform = p.platform AND e.post_id = p.post_id AND e.model = %s
        WHERE {clause}{src_clause}
          {FOOD_ONLY}
    """
    smp_clause, sparams = sample_predicate(cohort, sample, sample_threshold)
    sql += smp_clause
    params: list = [tag, *cparams, *sparams]
    rows: list[dict] = []
    with get_conn() as conn:
        with conn.cursor(name="cohort_posts") as cur:
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
                    row = dict(zip(cols, record))
                    row["vec"] = np.array(record[vec_at][1:-1].split(","), dtype=np.float32)
                    rows.append(row)
    return rows


def count_brand_accounts() -> int:
    """Brands the platform monitors — the canonical registry, not a count of
    scraped accounts.

    This used to count DISTINCT author_username where source='brand', which
    returned 4,261: the upstream scraper labels many personal creator accounts
    as 'brand', and 80% of them appeared only once in the corpus. That number
    described scrape composition, not a tracked brand roster.
    """
    from services.food_intelligence_service.app.registry import brands
    return len(brands.list_brands())


def update_trend_narrative(trend_id: str, narrative: dict) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE food_intel.trends SET narrative = %s WHERE trend_id = %s",
                    (json.dumps(narrative), trend_id))


TREND_COLUMNS = [
    "trend_id", "run_id", "level", "parent_trend_id", "name", "quadrant",
    "volume_index", "growth_index", "post_count", "unique_authors",
    "narrative", "metrics", "timeline", "example_posts", "member_posts",
    "origin", "created_by", "source_query", "country",
]

_JSONB = {"narrative", "metrics", "timeline", "example_posts", "member_posts"}


def upsert_trends(rows: list[dict]) -> int:
    if not rows:
        return 0
    values = _trend_values(rows)
    with get_conn() as conn, conn.cursor() as cur:
        _insert_trends(cur, values)
    return len(rows)


def _trend_values(rows: list[dict]) -> list[tuple]:
    # Provenance columns are optional on the caller's row: the batch pipeline
    # builds rows without them and everything it writes is pipeline-origin.
    defaults = {"origin": "pipeline", "created_by": None, "source_query": None}
    return [
        tuple(json.dumps(r[c]) if c in _JSONB else r.get(c, defaults.get(c))
              for c in TREND_COLUMNS)
        for r in rows
    ]


def _insert_trends(cur, values: list[tuple]) -> None:
    update = ", ".join(f"{c} = EXCLUDED.{c}" for c in TREND_COLUMNS if c != "trend_id")
    psycopg2.extras.execute_values(
        cur,
        f"""INSERT INTO food_intel.trends ({", ".join(TREND_COLUMNS)})
            VALUES %s
            ON CONFLICT (trend_id) DO UPDATE SET {update}""",
        values,
        page_size=100,
    )


def replace_run(run_id: str, rows: list[dict]) -> int:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""SELECT min(created_at) FROM food_intel.trends
                       WHERE run_id = %s AND origin = 'pipeline'""", (run_id,))
        born = cur.fetchone()[0]
        cur.execute("""DELETE FROM food_intel.trends
                       WHERE run_id = %s AND origin = 'pipeline'""", (run_id,))
        if rows:
            _insert_trends(cur, _trend_values(rows))
        if born is not None:
            cur.execute("""UPDATE food_intel.trends SET created_at = %s
                           WHERE run_id = %s AND origin = 'pipeline'""", (born, run_id))
    return len(rows)
