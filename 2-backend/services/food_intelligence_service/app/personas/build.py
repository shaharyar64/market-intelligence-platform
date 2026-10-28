"""Turn a persona definition into a measured region of the corpus.

The definition is prose. Prose does not sit where posts sit: embedding the
paragraph directly puts it 0.40-0.61 away from its own best matches, and that
distance varies per persona with how long and how abstract the writing is - so a
shared cut-off would mean something different for each one. The fix is the same
two-pass move adhoc.build uses for trends: find the definition's nearest posts,
average *their* vectors, and treat that as the persona. Recentred, the same four
personas land at 0.13-0.33 on one shared scale.

RADIUS was then read off the corpus rather than guessed, by reading posts in
bands outwards from the centre. Health Conscious at 0.33-0.42 is weight-loss
recipes, protein swaps and balanced-diet plans in Arabic and English; by
0.46-0.48 it is any salad; at 0.50 it is a late-night grocery run and a Ramadan
restaurant menu, which is a food post but not this persona's. 0.45 is the last
cut where a stranger reading the posts would still agree they belong together.

Membership is materialised into persona_post because the alternative is scanning
360k vectors per question. The scan is exact - no ANN, no recall loss - which is
affordable exactly once, when the persona is built.
"""
import logging
from datetime import date, timedelta
from decimal import Decimal

import numpy as np

from services.food_intelligence_service.app.core.config import get_settings
from services.food_intelligence_service.app.personas import store as pstore
from services.food_intelligence_service.app.trends import adhoc, store

logger = logging.getLogger("personas.build")

RADIUS = 0.45
SEED_NEIGHBOURS = 300      # first pass, to locate the region
CENTROID_POSTS = 120       # averaged into the centroid
MIN_MEMBERS = 200          # below this a persona is too thin to report on
WINDOW_DAYS = 30


