"""Build one trend on demand, from a question instead of from clustering.

The batch pipeline discovers trends bottom-up: cluster the corpus, then name
whatever falls out. This does the opposite - the user names the thing first and
the corpus is searched for it. Both write the same row into food_intel.trends,
which is the whole design constraint here: the explorer, the detail view, the
date-range recompute and the assistant's own tools all read that table, and they
work on an ad-hoc trend without a single change only if its shape and its
arithmetic match a pipeline trend's exactly.

Three things that are easy to get wrong, and what is done about them:

Ranking. `volume_index` and `growth_index` are percentile ranks *within a run* -
`metrics.percentile_index` over a set of one returns 50.0, so a trend built
alone would always report itself as precisely average. Here the raw volume and
growth are ranked into the live run's existing distribution, so "84th
percentile" means the same thing on both kinds of trend.

Retrieval. A query is short English; the corpus is mostly long Arabic captions.
Nearest neighbours of the query text alone skew to whatever happens to be
phrased like the query. So the query's own hits are used to compute a centroid,
and the neighbourhood is searched again around that - the topic's centre rather
than the question's wording.

Refusal. Vector search always returns something. Without a distance gate and a
floor on the number of posts, asking for a trend about bitcoin would produce a
confident, entirely fictional food trend. Below either threshold this returns
None and the caller says it found nothing.
"""
import hashlib
import logging
import re
import unicodedata
from datetime import date, datetime

import numpy as np

from services.food_intelligence_service.app.core.config import get_settings
from services.food_intelligence_service.app.trends import metrics, store

logger = logging.getLogger("trends.adhoc")

# Calibrated on the same scale the assistant's context retrieval uses: in-scope
# questions land at 0.22-0.36 and off-topic ones at 0.60 and beyond. This sits
# just below that gap.
MAX_DISTANCE = 0.52
MIN_POSTS = 12
CANDIDATES = 400
EF_SEARCH = 400

ORIGIN = "chat"


def _slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return (text or "trend")[:48]


def _vector_literal(vec) -> str:
    return "[" + ",".join(f"{float(v):.6f}" for v in vec) + "]"


def _neighbours(vec, tag: str, limit: int) -> list[dict]:
    """Nearest food posts to a vector, with everything the metrics need.

    Runs against the base tables rather than the trend_posts view: ordering by
    distance through a UNION view cannot use the HNSW index (it has to build the
    union before it can sort), which is a timeout rather than a slow query.
    """
    near_sql = """
        SELECT e.platform, e.post_id, (e.embedding <=> %(vec)s::vector) AS distance
        FROM food_intel.post_embedding e
        JOIN food_intel.post_food f
          ON f.platform = e.platform AND f.post_id = e.post_id AND f.is_food
        WHERE e.model = %(tag)s
        ORDER BY e.embedding <=> %(vec)s::vector
        LIMIT %(k)s
    """
    posts_sql = """
        SELECT p.platform, p.post_id, p.source, p.caption, p.hashtags, p.posted_at,
               p.author_username, p.engagement_total, p.likes, p.comments, p.views,
               p.media_keys, p.post_url
        FROM food_intel.trend_posts p
        WHERE p.platform = ANY(%(platforms)s::text[]) AND p.post_id = ANY(%(ids)s::text[])
          AND p.posted_at IS NOT NULL
    """
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = '60s'")
        cur.execute(f"SET LOCAL hnsw.ef_search = {EF_SEARCH}")
        cur.execute(near_sql, {"vec": _vector_literal(vec), "tag": tag, "k": limit})
        distance = {(r[0], r[1]): r[2] for r in cur.fetchall()}
        if not distance:
            return []
        cur.execute(posts_sql, {"platforms": sorted({p for p, _ in distance}),
                                "ids": sorted({i for _, i in distance})})
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    rows = [{**r, "distance": distance[(r["platform"], r["post_id"])]} for r in rows
            if (r["platform"], r["post_id"]) in distance]
    return sorted(rows, key=lambda r: r["distance"])


