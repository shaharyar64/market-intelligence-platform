"""SQL and pgvector access behind the assistant's tools.

Every query is hand-written and parameterised: the model supplies argument
values, never SQL.
"""
import json

import psycopg2.errors
from dataclasses import dataclass, field
from datetime import date

from services.food_intelligence_service.app.trends import store
from services.food_intelligence_service.app.trends.trend_posts_view import MEMBER_COUNTRY_JOIN

MAX_POSTS = 50
MAX_TRENDS = 20
OVERFETCH = 5
WIDE_POOL = 250
EXACT_SEARCH_TIMEOUT = '8s'
EF_SEARCH_MIN = 100


def _ef_search(k: int) -> int:
    return max(EF_SEARCH_MIN, k)


@dataclass
class PostFilters:
    platforms: list[str] | None = None
    sources: list[str] | None = None
    date_from: date | None = None
    date_to: date | None = None
    countries: list[str] | None = None
    min_engagement: int | None = None
    hashtag: str | None = None
    persona: str | None = None


def clamp_limit(value: int | None, maximum: int) -> int:
    if not value or value < 1:
        return 1 if value is not None and value < 1 else min(10, maximum)
    return min(value, maximum)


def build_post_where(f: PostFilters) -> tuple[str, dict]:
    """Every post query the assistant runs goes through here.

    The food guard is unconditional and first: the assistant answers from this
    corpus directly, so an unfiltered query would quote a bank or telecom post
    back to the user as food evidence.
    """
    clauses: list[str] = ["p.is_food IS TRUE"]
    params: dict = {}
    if f.platforms:
        clauses.append("p.platform = ANY(%(platforms)s)")
        params["platforms"] = list(f.platforms)
    if f.sources:
        clauses.append("p.source = ANY(%(sources)s)")
        params["sources"] = list(f.sources)
    if f.date_from:
        clauses.append("p.posted_at >= %(date_from)s")
        params["date_from"] = f.date_from
    if f.date_to:
        clauses.append("p.posted_at <= %(date_to)s")
        params["date_to"] = f.date_to
    if f.countries:
        clauses.append("p.country = ANY(%(countries)s)")
        params["countries"] = list(f.countries)
    if f.min_engagement is not None:
        clauses.append("p.engagement_total >= %(min_engagement)s")
        params["min_engagement"] = f.min_engagement
    if f.hashtag:
        clauses.append("%(hashtag)s = ANY(p.hashtags)")
        params["hashtag"] = f.hashtag
    if f.persona:
        clauses.append("""EXISTS (SELECT 1 FROM food_intel.persona_post pp
                                  WHERE pp.persona_id = %(persona)s
                                    AND pp.platform = p.platform
                                    AND pp.post_id = p.post_id)""")
        params["persona"] = f.persona
    return (" AND " + " AND ".join(clauses) if clauses else ""), params


