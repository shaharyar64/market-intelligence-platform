"""SQL and pgvector access behind the assistant's tools.

Every query is hand-written and parameterised: the model supplies argument
values, never SQL.
"""
import json
import logging
from dataclasses import dataclass
from datetime import date

from services.trends_real_estate_service.app.trends import store

logger = logging.getLogger("assistant.retrieval")

MAX_POSTS = 50
MAX_TRENDS = 20
OVERFETCH = 5
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


def clamp_limit(value: int | None, maximum: int) -> int:
    if not value or value < 1:
        return 1 if value is not None and value < 1 else min(10, maximum)
    return min(value, maximum)


def build_post_where(f: PostFilters) -> tuple[str, dict]:
    """Every post query the assistant runs goes through here.

    The corpus is bounded at collection rather than filtered here: community
    rows reach us only through the real_estate search keyword, and brand and
    influencer rows come from curated account lists.
    """
    clauses: list[str] = []
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
        # Case-insensitive because the cohorts disagree: brand_posts and
        # influencer_posts lower() their tags in the view, community_posts
        # passes them through raw and is 38% mixed case. An exact match on
        # "dubai" missed 56% of the posts that have it, and "Dubai" matched
        # community only - both returning a partial set that looks complete.
        clauses.append("EXISTS (SELECT 1 FROM unnest(p.hashtags) h "
                       "WHERE lower(h) = lower(%(hashtag)s))")
        params["hashtag"] = f.hashtag.lstrip("#")
    return (" AND " + " AND ".join(clauses) if clauses else ""), params


def _rows(cur) -> list[dict]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]


def search_posts(query_vector: list[float], f: PostFilters, limit: int = 10) -> list[dict]:
    from services.trends_real_estate_service.app.core.config import get_settings
    settings = get_settings()
    tag = store.model_tag(settings.TREND_EMBED_MODEL, settings.TREND_EMBED_DIM)
    k = clamp_limit(limit, MAX_POSTS)
    where, params = build_post_where(f)
    params.update({
        "tag": tag,
        "vec": "[" + ",".join(f"{v:.6f}" for v in query_vector) + "]",
        "k": k * OVERFETCH,
    })
    # A source filter has to reach INSIDE the nearest-neighbour pool, not sit in
    # the WHERE that runs after it. Influencer posts are 2.5% of the corpus and
    # brand posts 28%, so an unrestricted ANN returns its k nearest overall and
    # the outer filter then finds few or none of them - the assistant answers
    # "no data" to a question that has data. Restricting the pool costs nothing
    # when the filter is wide and is the whole answer when it is narrow.
    # The same argument applies to platform, and now bites harder than it used to:
    # while the enum was instagram+tiktok the filter always named the bulk of the
    # corpus, but LinkedIn is 8% of it and X 8%, so an unrestricted pool of k*OVERFETCH
    # nearest returns a handful of them at best. search_posts has no relaxation ladder
    # to fall back on, so the thinning surfaces as a short answer with no explanation.
    tracked_only = bool(f.sources) and "community" not in set(f.sources or ())
    pool_clauses = ["e.model = %(tag)s"]
    pool_join = ""
    if tracked_only:
        pool_join = ("JOIN realestate_intel.post_source ps"
                     "  ON ps.platform = e.platform AND ps.post_id = e.post_id")
        pool_clauses.append("ps.source = ANY(%(sources)s)")
    if f.platforms:
        pool_clauses.append("e.platform = ANY(%(platforms)s)")
    ann = f"""
        SELECT e.platform, e.post_id, (e.embedding <=> %(vec)s::vector) AS distance
        FROM realestate_intel.post_embedding e
        {pool_join}
        WHERE {" AND ".join(pool_clauses)}
        ORDER BY e.embedding <=> %(vec)s::vector, e.platform, e.post_id
        LIMIT %(k)s
    """
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = '40s'")
        cur.execute(f"SET LOCAL hnsw.ef_search = {_ef_search(k * OVERFETCH)}")
        cur.execute(ann, params)
        near = cur.fetchall()
        if not near:
            return []
        order = {(pl, pid): i for i, (pl, pid, _) in enumerate(near)}
        params["ids"] = tuple((pl, pid) for pl, pid, _ in near)
        cur.execute(f"""SELECT p.platform, p.post_id, p.source, p.caption, p.post_url,
                               p.author_username, p.likes, p.comments, p.views,
                               p.posted_at, p.country, p.hashtags
                        FROM realestate_intel.trend_posts p
                        WHERE (p.platform, p.post_id) IN %(ids)s{where}""", params)
        rows = _rows(cur)
    distance_by_id = {(pl, pid): dist for pl, pid, dist in near}
    for r in rows:
        r["distance"] = distance_by_id.get((r["platform"], r["post_id"]))
    rows.sort(key=lambda r: order.get((r["platform"], r["post_id"]), len(order)))
    return rows[:k]