def ensure_membership_table() -> None:
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS food_intel.persona_post (
                persona_id text NOT NULL,
                platform   text NOT NULL,
                post_id    text NOT NULL,
                distance   real NOT NULL,
                PRIMARY KEY (persona_id, platform, post_id)
            )
        """)
        cur.execute("""CREATE INDEX IF NOT EXISTS persona_post_by_persona
                       ON food_intel.persona_post (persona_id, distance)""")


def centroid_for(definition: str, embed_query, tag: str):
    """Where this definition actually lives in the corpus."""
    seed = np.array(embed_query(definition), dtype=np.float32)
    hits = adhoc._neighbours(seed, tag, SEED_NEIGHBOURS)
    if not hits:
        return None
    vectors = adhoc._embeddings_for(hits[:CENTROID_POSTS], tag)
    if not vectors:
        return None
    return np.mean(np.stack(list(vectors.values())), axis=0)


def _write_members(persona_id: str, centroid, tag: str, radius: float) -> int:
    """Exact scan of every food post, membership rewritten in one transaction.

    Delete-then-insert rather than upsert: a refreshed centroid moves, and posts
    that fall outside the new region have to leave. An upsert would keep them
    forever and the persona could only ever grow.
    """
    literal = adhoc._vector_literal(centroid)
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = '600s'")
        cur.execute("DELETE FROM food_intel.persona_post WHERE persona_id = %s",
                    (persona_id,))
        cur.execute("""
            INSERT INTO food_intel.persona_post (persona_id, platform, post_id, distance)
            SELECT %(pid)s, e.platform, e.post_id, (e.embedding <=> %(vec)s::vector)
            FROM food_intel.post_embedding e
            JOIN food_intel.post_food f
              ON f.platform = e.platform AND f.post_id = e.post_id AND f.is_food
            WHERE e.model = %(tag)s
              AND (e.embedding <=> %(vec)s::vector) <= %(radius)s
        """, {"pid": persona_id, "vec": literal, "tag": tag, "radius": radius})
        return cur.rowcount


def _plain(value):
    """psycopg2 returns sum() as Decimal, which json.dumps refuses. The stats go
    into a jsonb column, so every number has to survive the trip."""
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_plain(v) for v in value]
    return value


def _stats(persona_id: str) -> dict:
    """What the corpus says about this region. Every number here is counted."""
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = '300s'")
        cur.execute("""
            SELECT count(*) AS post_count,
                   count(DISTINCT p.author_username) AS unique_authors,
                   min(p.posted_at)::date AS first_post,
                   max(p.posted_at)::date AS last_post,
                   sum(p.engagement_total) AS total_engagement
            FROM food_intel.persona_post m
            JOIN food_intel.trend_posts p
              ON p.platform = m.platform AND p.post_id = m.post_id
            WHERE m.persona_id = %s
        """, (persona_id,))
        base = dict(zip([d[0] for d in cur.description], cur.fetchone()))

        # Carried with the persona so nobody has to derive it. Personas overlap,
        # so the only correct denominator is the food corpus - adding personas
        # together counts the posts in two of them twice.
        cur.execute("SELECT count(*) FROM food_intel.post_food WHERE is_food")
        base["food_posts_in_corpus"] = cur.fetchone()[0]
        if base["food_posts_in_corpus"] and base["post_count"]:
            base["share_of_food_posts_pct"] = round(
                100.0 * base["post_count"] / base["food_posts_in_corpus"], 2)

        cur.execute("""
            SELECT p.source, count(*) FROM food_intel.persona_post m
            JOIN food_intel.trend_posts p
              ON p.platform = m.platform AND p.post_id = m.post_id
            WHERE m.persona_id = %s GROUP BY 1
        """, (persona_id,))
        base["source_mix"] = {r[0]: r[1] for r in cur.fetchall()}

        cur.execute("""
            SELECT p.platform, count(*) FROM food_intel.persona_post m
            JOIN food_intel.trend_posts p
              ON p.platform = m.platform AND p.post_id = m.post_id
            WHERE m.persona_id = %s GROUP BY 1
        """, (persona_id,))
        base["platform_mix"] = {r[0]: r[1] for r in cur.fetchall()}

        cur.execute("""
            SELECT tag, count(*) c FROM food_intel.persona_post m
            JOIN food_intel.trend_posts p
              ON p.platform = m.platform AND p.post_id = m.post_id,
            LATERAL unnest(p.hashtags) tag
            WHERE m.persona_id = %s AND length(tag) > 2
            GROUP BY 1 ORDER BY c DESC LIMIT 15
        """, (persona_id,))
        base["top_hashtags"] = [{"tag": r[0], "posts": r[1]} for r in cur.fetchall()]

        # The visual axes come from the enrichment, which covers a sample rather
        # than the whole corpus, so the sample size travels with the numbers.
        cur.execute("""
            SELECT count(*),
                   avg((a.analysis->'semiotic'->'visual'->>'healthy')::float),
                   avg((a.analysis->'semiotic'->'visual'->>'indulgent')::float),
                   avg((a.analysis->'semiotic'->'visual'->>'premium')::float),
                   avg((a.analysis->'semiotic'->'visual'->>'natural')::float),
                   avg((a.analysis->'semiotic'->'visual'->>'traditional')::float),
                   avg((a.analysis->'semiotic'->'visual'->>'modern')::float)
            FROM food_intel.persona_post m
            JOIN food_intel.post_analysis a
              ON a.platform = m.platform AND a.post_id = m.post_id
            WHERE m.persona_id = %s
              AND a.analysis->'semiotic'->'visual' IS NOT NULL
        """, (persona_id,))
        row = cur.fetchone()
        if row and row[0]:
            axes = ["healthy", "indulgent", "premium", "natural", "traditional", "modern"]
            base["visual"] = {"analysed_posts": row[0],
                              **{a: round(v, 3) for a, v in zip(axes, row[1:])
                                 if v is not None}}

        cur.execute("""
            SELECT p.caption, p.author_username, p.source, p.engagement_total,
                   p.post_url, m.distance
            FROM food_intel.persona_post m
            JOIN food_intel.trend_posts p
              ON p.platform = m.platform AND p.post_id = m.post_id
            WHERE m.persona_id = %s AND p.caption IS NOT NULL
              AND length(p.caption) > 40
            ORDER BY m.distance LIMIT 6
        """, (persona_id,))
        base["examples"] = [
            {"caption": " ".join((r[0] or "").split())[:260], "author": r[1],
             "source": r[2], "engagement": r[3], "post_url": r[4],
             "distance": round(float(r[5]), 3)}
            for r in cur.fetchall()]
    return _plain(base)


def _growth(persona_id: str, as_of: date) -> dict:
    """Posts in the last window against the one before it.

    Both windows are reported rather than a single percentage: a change in this
    corpus measures collection timing as much as it measures the market, and a
    reader who can see the base can tell the difference.
    """
    prev_start = as_of - timedelta(days=WINDOW_DAYS * 2)
    mid = as_of - timedelta(days=WINDOW_DAYS)
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT count(*) FILTER (WHERE p.posted_at::date > %(mid)s),
                   count(*) FILTER (WHERE p.posted_at::date > %(prev)s
                                      AND p.posted_at::date <= %(mid)s)
            FROM food_intel.persona_post m
            JOIN food_intel.trend_posts p
              ON p.platform = m.platform AND p.post_id = m.post_id
            WHERE m.persona_id = %(pid)s AND p.posted_at IS NOT NULL
        """, {"pid": persona_id, "mid": mid, "prev": prev_start})
        recent, previous = cur.fetchone()
    return {"window_days": WINDOW_DAYS, "as_of": as_of.isoformat(),
            "recent_posts": recent, "previous_posts": previous}