def _rows(cur) -> list[dict]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def search_posts(query_vector: list[float], f: PostFilters, limit: int = 10) -> list[dict]:
    from services.food_intelligence_service.app.core.config import get_settings
    settings = get_settings()
    tag = store.model_tag(settings.TREND_EMBED_MODEL, settings.TREND_EMBED_DIM)
    k = clamp_limit(limit, MAX_POSTS)
    where, params = build_post_where(f)
    params.update({
        "tag": tag,
        "vec": "[" + ",".join(f"{v:.6f}" for v in query_vector) + "]",
        "k": k * OVERFETCH,
    })
    tracked_only = bool(f.sources) and "community" not in set(f.sources)
    if f.persona:
        params["persona"] = f.persona
        ann = """
            SELECT e.platform, e.post_id, (e.embedding <=> %(vec)s::vector) AS distance
            FROM food_intel.post_embedding e
            JOIN food_intel.persona_post pp
              ON pp.platform = e.platform AND pp.post_id = e.post_id
             AND pp.persona_id = %(persona)s
            JOIN food_intel.post_food f
              ON f.platform = e.platform AND f.post_id = e.post_id AND f.is_food
            WHERE e.model = %(tag)s
            ORDER BY e.embedding <=> %(vec)s::vector
            LIMIT %(k)s
        """
    elif tracked_only:
        ann = """
            SELECT e.platform, e.post_id, (e.embedding <=> %(vec)s::vector) AS distance
            FROM food_intel.post_embedding e
            JOIN food_intel.post_source ps
              ON ps.platform = e.platform AND ps.post_id = e.post_id
            JOIN food_intel.post_food f
              ON f.platform = e.platform AND f.post_id = e.post_id AND f.is_food
            WHERE e.model = %(tag)s AND ps.source = ANY(%(sources)s)
            ORDER BY e.embedding <=> %(vec)s::vector
            LIMIT %(k)s
        """
    else:
        ann = """
            SELECT e.platform, e.post_id, (e.embedding <=> %(vec)s::vector) AS distance
            FROM food_intel.post_embedding e
            JOIN food_intel.post_food f
              ON f.platform = e.platform AND f.post_id = e.post_id AND f.is_food
            WHERE e.model = %(tag)s
            ORDER BY e.embedding <=> %(vec)s::vector
            LIMIT %(k)s
        """
    filtered = bool(f.platforms or f.date_from or f.date_to or f.countries or f.hashtag
                    or f.min_engagement is not None or (f.sources and not tracked_only))
    pool = k * OVERFETCH
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = '40s'")
        while True:
            cur.execute(f"SET LOCAL hnsw.ef_search = {_ef_search(pool)}")
            params["k"] = pool
            cur.execute(ann, params)
            near = cur.fetchall()
            if not near:
                return []
            distance_by_id = {(pl, pid): dist for pl, pid, dist in near}
            params["id_platforms"] = sorted({pl for pl, _ in distance_by_id})
            params["id_posts"] = sorted({pid for _, pid in distance_by_id})
            cur.execute(f"""SELECT p.platform, p.post_id, p.source, p.caption, p.post_url,
                                   p.author_username, p.likes, p.comments, p.views,
                                   p.posted_at, p.country, p.hashtags
                            FROM food_intel.trend_posts p
                            WHERE p.platform = ANY(%(id_platforms)s)
                              AND p.post_id = ANY(%(id_posts)s){where}""", params)
            rows = [r for r in _rows(cur) if (r["platform"], r["post_id"]) in distance_by_id]
            if len(rows) >= k or not filtered or len(near) < pool or pool >= WIDE_POOL:
                break
            pool = WIDE_POOL
        if len(rows) < k and filtered:
            exact = _exact_filtered_search(cur, params, where, k)
            if exact is not None:
                return exact
    for r in rows:
        r["distance"] = distance_by_id.get((r["platform"], r["post_id"]))
    rows.sort(key=lambda r: r["distance"])
    return rows[:k]

def _exact_filtered_search(cur, params: dict, where: str, k: int) -> list[dict] | None:
    cur.execute("SAVEPOINT exact_search")
    try:
        cur.execute(f"SET LOCAL statement_timeout = '{EXACT_SEARCH_TIMEOUT}'")
        cur.execute(f"""SELECT p.platform, p.post_id, p.source, p.caption, p.post_url,
                               p.author_username, p.likes, p.comments, p.views,
                               p.posted_at, p.country, p.hashtags,
                               (e.embedding <=> %(vec)s::vector) AS distance
                        FROM food_intel.trend_posts p
                        JOIN food_intel.post_embedding e
                          ON e.platform = p.platform AND e.post_id = p.post_id
                         AND e.model = %(tag)s
                        WHERE TRUE{where}
                        ORDER BY distance
                        LIMIT %(k_exact)s""", {**params, "k_exact": k})
        rows = _rows(cur)
        cur.execute("RELEASE SAVEPOINT exact_search")
        return rows
    except psycopg2.errors.QueryCanceled:
        cur.execute("ROLLBACK TO SAVEPOINT exact_search")
        return None