COUNTRY_TREND_FLOOR = 10
MIN_COUNTRY_COVERAGE_PCT = 25
MIN_COUNTRY_SHARE_PCT = 40


# Measured against this corpus rather than guessed. A word people actually use
# lands at 0.44-0.52 from its trend ("townhouse" 0.464, "sea view" 0.439,
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


def _run_has_trend_embeddings() -> bool:
    """Whether the run the trends table currently points at has been embedded."""
    try:
        with store.get_conn() as conn, conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '10s'")
            cur.execute("""SELECT EXISTS (
                             SELECT 1 FROM realestate_intel.trend_embedding e
                              WHERE e.model = %(tag)s AND e.run_id =
                                    (SELECT run_id FROM realestate_intel.trends
                                      WHERE country IS NULL
                                      ORDER BY created_at DESC LIMIT 1))""",
                        {"tag": _embed_tag()})
            return bool(cur.fetchone()[0])
    except Exception:
        logger.exception("could not check trend embedding coverage")
        return False


def _embed_tag() -> str:
    from services.trends_real_estate_service.app.core.config import get_settings
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


def _latest_run(country: str | None = None) -> str | None:
    """The newest run for a market ('AE', 'SA'), or the all-markets run."""
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""SELECT run_id FROM realestate_intel.trends
                       WHERE country IS NOT DISTINCT FROM %s
                       ORDER BY created_at DESC LIMIT 1""", (country,))
        row = cur.fetchone()
        return row[0] if row else None


def _semantic_trends(query: str, quadrant: str | None, level: str | None,
                     k: int, embed_query, run_id: str | None = None) -> list[dict] | None:
    """Trends nearest the query in meaning, with exact text matches promoted.

    Returns None when the run has no embeddings, so the caller falls back to
    the text match rather than answering "nothing found" for a vocabulary gap.
    run_id defaults to the all-markets run; a market run is searched by passing it.
    """
    from services.trends_real_estate_service.app.core.config import get_settings
    settings = get_settings()
    tag = store.model_tag(settings.TREND_EMBED_MODEL, settings.TREND_EMBED_DIM)
    run_id = run_id or _latest_run()
    if not run_id:
        return None

    params: dict = {"k": k, "tag": tag, "q": f"%{query}%",
                    "max_dist": SEMANTIC_MAX_DISTANCE, "run": run_id}
    clauses = ["t.run_id = %(run)s"]
    if level:
        clauses.append("t.level = %(level)s")
        params["level"] = level
    if quadrant:
        clauses.append("t.quadrant = %(quadrant)s")
        params["quadrant"] = quadrant

    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = '25s'")
        cur.execute("""SELECT count(*) FROM realestate_intel.trend_embedding e
                       WHERE e.model = %(tag)s AND e.run_id = %(run)s""", params)
        if not cur.fetchone()[0]:
            return None

        params["vec"] = "[" + ",".join(f"{v:.6f}" for v in embed_query(query)) + "]"
        cur.execute(f"""
            SELECT t.trend_id, t.name, t.level, t.quadrant, t.post_count, t.unique_authors,
                   t.volume_index, t.growth_index, t.country,
                   t.narrative->>'summary' AS summary, t.metrics,
                   (e.embedding <=> %(vec)s::vector) AS distance,
                   (t.name ILIKE %(q)s) AS exact
            FROM realestate_intel.trends t
            JOIN realestate_intel.trend_embedding e
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
                  level: str | None = None, limit: int = 10,
                  countries: list[str] | None = None,
                  embed_query=None) -> list[dict]:
    """Trends matching a query, from the run that answers the question.

    One market asked for -> that market's own run, the same trends Trends
    Explorer shows under its Market filter, so the assistant and the page never
    disagree about "the top trends in KSA". Both markets asked for is the whole
    market, so it reads the all-markets run. Only when a market has no run of
    its own yet does it fall back to ranking all-markets trends by the share of
    their posts from that market.
    """
    markets = sorted(set(countries or []))
    if len(markets) > 1:
        markets = []
    if markets:
        market_run = _latest_run(markets[0])
        if market_run is None:
            return _trends_by_country(query, quadrant, level, limit,
                                      markets, embed_query)
        return _search_run(market_run, query, quadrant, level, limit, embed_query)
    return _search_run(None, query, quadrant, level, limit, embed_query)