def top_trends(persona_id: str, limit: int = 8) -> list[dict]:
    """Which trends this persona's posts fall into.

    Ranked by the share of the *trend* that belongs to this persona, not by raw
    overlap: rank by overlap and every persona returns the same list, because
    the biggest trends overlap everything. A floor keeps out trends where the
    share is arithmetic rather than evidence.
    """
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = '300s'")
        cur.execute("""
            WITH members AS (
                SELECT platform, post_id FROM food_intel.persona_post
                WHERE persona_id = %s
            ), expanded AS (
                SELECT t.trend_id, t.name, t.post_count, t.quadrant,
                       mp->>'platform' AS platform, mp->>'post_id' AS post_id
                FROM food_intel.trends t,
                     LATERAL jsonb_array_elements(t.member_posts) mp
                WHERE t.member_posts IS NOT NULL AND t.level = 'micro'
                  -- Superseded runs are still in the table. Without this the
                  -- same trend comes back once per run it appeared in, which
                  -- reads as two findings and is one.
                  AND t.run_id = (SELECT run_id FROM food_intel.trends
                                  WHERE country IS NULL
                                  ORDER BY created_at DESC LIMIT 1)
            )
            SELECT e.trend_id, e.name, e.quadrant, e.post_count, count(*) AS shared
            FROM expanded e
            JOIN members m ON m.platform = e.platform AND m.post_id = e.post_id
            GROUP BY 1,2,3,4
            HAVING count(*) >= 15
            ORDER BY (count(*)::float / NULLIF(e.post_count, 0)) DESC, shared DESC
            LIMIT %s
        """, (persona_id, limit))
        return [{"trend_id": r[0], "name": r[1], "quadrant": r[2],
                 "trend_post_count": r[3], "persona_posts": r[4],
                 "share_of_trend": round(100.0 * r[4] / r[3], 1) if r[3] else None}
                for r in cur.fetchall()]


def refresh_stats(persona_id: str) -> dict | None:
    """Recompute what the corpus says, reusing the centroid and membership.

    Separate from build() because the two go stale for different reasons: the
    centroid only needs redoing if the definition changes, while the stats go
    stale every time posts, trends or enrichment move underneath them.
    """
    persona = pstore.get(persona_id)
    if not persona:
        return None
    stats = _stats(persona_id)
    if not stats.get("post_count"):
        return None
    as_of = stats.get("last_post") or date.today()
    stats["growth"] = _growth(persona_id, as_of)
    stats["radius"] = persona.get("radius") or RADIUS
    stats["trends"] = top_trends(persona_id)
    for key in ("first_post", "last_post"):
        if stats.get(key):
            stats[key] = stats[key].isoformat()
    centroid, _ = pstore.centroid_of(persona_id)
    settings = get_settings()
    pstore.upsert({
        "persona_id": persona_id, "name": persona["name"],
        "tagline": persona.get("tagline"), "definition": persona["definition"],
        "motivations": persona.get("motivations") or [],
        "priorities": persona.get("priorities") or [],
        "behaviors": persona.get("behaviors") or [],
        "centroid": "[" + ",".join(f"{v:.6f}" for v in centroid) + "]",
        "model": store.model_tag(settings.TREND_EMBED_MODEL, settings.TREND_EMBED_DIM),
        "radius": persona.get("radius") or RADIUS, "stats": stats,
        "origin": persona.get("origin") or "seed", "created_by": None,
    })
    return stats


def build(seed: dict, embed_query, origin: str = "seed",
          created_by: str | None = None) -> dict | None:
    """Measure one persona and store it. Returns the stored stats, or None."""
    settings = get_settings()
    tag = store.model_tag(settings.TREND_EMBED_MODEL, settings.TREND_EMBED_DIM)
    ensure_membership_table()
    pstore.ensure_table()

    centroid = centroid_for(seed["definition"], embed_query, tag)
    if centroid is None:
        logger.warning("no neighbours for persona %s", seed["persona_id"])
        return None

    written = _write_members(seed["persona_id"], centroid, tag, RADIUS)
    if written < MIN_MEMBERS:
        logger.info("persona %s matched only %s posts", seed["persona_id"], written)
        return None

    stats = _stats(seed["persona_id"])
    as_of = stats.get("last_post") or date.today()
    stats["growth"] = _growth(seed["persona_id"], as_of)
    stats["radius"] = RADIUS
    stats["trends"] = top_trends(seed["persona_id"])
    for key in ("first_post", "last_post"):
        if stats.get(key):
            stats[key] = stats[key].isoformat()

    pstore.upsert({
        "persona_id": seed["persona_id"], "name": seed["name"],
        "tagline": seed.get("tagline"), "definition": seed["definition"],
        "motivations": seed.get("motivations") or [],
        "priorities": seed.get("priorities") or [],
        "behaviors": seed.get("behaviors") or [],
        "centroid": adhoc._vector_literal(centroid), "model": tag,
        "radius": RADIUS, "stats": stats, "origin": origin,
        "created_by": created_by,
    })
    return stats