PERSONA_TREND_FLOOR = 10
COUNTRY_TREND_FLOOR = 10
MIN_COUNTRY_COVERAGE_PCT = 25


# Measured against this corpus rather than guessed. A word people actually use
# lands at 0.44-0.52 from its trend ("labneh" 0.464, "sea food" 0.439,
# "bakery" 0.479). A category term nobody writes in a caption sits further out
# even when the match is obvious - "poultry" is 0.633 from Chicken-Based Dishes,
# and the old 0.55 ceiling threw it away. Genuinely off-topic queries are far
# behind that: "ghista" 0.781, "cryptocurrency" 0.813, "car insurance" 0.868.
# So the ceiling admits the vocabulary gap and still refuses the nonsense.
SEMANTIC_MAX_DISTANCE = 0.72

# The ceiling alone would let a good query drag in loose neighbours, so results
# are also cut relative to the best hit. Distance is only comparable within one
# query - an absolute number cannot express "much worse than the top match".
SEMANTIC_MARGIN = 0.12


def _embed_tag() -> str:
    from services.food_intelligence_service.app.core.config import get_settings
    settings = get_settings()
    return store.model_tag(settings.TREND_EMBED_MODEL, settings.TREND_EMBED_DIM)


def _query_vector(query: str, embed_query) -> str | None:
    """The literal a vector comparison needs, or None when embedding fails.

    Returning None rather than raising lets the caller fall back to the text
    match: a slow or unreachable embedding endpoint should degrade the search,
    not turn the whole question into "no data".
    """
    try:
        vec = embed_query(query)
    except Exception:
        return None
    if not vec:
        return None
    return "[" + ",".join(f"{v:.6f}" for v in vec) + "]"


def _semantic_trends(query: str, quadrant: str | None, level: str,
                     k: int, embed_query) -> list[dict] | None:
    """Trends nearest the query in meaning, with exact text matches promoted.

    Returns None when the run has no embeddings, so the caller falls back to
    the text match rather than answering "nothing found" for a vocabulary gap.
    """
    from services.food_intelligence_service.app.core.config import get_settings
    settings = get_settings()
    tag = store.model_tag(settings.TREND_EMBED_MODEL, settings.TREND_EMBED_DIM)

    params: dict = {"level": level, "k": k, "tag": tag, "q": f"%{query}%",
                    "max_dist": SEMANTIC_MAX_DISTANCE}
    clauses = ["t.level = %(level)s", "t.run_id = latest.run_id"]
    if quadrant:
        clauses.append("t.quadrant = %(quadrant)s")
        params["quadrant"] = quadrant

    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = '25s'")
        cur.execute("""SELECT count(*) FROM food_intel.trend_embedding e
                       WHERE e.model = %(tag)s AND e.run_id =
                             (SELECT run_id FROM food_intel.trends
                              WHERE country IS NULL
                              ORDER BY created_at DESC LIMIT 1)""", params)
        if not cur.fetchone()[0]:
            return None

        params["vec"] = "[" + ",".join(f"{v:.6f}" for v in embed_query(query)) + "]"
        cur.execute(f"""
            WITH latest AS (
                SELECT run_id FROM food_intel.trends
                WHERE country IS NULL ORDER BY created_at DESC LIMIT 1
            )
            SELECT t.trend_id, t.name, t.quadrant, t.post_count, t.unique_authors,
                   t.volume_index, t.growth_index,
                   t.narrative->>'summary' AS summary, t.metrics,
                   (e.embedding <=> %(vec)s::vector) AS distance,
                   (t.name ILIKE %(q)s) AS exact
            FROM food_intel.trends t
            CROSS JOIN latest
            JOIN food_intel.trend_embedding e
              ON e.run_id = t.run_id AND e.trend_id = t.trend_id AND e.model = %(tag)s
            WHERE {" AND ".join(clauses)}
              AND ((e.embedding <=> %(vec)s::vector) <= %(max_dist)s
                   OR t.name ILIKE %(q)s)
            ORDER BY exact DESC, distance
            LIMIT %(k)s
        """, params)
        return _within_margin(_rows(cur))