def _embeddings_for(posts: list[dict], tag: str) -> dict:
    if not posts:
        return {}
    keys = tuple((p["platform"], p["post_id"]) for p in posts)
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""SELECT platform, post_id, embedding::text
                       FROM food_intel.post_embedding
                       WHERE model = %s AND (platform, post_id) IN %s""", (tag, keys))
        return {(r[0], r[1]): np.fromstring(r[2][1:-1], sep=",", dtype=np.float32)
                for r in cur.fetchall()}


def _live_run() -> tuple[str, date, str | None] | tuple[None, None, None]:
    """The run an ad-hoc trend is measured against and ranked inside."""
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""SELECT run_id, metrics->>'as_of', country
                       FROM food_intel.trends
                       WHERE origin = 'pipeline' AND country IS NULL
                       ORDER BY created_at DESC LIMIT 1""")
        row = cur.fetchone()
    if not row:
        return None, None, None
    as_of = None
    if row[1]:
        try:
            as_of = datetime.fromisoformat(row[1]).date()
        except ValueError:
            as_of = None
    return row[0], as_of, row[2]


def _run_totals(run_id: str) -> tuple[int, int, int]:
    """The run's own window totals, so share-of-voice means the same thing here.

    Growth is a change in share of the conversation, not in raw volume, so it
    needs the totals across every trend in the window. Passing the trend's own
    counts as the totals makes both shares 1.0 and every trend report exactly
    0% - which is what happened before this existed.
    """
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""SELECT coalesce(sum((metrics->>'recent_posts')::int), 0),
                              coalesce(sum((metrics->>'previous_posts')::int), 0),
                              count(*)
                       FROM food_intel.trends
                       WHERE run_id = %s AND level = 'micro' AND origin = 'pipeline'""",
                    (run_id,))
        r = cur.fetchone()
    return int(r[0]), int(r[1]), max(int(r[2]), 1)


def _rank_within_run(run_id: str, volume_raw: float, growth_pct: float) -> tuple[float, float]:
    """Where this trend's raw numbers fall among the run's own micro trends.

    Ranking against the live distribution is what makes the index comparable.
    A percentile over a set of one is 50.0 by definition and would say nothing.
    """
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""SELECT (metrics->>'volume_raw')::float,
                              (metrics->>'growth_pct')::float
                       FROM food_intel.trends
                       WHERE run_id = %s AND level = 'micro' AND origin = 'pipeline'""",
                    (run_id,))
        rows = cur.fetchall()
    if not rows:
        return 50.0, 50.0
    volumes = [r[0] for r in rows if r[0] is not None]
    growths = [r[1] for r in rows if r[1] is not None]

    def pct(value: float, population: list[float]) -> float:
        if not population:
            return 50.0
        below = sum(1 for v in population if v < value)
        equal = sum(1 for v in population if v == value)
        return round((below + equal / 2.0) / len(population) * 100.0, 1)

    return pct(volume_raw, volumes), pct(growth_pct, growths)