def _search_run(run_id: str | None, query: str | None, quadrant: str | None,
                level: str | None, limit: int, embed_query) -> list[dict]:
    """Search one run: by meaning when the run is embedded, else by text."""
    k = clamp_limit(limit, MAX_TRENDS)
    run_id = run_id or _latest_run()
    if not run_id:
        return []

    if query and embed_query is not None:
        try:
            hits = _semantic_trends(query, quadrant, level, k, embed_query, run_id)
        except Exception:
            hits = None
        if hits:
            for r in hits:
                if isinstance(r.get("metrics"), str):
                    r["metrics"] = json.loads(r["metrics"])
            return hits

    params: dict = {"k": k, "run": run_id}
    clauses = ["TRUE"]
    if level:
        clauses.append("level = %(level)s")
        params["level"] = level
    if quadrant:
        clauses.append("quadrant = %(quadrant)s")
        params["quadrant"] = quadrant
    if query:
        clauses.append("(name ILIKE %(q)s OR narrative->>'summary' ILIKE %(q)s)")
        params["q"] = f"%{query}%"
    sql = f"""
        SELECT trend_id, name, level, quadrant, post_count, unique_authors,
               volume_index, growth_index, country, narrative->>'summary' AS summary,
               metrics
        FROM realestate_intel.trends
        WHERE run_id = %(run)s
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


def _trends_by_country(query: str | None, quadrant: str | None, level: str | None,
                       limit: int, countries: list[str] | None,
                       embed_query=None) -> list[dict]:
    """Trends ranked by where their posts are, rather than by how big they are.

    Ordering by raw overlap returns the corpus's biggest trends to every filter
    alike, because a big enough trend overlaps everything. Share is the finding.

    Geography carries a second number. Country is unknown on most community
    posts, so a share taken over the whole trend understates it and a share
    taken over attributed posts alone hides how little was attributable. Both
    ship: country_share_pct over attributed posts, country_coverage_pct saying
    how much of the trend that was.
    """
    k = clamp_limit(limit, MAX_TRENDS)
    params: dict = {"k": k}

    cand = ["t.member_posts IS NOT NULL", "t.run_id = latest.run_id"]
    if level:
        cand.append("t.level = %(level)s")
        params["level"] = level
    if quadrant:
        cand.append("t.quadrant = %(quadrant)s")
        params["quadrant"] = quadrant

    embed_join = ""
    margin_filter = ""
    distance_col = ""
    if query:
        params["q"] = f"%{query}%"
        vec = _query_vector(query, embed_query) if embed_query else None
        if vec is not None and not _run_has_trend_embeddings():
            # Same guard _semantic_trends applies. Without it the INNER JOIN on
            # trend_embedding returns nothing whenever the current run has not
            # been embedded - which is the default state, because embedding is a
            # separate command rather than a pipeline stage. The country search
            # then answered "no trends in that country" for a stale-data fault.
            vec = None
        if vec is not None:
            params["vec"] = vec
            params["tag"] = _embed_tag()
            params["max_dist"] = SEMANTIC_MAX_DISTANCE
            params["margin"] = SEMANTIC_MARGIN
            embed_join = """
                JOIN realestate_intel.trend_embedding te
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

    if countries:
        params["countries"] = list(countries)
        params["floor"] = COUNTRY_TREND_FLOOR
        params["min_coverage"] = MIN_COUNTRY_COVERAGE_PCT
        params["min_share"] = MIN_COUNTRY_SHARE_PCT
        counts = """count(*) FILTER (WHERE country = ANY(%(countries)s)) AS in_country,
                   count(*) FILTER (WHERE country IS NOT NULL) AS attributed,"""
        having = """a.in_country >= %(floor)s
                    AND (100.0 * a.attributed / NULLIF(a.matched, 0)) >= %(min_coverage)s
                    AND (100.0 * a.in_country / NULLIF(a.attributed, 0)) >= %(min_share)s"""
        extra_cols = """,
               a.in_country AS country_posts,
               round(100.0 * a.in_country / NULLIF(a.attributed, 0), 1) AS country_share_pct,
               round(100.0 * a.attributed / NULLIF(a.matched, 0), 1) AS country_coverage_pct"""
        order = "ORDER BY country_share_pct DESC NULLS LAST, a.in_country DESC"
    else:
        params["floor"] = COUNTRY_TREND_FLOOR
        counts = ""
        having = "a.matched >= %(floor)s"
        extra_cols = ""
        order = "ORDER BY a.matched DESC"

    if countries:
        member_join = """
            SELECT c.trend_id, p.country
            FROM candidates c,
                 LATERAL jsonb_array_elements(c.member_posts) mp
            JOIN realestate_intel.trend_posts p
              ON p.platform = mp->>'platform' AND p.post_id = mp->>'post_id'
"""

    sql = f"""
        WITH latest AS (
            SELECT run_id FROM realestate_intel.trends WHERE country IS NULL ORDER BY created_at DESC LIMIT 1
        ), scored AS (
            SELECT t.trend_id, t.member_posts{distance_col}
            FROM realestate_intel.trends t
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
               t.narrative->>'summary' AS summary, t.metrics{extra_cols}
        FROM realestate_intel.trends t
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
    assistant reached for get_brand_profile - which returns themes, offerings
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
                SELECT run_id FROM realestate_intel.trends WHERE country IS NULL ORDER BY created_at DESC LIMIT 1
            ), cand AS (
                SELECT t.trend_id, t.name, t.quadrant, t.post_count,
                       t.volume_index, t.growth_index,
                       t.narrative->>'summary' AS summary, t.member_posts
                FROM realestate_intel.trends t, latest
                WHERE t.run_id = latest.run_id AND t.member_posts IS NOT NULL
            ), hits AS (
                SELECT c.trend_id, pa.brand_name,
                       count(*) AS brand_posts,
                       count(DISTINCT pa.account_username) AS brand_accounts
                FROM cand c,
                     LATERAL jsonb_array_elements(c.member_posts) mp
                JOIN realestate_intel.post_analysis pa
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


TOPIC_POOL = 300
TOPIC_MAX_DISTANCE = 0.60


def developers_by_topic(query_vector: list[float], countries: list[str] | None = None,
                        limit: int = 10) -> list[dict]:
    """Developers whose own posts are closest to a topic, with example posts."""
    from services.trends_real_estate_service.app.core.config import get_settings
    settings = get_settings()
    tag = store.model_tag(settings.TREND_EMBED_MODEL, settings.TREND_EMBED_DIM)
    params = {"tag": tag, "k": TOPIC_POOL, "max_dist": TOPIC_MAX_DISTANCE,
              "vec": "[" + ",".join(f"{v:.6f}" for v in query_vector) + "]"}
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = '40s'")
        cur.execute(f"SET LOCAL hnsw.ef_search = {_ef_search(TOPIC_POOL)}")
        cur.execute("""
            SELECT e.platform, e.post_id, (e.embedding <=> %(vec)s::vector) AS distance
            FROM realestate_intel.post_embedding e
            JOIN realestate_intel.post_source ps
              ON ps.platform = e.platform AND ps.post_id = e.post_id
            WHERE e.model = %(tag)s AND ps.source = 'brand'
            ORDER BY e.embedding <=> %(vec)s::vector, e.platform, e.post_id
            LIMIT %(k)s
        """, params)
        near = {(pl, pid): d for pl, pid, d in cur.fetchall()
                if d is not None and d <= TOPIC_MAX_DISTANCE}
        if not near:
            return []
        where = ""
        params["ids"] = tuple(near)
        if countries:
            where = " AND p.country = ANY(%(countries)s)"
            params["countries"] = list(countries)
        cur.execute(f"""
            SELECT pa.brand_name, p.platform, p.post_id, p.caption, p.post_url,
                   p.author_username, p.country, p.engagement_total
            FROM realestate_intel.post_analysis pa
            JOIN realestate_intel.trend_posts p
              ON p.platform = pa.platform AND p.post_id = pa.post_id
            WHERE (pa.platform, pa.post_id) IN %(ids)s
              AND pa.brand_name IS NOT NULL AND pa.brand_name NOT ILIKE 'consumers'{where}
        """, params)
        rows = _rows(cur)
    by_brand: dict[str, dict] = {}
    for r in sorted(rows, key=lambda r: near[(r["platform"], r["post_id"])]):
        slot = by_brand.setdefault(r["brand_name"], {
            "developer": r["brand_name"], "country": r["country"],
            "matching_posts": 0, "accounts": set(), "example_posts": []})
        slot["matching_posts"] += 1
        slot["accounts"].add(r["author_username"])
        if len(slot["example_posts"]) < 3:
            slot["example_posts"].append({
                "author": r["author_username"], "platform": r["platform"],
                "caption": " ".join((r["caption"] or "").split())[:280],
                "post_url": r["post_url"],
                "distance": round(near[(r["platform"], r["post_id"])], 3)})
    out = sorted(by_brand.values(), key=lambda s: -s["matching_posts"])
    for s in out:
        s["accounts"] = sorted(a for a in s["accounts"] if a)
    return out[:clamp_limit(limit, MAX_TRENDS)]


def developers_in_trend(trend_id: str, limit: int = 15,
                        countries: list[str] | None = None) -> list[dict]:
    """Developers whose posts are members of one trend, with example posts."""
    country_filter = " AND p.country = ANY(%(countries)s)" if countries else ""
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = '60s'")
        cur.execute("""
            WITH current_runs AS (
                SELECT DISTINCT ON (country) run_id FROM realestate_intel.trends
                 ORDER BY country, created_at DESC
            ), t AS (
                SELECT trend_id, name, post_count, member_posts, country
                FROM realestate_intel.trends
                WHERE run_id IN (SELECT run_id FROM current_runs)
                  AND member_posts IS NOT NULL
                  AND (trend_id = %(id)s OR name ILIKE %(id)s
                       OR regexp_replace(split_part(trend_id, '--', 1), '^[uc]-', '')
                  = regexp_replace(split_part(%(id)s, '--', 1), '^[uc]-', ''))
                ORDER BY (trend_id = %(id)s) DESC, (country IS NULL) DESC
                LIMIT 1
            ), m AS (
                SELECT t.trend_id, t.name AS trend_name, t.post_count, pa.brand_name,
                       t.country AS trend_country, p.country,
                       p.author_username, p.caption, p.post_url, p.engagement_total
                FROM t, LATERAL jsonb_array_elements(t.member_posts) mp
                JOIN realestate_intel.post_analysis pa
                  ON pa.platform = mp->>'platform' AND pa.post_id = mp->>'post_id'
                JOIN realestate_intel.trend_posts p
                  ON p.platform = pa.platform AND p.post_id = pa.post_id
                WHERE pa.brand_name IS NOT NULL AND pa.brand_name NOT ILIKE 'consumers'
                  {country_filter}
            )
            SELECT brand_name AS developer,
                   mode() WITHIN GROUP (ORDER BY country) AS developer_country,
                   coalesce(max(trend_country), 'all markets') AS trend_market,
                   max(trend_id) AS trend_id,
                   max(trend_name) AS trend_name, max(post_count) AS trend_posts,
                   count(*) AS developer_posts,
                   round(100.0 * count(*) / NULLIF(max(post_count), 0), 1) AS share_pct,
                   jsonb_agg(jsonb_build_object(
                       'author', author_username, 'caption', left(caption, 280),
                       'post_url', post_url)
                       ORDER BY engagement_total DESC NULLS LAST) AS posts
            FROM m GROUP BY brand_name
            ORDER BY developer_posts DESC
            LIMIT %(k)s
        """.replace("{country_filter}", country_filter),
            {"id": trend_id, "k": clamp_limit(limit, MAX_TRENDS),
             "countries": list(countries) if countries else None})
        rows = _rows(cur)
    for r in rows:
        posts = r.pop("posts") or []
        if isinstance(posts, str):
            posts = json.loads(posts)
        r["example_posts"] = posts[:2]
    return rows


def get_trend(trend_id: str) -> dict | None:
    """One trend in full: headline metrics, weekly timeline, source mix.

    Matches on trend_id, and falls back to an exact name match because the model
    is told to pass the id but sometimes has only the display name.
    """
    # Any market's current run, not only the all-markets one: a trend found by
    # a KSA search lives in the KSA run, and the follow-up "tell me more about
    # it" must find it there. An id match beats a name match, and on a name
    # the all-markets trend wins.
    sql = """
        WITH current_runs AS (
            SELECT DISTINCT ON (country) run_id FROM realestate_intel.trends
             ORDER BY country, created_at DESC
        )
        SELECT trend_id, name, quadrant, level, post_count, unique_authors,
               volume_index, growth_index, origin, source_query, country,
               narrative->>'summary' AS summary,
               narrative->'keywords' AS keywords,
               narrative->'related_themes' AS related_themes,
               narrative->'offering_entities' AS offering_entities,
               metrics, timeline, example_posts
        FROM realestate_intel.trends
        WHERE run_id IN (SELECT run_id FROM current_runs)
          AND (trend_id = %(id)s OR name ILIKE %(id)s
               OR regexp_replace(split_part(trend_id, '--', 1), '^[uc]-', '')
                  = regexp_replace(split_part(%(id)s, '--', 1), '^[uc]-', ''))
        ORDER BY (trend_id = %(id)s) DESC, (country IS NULL) DESC
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
    for key in ("keywords", "related_themes", "offering_entities",
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
        FROM realestate_intel.trend_posts p
        WHERE TRUE{where}
        GROUP BY 1
        HAVING {label} IS NOT NULL
        ORDER BY {"1 ASC" if group_by == "month" else "2 DESC NULLS LAST"}
        LIMIT {200 if group_by == "month" else 40}
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


def list_brands(limit: int = 30, countries: list[str] | None = None) -> list[dict]:
    """The tracked accounts and how much of each is analysed.

    Read from post_analysis rather than the brand tables: this answers "which
    brands can you actually tell me about", and a brand with no analysed posts
    cannot be reported on however it is registered elsewhere.
    """
    sql = """
        SELECT pa.brand_key, max(pa.brand_name) AS brand_name,
               count(*) AS analysed_posts,
               count(DISTINCT pa.account_username) AS accounts,
               max(pa.account_type) AS account_type,
               mode() WITHIN GROUP (ORDER BY bp.country) AS country
        FROM realestate_intel.post_analysis pa
        LEFT JOIN realestate_intel.brand_posts bp
          ON bp.platform = pa.platform AND bp.post_id = pa.post_id
        WHERE pa.brand_key IS NOT NULL
        GROUP BY pa.brand_key
        HAVING %(countries)s::text[] IS NULL
            OR mode() WITHIN GROUP (ORDER BY bp.country) = ANY(%(countries)s::text[])
        ORDER BY analysed_posts DESC
        LIMIT %(k)s
    """
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = '30s'")
        cur.execute(sql, {"k": clamp_limit(limit, 100),
                          "countries": list(countries) if countries else None})
        return _rows(cur)


def get_brand_profile(brand: str, limit: int = 40) -> dict | None:
    """What a brand talks about, aggregated from its analysed posts.

    Themes and offerings are counted across posts rather than summarised by a
    model, so the assistant reports how often a subject actually appears.
    """
    sql = """
        SELECT brand_name, account_username, platform, caption, language,
               engagement_total, posted_at, post_url, analysis
        FROM realestate_intel.post_analysis
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
    offerings: dict[str, int] = {}
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
        for offering in analysis.get("offering_focus") or []:
            name = (offering.get("offering") or "").strip()
            if name:
                offerings[name] = offerings.get(name, 0) + 1
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
        "offerings": [{"offering": o, "posts": n}
                      for o, n in sorted(offerings.items(), key=lambda kv: -kv[1])[:12]],
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
        FROM realestate_intel.trends
        WHERE run_id = (SELECT run_id FROM realestate_intel.trends
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
    pre-fetch would attach relevant posts to a question about bitcoin and make an
    out-of-scope question look answerable. The distance cut is what keeps
    "I have no data" reachable.
    """
    from services.trends_real_estate_service.app.core.config import get_settings
    settings = get_settings()
    tag = store.model_tag(settings.TREND_EMBED_MODEL, settings.TREND_EMBED_DIM)
    ann = """
        SELECT e.platform, e.post_id, (e.embedding <=> %(vec)s::vector) AS distance
        FROM realestate_intel.post_embedding e
        WHERE e.model = %(tag)s
        ORDER BY e.embedding <=> %(vec)s::vector, e.platform, e.post_id
        LIMIT %(k)s
    """
    k = clamp_limit(limit, MAX_POSTS)
    params = {"tag": tag, "k": k,
              "vec": "[" + ",".join(f"{v:.6f}" for v in query_vector) + "]"}
    ef_search = _ef_search(k)
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute(f"SET LOCAL statement_timeout = '30s'; "
                    f"SET LOCAL hnsw.ef_search = {ef_search};" + ann, params)
        near = [(pl, pid, dist) for pl, pid, dist in cur.fetchall()
                if dist is not None and dist <= max_distance]
        if not near:
            return []
        cur.execute("""SELECT p.platform, p.post_id, p.source, p.caption,
                              p.author_username, p.post_url, p.engagement_total
                       FROM realestate_intel.trend_posts p
                       WHERE (p.platform, p.post_id) IN %s""",
                    (tuple((pl, pid) for pl, pid, _ in near),))
        meta = {(r["platform"], r["post_id"]): r for r in _rows(cur)}
    out = []
    for platform, post_id, distance in near:
        row = meta.get((platform, post_id))
        if row:
            out.append({**row, "distance": distance})
    return out