def _within_margin(rows: list[dict]) -> list[dict]:
    """Drop hits far behind the best one, keeping exact name matches regardless."""
    scored = [r["distance"] for r in rows if r.get("distance") is not None]
    if not scored:
        return rows
    cutoff = min(scored) + SEMANTIC_MARGIN
    return [r for r in rows
            if r.get("exact") or r.get("distance") is None or r["distance"] <= cutoff]


def search_trends(query: str | None = None, quadrant: str | None = None,
                  level: str = "micro", limit: int = 10,
                  persona: str | None = None,
                  countries: list[str] | None = None,
                  embed_query=None) -> list[dict]:
    if persona or countries:
        return _trends_by_membership(query, quadrant, level, limit, persona,
                                     countries, embed_query)
    k = clamp_limit(limit, MAX_TRENDS)

    if query and embed_query is not None:
        try:
            hits = _semantic_trends(query, quadrant, level, k, embed_query)
        except Exception:
            hits = None
        if hits:
            for r in hits:
                if isinstance(r.get("metrics"), str):
                    r["metrics"] = json.loads(r["metrics"])
            return hits

    params: dict = {"level": level, "k": k}
    clauses = ["level = %(level)s"]
    if quadrant:
        clauses.append("quadrant = %(quadrant)s")
        params["quadrant"] = quadrant
    if query:
        clauses.append("(name ILIKE %(q)s OR narrative->>'summary' ILIKE %(q)s)")
        params["q"] = f"%{query}%"
    sql = f"""
        SELECT trend_id, name, quadrant, post_count, unique_authors,
               volume_index, growth_index, narrative->>'summary' AS summary,
               metrics
        FROM food_intel.trends
        WHERE run_id = (SELECT run_id FROM food_intel.trends
                        WHERE country IS NULL
                        ORDER BY created_at DESC LIMIT 1)
          AND {" AND ".join(clauses)}
        ORDER BY growth_index DESC, post_count DESC
        LIMIT %(k)s
    """
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = '20s'")
        cur.execute(sql, params)
        rows = _rows(cur)
    for r in rows:
        if isinstance(r.get("metrics"), str):
            r["metrics"] = json.loads(r["metrics"])
    return rows