def build(query: str, embed_query, name: str | None = None,
          created_by: str | None = None, summary: str | None = None) -> dict | None:
    """Retrieve, measure and store one trend for `query`.

    Returns the stored row, or None when the corpus has too little to say —
    which is the honest answer far more often than a generated trend would be.
    """
    settings = get_settings()
    tag = store.model_tag(settings.TREND_EMBED_MODEL, settings.TREND_EMBED_DIM)
    run_id, as_of, run_country = _live_run()
    if not run_id:
        logger.warning("no pipeline run to measure against")
        return None

    seed = np.array(embed_query(query), dtype=np.float32)
    hits = [h for h in _neighbours(seed, tag, CANDIDATES) if h["distance"] <= MAX_DISTANCE]
    if len(hits) < MIN_POSTS:
        logger.info("query %r found only %s posts within %.2f", query, len(hits), MAX_DISTANCE)
        return None

    # Second pass around the centre of what came back, not the wording of the
    # question. Captions are mostly Arabic and queries mostly English, so the
    # first pass finds the topic but under-recalls it.
    vectors = _embeddings_for(hits[:60], tag)
    if vectors:
        centroid = np.mean(np.stack(list(vectors.values())), axis=0)
        merged = {(h["platform"], h["post_id"]): h for h in hits}
        for h in _neighbours(centroid, tag, CANDIDATES):
            if h["distance"] <= MAX_DISTANCE:
                merged.setdefault((h["platform"], h["post_id"]), h)
        hits = sorted(merged.values(), key=lambda h: h["distance"])

    posts = [h for h in hits if h.get("posted_at")]
    if len(posts) < MIN_POSTS:
        return None
    if as_of is None:
        as_of = max(p["posted_at"] for p in posts).date()

    label = (name or query).strip()[:120]
    terms = metrics.topical_terms(label, {"keywords": []})
    facts = metrics._post_facts(posts, as_of, terms)
    # Measured against the run's totals, and counted into them: this trend is
    # one more claimant on the same conversation, so it belongs in the
    # denominator alongside the trends it is being compared with.
    total_recent, total_previous, cohort_size = _run_totals(run_id)
    growth_pct = metrics.compute_growth_pct(
        facts["recent_posts"], facts["previous_posts"],
        total_recent + facts["recent_posts"],
        total_previous + facts["previous_posts"],
        cohort_size + 1)
    volume_index, growth_index = _rank_within_run(run_id, facts["volume_raw"], growth_pct)

    # Deterministic, so asking the same thing twice updates that trend instead
    # of littering the explorer with duplicates. Python's hash() is salted per
    # process and produced a fresh id on every call.
    fingerprint = hashlib.md5(f"{label}|{created_by or ''}".encode()).hexdigest()[:8]
    trend_id = f"c-{_slug(label)}--{fingerprint}"
    row = {
        "trend_id": trend_id,
        "run_id": run_id,
        "level": "micro",
        "parent_trend_id": None,
        "name": label,
        "quadrant": metrics.assign_quadrant(volume_index, growth_index),
        "volume_index": volume_index,
        "growth_index": growth_index,
        "post_count": facts["post_count"],
        "unique_authors": facts["unique_authors"],
        "narrative": {
            "summary": summary or f"Posts retrieved for the question: {query}",
            "related_themes": [], "product_entities": [], "keywords": [],
            "naming_confidence": None,
        },
        "metrics": {
            "volume_raw": facts["volume_raw"],
            "growth_pct": growth_pct,
            "engagement_total": facts["engagement_total"],
            "platform_mix": facts["platform_mix"],
            "source_mix": facts["source_mix"],
            "months": facts["months"],
            "recent_posts": facts["recent_posts"],
            "previous_posts": facts["previous_posts"],
            "first_post": facts["first_post"],
            "is_new": facts["is_new"],
            "as_of": as_of.isoformat(),
            "match_distance": round(float(np.mean([p["distance"] for p in posts])), 4),
        },
        "timeline": facts["timeline"],
        "example_posts": {"top": facts["example_posts"],
                          "by_source": facts["example_posts_by_source"]},
        "member_posts": facts["member_posts"],
        "origin": ORIGIN,
        "created_by": created_by,
        "source_query": query,
        "country": run_country,
    }
    store.upsert_trends([row])
    logger.info("stored ad-hoc trend %s (%s posts, volume p%s, growth p%s)",
                trend_id, facts["post_count"], volume_index, growth_index)
    return row


def similar_existing(query: str, embed_query, limit: int = 3) -> list[dict]:
    """Pipeline trends whose members overlap what this query retrieves.

    Offered so the answer can say "this is already covered by X" instead of
    quietly creating a near-duplicate of a trend the run already found.
    """
    settings = get_settings()
    tag = store.model_tag(settings.TREND_EMBED_MODEL, settings.TREND_EMBED_DIM)
    seed = np.array(embed_query(query), dtype=np.float32)
    hits = [h for h in _neighbours(seed, tag, 120) if h["distance"] <= MAX_DISTANCE]
    if not hits:
        return []
    keys = {(h["platform"], h["post_id"]) for h in hits}
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""SELECT trend_id, name, member_posts
                       FROM food_intel.trends
                       WHERE origin = 'pipeline' AND level = 'micro'
                         AND run_id = (SELECT run_id FROM food_intel.trends
                                       WHERE origin = 'pipeline' AND country IS NULL
                                       ORDER BY created_at DESC LIMIT 1)""")
        rows = cur.fetchall()
    import json
    scored = []
    for tid, tname, mp in rows:
        mp = mp if isinstance(mp, list) else json.loads(mp)
        members = {(m["platform"], m["post_id"]) for m in mp}
        if not members:
            continue
        overlap = len(keys & members)
        if overlap:
            scored.append({"trend_id": tid, "name": tname, "overlap_posts": overlap,
                           "overlap_pct": round(100.0 * overlap / len(keys), 1)})
    scored.sort(key=lambda r: -r["overlap_posts"])
    return scored[:limit]