def _trends_by_membership(query: str | None, quadrant: str | None, level: str,
                          limit: int, persona: str | None,
                          countries: list[str] | None,
                          embed_query=None) -> list[dict]:
    """Trends ranked by who is in them, rather than by how big they are.

    Persona and country are the same shape of question - both narrow or score a
    trend by the posts inside it - so they share one expansion of member_posts
    and compose in a single query.

    Ordering by raw overlap returns the corpus's biggest trends to every filter
    alike, because a big enough trend overlaps everything. Share is the finding.

    Geography carries a second number. Country is null on 60% of food posts, so
    a share taken over the whole trend understates it and a share taken over
    attributed posts alone hides how little was attributable. Both ship:
    country_share_pct over attributed posts, country_coverage_pct saying how
    much of the trend that was.
    """
    k = clamp_limit(limit, MAX_TRENDS)
    params: dict = {"level": level, "k": k}

    cand = ["t.member_posts IS NOT NULL", "t.run_id = latest.run_id",
            "t.level = %(level)s"]
    if quadrant:
        cand.append("t.quadrant = %(quadrant)s")
        params["quadrant"] = quadrant

    embed_join = ""
    margin_filter = ""
    distance_col = ""
    if query:
        params["q"] = f"%{query}%"
        vec = _query_vector(query, embed_query) if embed_query else None
        if vec is not None:
            params["vec"] = vec
            params["tag"] = _embed_tag()
            params["max_dist"] = SEMANTIC_MAX_DISTANCE
            params["margin"] = SEMANTIC_MARGIN
            embed_join = """
                JOIN food_intel.trend_embedding te
                  ON te.run_id = t.run_id AND te.trend_id = t.trend_id
                 AND te.model = %(tag)s"""
            cand.append("((te.embedding <=> %(vec)s::vector) <= %(max_dist)s"
                        " OR t.name ILIKE %(q)s)")
            # This path ranks by share, not by distance, so the ceiling alone
            # would let the most country-concentrated trend win however little
            # it has to do with the question - "milk and laban in the UAE"
            # answered with Turkish ice cream. Narrowing to the trends closest
            # in meaning first keeps share as the ranking while leaving only
            # on-topic trends to rank.
            distance_col = """,
                   (te.embedding <=> %(vec)s::vector) AS distance,
                   (t.name ILIKE %(q)s) AS exact"""
            margin_filter = """
                WHERE s.distance <= (SELECT min(distance) FROM scored) + %(margin)s
                   OR s.exact"""
        else:
            cand.append("(t.name ILIKE %(q)s OR t.narrative->>'summary' ILIKE %(q)s)")

    persona_join = ""
    if persona:
        params["persona"] = persona
        persona_join = """
            JOIN food_intel.persona_post pp
              ON pp.platform = mp->>'platform' AND pp.post_id = mp->>'post_id'
             AND pp.persona_id = %(persona)s"""

    if countries:
        params["countries"] = list(countries)
        params["floor"] = COUNTRY_TREND_FLOOR
        params["min_coverage"] = MIN_COUNTRY_COVERAGE_PCT
        counts = """count(*) FILTER (WHERE country = ANY(%(countries)s)) AS in_country,
                   count(*) FILTER (WHERE country IS NOT NULL) AS attributed,"""
        having = """a.in_country >= %(floor)s
                    AND (100.0 * a.attributed / NULLIF(a.matched, 0)) >= %(min_coverage)s"""
        extra_cols = """,
               a.in_country AS country_posts,
               round(100.0 * a.in_country / NULLIF(a.attributed, 0), 1) AS country_share_pct,
               round(100.0 * a.attributed / NULLIF(a.matched, 0), 1) AS country_coverage_pct"""
        order = "ORDER BY country_share_pct DESC NULLS LAST, a.in_country DESC"
    else:
        params["floor"] = PERSONA_TREND_FLOOR
        counts = ""
        having = "a.matched >= %(floor)s"
        extra_cols = ""
        order = "ORDER BY persona_share_pct DESC, a.matched DESC"

    persona_cols = """,
               a.matched AS persona_posts,
               round(100.0 * a.matched / NULLIF(t.post_count, 0), 1) AS persona_share_pct""" if persona else ""

    if countries:
        member_join = f"""
            SELECT c.trend_id, mcc.member_country AS country
            FROM candidates c
            CROSS JOIN LATERAL jsonb_array_elements(c.member_posts) mp
            {MEMBER_COUNTRY_JOIN}
            {persona_join}"""
    else:
        member_join = f"""
            SELECT c.trend_id, NULL::text AS country
            FROM candidates c,
                 LATERAL jsonb_array_elements(c.member_posts) mp
            JOIN food_intel.persona_post pp
              ON pp.platform = mp->>'platform' AND pp.post_id = mp->>'post_id'
             AND pp.persona_id = %(persona)s"""

    sql = f"""
        WITH latest AS (
            SELECT run_id FROM food_intel.trends
            WHERE country IS NULL ORDER BY created_at DESC LIMIT 1
        ), scored AS (
            SELECT t.trend_id, t.member_posts{distance_col}
            FROM food_intel.trends t
            CROSS JOIN latest{embed_join}
            WHERE {" AND ".join(cand)}
        ), candidates AS (
            SELECT s.trend_id, s.member_posts FROM scored s{margin_filter}
        ), joined AS ({member_join}
        ), agg AS (
            SELECT trend_id, {counts} count(*) AS matched
            FROM joined GROUP BY 1
        )
        SELECT t.trend_id, t.name, t.quadrant, t.post_count, t.unique_authors,
               t.volume_index, t.growth_index,
               t.narrative->>'summary' AS summary, t.metrics{persona_cols}{extra_cols}
        FROM food_intel.trends t
        JOIN agg a ON a.trend_id = t.trend_id
        WHERE {having}
        {order}
        LIMIT %(k)s
    """
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = '60s'")
        cur.execute(sql, params)
        rows = _rows(cur)
    for r in rows:
        if isinstance(r.get("metrics"), str):
            r["metrics"] = json.loads(r["metrics"])
    return rows


def get_brand_trends(brand: str, limit: int = 15) -> list[dict]:
    """Which trends a brand's own posts sit inside, and how deeply.

    Nothing answered this before. Asked which trends Almarai is in, the
    assistant reached for get_brand_profile - which returns themes, products
    and engagement but no trend membership - and then named a trend it had seen
    earlier in the conversation. Every figure around that claim was real, which
    is what made it hard to catch.

    The join is one hop: a trend lists its member posts, post_analysis says
    which brand posted each one.
    """
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = '60s'")
        cur.execute("""
            WITH latest AS (
                SELECT run_id FROM food_intel.trends
                WHERE country IS NULL ORDER BY created_at DESC LIMIT 1
            ), cand AS (
                SELECT t.trend_id, t.name, t.quadrant, t.post_count,
                       t.volume_index, t.growth_index,
                       t.narrative->>'summary' AS summary, t.member_posts
                FROM food_intel.trends t, latest
                WHERE t.run_id = latest.run_id AND t.member_posts IS NOT NULL
            ), hits AS (
                SELECT c.trend_id, pa.brand_name,
                       count(*) AS brand_posts,
                       count(DISTINCT pa.account_username) AS brand_accounts
                FROM cand c,
                     LATERAL jsonb_array_elements(c.member_posts) mp
                JOIN food_intel.post_analysis pa
                  ON pa.platform = mp->>'platform' AND pa.post_id = mp->>'post_id'
                WHERE pa.brand_name ILIKE %(brand)s
                GROUP BY 1, 2
            )
            SELECT c.trend_id, c.name, c.quadrant, c.post_count,
                   c.volume_index, c.growth_index, c.summary,
                   h.brand_name, h.brand_posts, h.brand_accounts,
                   round(100.0 * h.brand_posts / NULLIF(c.post_count, 0), 2)
                       AS brand_share_pct
            FROM hits h JOIN cand c ON c.trend_id = h.trend_id
            ORDER BY h.brand_posts DESC
            LIMIT %(k)s
        """, {"brand": f"%{brand}%", "k": clamp_limit(limit, MAX_TRENDS)})
        return _rows(cur)


def get_trend(trend_id: str) -> dict | None:
    """One trend in full: headline metrics, weekly timeline, source mix.

    Matches on trend_id, and falls back to an exact name match because the model
    is told to pass the id but sometimes has only the display name.
    """
    sql = """
        SELECT trend_id, name, quadrant, level, post_count, unique_authors,
               volume_index, growth_index, origin, source_query,
               narrative->>'summary' AS summary,
               narrative->'keywords' AS keywords,
               narrative->'related_themes' AS related_themes,
               narrative->'product_entities' AS product_entities,
               metrics, timeline, example_posts
        FROM food_intel.trends
        WHERE run_id = (SELECT run_id FROM food_intel.trends
                        WHERE country IS NULL
                        ORDER BY created_at DESC LIMIT 1)
          AND (trend_id = %(id)s OR name ILIKE %(id)s)
        LIMIT 1
    """
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = '20s'")
        cur.execute(sql, {"id": trend_id})
        rows = _rows(cur)
    if not rows:
        return None
    row = rows[0]
    if isinstance(row.get("metrics"), str):
        row["metrics"] = json.loads(row["metrics"])
    for key in ("keywords", "related_themes", "product_entities",
                "timeline", "example_posts"):
        if isinstance(row.get(key), str):
            row[key] = json.loads(row[key])
    metrics = row.get("metrics") or {}
    row["source_mix"] = metrics.get("source_mix") or {}
    row["platform_mix"] = metrics.get("platform_mix") or {}
    row["growth_pct"] = metrics.get("growth_pct")
    row["as_of"] = metrics.get("as_of")
    return row


_GROUP_BY = {"platform": "p.platform", "source": "p.source",
             "country": "p.country", "month": "date_trunc('month', p.posted_at)"}
_METRIC = {"count": "count(*)", "likes": "sum(p.likes)",
           "engagement": "sum(p.engagement_total)", "views": "sum(p.views)"}


def aggregate_posts(f: PostFilters, group_by: str = "source",
                    metric: str = "count") -> list[dict]:
    """Counts and sums over posts, grouped one dimension at a time."""
    column = _GROUP_BY.get(group_by)
    aggregate = _METRIC.get(metric)
    if column is None or aggregate is None:
        return []
    where, params = build_post_where(f)
    label = "to_char(date_trunc('month', p.posted_at), 'YYYY-MM')" \
        if group_by == "month" else column
    sql = f"""
        SELECT {label} AS group_value, {aggregate} AS value, count(*) AS posts
        FROM food_intel.trend_posts p
        WHERE TRUE{where}
        GROUP BY 1
        HAVING {label} IS NOT NULL
        ORDER BY 2 DESC NULLS LAST
        LIMIT 40
    """
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = '60s'")
        cur.execute(sql, params)
        rows = _rows(cur)
    for r in rows:
        r["group_by"] = group_by
        r["metric"] = metric
        if r.get("value") is not None:
            r["value"] = int(r["value"])
    return rows


def list_brands(limit: int = 30) -> list[dict]:
    """The tracked accounts and how much of each is analysed.

    Read from post_analysis rather than the brand tables: this answers "which
    brands can you actually tell me about", and a brand with no analysed posts
    cannot be reported on however it is registered elsewhere.
    """
    sql = """
        SELECT brand_key, max(brand_name) AS brand_name,
               count(*) AS analysed_posts,
               count(DISTINCT account_username) AS accounts,
               max(account_type) AS account_type
        FROM food_intel.post_analysis
        WHERE brand_key IS NOT NULL
        GROUP BY brand_key
        ORDER BY analysed_posts DESC
        LIMIT %(k)s
    """
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = '30s'")
        cur.execute(sql, {"k": clamp_limit(limit, 100)})
        return _rows(cur)


def get_brand_profile(brand: str, limit: int = 40) -> dict | None:
    """What a brand talks about, aggregated from its analysed posts.

    Themes and products are counted across posts rather than summarised by a
    model, so the assistant reports how often a subject actually appears.
    """
    sql = """
        SELECT brand_name, account_username, platform, caption, language,
               engagement_total, posted_at, post_url, analysis
        FROM food_intel.post_analysis
        WHERE brand_name ILIKE %(brand)s OR brand_key ILIKE %(brand)s
        ORDER BY engagement_total DESC NULLS LAST
        LIMIT %(k)s
    """
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = '20s'")
        cur.execute(sql, {"brand": f"%{brand}%", "k": clamp_limit(limit, 60)})
        rows = _rows(cur)
    if not rows:
        return None

    themes: dict[str, dict] = {}
    products: dict[str, int] = {}
    keywords: dict[str, int] = {}
    languages: dict[str, int] = {}
    for row in rows:
        analysis = row.get("analysis")
        if isinstance(analysis, str):
            analysis = json.loads(analysis)
        analysis = analysis or {}
        for theme in analysis.get("themes") or []:
            label = (theme.get("label") or "").strip()
            if not label:
                continue
            slot = themes.setdefault(label, {"theme": label, "posts": 0, "evidence": []})
            slot["posts"] += 1
            for quote in (theme.get("evidence") or [])[:1]:
                if len(slot["evidence"]) < 3:
                    slot["evidence"].append(quote[:160])
        for product in analysis.get("product_focus") or []:
            name = (product.get("product") or "").strip()
            if name:
                products[name] = products.get(name, 0) + 1
        for word in (analysis.get("keywords") or [])[:12]:
            if word:
                keywords[word] = keywords.get(word, 0) + 1
        if analysis.get("language"):
            languages[analysis["language"]] = languages.get(analysis["language"], 0) + 1

    top_posts = [{"platform": r["platform"], "author": r["account_username"],
                  "caption": (r["caption"] or "")[:240], "post_url": r["post_url"],
                  "engagement": r["engagement_total"], "posted_at": r["posted_at"]}
                 for r in rows[:5]]
    return {
        "brand": rows[0]["brand_name"],
        "analysed_posts": len(rows),
        "themes": sorted(themes.values(), key=lambda t: -t["posts"])[:12],
        "products": [{"product": p, "posts": n}
                     for p, n in sorted(products.items(), key=lambda kv: -kv[1])[:12]],
        "keywords": [k for k, _ in sorted(keywords.items(), key=lambda kv: -kv[1])[:15]],
        "languages": languages,
        "engagement_total": sum(r["engagement_total"] or 0 for r in rows),
        "example_posts": top_posts,
    }


_CATALOGUE_TTL = 300
_catalogue_cache: tuple[float, list[dict]] | None = None


def trend_catalogue(limit: int = 40) -> list[dict]:
    """Names and ids of the current run's trends.

    Handed to the model as context so it has the real vocabulary before it
    calls anything: early failures came from guessed trend_ids and invented
    category names.
    """
    global _catalogue_cache
    import time as _time
    now = _time.time()
    if _catalogue_cache and now - _catalogue_cache[0] < _CATALOGUE_TTL:
        return _catalogue_cache[1][:limit]
    sql = """
        SELECT trend_id, name, level, quadrant, post_count
        FROM food_intel.trends
        WHERE run_id = (SELECT run_id FROM food_intel.trends
                        WHERE country IS NULL
                        ORDER BY created_at DESC LIMIT 1)
        ORDER BY level, post_count DESC
        LIMIT %s
    """
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (limit,))
        rows = _rows(cur)
    _catalogue_cache = (now, rows)
    return rows


def search_posts_scored(query_vector: list[float], limit: int = 5,
                        max_distance: float = 0.62) -> list[dict]:
    """Nearest posts, but only those genuinely close to the question.

    Vector search returns neighbours whatever is asked, so an unfiltered
    pre-fetch would attach food posts to a question about bitcoin and make an
    out-of-scope question look answerable. The distance cut is what keeps
    "I have no data" reachable.
    """
    from services.food_intelligence_service.app.core.config import get_settings
    settings = get_settings()
    tag = store.model_tag(settings.TREND_EMBED_MODEL, settings.TREND_EMBED_DIM)
    ann = """
        SELECT e.platform, e.post_id, (e.embedding <=> %(vec)s::vector) AS distance
        FROM food_intel.post_embedding e
        JOIN food_intel.post_food f
          ON f.platform = e.platform AND f.post_id = e.post_id AND f.is_food
        WHERE e.model = %(tag)s
        ORDER BY e.embedding <=> %(vec)s::vector
        LIMIT %(k)s
    """
    params = {"tag": tag, "k": clamp_limit(limit, MAX_POSTS),
              "vec": "[" + ",".join(f"{v:.6f}" for v in query_vector) + "]"}
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute(f"SET LOCAL statement_timeout = '30s'; "
                    f"SET LOCAL hnsw.ef_search = {_ef_search(params['k'])};" + ann, params)
        near = [(pl, pid, dist) for pl, pid, dist in cur.fetchall()
                if dist is not None and dist <= max_distance]
        if not near:
            return []
        cur.execute("""SELECT p.platform, p.post_id, p.source, p.caption,
                              p.author_username, p.post_url, p.engagement_total
                       FROM food_intel.trend_posts p
                       WHERE (p.platform, p.post_id) IN %s""",
                    (tuple((pl, pid) for pl, pid, _ in near),))
        meta = {(r["platform"], r["post_id"]): r for r in _rows(cur)}
    out = []
    for platform, post_id, distance in near:
        row = meta.get((platform, post_id))
        if row:
            out.append({**row, "distance": distance})
    return out
